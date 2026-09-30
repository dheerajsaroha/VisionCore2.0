"""
Reproduce the 403s an employee sees on a plain dashboard load.

The UI now hides modules the caller cannot open, but a 403 toast can still come
from a *background* request the shell or the dashboard fires on mount. This runs
as a real OrgEmployee in a real tenant and reports the status of every call the
frontend makes on `/dashboard` load plus the 30-second notification poll.
"""
import os
import sys
import uuid

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

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

# Every call the frontend makes on a dashboard load, plus the layout's poll.
DASHBOARD_LOAD = [
    ("permission: my permissions",      "GET",  "/api/v1/rbac/me/permissions", None),
    ("subscription: my subscription",  "GET",  "/api/v1/subscription/my/subscription", None),
    ("dashboard: overview",            "GET",  "/api/v1/dashboard/overview", None),
    ("dashboard: workforce-breakdown", "GET",  "/api/v1/dashboard/workforce-breakdown", None),
    ("dashboard: attendance-stats",    "GET",  "/api/v1/dashboard/attendance-stats", None),
    ("dashboard: leave-overview",      "GET",  "/api/v1/dashboard/leave-overview", None),
    ("dashboard: pending-approvals",   "GET",  "/api/v1/dashboard/pending-approvals", None),
    ("dashboard: alerts",              "GET",  "/api/v1/dashboard/alerts", None),
    ("dashboard: activity-feed",       "GET",  "/api/v1/dashboard/activity-feed", None),
    ("dashboard: analytics",           "GET",  "/api/v1/dashboard/analytics", None),
    ("dashboard: ai-insights",         "GET",  "/api/v1/dashboard/ai-insights", None),
    ("notifications: poll",            "GET",  "/api/v1/notifications", None),
    ("notifications: unread-count",    "GET",  "/api/v1/notifications/unread-count", None),
]

# Calls made by the pages an OrgEmployee is entitled to open, per the gate.
EMPLOYEE_PAGES = [
    ("attendance: my history",   "GET",  "/api/v1/attendance/logs", None),
    ("attendance: summary",      "GET",  "/api/v1/attendance/summary", None),
    ("attendance: corrections",  "GET",  "/api/v1/attendance-corrections/my", None),
    ("leave: balance",           "GET",  "/api/v1/leave/balance", None),
    ("leave: requests",          "GET",  "/api/v1/leave/requests", None),
    ("leave: types",             "GET",  "/api/v1/leave/types", None),
    ("documents: mine",          "GET",  "/api/v1/hcm/documents", None),
    ("tickets: list",            "GET",  "/api/v1/ticketing/", None),
    ("reimbursements: list",     "GET",  "/api/v1/reimbursement/", None),
]


def _tenant(db, plan_code="professional"):
    org = Organization(
        name=f"Repro {uuid.uuid4().hex[:6]}",
        legal_id=f"REPRO-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == plan_code).first()
    db.add(OrganizationSubscription(
        organization_id=org.id,
        subscription_plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
    ))
    role = db.query(Role).filter(Role.name == "OrgEmployee").first()
    user = User(
        org_id=org.id,
        role_id=role.id,
        full_name="Repro Employee",
        username=f"repro-{uuid.uuid4().hex[:8]}",
        email=f"repro-{uuid.uuid4().hex[:8]}@example.com",
        employee_id=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        hashed_password="x",
        is_active=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def main(plan_code="professional"):
    db = SessionLocal()
    user = _tenant(db, plan_code)
    uid = user.id
    org_name = db.query(Organization).filter(Organization.id == user.org_id).first().name

    def current():
        return db.query(User).filter(User.id == uid).first()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[deps.get_current_active_user] = current

    failures = 0
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            for title, probes in (("DASHBOARD LOAD", DASHBOARD_LOAD), ("EMPLOYEE PAGES", EMPLOYEE_PAGES)):
                print(f"\n{'=' * 74}\n  {title}  (org: {org_name})\n{'=' * 74}")
                for label, method, path, body in probes:
                    try:
                        fn = getattr(c, method.lower())
                        r = fn(path, **({"json": body} if body is not None else {}))
                        status, payload = r.status_code, r.text[:150]
                    except Exception as exc:
                        status, payload = "ERR", f"{type(exc).__name__}: {exc}"[:150]

                    bad = status in (401, 403, 402, 500) or status == "ERR"
                    if bad:
                        failures += 1
                    mark = "FAIL" if bad else "ok  "
                    print(f"  {mark} [{status}] {label}")
                    if bad:
                        print(f"         {payload}")
    finally:
        app.dependency_overrides.clear()
        db.close()
        rate_limit._fallback_windows.clear()

    print(f"\n{'PROBLEMS: ' + str(failures) if failures else 'clean: no 4xx/5xx on employee load'}\n")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1] if len(sys.argv) > 1 else "professional") else 0)
