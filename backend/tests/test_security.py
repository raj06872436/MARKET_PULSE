import uuid

from fastapi.testclient import TestClient

from app.core.security import hash_password, verify_password
from app.db.models import AuditEvent, SocialRecord, UserSession
from app.main import app
from tests.conftest import PASSWORD, sign_up
from tests.test_analytics import upload

POSTS = "1,2026-09-01T08:00:00Z,Poco battery is terrible,,\n2,2026-09-02T08:00:00Z,Poco camera is great,,\n"


# --- accounts and sessions ---------------------------------------------------------------------------------


def test_password_hashing():
    stored = hash_password(PASSWORD)
    assert PASSWORD not in stored and stored.startswith("scrypt$")
    assert verify_password(PASSWORD, stored)
    assert not verify_password("wrong password", stored)
    assert stored != hash_password(PASSWORD)  # salted
    assert not verify_password(PASSWORD, None) and not verify_password(PASSWORD, "garbage")


def test_register_login_logout(anon_client, db_session):
    assert anon_client.get("/api/watchlists").status_code == 401
    assert anon_client.get("/api/auth/me").status_code == 401

    first = sign_up(anon_client, "Owner@Example.com ")
    assert (first["email"], first["role"]) == ("owner@example.com", "admin")
    cookie = anon_client.cookies.get("mp_session")
    assert cookie and db_session.query(UserSession).one().token_hash != cookie  # only a hash is stored
    assert [w["name"] for w in anon_client.get("/api/workspaces").json()] == ["My workspace"]

    assert anon_client.post("/api/auth/logout").status_code == 204
    assert anon_client.get("/api/auth/me").status_code == 401
    assert db_session.query(UserSession).count() == 0

    bad = anon_client.post("/api/auth/login", json={"email": "owner@example.com", "password": "nope nope nope"})
    unknown = anon_client.post("/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert bad.status_code == unknown.status_code == 401
    assert bad.json() == unknown.json()  # doesn't reveal which emails exist
    assert anon_client.post("/api/auth/login", json={"email": "OWNER@example.com", "password": PASSWORD}).status_code == 200
    assert anon_client.get("/api/auth/me").json()["email"] == "owner@example.com"

    assert anon_client.post("/api/auth/register", json={"email": "owner@example.com", "password": PASSWORD}).status_code == 409
    assert anon_client.post("/api/auth/register", json={"email": "x@example.com", "password": "short"}).status_code == 422
    assert anon_client.post("/api/auth/register", json={"email": "not-an-email", "password": PASSWORD}).status_code == 422
    events = {e.event_type for e in db_session.query(AuditEvent)}
    assert {"user.registered", "user.login", "user.login_failed"} <= events


def test_forged_or_expired_session_is_refused(client, db_session):
    client.cookies.set("mp_session", "made-up-token")
    assert client.get("/api/auth/me").status_code == 401


def test_first_account_adopts_workspaces_made_before_sign_in(anon_client, db_session):
    from app.db.models import Workspace

    db_session.add(Workspace(name="Old workspace"))
    db_session.commit()
    sign_up(anon_client, "owner@example.com")
    assert {w["name"] for w in anon_client.get("/api/workspaces").json()} == {"Old workspace"}


def test_registration_can_be_closed(client, other_client):
    from app.core.config import Settings, get_settings

    app.dependency_overrides[get_settings] = lambda: Settings(allow_registration=False)
    try:
        with TestClient(app) as third:
            response = third.post("/api/auth/register", json={"email": "third@example.com", "password": PASSWORD})
        assert response.status_code == 403
    finally:
        del app.dependency_overrides[get_settings]


def test_account_deletion_removes_workspaces_and_uploads(client, other_client, watchlist_id, db_session):
    other_ws = other_client.get("/api/workspaces").json()[0]["id"]
    other_client.post("/api/imports/csv", data={"dataset": "mine", "workspace_id": other_ws},
                      files={"file": ("d.csv", ("source_record_id,published_at,text\n" + "1,2026-09-01T08:00:00Z,hello\n").encode())})
    assert db_session.query(SocialRecord).filter_by(workspace_id=uuid.UUID(other_ws)).count() == 1
    assert client.delete("/api/auth/me").status_code == 409  # the only admin, while others still need one
    assert other_client.delete("/api/auth/me").status_code == 204
    assert db_session.query(SocialRecord).filter_by(workspace_id=uuid.UUID(other_ws)).count() == 0
    assert other_client.get("/api/auth/me").status_code == 401
    # Once nobody else is left, the admin can delete their own account too.
    assert client.delete("/api/auth/me").status_code == 204


# --- workspace isolation -------------------------------------------------------------------------------------


def test_other_accounts_cannot_see_or_change_a_workspace(client, other_client, watchlist_id, workspace_id):
    upload(client, "owner", POSTS)
    entity = client.get(f"/api/watchlists/{watchlist_id}").json()["entities"][1]["id"]
    alert = client.post("/api/alerts", json={"entity_id": entity, "rule": {"metric": "daily_mentions", "threshold": 1}}).json()
    rng = {"start": "2026-09-01", "end": "2026-09-02"}

    assert other_client.get("/api/watchlists").json() == []
    assert workspace_id not in {w["id"] for w in other_client.get("/api/workspaces").json()}
    for url, params in [
        (f"/api/watchlists/{watchlist_id}", {}),
        (f"/api/watchlists/{watchlist_id}/data-range", {}),
        ("/api/records", {"watchlist_id": watchlist_id, **rng}),
        ("/api/compare", {"watchlist_id": watchlist_id, **rng}),
        ("/api/trends", {"watchlist_id": watchlist_id}),
        ("/api/metrics/series", {"entity_ids": entity, **rng}),
        (f"/api/entities/{entity}/evidence", rng),
        (f"/api/entities/{entity}/sentiment", rng),
        ("/api/forecasts", {"watchlist_id": watchlist_id}),
        ("/api/insights", {"watchlist_id": watchlist_id}),
        ("/api/export/daily.csv", {"watchlist_id": watchlist_id, **rng}),
        ("/api/alerts", {"watchlist_id": watchlist_id}),
        ("/api/alerts/events", {"watchlist_id": watchlist_id}),
    ]:
        assert other_client.get(url, params=params).status_code == 404, url
    forecast = client.get("/api/forecasts", params={"watchlist_id": watchlist_id}).json()[0]["id"]
    assert other_client.get(f"/api/forecasts/{forecast}").status_code == 404

    for method, url, body in [
        ("patch", f"/api/watchlists/{watchlist_id}", {"name": "Mine now"}),
        ("delete", f"/api/watchlists/{watchlist_id}", None),
        ("post", f"/api/watchlists/{watchlist_id}/entities", {"term": "Pixel", "entity_type": "product"}),
        ("delete", f"/api/watchlists/{watchlist_id}/entities/{entity}", None),
        ("post", "/api/watchlists", {"workspace_id": workspace_id, "name": "Sneaky"}),
        ("post", "/api/forecasts", {"entity_id": entity, "horizon_days": 7}),
        ("post", "/api/insights/generate", {"watchlist_id": watchlist_id}),
        ("post", "/api/alerts", {"entity_id": entity, "rule": {"metric": "trend_score", "threshold": 70}}),
        ("patch", f"/api/alerts/{alert['id']}", {"active": False}),
        ("delete", f"/api/alerts/{alert['id']}", None),
    ]:
        response = getattr(other_client, method)(url, **({"json": body} if body is not None else {}))
        assert response.status_code == 404, (method, url, response.status_code)
    other_upload = other_client.post("/api/imports/csv", data={"dataset": "x", "workspace_id": workspace_id},
                                     files={"file": ("d.csv", b"source_record_id,published_at,text\n1,2026-09-01,hi\n")})
    assert other_upload.status_code == 404

    # Nothing changed for the owner.
    assert client.get(f"/api/watchlists/{watchlist_id}").json()["name"] == "Phones"
    assert client.get("/api/alerts", params={"watchlist_id": watchlist_id}).json()[0]["active"] is True


def test_uploads_only_match_their_own_workspace(client, other_client, watchlist_id, db_session):
    # The other account tracks the same term in its own workspace.
    other_ws = other_client.get("/api/workspaces").json()[0]["id"]
    other_wl = other_client.post("/api/watchlists", json={"workspace_id": other_ws, "name": "Theirs"}).json()
    other_client.post(f"/api/watchlists/{other_wl['id']}/entities", json={"term": "Poco", "entity_type": "brand"})

    upload(client, "same-name", POSTS)
    other_client.post("/api/imports/csv", data={"dataset": "same-name", "workspace_id": other_ws},
                      files={"file": ("d.csv", ("source_record_id,published_at,text,likes,comments\n" + POSTS).encode())})
    # Same dataset name and record IDs in two workspaces: stored twice, never treated as duplicates.
    assert db_session.query(SocialRecord).count() == 4

    rng = {"start": "2026-09-01", "end": "2026-09-02"}
    mine = client.get("/api/records", params={"watchlist_id": watchlist_id, **rng}).json()
    theirs = other_client.get("/api/records", params={"watchlist_id": other_wl["id"], **rng}).json()
    assert mine["total"] == theirs["total"] == 2
    assert {r["id"] for r in mine["items"]}.isdisjoint({r["id"] for r in theirs["items"]})

    # Each sees only their own upload on Sources and in the job list.
    for c, other in ((client, other_ws), (other_client, None)):
        runs = c.get("/api/jobs").json()
        assert len(runs) == 1
        csv_source = next(s for s in c.get("/api/sources").json() if s["source"] == "csv:same-name")
        assert csv_source["record_count"] == 2


def test_admin_only_actions(client, other_client):
    assert other_client.put("/api/sources/bluesky", json={"policy_reviewed": True}).status_code == 403
    assert other_client.post("/api/analysis/run").status_code == 403
    assert client.put("/api/sources/bluesky", json={"policy_reviewed": True}).status_code == 200
    assert client.post("/api/analysis/run").status_code == 200


# --- rate limits and hardening -------------------------------------------------------------------------------


def test_login_is_rate_limited(anon_client):
    sign_up(anon_client, "owner@example.com")
    anon_client.post("/api/auth/logout")
    codes = [anon_client.post("/api/auth/login", json={"email": "owner@example.com", "password": "wrong guess!"}).status_code
             for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429
    blocked = anon_client.post("/api/auth/login", json={"email": "owner@example.com", "password": PASSWORD})
    assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) > 0


def test_expensive_endpoints_are_rate_limited(client, watchlist_id):
    codes = [client.post("/api/analysis/run").status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]
    codes = [client.post("/api/insights/generate", json={"watchlist_id": watchlist_id}).status_code for _ in range(11)]
    assert codes[-1] == 429


def test_security_headers_and_error_shape(client):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "same-origin"
    assert response.headers["x-request-id"]
    assert client.get("/api/watchlists/not-a-uuid").status_code == 422
    assert client.get("/api/nothing-here").json() == {"detail": "Not Found"}


def test_unexpected_errors_return_a_safe_message(client, monkeypatch):
    from app.api.routes import workspaces

    def boom(*_args, **_kwargs):
        raise RuntimeError("database password is hunter2")

    monkeypatch.setattr(workspaces, "select", boom)
    with TestClient(app, raise_server_exceptions=False, cookies=client.cookies) as c:
        response = c.get("/api/workspaces")
    assert response.status_code == 500
    body = response.json()
    assert "hunter2" not in response.text
    assert body["detail"].startswith("Something went wrong") and body["request_id"] == response.headers["x-request-id"]
