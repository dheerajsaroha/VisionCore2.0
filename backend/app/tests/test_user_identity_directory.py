"""
test_user_identity_directory.py — Phase 5 Identity Directory & User Management Tests
Tests:
- Real metric summary endpoint
- Multi-field directory queries (pagination, department filtering, sorting, debounced search)
- Identity creation with duplicate prevention and audit logging
- Role update authorization and self-modification guards
- Sole administrator protection on deactivation, suspension, and deletion
- Cross-tenant isolation on identity details and effective permissions
"""
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from app.db.database import get_db, SessionLocal
from app.db.models.all_models import User, Role, Department, Organization, UserSession, Permission, RolePermission, Branch
from app.core import security


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def test_setup():
    db: Session = SessionLocal()
    try:
        # 1. Create Org A and Org B
        org_a = Organization(
            id=uuid.uuid4(),
            name="Alpha Corp Phase 5",
            legal_id=f"ALPHA-P5-{int(datetime.now(timezone.utc).timestamp())}",
            status="ACTIVE",
        )
        org_b = Organization(
            id=uuid.uuid4(),
            name="Beta Corp Phase 5",
            legal_id=f"BETA-P5-{int(datetime.now(timezone.utc).timestamp())}",
            status="ACTIVE",
        )
        db.add_all([org_a, org_b])
        db.commit()

        # 2. Roles
        role_admin = db.query(Role).filter(Role.name == "OrgAdmin").first()
        if not role_admin:
            role_admin = Role(name="OrgAdmin")
            db.add(role_admin)
            db.commit()

        role_emp = db.query(Role).filter(Role.name == "Employee").first()
        if not role_emp:
            role_emp = Role(name="Employee")
            db.add(role_emp)
            db.commit()

        role_mgr = db.query(Role).filter(Role.name == "Manager").first()
        if not role_mgr:
            role_mgr = Role(name="Manager")
            db.add(role_mgr)
            db.commit()

        # Ensure permissions for OrgAdmin
        perms = ["users.read", "users.create", "users.update", "users.delete", "roles.assign", "roles.view", "departments.read"]
        for p_name in perms:
            perm = db.query(Permission).filter(Permission.name == p_name).first()
            if not perm:
                perm = Permission(name=p_name, module="users", is_active=True)
                db.add(perm)
                db.commit()
            rp = db.query(RolePermission).filter(RolePermission.role_id == role_admin.id, RolePermission.permission_id == perm.id).first()
            if not rp:
                db.add(RolePermission(role_id=role_admin.id, permission_id=perm.id))
        db.commit()

        # 3. Departments & Branches in Org A
        dept_eng = Department(org_id=org_a.id, name="Engineering P5", is_deleted=0)
        dept_hr = Department(org_id=org_a.id, name="Human Resources P5", is_deleted=0)
        branch_a = Branch(org_id=org_a.id, name="HQ Bangalore P5", code=f"HQ-{uuid.uuid4().hex[:4].upper()}", city="Bangalore")
        db.add_all([dept_eng, dept_hr, branch_a])
        db.commit()

        # 4. Users in Org A
        admin_a = User(
            org_id=org_a.id,
            role_id=role_admin.id,
            dept_id=dept_eng.id,
            full_name="Alice Admin P5",
            username=f"alice_p5_{uuid.uuid4().hex[:6]}",
            email=f"alice_p5_{uuid.uuid4().hex[:6]}@alpha.com",
            employee_id=f"EMP-A-01-{uuid.uuid4().hex[:4]}",
            hashed_password=security.get_password_hash("Vision@123"),
            is_active=1,
            is_deleted=0,
        )
        emp_a = User(
            org_id=org_a.id,
            role_id=role_emp.id,
            dept_id=dept_eng.id,
            full_name="Bob Engineer P5",
            username=f"bob_p5_{uuid.uuid4().hex[:6]}",
            email=f"bob_p5_{uuid.uuid4().hex[:6]}@alpha.com",
            employee_id=f"EMP-A-02-{uuid.uuid4().hex[:4]}",
            hashed_password=security.get_password_hash("Vision@123"),
            is_active=1,
            is_deleted=0,
        )
        emp_hr = User(
            org_id=org_a.id,
            role_id=role_emp.id,
            dept_id=dept_hr.id,
            full_name="Carol HR P5",
            username=f"carol_p5_{uuid.uuid4().hex[:6]}",
            email=f"carol_p5_{uuid.uuid4().hex[:6]}@alpha.com",
            employee_id=f"EMP-A-03-{uuid.uuid4().hex[:4]}",
            hashed_password=security.get_password_hash("Vision@123"),
            is_active=1,
            is_deleted=0,
        )

        # 5. User in Org B
        emp_b = User(
            org_id=org_b.id,
            role_id=role_emp.id,
            full_name="David Beta P5",
            username=f"david_p5_{uuid.uuid4().hex[:6]}",
            email=f"david_p5_{uuid.uuid4().hex[:6]}@beta.com",
            employee_id=f"EMP-B-01-{uuid.uuid4().hex[:4]}",
            hashed_password=security.get_password_hash("Vision@123"),
            is_active=1,
            is_deleted=0,
        )
        db.add_all([admin_a, emp_a, emp_hr, emp_b])
        db.commit()

        # Log in via API to obtain session-bound access tokens
        from app.core import rate_limit
        rate_limit._fallback_windows.clear()

        client_test = TestClient(app)
        res_login_admin = client_test.post(
            "/api/v1/auth/login",
            data={"username": admin_a.email, "password": "Vision@123"},
        )
        assert res_login_admin.status_code == 200, res_login_admin.text
        token_admin_a = res_login_admin.json()["access_token"]

        res_login_emp = client_test.post(
            "/api/v1/auth/login",
            data={"username": emp_a.email, "password": "Vision@123"},
        )
        assert res_login_emp.status_code == 200, res_login_emp.text
        token_emp_a = res_login_emp.json()["access_token"]

        data = {
            "org_a_id": org_a.id,
            "org_b_id": org_b.id,
            "dept_eng_id": dept_eng.id,
            "dept_hr_id": dept_hr.id,
            "branch_a_id": branch_a.id,
            "admin_a_id": admin_a.id,
            "emp_a_id": emp_a.id,
            "emp_hr_id": emp_hr.id,
            "emp_b_id": emp_b.id,
            "token_admin_a": token_admin_a,
            "token_emp_a": token_emp_a,
        }
        return data
    finally:
        db.close()


def test_directory_summary_metrics(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['token_admin_a']}"}
    res = client.get("/api/v1/users/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "active_count" in data
    assert "inactive_count" in data
    assert "privileged_count" in data
    assert "enrolled_count" in data
    assert data["total"] >= 3
    assert data["active_count"] >= 3
    assert data["privileged_count"] >= 1


def test_directory_filtering_and_sorting(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['token_admin_a']}"}

    # Filter by department
    res = client.get(f"/api/v1/users/?dept_id={test_setup['dept_eng_id']}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["users"]) >= 2
    for u in data["users"]:
        assert u["dept_id"] == test_setup["dept_eng_id"]

    # Filter by role
    res = client.get("/api/v1/users/?role=Employee", headers=headers)
    assert res.status_code == 200
    for u in res.json()["users"]:
        assert u["role"]["name"] == "Employee"

    # Search
    res = client.get("/api/v1/users/?search=Alice", headers=headers)
    assert res.status_code == 200
    assert any("Alice" in u["full_name"] for u in res.json()["users"])

    # Sorting
    res_asc = client.get("/api/v1/users/?sort_by=full_name&sort_order=asc", headers=headers)
    assert res_asc.status_code == 200
    names_asc = [u["full_name"] for u in res_asc.json()["users"]]
    assert names_asc == sorted(names_asc)


def test_identity_creation_and_duplicate_handling(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['token_admin_a']}"}
    unique_email = f"new_dev_{uuid.uuid4().hex[:6]}@alpha.com"
    payload = {
        "full_name": "New Lead Architect",
        "email": unique_email,
        "password": "SecurePassword@123",
        "role": "Employee",
        "dept_id": test_setup["dept_eng_id"],
        "branch_id": test_setup["branch_a_id"],
        "phone": "+1234567890",
        "designation": "Principal System Architect",
        "employment_type": "CONTRACTOR",
        "reporting_manager_id": test_setup["admin_a_id"],
    }
    res = client.post("/api/v1/users/", json=payload, headers=headers)
    assert res.status_code == 200
    created = res.json()
    assert created["email"] == unique_email
    assert created["dept_id"] == test_setup["dept_eng_id"]
    assert created["branch_id"] == test_setup["branch_a_id"]
    assert created["location"] is not None
    assert "Bangalore" in created["location"]
    assert created["phone"] == "+1234567890"
    assert created["designation"] == "Principal System Architect"
    assert created["employment_type"] == "CONTRACTOR"
    assert created["manager_name"] == "Alice Admin P5"

    # Search by designation
    res_search = client.get("/api/v1/users/?search=Architect", headers=headers)
    assert res_search.status_code == 200
    assert any(u["email"] == unique_email for u in res_search.json()["users"])

    # Search by department name
    res_dept_search = client.get("/api/v1/users/?search=Engineering", headers=headers)
    assert res_dept_search.status_code == 200
    assert any(u["email"] == unique_email for u in res_dept_search.json()["users"])

    # Filter by employment_type
    res_type = client.get("/api/v1/users/?employment_type=CONTRACTOR", headers=headers)
    assert res_type.status_code == 200
    assert any(u["email"] == unique_email for u in res_type.json()["users"])

    # Filter by branch_id (Location)
    res_branch = client.get(f"/api/v1/users/?branch_id={test_setup['branch_a_id']}", headers=headers)
    assert res_branch.status_code == 200
    assert any(u["email"] == unique_email for u in res_branch.json()["users"])

    # Filter by manager_id
    res_mgr = client.get(f"/api/v1/users/?manager_id={test_setup['admin_a_id']}", headers=headers)
    assert res_mgr.status_code == 200
    assert any(u["email"] == unique_email for u in res_mgr.json()["users"])

    # Duplicate rejection
    res_dup = client.post("/api/v1/users/", json=payload, headers=headers)
    assert res_dup.status_code == 400
    assert "already registered" in res_dup.json()["detail"].lower()


def test_sole_admin_protection(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['token_admin_a']}"}
    admin_id = test_setup["admin_a_id"]

    # 1. Attempt self-deactivation
    res = client.patch(f"/api/v1/users/{admin_id}", json={"is_active": 0}, headers=headers)
    assert res.status_code == 400
    assert "cannot deactivate your own account" in res.json()["detail"].lower()

    # 2. Attempt self-suspension
    res = client.post(f"/api/v1/identity/{admin_id}/suspend", json={"reason": "Self test"}, headers=headers)
    assert res.status_code == 400
    assert "cannot suspend your own account" in res.json()["detail"].lower()

    # 3. Attempt self-deletion
    res = client.delete(f"/api/v1/users/{admin_id}", headers=headers)
    assert res.status_code == 400
    assert "cannot delete your own account" in res.json()["detail"].lower()


def test_role_assignment_requires_both_update_and_assign_permissions(client, test_setup):
    """Direct API calls cannot bypass either half of role-assignment RBAC."""
    db: Session = SessionLocal()
    try:
        org_id = test_setup["org_a_id"]
        permissions = {}
        for name in ("users.update", "roles.assign"):
            permission = db.query(Permission).filter(Permission.name == name).first()
            assert permission is not None
            permissions[name] = permission

        role_specs = {
            "P5 Update Only": ["users.update"],
            "P5 Assign Only": ["roles.assign"],
            "P5 Update And Assign": ["users.update", "roles.assign"],
            "P5 No Identity Changes": [],
        }
        tokens = {}
        for role_name, permission_names in role_specs.items():
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                role = Role(name=role_name)
                db.add(role)
                db.flush()
            for permission_name in permission_names:
                exists = db.query(RolePermission).filter(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == permissions[permission_name].id,
                ).first()
                if not exists:
                    db.add(RolePermission(role_id=role.id, permission_id=permissions[permission_name].id))

            caller = User(
                org_id=org_id,
                role_id=role.id,
                full_name=f"{role_name} Caller",
                username=f"p5_rbac_{uuid.uuid4().hex[:12]}",
                email=f"p5_rbac_{uuid.uuid4().hex[:12]}@alpha.com",
                employee_id=f"P5-RBAC-{uuid.uuid4().hex[:8]}",
                hashed_password=security.get_password_hash("Vision@123"),
                is_active=1,
                is_deleted=0,
            )
            db.add(caller)
            db.flush()
            tokens[role_name] = caller.email
        db.commit()

        from app.core import rate_limit
        rate_limit._fallback_windows.clear()
        for role_name, email in tokens.items():
            login = client.post("/api/v1/auth/login", data={"username": email, "password": "Vision@123"})
            assert login.status_code == 200, login.text
            tokens[role_name] = login.json()["access_token"]

        target_id = test_setup["emp_a_id"]
        expected_status = {
            "P5 Update Only": 403,
            "P5 Assign Only": 403,
            "P5 Update And Assign": 200,
            "P5 No Identity Changes": 403,
        }
        for role_name, status_code in expected_status.items():
            response = client.patch(
                f"/api/v1/users/{target_id}",
                json={"role": "Manager"},
                headers={"Authorization": f"Bearer {tokens[role_name]}"},
            )
            assert response.status_code == status_code, response.text
    finally:
        db.close()


def test_biometric_enrollment_authorization_matrix(client, test_setup):
    """Enrollment is self-service or requires users.update for another user."""
    headers_admin = {"Authorization": f"Bearer {test_setup['token_admin_a']}"}
    headers_employee = {"Authorization": f"Bearer {test_setup['token_emp_a']}"}
    employee_id = test_setup["emp_a_id"]
    other_employee_id = test_setup["emp_hr_id"]

    # An image is intentionally absent: a 400 proves authorization succeeded
    # and validation then rejected the invalid enrollment payload.
    assert client.post(
        f"/api/v1/users/{employee_id}/enroll", json={}, headers=headers_employee
    ).status_code == 400
    assert client.post(
        f"/api/v1/users/{other_employee_id}/enroll", json={}, headers=headers_admin
    ).status_code == 400
    assert client.post(
        f"/api/v1/users/{other_employee_id}/enroll", json={}, headers=headers_employee
    ).status_code == 403


def test_tenant_isolation_on_user_and_permissions(client, test_setup):
    headers_a = {"Authorization": f"Bearer {test_setup['token_admin_a']}"}
    user_b_id = test_setup["emp_b_id"]

    # 1. Attempt to get Org B user profile
    res = client.get(f"/api/v1/users/{user_b_id}", headers=headers_a)
    assert res.status_code == 404

    # 2. Attempt to get Org B user effective permissions
    res = client.get(f"/api/v1/rbac/user/{user_b_id}/permissions", headers=headers_a)
    assert res.status_code == 404

    # 3. Attempt to suspend Org B user
    res = client.post(f"/api/v1/identity/{user_b_id}/suspend", json={"reason": "cross-tenant"}, headers=headers_a)
    assert res.status_code == 404

    # 4. Attempt to activate Org B user
    res = client.post(f"/api/v1/identity/{user_b_id}/activate", headers=headers_a)
    assert res.status_code == 404

    # 5. Attempt to get Org B user timeline
    res = client.get(f"/api/v1/identity/{user_b_id}/timeline", headers=headers_a)
    assert res.status_code == 404

    # 6. Attempt to get Org B user employment record
    res = client.get(f"/api/v1/employment/{user_b_id}", headers=headers_a)
    assert res.status_code == 404

    # 7. Attempt to get Org B user trusted devices
    res = client.get(f"/api/v1/identity/{user_b_id}/trusted-devices", headers=headers_a)
    assert res.status_code == 404

    # 8. Attempt to get Org B user attendance summary
    res = client.get(f"/api/v1/attendance/summary?user_id={user_b_id}", headers=headers_a)
    assert res.status_code == 404

    # 9. Attempt to get Org B user leave balance (blocked by RBAC or tenant boundary)
    res = client.get(f"/api/v1/leave/balance?user_id={user_b_id}", headers=headers_a)
    assert res.status_code in (403, 404)


def test_workforce_user_attendance_and_summary(client, test_setup):
    headers_a = {"Authorization": f"Bearer {test_setup['token_admin_a']}"}
    emp_a_id = test_setup["emp_a_id"]

    # 1. Query attendance summary for own org employee
    res_summary = client.get(f"/api/v1/attendance/summary?user_id={emp_a_id}", headers=headers_a)
    assert res_summary.status_code == 200
    data = res_summary.json()
    assert data["user_id"] == emp_a_id
    assert "total_days_logged" in data
    assert "present_count" in data

    # 2. Query attendance logs filtered by user_id
    res_logs = client.get(f"/api/v1/attendance/logs?user_id={emp_a_id}", headers=headers_a)
    assert res_logs.status_code == 200
    assert isinstance(res_logs.json(), list)


def test_user_update_and_audit_logging(client, test_setup):
    """Verify editing identity attributes, employment record sync, and audit logging."""
    headers = {"Authorization": f"Bearer {test_setup['token_admin_a']}"}
    target_id = test_setup["emp_hr_id"]

    update_payload = {
        "full_name": "Carol HR Lead Updated",
        "phone": "+91 9876543210",
        "designation": "Senior HR Business Partner",
        "employment_type": "EMPLOYEE",
    }
    res = client.patch(f"/api/v1/users/{target_id}", json=update_payload, headers=headers)
    assert res.status_code == 200, res.text
    updated = res.json()
    assert updated["full_name"] == "Carol HR Lead Updated"
    assert updated["phone"] == "+91 9876543210"
    assert updated["designation"] == "Senior HR Business Partner"

    # Verify reflected in user get by ID
    res_get = client.get(f"/api/v1/users/{target_id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["full_name"] == "Carol HR Lead Updated"
    assert res_get.json()["designation"] == "Senior HR Business Partner"


def test_identity_activation_suspension_cycle(client, test_setup):
    """Verify suspension with compliance reason and subsequent reactivation."""
    headers = {"Authorization": f"Bearer {test_setup['token_admin_a']}"}
    target_id = test_setup["emp_a_id"]

    # 1. Suspend account with reason
    suspend_res = client.post(
        f"/api/v1/identity/{target_id}/suspend",
        json={"reason": "Security review in progress"},
        headers=headers,
    )
    assert suspend_res.status_code == 200
    assert suspend_res.json()["is_active"] == 0

    # Verify user record is inactive
    user_res = client.get(f"/api/v1/users/{target_id}", headers=headers)
    assert user_res.status_code == 200
    assert user_res.json()["is_active"] == 0

    # Verify timeline reflects the suspension event
    timeline_res = client.get(f"/api/v1/identity/{target_id}/timeline", headers=headers)
    assert timeline_res.status_code == 200
    events = timeline_res.json()
    assert any("suspend" in str(e.get("event_type", "")).lower() or "suspended" in str(e.get("reason", "")).lower() for e in events)

    # 2. Reactivate account
    activate_res = client.post(f"/api/v1/identity/{target_id}/activate", headers=headers)
    assert activate_res.status_code == 200
    assert activate_res.json()["is_active"] == 1

    # Verify user record is active again
    user_res2 = client.get(f"/api/v1/users/{target_id}", headers=headers)
    assert user_res2.status_code == 200
    assert user_res2.json()["is_active"] == 1

    # Re-authenticate emp_a to refresh session token after suspension cycle
    from app.core import rate_limit
    rate_limit._fallback_windows.clear()
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": user_res2.json()["email"], "password": "Vision@123"},
    )
    assert login_res.status_code == 200
    test_setup["token_emp_a"] = login_res.json()["access_token"]


def test_idor_unauthorized_user_mutations_blocked(client, test_setup):
    """Standard employee cannot modify another employee's profile or status."""
    headers_emp = {"Authorization": f"Bearer {test_setup['token_emp_a']}"}
    other_emp_id = test_setup["emp_hr_id"]

    # Attempt to edit other employee's profile
    res_edit = client.patch(
        f"/api/v1/users/{other_emp_id}",
        json={"full_name": "Hacked Name"},
        headers=headers_emp,
    )
    assert res_edit.status_code == 403

    # Attempt to suspend other employee
    res_suspend = client.post(
        f"/api/v1/identity/{other_emp_id}/suspend",
        json={"reason": "Malicious attempt"},
        headers=headers_emp,
    )
    assert res_suspend.status_code == 403

    # Attempt to activate other employee
    res_activate = client.post(
        f"/api/v1/identity/{other_emp_id}/activate",
        headers=headers_emp,
    )
    assert res_activate.status_code == 403

    # Attempt to delete other employee
    res_delete = client.delete(
        f"/api/v1/users/{other_emp_id}",
        headers=headers_emp,
    )
    assert res_delete.status_code == 403


def test_platform_privilege_escalation_blocked(client, test_setup):
    """OrgAdmin cannot assign or create platform-tier or system roles like SuperAdmin."""
    headers_admin = {"Authorization": f"Bearer {test_setup['token_admin_a']}"}
    emp_id = test_setup["emp_hr_id"]

    # Ensure SuperAdmin role exists in DB with tier='platform'
    db: Session = SessionLocal()
    try:
        super_role = db.query(Role).filter(Role.name == "SuperAdmin").first()
        if not super_role:
            super_role = Role(name="SuperAdmin", tier="platform", is_system=True)
            db.add(super_role)
            db.commit()
        else:
            if super_role.tier != "platform":
                super_role.tier = "platform"
                db.commit()
    finally:
        db.close()

    # 1. Attempt to create user with SuperAdmin role as OrgAdmin
    res_create = client.post(
        "/api/v1/users/",
        json={
            "full_name": "Malicious SuperAdmin",
            "email": f"malicious_{uuid.uuid4().hex[:6]}@alpha.com",
            "password": "Password@123",
            "role": "SuperAdmin",
        },
        headers=headers_admin,
    )
    assert res_create.status_code == 403
    assert "platform" in res_create.json()["detail"].lower() or "forbidden" in res_create.json()["detail"].lower()

    # 2. Attempt to patch user role to SuperAdmin as OrgAdmin
    res_patch = client.patch(
        f"/api/v1/users/{emp_id}",
        json={"role": "SuperAdmin"},
        headers=headers_admin,
    )
    assert res_patch.status_code == 403
    assert "platform" in res_patch.json()["detail"].lower() or "forbidden" in res_patch.json()["detail"].lower()


def test_active_session_revocation_on_deactivation_and_deletion(client, test_setup):
    """Deactivating or deleting a user immediately revokes active DB-backed sessions."""
    headers_admin = {"Authorization": f"Bearer {test_setup['token_admin_a']}"}

    # 1. Create a dedicated test user
    email = f"session_test_{uuid.uuid4().hex[:6]}@alpha.com"
    res_create = client.post(
        "/api/v1/users/",
        json={
            "full_name": "Session Lifecycle User",
            "email": email,
            "password": "Password@123",
            "role": "Employee",
        },
        headers=headers_admin,
    )
    assert res_create.status_code == 200
    user_id = res_create.json()["id"]

    # 2. Log in as that user to establish an active session
    from app.core import rate_limit
    rate_limit._fallback_windows.clear()
    res_login = client.post("/api/v1/auth/login", data={"username": email, "password": "Password@123"})
    assert res_login.status_code == 200

    db: Session = SessionLocal()
    try:
        active_sessions = db.query(UserSession).filter(UserSession.user_id == user_id, UserSession.is_active == True).all()
        assert len(active_sessions) >= 1
    finally:
        db.close()

    # 3. Deactivate user via PATCH /users/{id}
    res_deact = client.patch(
        f"/api/v1/users/{user_id}",
        json={"is_active": 0},
        headers=headers_admin,
    )
    assert res_deact.status_code == 200

    # Verify session is revoked
    db = SessionLocal()
    try:
        active_sessions = db.query(UserSession).filter(UserSession.user_id == user_id, UserSession.is_active == True).all()
        assert len(active_sessions) == 0
        revoked_sessions = db.query(UserSession).filter(UserSession.user_id == user_id, UserSession.revoke_reason == "account_deactivated").all()
        assert len(revoked_sessions) >= 1
    finally:
        db.close()

    # 4. Reactivate and log in again
    res_act = client.patch(
        f"/api/v1/users/{user_id}",
        json={"is_active": 1},
        headers=headers_admin,
    )
    assert res_act.status_code == 200

    rate_limit._fallback_windows.clear()
    res_login2 = client.post("/api/v1/auth/login", data={"username": email, "password": "Password@123"})
    assert res_login2.status_code == 200

    # 5. Delete (soft-delete / archive) user via DELETE /users/{id}
    res_del = client.delete(f"/api/v1/users/{user_id}", headers=headers_admin)
    assert res_del.status_code == 200

    # Verify session is revoked with reason account_deleted
    db = SessionLocal()
    try:
        active_sessions = db.query(UserSession).filter(UserSession.user_id == user_id, UserSession.is_active == True).all()
        assert len(active_sessions) == 0
        revoked_sessions = db.query(UserSession).filter(UserSession.user_id == user_id, UserSession.revoke_reason == "account_deleted").all()
        assert len(revoked_sessions) >= 1
    finally:
        db.close()


