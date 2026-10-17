import uuid

from tests.test_analytics import upload

POSTS = (
    "1,2026-09-01T08:00:00Z,Redmi Note 14 camera is amazing,10,2\n"
    "2,2026-09-01T09:00:00Z,Redmi Note 14 battery is terrible,,\n"
    "3,2026-09-02T10:00:00Z,Poco battery is terrible and support never replied,3,0\n"
    "4,2026-09-02T11:00:00Z,Poco battery is awful,1,1\n"
    "5,2026-09-03T10:00:00Z,#RedmiNote14 vs Poco: 50% off sale today,4,0\n"
    "6,2026-09-03T11:00:00Z,Redmi Note 14 battery lasts two days,,\n"
    "7,2026-09-04T11:00:00Z,Redmi Note 14 battery life is great,,\n"
)
RANGE = {"start": "2026-09-01", "end": "2026-09-04"}


def ids(client, watchlist_id):
    return {e["term"]: e["id"] for e in client.get(f"/api/watchlists/{watchlist_id}").json()["entities"]}


def test_data_range(client, watchlist_id):
    assert client.get(f"/api/watchlists/{watchlist_id}/data-range").json() == {"first": None, "last": None, "sources": []}
    upload(client, "x", POSTS)
    assert client.get(f"/api/watchlists/{watchlist_id}/data-range").json() == {
        "first": "2026-09-01", "last": "2026-09-04", "sources": ["csv:x"]}


def test_record_search_filters_and_pages(client, watchlist_id):
    upload(client, "x", POSTS)
    url, base = "/api/records", {"watchlist_id": watchlist_id, **RANGE}

    page = client.get(url, params={**base, "limit": 3}).json()
    assert page["total"] == 7 and len(page["items"]) == 3
    assert page["items"][0]["text"].startswith("Redmi Note 14 battery life")  # newest first
    both = next(r for r in client.get(url, params=base).json()["items"] if r["text"].startswith("#RedmiNote14"))
    assert both["terms"] == ["Poco", "Redmi Note 14"]
    assert both["engagement"] == 4

    # A literal % in the search must not act as a wildcard.
    assert client.get(url, params={**base, "q": "50%"}).json()["total"] == 1
    assert client.get(url, params={**base, "q": "BATTERY"}).json()["total"] == 5
    poco = ids(client, watchlist_id)["Poco"]
    assert client.get(url, params={**base, "entity_ids": poco}).json()["total"] == 3
    negative = client.get(url, params={**base, "sentiment": "negative"}).json()
    assert negative["total"] >= 2 and all(r["sentiment"] == "negative" for r in negative["items"])
    battery = client.get(url, params={**base, "aspect": "battery"}).json()["items"]
    assert battery and all(any(a["aspect"] == "battery" for a in r["aspects"]) for r in battery)
    by_engagement = client.get(url, params={**base, "sort": "engagement"}).json()["items"]
    assert [r["engagement"] for r in by_engagement[:3]] == [12, 4, 3]
    assert by_engagement[-1]["engagement"] is None  # unknown engagement sorts last, not as zero
    assert client.get(url, params={**base, "start": "2026-09-02", "end": "2026-09-02"}).json()["total"] == 2


def test_record_search_validation(client, watchlist_id, workspace_id):
    base = {"watchlist_id": watchlist_id, **RANGE}
    assert client.get("/api/records", params={**base, "limit": 101}).status_code == 422
    assert client.get("/api/records", params={**base, "sort": "random"}).status_code == 422
    assert client.get("/api/records", params={**base, "start": "2026-09-05"}).status_code == 422
    assert client.get("/api/records", params={**base, "watchlist_id": str(uuid.uuid4())}).status_code == 404
    other = client.post("/api/watchlists", json={"workspace_id": workspace_id, "name": "Other"}).json()
    term = client.post(f"/api/watchlists/{other['id']}/entities", json={"term": "Pixel", "entity_type": "product"}).json()
    # Terms from another watchlist can't be pulled in through this one.
    assert client.get("/api/records", params={**base, "entity_ids": term["id"]}).status_code == 422


def test_sentiment_breakdown(client, watchlist_id):
    upload(client, "x", POSTS)
    poco = ids(client, watchlist_id)["Poco"]
    body = client.get(f"/api/entities/{poco}/sentiment", params=RANGE).json()
    assert body["mentions"] == 3 and body["scored"] == 3
    assert sum(body["counts"].values()) == 3
    assert body["counts"]["negative"] >= 2
    battery = next(a for a in body["aspects"] if a["aspect"] == "battery")
    assert battery["negative"] == 2
    assert all(e["sentiment"] == "negative" for e in body["negative_examples"])
    assert body["sources"] == ["csv:x"]
    none = client.get(f"/api/entities/{poco}/sentiment", params={**RANGE, "source": "csv:other"}).json()
    assert none["mentions"] == 0 and none["counts"] == {"positive": 0, "neutral": 0, "negative": 0}


def test_compare_scorecards_and_gaps(client, watchlist_id):
    extra = "".join(
        f"{100 + i},2026-09-0{1 + i % 4}T12:00:00Z,{'Poco battery is terrible' if i % 2 else 'Redmi Note 14 battery is great'},,\n"
        for i in range(12)
    )
    upload(client, "x", POSTS + extra)
    body = client.get("/api/compare", params={"watchlist_id": watchlist_id, **RANGE}).json()
    cards = {c["term"]: c for c in body["scorecards"]}
    redmi, poco = cards["Redmi Note 14"], cards["Poco"]
    assert (redmi["mentions"], poco["mentions"]) == (11, 9)  # the post naming both counts for both
    assert redmi["share_of_voice"] + poco["share_of_voice"] == 1
    assert redmi["collected_days"] == 4
    assert redmi["engagement_per_post"] == 8.0  # (12 + 4) over the 2 posts that had engagement
    assert poco["net_sentiment"] < 0 < redmi["net_sentiment"]
    gap = next(g for g in body["aspect_gaps"] if g["term"] == "Poco" and g["aspect"] == "battery")
    assert gap["difference"] > 0.5
    assert body["days"] == 4 and body["sources"] == ["csv:x"]


def test_examples_skip_near_duplicates(client, watchlist_id):
    upload(client, "x", (
        "1,2026-09-01T08:00:00Z,#Poco is great value for money,,\n"
        "2,2026-09-01T09:00:00Z,Poco is great value for money!,,\n"
        "3,2026-09-02T09:00:00Z,Poco camera is amazing,,\n"
    ))
    poco = ids(client, watchlist_id)["Poco"]
    body = client.get(f"/api/entities/{poco}/sentiment", params=RANGE).json()
    assert body["counts"]["positive"] == 3
    assert len(body["positive_examples"]) == 2
