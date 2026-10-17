"""The whole path a new user takes, end to end through the API, as one test."""

import csv
import io

from app.core.config import Settings
from tests.test_insights import story


def test_new_user_journey(anon_client):
    # Sign up; the first account gets a workspace of its own.
    me = anon_client.post("/api/auth/register", json={"email": "first@example.com", "password": "correct horse battery"})
    assert me.status_code == 201 and me.json()["role"] == "admin"
    workspace = anon_client.get("/api/workspaces").json()[0]["id"]

    # Create a watchlist with a product and a competitor.
    watchlist = anon_client.post("/api/watchlists", json={"workspace_id": workspace, "name": "Phones"}).json()["id"]
    url = f"/api/watchlists/{watchlist}/entities"
    assert anon_client.post(url, json={"term": "Redmi Note 14", "entity_type": "product"}).status_code == 201
    assert anon_client.post(url, json={"term": "Poco", "entity_type": "competitor"}).status_code == 201

    # Upload three weeks of posts, then look at them.
    story(anon_client)
    data_range = anon_client.get(f"/api/watchlists/{watchlist}/data-range").json()
    assert (data_range["first"], data_range["last"]) == ("2026-09-01", "2026-09-21")
    rng = {"start": "2026-09-01", "end": "2026-09-21"}
    records = anon_client.get("/api/records", params={"watchlist_id": watchlist, **rng}).json()
    assert records["total"] > 0 and records["items"][0]["text"]
    compare = anon_client.get("/api/compare", params={"watchlist_id": watchlist, **rng}).json()
    assert {c["term"] for c in compare["scorecards"]} == {"Redmi Note 14", "Poco"}

    # Insight cards point at the change and the posts behind it.
    insights = anon_client.post("/api/insights/generate", json={"watchlist_id": watchlist}).json()["insights"]
    poco = next(c for c in insights if c["observation"].startswith("Mentions of Poco"))
    assert poco["evidence"]["examples"]

    # Export the daily totals.
    export = anon_client.get("/api/export/daily.csv", params={"watchlist_id": watchlist, **rng})
    rows = list(csv.DictReader(io.StringIO(export.text)))
    assert len(rows) == 21 * 2 and all(r["collection"] == "complete" for r in rows)

    # Sign out, and the data is no longer reachable.
    anon_client.post("/api/auth/logout")
    assert anon_client.get(f"/api/watchlists/{watchlist}").status_code == 401


def test_hosted_database_urls_use_the_installed_driver():
    for given in ("postgres://u:p@db.example.com:5432/mp", "postgresql://u:p@db.example.com:5432/mp"):
        assert Settings(database_url=given).database_url == "postgresql+psycopg://u:p@db.example.com:5432/mp"
    assert Settings(database_url="sqlite://").database_url == "sqlite://"
