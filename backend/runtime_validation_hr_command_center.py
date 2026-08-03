"""
runtime_validation_hr_command_center.py
Sprint 3 — Module 5: HR Command Center Validation Suite
"""
import sys
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from main import app
from app.db.database import SessionLocal
from app.db.models.all_models import User, Organization, Role
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


def run_hr_command_center_validation():
    print("=" * 80)
    print(" SPRINT 3 — MODULE 5: HR COMMAND CENTER RUNTIME VALIDATION")
    print("=" * 80)

    db = SessionLocal()

    # Setup Org & Admin
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name=f"CC Org {org_id.hex[:6]}", legal_id=f"CCO_{org_id.hex[:6]}")
    db.add(org)

    role_admin = db.query(Role).filter(Role.name == "Admin").first()

    ts = datetime.now(timezone.utc).strftime("%H%M%S%f")
    admin_user = User(
        full_name="CC Admin",
        employee_id=f"EMP_CCA_{ts[:6]}",
        email=f"cc_admin_{ts}@test.com",
        username=f"cc_admin_{ts}",
        hashed_password=get_password_hash("admin123"),
        org_id=org_id,
        role_id=role_admin.id if role_admin else 1,
        is_active=1
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    admin_jti = str(uuid.uuid4())
    user_session.create_for_user(db, user_id=admin_user.id, jti=admin_jti)

    admin_token = create_access_token(subject=str(admin_user.id), session_jti=admin_jti)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Test 1: Fetch Command Center Metrics
    r = client.get("/api/v1/hr/command-center", headers=admin_headers)
    tc("1. Fetch HR Command Center aggregated metrics", r.status_code == 200 and "total_employees" in r.json(), f"total_employees={r.json().get('total_employees') if r.status_code == 200 else 0}")

    print("=" * 80)
    print(f" TOTAL: {TOTAL_PASS + TOTAL_FAIL} | PASSED: {TOTAL_PASS} | FAILED: {TOTAL_FAIL}")
    print("=" * 80)

    db.close()
    return TOTAL_FAIL == 0


if __name__ == "__main__":
    success = run_hr_command_center_validation()
    sys.exit(0 if success else 1)
