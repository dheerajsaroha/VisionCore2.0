import os
import pytest
from typing import Generator
from fastapi.testclient import TestClient

# Signal to the rate-limit dependency that we are running under pytest so it
# can bypass per-IP throttling (tests make many requests from the same address).
os.environ.setdefault("TESTING", "true")

from main import app
from app.core import rate_limit
from app.db.database import SessionLocal


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Clear rate limiting state before each test.

    Both backends have to be reset. `rate_limit_dependency` prefers Redis and
    only degrades to the in-process `_fallback_windows` counter when the Redis
    pipeline raises, so clearing one but not the other leaves the other still
    counting. This fixture previously cleared only the local window, which was
    enough solely because the Redis path was always failing; once that path
    works, auth tests that issue several logins or reset attempts in a single
    test start legitimately hitting the real per-IP limits.
    """
    rate_limit._fallback_windows.clear()
    try:
        import redis as redis_sync

        from app.core.config import settings

        client = redis_sync.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        keys = list(client.scan_iter(match="rate_limit:*"))
        if keys:
            client.delete(*keys)
    except Exception:
        # Redis is optional for the suite; the local window reset above is
        # enough when it is unavailable.
        pass


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db() -> Generator:
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

