import json
import sqlite3

import pytest

import app.db as db_module
from app.agents.trace import NullRecorder, TraceRecorder, recorder_from
from app.config import Settings


class FakeDoc:
    def __init__(self, work_id="plato_apology", chunk_index=3):
        self.page_content = "The unexamined life is not worth living. " * 12
        self.metadata = {
            "work_id": work_id,
            "title": "Apology",
            "author": "Plato",
            "era": "Classical Greece",
            "chunk_index": chunk_index,
        }


def make_recorder(language: str = "en") -> TraceRecorder:
    return TraceRecorder("t1", "s1", "What is virtue?", "discuss", language)


def test_recorder_accumulates_spans_and_finishes_json_safe():
    rec = make_recorder(language="zh")
    rec.record_translation("What is virtue?", 42)
    rec.record_retrieval("socrates", [FakeDoc()], 14)
    rec.record_reply("socrates", 2350, 512)
    rec.record_critic("socrates", True, None, 1, from_cache=False)

    row = rec.finish("ok", None, ["socrates"])

    assert row["id"] == "t1"
    assert row["status"] == "ok"
    assert row["error"] is None
    assert row["total_ms"] >= 0
    detail = row["detail"]
    assert detail["retrieval_query"] == "What is virtue?"
    assert detail["translation_ms"] == 42
    (retrieval,) = detail["retrievals"]
    assert retrieval["persona"] == "socrates"
    assert retrieval["docs"][0]["title"] == "Apology"
    assert len(retrieval["docs"][0]["excerpt"]) <= 284  # 280 + "..."
    assert detail["replies"] == [{"persona": "socrates", "ms": 2350, "chars": 512}]
    assert detail["critic"][0]["supported"] is True
    json.dumps(row, ensure_ascii=False)  # raises if anything is not JSON-safe


def test_recorder_english_leaves_translation_empty():
    row = make_recorder("en").finish("ok", None, ["socrates"])
    assert row["detail"]["retrieval_query"] is None
    assert row["detail"]["translation_ms"] is None


def test_null_recorder_no_ops():
    null = NullRecorder()
    null.record_translation("x", 1)
    null.record_retrieval("socrates", [FakeDoc()], 1)
    null.record_reply("socrates", 1, 1)
    null.record_critic("socrates", True, None, 1, False)
    assert null.finish("ok", None, []) is None


def test_recorder_from_state_defaults_to_null():
    assert isinstance(recorder_from({}), NullRecorder)
    rec = make_recorder()
    assert recorder_from({"trace": rec}) is rec


@pytest.fixture
async def database(tmp_path, monkeypatch):
    monkeypatch.setattr(
        db_module, "get_settings", lambda: Settings(database_path=tmp_path / "t.db")
    )
    db = await db_module.Database.connect()
    yield db
    await db.close()


async def test_trace_roundtrip_and_filters(database):
    session = await database.create_session(mode="discuss", persona_ids=["socrates"])
    rec = TraceRecorder("t1", session["id"], "q1", "discuss", "en")
    rec.record_retrieval("socrates", [FakeDoc()], 10)
    await database.save_trace(rec.finish("ok", None, ["socrates"]))
    await database.save_trace(
        TraceRecorder("t2", session["id"], "q2", "discuss", "zh").finish(
            "error", "boom", ["socrates"]
        )
    )

    traces = await database.list_traces(session_id=session["id"])
    assert [t["id"] for t in traces] == ["t2", "t1"]  # newest first
    assert traces[1]["speakers"] == ["socrates"]
    assert "detail" not in traces[0]  # list rows stay light

    detail = await database.get_trace("t1")
    assert detail["detail"]["retrievals"][0]["docs"][0]["author"] == "Plato"
    assert (await database.get_trace("t2"))["error"] == "boom"
    assert await database.get_trace("missing") is None

    assert await database.list_traces(session_id="other") == []
    assert len(await database.list_traces(limit=1)) == 1


async def test_traces_cascade_on_session_delete(database):
    session = await database.create_session(mode="study", persona_ids=[])
    await database.save_trace(
        TraceRecorder("t1", session["id"], "q", "study", "en").finish("ok", None, [])
    )
    await database.delete_session(session["id"])
    assert await database.list_traces() == []


async def test_traces_table_created_on_legacy_database(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(db_path)
    legacy.execute(
        "CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT NOT NULL,"
        " mode TEXT NOT NULL, persona_ids TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    legacy.commit()
    legacy.close()

    monkeypatch.setattr(
        db_module, "get_settings", lambda: Settings(database_path=db_path)
    )
    db = await db_module.Database.connect()
    try:
        assert await db.list_traces() == []
    finally:
        await db.close()
