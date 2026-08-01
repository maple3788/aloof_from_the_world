import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.agents.persona_forge import get_or_generate
from app.agents.personas import PersonaCard, load_personas, persona_for_author
from app.config import get_settings
from app.llm import get_chat_model
from app.rag.ingest import load_manifest
from app.rag.loaders import load_work_text
from app.rag.store import count_work_chunks

logger = logging.getLogger(__name__)

router = APIRouter()


def _persona_payload(card: PersonaCard) -> dict:
    return {
        "id": card.id,
        "name": card.name,
        "era": card.era,
        "tradition": card.tradition,
        "color": card.color,
        "greeting": card.greeting,
        "greeting_zh": card.greeting_zh,
    }


@router.get("/personas")
def list_personas():
    return [_persona_payload(card) for card in load_personas().values()]


class PersonaGenerateRequest(BaseModel):
    work_id: str


@router.post("/personas/generate")
async def generate_persona(body: PersonaGenerateRequest, request: Request, response: Response):
    """Idempotent: 200 if a card already claims the author, 201 when newly forged."""
    work = next((w for w in load_manifest() if w["id"] == body.work_id), None)
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    existing = persona_for_author(work["author"])
    if existing is not None:
        return _persona_payload(existing)
    settings = get_settings()
    if not settings.persona_autogen:
        raise HTTPException(status_code=403, detail="Persona autogeneration disabled")
    llm = get_chat_model(settings)
    try:
        card, created = await asyncio.wait_for(
            get_or_generate(work["author"], work, llm),
            timeout=settings.persona_gen_timeout,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Persona generation timed out") from exc
    except Exception as exc:
        logger.warning("Persona generation failed for %s: %s", work["author"], exc)
        raise HTTPException(status_code=502, detail="Persona generation failed") from exc
    if card is None:
        raise HTTPException(status_code=502, detail="Persona generation failed")
    if created:
        response.status_code = 201
    return _persona_payload(card)


@router.get("/library/works")
def list_works(request: Request):
    """Corpus manifest enriched with per-work chunk counts (best effort)."""
    store = getattr(request.app.state, "store", None)
    works = []
    for work in load_manifest():
        chunks = 0
        if store is not None:
            try:
                chunks = count_work_chunks(store, work["id"])
            except Exception:
                chunks = 0
        card = persona_for_author(work["author"])
        works.append({**work, "chunks": chunks, "persona_id": card.id if card else None})
    return works


@router.get("/library/works/{work_id}/text")
def get_work_text(work_id: str):
    """Full cleaned text of a work; downloads from Gutenberg on first cache miss."""
    work = next((w for w in load_manifest() if w["id"] == work_id), None)
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    try:
        text, _ = load_work_text(work["gutenberg_id"], get_settings().corpus_dir)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Text unavailable") from exc
    card = persona_for_author(work["author"])
    return {
        "id": work["id"],
        "title": work["title"],
        "author": work["author"],
        "persona_id": card.id if card else None,
        "chars": len(text),
        "text": text,
    }
