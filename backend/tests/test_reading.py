import sqlite3

import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage

import app.api.library as library_module
import app.db as db_module
import app.rag.store as store_module
from app.agents.graph import build_graph
from app.agents.personas import get_persona, persona_for_author
from app.agents.retriever import retrieve_for_persona
from app.config import Settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = Settings(database_path=tmp_path / "test.db")
    monkeypatch.setattr(db_module, "get_settings", lambda: settings)
    monkeypatch.setattr(store_module, "get_vector_store", lambda *a, **k: None)
    with TestClient(app) as test_client:
        yield test_client


def test_persona_for_author_prefers_most_specific_card():
    assert persona_for_author("Plato").id == "plato"
    assert persona_for_author("Xenophon").id == "socrates"
    assert persona_for_author("Friedrich Nietzsche").id == "nietzsche"


def test_persona_for_author_returns_none_without_match():
    assert persona_for_author("Thucydides") is None
    assert persona_for_author("Nobody") is None


def test_library_works_include_persona_id(client):
    works = client.get("/library/works").json()
    by_id = {w["id"]: w for w in works}
    assert by_id["plato_republic"]["persona_id"] == "plato"
    assert by_id["plato_apology"]["persona_id"] == "plato"
    assert by_id["confucius_analects"]["persona_id"] == "confucius"
    assert by_id["thucydides_history"]["persona_id"] is None


def test_work_text_serves_cached_text(client, monkeypatch):
    monkeypatch.setattr(
        library_module,
        "load_work_text",
        lambda gutenberg_id, cache_dir: ("The Republic body text.", True),
    )
    body = client.get("/library/works/plato_republic/text").json()
    assert body["text"] == "The Republic body text."
    assert body["persona_id"] == "plato"
    assert body["title"] == "The Republic"
    assert body["author"] == "Plato"
    assert body["chars"] == len("The Republic body text.")


def test_work_text_unknown_work_404(client):
    assert client.get("/library/works/nonexistent/text").status_code == 404


def test_work_text_loader_failure_502(client, monkeypatch):
    def explode(gutenberg_id, cache_dir):
        raise RuntimeError("network down")

    monkeypatch.setattr(library_module, "load_work_text", explode)
    response = client.get("/library/works/plato_republic/text")
    assert response.status_code == 502
    assert response.json()["detail"] == "Text unavailable"


# --- sessions.work_id + work-scoped retrieval (reading sessions) ---


def test_session_with_work_id_roundtrip(client):
    created = client.post(
        "/sessions", json={"persona_ids": ["plato"], "work_id": "plato_republic"}
    )
    assert created.status_code == 201
    body = created.json()
    assert body["work_id"] == "plato_republic"
    assert body["title"] == "Reading The Republic"
    detail = client.get(f"/sessions/{body['id']}").json()
    assert detail["work_id"] == "plato_republic"


def test_session_invalid_work_id_becomes_null(client):
    body = client.post("/sessions", json={"work_id": "nope"}).json()
    assert body["work_id"] is None
    assert body["title"] == "New chat"


async def test_work_id_column_migration(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(db_path)
    legacy.execute(
        "CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT NOT NULL,"
        " mode TEXT NOT NULL, persona_ids TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    legacy.execute(
        "INSERT INTO sessions VALUES ('s1', 'old chat', 'discuss', '[\"socrates\"]', '2026-01-01')"
    )
    legacy.commit()
    legacy.close()

    monkeypatch.setattr(db_module, "get_settings", lambda: Settings(database_path=db_path))
    database = await db_module.Database.connect()
    try:
        session = await database.get_session("s1")
        assert session is not None
        assert session["work_id"] is None
        created = await database.create_session(
            mode="discuss", persona_ids=["plato"], work_id="plato_republic"
        )
        assert created["work_id"] == "plato_republic"
    finally:
        await database.close()


class FilterCapturingStore:
    def __init__(self):
        self.last_filter = None

    def similarity_search(self, query, k=6, filter=None):
        self.last_filter = filter
        return [
            Document(
                page_content=f"Passage {i} on {query}",
                metadata={
                    "work_id": "plato_republic",
                    "title": "The Republic",
                    "author": "Plato",
                    "tradition": "Western philosophy",
                    "era": "Classical Greece",
                    "chunk_index": i,
                },
            )
            for i in range(2)
        ]


async def test_retrieve_for_persona_scopes_to_work():
    store = FilterCapturingStore()
    await retrieve_for_persona(store, get_persona("plato"), "justice", work_id="plato_republic")
    top = store.last_filter
    assert "$and" in top
    assert top["$and"][1] == {"work_id": "plato_republic"}
    assert "$or" in top["$and"][0]  # persona clause (authors/traditions) intact


async def test_retrieve_for_persona_without_work_unchanged():
    store = FilterCapturingStore()
    await retrieve_for_persona(store, get_persona("plato"), "justice")
    assert store.last_filter is not None
    assert "$and" not in store.last_filter


CRITIC_OK = '{"supported": true, "citation_indices": [1], "note": null}'


async def test_graph_work_id_reaches_retrieval():
    store = FilterCapturingStore()
    llm = FakeListChatModel(responses=["Justice is the harmony of the soul.", CRITIC_OK])
    graph = build_graph(llm=llm, store=store)
    await graph.ainvoke(
        {
            "messages": [HumanMessage(content="What is justice?")],
            "mode": "discuss",
            "persona_ids": ["plato"],
            "work_id": "plato_republic",
        }
    )
    assert "$and" in store.last_filter
    assert store.last_filter["$and"][1] == {"work_id": "plato_republic"}


class StubGraph:
    last_input: dict | None = None

    async def astream_events(self, input, version="v2"):
        StubGraph.last_input = input
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "data": {"output": {"responses": []}},
        }


def test_chat_stream_passes_work_id_to_graph(client):
    client.app.state.graph = StubGraph()
    session = client.post("/sessions", json={"work_id": "plato_republic"}).json()
    response = client.post(
        "/chat/stream", json={"session_id": session["id"], "message": "What is justice?"}
    )
    assert response.status_code == 200
    assert StubGraph.last_input["work_id"] == "plato_republic"
