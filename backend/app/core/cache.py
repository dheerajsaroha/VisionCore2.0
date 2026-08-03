"""
core/cache.py — Redis-based caching layer for permissions and authorization.

Provides a generic caching interface with:
- TTL-based key expiration
- Graceful degradation when Redis is unavailable
- Automatic JSON serialization/deserialization
- Lazy Redis connection (same pattern as app/core/security.py and app/core/rate_limit.py)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional, TypeVar

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ── Lazy Redis Client (optional) ───────────────────────────────────────────
# Redis is instantiated lazily with timeouts so that an unavailable Redis
# server does NOT block application startup or cause imports to hang.
_redis_client_cache = None

def _get_redis():
    """Return a lazily-initialized async Redis client with connection timeouts."""
    global _redis_client_cache
    if _redis_client_cache is None:
        import redis.asyncio as redis_async
        _redis_client_cache = redis_async.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
        )
    return _redis_client_cache


# ── Permission Cache Keys ─────────────────────────────────────────────────────
PCK = "perm:cache:"  # permission cache key prefix


def _permission_cache_key(role_id: int) -> str:
    """Generate a cache key for a role's permissions."""
    return f"{PCK}role:{role_id}"


def _module_cache_key() -> str:
    """Generate a cache key for module listing."""
    return f"{PCK}modules"


def _all_permissions_key() -> str:
    """Generate a cache key for all permissions."""
    return f"{PCK}all"


# ── Generic Cache Operations ──────────────────────────────────────────────────

async def cache_get(key: str) -> Optional[str]:
    """Get a value from cache. Returns None on miss or Redis failure."""
    try:
        client = _get_redis()
        val = await client.get(key)
        if isinstance(val, bytes):
            return val.decode("utf-8")
        return val  # str | None
    except Exception as exc:
        logger.warning("Cache GET failed for key=%s: %s", key, exc)
        return None


async def cache_set(key: str, value: str, ttl: int = 300) -> bool:
    """Set a value in cache with TTL (seconds). Returns False on failure."""
    try:
        client = _get_redis()
        await client.setex(key, ttl, value)
        return True
    except Exception as exc:
        logger.warning("Cache SET failed for key=%s: %s", key, exc)
        return False


async def cache_delete(key: str) -> bool:
    """Delete a key from cache. Returns False on failure."""
    try:
        client = _get_redis()
        await client.delete(key)
        return True
    except Exception as exc:
        logger.warning("Cache DELETE failed for key=%s: %s", key, exc)
        return False


async def cache_delete_pattern(pattern: str) -> bool:
    """Delete all keys matching a glob pattern. Returns False on failure."""
    try:
        client = _get_redis()
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await client.delete(*keys)
            if cursor == 0:
                break
        return True
    except Exception as exc:
        logger.warning("Cache DELETE pattern failed for pattern=%s: %s", pattern, exc)
        return False


# ── JSON Cache Operations ─────────────────────────────────────────────────────

async def cache_get_json(key: str) -> Optional[Any]:
    """Get a JSON value from cache. Returns None on miss or parse failure."""
    raw = await cache_get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("Cache JSON decode failed for key=%s: %s", key, exc)
        return None


async def cache_set_json(key: str, value: Any, ttl: int = 300) -> bool:
    """Set a JSON value in cache with TTL (seconds)."""
    try:
        raw = json.dumps(value, default=str)
        return await cache_set(key, raw, ttl)
    except (TypeError, ValueError) as exc:
        logger.warning("Cache JSON encode failed for key=%s: %s", key, exc)
        return False


# ── Permission-specific Cache Operations ──────────────────────────────────────

async def cache_role_permissions(role_id: int, permission_names: list[str], ttl: int = 300) -> bool:
    """Cache the set of permission names for a role."""
    return await cache_set_json(_permission_cache_key(role_id), permission_names, ttl)


async def get_cached_role_permissions(role_id: int) -> Optional[list[str]]:
    """Get cached permission names for a role."""
    return await cache_get_json(_permission_cache_key(role_id))


async def cache_all_permissions(permissions: list[dict], ttl: int = 600) -> bool:
    """Cache the full list of all permissions."""
    return await cache_set_json(_all_permissions_key(), permissions, ttl)


async def get_cached_all_permissions() -> Optional[list[dict]]:
    """Get cached full permission list."""
    return await cache_get_json(_all_permissions_key())


async def cache_modules(modules: list[dict], ttl: int = 600) -> bool:
    """Cache the module listing."""
    return await cache_set_json(_module_cache_key(), modules, ttl)


async def get_cached_modules() -> Optional[list[dict]]:
    """Get cached module listing."""
    return await cache_get_json(_module_cache_key())


async def invalidate_role_permissions(role_id: int) -> bool:
    """Invalidate permission cache for a specific role."""
    return await cache_delete(_permission_cache_key(role_id))


async def invalidate_all_permissions() -> bool:
    """Invalidate the global permission cache."""
    await cache_delete(_all_permissions_key())
    await cache_delete(_module_cache_key())
    return True


async def invalidate_all_role_permissions() -> int:
    """Invalidate permission caches for ALL roles. Returns count of keys deleted."""
    try:
        client = _get_redis()
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match=f"{PCK}role:*", count=100)
            if keys:
                await client.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
        return deleted
    except Exception as exc:
        logger.warning("Cache invalidate all roles failed: %s", exc)
        return 0
