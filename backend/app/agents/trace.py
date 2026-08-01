"""Per-request query tracing through the agent pipeline.

chat.py creates a TraceRecorder per user message, passes it through graph
state (the `trace` channel), and persists the finished row after the stream.
Nodes record spans unconditionally; the NullRecorder default makes recording
a no-op wherever no recorder is attached (tests, CLI, direct graph calls).
"""

import time
from datetime import UTC, datetime

from app.agents.retriever import doc_to_excerpt


def elapsed_ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


class TraceRecorder:
    def __init__(
        self, trace_id: str, session_id: str, query: str, mode: str, language: str
    ) -> None:
        self._id = trace_id
        self._session_id = session_id
        self._query = query
        self._mode = mode
        self._language = language
        self._started = time.perf_counter()
        self._retrieval_query: str | None = None
        self._translation_ms: int | None = None
        self._retrievals: list[dict] = []
        self._replies: list[dict] = []
        self._critic: list[dict] = []

    def record_translation(self, retrieval_query: str, ms: int) -> None:
        self._retrieval_query = retrieval_query
        self._translation_ms = ms

    def record_retrieval(self, persona: str, docs: list, ms: int) -> None:
        self._retrievals.append(
            {
                "persona": persona,
                "ms": ms,
                "docs": [
                    {
                        "work_id": d.metadata.get("work_id", ""),
                        "title": d.metadata.get("title", "Unknown work"),
                        "author": d.metadata.get("author", "Unknown author"),
                        "era": d.metadata.get("era", ""),
                        "chunk_index": d.metadata.get("chunk_index", 0),
                        "excerpt": doc_to_excerpt(d),
                    }
                    for d in docs
                ],
            }
        )

    def record_reply(self, persona: str, ms: int, chars: int) -> None:
        self._replies.append({"persona": persona, "ms": ms, "chars": chars})

    def record_critic(
        self,
        persona: str,
        supported: bool | None,
        note: str | None,
        citations: int,
        from_cache: bool,
    ) -> None:
        self._critic.append(
            {
                "persona": persona,
                "supported": supported,
                "note": note,
                "citations": citations,
                "from_cache": from_cache,
            }
        )

    def finish(self, status: str, error: str | None, speakers: list[str]) -> dict:
        return {
            "id": self._id,
            "session_id": self._session_id,
            "query": self._query,
            "mode": self._mode,
            "language": self._language,
            "speakers": speakers,
            "status": status,
            "error": error,
            "total_ms": elapsed_ms(self._started),
            "created_at": datetime.now(UTC).isoformat(),
            "detail": {
                "retrieval_query": self._retrieval_query,
                "translation_ms": self._translation_ms,
                "retrievals": self._retrievals,
                "replies": self._replies,
                "critic": self._critic,
            },
        }


class NullRecorder:
    def record_translation(self, *args, **kwargs) -> None:
        pass

    def record_retrieval(self, *args, **kwargs) -> None:
        pass

    def record_reply(self, *args, **kwargs) -> None:
        pass

    def record_critic(self, *args, **kwargs) -> None:
        pass

    def finish(self, *args, **kwargs) -> None:
        return None


_NULL = NullRecorder()


def recorder_from(state: dict) -> TraceRecorder | NullRecorder:
    return state.get("trace") or _NULL
