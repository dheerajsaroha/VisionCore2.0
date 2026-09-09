import pytest
from fastapi.testclient import TestClient

from main import app
from app.core.config import settings


@pytest.fixture
def client():
    return TestClient(app)


def test_refresh_rotation_flow(client: TestClient, qa_email, qa_password):
    if not qa_email:
        pytest.skip("QA_EMAIL not available (env/DB discovery)")

    # Login to obtain fresh + refresh tokens
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": qa_email, "password": qa_password},
    )
    assert login_res.status_code == 200

    payload = login_res.json()
    access_1 = payload["access_token"]
    assert access_1
    assert payload.get("refresh_token") is None
    refresh_1 = client.cookies.get(settings.REFRESH_COOKIE_NAME)
    assert refresh_1

    # Refresh should rotate refresh token
    refresh_res = client.post("/api/v1/auth/refresh")



    if refresh_res.status_code != 200:

        # Contract expects a 200. If 422, surface payload for debugging.
        pytest.fail(f"/api/v1/auth/refresh expected 200, got {refresh_res.status_code}: {refresh_res.text}")


    payload2 = refresh_res.json()
    access_2 = payload2["access_token"]
    refresh_2 = client.cookies.get(settings.REFRESH_COOKIE_NAME)

    assert access_2
    assert refresh_2
    assert payload2.get("refresh_token") is None
    assert refresh_2 != refresh_1



    # Replay old refresh token should now be rejected.
    # If refresh-token rotation is not implemented/disabled, this may still succeed.
    # We treat non-200 as the desired behavior.
    # Explicitly supplying the stolen, pre-rotation credential must fail even
    # though the client's cookie already contains the rotated credential.
    client.cookies.delete(settings.REFRESH_COOKIE_NAME)
    replay_res = client.post(f"/api/v1/auth/refresh?refresh_token={refresh_1}")
    assert replay_res.status_code == 401



