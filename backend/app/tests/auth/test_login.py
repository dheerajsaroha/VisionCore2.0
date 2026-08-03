import pytest

from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_login_needs_credentials(client: TestClient):
    # Basic negative check: missing username/password should fail.
    res = client.post("/api/v1/auth/login", data={})
    assert res.status_code in (400, 401, 422)


@pytest.mark.skip(reason="QA credentials must be discovered and provided via env/fixtures")
def test_login_with_qa_account(client: TestClient):
    # Placeholder: actual QA creds must be wired via test fixtures.
    pass

