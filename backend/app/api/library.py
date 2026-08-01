import asyncio
import logging
import time
from collections import deque
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.agents.persona_forge import add_author_variant, get_or_generate
from app.agents.personas import PersonaCard, load_personas, persona_for_author
from app.cache import get_cache
from app.config import get_settings
from app.db import Database
from app.llm import get_chat_model
from app.rag.ingest import ingest_text, load_manifest
from app.rag.loaders import load_work_text
from app.rag.store import count_work_chunks, delete_work_chunks
from app.rag.uploads import (
    UploadValidationError,
    extract_text,
    match_persona,
    merge_works,
    new_work_id,
    validate_size,
)

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


@router.get("/personas/{persona_id}")
async def get_persona_detail(persona_id: str, request: Request):
    """Full persona card plus the works (manifest + uploads) it can speak from."""
    card = load_personas().get(persona_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    store = getattr(request.app.state, "store", None)
    database: Database = request.app.state.db
    works = []
    for work in merge_works(load_manifest(), await database.list_uploaded_works()):
        if work["author"] not in card.authors:
            continue
        chunks = work["chunks"]
        if work["source"] == "gutenberg":
            chunks = 0
            if store is not None:
                try:
                    chunks = count_work_chunks(store, work["id"])
                except Exception:
                    chunks = 0
        public = {k: v for k, v in work.items() if k != "text_path"}
        works.append({**public, "chunks": chunks})
    return {
        **_persona_payload(card),
        "authors": card.authors,
        "traditions": card.traditions,
        "voice": card.voice,
        "worldview": card.worldview,
        "style_rules": card.style_rules,
        "works": works,
    }


class PersonaGenerateRequest(BaseModel):
    work_id: str


@router.post("/personas/generate")
async def generate_persona(body: PersonaGenerateRequest, request: Request, response: Response):
    """Idempotent: 200 if a card already claims the author, 201 when newly forged."""
    database: Database = request.app.state.db
    works = merge_works(load_manifest(), await database.list_uploaded_works())
    work = next((w for w in works if w["id"] == body.work_id), None)
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
async def list_works(request: Request):
    """Manifest + uploaded works, enriched with chunk counts (best effort)."""
    store = getattr(request.app.state, "store", None)
    database: Database = request.app.state.db
    works = []
    for work in merge_works(load_manifest(), await database.list_uploaded_works()):
        chunks = work["chunks"]
        if work["source"] == "gutenberg" and store is not None:
            try:
                chunks = count_work_chunks(store, work["id"])
            except Exception:
                chunks = 0
        card = persona_for_author(work["author"])
        public = {k: v for k, v in work.items() if k != "text_path"}
        works.append({**public, "chunks": chunks, "persona_id": card.id if card else None})
    return works


@router.get("/library/works/{work_id}/text")
async def get_work_text(work_id: str, request: Request):
    """Full cleaned text of a work; downloads from Gutenberg on first cache miss."""
    database: Database = request.app.state.db
    work = next(
        (
            w
            for w in merge_works(load_manifest(), await database.list_uploaded_works())
            if w["id"] == work_id
        ),
        None,
    )
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    if work["source"] == "upload":
        # text_path is server-generated, but never trust stored paths blindly.
        root = get_settings().upload_dir.resolve()
        path = Path(work["text_path"]).resolve()
        if path != root and root not in path.parents:
            raise HTTPException(status_code=404, detail="Work not found")
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise HTTPException(status_code=502, detail="Text unavailable") from exc
    else:
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


# --- Uploads: user-supplied texts, analyzed and indexed at request time ---

_UPLOAD_WINDOW_S = 3600
_UPLOAD_RATE_LIMIT = 20
_upload_hits: dict[str, deque[float]] = {}

_MAX_FIELD_CHARS = {"title": 200, "author": 120, "tradition": 120, "era": 120}


def _check_upload_rate(ip: str) -> bool:
    """Sliding-window per-IP quota; False means the caller is over the limit."""
    now = time.monotonic()
    hits = _upload_hits.setdefault(ip, deque())
    while hits and now - hits[0] > _UPLOAD_WINDOW_S:
        hits.popleft()
    if len(hits) >= _UPLOAD_RATE_LIMIT:
        return False
    hits.append(now)
    return True


def _clean_field(value: str, name: str, required: bool) -> str:
    cleaned = value.strip()
    if required and not cleaned:
        raise HTTPException(status_code=422, detail=f"{name} is required")
    if len(cleaned) > _MAX_FIELD_CHARS[name]:
        raise HTTPException(status_code=422, detail=f"{name} is too long")
    return cleaned


@router.post("/library/uploads", status_code=201)
async def upload_work(
    request: Request,
    file: UploadFile,
    title: str = Form(...),
    author: str = Form(...),
    tradition: str = Form(""),
    era: str = Form(""),
    confirm_persona_id: str | None = Form(None),
):
    """Ingest a user text: extract, match the author to a persona, embed.

    A probable author match returns 409 with the candidate card; the caller
    resubmits with confirm_persona_id set to the candidate id (attach) or the
    string "decline" (keep separate — empty form fields arrive as None, so an
    explicit sentinel is required). Any failure after the DB row is written
    cleans up row, file, and chunks.
    """
    settings = get_settings()
    if not settings.upload_enabled:
        raise HTTPException(status_code=403, detail="Uploads disabled")
    ip = request.client.host if request.client else "unknown"
    if not _check_upload_rate(ip):
        raise HTTPException(status_code=429, detail="Too many uploads; try again later")

    title = _clean_field(title, "title", required=True)
    author = _clean_field(author, "author", required=True)
    tradition = _clean_field(tradition, "tradition", required=False) or "Unknown tradition"
    era = _clean_field(era, "era", required=False) or "Unknown era"

    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    try:
        validate_size(content, settings)
        text = extract_text(file.filename or "", content)
    except UploadValidationError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc

    card, kind = match_persona(author)
    persona_id: str | None = None
    match = "none"
    if kind == "exact" and card is not None:
        persona_id, match = card.id, "exact"
    elif kind == "probable" and card is not None:
        if confirm_persona_id is None:
            return JSONResponse(
                status_code=409,
                content={"match": "ambiguous", "candidate": _persona_payload(card)},
            )
        if confirm_persona_id == card.id:
            persona_id, match = card.id, "confirmed"
        elif confirm_persona_id != "decline":
            raise HTTPException(status_code=422, detail="Unknown confirm_persona_id")

    if match == "confirmed" and card is not None:
        # Teach the card this spelling so future matches are exact.
        add_author_variant(card.id, author)

    store = getattr(request.app.state, "store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Vector store unavailable")

    database: Database = request.app.state.db
    work_id = new_work_id(title)
    path = settings.upload_dir / f"{work_id}.txt"
    work = {
        "id": work_id,
        "title": title,
        "author": author,
        "tradition": tradition,
        "era": era,
        "source": "upload",
    }
    try:
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        await database.add_uploaded_work(
            {**work, "text_path": str(path), "status": "indexing"}
        )
        chunks = await asyncio.wait_for(
            asyncio.to_thread(ingest_text, store, work, text),
            timeout=settings.upload_timeout,
        )
        if chunks == 0:
            raise UploadValidationError("No readable text in file")
        await database.update_upload_status(work_id, "ready", chunks)
    except UploadValidationError as exc:
        await _cleanup_upload(database, store, work_id, path)
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Upload %s failed: %s", work_id, exc)
        await _cleanup_upload(database, store, work_id, path)
        raise HTTPException(status_code=502, detail="Upload indexing failed") from exc

    removed = await get_cache().clear_prefix("rag")
    if removed:
        logger.info("Flushed %d cached retrieval entries after upload", removed)

    # Eager forge: an author with no persona gets one now, so the reading
    # room opens with them present. Failure is non-fatal — the work stays
    # readable and the reading-room summon retries lazily.
    persona_status = "existing" if persona_id else "skipped"
    if persona_id is None and settings.persona_autogen:
        try:
            llm = get_chat_model(settings)
            forged, created = await asyncio.wait_for(
                get_or_generate(author, work, llm),
                timeout=settings.persona_gen_timeout,
            )
            if forged is not None:
                persona_id = forged.id
                persona_status = "created" if created else "existing"
            else:
                persona_status = "failed"
        except Exception as exc:
            logger.warning("Eager persona forge failed for %s: %s", author, exc)
            persona_status = "failed"

    return {
        "work": {**work, "chunks": chunks, "persona_id": persona_id},
        "persona_id": persona_id,
        "match": match,
        "persona_status": persona_status,
    }


async def _cleanup_upload(database: Database, store, work_id: str, path: Path) -> None:
    try:
        await database.delete_uploaded_work(work_id)
    except Exception:
        logger.warning("Cleanup: could not delete upload row %s", work_id)
    path.unlink(missing_ok=True)
    try:
        delete_work_chunks(store, work_id)
    except Exception:
        pass  # best effort: a store without internals, or nothing indexed yet
