import json
import sqlite3
import zipfile
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

import app.agents.persona_forge as forge_module
import app.api.library as library_module
import app.db as db_module
import app.rag.store as store_module
from app.agents.persona_forge import add_author_variant, persist_card
from app.agents.personas import PersonaCard, load_personas
from app.config import Settings
from app.main import app
from app.rag.ingest import ingest_text
from app.rag.store import persona_where_filter
from app.rag.uploads import (
    UploadValidationError,
    extract_text,
    match_persona,
    merge_works,
    new_work_id,
    validate_size,
)

# --- fixtures and fakes ---


class FakeStore:
    """Minimal Chroma stand-in: records calls, shares _collection like Chroma."""

    def __init__(self):
        self.events = []
        self._collection = self

    def delete(self, where):
        self.events.append(("delete", where))

    def add_documents(self, docs, ids=None):
        self.events.append(("add", [d.metadata for d in docs], ids))


class ExplodingStore(FakeStore):
    def add_documents(self, docs, ids=None):
        raise RuntimeError("embedder down")


def _client(tmp_path, monkeypatch, store=None, **settings_over):
    settings = Settings(
        database_path=tmp_path / "test.db",
        upload_dir=tmp_path / "uploads",
        **{"persona_autogen": False, **settings_over},
    )
    monkeypatch.setattr(db_module, "get_settings", lambda: settings)
    monkeypatch.setattr(store_module, "get_vector_store", lambda *a, **k: None)
    monkeypatch.setattr(library_module, "get_settings", lambda: settings)
    # Never let a test rewrite the repo's real persona YAML files.
    monkeypatch.setattr(library_module, "add_author_variant", lambda pid, author: None)
    library_module._upload_hits.clear()
    client = TestClient(app)
    client.__enter__()
    client.app.state.store = store or FakeStore()
    return client, settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_client, _ = _client(tmp_path, monkeypatch)
    yield test_client
    test_client.__exit__(None, None, None)


def _pdf_bytes(text: str) -> bytes:
    """A minimal valid one-page PDF carrying one line of text."""
    stream = f"BT /F1 24 Tf 100 700 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        b" /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return bytes(out)


def _epub_bytes() -> bytes:
    """A minimal EPUB (zip) with one chapter."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>\n<container version="1.0"'
            ' xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
            '<rootfile full-path="OPS/content.opf"'
            ' media-type="application/oebps-package+xml"/>'
            "</rootfiles></container>",
        )
        z.writestr(
            "OPS/content.opf",
            '<?xml version="1.0"?>\n<package xmlns="http://www.idpf.org/2007/opf"'
            ' unique-identifier="id" version="2.0">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            "<dc:identifier id=\"id\">t</dc:identifier><dc:title>T</dc:title>"
            "<dc:language>en</dc:language></metadata>"
            '<manifest><item id="ch1" href="ch1.xhtml"'
            ' media-type="application/xhtml+xml"/></manifest>'
            '<spine><itemref idref="ch1"/></spine></package>',
        )
        z.writestr(
            "OPS/ch1.xhtml",
            "<html><body><p>The wise person neither fears death"
            " nor longs for it.</p></body></html>",
        )
    return buf.getvalue()


# --- validation + extraction units ---


def test_extract_plain_text():
    raw = b"# Chapter\n\nSome words."
    assert extract_text("notes.md", raw) == "# Chapter\n\nSome words."


def test_extract_rejects_bad_extension():
    with pytest.raises(UploadValidationError) as err:
        extract_text("book.docx", b"anything")
    assert err.value.status == 415


def test_extract_rejects_invalid_utf8():
    with pytest.raises(UploadValidationError) as err:
        extract_text("book.txt", b"\xff\xfe binary \x00")
    assert err.value.status == 422


def test_extract_rejects_nul_bytes():
    with pytest.raises(UploadValidationError) as err:
        extract_text("book.txt", b"text\x00with nul")
    assert err.value.status == 422


def test_validate_size_limits(tmp_path):
    settings = Settings(max_upload_mb=0)
    with pytest.raises(UploadValidationError) as err:
        validate_size(b"one byte is too many", settings)
    assert err.value.status == 413
    with pytest.raises(UploadValidationError):
        validate_size(b"", settings)


def test_extract_pdf():
    text = extract_text("letters.pdf", _pdf_bytes("Wisdom from a PDF"))
    assert "Wisdom from a PDF" in text


def test_extract_pdf_rejects_non_pdf():
    with pytest.raises(UploadValidationError) as err:
        extract_text("fake.pdf", b"not a pdf at all")
    assert err.value.status == 415


def test_extract_epub():
    text = extract_text("chapters.epub", _epub_bytes())
    assert "neither fears death nor longs for it" in text


def test_extract_epub_rejects_non_zip():
    with pytest.raises(UploadValidationError) as err:
        extract_text("fake.epub", b"definitely not a zip")
    assert err.value.status == 415


# --- author matching ---


def test_match_persona_exact():
    card, kind = match_persona("Marcus Aurelius")
    assert kind == "exact"
    assert card.id == "marcus_aurelius"


def test_match_persona_folded_variant_is_probable():
    card, kind = match_persona("marcus  aurelius")
    assert kind == "probable"
    assert card.id == "marcus_aurelius"


def test_match_persona_none_for_unknown_author():
    card, kind = match_persona("Plotinus")
    assert (card, kind) == (None, "none")


def test_match_persona_plato_not_plotinus_regression():
    card, kind = match_persona("Plato")
    assert kind == "exact"
    assert card.id == "plato"


# --- merge + ingest units ---


def test_merge_works_pure_and_ready_only():
    manifest = [{"id": "w1", "title": "T", "author": "A"}]
    uploads = [
        {
            "id": "u1",
            "title": "UT",
            "author": "UA",
            "tradition": "Tr",
            "era": "E",
            "text_path": "/x/u1.txt",
            "chunks": 7,
            "status": "ready",
        },
        {
            "id": "u2",
            "title": "Indexing",
            "author": "UB",
            "tradition": "Tr",
            "era": "E",
            "text_path": "/x/u2.txt",
            "chunks": 0,
            "status": "indexing",
        },
    ]
    merged = merge_works(manifest, uploads)
    assert [w["id"] for w in merged] == ["w1", "u1"]
    assert merged[0]["source"] == "gutenberg"
    assert merged[1]["source"] == "upload"
    assert merged[1]["chunks"] == 7
    # pure: inputs untouched
    assert manifest == [{"id": "w1", "title": "T", "author": "A"}]
    assert "source" not in uploads[0]


def test_ingest_text_metadata_and_delete_before_add():
    store = FakeStore()
    work = {
        "id": "upload_x",
        "title": "T",
        "author": "A",
        "tradition": "Tr",
        "era": "E",
        "source": "upload",
    }
    n = ingest_text(store, work, "word " * 3000)
    assert n > 1
    assert store.events[0] == ("delete", {"work_id": "upload_x"})
    _, metadata, ids = store.events[1]
    assert ids[0] == "upload_x:0"
    assert metadata[0]["work_id"] == "upload_x"
    assert metadata[0]["source"] == "upload"
    assert "gutenberg_id" not in metadata[0]


# --- endpoint ---

SENECA = (
    "It is not that we have a short time to live, but that we waste a lot of it. "
    * 60
).encode()


def _post(client, content=SENECA, filename="seneca.txt", **fields):
    data = {"title": "Letter I", "author": "Seneca", **fields}
    data = {k: v for k, v in data.items() if v is not None}
    return client.post(
        "/library/uploads",
        files={"file": (filename, content, "application/octet-stream")},
        data=data,
    )


def test_upload_happy_path_registers_and_serves(client):
    response = _post(client, tradition="Stoicism", era="Roman Empire")
    assert response.status_code == 201
    body = response.json()
    assert body["match"] == "none"
    assert body["persona_id"] is None
    assert body["persona_status"] == "skipped"  # autogen off in this fixture
    work = body["work"]
    assert work["id"].startswith("upload_letter_i_")
    assert work["chunks"] > 1
    assert work["source"] == "upload"

    works = client.get("/library/works").json()
    listed = next(w for w in works if w["id"] == work["id"])
    assert listed["chunks"] == work["chunks"]
    assert "text_path" not in listed

    text = client.get(f"/library/works/{work['id']}/text").json()
    assert "waste a lot of it" in text["text"]
    assert text["persona_id"] is None

    session = client.post("/sessions", json={"work_id": work["id"]}).json()
    assert session["work_id"] == work["id"]
    assert session["title"] == "Reading Letter I"


def test_upload_defaults_for_optional_fields(client):
    body = _post(client).json()
    assert body["work"]["tradition"] == "Unknown tradition"
    assert body["work"]["era"] == "Unknown era"


def test_upload_exact_author_match(client):
    body = _post(client, author="Marcus Aurelius").json()
    assert body["match"] == "exact"
    assert body["persona_id"] == "marcus_aurelius"
    assert body["persona_status"] == "existing"


def test_upload_ambiguous_requires_confirmation(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    variants = []
    monkeypatch.setattr(
        library_module,
        "add_author_variant",
        lambda pid, author: variants.append((pid, author)),
    )
    try:
        first = _post(client, author="marcus  aurelius")
        assert first.status_code == 409
        candidate = first.json()["candidate"]
        assert candidate["id"] == "marcus_aurelius"

        confirmed = _post(
            client, author="marcus  aurelius", confirm_persona_id="marcus_aurelius"
        )
        assert confirmed.status_code == 201
        assert confirmed.json()["match"] == "confirmed"
        assert confirmed.json()["persona_id"] == "marcus_aurelius"
        # Confirmed variants extend the card so future matches are exact.
        assert variants == [("marcus_aurelius", "marcus  aurelius")]

        declined = _post(client, author="marcus  aurelius", confirm_persona_id="decline")
        assert declined.status_code == 201
        assert declined.json()["match"] == "none"
        assert declined.json()["persona_id"] is None
    finally:
        client.__exit__(None, None, None)


def test_upload_bad_confirm_id_422(client):
    response = _post(client, author="marcus  aurelius", confirm_persona_id="socrates")
    assert response.status_code == 422


def test_upload_missing_title_422(client):
    assert _post(client, title="   ").status_code == 422


def test_upload_bad_extension_415(client):
    assert _post(client, filename="book.docx").status_code == 415


def test_upload_failure_cleans_up(tmp_path, monkeypatch):
    client, settings = _client(tmp_path, monkeypatch, store=ExplodingStore())
    try:
        response = _post(client)
        assert response.status_code == 502
        assert list(settings.upload_dir.iterdir()) == []
        works = client.get("/library/works").json()
        assert not any(w["id"].startswith("upload_") for w in works)
    finally:
        client.__exit__(None, None, None)


def test_upload_disabled_403(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch, upload_enabled=False)
    try:
        assert _post(client).status_code == 403
    finally:
        client.__exit__(None, None, None)


def test_upload_oversize_413(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch, max_upload_mb=0)
    try:
        assert _post(client).status_code == 413
    finally:
        client.__exit__(None, None, None)


def test_upload_rate_limit_429(client, monkeypatch):
    monkeypatch.setattr(library_module, "_UPLOAD_RATE_LIMIT", 2)
    assert _post(client).status_code == 201
    assert _post(client, title="Second").status_code == 201
    assert _post(client, title="Third").status_code == 429


def test_upload_text_path_traversal_refused(client, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret", encoding="utf-8")
    conn = sqlite3.connect(tmp_path / "test.db")
    conn.execute(
        "INSERT INTO uploaded_works"
        " (id, title, author, tradition, era, text_path, chunks, status, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "upload_evil_1",
            "Evil",
            "Nobody",
            "Tr",
            "E",
            str(secret),
            1,
            "ready",
            "2026-08-01",
        ),
    )
    conn.commit()
    conn.close()
    assert client.get("/library/works/upload_evil_1/text").status_code == 404


def test_new_work_id_shape():
    wid = new_work_id("On the Shortness of Life!")
    assert wid.startswith("upload_on_the_shortness_of_life_")
    assert len(wid.rsplit("_", 1)[1]) == 6


# --- Phase 3: eager forge + author-variant card extension ---

CARD_JSON = json.dumps(
    {
        "name": "Seneca",
        "era": "Roman Empire, c. 4 BC-65 AD",
        "tradition": "Stoicism",
        "color": "emerald",
        "greeting": "It is not that we have a short time to live, "
        "but that we waste much of it. What troubles you?",
        "greeting_zh": "我们并非生命短暂，而是浪费太多。何事困扰你？",
        "voice": "You are Seneca the Younger: epistolary, direct, consoling yet firm.",
        "worldview": "Virtue is sufficient for happiness; fortune's gifts are loans.",
        "style_rules": [
            "Console through reason, not sentiment.",
            "Quote the provided passages when they serve.",
            "Address the reader as a friend in letters.",
            "Keep replies under 160 words unless depth is asked.",
        ],
    },
    ensure_ascii=False,
)


async def _no_reference(author, client):
    return None


def test_upload_eager_forge_creates_persona(tmp_path, monkeypatch):
    personas_dir = tmp_path / "personas"
    personas_dir.mkdir()
    real_get_or_generate = forge_module.get_or_generate

    async def forge_into_tmp(author, work, llm):
        return await real_get_or_generate(author, work, llm, personas_dir=personas_dir)

    client, _ = _client(tmp_path, monkeypatch, persona_autogen=True)
    try:
        monkeypatch.setattr(library_module, "get_or_generate", forge_into_tmp)
        monkeypatch.setattr(forge_module, "fetch_author_reference", _no_reference)
        monkeypatch.setattr(
            library_module,
            "get_chat_model",
            lambda s: FakeListChatModel(responses=[CARD_JSON]),
        )
        response = _post(client, author="Seneca")
        assert response.status_code == 201
        body = response.json()
        assert body["persona_status"] == "created"
        assert body["persona_id"] == "seneca"
        assert body["work"]["persona_id"] == "seneca"
        assert (personas_dir / "seneca.yaml").exists()
    finally:
        client.__exit__(None, None, None)


def test_upload_forge_failure_is_nonfatal(tmp_path, monkeypatch):
    async def explode(author, work, llm):
        raise RuntimeError("LLM down")

    client, _ = _client(tmp_path, monkeypatch, persona_autogen=True)
    try:
        monkeypatch.setattr(library_module, "get_or_generate", explode)
        monkeypatch.setattr(library_module, "get_chat_model", lambda s: None)
        response = _post(client, author="Seneca")
        assert response.status_code == 201
        body = response.json()
        assert body["persona_status"] == "failed"
        assert body["persona_id"] is None
        works = client.get("/library/works").json()
        assert any(w["id"] == body["work"]["id"] for w in works)
    finally:
        client.__exit__(None, None, None)


def test_add_author_variant_rewrites_card(tmp_path):
    original = PersonaCard(
        id="seneca",
        name="Seneca",
        era="Roman Empire",
        tradition="Stoicism",
        color="emerald",
        authors=["Seneca"],
        traditions=["Stoicism"],
        voice="Epistolary and firm.",
    )
    persist_card(original, tmp_path)

    updated = add_author_variant("seneca", "Lucius Annaeus Seneca", personas_dir=tmp_path)
    assert updated is not None
    assert updated.authors == ["Seneca", "Lucius Annaeus Seneca"]

    reloaded = load_personas(tmp_path)["seneca"]
    assert "Lucius Annaeus Seneca" in reloaded.authors
    assert reloaded.voice == "Epistolary and firm."

    where = persona_where_filter(authors=reloaded.authors, traditions=reloaded.traditions)
    assert "Lucius Annaeus Seneca" in str(where)


def test_add_author_variant_idempotent_and_unknown(tmp_path):
    persist_card(
        PersonaCard(
            id="seneca",
            name="Seneca",
            era="Roman Empire",
            tradition="Stoicism",
            color="emerald",
            authors=["Seneca"],
        ),
        tmp_path,
    )
    card = add_author_variant("seneca", "Seneca", personas_dir=tmp_path)
    assert card is not None and card.authors == ["Seneca"]
    assert add_author_variant("nobody", "X", personas_dir=tmp_path) is None
