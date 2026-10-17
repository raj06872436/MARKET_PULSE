from datetime import UTC, datetime, timedelta

import pytest

from app.api.routes import sources as sources_route
from app.connectors.base import ConnectorError, ConnectorHealth, FetchCoverage, NormalizedRecord, SourceConnector
from app.db.models import IngestionRun, NlpResult, SocialRecord
from tests.conftest import upload_workspace


def record(n: int, text="Redmi Note 14 is great") -> NormalizedRecord:
    return NormalizedRecord(
        source="bluesky",
        source_record_id=f"at://x/{n}",
        published_at=datetime(2026, 10, 1, tzinfo=UTC) + timedelta(minutes=n),
        text=text,
    )


class FakeConnector(SourceConnector):
    name = "bluesky"
    version = "fake-1"

    def __init__(self, records, fail_with=None, truncate=False):
        self.records = records
        self.fail_with = fail_with
        self.truncate = truncate
        self.calls: list[tuple[list[str], datetime | None]] = []

    def fetch(self, terms, since, coverage: FetchCoverage):
        self.calls.append((terms, since))
        coverage.queries.extend(terms)
        if self.truncate:
            coverage.truncated_queries.append(terms[0])
        yield from self.records
        if self.fail_with:
            raise ConnectorError(self.fail_with, "Bluesky returned HTTP 503 after 4 attempts")

    def health(self):
        return ConnectorHealth(status="ok", notes=["fake"])


@pytest.fixture
def fake(monkeypatch):
    holder = {"connector": FakeConnector([record(1), record(2), record(3, text="nothing relevant")])}
    monkeypatch.setattr(sources_route, "build_connector", lambda source, settings: holder["connector"])
    return holder


def enable(client):
    response = client.put("/api/sources/bluesky", json={"policy_reviewed": True, "enabled": True, "policy_notes": "Checked public API terms"})
    assert response.status_code == 200, response.text
    return response.json()


def bluesky_status(client):
    return next(s for s in client.get("/api/sources").json() if s["source"] == "bluesky")


def test_source_starts_not_connected_and_sync_is_blocked(client, fake):
    status = bluesky_status(client)
    assert status["status"] == "not_connected"
    assert any("policy review" in note for note in status["notes"])
    assert client.post("/api/sources/bluesky/sync").status_code == 409


def test_enabling_requires_a_policy_review(client, fake):
    response = client.put("/api/sources/bluesky", json={"enabled": True})
    assert response.status_code == 409
    assert enable(client)["status"] == "never_run"


def test_unknown_source_is_404(client):
    assert client.post("/api/sources/twitter/sync").status_code == 404


def test_sync_stores_and_matches_records(client, fake, watchlist_id):
    enable(client)
    job = client.post("/api/sources/bluesky/sync")
    assert job.status_code == 202
    run = client.get(f"/api/jobs/{job.json()['id']}").json()
    assert run["status"] == "succeeded"
    assert (run["fetched_count"], run["inserted_count"], run["duplicate_count"], run["matched_count"]) == (3, 3, 0, 2)
    terms, since = fake["connector"].calls[0]
    assert terms == ["Redmi Note 14", "#RedmiNote14", "Poco"]
    assert since is None
    status = bluesky_status(client)
    assert status["status"] == "ok"
    assert status["record_count"] == 3
    assert status["last_success_at"] is not None


def test_synced_records_get_sentiment(client, fake, watchlist_id, db_session):
    enable(client)
    client.post("/api/sources/bluesky/sync")
    assert db_session.query(NlpResult).count() == 3


def test_repeated_sync_does_not_double_count(client, fake, watchlist_id, db_session):
    enable(client)
    first = client.post("/api/sources/bluesky/sync").json()
    second_id = client.post("/api/sources/bluesky/sync").json()["id"]
    second = client.get(f"/api/jobs/{second_id}").json()
    assert (second["inserted_count"], second["duplicate_count"], second["matched_count"]) == (0, 3, 0)
    assert db_session.query(SocialRecord).count() == 3

    # The second run asks only for posts since the first run, with an hour of overlap.
    first_started = db_session.get(IngestionRun, __import__("uuid").UUID(first["id"])).started_at
    _, since = fake["connector"].calls[1]
    assert since == first_started - timedelta(hours=1)


def test_source_failure_is_visible_and_keeps_records_that_arrived(client, fake, watchlist_id, db_session):
    enable(client)
    fake["connector"] = FakeConnector([record(1)], fail_with="source_unavailable")
    run_id = client.post("/api/sources/bluesky/sync").json()["id"]
    run = client.get(f"/api/jobs/{run_id}").json()
    assert run["status"] == "failed"
    assert run["error_code"] == "source_unavailable"
    assert "503" in run["error_detail"]
    assert run["inserted_count"] == 1
    assert run["coverage_json"]["complete"] is False
    assert db_session.query(SocialRecord).count() == 1

    status = bluesky_status(client)
    assert status["status"] == "failed"
    assert status["last_success_at"] is None


def test_failed_runs_do_not_move_the_incremental_window(client, fake, watchlist_id):
    enable(client)
    fake["connector"] = FakeConnector([], fail_with="timeout")
    client.post("/api/sources/bluesky/sync")
    client.post("/api/sources/bluesky/sync")
    assert [since for _, since in fake["connector"].calls] == [None, None]


def test_incomplete_coverage_is_reported_as_degraded(client, fake, watchlist_id):
    enable(client)
    fake["connector"] = FakeConnector([record(1)], truncate=True)
    run_id = client.post("/api/sources/bluesky/sync").json()["id"]
    run = client.get(f"/api/jobs/{run_id}").json()
    assert run["status"] == "partial"
    assert run["coverage_json"]["truncated_queries"] == ["Redmi Note 14"]
    assert bluesky_status(client)["status"] == "degraded"


def test_sync_with_no_tracked_terms_says_so(client, fake):
    enable(client)
    run_id = client.post("/api/sources/bluesky/sync").json()["id"]
    run = client.get(f"/api/jobs/{run_id}").json()
    assert run["status"] == "succeeded"
    assert run["coverage_json"]["no_terms"] is True
    assert fake["connector"].calls == []


def test_disabling_a_source_blocks_sync(client, fake):
    enable(client)
    client.put("/api/sources/bluesky", json={"enabled": False})
    assert client.post("/api/sources/bluesky/sync").status_code == 409
    assert bluesky_status(client)["status"] == "not_connected"


def test_csv_datasets_appear_as_sources(client):
    client.post(
        "/api/imports/csv",
        data={"dataset": "survey", "workspace_id": upload_workspace(client)},
        files={"file": ("s.csv", b"source_record_id,published_at,text\n1,2026-09-01T00:00:00Z,hi\n", "text/csv")},
    )
    csv_source = next(s for s in client.get("/api/sources").json() if s["source"] == "csv:survey")
    assert csv_source["kind"] == "csv"
    assert csv_source["label"] == "survey (CSV)"
    assert csv_source["status"] == "ok"
    assert csv_source["record_count"] == 1


def test_jobs_list_filters_by_source(client, fake):
    enable(client)
    client.post("/api/sources/bluesky/sync")
    jobs = client.get("/api/jobs", params={"source": "bluesky"}).json()
    assert len(jobs) == 1 and jobs[0]["source"] == "bluesky"
    assert client.get("/api/jobs/00000000-0000-0000-0000-000000000000").status_code == 404
