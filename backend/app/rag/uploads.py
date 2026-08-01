"""User-uploaded texts: validation, text extraction, author matching, registry merge.

Uploaded works live outside the curated corpus: text files under
`settings.upload_dir`, metadata rows in the SQLite `uploaded_works` table.
`merge_works` presents them alongside the Gutenberg manifest so the library,
reading room, and session validation treat them uniformly.
"""

import re
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

from app.agents.persona_forge import slugify
from app.agents.personas import PERSONAS_DIR, PersonaCard, load_personas, persona_for_author
from app.config import Settings

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".epub"}
MatchKind = Literal["exact", "probable", "none"]


class UploadValidationError(ValueError):
    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


def validate_size(content: bytes, settings: Settings) -> None:
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise UploadValidationError(
            f"File exceeds the {settings.max_upload_mb} MB limit", status=413
        )
    if not content:
        raise UploadValidationError("Empty file")


def extract_text(filename: str, content: bytes) -> str:
    """Validate the format and return the work's plain text.

    Raises UploadValidationError: 415 for unsupported types, 422 for files
    we cannot decode or that yield no text.
    """
    ext = Path(filename).suffix.lower()
    if ext in {".txt", ".md"}:
        text = _decode_plain(content)
    elif ext == ".pdf":
        text = _extract_pdf(content)
    elif ext == ".epub":
        text = _extract_epub(content)
    else:
        raise UploadValidationError(
            f"Unsupported file type '{ext or filename}'; "
            f"allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            status=415,
        )
    if not text.strip():
        raise UploadValidationError("No readable text in file")
    return text


def _decode_plain(content: bytes) -> str:
    if b"\x00" in content[:8192]:
        raise UploadValidationError("File looks binary, not text")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadValidationError("File is not valid UTF-8 text") from exc


def _extract_pdf(content: bytes) -> str:
    if not content.startswith(b"%PDF"):
        raise UploadValidationError("File is not a PDF", status=415)
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(content))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise UploadValidationError(f"Could not read the PDF ({exc})") from exc
    return "\n\n".join(p for p in pages if p.strip())


def _extract_epub(content: bytes) -> str:
    if not content.startswith(b"PK\x03\x04"):
        raise UploadValidationError("File is not an EPUB", status=415)
    from bs4 import BeautifulSoup
    from ebooklib import ITEM_DOCUMENT, epub

    try:
        book = epub.read_epub(BytesIO(content))
        docs = []
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            text = BeautifulSoup(item.get_content(), "html.parser").get_text("\n")
            if text.strip():
                docs.append(text.strip())
    except Exception as exc:
        raise UploadValidationError(f"Could not read the EPUB ({exc})") from exc
    return "\n\n".join(docs)


def fold_name(name: str) -> str:
    """Comparison-only normalization: case/punct/whitespace-insensitive."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", name.lower())).strip()


def match_persona(
    author: str, personas_dir: Path = PERSONAS_DIR
) -> tuple[PersonaCard | None, MatchKind]:
    """Decide whether an upload's author belongs to an existing persona.

    exact: the card's authors list claims this string (retrieval filter match).
    probable: equal after folding (typos/variants) — caller must confirm.
    none: no candidate; the work goes in persona-less.
    """
    card = persona_for_author(author, personas_dir)
    if card is not None:
        return card, "exact"
    folded = fold_name(author)
    candidates = [
        c
        for c in load_personas(personas_dir).values()
        if any(fold_name(a) == folded for a in c.authors)
    ]
    if candidates:
        return min(candidates, key=lambda c: (len(c.authors), c.id)), "probable"
    return None, "none"


def new_work_id(title: str) -> str:
    return f"upload_{slugify(title)}_{uuid.uuid4().hex[:6]}"


def merge_works(manifest: list[dict], uploads: list[dict]) -> list[dict[str, Any]]:
    """Unified work dicts: manifest (gutenberg) + ready uploads.

    Pure: inputs are not mutated. Upload rows carry their own chunk count;
    only rows that finished indexing are listed.
    """
    works: list[dict[str, Any]] = [
        {**w, "source": "gutenberg", "chunks": 0} for w in manifest
    ]
    works += [
        {
            "id": u["id"],
            "title": u["title"],
            "author": u["author"],
            "tradition": u["tradition"],
            "era": u["era"],
            "text_path": u["text_path"],
            "chunks": u["chunks"],
            "source": "upload",
        }
        for u in uploads
        if u["status"] == "ready"
    ]
    return works
