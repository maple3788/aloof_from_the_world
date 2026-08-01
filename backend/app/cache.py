"""Redis-backed cache with a no-op fallback.

Caching is optional: when `redis_url` is unset (or Redis is unreachable),
`get_cache()` returns a NullCache so the app keeps working local-first.
All values are JSON strings; keys are content hashes so callers never
manage key shapes beyond the builder functions below.
"""

import hashlib
import json
import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

PREFIX = "aloof"


def retrieval_key(query: str, where: dict | None, k: int) -> str:
    payload = json.dumps({"q": query, "where": where, "k": k}, sort_keys=True)
    return f"{PREFIX}:rag:{hashlib.sha256(payload.encode()).hexdigest()}"


def critic_key(response: str, context: str) -> str:
    payload = json.dumps({"r": response, "c": context})
    return f"{PREFIX}:critic:{hashlib.sha256(payload.encode()).hexdigest()}"


class NullCache:
    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        return None

    async def clear_prefix(self, prefix: str) -> int:
        return 0


class RedisCache:
    def __init__(self, url: str) -> None:
        from redis import asyncio as aioredis

        # from_url is lazy: no connection until the first command.
        self._client = aioredis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> Any | None:
        try:
            raw = await self._client.get(key)
        except Exception:
            logger.warning("Cache GET failed; treating as a miss", exc_info=True)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Corrupt cache entry at %s; ignoring", key)
            return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        try:
            await self._client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
        except Exception:
            logger.warning("Cache SET failed; skipping", exc_info=True)

    async def clear_prefix(self, prefix: str) -> int:
        removed = 0
        try:
            async for key in self._client.scan_iter(match=f"{PREFIX}:{prefix}:*"):
                removed += await self._client.delete(key)
        except Exception:
            logger.warning("Cache flush failed for prefix %s", prefix, exc_info=True)
        return removed


_cache: NullCache | RedisCache | None = None


def get_cache() -> NullCache | RedisCache:
    global _cache
    if _cache is None:
        url = get_settings().redis_url
        _cache = RedisCache(url) if url else NullCache()
        logger.info("Cache: %s", "Redis" if url else "disabled (REDIS_URL unset)")
    return _cache
