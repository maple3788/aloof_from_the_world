import logging
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.cache import get_cache, retrieval_key
from app.config import Settings, get_settings
from app.llm import get_embeddings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "corpus"


def get_vector_store(
    settings: Settings | None = None,
    embeddings: Embeddings | None = None,
    collection_name: str = COLLECTION_NAME,
) -> Chroma:
    settings = settings or get_settings()
    return Chroma(
        collection_name=collection_name,
        embedding_function=embeddings or get_embeddings(settings),
        persist_directory=str(settings.chroma_dir),
    )


def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [c for c in splitter.split_text(text) if c.strip()]


def persona_where_filter(
    authors: list[str] | None = None,
    traditions: list[str] | None = None,
) -> dict[str, Any] | None:
    """Build a Chroma metadata filter scoping retrieval to a persona's corpus.

    Matches chunks by any of the persona's authors OR traditions (a persona can
    quote both their own works and the tradition they belong to).
    """
    clauses: list[dict[str, Any]] = []
    if authors:
        clauses.append({"author": {"$in": authors}})
    if traditions:
        clauses.append({"tradition": {"$in": traditions}})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$or": clauses}


def _docs_to_json(docs: list[Document]) -> list[dict[str, Any]]:
    return [{"page_content": d.page_content, "metadata": d.metadata} for d in docs]


def _docs_from_json(payload: list[dict[str, Any]]) -> list[Document]:
    return [Document(page_content=p["page_content"], metadata=p["metadata"]) for p in payload]


async def retrieve(
    store: Chroma,
    query: str,
    k: int | None = None,
    where: dict[str, Any] | None = None,
) -> list[Document]:
    settings = get_settings()
    k = k or settings.retrieval_top_k

    cache = get_cache()
    key = retrieval_key(query, where, k)
    cached = await cache.get(key)
    if cached is not None:
        return _docs_from_json(cached)

    try:
        results = store.similarity_search(query, k=k, filter=where)
    except Exception:
        logger.warning("Filtered similarity search failed; retrying unscoped", exc_info=True)
        results = []
    # Scoped corpora are small; fall back to the whole corpus when a filter
    # yields too little to ground an answer.
    if len(results) < min(2, k) and where is not None:
        results = store.similarity_search(query, k=k)

    await cache.set(key, _docs_to_json(results), settings.cache_ttl_retrieval)
    return results


# --- Chroma internals, isolated here so the rest of the app stays on the
# --- LangChain API. These touch chromadb private surfaces that may change
# --- across minor versions.


def delete_work_chunks(store: Chroma, work_id: str) -> None:
    store._collection.delete(where={"work_id": work_id})


def count_work_chunks(store: Chroma, work_id: str) -> int:
    result = store._collection.get(where={"work_id": work_id}, include=[])
    return len(result.get("ids", []))


def count_all_chunks(store: Chroma) -> int:
    return store._collection.count()


def drop_collection(store: Chroma) -> None:
    store._client.delete_collection(store._collection.name)
