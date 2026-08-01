import argparse
import asyncio
import sys
from pathlib import Path

import yaml
from langchain_core.documents import Document

from app.cache import get_cache
from app.config import get_settings
from app.rag.loaders import load_work_text
from app.rag.store import (
    COLLECTION_NAME,
    chunk_text,
    count_all_chunks,
    delete_work_chunks,
    drop_collection,
    get_vector_store,
)

CORPUS_MANIFEST = Path(__file__).parent / "corpus.yaml"
BATCH_SIZE = 128


def load_manifest(path: Path = CORPUS_MANIFEST) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)["works"]


def ingest_text(store, work: dict, text: str) -> int:
    """Chunk one work's text and embed it; replaces any existing chunks.

    `work` needs id/title/author/tradition/era; `gutenberg_id` is optional,
    `source` defaults to "gutenberg". Returns the chunk count.
    """
    chunks = chunk_text(text)
    if not chunks:
        return 0

    delete_work_chunks(store, work["id"])

    docs = [
        Document(
            page_content=chunk,
            metadata={
                "work_id": work["id"],
                "title": work["title"],
                "author": work["author"],
                "tradition": work["tradition"],
                "era": work["era"],
                **(
                    {"gutenberg_id": work["gutenberg_id"]}
                    if work.get("gutenberg_id") is not None
                    else {}
                ),
                "chunk_index": i,
                "source": work.get("source", "gutenberg"),
            },
        )
        for i, chunk in enumerate(chunks)
    ]
    for start in range(0, len(docs), BATCH_SIZE):
        batch = docs[start : start + BATCH_SIZE]
        store.add_documents(
            batch, ids=[f"{work['id']}:{d.metadata['chunk_index']}" for d in batch]
        )
    return len(chunks)


def ingest_work(store, work: dict, corpus_dir: Path) -> int:
    try:
        text, cached = load_work_text(work["gutenberg_id"], corpus_dir)
    except Exception as exc:
        print(f"  SKIP {work['title']}: download failed ({exc})", file=sys.stderr)
        return 0

    count = ingest_text(store, work, text)
    if count == 0:
        print(f"  SKIP {work['title']}: no text after cleaning", file=sys.stderr)
        return 0
    origin = "cache" if cached else "download"
    print(f"  OK   {work['title']} ({work['author']}): {count} chunks [{origin}]")
    return count


async def _ingest_uploads(store) -> int:
    """Re-embed uploaded works from the DB registry (e.g. after --reset)."""
    from app.db import Database

    database = await Database.connect()
    try:
        uploads = await database.list_uploaded_works()
    finally:
        await database.close()
    total = 0
    for row in uploads:
        text = Path(row["text_path"]).read_text(encoding="utf-8")
        work = {**row, "source": "upload"}
        count = ingest_text(store, work, text)
        print(f"  OK   {row['title']} ({row['author']}): {count} chunks [upload]")
        total += count
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest the corpus into Chroma")
    parser.add_argument("--only", help="Comma-separated work ids to ingest")
    parser.add_argument("--reset", action="store_true", help="Drop the collection first")
    parser.add_argument("--stats", action="store_true", help="Print collection stats and exit")
    parser.add_argument(
        "--uploads",
        action="store_true",
        help="Re-ingest user-uploaded works from the database registry",
    )
    args = parser.parse_args()

    settings = get_settings()
    store = get_vector_store(settings)

    if args.stats:
        print(f"chunks in '{COLLECTION_NAME}': {count_all_chunks(store)}")
        return

    if args.reset:
        drop_collection(store)
        store = get_vector_store(settings)
        print("Collection reset.")

    works = load_manifest()
    if args.only:
        wanted = set(args.only.split(","))
        works = [w for w in works if w["id"] in wanted]

    total = 0
    print(f"Ingesting {len(works)} works...")
    for work in works:
        total += ingest_work(store, work, settings.corpus_dir)
    if args.uploads:
        total += asyncio.run(_ingest_uploads(store))
    print(f"Done. {total} chunks ingested.")

    # Cached retrieval results may now be stale.
    removed = asyncio.run(get_cache().clear_prefix("rag"))
    if removed:
        print(f"Flushed {removed} cached retrieval entries.")


if __name__ == "__main__":
    main()
