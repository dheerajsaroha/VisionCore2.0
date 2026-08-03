"""
runtime_validation_leave.py
Sprint 3 — Module 1: Leave Management Validation Suite
"""
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from main import app
from app.db.database import SessionLocal
from app.db.models.all_models import User, Organization, Role, LeaveType, LeaveBalance, LeaveRequest
from app.core.security import create_access_token, get_password_hash

client = TestClient(app)

TOTAL_PASS = 0
TOTAL_FAIL = 0


def tc(name: str, passed: bool, detail: str = ""):
    global TOTAL_PASS, TOTAL_FAIL
    if passed:
        TOTAL_PASS += 1
        print(f"  ✅ PASS | {name} {f'({detail})' if detail else ''}")
    else:
        TOTAL_FAIL += 1
        print(f"  ❌ FAIL | {name} {f'({detail})' if detail else ''}")


def run_leave_validation():
    print("=" * 80)
    print(" SPRINT 3 — MODULE 1: LEAVE MANAGEMENT RUNTIME VALIDATION")
    print("=" * 80)

    db = SessionLocal()

    # 1. Setup Test Tenant & Users
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name=f"Leave Validation Org {org_id.hex[:6]}", legal_id=f"LVO_{org_id.hex[:6]}")
    db.add(org)

    role_admin = db.query(Role).filter(Role.name == "Admin").first()
    role_emp = db.query(Role).filter(Role.name == "Employee").first()

    ts = datetime.now(timezone.utc).strftime("%H%M%S%f")
    admin_user = User(
        full_name="Leave Admin",
        employee_id=f"EMP_A_{ts[:6]}",
        email=f"leave_admin_{ts}@test.com",
        username=f"leave_admin_{ts}",
        hashed_password=get_password_hash("admin123"),
        org_id=org_id,
        role_id=role_admin.id if role_admin else 1,
        is_active=True
    )
    emp_user = User(
        full_name="Leave Employee",
        employee_id=f"EMP_E_{ts[:6]}",
        email=f"leave_emp_{ts}@test.com",
        username=f"leave_emp_{ts}",
        hashed_password=get_password_hash("emp123"),
        org_id=org_id,
        role_id=role_emp.id if role_emp else 2,
        is_active=True
    )
    db.add_all([admin_user, emp_user])
    db.commit()
    db.refresh(admin_user)
    db.refresh(emp_user)

    admin_jti = str(uuid.uuid4())
    emp_jti = str(uuid.uuid4())

    from app.crud.crud_session import user_session
    user_session.create_for_user(db, user_id=admin_user.id, jti=admin_jti)
    user_session.create_for_user(db, user_id=emp_user.id, jti=emp_jti)

    admin_token = create_access_token(subject=str(admin_user.id), session_jti=admin_jti)
    emp_token = create_access_token(subject=str(emp_user.id), session_jti=emp_jti)

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # Test 1: Auto-seeding default leave types on GET /types
    r = client.get("/api/v1/leave/types", headers=emp_headers)
    tc("1. Auto-seeding default leave types", r.status_code == 200 and len(r.json()) >= 5, f"count={len(r.json()) if r.status_code == 200 else 0}")
    leave_types = r.json()
    annual_type = next((t for t in leave_types if t["code"] == "ANNUAL"), None)

    # Test 2: Admin creating a new custom leave type
    new_type_payload = {
        "name": "Sabbatical Leave",
        "code": f"SABBATICAL_{ts[:4]}",
        "description": "Long-term sabbatical leave",
        "max_days_per_year": 30,
        "max_days_per_request": 30,
        "is_paid": False
    }
    r = client.post("/api/v1/leave/types", json=new_type_payload, headers=admin_headers)
    tc("2. Admin creating custom leave type", r.status_code == 201, f"status={r.status_code}")

    # Test 3: Employee forbidden from creating leave types
    r = client.post("/api/v1/leave/types", json=new_type_payload, headers=emp_headers)
    tc("3. Employee forbidden from creating leave types (403)", r.status_code == 403, f"status={r.status_code}")

    # Test 4: Fetch user leave balances (initialization)
    r = client.get("/api/v1/leave/balance", headers=emp_headers)
    tc("4. Fetch user leave balances", r.status_code == 200 and len(r.json()) > 0, f"count={len(r.json()) if r.status_code == 200 else 0}")

    # Test 5: Employee submitting valid leave request
    today = datetime.now(timezone.utc)
    req_payload = {
        "leave_type_id": annual_type["id"] if annual_type else 1,
        "start_date": (today + timedelta(days=2)).isoformat(),
        "end_date": (today + timedelta(days=4)).isoformat(),
        "total_days": 2.0,
        "reason": "Family vacation"
    }
    r = client.post("/api/v1/leave/requests", json=req_payload, headers=emp_headers)
    tc("5. Employee submitting leave request", r.status_code == 201 and r.json()["status"] == "pending", f"status={r.status_code}")
    req_id = r.json()["id"] if r.status_code == 201 else None

    # Test 6: Verify pending_days increased in balance ledger
    r = client.get("/api/v1/leave/balance", headers=emp_headers)
    bals = r.json() if r.status_code == 200 else []
    ann_bal = next((b for b in bals if b["leave_type_id"] == (annual_type["id"] if annual_type else 1)), None)
    tc("6. Pending days ledger update", ann_bal is not None and ann_bal["pending_days"] == 2.0, f"pending={ann_bal['pending_days'] if ann_bal else None}")

    # Test 7: Admin approving leave request
    if req_id:
        r = client.post(f"/api/v1/leave/requests/{req_id}/approve", json={"status": "approved", "note": "Approved by HR"}, headers=admin_headers)
        tc("7. Admin approving leave request", r.status_code == 200 and r.json()["status"] == "approved", f"status={r.status_code}")

    # Test 8: Verify used_days increased and pending_days released
    r = client.get("/api/v1/leave/balance", headers=emp_headers)
    bals = r.json() if r.status_code == 200 else []
    ann_bal = next((b for b in bals if b["leave_type_id"] == (annual_type["id"] if annual_type else 1)), None)
    tc("8. Used days ledger update after approval", ann_bal is not None and ann_bal["used_days"] == 2.0 and ann_bal["pending_days"] == 0.0, f"used={ann_bal['used_days'] if ann_bal else None}")

    # Test 9: Submitting request exceeding max balance
    excess_req_payload = {
        "leave_type_id": annual_type["id"] if annual_type else 1,
        "start_date": (today + timedelta(days=10)).isoformat(),
        "end_date": (today + timedelta(days=40)).isoformat(),
        "total_days": 30.0,
        "reason": "Excessive leave"
    }
    r = client.post("/api/v1/leave/requests", json=excess_req_payload, headers=emp_headers)
    tc("9. Request exceeding balance rejected (400)", r.status_code == 400, f"status={r.status_code}")

    # Test 10: Listing leave requests with status filter
    r = client.get("/api/v1/leave/requests?status=approved", headers=admin_headers)
    tc("10. Filter leave requests by status", r.status_code == 200 and len(r.json()) >= 1, f"count={len(r.json()) if r.status_code == 200 else 0}")

    print("=" * 80)
    print(f" TOTAL: {TOTAL_PASS + TOTAL_FAIL} | PASSED: {TOTAL_PASS} | FAILED: {TOTAL_FAIL}")
    print("=" * 80)

    db.close()
    return TOTAL_FAIL == 0


if __name__ == "__main__":
    success = run_leave_validation()
    sys.exit(0 if success else 1)
