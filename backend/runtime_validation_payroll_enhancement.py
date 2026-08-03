"""
runtime_validation_payroll_enhancement.py
Sprint 3 — Module 3: Payroll Enhancement Validation Suite
"""
import sys
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from main import app
from app.db.database import SessionLocal
from app.db.models.all_models import User, Organization, Role, PayGrade, SalaryStructure, PayrollAdvance
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


def run_payroll_enhancement_validation():
    print("=" * 80)
    print(" SPRINT 3 — MODULE 3: PAYROLL ENHANCEMENT RUNTIME VALIDATION")
    print("=" * 80)

    db = SessionLocal()

    # Setup Org & Users
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name=f"Pay Org {org_id.hex[:6]}", legal_id=f"PO_{org_id.hex[:6]}")
    db.add(org)

    role_admin = db.query(Role).filter(Role.name == "Admin").first()
    role_emp = db.query(Role).filter(Role.name == "Employee").first()

    ts = datetime.now(timezone.utc).strftime("%H%M%S%f")
    admin_user = User(
        full_name="Pay Admin",
        employee_id=f"EMP_PA_{ts[:6]}",
        email=f"pay_admin_{ts}@test.com",
        username=f"pay_admin_{ts}",
        hashed_password=get_password_hash("admin123"),
        org_id=org_id,
        role_id=role_admin.id if role_admin else 1,
        is_active=True
    )
    emp_user = User(
        full_name="Pay Employee",
        employee_id=f"EMP_PE_{ts[:6]}",
        email=f"pay_emp_{ts}@test.com",
        username=f"pay_emp_{ts}",
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

    # Test 1: Admin Create Pay Grade
    grade_payload = {"grade_name": "Grade-E3 Senior Engineer", "min_salary": 80000.0, "max_salary": 150000.0}
    r = client.post("/api/v1/payroll/grades", json=grade_payload, headers=admin_headers)
    tc("1. Create Pay Grade", r.status_code == 200 and r.json()["grade_name"] == "Grade-E3 Senior Engineer", f"status={r.status_code}")
    grade_id = r.json()["id"] if r.status_code == 200 else None

    # Test 2: Admin Assign Salary Structure
    struct_payload = {"user_id": emp_user.id, "pay_grade_id": grade_id, "base_pay": 100000.0, "special_allowance": 15000.0}
    r = client.post("/api/v1/payroll/structure", json=struct_payload, headers=admin_headers)
    tc("2. Assign Salary Structure", r.status_code == 200 and r.json()["net_salary"] > 0, f"net={r.json().get('net_salary') if r.status_code == 200 else 0}")

    # Test 3: Employee Request Salary Advance
    adv_payload = {"amount": 25000.0, "reason": "Medical emergency advance"}
    r = client.post("/api/v1/payroll/advances", json=adv_payload, headers=emp_headers)
    tc("3. Employee Request Salary Advance", r.status_code == 201 and r.json()["status"] == "pending", f"status={r.status_code}")
    adv_id = r.json()["id"] if r.status_code == 201 else None

    # Test 4: List Salary Advances
    r = client.get("/api/v1/payroll/advances", headers=admin_headers)
    tc("4. List Salary Advances", r.status_code == 200 and len(r.json()) >= 1, f"count={len(r.json()) if r.status_code == 200 else 0}")

    # Test 5: Admin Approve Advance Request
    if adv_id:
        r = client.post(f"/api/v1/payroll/advances/{adv_id}/approve", json={"status": "approved"}, headers=admin_headers)
        tc("5. Admin Approve Salary Advance", r.status_code == 200 and r.json()["status"] == "approved", f"status={r.status_code}")

    print("=" * 80)
    print(f" TOTAL: {TOTAL_PASS + TOTAL_FAIL} | PASSED: {TOTAL_PASS} | FAILED: {TOTAL_FAIL}")
    print("=" * 80)

    db.close()
    return TOTAL_FAIL == 0


if __name__ == "__main__":
    success = run_payroll_enhancement_validation()
    sys.exit(0 if success else 1)
