import uuid
from datetime import date, timedelta

from app.analytics import trend
from app.db.models import DailyMetric, NlpResult, RecordMatch, TrendSignal
from app.demo.synthetic import GAP, generate

HEADER = "source_record_id,published_at,text,likes,comments\n"


def upload(client, dataset: str, body: str):
    response = client.post("/api/imports/csv", data={"dataset": dataset}, files={"file": ("d.csv", (HEADER + body).encode(), "text/csv")})
    assert response.status_code == 201, response.text
    return response.json()


def point(day: int, mentions: int, positive=0, negative=0, scored=None, engagement=None, eng_records=0, covered=True):
    return trend.DayPoint(
        date=date(2026, 9, 1) + timedelta(days=day), covered=covered, complete=covered, mentions=mentions,
        engagement=engagement, engagement_records=eng_records, positive=positive, negative=negative,
        scored=mentions if scored is None else scored,
    )


# --- trend score -----------------------------------------------------------------------------------------


def test_trend_needs_two_full_windows():
    days = [point(i, 5) for i in range(13)]
    assert trend.compute(days, 12) is None
    assert trend.compute(days + [point(13, 5)], 13) is not None


def test_flat_series_scores_about_fifty_and_drops_missing_components():
    days = [point(i, 10, positive=5, negative=2) for i in range(14)]
    result = trend.compute(days, 13)
    assert result["components"]["mention_growth"]["value"] == 50.0
    assert result["components"]["engagement_growth"]["value"] is None
    assert result["components"]["persistence"]["value"] is None  # no history before the windows
    weights = {k: c["weight"] for k, c in result["components"].items()}
    assert weights["engagement_growth"] == 0 and abs(sum(weights.values()) - 1) < 0.01
    assert result["explanation_code"] == "stable"
    assert result["confidence"] == "high"


def test_growth_from_near_zero_is_smoothed_not_explosive():
    days = [point(i, 0) for i in range(7)] + [point(7 + i, 1) for i in range(7)]
    result = trend.compute(days, 13)
    # 0 -> 7 posts would be "infinite" growth; smoothing keeps it well short of 100.
    assert result["components"]["mention_growth"]["value"] < 85
    assert result["explanation_code"] == "insufficient_data"
    assert result["confidence"] == "low"


def test_rising_negative_and_one_day_spike():
    history = [point(i, 10, positive=6, negative=2) for i in range(28)]
    complaints = [point(28 + i, 25, positive=3, negative=17) for i in range(7)]
    rising = trend.compute(history + complaints, 34)
    assert rising["explanation_code"] == "rising_negative"
    assert rising["components"]["persistence"]["value"] == 100.0

    spike = [point(28 + i, 10, positive=6, negative=2) for i in range(6)] + [point(34, 80, positive=50, negative=10)]
    assert trend.compute(history + spike, 34)["explanation_code"] == "one_day_spike"


def test_engagement_component_uses_per_post_averages():
    days = [point(i, 10, engagement=50, eng_records=10) for i in range(7)] + [point(7 + i, 10, engagement=150, eng_records=10) for i in range(7)]
    comp = trend.compute(days, 13)["components"]["engagement_growth"]
    assert (comp["previous_per_post"], comp["current_per_post"]) == (5.0, 15.0)
    assert comp["value"] > 50


# --- pipeline: hand-calculated sample ---------------------------------------------------------------------


def test_daily_metrics_match_a_hand_calculated_sample(client, watchlist_id, db_session):
    upload(client, "hand", (
        "1,2026-09-01T08:00:00Z,Redmi Note 14 camera is amazing,10,2\n"
        "2,2026-09-01T09:00:00Z,Redmi Note 14 battery is terrible,,\n"
        "3,2026-09-01T23:30:00-02:00,Poco support never replied,,\n"   # 01:30 UTC on 2 Sep
        "4,2026-09-03T10:00:00Z,#RedmiNote14 arrived today,4,0\n"
        "5,2026-09-03T11:00:00Z,Unrelated post about tablets,,\n"
    ))
    rows = {(m.date, m.tracked_entity_id): m for m in db_session.query(DailyMetric)}
    entities = {e["term"]: e["id"] for e in client.get(f"/api/watchlists/{watchlist_id}").json()["entities"]}

    redmi_id, poco_id = uuid.UUID(entities["Redmi Note 14"]), uuid.UUID(entities["Poco"])
    day1, day2, day3 = date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)

    r1 = rows[(day1, redmi_id)]
    assert (r1.mentions, r1.engagement, r1.positive_share, r1.negative_share) == (2, 12, 0.5, 0.5)
    assert r1.coverage_flags == {"collection": "complete", "scored": 2, "low_confidence": 0, "engagement_records": 1}
    # Covered day with no Redmi posts is an observed zero, with engagement unknown rather than zero.
    r2 = rows[(day2, redmi_id)]
    assert (r2.mentions, r2.engagement, r2.positive_share) == (0, None, None)
    assert rows[(day2, poco_id)].mentions == 1
    assert rows[(day2, poco_id)].negative_share == 1.0
    r3 = rows[(day3, redmi_id)]
    assert (r3.mentions, r3.engagement, r3.neutral_share) == (1, 4, 1.0)


def test_series_marks_uncollected_days_as_missing(client, watchlist_id):
    upload(client, "a", "1,2026-09-01T08:00:00Z,Redmi Note 14 is great,,\n2,2026-09-02T08:00:00Z,Redmi Note 14 again,,\n")
    upload(client, "b", "3,2026-09-05T08:00:00Z,Redmi Note 14 is great,,\n")
    entity = client.get(f"/api/watchlists/{watchlist_id}").json()["entities"][0]
    series = client.get("/api/metrics/series", params={"entity_ids": entity["id"], "start": "2026-09-01", "end": "2026-09-05"}).json()
    points = {p["date"]: p for p in series["series"][0]["points"]}
    assert series["timezone"] == "UTC"
    assert points["2026-09-01"]["mentions"] == 1 and points["2026-09-01"]["collection"] == "complete"
    assert points["2026-09-03"]["collection"] == "missing" and points["2026-09-03"]["mentions"] is None
    assert points["2026-09-05"]["mentions"] == 1


def test_series_validates_input(client, watchlist_id):
    entity = client.get(f"/api/watchlists/{watchlist_id}").json()["entities"][0]
    bad_range = client.get("/api/metrics/series", params={"entity_ids": entity["id"], "start": "2026-09-05", "end": "2026-09-01"})
    assert bad_range.status_code == 422
    too_long = client.get("/api/metrics/series", params={"entity_ids": entity["id"], "start": "2024-01-01", "end": "2026-01-01"})
    assert too_long.status_code == 422
    assert client.get("/api/metrics/series", params={"entity_ids": "nope", "start": "2026-09-01", "end": "2026-09-02"}).status_code == 422


def test_new_terms_match_posts_collected_earlier(client, watchlist_id, db_session):
    upload(client, "early", "1,2026-09-01T08:00:00Z,Samsung Galaxy M35 display is lovely,,\n")
    assert db_session.query(RecordMatch).count() == 0
    client.post(f"/api/watchlists/{watchlist_id}/entities", json={"term": "Galaxy M35", "entity_type": "competitor"})
    assert db_session.query(RecordMatch).count() == 1
    assert sum(m.mentions for m in db_session.query(DailyMetric)) == 1


def test_aspects_are_stored_per_clause(client, watchlist_id, db_session):
    upload(client, "asp", "1,2026-09-01T08:00:00Z,Redmi Note 14 camera is great but the battery is terrible,,\n")
    result = db_session.query(NlpResult).one()
    assert result.aspects_json == {"version": "asp-1", "items": [
        {"aspect": "battery", "sentiment": "negative"}, {"aspect": "camera", "sentiment": "positive"}]}


def test_evidence_and_trend_cards(client, watchlist_id, db_session):
    rows = []
    n = 0
    for day in range(21):
        count = 2 if day < 14 else 6
        for _ in range(count):
            n += 1
            text = "\"Poco support never replied, terrible\"" if day >= 14 else "Poco camera is great"
            rows.append(f"{n},2026-09-{day + 1:02d}T10:00:00Z,{text},,\n")
    upload(client, "story", "".join(rows))
    assert db_session.query(TrendSignal).count() > 0

    cards = client.get("/api/trends", params={"watchlist_id": watchlist_id}).json()
    poco = next(c for c in cards if c["term"] == "Poco")
    assert poco["explanation_code"] == "rising_negative"
    assert poco["details"]["components"]["mention_growth"]["current_mentions"] == 42
    assert len(poco["sparkline"]) == 28
    evidence = poco["evidence"]
    assert evidence["mentions"] == 42 and evidence["sentiment"]["negative"] == 42
    assert evidence["aspects"][0]["aspect"] == "customer_support"
    assert evidence["phrases"][0][0] == "support never replied"
    assert len(evidence["examples"]) <= 5

    evidence_url = f"/api/entities/{poco['entity_id']}/evidence"
    assert client.get(evidence_url, params={"start": "2026-09-01", "end": "2026-09-07"}).json()["mentions"] == 14


def test_synthetic_demo_data_is_deterministic_and_has_a_gap():
    end = date(2026, 10, 17)
    history, recent = generate(end)
    assert (history, recent) == generate(end)
    days = {r["published_at"][:10] for r in history + recent}
    for back in GAP:
        assert (end - timedelta(days=back)).isoformat() not in days
    assert all(r["url"].startswith("https://example.com/") for r in history[:50])
