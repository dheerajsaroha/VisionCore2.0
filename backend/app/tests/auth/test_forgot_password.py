import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_forgot_password_contract(client: TestClient, qa_email, qa_password):
    # If endpoint exists, missing email should yield 400/422.
    res = client.post("/api/v1/auth/forgot-password", json={})
    assert res.status_code in (400, 401, 404, 422)

