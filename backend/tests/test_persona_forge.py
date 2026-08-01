import asyncio
import json
from typing import ClassVar

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

import app.agents.persona_forge as forge_module
import app.api.library as library_module
import app.db as db_module
import app.rag.store as store_module
from app.agents.persona_forge import (
    PersonaForgeError,
    _parse_card_json,
    fetch_author_reference,
    generate_persona_card,
    get_or_generate,
    slugify,
)
from app.agents.personas import load_personas
from app.config import Settings
from app.main import app

VALID_CARD_JSON = json.dumps(
    {
        "name": "Marcus Aurelius",
        "era": "Roman Empire, 121-180 AD",
        "tradition": "Stoicism",
        "color": "violet",
        "greeting": "Waste no more time arguing what a good man should be. Be one.",
        "greeting_zh": "别再空谈一个好人该是什么样，去做一个好人。",
        "voice": "You are Marcus Aurelius, emperor and Stoic: you speak in short "
        "meditative reflections addressed to yourself, calm and duty-bound.",
        "worldview": "The universe is transformation; life is opinion. Fame is smoke; "
        "only virtue — justice, temperance, courage, wisdom — is good. Do what nature "
        "demands in the present moment.",
        "style_rules": [
            "Speak in short meditative reflections.",
            "Quote or paraphrase the provided source passages when apt.",
            "Frame adversity as material for virtue.",
            "Keep replies under 160 words unless the user asks for depth.",
        ],
    }
)

MEDITATIONS_WORK = {
    "id": "marcus_meditations",
    "title": "Meditations",
    "author": "Marcus Aurelius",
    "tradition": "Stoicism",
    "era": "Roman Empire",
    "gutenberg_id": 2680,
}


async def _no_reference(author, client):
    return None


def test_parse_card_json_extracts_object_from_prose():
    fields = _parse_card_json(f"Here you go! {VALID_CARD_JSON} — done")
    assert fields is not None
    assert fields.name == "Marcus Aurelius"
    assert fields.color == "violet"


def test_parse_card_json_rejects_garbage_and_schema_violations():
    assert _parse_card_json("no json here") is None
    assert _parse_card_json('{"name": "Marcus"}') is None

    bad_color = json.loads(VALID_CARD_JSON)
    bad_color["color"] = "teal"  # reserved for the tutor identity
    assert _parse_card_json(json.dumps(bad_color)) is None

    too_few_rules = json.loads(VALID_CARD_JSON)
    too_few_rules["style_rules"] = ["Only one."]
    assert _parse_card_json(json.dumps(too_few_rules)) is None


def test_slugify():
    assert slugify("Marcus Aurelius") == "marcus_aurelius"
    assert slugify("Niccolo Machiavelli") == "niccolo_machiavelli"
    assert slugify("Laozi") == "laozi"


async def test_generate_persona_card_forces_server_owned_fields():
    llm = FakeListChatModel(responses=[VALID_CARD_JSON])
    card = await generate_persona_card(llm, MEDITATIONS_WORK, reference=None)
    assert card.id == "marcus_aurelius"
    assert card.authors == ["Marcus Aurelius"]
    assert card.traditions == ["Stoicism"]
    assert card.name == "Marcus Aurelius"


async def test_generate_persona_card_repairs_once_then_raises():
    llm = FakeListChatModel(responses=["garbage", VALID_CARD_JSON])
    card = await generate_persona_card(llm, MEDITATIONS_WORK, reference=None)
    assert card.id == "marcus_aurelius"

    llm = FakeListChatModel(responses=["garbage", "still garbage"])
    with pytest.raises(PersonaForgeError):
        await generate_persona_card(llm, MEDITATIONS_WORK, reference=None)


def _wiki_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_author_reference_direct_hit():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Marcus_Aurelius" in request.url.path
        return httpx.Response(
            200,
            json={
                "type": "standard",
                "title": "Marcus Aurelius",
                "extract": "Roman emperor and Stoic philosopher.",
            },
        )

    async with _wiki_client(handler) as client:
        reference = await fetch_author_reference("Marcus Aurelius", client)
    assert reference == "Marcus Aurelius: Roman emperor and Stoic philosopher."


async def test_fetch_author_reference_opensearch_fallback():
    def handler(request: httpx.Request) -> httpx.Response:
        if "summary" in request.url.path:
            if request.url.path.endswith("John_Stuart_Mill"):
                return httpx.Response(
                    200,
                    json={
                        "type": "standard",
                        "title": "John Stuart Mill",
                        "extract": "English philosopher.",
                    },
                )
            return httpx.Response(404)
        return httpx.Response(200, json=["Mill", ["John Stuart Mill"], [], []])

    async with _wiki_client(handler) as client:
        reference = await fetch_author_reference("Mill", client)
    assert reference == "John Stuart Mill: English philosopher."


async def test_fetch_author_reference_disambiguation_hits_opensearch():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "summary" in request.url.path:
            return httpx.Response(
                200, json={"type": "disambiguation", "title": "Mill", "extract": ""}
            )
        return httpx.Response(404)

    async with _wiki_client(handler) as client:
        assert await fetch_author_reference("Mill", client) is None
    assert any("opensearch" in url for url in calls)


async def test_fetch_author_reference_network_failure_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    async with _wiki_client(handler) as client:
        assert await fetch_author_reference("Marcus Aurelius", client) is None


async def test_get_or_generate_returns_existing_card_without_llm():
    republic = {
        "id": "plato_republic",
        "title": "The Republic",
        "author": "Plato",
        "tradition": "Western philosophy",
        "era": "Classical Greece",
        "gutenberg_id": 1497,
    }
    # Empty responses list: raises if the LLM were ever invoked.
    card, created = await get_or_generate(
        "Plato", republic, llm=FakeListChatModel(responses=[])
    )
    assert card.id == "plato"
    assert created is False


async def test_get_or_generate_forges_and_goes_live(tmp_path, monkeypatch):
    monkeypatch.setattr(forge_module, "fetch_author_reference", _no_reference)
    llm = FakeListChatModel(responses=[VALID_CARD_JSON])

    assert load_personas(tmp_path) == {}  # cached empty before the forge
    card, created = await get_or_generate(
        "Marcus Aurelius", MEDITATIONS_WORK, llm, personas_dir=tmp_path
    )
    assert created is True
    assert card.id == "marcus_aurelius"
    assert (tmp_path / "marcus_aurelius.yaml").exists()
    # Live without restart: the cache bust makes the new card resolvable.
    assert load_personas(tmp_path)["marcus_aurelius"].authors == ["Marcus Aurelius"]


async def test_get_or_generate_serializes_concurrent_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(forge_module, "fetch_author_reference", _no_reference)

    class SlowFake(FakeListChatModel):
        calls: ClassVar[int] = 0

        async def ainvoke(self, *args, **kwargs):
            SlowFake.calls += 1
            await asyncio.sleep(0.05)
            return await super().ainvoke(*args, **kwargs)

    llm = SlowFake(responses=[VALID_CARD_JSON])
    (first, created_first), (second, created_second) = await asyncio.gather(
        get_or_generate("Marcus Aurelius", MEDITATIONS_WORK, llm, personas_dir=tmp_path),
        get_or_generate("Marcus Aurelius", MEDITATIONS_WORK, llm, personas_dir=tmp_path),
    )
    assert first.id == second.id == "marcus_aurelius"
    assert (created_first, created_second) in [(True, False), (False, True)]
    assert SlowFake.calls == 1


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = Settings(database_path=tmp_path / "test.db")
    monkeypatch.setattr(db_module, "get_settings", lambda: settings)
    monkeypatch.setattr(store_module, "get_vector_store", lambda *a, **k: None)
    with TestClient(app) as test_client:
        yield test_client


def test_generate_endpoint_returns_existing_persona(client):
    response = client.post("/personas/generate", json={"work_id": "plato_republic"})
    assert response.status_code == 200
    assert response.json()["id"] == "plato"


def test_generate_endpoint_unknown_work_404(client):
    assert client.post("/personas/generate", json={"work_id": "nope"}).status_code == 404


def test_generate_endpoint_autogen_disabled_403(client, monkeypatch):
    # Hermetic: act as if no card claims the author, regardless of cards on disk.
    monkeypatch.setattr(library_module, "persona_for_author", lambda author: None)
    monkeypatch.setattr(
        library_module, "get_settings", lambda: Settings(persona_autogen=False)
    )
    response = client.post("/personas/generate", json={"work_id": "marcus_meditations"})
    assert response.status_code == 403


def test_generate_endpoint_forges_new_persona(client, tmp_path, monkeypatch):
    monkeypatch.setattr(library_module, "persona_for_author", lambda author: None)
    monkeypatch.setattr(forge_module, "fetch_author_reference", _no_reference)
    monkeypatch.setattr(
        library_module,
        "get_chat_model",
        lambda settings: FakeListChatModel(responses=[VALID_CARD_JSON]),
    )
    real_get_or_generate = forge_module.get_or_generate
    monkeypatch.setattr(
        library_module,
        "get_or_generate",
        lambda author, work, llm: real_get_or_generate(
            author, work, llm, personas_dir=tmp_path
        ),
    )

    response = client.post("/personas/generate", json={"work_id": "marcus_meditations"})
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "marcus_aurelius"
    assert body["greeting_zh"]
    assert (tmp_path / "marcus_aurelius.yaml").exists()
    assert load_personas(tmp_path)["marcus_aurelius"].greeting

    repeat = client.post("/personas/generate", json={"work_id": "marcus_meditations"})
    assert repeat.status_code == 200
    assert repeat.json()["id"] == "marcus_aurelius"
