from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401  (registers every table)
from app.core.ratelimit import limiter
from app.db.base import Base
from app.db.session import get_db, get_session_factory
from app.main import app


@pytest.fixture
def session_factory() -> Iterator[sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def db_session(session_factory: sessionmaker) -> Iterator[Session]:
    with session_factory() as session:
        yield session


PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> Iterator[None]:
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def anon_client(db_session: Session, session_factory: sessionmaker) -> Iterator[TestClient]:
    """A client with no session cookie."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def sign_up(client: TestClient, email: str) -> dict:
    response = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def client(anon_client: TestClient) -> TestClient:
    """Signed in as the first account, which is the admin."""
    sign_up(anon_client, "owner@example.com")
    return anon_client


@pytest.fixture
def other_client(client: TestClient, db_session: Session, session_factory: sessionmaker) -> Iterator[TestClient]:
    """A second, separate account in its own browser."""
    with TestClient(app) as second:
        sign_up(second, "other@example.com")
        yield second


@pytest.fixture
def workspace_id(client: TestClient) -> str:
    return client.post("/api/workspaces", json={"name": "Test workspace"}).json()["id"]


@pytest.fixture
def watchlist_id(client: TestClient, workspace_id: str) -> str:
    """A watchlist tracking Redmi Note 14 (with variants) and Poco."""
    watchlist = client.post("/api/watchlists", json={"workspace_id": workspace_id, "name": "Phones"}).json()
    url = f"/api/watchlists/{watchlist['id']}/entities"
    client.post(url, json={"term": "Redmi Note 14", "entity_type": "product", "variants": ["#RedmiNote14"]})
    client.post(url, json={"term": "Poco", "entity_type": "competitor"})
    return watchlist["id"]


def upload_workspace(client: TestClient) -> str:
    """Where test uploads go: the workspace of the first watchlist, or the account's own workspace."""
    watchlists = client.get("/api/watchlists").json()
    return watchlists[0]["workspace_id"] if watchlists else client.get("/api/workspaces").json()[0]["id"]
