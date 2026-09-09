"""
test_profile_update.py — Unit tests for profile self-update (PATCH /users/me).
Verifies profile update success, name validation, and parameter tampering prevention.
"""
from fastapi.testclient import TestClient
import pytest


@pytest.fixture
def auth_headers(client: TestClient, qa_email: str, qa_password: str) -> dict:
    from app.core import rate_limit
    rate_limit._fallback_windows.clear()
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": qa_email, "password": qa_password},
    )
    if login_res.status_code != 200:
        print("LOGIN FAILED:", login_res.status_code, login_res.text)
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}





def test_profile_update_success(client: TestClient, auth_headers: dict):
    res = client.get("/api/v1/users/me", headers=auth_headers)
    assert res.status_code == 200
    original_name = res.json()["full_name"]

    new_name = "Updated QA Name"
    res_update = client.patch(
        "/api/v1/users/me",
        json={"full_name": new_name},
        headers=auth_headers,
    )
    assert res_update.status_code == 200
    assert res_update.json()["full_name"] == new_name

    res_me = client.get("/api/v1/users/me", headers=auth_headers)
    assert res_me.status_code == 200
    assert res_me.json()["full_name"] == new_name

    # Restore original name
    client.patch(
        "/api/v1/users/me",
        json={"full_name": original_name},
        headers=auth_headers,
    )


def test_profile_update_empty_name_rejected(client: TestClient, auth_headers: dict):
    res = client.patch(
        "/api/v1/users/me",
        json={"full_name": "   "},
        headers=auth_headers,
    )
    assert res.status_code == 400


def test_profile_update_tampering_ignored(client: TestClient, auth_headers: dict):
    res_me_before = client.get("/api/v1/users/me", headers=auth_headers).json()
    original_role = res_me_before["role"]["name"]
    original_org = res_me_before["org_id"]

    res = client.patch(
        "/api/v1/users/me",
        json={
            "full_name": "Tamper Test User",
            "role": "SuperAdmin",
            "org_id": "00000000-0000-0000-0000-000000000000",
            "is_active": 0,
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["full_name"] == "Tamper Test User"
    assert res_data["role"]["name"] == original_role
    assert res_data["org_id"] == original_org
