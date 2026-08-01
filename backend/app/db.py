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
    persona_ids TEXT NOT NULL,
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
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_session(row: aiosqlite.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "mode": row["mode"],
        "persona_ids": json.loads(row["persona_ids"]),
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
            await conn.commit()
        return database

    async def close(self) -> None:
        async with self._lock:
            await self._conn.close()

    async def create_session(
        self, mode: str, persona_ids: list[str], title: str = "New chat"
    ) -> dict:
        session = {
            "id": uuid.uuid4().hex[:12],
            "title": title,
            "mode": mode,
            "persona_ids": persona_ids,
            "created_at": _now(),
        }
        async with self._lock:
            await self._conn.execute(
                "INSERT INTO sessions (id, title, mode, persona_ids, created_at)"
                " VALUES (?,?,?,?,?)",
                (
                    session["id"],
                    title,
                    mode,
                    json.dumps(persona_ids),
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
