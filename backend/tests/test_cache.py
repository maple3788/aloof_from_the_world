import fnmatch

from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel

import app.agents.critic as critic_module
import app.rag.store as store_module
from app.agents.critic import _critique_one
from app.cache import NullCache, RedisCache, critic_key, retrieval_key
from app.rag.store import retrieve

CRITIC_OK = '{"supported": true, "citation_indices": [1], "note": null}'


class DictCache:
    """In-memory stand-in for the cache interface."""

    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ttl):
        self.data[key] = value


class FakeRedisClient:
    """Minimal async client double for RedisCache (stores raw JSON strings)."""

    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ex=None):
        self.data[key] = value

    async def delete(self, *keys):
        removed = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                removed += 1
        return removed

    async def scan_iter(self, match=None):
        for key in list(self.data):
            if match is None or fnmatch.fnmatch(key, match):
                yield key


class CountingStore:
    def __init__(self):
        self.calls = 0

    def similarity_search(self, query, k=6, filter=None):
        self.calls += 1
        return [
            Document(
                page_content=f"passage for {query}",
                metadata={"work_id": "republic", "chunk_index": 0},
            )
            for _ in range(3)
        ]


class CountingChatModel(FakeListChatModel):
    calls: int = 0

    def _call(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        return super()._call(messages, stop=stop, run_manager=run_manager, **kwargs)


def make_response() -> dict:
    return {
        "responder": "socrates",
        "responder_name": "Socrates",
        "content": "Virtue is knowledge.",
        "citations": [],
        "critic_note": None,
        "docs": [
            Document(
                page_content="Excerpt one. " * 20,
                metadata={"work_id": "republic", "title": "Republic", "chunk_index": 0},
            )
        ],
    }


def test_keys_are_deterministic_and_scoped():
    assert retrieval_key("q", None, 6) == retrieval_key("q", None, 6)
    assert retrieval_key("q", None, 6) != retrieval_key("q", {"author": {"$in": ["Plato"]}}, 6)
    assert retrieval_key("q", None, 6) != retrieval_key("other", None, 6)
    assert critic_key("r", "c") == critic_key("r", "c")
    assert critic_key("r", "c") != retrieval_key("r", None, 6)


async def test_null_cache_is_a_noop():
    cache = NullCache()
    await cache.set("k", {"v": 1}, 60)
    assert await cache.get("k") is None
    assert await cache.clear_prefix("rag") == 0


async def test_redis_cache_round_trip_and_flush():
    cache = RedisCache("redis://localhost:6379/0")
    cache._client = FakeRedisClient()

    await cache.set("aloof:rag:abc", [{"page_content": "p", "metadata": {}}], 60)
    await cache.set("aloof:critic:xyz", {"supported": True}, 60)
    assert await cache.get("aloof:rag:abc") == [{"page_content": "p", "metadata": {}}]
    assert await cache.get("aloof:missing") is None

    assert await cache.clear_prefix("rag") == 1
    assert await cache.get("aloof:rag:abc") is None
    assert await cache.get("aloof:critic:xyz") == {"supported": True}


async def test_retrieve_caches_results(monkeypatch):
    cache = DictCache()
    monkeypatch.setattr(store_module, "get_cache", lambda: cache)
    store = CountingStore()

    first = await retrieve(store, "What is virtue?")
    second = await retrieve(store, "What is virtue?")

    assert store.calls == 1
    assert [d.page_content for d in second] == [d.page_content for d in first]
    assert second[0].metadata == first[0].metadata


async def test_retrieve_without_cache_hits_store_every_time(monkeypatch):
    monkeypatch.setattr(store_module, "get_cache", lambda: NullCache())
    store = CountingStore()

    await retrieve(store, "What is virtue?")
    await retrieve(store, "What is virtue?")

    assert store.calls == 2


async def test_critic_caches_llm_verdict(monkeypatch):
    cache = DictCache()
    monkeypatch.setattr(critic_module, "get_cache", lambda: cache)
    llm = CountingChatModel(responses=[CRITIC_OK])
    resp = make_response()

    first = await _critique_one(resp, llm, True)
    second = await _critique_one(resp, llm, True)

    assert llm.calls == 1
    assert first["citations"][0]["chunk_index"] == second["citations"][0]["chunk_index"]
