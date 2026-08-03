import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.skip(reason="QA credentials must be discovered and provided via env/fixtures")
def test_users_me_requires_auth(client: TestClient):
    res = client.get("/api/v1/users/me")
    assert res.status_code in (401, 403)

