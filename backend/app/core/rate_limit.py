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
_redis_client = None
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
    """Return a lazily-initialized async Redis client with connection timeouts."""
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as redis_async
        _redis_client = redis_async.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
        )
    return _redis_client


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
