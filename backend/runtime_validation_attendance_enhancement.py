"""
runtime_validation_attendance_enhancement.py
Sprint 3 — Module 2: Attendance Enhancement Validation Suite
"""
import sys
import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from main import app
from app.db.database import SessionLocal
from app.db.models.all_models import User, Organization, Role, AttendanceLog, AttendanceCorrection
from app.core.security import create_access_token, get_password_hash
from app.crud.crud_session import user_session

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


def run_attendance_enhancement_validation():
    print("=" * 80)
    print(" SPRINT 3 — MODULE 2: ATTENDANCE ENHANCEMENT RUNTIME VALIDATION")
    print("=" * 80)

    db = SessionLocal()

    # 1. Setup Test Org & Users
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name=f"Att Org {org_id.hex[:6]}", legal_id=f"AO_{org_id.hex[:6]}")
    db.add(org)

    role_admin = db.query(Role).filter(Role.name == "Admin").first()
    role_emp = db.query(Role).filter(Role.name == "Employee").first()

    ts = datetime.now(timezone.utc).strftime("%H%M%S%f")
    admin_user = User(
        full_name="Att Admin",
        employee_id=f"EMP_AA_{ts[:6]}",
        email=f"att_admin_{ts}@test.com",
        username=f"att_admin_{ts}",
        hashed_password=get_password_hash("admin123"),
        org_id=org_id,
        role_id=role_admin.id if role_admin else 1,
        is_active=True
    )
    emp_user = User(
        full_name="Att Employee",
        employee_id=f"EMP_AE_{ts[:6]}",
        email=f"att_emp_{ts}@test.com",
        username=f"att_emp_{ts}",
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

    user_session.create_for_user(db, user_id=admin_user.id, jti=admin_jti)
    user_session.create_for_user(db, user_id=emp_user.id, jti=emp_jti)

    admin_token = create_access_token(subject=str(admin_user.id), session_jti=admin_jti)
    emp_token = create_access_token(subject=str(emp_user.id), session_jti=emp_jti)

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # Seed an AttendanceLog
    today = datetime.now(timezone.utc)
    log = AttendanceLog(
        user_id=emp_user.id,
        check_in=today - timedelta(hours=8),
        status="late",
        is_deleted=0
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    # Test 1: GET Attendance Summary
    r = client.get(f"/api/v1/attendance/summary?month={today.month}&year={today.year}", headers=emp_headers)
    tc("1. Fetch attendance summary", r.status_code == 200 and r.json()["total_days_logged"] >= 1, f"logged={r.json().get('total_days_logged') if r.status_code == 200 else 0}")

    # Test 2: Submit Correction Request
    corr_payload = {
        "attendance_log_id": log.id,
        "requested_clock_in": (today - timedelta(hours=9)).isoformat(),
        "requested_clock_out": (today - timedelta(hours=1)).isoformat(),
        "reason": "Punch-in system glitch recorded late"
    }
    r = client.post("/api/v1/attendance/corrections", json=corr_payload, headers=emp_headers)
    tc("2. Submit attendance correction request", r.status_code == 201 and r.json()["status"] == "pending", f"status={r.status_code}")
    corr_id = r.json()["id"] if r.status_code == 201 else None

    # Test 3: List Corrections
    r = client.get("/api/v1/attendance/corrections", headers=admin_headers)
    tc("3. Admin list correction requests", r.status_code == 200 and len(r.json()) >= 1, f"count={len(r.json()) if r.status_code == 200 else 0}")

    # Test 4: Admin Approve Correction Request
    if corr_id:
        r = client.post(f"/api/v1/attendance/corrections/{corr_id}/approve", json={"status": "approved", "note": "Verified by Manager"}, headers=admin_headers)
        tc("4. Admin approve correction request", r.status_code == 200 and r.json()["status"] == "approved", f"status={r.status_code}")

    # Test 5: Verify log status updated to on_time
    db.refresh(log)
    tc("5. AttendanceLog status updated after correction approval", log.status == "on_time", f"status={log.status}")

    print("=" * 80)
    print(f" TOTAL: {TOTAL_PASS + TOTAL_FAIL} | PASSED: {TOTAL_PASS} | FAILED: {TOTAL_FAIL}")
    print("=" * 80)

    db.close()
    return TOTAL_FAIL == 0


if __name__ == "__main__":
    success = run_attendance_enhancement_validation()
    sys.exit(0 if success else 1)
