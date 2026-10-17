from app.db.models import RecordMatch, SocialRecord

HEADER = "source_record_id,published_at,text,url,language,likes,comments,shares,views\n"
ROWS = (
    "r1,2026-09-01T10:00:00Z,Loving my new Redmi Note 14 camera,https://example.com/r1,en,12,3,,\n"
    "r2,2026-09-01T11:30:00+05:30,Battery on the redmi   note 14 is great #RedmiNote14,,en,,,,\n"
    "r3,2026-09-02T09:00:00Z,Poco support took a week to reply,,en,4,0,1,250\n"
    "r4,2026-09-02T09:05:00Z,Pocophone nostalgia thread,,en,,,,\n"
)


def upload(client, body: str, dataset="phones-sample", timezone="UTC", filename="data.csv"):
    return client.post(
        "/api/imports/csv",
        data={"dataset": dataset, "timezone": timezone},
        files={"file": (filename, body.encode(), "text/csv")},
    )


def test_import_stores_records_and_matches(client, watchlist_id, db_session):
    response = upload(client, HEADER + ROWS)
    assert response.status_code == 201, response.text
    run = response.json()["run"]
    assert run["source"] == "csv:phones-sample"
    assert run["status"] == "succeeded"
    assert (run["fetched_count"], run["inserted_count"], run["duplicate_count"], run["rejected_count"]) == (4, 4, 0, 0)
    # r1 and r2 match Redmi, r3 matches Poco, r4 ("Pocophone") must not match "Poco".
    assert run["matched_count"] == 3
    assert db_session.query(RecordMatch).count() == 3


def test_reimporting_the_same_file_does_not_double_count(client, watchlist_id, db_session):
    upload(client, HEADER + ROWS)
    second = upload(client, HEADER + ROWS).json()["run"]
    assert (second["inserted_count"], second["duplicate_count"], second["matched_count"]) == (0, 4, 0)
    assert db_session.query(SocialRecord).count() == 4
    assert db_session.query(RecordMatch).count() == 3


def test_same_ids_in_different_datasets_are_separate_records(client, db_session):
    upload(client, HEADER + ROWS, dataset="a")
    upload(client, HEADER + ROWS, dataset="b")
    assert db_session.query(SocialRecord).count() == 8


def test_engagement_is_null_when_missing_never_zero(client, db_session):
    upload(client, HEADER + ROWS)
    records = {r.source_record_id: r for r in db_session.query(SocialRecord)}
    assert records["r1"].engagement_json == {"likes": 12, "comments": 3}
    assert records["r2"].engagement_json is None
    assert records["r3"].engagement_json == {"likes": 4, "comments": 0, "shares": 1, "views": 250}
    # Stored as SQL NULL (not JSON null), so aggregate queries can filter on IS NULL.
    assert db_session.query(SocialRecord).filter(SocialRecord.engagement_json.is_(None)).count() == 2


def test_timestamps_are_normalized_to_utc(client, db_session):
    body = "source_record_id,published_at,text\nn1,2026-09-01 10:00:00,naive time\nn2,2026-09-01T10:00:00+05:30,with offset\n"
    upload(client, body, timezone="Asia/Kolkata")
    records = {r.source_record_id: r for r in db_session.query(SocialRecord)}
    # SQLite drops tzinfo on read, so compare the UTC wall-clock values.
    assert records["n1"].published_at.replace(tzinfo=None).isoformat() == "2026-09-01T04:30:00"
    assert records["n2"].published_at.replace(tzinfo=None).isoformat() == "2026-09-01T04:30:00"


def test_bad_rows_are_rejected_with_reasons_and_good_rows_kept(client):
    body = HEADER + (
        "ok1,2026-09-01T10:00:00Z,fine,,,,,,\n"
        ",2026-09-01T10:00:00Z,no id,,,,,,\n"
        "bad2,not-a-date,bad date,,,,,,\n"
        "bad3,2099-01-01T00:00:00Z,future,,,,,,\n"
        "bad4,2026-09-01T10:00:00Z,,,,,,,\n"
        "bad5,2026-09-01T10:00:00Z,negative,,,-4,,,\n"
        "bad6,2026-09-01T10:00:00Z,text,,,1.5,,,\n"
    )
    result = upload(client, body).json()
    assert result["run"]["status"] == "partial"
    assert result["run"]["inserted_count"] == 1
    assert result["run"]["rejected_count"] == 6
    assert [(e["row"], e["column"]) for e in result["errors"]] == [
        (3, "source_record_id"),
        (4, "published_at"),
        (5, "published_at"),
        (6, "text"),
        (7, "likes"),
        (8, "likes"),
    ]


def test_file_level_problems_are_refused(client):
    assert upload(client, "id,text\n1,hi\n").status_code == 422
    assert upload(client, HEADER + ROWS, dataset="Bad Name!").status_code == 422
    assert upload(client, HEADER + ROWS, timezone="Mars/Olympus").status_code == 422
    response = client.post(
        "/api/imports/csv",
        data={"dataset": "latin1"},
        files={"file": ("x.csv", "source_record_id,published_at,text\n1,2026-09-01,café\n".encode("latin-1"), "text/csv")},
    )
    assert response.status_code == 422
    assert "UTF-8" in response.json()["detail"]


def test_unknown_columns_are_reported(client):
    result = upload(client, "source_record_id,published_at,text,author_email\n1,2026-09-01T00:00:00Z,hi,x@y.z\n").json()
    assert result["unknown_columns"] == ["author_email"]


def test_paused_watchlists_do_not_match(client, watchlist_id):
    client.patch(f"/api/watchlists/{watchlist_id}", json={"active": False})
    run = upload(client, HEADER + ROWS).json()["run"]
    assert run["matched_count"] == 0
