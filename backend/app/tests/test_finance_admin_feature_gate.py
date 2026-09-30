"""
Tests that the finance-admin surface honours the subscription feature gate.

The router was mounted with no `require_feature` dependency while `payroll.py`
was gated on the `payroll` feature. That let a tenant on a plan without payroll
read payroll-run totals and execute a full payroll run through
`/finance-admin/payroll-runs`, sidestepping the 402 on `/payroll/generate`.

These tests assert the gate holds on the gated paths and still admits a tenant
that has paid for the feature, so the fix cannot silently lock out real
customers.
"""
import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from main import app
from app.api import deps
from app.core import rate_limit
from app.db.database import SessionLocal, get_db
from app.db.models.all_models import (
    Organization,
    OrganizationSubscription,
    PayrollPeriod,
    PayrollRun,
    Role,
    SubscriptionPlan,
    User,
)


# Endpoints that are only entitled by a plan feature, with that feature.
GATED = [
    ("GET",    "/api/v1/finance-admin/expense-categories",   "expenses"),
    ("POST",   "/api/v1/finance-admin/expense-categories",   "expenses"),
    ("GET",    "/api/v1/finance-admin/salary-components",    "payroll"),
    ("GET",    "/api/v1/finance-admin/statutory-rules",      "payroll"),
    ("GET",    "/api/v1/finance-admin/tax-configurations",  "payroll"),
    ("GET",    "/api/v1/finance-admin/payroll-periods",      "payroll"),
    ("GET",    "/api/v1/finance-admin/payroll-runs",        "payroll"),
    ("POST",   "/api/v1/finance-admin/payroll-runs",        "payroll"),
]


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _tenant(db, plan_code):
    org = Organization(
        name=f"Gate {plan_code} {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-GATE-{uuid.uuid4().hex[:8].upper()}",
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

    role = db.query(Role).filter(Role.name == "OrgHR").first()
    user = User(
        org_id=org.id,
        role_id=role.id,
        full_name="Gate HR",
        username=f"gate-{uuid.uuid4().hex[:8]}",
        email=f"gate-{uuid.uuid4().hex[:8]}@example.com",
        employee_id=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        hashed_password="x",
        is_active=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    period = PayrollPeriod(
        organization_id=org.id,
        period_name="March 2026",
        start_date=datetime.date(2026, 3, 1),
        end_date=datetime.date(2026, 3, 31),
        pay_date=datetime.date(2026, 3, 31),
        status="draft",
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return user, period


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        app.dependency_overrides[get_db] = lambda: db
        try:
            yield c
        finally:
            app.dependency_overrides.clear()
            rate_limit._fallback_windows.clear()


def _call(db, client, method, path, user, body=None):
    app.dependency_overrides[deps.get_current_active_user] = (
        lambda uid=user.id: db.query(User).filter(User.id == uid).first()
    )
    try:
        fn = getattr(client, method.lower())
        return fn(path, json=body) if body is not None else fn(path)
    finally:
        app.dependency_overrides.pop(deps.get_current_active_user, None)


class TestFinanceAdminRespectsPlanFeatures:
    @pytest.mark.parametrize("method,path,feature", GATED)
    def test_starter_tenant_is_refused(self, db, client, method, path, feature):
        """A tenant on a plan without the feature must be refused, not 403/404."""
        user, _ = _tenant(db, "starter")
        resp = _call(db, client, method, path, user, body={} if method == "POST" else None)
        assert resp.status_code == 402, f"{method} {path} -> {resp.status_code}"
        assert resp.headers.get("X-Subscription-Feature") == feature

    @pytest.mark.parametrize("method,path,feature", GATED)
    def test_paid_tenant_is_admitted(self, db, client, method, path, feature):
        """The gate must not lock out a tenant that has bought the feature."""
        user, _ = _tenant(db, "professional")
        resp = _call(db, client, method, path, user, body={} if method == "POST" else None)
        # 403 means the permission check ran, i.e. the feature gate let it past.
        assert resp.status_code != 402, f"{method} {path} wrongly refused a paying tenant"

    def test_cannot_execute_a_payroll_run_without_the_feature(self, db, client):
        """The concrete abuse: a Starter tenant running payroll for the org."""
        user, period = _tenant(db, "starter")
        resp = _call(db, client, "POST", "/api/v1/finance-admin/payroll-runs", user, body={
            "payroll_period_id": period.id,
            "run_name": "unauthorised-run",
            "month": 3,
            "year": 2026,
        })
        assert resp.status_code == 402

        runs = db.query(PayrollRun).filter(
            PayrollRun.organization_id == user.org_id
        ).all()
        assert runs == [], f"a payroll run was persisted without the feature: {runs}"

    def test_payroll_run_totals_are_not_readable_without_the_feature(self, db, client):
        user, _ = _tenant(db, "starter")
        resp = _call(db, client, "GET", "/api/v1/finance-admin/payroll-runs", user)
        assert resp.status_code == 402
        # Aggregate gross/net must not leak through an error body either.
        assert "total_gross" not in resp.text

    def test_parity_with_the_payroll_router(self, db, client):
        """Both payroll entry points must agree on who is allowed."""
        user, _ = _tenant(db, "starter")
        via_payroll = _call(db, client, "GET", "/api/v1/payroll/", user)
        via_finance = _call(db, client, "GET", "/api/v1/finance-admin/payroll-runs", user)
        assert via_payroll.status_code == via_finance.status_code == 402
