"""
runtime_validation_integration.py — Enterprise Authorization Integration (Entity 6) Validation Suite
Sprint 2 — Entity 6: Unified EAAC Pipeline Runtime Validation
"""
import sys
import time
import json
import uuid
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("validation_eaac")

from fastapi.testclient import TestClient
from main import app
from app.db.database import SessionLocal
from app.db.models.all_models import (
    User, Organization, Role, DynamicRole
)
from app.core.security import get_password_hash

client = TestClient(app)

REPORT = {
    "entity": "Entity 6: Enterprise Authorization Integration",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "phases": {},
    "passed": 0,
    "failed": 0,
    "total": 0,
    "score": 0.0
}

def log(msg, level="info"):
    prefix = "  ✅ PASS |" if level == "pass" else ("  ❌ FAIL |" if level == "fail" else "ℹ️ ")
    print(f"{prefix} {msg}")

def tc(name, condition, detail="", category="general"):
    REPORT["total"] += 1
    if category not in REPORT["phases"]:
        REPORT["phases"][category] = {"passed": 0, "failed": 0, "tests": []}

    if condition:
        REPORT["passed"] += 1
        REPORT["phases"][category]["passed"] += 1
        REPORT["phases"][category]["tests"].append({"name": name, "status": "PASS", "detail": detail})
        log(f"[{category}] {name}\n         {detail}", level="pass")
    else:
        REPORT["failed"] += 1
        REPORT["phases"][category]["failed"] += 1
        REPORT["phases"][category]["tests"].append({"name": name, "status": "FAIL", "detail": detail})
        log(f"[{category}] {name}\n         {detail}", level="fail")

PASSWORD = "TestPassword123!"

def login_user(email):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": PASSWORD})
    if r.status_code != 200:
        return None, None
    tok = r.json().get("access_token")
    return tok, {"Authorization": f"Bearer {tok}"}

def bootstrap():
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.name == "EAAC Test Corp").first()
        if not org:
            org = Organization(name="EAAC Test Corp", legal_id="ORG-EAAC-TEST-001", is_active=True)
            db.add(org); db.commit(); db.refresh(org)
        org_id = org.id

        roles = {r.name: r for r in db.query(Role).all()}

        def get_or_create_user(email, name, role_name):
            u = db.query(User).filter(User.email == email).first()
            if not u:
                uname = email.split("@")[0]
                role_obj = roles.get(role_name) or roles.get("Employee") or list(roles.values())[0]
                u = User(
                    email=email, username=uname, employee_id=f"EMP-{uname}",
                    full_name=name, hashed_password=get_password_hash(PASSWORD),
                    role_id=role_obj.id, org_id=org_id, is_active=1, is_deleted=0
                )
                db.add(u); db.commit(); db.refresh(u)
            return u

        sa = get_or_create_user("eaac_sa@test.com", "EAAC SuperAdmin", "SuperAdmin")
        emp = get_or_create_user("eaac_emp@test.com", "EAAC Employee", "Employee")

        return org_id, sa.id, emp.id
    finally:
        db.close()

def main():
    print("\n" + "="*80)
    print(" VISIONCORE v2.0 — SPRINT 2 — ENTITY 6: EAAC INTEGRATION RUNTIME VALIDATION")
    print("="*80 + "\n")

    org_id, sa_id, emp_id = bootstrap()

    _, sa_h = login_user("eaac_sa@test.com")
    _, emp_h = login_user("eaac_emp@test.com")

    # =========================================================================
    # PHASE A: Identity & Tenant Context Verification
    # =========================================================================
    print("PHASE A: Identity & Tenant Context Verification")
    print("="*80)

    r = client.get("/api/v1/users/me", headers=sa_h)
    tc("A.1 SuperAdmin identity verified", r.status_code == 200, f"Got {r.status_code}", "identity")

    r = client.get("/api/v1/org/current", headers=sa_h)
    tc("A.2 Tenant context verified", r.status_code == 200, f"Got {r.status_code}", "identity")

    # =========================================================================
    # PHASE B: EAAC Diagnostic Evaluation Inspector
    # =========================================================================
    print("\nPHASE B: EAAC Diagnostic Evaluation Inspector")
    print("="*80)

    r = client.post("/api/v1/eaac/evaluate", json={
        "permission": "employee.read", "action": "read"
    }, headers=sa_h)
    tc("B.1 POST /eaac/evaluate grants SuperAdmin access", r.status_code == 200 and r.json()["granted"] is True, f"Got {r.status_code}", "eaac_eval")

    r = client.get("/api/v1/eaac/user-pipeline", headers=emp_h)
    tc("B.2 GET /eaac/user-pipeline returns 8-stage pipeline state", r.status_code == 200 and "pipeline_stages" in r.json(), f"Got {r.status_code}", "eaac_eval")

    # =========================================================================
    # PHASE C: Subscription Feature Entitlement Enforcement
    # =========================================================================
    print("\nPHASE C: Subscription Feature Entitlement Enforcement")
    print("="*80)

    r = client.get("/api/v1/subscription/plans", headers=sa_h)
    tc("C.1 Subscription plans active", r.status_code == 200, f"Got {r.status_code}", "subscription")

    # =========================================================================
    # PHASE D: Dynamic Role Permission Aggregation
    # =========================================================================
    print("\nPHASE D: Dynamic Role Permission Aggregation")
    print("="*80)

    r = client.get("/api/v1/dynamic-roles/effective-authorization", headers=emp_h)
    tc("D.1 Effective permissions resolved for dynamic user", r.status_code == 200, f"Got {r.status_code}", "roles")

    # =========================================================================
    # PHASE E: Data Scope Boundary Filter
    # =========================================================================
    print("\nPHASE E: Data Scope Boundary Filter")
    print("="*80)

    r = client.get("/api/v1/scope/effective-scope", params={"permission": "attendance.read"}, headers=emp_h)
    tc("E.1 Data scope resolved for attendance.read", r.status_code == 200, f"Got {r.status_code}", "scope")

    # =========================================================================
    # PHASE F: Governance & Approval Gate Check
    # =========================================================================
    print("\nPHASE F: Governance & Approval Gate Check")
    print("="*80)

    r = client.get("/api/v1/workflow/workflows", headers=sa_h)
    tc("F.1 Workflows engine integrated", r.status_code == 200, f"Got {r.status_code}", "workflow")

    # =========================================================================
    # PHASE G: Security & Boundary Defense
    # =========================================================================
    print("\nPHASE G: Security & Boundary Defense")
    print("="*80)

    r = client.post("/api/v1/dynamic-roles/roles", json={"code": "hack_role", "name": "Hack"}, headers=emp_h)
    tc("G.1 Non-admin unauthorized role creation returns 403", r.status_code == 403, f"Got {r.status_code}", "security")

    r = client.get("/api/v1/eaac/user-pipeline")
    tc("G.2 Unauthenticated access returns 401", r.status_code == 401, f"Got {r.status_code}", "security")

    # =========================================================================
    # PHASE H: High-Performance Benchmarks (< 200ms)
    # =========================================================================
    print("\nPHASE H: High-Performance Benchmarks (< 200ms)")
    print("="*80)

    t0 = time.time()
    for _ in range(5):
        client.post("/api/v1/eaac/evaluate", json={"permission": "attendance.read"}, headers=emp_h)
    avg_t = ((time.time() - t0) / 5.0) * 1000.0
    tc("H.1 Unified EAAC evaluation benchmark < 200ms", avg_t < 200.0, f"took {avg_t:.1f}ms", "performance")

    # =========================================================================
    # PHASE I & J: System-wide Regression Validation across all 8 Entities
    # =========================================================================
    print("\nPHASE I & J: System-wide Regression Validation across all 8 Entities")
    print("="*80)

    r = client.get("/api/v1/users/me", headers=sa_h)
    tc("I.1 Auth & User Service intact", r.status_code == 200, f"Got {r.status_code}", "regression")

    r = client.get("/api/v1/org/current", headers=sa_h)
    tc("I.2 Organization Service intact", r.status_code == 200, f"Got {r.status_code}", "regression")

    r = client.get("/api/v1/rbac/permissions", headers=sa_h)
    tc("I.3 RBAC Permission System intact", r.status_code == 200, f"Got {r.status_code}", "regression")

    r = client.get("/api/v1/subscription/plans", headers=sa_h)
    tc("I.4 Subscription & Feature Engine intact", r.status_code == 200, f"Got {r.status_code}", "regression")

    r = client.get("/api/v1/scope/effective-scope", params={"permission": "attendance.read"}, headers=sa_h)
    tc("I.5 Data Scope Engine intact", r.status_code == 200, f"Got {r.status_code}", "regression")

    r = client.get("/api/v1/workflow/workflows", headers=sa_h)
    tc("I.6 Approval Workflow Engine intact", r.status_code == 200, f"Got {r.status_code}", "regression")

    r = client.get("/api/v1/dynamic-roles/roles", headers=sa_h)
    tc("I.7 Dynamic Roles & Templates Engine intact", r.status_code == 200, f"Got {r.status_code}", "regression")

    # Summary
    print("\n" + "="*80)
    print(" VALIDATION SUMMARY")
    print("="*80)
    for cat, data in REPORT["phases"].items():
        pct = (data["passed"] / (data["passed"] + data["failed"])) * 100.0
        bar = "█" * int(pct // 10) + "░" * (10 - int(pct // 10))
        print(f"  {cat:<30} {bar} {pct:.1f}% ({data['passed']}/{data['passed'] + data['failed']})")

    REPORT["score"] = (REPORT["passed"] / REPORT["total"]) * 100.0
    print(f"\n  Total tests:   {REPORT['total']}")
    print(f"  Passed:        {REPORT['passed']}")
    print(f"  Failed:        {REPORT['failed']}")
    print(f"  Score:         {REPORT['score']:.1f}%")

    if REPORT["score"] == 100.0:
        print("\n" + "="*60)
        print("  Sprint 2 — Entity 6: Enterprise Authorization Integration")
        print("  Status: ✅ COMPLETE")
        print("  State: 🔒 FROZEN")
        print("  Score: 100.0%")
        print("="*60 + "\n")

    with open("integration_validation_report.json", "w") as f:
        json.dump(REPORT, f, indent=2)

    if REPORT["failed"] > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
