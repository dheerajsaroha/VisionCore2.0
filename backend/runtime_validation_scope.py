#!/usr/bin/env python3
"""
runtime_validation_scope.py — Enterprise Data Scope & Resource Ownership Runtime Validation
Sprint 2 — Entity 3
"""
from __future__ import annotations
import json, logging, os, sys, time, uuid as uuid_mod
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

PYTHONPATH = os.path.join(os.path.dirname(__file__))
if PYTHONPATH not in sys.path:
    sys.path.insert(0, PYTHONPATH)

logging.basicConfig(level=logging.WARNING)

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from main import app
from app.db.database import SessionLocal
from app.db.models.all_models import (
    User, Role, Organization, DataScope, RoleDataScope,
    ResourceOwnership, OwnershipHistory, OwnershipDelegation,
    OwnershipRule, OwnershipPolicy, OwnershipException,
)
from app.core.security import get_password_hash

PASSWORD = "Vision@123"
RESULTS: dict[str, Any] = {
    "metadata": {"suite": "Data Scope & Resource Ownership", "sprint": "Sprint 2",
                 "entity": "Data Scope & Resource Ownership", "timestamp": datetime.now(timezone.utc).isoformat()},
    "phases": {}, "summary": {"total": 0, "passed": 0, "failed": 0, "defects": []},
}
ERRORS: list[str] = []
client = TestClient(app)

def log(msg): print(msg); sys.stdout.flush()

def phase_header(p, n):
    log(f"\n{'='*80}\nPHASE {p}: {n}\n{'='*80}")

def tc(name, cond, detail="", phase="general"):
    RESULTS["summary"]["total"] += 1
    s = "✅ PASS" if cond else "❌ FAIL"
    log(f"  {s} | [{phase}] {name}")
    if detail: log(f"         {detail}")
    if phase not in RESULTS["phases"]:
        RESULTS["phases"][phase] = {"passed": 0, "failed": 0, "tests": []}
    RESULTS["phases"][phase]["tests"].append({"name": name, "passed": cond, "detail": detail})
    if cond:
        RESULTS["phases"][phase]["passed"] += 1; RESULTS["summary"]["passed"] += 1
    else:
        RESULTS["phases"][phase]["failed"] += 1; RESULTS["summary"]["failed"] += 1
        RESULTS["summary"]["defects"].append({"phase": phase, "test": name, "detail": detail})
        ERRORS.append(f"[{phase}] {name}: {detail}")

def login_user(email):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": PASSWORD})
    if r.status_code != 200: return None, None
    tok = r.json().get("access_token")
    r2 = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tok}"})
    return tok, r2.json() if r2.status_code == 200 else None

def bootstrap():
    log(f"\n{'='*80}\nBOOTSTRAP\n{'='*80}")
    db = SessionLocal()
    from app.db.seed_subscription import seed_all, validate_subscription_seed
    seed_all(db)
    org = db.query(Organization).order_by(Organization.created_at).first()
    if not org:
        org = Organization(name="Scope Validation Org", legal_id=f"SCV-{uuid_mod.uuid4().hex[:8]}", primary_color="#4F46E5")
        db.add(org); db.commit(); db.refresh(org)
    roles = {r.name: r for r in db.query(Role).all()}
    user_map = {}
    for rn, em in [("SuperAdmin","sa_scope@test.local"),("OrgAdmin","oa_scope@test.local"),("OrgEmployee","emp_scope@test.local")]:
        role = roles.get(rn)
        if not role: continue
        u = db.query(User).filter(User.email == em).first()
        if not u:
            u = User(org_id=org.id, role_id=role.id, full_name=f"Scope {rn}",
                     username=f"scope_{rn.lower()}_{uuid_mod.uuid4().hex[:4]}",
                     email=em, employee_id=f"SCV-{rn[:3]}-{uuid_mod.uuid4().hex[:4]}",
                     hashed_password=get_password_hash(PASSWORD))
            db.add(u); db.commit(); db.refresh(u)
        user_map[rn] = {"email": em, "id": u.id, "user": u}
    org_id = org.id
    user_map["_org"] = org; user_map["_org_id"] = org_id; user_map["_roles"] = roles
    db.close()
    log(f"  ✅ Bootstrap complete: org_id={org_id}, users={list(user_map.keys())[:3]}")
    return user_map


# ── PHASE A: Scope API Validation ──
def phase_a_scope_apis(um):
    phase_header("A", "Scope API Validation")
    sa_tok, _ = login_user(um["SuperAdmin"]["email"])
    tc("A.0 SuperAdmin login", sa_tok is not None, phase="scope_apis")
    h = {"Authorization": f"Bearer {sa_tok}"}

    # Seed
    r = client.post("/api/v1/scope/seed", headers=h)
    tc("A.1 POST /scope/seed returns 200", r.status_code == 200, f"Got {r.status_code}", "scope_apis")
    tc("A.2 Seed returns scopes_seeded", r.json().get("scopes_seeded", 0) > 0, phase="scope_apis")

    # List data scopes
    r = client.get("/api/v1/scope/data-scopes", headers=h)
    tc("A.3 GET /data-scopes returns 200", r.status_code == 200, f"Got {r.status_code}", "scope_apis")
    d = r.json()
    tc("A.4 Has total field", "total" in d, phase="scope_apis")
    tc("A.5 Has data_scopes array", "data_scopes" in d, phase="scope_apis")
    tc("A.6 At least 11 scopes seeded", d.get("total", 0) >= 11, f"Got {d.get('total')}", "scope_apis")
    scopes = d.get("data_scopes", [])
    codes = [s["code"] for s in scopes]
    for c in ["platform", "organization", "department", "self"]:
        tc(f"A.7 Scope '{c}' exists", c in codes, phase="scope_apis")

    # Create duplicate scope → 409
    r = client.post("/api/v1/scope/data-scopes", json={"code": "platform", "name": "Dup", "scope_level": 100}, headers=h)
    tc("A.8 Duplicate scope code → 409", r.status_code == 409, f"Got {r.status_code}", "scope_apis")

    # Role data scopes
    r = client.get("/api/v1/scope/role-data-scopes", headers=h)
    tc("A.9 GET /role-data-scopes returns 200", r.status_code == 200, f"Got {r.status_code}", "scope_apis")
    tc("A.10 Has role_data_scopes array", "role_data_scopes" in r.json(), phase="scope_apis")

    # Effective scope
    r = client.get("/api/v1/scope/effective-scope", params={"permission": "attendance.read"}, headers=h)
    tc("A.11 GET /effective-scope returns 200", r.status_code == 200, f"Got {r.status_code}", "scope_apis")
    ed = r.json()
    tc("A.12 Has scope_code", "scope_code" in ed, phase="scope_apis")
    tc("A.13 Has scope_level", "scope_level" in ed, phase="scope_apis")
    tc("A.14 SuperAdmin gets platform scope", ed.get("scope_code") == "platform", f"Got {ed.get('scope_code')}", "scope_apis")
    tc("A.15 SuperAdmin scope level 100", ed.get("scope_level") == 100, f"Got {ed.get('scope_level')}", "scope_apis")
    tc("A.16 is_platform_admin=true", ed.get("is_platform_admin") is True, phase="scope_apis")

# ── PHASE B: Ownership API Validation ──
def phase_b_ownership_apis(um):
    phase_header("B", "Ownership API Validation")
    sa_tok, _ = login_user(um["SuperAdmin"]["email"])
    tc("B.0 SuperAdmin login", sa_tok is not None, phase="ownership_apis")
    h = {"Authorization": f"Bearer {sa_tok}"}
    org = um["_org"]
    sa_id = um["SuperAdmin"]["id"]
    emp_id = um["OrgEmployee"]["id"]

    # Assign ownership
    r = client.post("/api/v1/scope/ownerships", json={
        "entity_type": "document", "entity_id": f"test-doc-{uuid_mod.uuid4().hex[:8]}",
        "owner_type": "creator", "owner_user_id": sa_id,
    }, headers=h)
    tc("B.1 POST /ownerships returns 201", r.status_code == 201, f"Got {r.status_code}", "ownership_apis")
    od = r.json()
    tc("B.2 Has id", "id" in od, phase="ownership_apis")
    tc("B.3 owner_type=creator", od.get("owner_type") == "creator", phase="ownership_apis")

    # List ownerships
    r = client.get("/api/v1/scope/ownerships", headers=h)
    tc("B.4 GET /ownerships returns 200", r.status_code == 200, f"Got {r.status_code}", "ownership_apis")
    tc("B.5 Has ownerships array", "ownerships" in r.json(), phase="ownership_apis")
    tc("B.6 Has total", "total" in r.json(), phase="ownership_apis")

    # Transfer ownership
    eid = od.get("entity_id", "x")
    r = client.post("/api/v1/scope/ownerships/transfer", json={
        "entity_type": "document", "entity_id": eid,
        "new_owner_user_id": emp_id, "new_owner_type": "assignee", "reason": "Validation transfer test",
    }, headers=h)
    tc("B.7 POST /ownerships/transfer returns 200", r.status_code == 200, f"Got {r.status_code}", "ownership_apis")
    td = r.json()
    tc("B.8 Transfer new owner_type=assignee", td.get("owner_type") == "assignee", phase="ownership_apis")

    # History
    r = client.get("/api/v1/scope/ownerships/history", headers=h)
    tc("B.9 GET /ownerships/history returns 200", r.status_code == 200, f"Got {r.status_code}", "ownership_apis")
    hd = r.json()
    tc("B.10 Has history array", "history" in hd, phase="ownership_apis")
    tc("B.11 History has records", len(hd.get("history", [])) > 0, phase="ownership_apis")

# ── PHASE C: Delegation Validation ──
def phase_c_delegation(um):
    phase_header("C", "Delegation Validation")
    sa_tok, _ = login_user(um["SuperAdmin"]["email"])
    tc("C.0 SuperAdmin login", sa_tok is not None, phase="delegation")
    h = {"Authorization": f"Bearer {sa_tok}"}
    org_id = um["_org_id"]
    sa_id = um["SuperAdmin"]["id"]
    emp_id = um["OrgEmployee"]["id"]

    now = datetime.now(timezone.utc)
    r = client.post("/api/v1/scope/delegations", json={
        "delegator_user_id": sa_id, "delegatee_user_id": emp_id,
        "organization_id": str(org_id), "entity_type": "attendance",
        "start_date": now.isoformat(), "end_date": (now + timedelta(days=7)).isoformat(),
        "reason": "Validation delegation test",
    }, headers=h)
    tc("C.1 POST /delegations returns 201", r.status_code == 201, f"Got {r.status_code}", "delegation")
    dd = r.json()
    tc("C.2 Delegation has id", "id" in dd, phase="delegation")
    tc("C.3 Delegation is_active=true", dd.get("is_active") is True, phase="delegation")

    r = client.get("/api/v1/scope/delegations", headers=h)
    tc("C.4 GET /delegations returns 200", r.status_code == 200, f"Got {r.status_code}", "delegation")
    tc("C.5 Has delegations array", "delegations" in r.json(), phase="delegation")
    tc("C.6 Has total", "total" in r.json(), phase="delegation")

# ── PHASE D: Rules & Policies ──
def phase_d_rules_policies(um):
    phase_header("D", "Rules & Policies Validation")
    sa_tok, _ = login_user(um["SuperAdmin"]["email"])
    tc("D.0 SuperAdmin login", sa_tok is not None, phase="rules_policies")
    h = {"Authorization": f"Bearer {sa_tok}"}

    r = client.get("/api/v1/scope/rules", headers=h)
    tc("D.1 GET /rules returns 200", r.status_code == 200, f"Got {r.status_code}", "rules_policies")
    rd = r.json()
    tc("D.2 Has rules array", "rules" in rd, phase="rules_policies")
    tc("D.3 Rules seeded (>0)", len(rd.get("rules", [])) > 0, f"count={len(rd.get('rules',[]))}", "rules_policies")

    r = client.get("/api/v1/scope/policies", headers=h)
    tc("D.4 GET /policies returns 200", r.status_code == 200, f"Got {r.status_code}", "rules_policies")
    pd = r.json()
    tc("D.5 Has policies array", "policies" in pd, phase="rules_policies")
    tc("D.6 Policies seeded (>0)", len(pd.get("policies", [])) > 0, phase="rules_policies")

    # Create rule
    r = client.post("/api/v1/scope/rules", json={
        "entity_type": f"test_{uuid_mod.uuid4().hex[:4]}", "name": "Test Rule",
        "default_owner_type": "creator",
    }, headers=h)
    tc("D.7 POST /rules returns 201", r.status_code == 201, f"Got {r.status_code}", "rules_policies")

# ── PHASE E: Scope Resolution ──
def phase_e_scope_resolution(um):
    phase_header("E", "Scope Resolution Validation")
    h = {}
    for rn in ["SuperAdmin", "OrgAdmin", "OrgEmployee"]:
        tok, _ = login_user(um[rn]["email"])
        tc(f"E.0 {rn} login", tok is not None, phase="scope_resolution")
        hdr = {"Authorization": f"Bearer {tok}"}
        r = client.get("/api/v1/scope/effective-scope", params={"permission": "attendance.read"}, headers=hdr)
        tc(f"E.1 {rn} effective-scope 200", r.status_code == 200, f"Got {r.status_code}", "scope_resolution")
        d = r.json()
        if rn == "SuperAdmin":
            tc("E.2 SA scope=platform", d.get("scope_code") == "platform", f"Got {d.get('scope_code')}", "scope_resolution")
            tc("E.3 SA level=100", d.get("scope_level") == 100, phase="scope_resolution")
        elif rn == "OrgAdmin":
            tc("E.4 OA scope=organization", d.get("scope_code") == "organization", f"Got {d.get('scope_code')}", "scope_resolution")
            tc("E.5 OA level=80", d.get("scope_level") == 80, phase="scope_resolution")
        elif rn == "OrgEmployee":
            tc("E.6 Emp scope=self", d.get("scope_code") == "self", f"Got {d.get('scope_code')}", "scope_resolution")
            tc("E.7 Emp level=10", d.get("scope_level") == 10, phase="scope_resolution")

# ── PHASE F: Authorization Inspector ──
def phase_f_inspector(um):
    phase_header("F", "Authorization Inspector")
    sa_tok, _ = login_user(um["SuperAdmin"]["email"])
    tc("F.0 SuperAdmin login", sa_tok is not None, phase="inspector")
    h = {"Authorization": f"Bearer {sa_tok}"}
    org_id = um["_org_id"]

    r = client.post("/api/v1/scope/inspect", json={
        "user_id": um["SuperAdmin"]["id"], "organization_id": str(org_id), "permission_code": "attendance.read",
    }, headers=h)
    tc("F.1 POST /inspect returns 200", r.status_code == 200, f"Got {r.status_code}", "inspector")
    d = r.json()
    tc("F.2 Has allowed field", "allowed" in d, phase="inspector")
    tc("F.3 SA allowed=true", d.get("allowed") is True, phase="inspector")
    tc("F.4 Has resolved_scope_code", "resolved_scope_code" in d, phase="inspector")
    tc("F.5 Has ownership_matched", "ownership_matched" in d, phase="inspector")

    # Employee inspect
    r = client.post("/api/v1/scope/inspect", json={
        "user_id": um["OrgEmployee"]["id"], "organization_id": str(org_id), "permission_code": "attendance.read",
    }, headers=h)
    tc("F.6 Employee inspect 200", r.status_code == 200, f"Got {r.status_code}", "inspector")
    ed = r.json()
    tc("F.7 Employee scope=self", ed.get("resolved_scope_code") == "self", f"Got {ed.get('resolved_scope_code')}", "inspector")

# ── PHASE G: Database Validation ──
def phase_g_database(um):
    phase_header("G", "Database Validation")
    db = SessionLocal()
    try:
        tc("G.1 DataScope table exists", db.query(DataScope).count() >= 11, phase="database")
        tc("G.2 RoleDataScope table exists", db.query(RoleDataScope).count() >= 0, phase="database")
        tc("G.3 ResourceOwnership table exists", db.query(ResourceOwnership).count() >= 0, phase="database")
        tc("G.4 OwnershipHistory table exists", db.query(OwnershipHistory).count() >= 0, phase="database")
        tc("G.5 OwnershipDelegation table exists", db.query(OwnershipDelegation).count() >= 0, phase="database")
        tc("G.6 OwnershipRule table exists", db.query(OwnershipRule).count() >= 0, phase="database")
        tc("G.7 OwnershipPolicy table exists", db.query(OwnershipPolicy).count() >= 0, phase="database")
        tc("G.8 OwnershipException table exists", db.query(OwnershipException).count() >= 0, phase="database")
        p = db.query(DataScope).filter(DataScope.code == "platform").first()
        tc("G.9 Platform scope level=100", p and p.scope_level == 100, phase="database")
        s = db.query(DataScope).filter(DataScope.code == "self").first()
        tc("G.10 Self scope level=10", s and s.scope_level == 10, phase="database")
    finally:
        db.close()

# ── PHASE H: Security ──
def phase_h_security(um):
    phase_header("H", "Security Validation")
    emp_tok, _ = login_user(um["OrgEmployee"]["email"])
    tc("H.0 Employee login", emp_tok is not None, phase="security")
    h = {"Authorization": f"Bearer {emp_tok}"}

    r = client.post("/api/v1/scope/seed", headers=h)
    tc("H.1 Employee cannot seed (403)", r.status_code == 403, f"Got {r.status_code}", "security")
    r = client.post("/api/v1/scope/data-scopes", json={"code":"x","name":"x","scope_level":1}, headers=h)
    tc("H.2 Employee cannot create scope (403)", r.status_code == 403, f"Got {r.status_code}", "security")
    r = client.post("/api/v1/scope/role-data-scopes", json={"role_id":1,"data_scope_id":1}, headers=h)
    tc("H.3 Employee cannot create RDS (403)", r.status_code == 403, f"Got {r.status_code}", "security")
    r = client.post("/api/v1/scope/rules", json={"entity_type":"x","name":"x"}, headers=h)
    tc("H.4 Employee cannot create rules (403)", r.status_code == 403, f"Got {r.status_code}", "security")

    # Unauthenticated
    r = client.get("/api/v1/scope/data-scopes")
    tc("H.5 Unauthenticated → 401", r.status_code == 401, f"Got {r.status_code}", "security")
    r = client.get("/api/v1/scope/effective-scope", params={"permission": "x"})
    tc("H.6 Unauthenticated effective-scope → 401", r.status_code == 401, f"Got {r.status_code}", "security")

# ── PHASE I: Performance ──
def phase_i_performance(um):
    phase_header("I", "Performance Validation")
    sa_tok, _ = login_user(um["SuperAdmin"]["email"])
    tc("I.0 SuperAdmin login", sa_tok is not None, phase="performance")
    h = {"Authorization": f"Bearer {sa_tok}"}
    org_id = um["_org_id"]

    t0 = time.time(); client.get("/api/v1/scope/effective-scope", params={"permission":"attendance.read"}, headers=h)
    ms = (time.time()-t0)*1000
    tc("I.1 Scope resolution < 200ms", ms < 200, f"took {ms:.1f}ms", "performance")

    t0 = time.time(); client.get("/api/v1/scope/ownerships", headers=h)
    ms = (time.time()-t0)*1000
    tc("I.2 Ownership lookup < 200ms", ms < 200, f"took {ms:.1f}ms", "performance")

    t0 = time.time(); client.post("/api/v1/scope/inspect", json={"user_id":um["SuperAdmin"]["id"],"organization_id":str(org_id),"permission_code":"attendance.read"}, headers=h)
    ms = (time.time()-t0)*1000
    tc("I.3 Inspector < 200ms", ms < 200, f"took {ms:.1f}ms", "performance")

    t0 = time.time(); client.get("/api/v1/scope/data-scopes", headers=h)
    ms = (time.time()-t0)*1000
    tc("I.4 Data scopes listing < 200ms", ms < 200, f"took {ms:.1f}ms", "performance")

# ── PHASE J: Regression ──
def phase_j_regression(um):
    phase_header("J", "Regression Validation")
    sa_tok, _ = login_user(um["SuperAdmin"]["email"])
    tc("J.1 Login still works", sa_tok is not None, phase="regression")
    h = {"Authorization": f"Bearer {sa_tok}"}

    r = client.get("/api/v1/users/me", headers=h)
    tc("J.2 /users/me works", r.status_code == 200, f"Got {r.status_code}", "regression")
    r = client.get("/api/v1/org/current", headers=h)
    tc("J.3 /org/current works", r.status_code == 200, f"Got {r.status_code}", "regression")
    r = client.get("/api/v1/rbac/permissions", headers=h)
    tc("J.4 RBAC permissions works", r.status_code == 200, f"Got {r.status_code}", "regression")
    r = client.get("/api/v1/subscription/plans", headers=h)
    tc("J.5 Subscription plans works", r.status_code == 200, f"Got {r.status_code}", "regression")
    r = client.get("/health")
    tc("J.6 Health check works", r.status_code == 200, f"Got {r.status_code}", "regression")
    r = client.get("/api/v1/subscription/features", headers=h, params={"skip":0,"limit":5})
    tc("J.7 Features endpoint works", r.status_code == 200, f"Got {r.status_code}", "regression")

# ── MAIN ──
def main():
    log(f"\n{'#'*80}")
    log(f"  VisionCore v2.0 — Sprint 2 — Entity 3")
    log(f"  Enterprise Data Scope & Resource Ownership Runtime Validation")
    log(f"  {datetime.now(timezone.utc).isoformat()}")
    log(f"{'#'*80}")

    um = bootstrap()
    phase_a_scope_apis(um)
    phase_b_ownership_apis(um)
    phase_c_delegation(um)
    phase_d_rules_policies(um)
    phase_e_scope_resolution(um)
    phase_f_inspector(um)
    phase_g_database(um)
    phase_h_security(um)
    phase_i_performance(um)
    phase_j_regression(um)

    # Summary
    total = RESULTS["summary"]["total"]
    passed = RESULTS["summary"]["passed"]
    failed = RESULTS["summary"]["failed"]
    score = (passed / total * 100) if total > 0 else 0
    frozen = failed == 0

    log(f"\n{'='*80}\nVALIDATION SUMMARY\n{'='*80}")
    for ph, data in RESULTS["phases"].items():
        p = data["passed"]; f = data["failed"]; t = p + f
        pct = (p/t*100) if t > 0 else 0
        bar = "█" * int(pct/10)
        log(f"  {ph:30s} {bar:10s} {pct:5.1f}%")

    log(f"\n{'='*80}")
    log(f"  Total tests:   {total}")
    log(f"  Passed:        {passed}")
    log(f"  Failed:        {failed}")
    log(f"  Score:         {score:.1f}%")
    log(f"\n{'='*60}")
    log(f"  Sprint 2")
    log(f"  Entity 3 — Data Scope & Resource Ownership")
    log(f"  Status: {'✅ COMPLETE' if frozen else '❌ DEFECTS FOUND'}")
    log(f"  State: {'🔒 FROZEN' if frozen else '⚠️ NOT FROZEN'}")
    log(f"  Score: {score:.1f}%")
    log(f"{'='*60}")

    report_path = os.path.join(os.path.dirname(__file__), "scope_validation_report.json")
    RESULTS["summary"]["score"] = score
    RESULTS["summary"]["frozen"] = frozen
    with open(report_path, "w") as f:
        json.dump(RESULTS, f, indent=2, default=str)
    log(f"\n  Report saved to: {report_path}")
    log(f"\nJSON_RESULT:{json.dumps({'total':total,'passed':passed,'failed':failed,'score':score,'frozen':frozen})}")
    sys.exit(0 if frozen else 1)

if __name__ == "__main__":
    main()
