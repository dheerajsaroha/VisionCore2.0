import pytest
from typing import Generator
from fastapi.testclient import TestClient

from main import app
from app.core import rate_limit
from app.db.database import SessionLocal


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Clear rate limiting windows before each test to prevent inter-test rate limiting flakiness."""
    rate_limit._fallback_windows.clear()


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

