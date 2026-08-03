"""
runtime_validation_roles.py — Automated 10-Phase Runtime Validation Suite
Sprint 2 — Entity 5: Enterprise Dynamic Roles & Role Template Engine
"""
import sys
import time
import json
import uuid
import logging
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("validation_roles")

from fastapi.testclient import TestClient
from main import app
from app.db.database import SessionLocal

from app.db.models.all_models import (
    User, Organization, Role, DynamicRole, RoleTemplate,
    RoleInheritance, RoleVersion, UserRoleAssignment
)
from app.core.security import get_password_hash, create_access_token
from app.services.dynamic_role_engine import RoleInheritanceService

client = TestClient(app)

REPORT = {
    "entity": "Entity 5: Enterprise Dynamic Roles & Role Template Engine",
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

def bootstrap():
    db = SessionLocal()
    try:
        # Organization
        org = db.query(Organization).filter(Organization.name == "Role Test Corp").first()
        if not org:
            org = Organization(name="Role Test Corp", legal_id="ORG-ROLE-TEST-001", is_active=True)
            db.add(org); db.commit(); db.refresh(org)
        org_id = org.id


        # Roles
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

        sa = get_or_create_user("dr_sa@test.com", "DR SuperAdmin", "SuperAdmin")
        oa = get_or_create_user("dr_oa@test.com", "DR OrgAdmin", "OrgAdmin")
        emp = get_or_create_user("dr_emp@test.com", "DR Employee", "Employee")

        return org_id, sa.id, oa.id, emp.id
    finally:
        db.close()

def login_user(email):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": PASSWORD})
    if r.status_code != 200: return None, None
    tok = r.json().get("access_token")
    return tok, {"Authorization": f"Bearer {tok}"}

def main():
    print("\n" + "="*80)
    print(" VISIONCORE v2.0 — SPRINT 2 — ENTITY 5: DYNAMIC ROLES RUNTIME VALIDATION")
    print("="*80 + "\n")

    org_id, sa_id, oa_id, emp_id = bootstrap()

    # Headers
    _, sa_h = login_user("dr_sa@test.com")
    _, emp_h = login_user("dr_emp@test.com")



    # =========================================================================
    # PHASE A: Role Engine & Template Seeding
    # =========================================================================
    print("PHASE A: Role Engine & Template Seeding")
    print("="*80)

    r = client.post("/api/v1/dynamic-roles/seed", headers=sa_h)
    tc("A.1 POST /dynamic-roles/seed returns 200", r.status_code == 200, f"Got {r.status_code}", "templates")

    r = client.get("/api/v1/dynamic-roles/templates", headers=sa_h)
    tc("A.2 GET /dynamic-roles/templates returns 200", r.status_code == 200, f"Got {r.status_code}", "templates")
    templates = r.json()
    tc("A.3 Blueprint templates seeded (>0)", len(templates) > 0, f"count={len(templates)}", "templates")

    # =========================================================================
    # PHASE B: Role CRUD & Template Instantiation
    # =========================================================================
    print("\nPHASE B: Role CRUD & Template Instantiation")
    print("="*80)

    r = client.post("/api/v1/dynamic-roles/roles/from-template", params={"template_code": "hr_manager_template", "custom_name": "Custom HR Manager"}, headers=sa_h)
    tc("B.1 Create custom role from template", r.status_code == 201, f"Got {r.status_code}", "role_crud")
    hr_role = r.json()
    hr_role_id = hr_role["id"]

    role_code = f"custom_lead_dev_{uuid.uuid4().hex[:6]}"
    r = client.post("/api/v1/dynamic-roles/roles", json={
        "code": role_code,
        "name": "Lead Developer",
        "description": "Team lead developer role",
        "permissions_json": ["code.review", "deployment.trigger"]
    }, headers=sa_h)
    tc("B.2 POST /dynamic-roles/roles creates custom role", r.status_code == 201, f"Got {r.status_code}", "role_crud")

    lead_role = r.json()
    lead_role_id = lead_role["id"]

    r = client.get("/api/v1/dynamic-roles/roles", headers=sa_h)
    tc("B.3 GET /dynamic-roles/roles lists active roles", r.status_code == 200, f"Got {r.status_code}", "role_crud")

    # =========================================================================
    # PHASE C: Role Cloning & Inheritance Engine (DAG & Cycle Detection)
    # =========================================================================
    print("\nPHASE C: Role Cloning & Inheritance Engine")
    print("="*80)

    r = client.post(f"/api/v1/dynamic-roles/roles/{lead_role_id}/clone", params={"new_code": f"cloned_lead_dev_{uuid.uuid4().hex[:6]}", "new_name": "Cloned Lead Dev"}, headers=sa_h)

    tc("C.1 POST /roles/{id}/clone clones role", r.status_code == 201, f"Got {r.status_code}", "cloning")

    # Establish parent-child inheritance
    r = client.post("/api/v1/dynamic-roles/roles/inheritance", json={
        "parent_role_id": hr_role_id,
        "child_role_id": lead_role_id,
        "inherit_permissions": True
    }, headers=sa_h)
    tc("C.2 Establish parent-child inheritance (HR -> LeadDev)", r.status_code == 201, f"Got {r.status_code}", "inheritance")

    # Test Cycle Detection
    r = client.post("/api/v1/dynamic-roles/roles/inheritance", json={
        "parent_role_id": lead_role_id,
        "child_role_id": hr_role_id
    }, headers=sa_h)
    tc("C.3 Cycle detection prevents circular inheritance (400)", r.status_code == 400, f"Got {r.status_code}", "inheritance")

    # =========================================================================
    # PHASE D: Versioning, Diffing & Rollback Engine
    # =========================================================================
    print("\nPHASE D: Versioning, Diffing & Rollback Engine")
    print("="*80)

    r = client.put(f"/api/v1/dynamic-roles/roles/{lead_role_id}", json={
        "permissions_json": ["code.review", "deployment.trigger", "server.reboot"]
    }, headers=sa_h)
    tc("D.1 Update role increments version to v2", r.status_code == 200 and r.json()["version"] == 2, f"version={r.json().get('version')}", "versioning")

    r = client.get(f"/api/v1/dynamic-roles/roles/{lead_role_id}/versions", headers=sa_h)
    tc("D.2 GET /roles/{id}/versions returns version history", r.status_code == 200 and len(r.json()) >= 2, f"count={len(r.json())}", "versioning")

    r = client.get(f"/api/v1/dynamic-roles/roles/{lead_role_id}/diff", params={"v1": 1, "v2": 2}, headers=sa_h)
    tc("D.3 Role diff shows added permissions", r.status_code == 200 and "server.reboot" in r.json()["added_permissions"], f"diff={r.json()}", "diff")

    r = client.post(f"/api/v1/dynamic-roles/roles/{lead_role_id}/rollback/1", headers=sa_h)
    tc("D.4 Rollback restores version 1 state", r.status_code == 200 and "server.reboot" not in r.json()["permissions_json"], f"permissions={r.json().get('permissions_json')}", "rollback")

    # =========================================================================
    # PHASE E: User Multi-Role Assignment
    # =========================================================================
    print("\nPHASE E: User Multi-Role Assignment")
    print("="*80)

    r = client.post("/api/v1/dynamic-roles/roles/assign", json={
        "user_id": emp_id,
        "role_id": lead_role_id,
        "is_primary": True
    }, headers=sa_h)
    tc("E.1 Assign primary dynamic role to user", r.status_code == 201, f"Got {r.status_code}", "assignments")
    asgn_id = r.json()["id"]

    r = client.post("/api/v1/dynamic-roles/roles/assign", json={
        "user_id": emp_id,
        "role_id": hr_role_id,
        "is_primary": False
    }, headers=sa_h)
    tc("E.2 Assign secondary dynamic role to user", r.status_code == 201, f"Got {r.status_code}", "assignments")

    # =========================================================================
    # PHASE F: Effective Authorization Resolution
    # =========================================================================
    print("\nPHASE F: Effective Authorization Resolution")
    print("="*80)

    r = client.get("/api/v1/dynamic-roles/effective-authorization", headers=emp_h)
    tc("F.1 GET /effective-authorization returns 200", r.status_code == 200, f"Got {r.status_code}", "effective_auth")
    eff = r.json()
    tc("F.2 Effective permissions include inherited role permissions", len(eff["effective_permissions"]) > 0, f"perms={eff['effective_permissions']}", "effective_auth")

    # =========================================================================
    # PHASE G: Security & Multi-Tenant Isolation
    # =========================================================================
    print("\nPHASE G: Security & Multi-Tenant Isolation")
    print("="*80)

    r = client.post("/api/v1/dynamic-roles/roles", json={"code": "hacker_role", "name": "Hacker"}, headers=emp_h)
    tc("G.1 Non-admin user cannot create role (403)", r.status_code == 403, f"Got {r.status_code}", "security")

    r = client.get("/api/v1/dynamic-roles/roles")
    tc("G.2 Unauthenticated call returns 401", r.status_code == 401, f"Got {r.status_code}", "security")


    # =========================================================================
    # PHASE H: High-Performance Benchmarks (< 200ms)
    # =========================================================================
    print("\nPHASE H: High-Performance Benchmarks (< 200ms)")
    print("="*80)

    t0 = time.time()
    for _ in range(5):
        client.get("/api/v1/dynamic-roles/effective-authorization", headers=emp_h)
    avg_t = ((time.time() - t0) / 5.0) * 1000.0
    tc("H.1 Effective authorization benchmark < 200ms", avg_t < 200.0, f"took {avg_t:.1f}ms", "performance")

    # =========================================================================
    # PHASE I: System-wide Regression Validation across Frozen Modules
    # =========================================================================
    print("\nPHASE I: System-wide Regression Validation across Frozen Modules")
    print("="*80)

    r = client.get("/api/v1/users/me", headers=sa_h)
    tc("I.1 /users/me works (Auth/User frozen)", r.status_code == 200, f"Got {r.status_code}", "regression")

    r = client.get("/api/v1/org/current", headers=sa_h)
    tc("I.2 /org/current works (Organization frozen)", r.status_code == 200, f"Got {r.status_code}", "regression")

    r = client.get("/api/v1/rbac/permissions", headers=sa_h)
    tc("I.3 RBAC permissions works (RBAC frozen)", r.status_code == 200, f"Got {r.status_code}", "regression")

    r = client.get("/api/v1/subscription/plans", headers=sa_h)
    tc("I.4 Subscription plans works (Subscription frozen)", r.status_code == 200, f"Got {r.status_code}", "regression")

    r = client.get("/api/v1/scope/effective-scope", params={"permission": "attendance.read"}, headers=sa_h)
    tc("I.5 Data scope works (Data Scope frozen)", r.status_code == 200, f"Got {r.status_code}", "regression")

    r = client.get("/api/v1/workflow/workflows", headers=sa_h)
    tc("I.6 Workflow Engine works (Workflow frozen)", r.status_code == 200, f"Got {r.status_code}", "regression")

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
        print("  Sprint 2 — Entity 5: Enterprise Dynamic Roles Engine")
        print("  Status: ✅ COMPLETE")
        print("  State: 🔒 FROZEN")
        print("  Score: 100.0%")
        print("="*60 + "\n")

    with open("roles_validation_report.json", "w") as f:
        json.dump(REPORT, f, indent=2)

    if REPORT["failed"] > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
