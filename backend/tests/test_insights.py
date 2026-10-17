import csv
import io
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import anthropic
import httpx

from app.analytics.alerts import check_alerts
from app.core.config import Settings
from app.db.models import Alert, AlertEvent, Watchlist
from app.insights.drafts import Draft, template_drafts, validate
from app.insights.facts import build_facts
from app.insights.service import generate
from app.ml.sentiment.registry import get_model
from tests.test_analytics import upload

END = date(2026, 9, 21)
MODEL = get_model("lexicon")


def story(client, days: int = 21, skip: tuple[int, ...] = ()) -> None:
    """Poco: two mixed posts a day for two weeks, then six complaints a day. Redmi: one calm post a day.

    Each unbroken run of days is its own upload, since a file counts as collecting every day it spans."""
    runs: list[list[str]] = [[]]
    n = 0
    for day in range(days):
        if day in skip:
            if runs[-1]:
                runs.append([])
            continue
        stamp = f"2026-09-{day + 1:02d}T10:00:00Z"
        complaints = day >= 14
        for i in range(6 if complaints else 2):
            n += 1
            text = (f"Poco support never replied and it is terrible #{i}" if complaints
                    else ("Poco camera is great" if i % 2 else "Poco display is fine"))
            runs[-1].append(f"{n},{stamp},{text},,\n")
        n += 1
        runs[-1].append(f"{n},{stamp},Redmi Note 14 arrived today,,\n")
    for i, rows in enumerate(r for r in runs if r):
        upload(client, f"story{i}", "".join(rows))


def sheet_for(db, watchlist_id):
    return build_facts(db, db.get(Watchlist, uuid.UUID(watchlist_id)), END, MODEL)


# --- facts and templates ---------------------------------------------------------------------------------


def test_fact_sheet_and_template_cards(client, watchlist_id, db_session):
    story(client)
    sheet = sheet_for(db_session, watchlist_id)
    poco = next(t for t in sheet.terms if t.term == "Poco")
    assert (poco.value("mentions"), poco.value("mentions_previous")) == (42, 14)
    assert poco.value("mentions_change") == 2.0
    assert poco.value("trend_code") == "rising_negative"
    assert poco.value("top_negative_topic") == "customer_support"
    assert (sheet.start, sheet.previous_start) == (date(2026, 9, 15), date(2026, 9, 8))

    drafts = template_drafts(sheet)
    card = next(d for d in drafts if d.entity_alias == poco.alias)
    assert card.observation.startswith("Mentions of Poco rose from 14 to 42 (+200%) in the 7 days to Sep 21")
    assert card.interpretation.startswith("Possibly")
    assert card.example_ids and all(e.sentiment == "negative" for e in sheet.examples if e.id in card.example_ids)
    quiet = next(d for d in drafts if d.entity_alias is None)
    assert quiet.observation == "No notable change for Redmi Note 14 (7 mentions) in the 7 days to Sep 21."
    for d in drafts:
        assert validate(d, sheet) == [], d


def test_validator_rejects_unsupported_claims(client, watchlist_id, db_session):
    story(client)
    sheet = sheet_for(db_session, watchlist_id)
    poco = next(t for t in sheet.terms if t.term == "Poco").alias
    good = Draft(poco, "Mentions of Poco rose from 14 to 42 in the 7 days to Sep 21.",
                 [f"{poco}.mentions", f"{poco}.mentions_previous"], "Possibly a support backlog.", "Few days.", "Read the posts.")
    assert validate(good, sheet) == []

    invented = Draft(**{**good.__dict__, "observation": "Mentions of Poco rose 3x to 42, with 35% from one store."})
    problems = validate(invented, sheet)
    assert any("numbers no cited fact supports: 3, 35" in p for p in problems), problems
    # A real number is still rejected when the card doesn't cite the fact it comes from.
    uncited = Draft(**{**good.__dict__, "observation": "Mentions of Poco rose 200% to 42.", "fact_ids": [f"{poco}.mentions"]})
    assert any("supports: 200" in p for p in validate(uncited, sheet))
    assert validate(Draft(**{**uncited.__dict__, "fact_ids": [f"{poco}.mentions", f"{poco}.mentions_change"]}), sheet) == []
    unknown = Draft(**{**good.__dict__, "fact_ids": ["t9.mentions"], "example_ids": ["not-a-post"], "entity_alias": "t9"})
    problems = validate(unknown, sheet)
    assert any("unknown term alias" in p for p in problems)
    assert any("facts that don't exist" in p for p in problems)
    assert any("posts that weren't provided" in p for p in problems)


def test_generate_route_uses_templates_and_stores_cards(client, watchlist_id):
    story(client)
    body = client.post("/api/insights/generate", json={"watchlist_id": watchlist_id}).json()
    assert (body["generator"], body["llm_status"], body["llm_available"]) == ("template", "not_configured", False)
    poco = next(c for c in body["insights"] if c["observation"].startswith("Mentions of Poco"))
    assert poco["period_end"] == "2026-09-21" and poco["evidence"]["comparison"] == {"start": "2026-09-08", "end": "2026-09-14"}
    assert {"id", "label", "value", "unit"} <= set(poco["evidence"]["facts"][0])
    assert poco["evidence"]["examples"][0]["text"].startswith("Poco support never replied")

    # Regenerating the same period replaces the cards rather than piling up duplicates.
    again = client.post("/api/insights/generate", json={"watchlist_id": watchlist_id, "use_llm": False}).json()
    assert again["llm_status"] == "not_requested"
    stored = client.get("/api/insights", params={"watchlist_id": watchlist_id}).json()
    assert len(stored["insights"]) == len(again["insights"])

    assert client.post("/api/insights/generate", json={"watchlist_id": str(uuid.uuid4())}).status_code == 404
    empty = client.post("/api/watchlists", json={"workspace_id": client.get(f"/api/watchlists/{watchlist_id}").json()["workspace_id"],
                                                 "name": "Empty"}).json()
    assert client.post("/api/insights/generate", json={"watchlist_id": empty["id"]}).json()["insights"] == []


# --- model-written insights, with a stand-in client ------------------------------------------------------------


class FakeClient:
    def __init__(self, response=None, error: Exception | None = None):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self._response, self._error = response, error

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._response


def reply(cards: list[dict], stop_reason: str = "end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=json.dumps({"cards": cards}))])


def card(alias: str, observation: str, fact_ids: list[str], examples: list[str] | None = None) -> dict:
    return {"term_alias": alias, "observation": observation, "fact_ids": fact_ids, "example_record_ids": examples or [],
            "interpretation": "Possibly a support backlog.", "caveat": "Based on one source.",
            "suggested_investigation": "Read the customer support posts in Explore."}


def run_llm(db, watchlist_id, client):
    settings = Settings(insights_llm_enabled=True, anthropic_api_key="test-key")
    return generate(db, db.get(Watchlist, uuid.UUID(watchlist_id)), MODEL, settings, client=client)


def test_model_cards_are_validated_and_bad_ones_dropped(client, watchlist_id, db_session):
    story(client)
    sheet = sheet_for(db_session, watchlist_id)
    poco = next(t for t in sheet.terms if t.term == "Poco").alias
    example = next(e.id for e in sheet.examples if e.entity_alias == poco)
    fake = FakeClient(reply([
        card(poco, "Poco mentions tripled to 42 between Sep 15 and Sep 21.", [f"{poco}.mentions", f"{poco}.mentions_change"], [example]),
        card(poco, "Poco mentions rose 4x, to 57.", [f"{poco}.mentions"]),
    ]))
    result = run_llm(db_session, watchlist_id, fake)

    assert (result.generator, result.llm_status) == ("llm", "used")
    assert [c.claim for c in result.cards] == ["Poco mentions tripled to 42 between Sep 15 and Sep 21."]
    assert result.cards[0].model_version == "claude-opus-5-5/ins-1"
    assert result.cards[0].evidence_json["examples"][0]["id"] == example
    assert len(result.rejected) == 1 and "4, 57" in result.rejected[0]["problems"][0]

    sent = fake.calls[0]
    assert sent["model"] == "claude-opus-5-5"
    assert sent["output_config"]["format"]["type"] == "json_schema"
    payload = json.loads(sent["messages"][0]["content"])
    assert {t["alias"] for t in payload["terms"]} == {t.alias for t in sheet.terms}
    # Only aggregates and the selected example posts go to the model: no authors and no other posts.
    assert "author" not in sent["messages"][0]["content"]
    assert len(payload["examples"]) == len(sheet.examples)


def test_model_failures_fall_back_to_templates(client, watchlist_id, db_session):
    story(client)
    poco = next(t for t in sheet_for(db_session, watchlist_id).terms if t.term == "Poco").alias

    refused = run_llm(db_session, watchlist_id, FakeClient(reply([], stop_reason="refusal")))
    assert (refused.generator, refused.llm_status) == ("template", "failed: the model declined the request")
    assert refused.cards

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    down = run_llm(db_session, watchlist_id, FakeClient(error=anthropic.APIConnectionError(request=request)))
    assert down.llm_status == "failed: could not reach the Anthropic API" and down.generator == "template"

    garbage = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="not json")])
    assert run_llm(db_session, watchlist_id, FakeClient(garbage)).llm_status == "failed: the response didn't match the schema"

    all_bad = run_llm(db_session, watchlist_id, FakeClient(reply([card(poco, "Up 999%.", [f"{poco}.mentions"])])))
    assert (all_bad.generator, all_bad.llm_status, len(all_bad.rejected)) == ("template", "all rejected", 1)


# --- alerts --------------------------------------------------------------------------------------------------


def entity(client, watchlist_id, term):
    return next(e["id"] for e in client.get(f"/api/watchlists/{watchlist_id}").json()["entities"] if e["term"] == term)


def test_alert_fires_once_per_day_and_respects_cooldown(client, watchlist_id, db_session):
    story(client, days=20)
    poco = entity(client, watchlist_id, "Poco")
    created = client.post("/api/alerts", json={"entity_id": poco, "rule": {"metric": "daily_mentions", "threshold": 6}})
    assert created.status_code == 201
    alert_id = created.json()["id"]

    now = datetime(2026, 9, 21, 12, tzinfo=UTC)
    fired = check_alerts(db_session, now)
    assert len(fired) == 1
    assert fired[0].message == "Daily mentions for Poco was 6 on 2026-09-20, at or above the 6 threshold."
    assert check_alerts(db_session, now + timedelta(days=3)) == []  # same data day: never twice

    # A new day of data inside the cooldown doesn't fire; after the cooldown it does.
    upload(client, "day21", "900,2026-09-21T10:00:00Z,Poco support never replied,,\n" * 1
           + "".join(f"{901 + i},2026-09-21T11:0{i}:00Z,Poco support still silent {i},,\n" for i in range(6)))
    db_session.query(AlertEvent).delete()  # the upload's own analysis run already checked; start clean
    db_session.get(Alert, uuid.UUID(alert_id)).last_triggered_at = now
    db_session.commit()
    assert check_alerts(db_session, now + timedelta(hours=2)) == []
    assert len(check_alerts(db_session, now + timedelta(days=2))) == 1

    events = client.get("/api/alerts/events", params={"watchlist_id": watchlist_id}).json()
    assert [e["data_date"] for e in events] == ["2026-09-21"] and events[0]["term"] == "Poco"


def test_alerts_ignore_uncollected_days_and_thin_weeks(client, watchlist_id, db_session):
    # Days 15 to 19 were never collected: a weekly rule can't be judged on the week ending day 21.
    story(client, skip=(14, 15, 16, 17, 18))
    poco = entity(client, watchlist_id, "Poco")
    for metric in ("weekly_change", "negative_share"):
        client.post("/api/alerts", json={"entity_id": poco, "rule": {"metric": metric, "threshold": 0}})
    assert check_alerts(db_session, datetime(2026, 9, 22, tzinfo=UTC)) == []

    # A daily rule only ever looks at the last collected day, never at a gap counted as zero.
    redmi = entity(client, watchlist_id, "Redmi Note 14")
    client.post("/api/alerts", json={"entity_id": redmi, "rule": {"metric": "daily_mentions", "threshold": 1}})
    fired = check_alerts(db_session, datetime(2026, 9, 22, tzinfo=UTC))
    assert [(e.data_date, e.value) for e in fired] == [(date(2026, 9, 21), 1.0)]


def test_alert_routes(client, watchlist_id):
    poco = entity(client, watchlist_id, "Poco")
    url = "/api/alerts"
    assert client.post(url, json={"entity_id": poco, "rule": {"metric": "followers", "threshold": 1}}).status_code == 422
    assert client.post(url, json={"entity_id": poco, "rule": {"metric": "trend_score", "threshold": -1}}).status_code == 422
    assert client.post(url, json={"entity_id": poco, "rule": {"metric": "trend_score", "threshold": 70},
                                  "cooldown_minutes": 1}).status_code == 422
    assert client.post(url, json={"entity_id": str(uuid.uuid4()), "rule": {"metric": "trend_score", "threshold": 70}}).status_code == 404

    alert = client.post(url, json={"entity_id": poco, "rule": {"metric": "trend_score", "threshold": 70}}).json()
    assert alert["term"] == "Poco" and alert["active"] and alert["cooldown_minutes"] == 1440
    paused = client.patch(f"{url}/{alert['id']}", json={"active": False}).json()
    assert paused["active"] is False and paused["rule"]["threshold"] == 70
    assert [a["id"] for a in client.get(url, params={"watchlist_id": watchlist_id}).json()] == [alert["id"]]
    assert client.delete(f"{url}/{alert['id']}").status_code == 204
    assert client.get(url, params={"watchlist_id": watchlist_id}).json() == []
    assert client.delete(f"{url}/{alert['id']}").status_code == 404


# --- export --------------------------------------------------------------------------------------------------


def test_daily_export_marks_gaps_and_has_no_post_text(client, watchlist_id):
    upload(client, "a", "1,2026-09-01T08:00:00Z,Redmi Note 14 battery is terrible,5,1\n")
    upload(client, "b", "2,2026-09-03T08:00:00Z,Poco camera is great,,\n")
    response = client.get("/api/export/daily.csv", params={"watchlist_id": watchlist_id, "start": "2026-09-01", "end": "2026-09-03"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="marketpulse-phones-2026-09-01-to-2026-09-03.csv"' in response.headers["content-disposition"]
    assert "terrible" not in response.text

    rows = list(csv.DictReader(io.StringIO(response.text)))
    by = {(r["date"], r["term"]): r for r in rows}
    redmi = by[("2026-09-01", "Redmi Note 14")]
    assert (redmi["mentions"], redmi["engagement"], redmi["negative_share"], redmi["collection"]) == ("1", "6", "1.0", "complete")
    poco_day1 = by[("2026-09-01", "Poco")]
    assert (poco_day1["mentions"], poco_day1["engagement"]) == ("0", "")  # collected, nothing said: a real zero
    gap = by[("2026-09-02", "Poco")]
    assert (gap["collection"], gap["mentions"], gap["source"]) == ("not_collected", "", "")

    params = {"watchlist_id": watchlist_id, "start": "2026-09-03", "end": "2026-09-01"}
    assert client.get("/api/export/daily.csv", params=params).status_code == 422
    assert client.get("/api/export/daily.csv", params={**params, "watchlist_id": str(uuid.uuid4()), "end": "2026-09-04"}).status_code == 404
