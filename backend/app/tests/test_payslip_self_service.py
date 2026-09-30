"""
Tests for employee payslip self-service.

The blueprint puts digital payslips in the employee self-service portal, but
there was no way for an employee to reach one: the listing route requires
`payroll.view`, which an ordinary employee does not hold, and the payslip route
takes a raw internal integer id they would have to guess. `/payroll/me/payslips`
closes that gap.

These also cover the ownership rules, since a self-service listing is exactly
the kind of endpoint that must not leak a colleague's pay.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from main import app
from app.api import deps
from app.db.database import SessionLocal, get_db
from app.db.models.all_models import (
    Organization,
    OrganizationSubscription,
    Payroll,
    Payslip,
    Role,
    SubscriptionPlan,
    User,
)


VALID_PASSWORD = "Str0ng-Passphrase!42"


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def org(db):
    row = Organization(
        name=f"Payslip Org {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-PSLIP-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    # The payroll router is gated on the 'payroll' feature, so the tenant needs
    # a plan that grants it. `professional` is the cheapest plan that does.
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "professional").first()
    assert plan is not None, "the professional plan must be seeded"
    db.add(OrganizationSubscription(
        organization_id=row.id,
        subscription_plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
    ))
    db.commit()
    return row


def _user(db, org, role_name, label):
    role = db.query(Role).filter(Role.name == role_name).first()
    assert role is not None, f"seeded role {role_name} required"
    user = User(
        org_id=org.id,
        role_id=role.id,
        full_name=label,
        username=f"ps-{uuid.uuid4().hex[:8]}",
        email=f"ps-{uuid.uuid4().hex[:8]}@example.com",
        employee_id=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        hashed_password="x",
        is_active=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _payroll(db, org, user, month=3, year=2026, status="paid", currency="INR"):
    row = Payroll(
        user_id=user.id,
        org_id=org.id,
        month=month,
        year=year,
        base_salary=Decimal("50000.00"),
        deductions=Decimal("6000.00"),
        reimbursements_total=Decimal("0.00"),
        total_salary=Decimal("44000.00"),
        status=status,
        currency=currency,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def client(db):
    from app.core import rate_limit

    with TestClient(app) as c:
        app.dependency_overrides[get_db] = lambda: db
        try:
            yield c
        finally:
            app.dependency_overrides.clear()
            rate_limit._fallback_windows.clear()


def _as(user):
    app.dependency_overrides[deps.get_current_active_user] = lambda: user


class TestMyPayslips:
    def test_returns_only_the_callers_own_payslips(self, db, org, client):
        me = _user(db, org, "OrgEmployee", "Me")
        colleague = _user(db, org, "OrgEmployee", "Colleague")
        mine = _payroll(db, org, me)
        colleague_payroll = _payroll(db, org, colleague)

        _as(me)
        response = client.get("/api/v1/payroll/me/payslips")
        assert response.status_code == 200, response.text
        rows = response.json()

        assert len(rows) == 1
        assert rows[0]["payroll_id"] == mine.id
        assert all(r["payroll_id"] != colleague_payroll.id for r in rows)

    def test_never_returns_another_tenants_payslips(self, db, org, client):
        other = Organization(
            name=f"Other {uuid.uuid4().hex[:6]}",
            legal_id=f"TEST-PSLIP-{uuid.uuid4().hex[:8].upper()}",
        )
        db.add(other)
        db.commit()
        db.refresh(other)

        me = _user(db, org, "OrgEmployee", "Mine")
        theirs = _user(db, other, "OrgEmployee", "Theirs")
        _payroll(db, org, me)
        _payroll(db, other, theirs)

        _as(me)
        rows = client.get("/api/v1/payroll/me/payslips").json()
        assert len(rows) == 1

    def test_newest_period_first(self, db, org, client):
        me = _user(db, org, "OrgEmployee", "Ordered")
        _payroll(db, org, me, month=1, year=2026)
        _payroll(db, org, me, month=11, year=2026)
        _payroll(db, org, me, month=6, year=2025)

        _as(me)
        rows = client.get("/api/v1/payroll/me/payslips").json()
        assert [(r["year"], r["month"]) for r in rows] == [
            (2026, 11), (2026, 1), (2025, 6),
        ]

    def test_reports_the_payslip_currency(self, db, org, client):
        me = _user(db, org, "OrgEmployee", "Currency")
        _payroll(db, org, me, currency="INR")

        _as(me)
        rows = client.get("/api/v1/payroll/me/payslips").json()
        assert rows[0]["currency"] == "INR"

    def test_marks_whether_a_document_exists(self, db, org, client):
        me = _user(db, org, "OrgEmployee", "Docs")
        with_doc = _payroll(db, org, me, month=1)
        _payroll(db, org, me, month=2)  # no payslip row yet

        db.add(Payslip(
            payroll_id=with_doc.id,
            org_id=org.id,
            user_id=me.id,
            period_label="2026-01",
            gross_salary=Decimal("50000.00"),
            total_deductions=Decimal("6000.00"),
            net_pay=Decimal("44000.00"),
            currency="INR",
            file_url="payslips/2026-01/abc.pdf",
            pdf_sha256="a" * 64,
        ))
        db.commit()

        _as(me)
        rows = {
            r["month"]: r for r in client.get("/api/v1/payroll/me/payslips").json()
        }
        assert rows[1]["payslip_available"] is True
        assert rows[2]["payslip_available"] is False

    def test_empty_when_nothing_paid(self, db, org, client):
        me = _user(db, org, "OrgEmployee", "No Payslips")
        _as(me)
        response = client.get("/api/v1/payroll/me/payslips")
        assert response.status_code == 200
        assert response.json() == []

    def test_exposes_no_other_employee_identifiers(self, db, org, client):
        """A self-service listing should describe only the caller."""
        me = _user(db, org, "OrgEmployee", "Private")
        _payroll(db, org, me)
        _as(me)
        row = client.get("/api/v1/payroll/me/payslips").json()[0]

        assert "user_id" not in row
        assert "org_id" not in row
        assert "file_url" not in row
