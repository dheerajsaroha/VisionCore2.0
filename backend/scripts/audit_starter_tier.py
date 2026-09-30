"""
Starter-tier reachability probe.

Not a regression test: this is the evidence pass behind the Starter packaging
gap analysis. It provisions a real tenant on the *seeded Starter plan* and
probes every Starter-scope workflow an employee and an HR admin would need,
recording the exact status each call returns.

Run with:  .venv/bin/python backend/scripts/audit_starter_tier.py
"""
import os
import sys
import uuid

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from app.api import deps  # noqa: E402
from app.core import rate_limit  # noqa: E402
from app.db.database import SessionLocal, get_db  # noqa: E402
from app.db.models.all_models import (  # noqa: E402
    Organization,
    OrganizationSubscription,
    Role,
    SubscriptionPlan,
    User,
)

# (label, method, path, body) for the Starter-scope workflows in the roadmap.
# Paths are taken from the live OpenAPI spec, not guessed.
EMPLOYEE_PROBES = [
    ("dashboard overview",        "GET",  "/api/v1/dashboard/overview", None),
    ("attendance summary",        "GET",  "/api/v1/attendance/summary", None),
    ("leave balance",             "GET",  "/api/v1/leave/balance", None),
    ("my leave requests",         "GET",  "/api/v1/leave/requests", None),
    ("own documents",             "GET",  "/api/v1/hcm/documents", None),
    ("notifications",             "GET",  "/api/v1/notifications", None),
    ("my attendance corrections", "GET",  "/api/v1/attendance-corrections/my", None),
    ("my payslips",               "GET",  "/api/v1/payroll/me/payslips", None),
    ("my reimbursements",         "GET",  "/api/v1/reimbursement/", None),
]

HR_PROBES = [
    ("employee list",             "GET",  "/api/v1/users/?skip=0&limit=5", None),
    ("run payroll",               "GET",  "/api/v1/payroll/", None),
    ("statutory rules",           "GET",  "/api/v1/finance-admin/statutory-rules", None),
    ("payroll runs",              "GET",  "/api/v1/finance-admin/payroll-runs", None),
    ("candidates",                "GET",  "/api/v1/recruitment/candidates", None),
    ("offer letters",             "GET",  "/api/v1/recruitment/offer-letters", None),
    ("assets inventory",          "GET",  "/api/v1/assets/inventory", None),
    ("learning courses",          "GET",  "/api/v1/learning/courses", None),
    ("performance cycles",        "GET",  "/api/v1/hcm/performance/cycles", None),
    ("invite employee",           "POST", "/api/v1/org/invites", {}),
]


def _provision(db, plan_code, role_name):
    org = Organization(
        name=f"Audit {plan_code} {uuid.uuid4().hex[:6]}",
        legal_id=f"AUDIT-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == plan_code).first()
    assert plan, f"plan {plan_code} must be seeded"
    db.add(OrganizationSubscription(
        organization_id=org.id,
        subscription_plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
    ))

    role = db.query(Role).filter(Role.name == role_name).first()
    assert role, f"role {role_name} must be seeded"
    user = User(
        org_id=org.id,
        role_id=role.id,
        full_name=f"Audit {role_name}",
        username=f"audit-{uuid.uuid4().hex[:8]}",
        email=f"audit-{uuid.uuid4().hex[:8]}@example.com",
        employee_id=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        hashed_password="x",
        is_active=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return org, user


def _probe(client, label, method, path, body):
    fn = getattr(client, method.lower())
    kwargs = {"json": body} if body is not None else {}
    try:
        r = fn(path, **kwargs)
    except Exception as exc:
        return label, "ERR", type(exc).__name__
    return label, r.status_code, _why(r)


def _why(r):
    if r.status_code == 402:
        return r.headers.get("X-Subscription-Feature", "?")
    if r.status_code == 403:
        return r.headers.get("X-Permission", "perm")
    return ""


def audit(plan_code):
    db = SessionLocal()
    results = []
    try:
        _, employee = _provision(db, plan_code, "OrgEmployee")
        _, hr = _provision(db, plan_code, "OrgHR")
        for user, probes in ((employee, EMPLOYEE_PROBES), (hr, HR_PROBES)):
            # Re-read the user per request: a previous TestClient lifespan can
            # leave the instance detached, and the auth/permission path needs
            # `user.role` to be live.
            uid, who = user.id, user.full_name.split()[1]

            def _current(uid=uid):
                return db.query(User).filter(User.id == uid).first()

            app.dependency_overrides[get_db] = lambda: db
            app.dependency_overrides[deps.get_current_active_user] = _current
            with TestClient(app) as client:
                for probe in probes:
                    results.append((who,) + _probe(client, *probe))
            app.dependency_overrides.pop(deps.get_current_active_user, None)
    finally:
        app.dependency_overrides.clear()
        db.close()
        rate_limit._fallback_windows.clear()
    return results


def report(plan_code):
    print(f"\n{'=' * 74}\n  {plan_code.upper()} TIER REACHABILITY\n{'=' * 74}")
    results = audit(plan_code)
    groups = {}
    for who, label, code, why in results:
        groups.setdefault(who, []).append((label, code, why))

    for who, rows in groups.items():
        print(f"\n  -- acting as {who} --")
        for label, code, why in rows:
            mark = {200: "OK  ", 201: "OK  ", 200: "OK  "}.get(code, "FAIL")
            if code in (200, 201, 204):
                mark = "OK  "
            elif code == 422:
                mark = "SENT"   # reached the handler; body shape only
            detail = f"  <- {why}" if why else ""
            print(f"    {mark} [{code}] {label}{detail}")

    blocked = [r for r in results if r[2] not in (200, 201, 204, 422)]
    print(f"\n  blocked: {len(blocked)}/{len(results)}")
    return results


if __name__ == "__main__":
    for plan in ("starter", "professional"):
        report(plan)
