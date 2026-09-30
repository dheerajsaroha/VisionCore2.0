"""
Tests for the employee leave-balance KPI.

Two defects made the dashboard show an impossible figure:

  1. the balance query had no year filter, so every ledger year a user had been
     seeded for was summed together (a 2025 + 2026 pair doubled the figure);
  2. it summed every leave type, including life-event entitlements such as a
     180-day Maternity Leave, while the card was labelled "Annual & casual".

A real employee reported "245 leaves", which was 180 maternity + 15 paternity +
the genuine annual types, for a single ledger year.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from main import app
from app.api import deps
from app.core import rate_limit
from app.db.database import SessionLocal, get_db
from app.db.models.all_models import (
    LeaveBalance,
    LeaveType,
    Organization,
    OrganizationSubscription,
    Role,
    SubscriptionPlan,
    User,
)


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
        name=f"Leave KPI {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-LKPI-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "professional").first()
    db.add(OrganizationSubscription(
        organization_id=row.id,
        subscription_plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
    ))
    db.commit()
    return row


@pytest.fixture
def employee(db, org):
    role = db.query(Role).filter(Role.name == "OrgEmployee").first()
    user = User(
        org_id=org.id,
        role_id=role.id,
        full_name="Leave KPI Employee",
        username=f"lk-{uuid.uuid4().hex[:8]}",
        email=f"lk-{uuid.uuid4().hex[:8]}@example.com",
        employee_id=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        hashed_password="x",
        is_active=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def client(db, employee):
    with TestClient(app) as c:
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_active_user] = (
            lambda: db.query(User).filter(User.id == employee.id).first()
        )
        try:
            yield c
        finally:
            app.dependency_overrides.clear()
            rate_limit._fallback_windows.clear()


def _leave_type(db, org, code, name, gender_specific=None, max_days=30.0):
    lt = LeaveType(
        organization_id=org.id,
        code=code,
        name=name,
        max_days_per_year=max_days,
        is_active=1,
        gender_specific=gender_specific,
    )
    db.add(lt)
    db.commit()
    db.refresh(lt)
    return lt


def _balance(db, org, employee, lt, year, entitled):
    bal = LeaveBalance(
        user_id=employee.id,
        organization_id=org.id,
        leave_type_id=lt.id,
        year=year,
        entitled_days=entitled,
    )
    db.add(bal)
    db.commit()
    db.refresh(bal)
    return bal


def _stats(client):
    resp = client.get("/api/v1/dashboard/overview")
    assert resp.status_code == 200, resp.text
    return resp.json()["stats"]


class TestLeaveBalanceKpi:
    def test_sums_only_the_current_ledger_year(self, db, org, employee, client):
        """A prior year's entitlement must not be added to the current one."""
        from datetime import date

        year = date.today().year
        annual = _leave_type(db, org, "ANNUAL", "Annual Leave", max_days=18.0)
        _balance(db, org, employee, annual, year, 18.0)
        _balance(db, org, employee, annual, year - 1, 18.0)

        # 18 for this year plus 18 for last year would be 36.
        assert _stats(client)["leaveBalanceDays"] == 18.0

    def test_excludes_gender_specific_entitlements(self, db, org, employee, client):
        from datetime import date

        year = date.today().year
        annual = _leave_type(db, org, "ANNUAL2", "Annual Leave", max_days=18.0)
        maternity = _leave_type(db, org, "MATERNITY", "Maternity Leave",
                                gender_specific="female", max_days=180.0)
        _balance(db, org, employee, annual, year, 18.0)
        _balance(db, org, employee, maternity, year, 180.0)

        stats = _stats(client)
        # A 180-day life-event entitlement is not part of an annual balance.
        assert stats["leaveBalanceDays"] == 18.0
        assert stats["eventEntitlementDays"] == 180.0

    def test_a_plausible_figure_for_a_realistic_policy(self, db, org, employee, client):
        from datetime import date

        year = date.today().year
        for code, name, days in [
            ("A3", "Annual Leave", 18.0),
            ("S3", "Sick Leave", 12.0),
            ("C3", "Casual Leave", 10.0),
            ("COMP3", "Compensatory Off", 10.0),
        ]:
            lt = _leave_type(db, org, code, name, max_days=days)
            _balance(db, org, employee, lt, year, days)

        total = _stats(client)["leaveBalanceDays"]
        assert total == 50.0
        # Guards the reported symptom: a balance must never be absurd.
        assert total <= 365, f"implausible annual leave balance: {total}"

    def test_does_not_double_count_across_years(self, db, org, employee, client):
        from datetime import date

        year = date.today().year
        for offset in (0, 1, 2):
            lt = _leave_type(db, org, f"MULTI{offset}", "Annual Leave", max_days=18.0)
            _balance(db, org, employee, lt, year - offset, 18.0)

        # Three seeded years must still read as one entitlement.
        assert _stats(client)["leaveBalanceDays"] == 18.0

    def test_reports_used_days_against_the_right_year(self, db, org, employee, client):
        from datetime import date

        year = date.today().year
        annual = _leave_type(db, org, "USED", "Annual Leave", max_days=18.0)
        this_year = _balance(db, org, employee, annual, year, 18.0)
        this_year.used_days = 5.0
        stale = _balance(db, org, employee, annual, year - 1, 18.0)
        stale.used_days = 17.0
        db.commit()

        # Last year's row is 1 day left; ignoring the year filter would win here.
        assert _stats(client)["leaveBalanceDays"] == 13.0

    def test_leave_overview_lists_each_type_once(self, db, org, employee, client):
        from datetime import date

        year = date.today().year
        annual = _leave_type(db, org, "ONCE", "Annual Leave", max_days=18.0)
        _balance(db, org, employee, annual, year, 18.0)
        _balance(db, org, employee, annual, year - 1, 18.0)

        resp = client.get("/api/v1/dashboard/leave-overview")
        assert resp.status_code == 200, resp.text
        rows = resp.json()["myBalances"]
        assert [r["type"] for r in rows] == ["Annual Leave"]

    def test_leave_overview_flags_event_entitlements(self, db, org, employee, client):
        from datetime import date

        year = date.today().year
        maternity = _leave_type(db, org, "MATFLAG", "Maternity Leave",
                                gender_specific="female", max_days=180.0)
        _balance(db, org, employee, maternity, year, 180.0)

        rows = client.get("/api/v1/dashboard/leave-overview").json()["myBalances"]
        assert rows[0]["genderSpecific"] == "female"

    def test_never_negative(self, db, org, employee, client):
        from datetime import date

        year = date.today().year
        annual = _leave_type(db, org, "OVER", "Annual Leave", max_days=18.0)
        bal = _balance(db, org, employee, annual, year, 18.0)
        bal.used_days = 40.0
        db.commit()

        assert _stats(client)["leaveBalanceDays"] >= 0
