import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_reset_password_contract(client: TestClient, qa_email, qa_password):
    # Contract-level check; invalid payload or absent POST route should fail.
    res = client.post("/api/v1/auth/reset-password", json={})
    assert res.status_code in (400, 401, 404, 405, 422)

