import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

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

    async def event_stream():
        final_state: dict | None = None
        partial: dict[str, str] = {}
        try:
            yield _sse(
                {
                    "type": "start",
                    "mode": session["mode"],
                    "persona_ids": session["persona_ids"],
                }
            )
            async for event in graph.astream_events(
                {
                    "messages": messages,
                    "mode": session["mode"],
                    "persona_ids": session["persona_ids"],
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
            yield _sse(
                {"type": "done", "responses": [_public_response(r) for r in responses]}
            )
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
            yield _sse({"type": "error", "detail": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
