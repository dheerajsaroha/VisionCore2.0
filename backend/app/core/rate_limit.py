"""
Simple in-memory rate limiter for auth endpoints.
Production: Replace with Redis-backed limiter (e.g., Slowapi + Redis).
Uses lazy Redis initialization (same pattern as app/core/security.py) so the
module does NOT block startup or imports when Redis is unavailable.
"""
import logging
import threading
import time
from fastapi import HTTPException, Request
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Lazy Redis Client (optional) ───────────────────────────────────────────
# Redis is instantiated lazily with timeouts so that an unavailable Redis
# server does NOT block application startup or cause imports to hang.
_redis_clients: dict = {}
_fallback_lock = threading.Lock()
_fallback_windows: dict[str, tuple[int, float]] = {}


def _check_local_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """Bounded-process fallback when Redis is unavailable.

    It intentionally does not claim distributed correctness; it prevents a
    Redis outage from turning authentication endpoints into unlimited paths.
    """
    now = time.monotonic()
    with _fallback_lock:
        count, reset_at = _fallback_windows.get(key, (0, now + window_seconds))
        if now >= reset_at:
            count, reset_at = 0, now + window_seconds
        count += 1
        _fallback_windows[key] = (count, reset_at)
        # Prevent unbounded memory growth from spoofed client addresses.
        if len(_fallback_windows) > 10000:
            expired = [k for k, (_, expiry) in _fallback_windows.items() if expiry <= now]
            for expired_key in expired:
                _fallback_windows.pop(expired_key, None)
        return count <= max_requests

def _get_redis():
    """Return an async Redis client bound to the *current* event loop.

    A single cached client is only valid while one event loop lives for the
    process. The test client creates a loop per request, so a globally cached
    client ends up attached to a dead loop and every pipeline raises "Event
    loop is closed" -- which silently demotes a distributed rate limit to the
    per-process fallback below. Keyed by loop so each gets a working client.
    """
    import asyncio

    import redis.asyncio as redis_async

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    key = id(loop) if loop is not None else None
    cached = _redis_clients.get(key)
    if cached is not None:
        return cached

    client = redis_async.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        retry_on_timeout=False,
    )
    for stale_key, stale in list(_redis_clients.items()):
        if stale_key != key:
            owner = getattr(stale, "_visioncore_loop", None)
            if owner is None or owner.is_closed():
                _redis_clients.pop(stale_key, None)
    try:
        client._visioncore_loop = loop
    except Exception:  # noqa: BLE001 - attribute is best effort
        pass
    _redis_clients[key] = client
    return client


def rate_limit_dependency(max_requests: int = 5, window_seconds: int = 60):
    """
    FastAPI dependency for rate limiting by client IP using Redis.
    Usage: Depends(rate_limit_dependency(max_requests=5, window_seconds=60))
    """
    async def _check(request: Request):
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{request.url.path}:{client_ip}"
        
        # Rate limiting must never break auth flows during tests.
        try:
            client = _get_redis()
            async with client.pipeline(transaction=True) as pipe:
                try:
                    pipe.incr(key)
                    pipe.expire(key, window_seconds, nx=True)
                    results = await pipe.execute()

                    current_requests = results[0]

                    if current_requests > max_requests:
                        logger.warning(
                            "Rate limit exceeded for %s on %s",
                            client_ip,
                            request.url.path,
                        )
                        raise HTTPException(
                            status_code=429,
                            detail="Too many requests. Please try again later.",
                        )
                except Exception as e:
                    # The deliberate 429 raised just above is an HTTPException,
                    # and this bare handler used to swallow it, log a bogus
                    # "Redis rate limiter unavailable", and hand the request to
                    # the per-process fallback -- whose counter was still empty,
                    # so it allowed the call. The Redis limiter therefore never
                    # limited anything; every request was counted locally, which
                    # also made the effective limit N x the intended one across
                    # multiple workers. Re-raise it, as the outer handler below
                    # already does.
                    if isinstance(e, HTTPException):
                        raise
                    logger.warning("Redis rate limiter unavailable; using local fallback: %s", e)
                    if not _check_local_limit(key, max_requests, window_seconds):
                        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
                    return True
        except Exception as e:
            # Do not catch the deliberate 429 raised by the local fallback.
            if isinstance(e, HTTPException):
                raise
            logger.warning("Rate limiter unavailable; using local fallback: %s", e)
            if not _check_local_limit(key, max_requests, window_seconds):
                raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
            return True

        return True
    return _check
