import re
from pathlib import Path

import httpx

GUTENBERG_URLS = [
    "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt",
    "https://www.gutenberg.org/files/{id}/{id}-8.txt",
    "https://www.gutenberg.org/files/{id}/{id}.txt",
]

_START_RE = re.compile(r"^\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG EBOOK.*\*\*\*\s*$", re.M)
_END_RE = re.compile(r"^\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG EBOOK.*\*\*\*\s*$", re.M)


def strip_gutenberg_boilerplate(text: str) -> str:
    """Remove Project Gutenberg license header/footer, keeping only the work itself."""
    start = _START_RE.search(text)
    if start:
        text = text[start.end() :]
    end = _END_RE.search(text)
    if end:
        text = text[: end.start()]
    return text.strip()


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


def download_gutenberg_text(gutenberg_id: int, timeout: float = 60.0) -> str:
    """Fetch a plain-text ebook from Project Gutenberg, trying known URL layouts."""
    last_error: Exception | None = None
    for url_template in GUTENBERG_URLS:
        url = url_template.format(id=gutenberg_id)
        try:
            resp = httpx.get(url, timeout=timeout, follow_redirects=True)
            if resp.status_code == 200 and len(resp.text) > 1000:
                return resp.text
        except httpx.HTTPError as exc:  # network down / blocked: try next layout
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError(f"No usable Gutenberg text found for id {gutenberg_id}")


def load_work_text(gutenberg_id: int, cache_dir: Path) -> tuple[str, bool]:
    """Return (cleaned_text, was_cached). Caches the cleaned text under cache_dir."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"gutenberg_{gutenberg_id}.txt"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8"), True
    raw = download_gutenberg_text(gutenberg_id)
    cleaned = normalize_text(strip_gutenberg_boilerplate(raw))
    cache_path.write_text(cleaned, encoding="utf-8")
    return cleaned, False
