import argparse
import sys
from pathlib import Path

import yaml
from langchain_core.documents import Document

from app.config import get_settings
from app.rag.loaders import load_work_text
from app.rag.store import chunk_text, get_vector_store

CORPUS_MANIFEST = Path(__file__).parent / "corpus.yaml"
BATCH_SIZE = 128


def load_manifest(path: Path = CORPUS_MANIFEST) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)["works"]


def ingest_work(store, work: dict, corpus_dir: Path) -> int:
    try:
        text, cached = load_work_text(work["gutenberg_id"], corpus_dir)
    except Exception as exc:
        print(f"  SKIP {work['title']}: download failed ({exc})", file=sys.stderr)
        return 0

    chunks = chunk_text(text)
    if not chunks:
        print(f"  SKIP {work['title']}: no text after cleaning", file=sys.stderr)
        return 0

    store._collection.delete(where={"work_id": work["id"]})

    docs = [
        Document(
            page_content=chunk,
            metadata={
                "work_id": work["id"],
                "title": work["title"],
                "author": work["author"],
                "tradition": work["tradition"],
                "era": work["era"],
                "gutenberg_id": work["gutenberg_id"],
                "chunk_index": i,
            },
        )
        for i, chunk in enumerate(chunks)
    ]
    for start in range(0, len(docs), BATCH_SIZE):
        batch = docs[start : start + BATCH_SIZE]
        store.add_documents(
            batch, ids=[f"{work['id']}:{d.metadata['chunk_index']}" for d in batch]
        )
    origin = "cache" if cached else "download"
    print(f"  OK   {work['title']} ({work['author']}): {len(chunks)} chunks [{origin}]")
    return len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest the corpus into Chroma")
    parser.add_argument("--only", help="Comma-separated work ids to ingest")
    parser.add_argument("--reset", action="store_true", help="Drop the collection first")
    parser.add_argument("--stats", action="store_true", help="Print collection stats and exit")
    args = parser.parse_args()

    settings = get_settings()
    store = get_vector_store(settings)

    if args.stats:
        print(f"chunks in '{store._collection.name}': {store._collection.count()}")
        return

    if args.reset:
        store._client.delete_collection(store._collection.name)
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
    print(f"Done. {total} chunks ingested.")


if __name__ == "__main__":
    main()
