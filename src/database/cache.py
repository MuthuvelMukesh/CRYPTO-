"""Cache layer with Redis client and in-memory fallback."""

import time
from typing import Any

from src.config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger("database.cache")

_redis_client = None
_in_memory_store: dict[str, tuple[Any, float]] = {}
_is_redis_available = False


async def get_redis_client():
    """Attempt to initialize or retrieve Redis client; marks availability."""
    global _redis_client, _is_redis_available
    if _redis_client is None:
        settings = get_settings()
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2.0,
            )
            # Ping test
            await client.ping()
            _redis_client = client
            _is_redis_available = True
            logger.info("redis_connected", url=settings.REDIS_URL)
        except Exception as e:
            logger.warning("redis_unavailable_fallback_to_memory", reason=str(e))
            _is_redis_available = False
            _redis_client = None
    return _redis_client


class CacheService:
    """Unified cache interface with transparent Redis / in-memory fallback."""

    @classmethod
    async def get(cls, key: str) -> Any | None:
        client = await get_redis_client()
        if _is_redis_available and client is not None:
            try:
                return await client.get(key)
            except Exception as e:
                logger.warning("redis_get_failed_fallback_memory", key=key, error=str(e))

        # In-memory fallback
        item = _in_memory_store.get(key)
        if item is not None:
            val, expiry = item
            if expiry == 0 or time.time() < expiry:
                return val
            del _in_memory_store[key]
        return None

    @classmethod
    async def set(cls, key: str, value: Any, ttl_seconds: int = 300) -> None:
        client = await get_redis_client()
        if _is_redis_available and client is not None:
            try:
                await client.set(key, str(value), ex=ttl_seconds)
                return
            except Exception as e:
                logger.warning("redis_set_failed_fallback_memory", key=key, error=str(e))

        # In-memory fallback
        expiry = time.time() + ttl_seconds if ttl_seconds > 0 else 0
        _in_memory_store[key] = (value, expiry)

    @classmethod
    async def delete(cls, key: str) -> None:
        client = await get_redis_client()
        if _is_redis_available and client is not None:
            try:
                await client.delete(key)
                return
            except Exception:
                pass
        _in_memory_store.pop(key, None)

    @classmethod
    async def check_health(cls) -> dict[str, object]:
        start = time.perf_counter()
        client = await get_redis_client()
        if _is_redis_available and client is not None:
            try:
                await client.ping()
                latency_ms = round((time.perf_counter() - start) * 1000, 2)
                return {
                    "status": "healthy",
                    "backend": "redis",
                    "latency_ms": latency_ms,
                }
            except Exception as e:
                return {
                    "status": "degraded",
                    "backend": "in_memory_fallback",
                    "error": str(e),
                }
        return {
            "status": "healthy",
            "backend": "in_memory_fallback",
            "keys_count": len(_in_memory_store),
        }
