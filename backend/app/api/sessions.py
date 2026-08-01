from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.agents.i18n import normalize_language
from app.agents.personas import load_personas
from app.agents.router import VALID_MODES
from app.db import Database
from app.rag.ingest import load_manifest
from app.rag.uploads import merge_works

router = APIRouter()


class SessionCreate(BaseModel):
    mode: str = "discuss"
    language: str = "en"
    persona_ids: list[str] = ["socrates"]
    work_id: str | None = None


@router.get("/sessions")
async def list_sessions(request: Request):
    database: Database = request.app.state.db
    return await database.list_sessions()


@router.post("/sessions", status_code=201)
async def create_session(body: SessionCreate, request: Request):
    database: Database = request.app.state.db
    mode = body.mode if body.mode in VALID_MODES else "discuss"
    language = normalize_language(body.language)
    personas = load_personas()
    persona_ids = [p for p in body.persona_ids if p in personas] or ["socrates"]
    works = merge_works(load_manifest(), await database.list_uploaded_works())
    work = next((w for w in works if w["id"] == body.work_id), None)
    return await database.create_session(
        mode=mode,
        persona_ids=persona_ids,
        language=language,
        work_id=work["id"] if work else None,
        title=f"Reading {work['title']}" if work else "New chat",
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    database: Database = request.app.state.db
    session = await database.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session["messages"] = await database.get_messages(session_id)
    return session


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, request: Request):
    database: Database = request.app.state.db
    if not await database.get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    await database.delete_session(session_id)
