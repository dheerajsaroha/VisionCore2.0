#!/usr/bin/env python3
"""
runtime_validation_workflow.py — Enterprise Approval Workflow Engine Runtime Validation Suite
Sprint 2 — Entity 4
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
    User, Role, Organization, ApprovalWorkflow, ApprovalStage,
    ApprovalStageApprover, ApprovalTemplate, ApprovalRequest,
    ApprovalAction, ApprovalHistory, ApprovalDelegation
)
from app.core.security import get_password_hash

PASSWORD = "Vision@123"
RESULTS: dict[str, Any] = {
    "metadata": {"suite": "Enterprise Approval Workflow Engine", "sprint": "Sprint 2",
                 "entity": "Approval Workflow Engine", "timestamp": datetime.now(timezone.utc).isoformat()},
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
    return tok, {"Authorization": f"Bearer {tok}"}

def bootstrap():
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.legal_id == "val-org-wf").first()
        if not org:
            org = Organization(name="WF Validation Org", legal_id="val-org-wf", is_active=True)
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




        sa = get_or_create_user("wf_sa@test.com", "WF SuperAdmin", "SuperAdmin")
        oa = get_or_create_user("wf_oa@test.com", "WF OrgAdmin", "OrgAdmin")
        emp = get_or_create_user("wf_emp@test.com", "WF Employee", "Employee")
        mgr = get_or_create_user("wf_mgr@test.com", "WF Manager", "DepartmentHead")

        sa_id, oa_id, emp_id, mgr_id = sa.id, oa.id, emp.id, mgr.id
        return org_id, sa_id, oa_id, emp_id, mgr_id
    finally:
        db.close()

def main():
    log("\n" + "="*80)
    log(" VisionCore v2.0 — Sprint 2 — Entity 4")
    log(" Enterprise Approval Workflow Engine Runtime Validation Suite")
    log("="*80)

    org_id, sa_id, oa_id, emp_id, mgr_id = bootstrap()
    _, sa_h = login_user("wf_sa@test.com")
    _, oa_h = login_user("wf_oa@test.com")
    _, emp_h = login_user("wf_emp@test.com")

    # ── PHASE A: Workflow & Template Management ──
    phase_header("A", "Workflow & Blueprint Templates")
    r = client.post("/api/v1/workflow/seed", headers=sa_h)
    tc("A.1 POST /workflow/seed returns 200", r.status_code == 200, f"Got {r.status_code}", "templates")
    
    r = client.get("/api/v1/workflow/templates", headers=sa_h)
    tc("A.2 GET /workflow/templates returns 200", r.status_code == 200, f"Got {r.status_code}", "templates")
    tmpls = r.json() if r.status_code == 200 else []
    tc("A.3 Blueprint templates seeded (>0)", len(tmpls) > 0, f"count={len(tmpls)}", "templates")

    r = client.get("/api/v1/workflow/workflows", headers=sa_h)
    tc("A.4 GET /workflow/workflows returns 200", r.status_code == 200, f"Got {r.status_code}", "workflows")

    wf_code = f"custom_leave_wf_{uuid_mod.uuid4().hex[:6]}"
    wf_payload = {
        "code": wf_code, "name": "Custom Leave Workflow",
        "entity_type": "leave", "description": "2-stage approval workflow",
        "stages": [
            {
                "stage_order": 1, "name": "Manager Review", "approval_type": "single",
                "sla_hours": 24, "approvers": [{"approver_type": "user", "approver_user_id": oa_id}]
            },
            {
                "stage_order": 2, "name": "HR Final Signoff", "approval_type": "single",
                "sla_hours": 48, "approvers": [{"approver_type": "user", "approver_user_id": sa_id}]
            }
        ]
    }
    r = client.post("/api/v1/workflow/workflows", json=wf_payload, headers=sa_h)
    tc("A.5 POST /workflow/workflows creates custom workflow", r.status_code == 201, f"Got {r.status_code}", "workflows")
    created_wf = r.json() if r.status_code == 201 else {}
    custom_wf_id = created_wf.get("id")

    # ── PHASE B: Stage & Approver Configuration ──
    phase_header("B", "Stage & Approver Configuration")
    tc("B.1 Custom workflow has 2 stages", len(created_wf.get("stages", [])) == 2, f"stages={len(created_wf.get('stages', []))}", "stages")
    
    stage_add = {
        "stage_order": 3, "name": "Executive Audit", "approval_type": "single",
        "sla_hours": 72, "approvers": [{"approver_type": "user", "approver_user_id": sa_id}]
    }
    r = client.post(f"/api/v1/workflow/workflows/{custom_wf_id}/stages", json=stage_add, headers=sa_h)
    tc("B.2 POST /workflows/{id}/stages appends 3rd stage", r.status_code == 201, f"Got {r.status_code}", "stages")

    # ── PHASE C: Single & Multi-Stage Approval Flows ──
    phase_header("C", "Single & Multi-Stage Approval Execution")
    req_payload = {
        "workflow_code": wf_code, "entity_type": "leave",
        "entity_id": f"LV-{uuid_mod.uuid4().hex[:6]}", "priority": "high",
        "title": "Annual Leave Request", "request_payload": {"days": 5, "reason": "Vacation"}
    }
    r = client.post("/api/v1/workflow/requests/submit", json=req_payload, headers=emp_h)
    tc("C.1 POST /requests/submit creates request", r.status_code == 201, f"Got {r.status_code}", "request_flow")
    req_obj = r.json() if r.status_code == 201 else {}
    req_id = req_obj.get("id")
    tc("C.2 Initial status is pending", req_obj.get("status") == "pending", f"status={req_obj.get('status')}", "request_flow")
    tc("C.3 Stage order is 1", req_obj.get("current_stage_order") == 1, f"stage={req_obj.get('current_stage_order')}", "request_flow")

    # OrgAdmin approves stage 1 -> advances to stage 2
    r = client.post(f"/api/v1/workflow/requests/{req_id}/action", json={"action": "approve", "comments": "Manager LGTM"}, headers=oa_h)
    tc("C.4 Stage 1 approval advances request", r.status_code == 200, f"Got {r.status_code}", "request_flow")
    adv_req = r.json() if r.status_code == 200 else {}
    tc("C.5 Current stage order is 2", adv_req.get("current_stage_order") == 2, f"stage={adv_req.get('current_stage_order')}", "request_flow")

    # SuperAdmin approves stage 2 -> advances to stage 3
    r = client.post(f"/api/v1/workflow/requests/{req_id}/action", json={"action": "approve", "comments": "HR approved"}, headers=sa_h)
    tc("C.6 Stage 2 approval advances request", r.status_code == 200, f"Got {r.status_code}", "request_flow")

    # SuperAdmin approves stage 3 -> completes approval
    r = client.post(f"/api/v1/workflow/requests/{req_id}/action", json={"action": "approve", "comments": "Final signoff"}, headers=sa_h)
    tc("C.7 Stage 3 approval completes workflow", r.status_code == 200, f"Got {r.status_code}", "request_flow")
    final_req = r.json() if r.status_code == 200 else {}
    tc("C.8 Final status is approved", final_req.get("status") == "approved", f"status={final_req.get('status')}", "request_flow")

    # ── PHASE D: Rejection & Rework ──
    phase_header("D", "Rejection & Rework Return Flows")
    req_payload2 = {
        "workflow_code": wf_code, "entity_type": "leave",
        "entity_id": f"LV-{uuid_mod.uuid4().hex[:6]}", "priority": "medium",
        "title": "Short Leave Request", "request_payload": {"days": 1}
    }
    r = client.post("/api/v1/workflow/requests/submit", json=req_payload2, headers=emp_h)
    req_id2 = r.json().get("id") if r.status_code == 201 else None

    # OrgAdmin rejects request
    r = client.post(f"/api/v1/workflow/requests/{req_id2}/action", json={"action": "reject", "comments": "Insufficient notice"}, headers=oa_h)
    tc("D.1 Rejection sets status to rejected", r.status_code == 200 and r.json().get("status") == "rejected", f"Got {r.status_code}", "rejection")

    # Test Return for Rework
    r = client.post("/api/v1/workflow/requests/submit", json=req_payload2, headers=emp_h)
    req_id3 = r.json().get("id") if r.status_code == 201 else None
    r = client.post(f"/api/v1/workflow/requests/{req_id3}/action", json={"action": "return", "comments": "Provide medical note"}, headers=oa_h)
    tc("D.2 Return sets status to returned", r.status_code == 200 and r.json().get("status") == "returned", f"Got {r.status_code}", "rework")

    # ── PHASE E: Auto-Approval & Inspection ──
    phase_header("E", "Auto-Approval & Inspector Validation")
    auto_wf_code = f"auto_wf_{uuid_mod.uuid4().hex[:6]}"
    r = client.post("/api/v1/workflow/workflows", json={
        "code": auto_wf_code, "name": "Auto Approve Workflow",
        "entity_type": "attendance", "auto_approval_enabled": True,
        "stages": [{"stage_order": 1, "name": "Auto Stage", "approval_type": "single", "approvers": [{"approver_type": "user", "approver_user_id": sa_id}]}]
    }, headers=sa_h)
    tc("E.1 Auto-approval workflow created", r.status_code == 201, f"Got {r.status_code}", "auto_approve")

    r = client.post("/api/v1/workflow/requests/submit", json={
        "workflow_code": auto_wf_code, "entity_type": "attendance",
        "entity_id": f"ATT-{uuid_mod.uuid4().hex[:6]}", "title": "Clock Correction"
    }, headers=emp_h)
    tc("E.2 Auto-approval triggers status=approved immediately", r.status_code == 201 and r.json().get("status") == "approved", f"Got {r.status_code}", "auto_approve")

    r = client.post("/api/v1/workflow/inspect", params={"entity_type": "leave"}, headers=sa_h)
    tc("E.3 POST /workflow/inspect returns applicable stages", r.status_code == 200 and r.json().get("workflow_found") is True, f"Got {r.status_code}", "inspector")

    # ── PHASE F: Delegations & SLA Breaches ──
    phase_header("F", "Delegations & SLA Breach Monitoring")
    deleg_start = datetime.now(timezone.utc).isoformat()
    deleg_end = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    r = client.post("/api/v1/workflow/delegations", json={
        "delegatee_user_id": oa_id, "entity_type": "leave",
        "start_date": deleg_start, "end_date": deleg_end, "reason": "Vacation delegate"
    }, headers=emp_h)
    tc("F.1 POST /workflow/delegations creates delegation", r.status_code == 201, f"Got {r.status_code}", "delegations")

    r = client.get("/api/v1/workflow/delegations", headers=oa_h)
    tc("F.2 GET /workflow/delegations returns active delegation", r.status_code == 200 and len(r.json()) > 0, f"Got {r.status_code}", "delegations")

    r = client.post("/api/v1/workflow/sla/check-breaches", headers=sa_h)
    tc("F.3 POST /workflow/sla/check-breaches executes successfully", r.status_code == 200, f"Got {r.status_code}", "sla")

    # ── PHASE G: Queues & Analytics ──
    phase_header("G", "Pending Queue & Analytics Validation")
    r = client.get("/api/v1/workflow/requests/pending", headers=oa_h)
    tc("G.1 GET /workflow/requests/pending returns 200", r.status_code == 200, f"Got {r.status_code}", "queues")

    r = client.get("/api/v1/workflow/requests/my-requests", headers=emp_h)
    tc("G.2 GET /workflow/requests/my-requests returns user requests", r.status_code == 200 and r.json().get("total") > 0, f"Got {r.status_code}", "queues")

    r = client.get("/api/v1/workflow/analytics", headers=sa_h)
    tc("G.3 GET /workflow/analytics returns performance metrics", r.status_code == 200 and "sla_compliance_rate" in r.json(), f"Got {r.status_code}", "analytics")

    # ── PHASE H: Security & Multi-Tenant Isolation ──
    phase_header("H", "Security & Multi-Tenant Isolation")
    r = client.post("/api/v1/workflow/workflows", json={"code": "hack_wf", "name": "Hack", "entity_type": "leave"}, headers=emp_h)
    tc("H.1 Non-admin cannot create workflow (403)", r.status_code == 403, f"Got {r.status_code}", "security")

    r = client.post("/api/v1/workflow/requests/submit", json={"workflow_code": wf_code, "entity_type": "leave", "entity_id": "L1"})
    tc("H.2 Unauthenticated submit returns 401", r.status_code == 401, f"Got {r.status_code}", "security")

    # ── PHASE I: Performance Validation ──
    phase_header("I", "Performance Validation (< 200ms)")
    t0 = time.time()
    client.get("/api/v1/workflow/workflows", headers=sa_h)
    dt1 = (time.time() - t0) * 1000
    tc("I.1 Workflows listing < 200ms", dt1 < 200, f"took {dt1:.1f}ms", "performance")

    t0 = time.time()
    client.get("/api/v1/workflow/requests/pending", headers=oa_h)
    dt2 = (time.time() - t0) * 1000
    tc("I.2 Pending queue resolution < 200ms", dt2 < 200, f"took {dt2:.1f}ms", "performance")

    t0 = time.time()
    client.post("/api/v1/workflow/inspect", params={"entity_type": "leave"}, headers=sa_h)
    dt3 = (time.time() - t0) * 1000
    tc("I.3 Workflow inspector < 200ms", dt3 < 200, f"took {dt3:.1f}ms", "performance")

    # ── PHASE J: Regression Validation ──
    phase_header("J", "Regression Validation across Frozen Modules")
    r = client.get("/api/v1/users/me", headers=emp_h)
    tc("J.1 /users/me works (Auth/User frozen)", r.status_code == 200, f"Got {r.status_code}", "regression")

    r = client.get("/api/v1/org/current", headers=oa_h)
    tc("J.2 /org/current works (Organization frozen)", r.status_code == 200, f"Got {r.status_code}", "regression")

    r = client.get("/api/v1/rbac/permissions", headers=sa_h)
    tc("J.3 RBAC permissions works (RBAC frozen)", r.status_code == 200, f"Got {r.status_code}", "regression")

    r = client.get("/api/v1/subscription/plans", headers=sa_h)
    tc("J.4 Subscription plans works (Subscription frozen)", r.status_code == 200, f"Got {r.status_code}", "regression")

    r = client.get("/api/v1/scope/effective-scope", params={"permission": "attendance.read"}, headers=sa_h)
    tc("J.5 Data scope works (Data Scope frozen)", r.status_code == 200, f"Got {r.status_code}", "regression")


    # Summary
    log("\n" + "="*80)
    log(" VALIDATION SUMMARY")
    log("="*80)
    total_passed = RESULTS["summary"]["passed"]
    total_tests = RESULTS["summary"]["total"]
    score = (total_passed / total_tests * 100) if total_tests > 0 else 0.0
    for p, pdata in RESULTS["phases"].items():
        pct = (pdata["passed"] / len(pdata["tests"]) * 100) if pdata["tests"] else 0.0
        bar = "█" * int(pct // 10) + "░" * (10 - int(pct // 10))
        log(f"  {p:<30} {bar} {pct:.1f}% ({pdata['passed']}/{len(pdata['tests'])})")

    log(f"\n  Total tests:   {total_tests}")
    log(f"  Passed:        {total_passed}")
    log(f"  Failed:        {RESULTS['summary']['failed']}")
    log(f"  Score:         {score:.1f}%\n")

    if score == 100.0:
        log("============================================================")
        log("  Sprint 2 — Entity 4: Enterprise Approval Workflow Engine")
        log("  Status: ✅ COMPLETE")
        log("  State: 🔒 FROZEN")
        log("  Score: 100.0%")
        log("============================================================\n")

    report_path = os.path.join(os.path.dirname(__file__), "workflow_validation_report.json")
    with open(report_path, "w") as f:
        json.dump(RESULTS, f, indent=2)
    log(f"  Report saved to: {report_path}")

    if ERRORS:
        sys.exit(1)

if __name__ == "__main__":
    main()
