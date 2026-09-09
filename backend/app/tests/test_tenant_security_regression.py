import uuid
import pytest
from fastapi.testclient import TestClient

from main import app
from app.db.database import SessionLocal
from app.db.models.all_models import Organization, Role, User, Department
from app.core.security import get_password_hash

@pytest.fixture(scope="module")
def two_tenant_setup():
    """Setup two isolated tenants in the database with users and data."""
    db = SessionLocal()
    try:
        # Create Tenant A
        org_a = Organization(
            name=f"Tenant A Org {uuid.uuid4().hex[:6]}",
            legal_id=f"TA-{uuid.uuid4().hex[:6]}",
            zkp_threshold=0.95,
        )
        # Create Tenant B
        org_b = Organization(
            name=f"Tenant B Org {uuid.uuid4().hex[:6]}",
            legal_id=f"TB-{uuid.uuid4().hex[:6]}",
            zkp_threshold=0.95,
        )
        db.add_all([org_a, org_b])
        db.commit()
        db.refresh(org_a)
        db.refresh(org_b)

        role_admin = db.query(Role).filter(Role.name == "Admin").first()

        pass_hash = get_password_hash("TenantSecret@123")

        user_a = User(
            org_id=org_a.id,
            role_id=role_admin.id,
            full_name="Admin Tenant A",
            username=f"admin_a_{uuid.uuid4().hex[:6]}",
            email=f"admin_a_{uuid.uuid4().hex[:6]}@tenant-a.com",
            employee_id=f"EMP-A-{uuid.uuid4().hex[:6]}",
            hashed_password=pass_hash,
            is_active=1,
            is_deleted=0,
        )

        user_b = User(
            org_id=org_b.id,
            role_id=role_admin.id,
            full_name="Admin Tenant B",
            username=f"admin_b_{uuid.uuid4().hex[:6]}",
            email=f"admin_b_{uuid.uuid4().hex[:6]}@tenant-b.com",
            employee_id=f"EMP-B-{uuid.uuid4().hex[:6]}",
            hashed_password=pass_hash,
            is_active=1,
            is_deleted=0,
        )
        db.add_all([user_a, user_b])
        db.commit()
        db.refresh(user_a)
        db.refresh(user_b)

        # Department A
        dept_a = Department(
            org_id=org_a.id,
            name=f"Engineering A {uuid.uuid4().hex[:4]}",
        )
        # Department B
        dept_b = Department(
            org_id=org_b.id,
            name=f"Engineering B {uuid.uuid4().hex[:4]}",
        )
        db.add_all([dept_a, dept_b])
        db.commit()
        db.refresh(dept_a)
        db.refresh(dept_b)

        return {
            "org_a_id": org_a.id,
            "org_b_id": org_b.id,
            "user_a_email": user_a.email,
            "user_b_email": user_b.email,
            "password": "TenantSecret@123",
            "dept_a_id": dept_a.id,
            "dept_b_id": dept_b.id,
        }
    finally:
        db.close()


def test_two_tenant_isolation_and_parameter_tampering(two_tenant_setup):
    from app.core import rate_limit
    rate_limit._fallback_windows.clear()

    data = two_tenant_setup
    client_a = TestClient(app)
    client_b = TestClient(app)


    # Login User A
    res_a = client_a.post(
        "/api/v1/auth/login",
        data={"username": data["user_a_email"], "password": data["password"]},
    )
    assert res_a.status_code == 200
    token_a = res_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Login User B
    res_b = client_b.post(
        "/api/v1/auth/login",
        data={"username": data["user_b_email"], "password": data["password"]},
    )
    assert res_b.status_code == 200
    token_b = res_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. User A lists departments -> should see Dept A, NOT Dept B
    resp_depts_a = client_a.get("/api/v1/org/departments/", headers=headers_a)
    assert resp_depts_a.status_code == 200
    depts_a = resp_depts_a.json()
    dept_ids_a = [d.get("id") for d in depts_a if isinstance(d, dict)]
    assert data["dept_a_id"] in dept_ids_a
    assert data["dept_b_id"] not in dept_ids_a

    # 2. User B lists departments -> should see Dept B, NOT Dept A
    resp_depts_b = client_b.get("/api/v1/org/departments/", headers=headers_b)
    assert resp_depts_b.status_code == 200
    depts_b = resp_depts_b.json()
    dept_ids_b = [d.get("id") for d in depts_b if isinstance(d, dict)]
    assert data["dept_b_id"] in dept_ids_b
    assert data["dept_a_id"] not in dept_ids_b

    # 3. User A queries users with parameter tampering (org_id=org_b_id)
    tampered_query = client_a.get(f"/api/v1/users/?org_id={data['org_b_id']}", headers=headers_a)
    if tampered_query.status_code == 200:
        users_list = tampered_query.json()
        if isinstance(users_list, list):
            user_emails = [u.get("email") for u in users_list if isinstance(u, dict)]
            # User B must NOT be exposed to User A even with org_id query parameter tampering
            assert data["user_b_email"] not in user_emails
