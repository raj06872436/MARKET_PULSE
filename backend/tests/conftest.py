from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401  (registers every table)
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


@pytest.fixture
def client(db_session: Session, session_factory: sessionmaker) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


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
