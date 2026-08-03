"""
runtime_validation_recruitment.py
Sprint 3 — Module 4: Recruitment & ATS Validation Suite
"""
import sys
import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from main import app
from app.db.database import SessionLocal
from app.db.models.all_models import User, Organization, Role, JobPosting, Candidate, JobApplication, InterviewSchedule
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


def run_recruitment_validation():
    print("=" * 80)
    print(" SPRINT 3 — MODULE 4: RECRUITMENT & ATS RUNTIME VALIDATION")
    print("=" * 80)

    db = SessionLocal()

    # Setup Org & Users
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name=f"Rec Org {org_id.hex[:6]}", legal_id=f"RO_{org_id.hex[:6]}")
    db.add(org)

    role_admin = db.query(Role).filter(Role.name == "Admin").first()
    role_emp = db.query(Role).filter(Role.name == "Employee").first()

    ts = datetime.now(timezone.utc).strftime("%H%M%S%f")
    admin_user = User(
        full_name="Rec Admin",
        employee_id=f"EMP_RA_{ts[:6]}",
        email=f"rec_admin_{ts}@test.com",
        username=f"rec_admin_{ts}",
        hashed_password=get_password_hash("admin123"),
        org_id=org_id,
        role_id=role_admin.id if role_admin else 1,
        is_active=True
    )
    emp_user = User(
        full_name="Rec Employee",
        employee_id=f"EMP_RE_{ts[:6]}",
        email=f"rec_emp_{ts}@test.com",
        username=f"rec_emp_{ts}",
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

    # Test 1: Admin Create Job Posting
    job_payload = {
        "title": "Senior AI Infrastructure Engineer",
        "description": "Lead the design and scaling of computer vision pipelines.",
        "location": "San Francisco / Hybrid",
        "employment_type": "Full-time"
    }
    r = client.post("/api/v1/recruitment/jobs", json=job_payload, headers=admin_headers)
    tc("1. Create Job Posting", r.status_code == 201 and r.json()["title"] == "Senior AI Infrastructure Engineer", f"status={r.status_code}")
    job_id = r.json()["id"] if r.status_code == 201 else None

    # Test 2: Register Candidate
    cand_payload = {
        "full_name": "Alice Smith",
        "email": f"alice_{ts}@example.com",
        "phone": "+1-555-0199"
    }
    r = client.post("/api/v1/recruitment/candidates", json=cand_payload, headers=admin_headers)
    tc("2. Register Candidate", r.status_code == 201 and r.json()["full_name"] == "Alice Smith", f"status={r.status_code}")
    cand_id = r.json()["id"] if r.status_code == 201 else None

    # Test 3: Submit Application
    if job_id and cand_id:
        app_payload = {"job_posting_id": job_id, "candidate_id": cand_id, "stage": "applied"}
        r = client.post("/api/v1/recruitment/applications", json=app_payload, headers=admin_headers)
        tc("3. Submit Application", r.status_code == 201 and r.json()["stage"] == "applied", f"status={r.status_code}")
        app_id = r.json()["id"] if r.status_code == 201 else None

    # Test 4: Schedule Interview
    if app_id:
        sched_payload = {
            "application_id": app_id,
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "meeting_link": "https://meet.google.com/abc-defg-hij"
        }
        r = client.post("/api/v1/recruitment/interviews", json=sched_payload, headers=admin_headers)
        tc("4. Schedule Interview & auto-advance stage", r.status_code == 201 and r.json()["status"] == "scheduled", f"status={r.status_code}")

    # Test 5: List Applications & Verify Stage Advanced to 'interview'
    r = client.get("/api/v1/recruitment/applications", headers=admin_headers)
    tc("5. Verify Application pipeline stage", r.status_code == 200 and r.json()[0]["stage"] == "interview", f"stage={r.json()[0]['stage'] if r.status_code == 200 else ''}")

    print("=" * 80)
    print(f" TOTAL: {TOTAL_PASS + TOTAL_FAIL} | PASSED: {TOTAL_PASS} | FAILED: {TOTAL_FAIL}")
    print("=" * 80)

    db.close()
    return TOTAL_FAIL == 0


if __name__ == "__main__":
    success = run_recruitment_validation()
    sys.exit(0 if success else 1)
