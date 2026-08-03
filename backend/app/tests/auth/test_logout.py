import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.skip(reason="QA credentials must be discovered and provided via env/fixtures")
def test_logout_invalid_token_blacklists(client: TestClient):
    # Placeholder
    res = client.post("/api/v1/auth/logout", headers={"Authorization": "Bearer invalid"})
    assert res.status_code in (400, 401)

