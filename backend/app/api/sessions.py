from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import db
from app.agents.personas import load_personas
from app.agents.router import VALID_MODES

router = APIRouter()


class SessionCreate(BaseModel):
    mode: str = "discuss"
    persona_ids: list[str] = ["socrates"]


@router.get("/sessions")
async def list_sessions():
    return await db.list_sessions()


@router.post("/sessions", status_code=201)
async def create_session(body: SessionCreate):
    mode = body.mode if body.mode in VALID_MODES else "discuss"
    personas = load_personas()
    persona_ids = [p for p in body.persona_ids if p in personas] or ["socrates"]
    return await db.create_session(mode=mode, persona_ids=persona_ids)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session["messages"] = await db.get_messages(session_id)
    return session


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str):
    if not await db.get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete_session(session_id)
