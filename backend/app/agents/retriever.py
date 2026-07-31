from langchain_core.documents import Document

from app.rag.store import persona_where_filter, retrieve

EXCERPT_LEN = 280


def retrieve_for_persona(store, persona, query: str, k: int | None = None) -> list[Document]:
    where = persona_where_filter(authors=persona.authors, traditions=persona.traditions)
    return retrieve(store, query, k=k, where=where)


def retrieve_for_tutor(store, query: str, k: int | None = None) -> list[Document]:
    return retrieve(store, query, k=k)


def format_context(docs: list[Document]) -> str:
    """Numbered source excerpts; indices align with what the critic cites."""
    lines = []
    for i, doc in enumerate(docs, start=1):
        title = doc.metadata.get("title", "Unknown work")
        author = doc.metadata.get("author", "Unknown author")
        lines.append(f"[{i}] {title} — {author}:\n{doc.page_content}")
    return "\n\n".join(lines)


def doc_to_excerpt(doc: Document, length: int = EXCERPT_LEN) -> str:
    text = " ".join(doc.page_content.split())
    if len(text) > length:
        return text[:length].rsplit(" ", 1)[0] + "..."
    return text
