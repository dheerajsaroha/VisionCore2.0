"""
Tests for loss-of-pay (LOP) calculation in the payroll engine.

Loss of pay is a legal deduction, so these cover the behaviour the engine
previously stubbed out: unpaid leave used to be hard-coded to zero, which made
every payslip display a compliant-looking "0 unpaid day(s)" row while
understating the deduction.

The denominator matters as much as the numerator: the engine divided by
calendar days, so March (22 working days out of 31) lost about a quarter of its
worth of deduction.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.db.database import SessionLocal
from app.db.models.all_models import (
    AttendanceLog,
    LeaveRequest,
    LeaveType,
    Organization,
    Role,
    User,
)
from app.services import payroll_engine as engine


MONTH, YEAR = 3, 2026


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
        name=f"LOP Org {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-LOP-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def employee(db, org):
    role = db.query(Role).filter(Role.name == "Employee").first()
    assert role is not None, "seeded Employee role is required"
    user = User(
        org_id=org.id,
        role_id=role.id,
        full_name="LOP Employee",
        username=f"lop-{uuid.uuid4().hex[:8]}",
        email=f"lop-{uuid.uuid4().hex[:8]}@example.com",
        employee_id=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        hashed_password="x",
        is_active=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _leave_type(db, org, *, is_paid: bool, code: str) -> LeaveType:
    row = LeaveType(
        organization_id=org.id,
        name="Unpaid" if not is_paid else "Paid",
        code=code,
        is_paid=is_paid,
        max_days_per_year=30,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _request(db, org, user, leave_type, start, end, status="approved", is_half_day=False):
    row = LeaveRequest(
        organization_id=org.id,
        user_id=user.id,
        leave_type_id=leave_type.id,
        start_date=datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
        end_date=datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc),
        total_days=float((end - start).days + 1),
        is_half_day=is_half_day,
        status=status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class TestUnpaidLeaveDays:
    def test_no_requests_means_no_loss(self, db, org, employee):
        assert engine._unpaid_leave_days(db, employee.id, org.id, MONTH, YEAR) == Decimal("0.00")

    def test_approved_unpaid_leave_is_counted(self, db, org, employee):
        """The core blueprint requirement: unpaid leave must reduce pay."""
        unpaid = _leave_type(db, org, is_paid=False, code=f"UNPAID{uuid.uuid4().hex[:5].upper()}")
        # Mon 2nd - Fri 6th March 2026 is five weekdays.
        _request(db, org, employee, unpaid, date(2026, 3, 2), date(2026, 3, 6))

        days = engine._unpaid_leave_days(db, employee.id, org.id, MONTH, YEAR)
        assert days == Decimal("5.00")

    def test_paid_leave_is_not_loss_of_pay(self, db, org, employee):
        paid = _leave_type(db, org, is_paid=True, code=f"PAID{uuid.uuid4().hex[:5].upper()}")
        _request(db, org, employee, paid, date(2026, 3, 2), date(2026, 3, 6))

        assert engine._unpaid_leave_days(db, employee.id, org.id, MONTH, YEAR) == Decimal("0.00")

    @pytest.mark.parametrize("status", ["pending", "rejected", "cancelled"])
    def test_only_approved_leave_counts(self, db, org, employee, status):
        unpaid = _leave_type(db, org, is_paid=False, code=f"UNP{uuid.uuid4().hex[:5].upper()}")
        _request(db, org, employee, unpaid, date(2026, 3, 2), date(2026, 3, 6), status=status)

        assert engine._unpaid_leave_days(db, employee.id, org.id, MONTH, YEAR) == Decimal("0.00")

    def test_weekends_are_excluded(self, db, org, employee):
        unpaid = _leave_type(db, org, is_paid=False, code=f"UNP{uuid.uuid4().hex[:5].upper()}")
        # 7th-8th March 2026 is a Saturday and Sunday.
        _request(db, org, employee, unpaid, date(2026, 3, 7), date(2026, 3, 8))

        assert engine._unpaid_leave_days(db, employee.id, org.id, MONTH, YEAR) == Decimal("0.00")

    def test_month_boundary_contributes_only_its_share(self, db, org, employee):
        """A request spanning February and March deducts only the March days."""
        unpaid = _leave_type(db, org, is_paid=False, code=f"UNP{uuid.uuid4().hex[:5].upper()}")
        # 27 Feb 2026 is a Friday and 2 Mar a Monday, so the March portion is
        # 1 Mar (Sunday) and 2 Mar (Monday) — one weekday, not two days.
        _request(db, org, employee, unpaid, date(2026, 2, 27), date(2026, 3, 2))

        assert engine._unpaid_leave_days(db, employee.id, org.id, MONTH, YEAR) == Decimal("1.00")

    def test_leave_outside_the_month_is_ignored(self, db, org, employee):
        unpaid = _leave_type(db, org, is_paid=False, code=f"UNP{uuid.uuid4().hex[:5].upper()}")
        _request(db, org, employee, unpaid, date(2026, 4, 1), date(2026, 4, 3))

        assert engine._unpaid_leave_days(db, employee.id, org.id, MONTH, YEAR) == Decimal("0.00")

    def test_half_day_request_counts_as_half(self, db, org, employee):
        unpaid = _leave_type(db, org, is_paid=False, code=f"UNP{uuid.uuid4().hex[:5].upper()}")
        _request(
            db, org, employee, unpaid,
            date(2026, 3, 2), date(2026, 3, 2), is_half_day=True,
        )

        assert engine._unpaid_leave_days(db, employee.id, org.id, MONTH, YEAR) == Decimal("0.50")

    def test_another_employees_leave_is_not_counted(self, db, org, employee):
        other = User(
            org_id=org.id,
            role_id=employee.role_id,
            full_name="Other",
            username=f"lop2-{uuid.uuid4().hex[:8]}",
            email=f"lop2-{uuid.uuid4().hex[:8]}@example.com",
            employee_id=f"EMP-{uuid.uuid4().hex[:6].upper()}",
            hashed_password="x",
            is_active=1,
        )
        db.add(other)
        db.commit()

        unpaid = _leave_type(db, org, is_paid=False, code=f"UNP{uuid.uuid4().hex[:5].upper()}")
        _request(db, org, other, unpaid, date(2026, 3, 2), date(2026, 3, 6))

        assert engine._unpaid_leave_days(db, employee.id, org.id, MONTH, YEAR) == Decimal("0.00")

    def test_multiple_requests_accumulate(self, db, org, employee):
        unpaid = _leave_type(db, org, is_paid=False, code=f"UNP{uuid.uuid4().hex[:5].upper()}")
        _request(db, org, employee, unpaid, date(2026, 3, 2), date(2026, 3, 3))   # 2 days
        _request(db, org, employee, unpaid, date(2026, 3, 9), date(2026, 3, 10))  # 2 days

        assert engine._unpaid_leave_days(db, employee.id, org.id, MONTH, YEAR) == Decimal("4.00")


class TestWorkingDayDenominator:
    def test_denominator_counts_working_days_not_calendar_days(self):
        """March 2026 has 31 calendar days but only 22 working days."""
        working = engine._working_days_in_month(None, YEAR, MONTH)
        _, calendar_days = __import__("calendar").monthrange(YEAR, MONTH)

        assert working == 22
        assert calendar_days == 31
        assert working < calendar_days

    def test_sanitised_weekends_only(self):
        # August 2026: 31 days, 21 weekdays.
        assert engine._working_days_in_month(None, 2026, 8) == 21


class TestLateMarkExclusion:
    def test_soft_deleted_late_marks_are_not_deducted(self, db, org, employee):
        """
        A corrected or voided late mark must stop deducting pay.

        The query previously omitted `is_deleted == 0`, so reversing a late mark
        left the deduction in place for every later payroll run.
        """
        day = datetime(2026, 3, 10, 9, 30, tzinfo=timezone.utc)
        for is_deleted in (0, 1):
            db.add(AttendanceLog(
                user_id=employee.id,
                check_in=day,
                check_out=day.replace(hour=18),
                status="late",
                source="manual",
                is_deleted=is_deleted,
            ))
        db.commit()

        late_count, _ = engine._attendance_data(db, employee.id, org.id, MONTH, YEAR)
        assert late_count == 1, "only the live late mark should be counted"

    def test_live_late_marks_still_count(self, db, org, employee):
        day = datetime(2026, 3, 11, 9, 30, tzinfo=timezone.utc)
        db.add(AttendanceLog(
            user_id=employee.id,
            check_in=day,
            check_out=day.replace(hour=18),
            status="late",
            source="manual",
            is_deleted=0,
        ))
        db.commit()

        late_count, _ = engine._attendance_data(db, employee.id, org.id, MONTH, YEAR)
        assert late_count == 1
