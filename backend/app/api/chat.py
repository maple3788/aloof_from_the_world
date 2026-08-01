import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from app.agents.trace import TraceRecorder
from app.config import get_settings
from app.db import Database

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=4000)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _chunk_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    return ""


def _to_langchain(rows: list[dict]) -> list:
    messages = []
    for row in rows:
        if row["role"] == "user":
            messages.append(HumanMessage(content=row["content"]))
        else:
            messages.append(AIMessage(content=row["content"], name=row.get("persona_id")))
    return messages


def _public_response(resp: dict) -> dict:
    return {k: v for k, v in resp.items() if k != "docs"}


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest, request: Request):
    database: Database = request.app.state.db
    session = await database.get_session(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    history_rows = await database.get_messages(session["id"])
    # Only the recent tail goes to the LLM; the full history stays in the DB.
    # Prompt size would otherwise grow quadratically over a session.
    history_rows = history_rows[-get_settings().max_history_messages :]
    await database.add_message(session["id"], "user", body.message)
    if session["title"] == "New chat":
        title = body.message[:40].rstrip() + ("..." if len(body.message) > 40 else "")
        await database.rename_session(session["id"], title)

    messages = _to_langchain(history_rows) + [HumanMessage(content=body.message)]
    graph = request.app.state.graph
    trace_id = uuid.uuid4().hex[:12]
    recorder = TraceRecorder(
        trace_id, session["id"], body.message, session["mode"], session["language"]
    )

    async def event_stream():
        final_state: dict | None = None
        partial: dict[str, str] = {}
        trace_saved = False

        async def save_trace(status: str, error: str | None = None) -> None:
            # Trace persistence must never break the SSE stream itself.
            nonlocal trace_saved
            if trace_saved:
                return
            trace_saved = True
            speakers = (final_state or {}).get("speakers") or session["persona_ids"]
            try:
                await database.save_trace(recorder.finish(status, error, speakers))
            except Exception:
                logger.error("Failed to persist trace %s", trace_id, exc_info=True)

        try:
            yield _sse(
                {
                    "type": "start",
                    "mode": session["mode"],
                    "language": session["language"],
                    "persona_ids": session["persona_ids"],
                }
            )
            async for event in graph.astream_events(
                {
                    "messages": messages,
                    "mode": session["mode"],
                    "language": session["language"],
                    "persona_ids": session["persona_ids"],
                    "work_id": session["work_id"],
                    "trace": recorder,
                },
                version="v2",
            ):
                if event["event"] == "on_chat_model_stream":
                    tags = event.get("tags") or []
                    persona = next(
                        (t.split(":", 1)[1] for t in tags if t.startswith("persona:")),
                        None,
                    )
                    if persona:
                        text = _chunk_text(event["data"]["chunk"].content)
                        if text:
                            partial[persona] = partial.get(persona, "") + text
                            yield _sse(
                                {"type": "token", "persona": persona, "content": text}
                            )
                elif event["event"] == "on_chain_end" and event["name"] == "LangGraph":
                    final_state = event["data"]["output"]

            responses = (final_state or {}).get("responses", [])
            for resp in responses:
                await database.add_message(
                    session["id"],
                    "assistant",
                    resp["content"],
                    persona_id=resp["responder"],
                    citations=resp.get("citations"),
                    critic_note=resp.get("critic_note"),
                )
            await save_trace("ok")
            yield _sse(
                {
                    "type": "done",
                    "trace_id": trace_id,
                    "responses": [_public_response(r) for r in responses],
                }
            )
        except asyncio.CancelledError:
            # Client aborted (session switch / unmount): record what completed,
            # but don't persist a half-finished reply the user walked away from.
            await save_trace("aborted")
            raise
        except Exception as exc:
            # Persist whatever was streamed so the user's message isn't orphaned
            # with a vanished reply on reload.
            for pid, content in partial.items():
                if content.strip():
                    try:
                        await database.add_message(
                            session["id"], "assistant", content.strip(), persona_id=pid
                        )
                    except Exception:
                        logger.error(
                            "Failed to persist partial reply for session %s",
                            session["id"],
                            exc_info=True,
                        )
            await save_trace("error", str(exc))
            yield _sse({"type": "error", "detail": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
