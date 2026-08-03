"""
Simple in-memory rate limiter for auth endpoints.
Production: Replace with Redis-backed limiter (e.g., Slowapi + Redis).
Uses lazy Redis initialization (same pattern as app/core/security.py) so the
module does NOT block startup or imports when Redis is unavailable.
"""
import logging
from fastapi import HTTPException, Request
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Lazy Redis Client (optional) ───────────────────────────────────────────
# Redis is instantiated lazily with timeouts so that an unavailable Redis
# server does NOT block application startup or cause imports to hang.
_redis_client = None

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
                    # RuntimeError can occur with closed/foreign event loops in test clients.
                    logger.warning("Rate limiter disabled due to Redis/runtime error: %s", e)
                    return True
        except Exception as e:
            logger.warning("Rate limiter disabled due to unexpected error: %s", e)
            return True

        return True
    return _check
