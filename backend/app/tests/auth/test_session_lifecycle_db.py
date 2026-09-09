import pytest
import concurrent.futures
from fastapi.testclient import TestClient
from main import app
from app.core.config import settings

@pytest.fixture
def client():
    return TestClient(app)

def test_full_db_backed_refresh_lifecycle(client: TestClient, qa_email, qa_password):
    if not qa_email:
        pytest.skip("QA identity missing")

    # 1. LOGIN
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": qa_email, "password": qa_password},
    )
    assert login_res.status_code == 200
    token1 = login_res.json()["access_token"]
    refresh1 = client.cookies.get(settings.REFRESH_COOKIE_NAME)
    assert refresh1

    # 2. PROTECTED REQUEST using access token
    me_res = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token1}"})
    assert me_res.status_code == 200

    # 3. REFRESH -> get new access token + rotated refresh cookie
    refresh_res = client.post("/api/v1/auth/refresh")
    assert refresh_res.status_code == 200
    token2 = refresh_res.json()["access_token"]
    refresh2 = client.cookies.get(settings.REFRESH_COOKIE_NAME)
    assert refresh2
    assert refresh2 != refresh1

    # 4. REPLAY OLD REFRESH -> must be rejected (401)
    client.cookies.delete(settings.REFRESH_COOKIE_NAME)
    replay_res = client.post(f"/api/v1/auth/refresh?refresh_token={refresh1}")
    assert replay_res.status_code == 401

    # 5. LOGOUT using token2
    client.cookies.set(settings.REFRESH_COOKIE_NAME, refresh2)
    logout_res = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token2}"})
    assert logout_res.status_code == 200

    # 6. REFRESH AFTER LOGOUT -> must be rejected (401)
    refresh_after_logout = client.post("/api/v1/auth/refresh")
    assert refresh_after_logout.status_code == 401


def test_concurrent_refresh_atomic_consumption(client: TestClient, qa_email, qa_password):
    if not qa_email:
        pytest.skip("QA identity missing")

    # Login to obtain fresh refresh cookie
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": qa_email, "password": qa_password},
    )
    assert login_res.status_code == 200
    refresh_cookie = login_res.cookies.get(settings.REFRESH_COOKIE_NAME)
    assert refresh_cookie

    # First refresh request using the cookie
    c1 = TestClient(app)
    c1.cookies.set(settings.REFRESH_COOKIE_NAME, refresh_cookie)
    r1 = c1.post("/api/v1/auth/refresh")
    assert r1.status_code == 200

    # Second refresh request with the EXACT SAME (now consumed) refresh cookie must fail (401)
    c2 = TestClient(app)
    c2.cookies.set(settings.REFRESH_COOKIE_NAME, refresh_cookie)
    r2 = c2.post("/api/v1/auth/refresh")
    assert r2.status_code == 401, f"Expected 401 on replay of consumed refresh token, got {r2.status_code}"



def test_password_change_invalidates_all_sessions(client: TestClient, qa_email, qa_password):
    if not qa_email:
        pytest.skip("QA identity missing")

    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": qa_email, "password": qa_password},
    )
    assert login_res.status_code == 200
    token1 = login_res.json()["access_token"]
    refresh1 = client.cookies.get(settings.REFRESH_COOKIE_NAME)

    new_pass = f"NewPass@{qa_password}"

    # Change password
    change_res = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token1}"},
        json={"current_password": qa_password, "new_password": new_pass},
    )
    assert change_res.status_code == 200

    # Old refresh attempt must be rejected
    client.cookies.set(settings.REFRESH_COOKIE_NAME, refresh1)
    ref_res = client.post("/api/v1/auth/refresh")
    assert ref_res.status_code == 401

    # Login with old password fails
    old_login = client.post(
        "/api/v1/auth/login",
        data={"username": qa_email, "password": qa_password},
    )
    assert old_login.status_code == 401

    # Login with new password succeeds
    new_login = client.post(
        "/api/v1/auth/login",
        data={"username": qa_email, "password": new_pass},
    )
    assert new_login.status_code == 200

    # Revert password back to original qa_password for test idempotency
    token_new = new_login.json()["access_token"]
    revert_res = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token_new}"},
        json={"current_password": new_pass, "new_password": qa_password},
    )
    assert revert_res.status_code == 200
