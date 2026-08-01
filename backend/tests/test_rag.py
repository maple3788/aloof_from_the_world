from app.rag.loaders import normalize_text, strip_gutenberg_boilerplate
from app.rag.store import (
    chunk_text,
    count_all_chunks,
    count_work_chunks,
    delete_work_chunks,
    drop_collection,
    persona_where_filter,
)

SAMPLE = """Header garbage
*** START OF THE PROJECT GUTENBERG EBOOK THE REPUBLIC ***

The actual text of the work.

More text here.

*** END OF THE PROJECT GUTENBERG EBOOK THE REPUBLIC ***
License garbage
"""


def test_strip_boilerplate_keeps_only_the_work():
    cleaned = strip_gutenberg_boilerplate(SAMPLE)
    assert "The actual text of the work." in cleaned
    assert "Header garbage" not in cleaned
    assert "License garbage" not in cleaned


def test_normalize_collapses_blank_runs():
    text = normalize_text("a\r\n\r\n\r\n\r\nb")
    assert text == "a\n\nb"


def test_chunk_text_splits_and_drops_empties():
    text = "\n\n".join(f"Paragraph {i} " + "word " * 50 for i in range(20))
    chunks = chunk_text(text, chunk_size=500, chunk_overlap=50)
    assert len(chunks) > 1
    assert all(c.strip() for c in chunks)


def test_persona_where_filter_single_author():
    assert persona_where_filter(authors=["Plato"]) == {"author": {"$in": ["Plato"]}}


def test_persona_where_filter_combines_with_or():
    where = persona_where_filter(authors=["Plato"], traditions=["Stoicism"])
    assert where == {
        "$or": [{"author": {"$in": ["Plato"]}}, {"tradition": {"$in": ["Stoicism"]}}]
    }


def test_persona_where_filter_none_when_empty():
    assert persona_where_filter() is None


class _FakeCollection:
    name = "corpus"

    def __init__(self):
        self.deleted_where = None

    def delete(self, where):
        self.deleted_where = where

    def get(self, where, include):
        return {"ids": ["a", "b"]}

    def count(self):
        return 42


class _FakeClient:
    def __init__(self):
        self.dropped = None

    def delete_collection(self, name):
        self.dropped = name


class _FakeChroma:
    def __init__(self):
        self._collection = _FakeCollection()
        self._client = _FakeClient()


def test_store_helpers_wrap_chroma_internals():
    store = _FakeChroma()
    delete_work_chunks(store, "tao")
    assert store._collection.deleted_where == {"work_id": "tao"}
    assert count_work_chunks(store, "tao") == 2
    assert count_all_chunks(store) == 42
    drop_collection(store)
    assert store._client.dropped == "corpus"
