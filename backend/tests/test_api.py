import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.db as db_module
import app.rag.store as store_module
from app.config import Settings
from app.main import app


class StubGraph:
    """Mimics the compiled LangGraph: one token event, then the final state."""

    last_input: dict | None = None

    async def astream_events(self, input, version="v2"):
        StubGraph.last_input = input
        yield {
            "event": "on_chat_model_stream",
            "tags": ["persona:socrates"],
            "data": {"chunk": SimpleNamespace(content="Well met, friend.")},
        }
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "data": {
                "output": {
                    "responses": [
                        {
                            "responder": "socrates",
                            "responder_name": "Socrates",
                            "content": "Well met, friend.",
                            "citations": [
                                {
                                    "work_id": "plato_apology",
                                    "title": "Apology",
                                    "author": "Plato",
                                    "era": "Classical Greece",
                                    "chunk_index": 3,
                                    "excerpt": "The unexamined life...",
                                }
                            ],
                            "critic_note": None,
                            "docs": [],
                        }
                    ]
                }
            },
        }


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = Settings(database_path=tmp_path / "test.db")
    monkeypatch.setattr(db_module, "get_settings", lambda: settings)
    monkeypatch.setattr(store_module, "get_vector_store", lambda *a, **k: None)
    with TestClient(app) as test_client:
        test_client.app.state.graph = StubGraph()
        yield test_client


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["max_personas"] == 3
    assert body["cache"] == "off"


def test_personas_lists_starters(client):
    personas = client.get("/personas").json()
    ids = {p["id"] for p in personas}
    assert {"socrates", "nietzsche", "freud", "confucius"} <= ids
    assert all(p["greeting"] for p in personas)


def test_database_uses_wal_mode(client, tmp_path):
    journal_mode = (
        sqlite3.connect(tmp_path / "test.db")
        .execute("PRAGMA journal_mode")
        .fetchone()[0]
    )
    assert journal_mode == "wal"


def test_session_crud(client):
    created = client.post(
        "/sessions", json={"mode": "discuss", "persona_ids": ["socrates"]}
    )
    assert created.status_code == 201
    session_id = created.json()["id"]

    sessions = client.get("/sessions").json()
    assert any(s["id"] == session_id for s in sessions)

    detail = client.get(f"/sessions/{session_id}").json()
    assert detail["messages"] == []

    assert client.delete(f"/sessions/{session_id}").status_code == 204
    assert client.get(f"/sessions/{session_id}").status_code == 404


def test_create_session_validates_mode_and_personas(client):
    created = client.post(
        "/sessions", json={"mode": "bogus", "persona_ids": ["nobody"]}
    ).json()
    assert created["mode"] == "discuss"
    assert created["persona_ids"] == ["socrates"]


def test_chat_stream_tokens_and_persistence(client):
    session_id = client.post("/sessions", json={}).json()["id"]
    response = client.post(
        "/chat/stream", json={"session_id": session_id, "message": "What is virtue?"}
    )
    assert response.status_code == 200
    body = response.text
    assert '"type": "start"' in body
    assert '"type": "token"' in body and "Well met, friend." in body
    assert '"type": "done"' in body and "Apology" in body

    detail = client.get(f"/sessions/{session_id}").json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assistant = detail["messages"][1]
    assert assistant["persona_id"] == "socrates"
    assert assistant["citations"][0]["title"] == "Apology"
    assert detail["title"] == "What is virtue?"


def test_chat_stream_unknown_session_404(client):
    response = client.post(
        "/chat/stream", json={"session_id": "missing", "message": "hi"}
    )
    assert response.status_code == 404


def test_chat_rejects_overlong_message(client):
    session_id = client.post("/sessions", json={}).json()["id"]
    response = client.post(
        "/chat/stream", json={"session_id": session_id, "message": "x" * 4001}
    )
    assert response.status_code == 422


def test_chat_history_truncated_for_llm(client, monkeypatch):
    import app.api.chat as chat_module

    monkeypatch.setattr(
        chat_module, "get_settings", lambda: Settings(max_history_messages=2)
    )
    session_id = client.post("/sessions", json={}).json()["id"]
    for i in range(2):
        client.post(
            "/chat/stream", json={"session_id": session_id, "message": f"turn {i}"}
        )
    # DB now holds 4 rows (2 user + 2 assistant); only 2 may reach the LLM.
    client.post("/chat/stream", json={"session_id": session_id, "message": "turn 2"})
    assert len(StubGraph.last_input["messages"]) == 3  # 2 truncated + 1 new


def test_chat_stream_error_persists_partial_reply(client):
    class FailingGraph:
        async def astream_events(self, input, version="v2"):
            yield {
                "event": "on_chat_model_stream",
                "tags": ["persona:socrates"],
                "data": {"chunk": SimpleNamespace(content="A partial thought.")},
            }
            raise RuntimeError("graph exploded mid-stream")

    client.app.state.graph = FailingGraph()
    session_id = client.post("/sessions", json={}).json()["id"]
    response = client.post(
        "/chat/stream", json={"session_id": session_id, "message": "What is virtue?"}
    )
    assert response.status_code == 200
    assert '"type": "error"' in response.text

    detail = client.get(f"/sessions/{session_id}").json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["content"] == "A partial thought."
