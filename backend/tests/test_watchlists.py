import uuid


def create_watchlist(client, workspace_id, name="Budget smartphones India"):
    response = client.post("/api/watchlists", json={"workspace_id": workspace_id, "name": name})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_list_watchlist(client, workspace_id):
    created = create_watchlist(client, workspace_id)
    assert created["active"] is True
    assert created["language"] == "en"
    assert created["entities"] == []

    listed = client.get("/api/watchlists", params={"workspace_id": workspace_id}).json()
    assert [w["id"] for w in listed] == [created["id"]]


def test_create_watchlist_requires_existing_workspace(client):
    response = client.post("/api/watchlists", json={"workspace_id": str(uuid.uuid4()), "name": "x"})
    assert response.status_code == 404


def test_pause_rename_and_delete_watchlist(client, workspace_id):
    watchlist = create_watchlist(client, workspace_id)
    url = f"/api/watchlists/{watchlist['id']}"

    paused = client.patch(url, json={"active": False, "name": "Renamed"}).json()
    assert paused["active"] is False
    assert paused["name"] == "Renamed"

    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404


def test_add_entity_normalizes_variants(client, workspace_id):
    watchlist = create_watchlist(client, workspace_id)
    response = client.post(
        f"/api/watchlists/{watchlist['id']}/entities",
        json={
            "term": "  Redmi   Note 14 ",
            "entity_type": "product",
            "variants": ["redmi note 14", "RedmiNote14", "  #RedmiNote14", "redminote14"],
        },
    )
    assert response.status_code == 201, response.text
    entity = response.json()
    assert entity["term"] == "Redmi Note 14"
    # Duplicates of each other and of the main term are dropped, first spelling kept.
    assert entity["variants"] == ["RedmiNote14", "#RedmiNote14"]


def test_duplicate_entity_is_rejected(client, workspace_id):
    watchlist = create_watchlist(client, workspace_id)
    url = f"/api/watchlists/{watchlist['id']}/entities"
    assert client.post(url, json={"term": "Samsung", "entity_type": "brand"}).status_code == 201
    assert client.post(url, json={"term": " SAMSUNG ", "entity_type": "competitor"}).status_code == 409


def test_delete_entity(client, workspace_id):
    watchlist = create_watchlist(client, workspace_id)
    entity = client.post(
        f"/api/watchlists/{watchlist['id']}/entities", json={"term": "Poco", "entity_type": "brand"}
    ).json()

    assert client.delete(f"/api/watchlists/{watchlist['id']}/entities/{entity['id']}").status_code == 204
    assert client.get(f"/api/watchlists/{watchlist['id']}").json()["entities"] == []


def test_deleting_watchlist_cascades_to_entities(client, workspace_id, db_session):
    from app.db.models import TrackedEntity

    watchlist = create_watchlist(client, workspace_id)
    client.post(f"/api/watchlists/{watchlist['id']}/entities", json={"term": "Realme", "entity_type": "brand"})
    client.delete(f"/api/watchlists/{watchlist['id']}")
    assert db_session.query(TrackedEntity).count() == 0
