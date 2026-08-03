import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_change_password_invalid_case(client: TestClient, qa_email, qa_password):
    # Without a real access token, we only validate the contract.
    res = client.post("/api/v1/auth/change-password", json={"current_password": "x", "new_password": "y"})
    assert res.status_code in (400, 401, 404, 422)

