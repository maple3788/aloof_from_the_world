import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    mode TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    persona_ids TEXT NOT NULL,
    work_id TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    persona_id TEXT,
    content TEXT NOT NULL,
    citations TEXT,
    critic_note TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE TABLE IF NOT EXISTS traces (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    mode TEXT NOT NULL,
    language TEXT NOT NULL,
    speakers TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    total_ms INTEGER NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_traces_session ON traces(session_id);
CREATE INDEX IF NOT EXISTS idx_traces_created ON traces(created_at);
CREATE TABLE IF NOT EXISTS uploaded_works (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    tradition TEXT NOT NULL,
    era TEXT NOT NULL,
    text_path TEXT NOT NULL,
    chunks INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_session(row: aiosqlite.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "mode": row["mode"],
        "language": row["language"],
        "persona_ids": json.loads(row["persona_ids"]),
        "work_id": row["work_id"],
        "created_at": row["created_at"],
    }


def _row_to_trace(row: aiosqlite.Row, include_detail: bool = False) -> dict[str, Any]:
    trace = {
        "id": row["id"],
        "session_id": row["session_id"],
        "query": row["query"],
        "mode": row["mode"],
        "language": row["language"],
        "speakers": json.loads(row["speakers"]),
        "status": row["status"],
        "error": row["error"],
        "total_ms": row["total_ms"],
        "created_at": row["created_at"],
    }
    if include_detail:
        trace["detail"] = json.loads(row["detail"])
    return trace


def _row_to_uploaded_work(row: aiosqlite.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "author": row["author"],
        "tradition": row["tradition"],
        "era": row["era"],
        "text_path": row["text_path"],
        "chunks": row["chunks"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def _row_to_message(row: aiosqlite.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "role": row["role"],
        "persona_id": row["persona_id"],
        "content": row["content"],
        "citations": json.loads(row["citations"]) if row["citations"] else [],
        "critic_note": row["critic_note"],
        "created_at": row["created_at"],
    }


class Database:
    """One shared connection for the process, guarded by a lock.

    aiosqlite serializes calls per connection, but the lock keeps
    multi-statement writes (e.g. session delete) atomic. WAL mode lets
    reads proceed alongside a write.
    """

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn
        self._lock = asyncio.Lock()

    @classmethod
    async def connect(cls) -> "Database":
        settings = get_settings()
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(settings.database_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        database = cls(conn)
        async with database._lock:
            await conn.executescript(SCHEMA)
            # Lightweight migrations for DBs created before these columns existed.
            columns = {
                row[1]
                for row in await conn.execute_fetchall("PRAGMA table_info(sessions)")
            }
            if "language" not in columns:
                await conn.execute(
                    "ALTER TABLE sessions ADD COLUMN language TEXT NOT NULL DEFAULT 'en'"
                )
            if "work_id" not in columns:
                await conn.execute("ALTER TABLE sessions ADD COLUMN work_id TEXT")
            await conn.commit()
        return database

    async def close(self) -> None:
        async with self._lock:
            await self._conn.close()

    async def create_session(
        self,
        mode: str,
        persona_ids: list[str],
        language: str = "en",
        work_id: str | None = None,
        title: str = "New chat",
    ) -> dict:
        session = {
            "id": uuid.uuid4().hex[:12],
            "title": title,
            "mode": mode,
            "language": language,
            "persona_ids": persona_ids,
            "work_id": work_id,
            "created_at": _now(),
        }
        async with self._lock:
            await self._conn.execute(
                "INSERT INTO sessions (id, title, mode, language, persona_ids, work_id,"
                " created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    session["id"],
                    title,
                    mode,
                    language,
                    json.dumps(persona_ids),
                    work_id,
                    session["created_at"],
                ),
            )
            await self._conn.commit()
        return session

    async def list_sessions(self) -> list[dict]:
        async with self._lock:
            cursor = await self._conn.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC"
            )
            return [_row_to_session(row) for row in await cursor.fetchall()]

    async def get_session(self, session_id: str) -> dict | None:
        async with self._lock:
            cursor = await self._conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            )
            row = await cursor.fetchone()
            return _row_to_session(row) if row else None

    async def rename_session(self, session_id: str, title: str) -> None:
        async with self._lock:
            await self._conn.execute(
                "UPDATE sessions SET title = ? WHERE id = ?", (title, session_id)
            )
            await self._conn.commit()

    async def delete_session(self, session_id: str) -> None:
        async with self._lock:
            await self._conn.execute(
                "DELETE FROM messages WHERE session_id = ?", (session_id,)
            )
            await self._conn.execute(
                "DELETE FROM traces WHERE session_id = ?", (session_id,)
            )
            await self._conn.execute(
                "DELETE FROM sessions WHERE id = ?", (session_id,)
            )
            await self._conn.commit()

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        persona_id: str | None = None,
        citations: list | None = None,
        critic_note: str | None = None,
    ) -> dict:
        row = {
            "session_id": session_id,
            "role": role,
            "persona_id": persona_id,
            "content": content,
            "citations": citations or [],
            "critic_note": critic_note,
            "created_at": _now(),
        }
        async with self._lock:
            cursor = await self._conn.execute(
                """INSERT INTO messages
                   (session_id, role, persona_id, content, citations, critic_note, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    session_id,
                    role,
                    persona_id,
                    content,
                    json.dumps(citations or []),
                    critic_note,
                    row["created_at"],
                ),
            )
            await self._conn.commit()
            row["id"] = cursor.lastrowid
        return row

    async def get_messages(self, session_id: str) -> list[dict]:
        async with self._lock:
            cursor = await self._conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            )
            return [_row_to_message(row) for row in await cursor.fetchall()]

    async def save_trace(self, row: dict) -> None:
        async with self._lock:
            await self._conn.execute(
                """INSERT INTO traces
                   (id, session_id, query, mode, language, speakers, status, error,
                    total_ms, detail, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    row["id"],
                    row["session_id"],
                    row["query"],
                    row["mode"],
                    row["language"],
                    json.dumps(row["speakers"]),
                    row["status"],
                    row["error"],
                    row["total_ms"],
                    json.dumps(row["detail"], ensure_ascii=False),
                    row["created_at"],
                ),
            )
            await self._conn.commit()

    async def list_traces(
        self, session_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        sql = "SELECT * FROM traces"
        params: list = []
        if session_id:
            sql += " WHERE session_id = ?"
            params.append(session_id)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        async with self._lock:
            cursor = await self._conn.execute(sql, params)
            return [_row_to_trace(row) for row in await cursor.fetchall()]

    async def get_trace(self, trace_id: str) -> dict | None:
        async with self._lock:
            cursor = await self._conn.execute(
                "SELECT * FROM traces WHERE id = ?", (trace_id,)
            )
            row = await cursor.fetchone()
            return _row_to_trace(row, include_detail=True) if row else None

    async def add_uploaded_work(self, row: dict) -> dict:
        work = {**row, "created_at": _now()}
        async with self._lock:
            await self._conn.execute(
                """INSERT INTO uploaded_works
                   (id, title, author, tradition, era, text_path, chunks, status, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    work["id"],
                    work["title"],
                    work["author"],
                    work["tradition"],
                    work["era"],
                    work["text_path"],
                    work.get("chunks", 0),
                    work["status"],
                    work["created_at"],
                ),
            )
            await self._conn.commit()
        return work

    async def list_uploaded_works(self) -> list[dict]:
        async with self._lock:
            cursor = await self._conn.execute(
                "SELECT * FROM uploaded_works ORDER BY created_at DESC"
            )
            return [_row_to_uploaded_work(row) for row in await cursor.fetchall()]

    async def get_uploaded_work(self, work_id: str) -> dict | None:
        async with self._lock:
            cursor = await self._conn.execute(
                "SELECT * FROM uploaded_works WHERE id = ?", (work_id,)
            )
            row = await cursor.fetchone()
            return _row_to_uploaded_work(row) if row else None

    async def update_upload_status(
        self, work_id: str, status: str, chunks: int | None = None
    ) -> None:
        async with self._lock:
            if chunks is None:
                await self._conn.execute(
                    "UPDATE uploaded_works SET status = ? WHERE id = ?",
                    (status, work_id),
                )
            else:
                await self._conn.execute(
                    "UPDATE uploaded_works SET status = ?, chunks = ? WHERE id = ?",
                    (status, chunks, work_id),
                )
            await self._conn.commit()

    async def delete_uploaded_work(self, work_id: str) -> None:
        async with self._lock:
            await self._conn.execute(
                "DELETE FROM uploaded_works WHERE id = ?", (work_id,)
            )
            await self._conn.commit()
