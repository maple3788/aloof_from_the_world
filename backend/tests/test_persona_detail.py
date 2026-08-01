import pytest
from fastapi.testclient import TestClient

import app.api.library as library_module
import app.db as db_module
import app.rag.store as store_module
from app.config import Settings
from app.main import app


class FakeStore:
    """Just enough Chroma for ingest: delete + add_documents."""

    def __init__(self):
        self._collection = self

    def delete(self, where):
        pass

    def add_documents(self, docs, ids=None):
        pass


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = Settings(
        database_path=tmp_path / "test.db", upload_dir=tmp_path / "uploads"
    )
    monkeypatch.setattr(db_module, "get_settings", lambda: settings)
    monkeypatch.setattr(store_module, "get_vector_store", lambda *a, **k: None)
    monkeypatch.setattr(library_module, "get_settings", lambda: settings)
    library_module._upload_hits.clear()
    with TestClient(app) as test_client:
        yield test_client


def test_persona_detail_full_card(client):
    body = client.get("/personas/plato").json()
    assert body["id"] == "plato"
    assert body["name"] == "Plato"
    assert body["color"] == "sky"
    assert body["authors"] == ["Plato"]
    assert body["traditions"] == ["Western philosophy"]
    assert body["greeting"]
    assert body["greeting_zh"]
    assert body["voice"]
    assert body["worldview"]
    assert len(body["style_rules"]) >= 4


def test_persona_detail_unknown_404(client):
    assert client.get("/personas/plotinus").status_code == 404


def test_persona_detail_links_own_works_only(client):
    body = client.get("/personas/plato").json()
    work_ids = {w["id"] for w in body["works"]}
    assert work_ids == {"plato_republic", "plato_apology"}
    for work in body["works"]:
        assert work["author"] == "Plato"
        assert work["chunks"] == 0  # no vector store in tests


def test_persona_detail_marcus_links_meditations(client):
    body = client.get("/personas/marcus_aurelius").json()
    assert [w["id"] for w in body["works"]] == ["marcus_meditations"]


def test_persona_detail_includes_uploaded_works(client):
    client.app.state.store = FakeStore()
    response = client.post(
        "/library/uploads",
        files={"file": ("letters.txt", b"Wisdom from the upload. " * 100, "text/plain")},
        data={"title": "Uploaded Letters", "author": "Plato"},
    )
    assert response.status_code == 201
    upload = response.json()["work"]

    body = client.get("/personas/plato").json()
    by_id = {w["id"]: w for w in body["works"]}
    assert upload["id"] in by_id
    assert by_id[upload["id"]]["chunks"] == upload["chunks"]
    assert by_id[upload["id"]]["source"] == "upload"
    assert "text_path" not in by_id[upload["id"]]
