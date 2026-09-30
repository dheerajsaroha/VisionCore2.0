"""
Regression tests for fabricated dashboard data.

The "Enterprise Analytics" board and the workforce breakdown used to return a
fixed demo dataset for every tenant regardless of what had actually been
recorded: a Mon-Sun compliance table, six months of leave/hiring/payroll, a
18/32/41/5 review split, a 110->142 headcount ramp, a five-way department
split, and San Francisco / New York sites. The frontend held a byte-identical
copy as `||` fallbacks, so an organization with no data at all still saw a
fully populated dashboard.

These tests assert that an empty organization reports empty, and that real rows
are actually aggregated (rather than merely "not fabricated").
"""
from __future__ import annotations

import datetime as _dt
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from app.api import deps
from app.db.models.all_models import (
    AttendanceSession,
    Branch,
    Department,
    EmploymentRecord,
    JobPosition,
    LeaveRequest,
    LeaveType,
    Payroll,
    PerformanceCycle,
    PerformanceReview,
    Role,
    User,
)


@pytest.fixture()
def client():
    return TestClient(app)


def _fresh_org(db: Session):
    """A brand new organization with no departments, branches, or staff.

    Using a fresh org (rather than a seeded one) is what makes the
    "reports nothing" assertions meaningful.
    """
    from app.db.models.all_models import Organization

    org = Organization(
        name=f"FabX {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-FAB-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _make_user(db: Session, org, role_name: str, tag: str) -> User:
    from app.core.security import get_password_hash

    role = db.query(Role).filter(Role.name == role_name).first()
    assert role, f"missing seeded role {role_name}"
    slug = f"{tag}-{uuid.uuid4().hex[:6]}"
    user = User(
        email=f"{slug}@example.com",
        username=slug,
        employee_id=slug.upper(),
        full_name=f"Fabrication Probe {tag}",
        org_id=org.id,
        role_id=role.id,
        is_active=1,
        is_deleted=0,
        hashed_password=get_password_hash("Test-Passw0rd!"),
        # Backdated so the probe account is not itself counted as a recent
        # hire; the hiring series is asserted to be all zeros.
        created_at=_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=1100),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_leave_type(db: Session, org) -> LeaveType:
    """A leave type for the probe org (a fresh org has none)."""
    slug = uuid.uuid4().hex[:6].upper()
    lt = LeaveType(
        organization_id=org.id,
        name="Probe Annual",
        code=f"PROBE{slug[:4]}",
        is_paid=True,
        is_active=True,
    )
    db.add(lt)
    db.commit()
    db.refresh(lt)
    return lt


def _drop_probe(db: Session, org):
    """Remove the probe org and everything hanging off it.

    Order matters: child rows must go before `users`, or the FK to `users.id`
    aborts the delete. Payroll in particular was missing, and the bare
    `except Exception: db.rollback()` that used to wrap each statement turned
    that FK violation into a silent no-op -- so every run leaked a probe
    organization and its users into the development database.
    """
    from app.db.models.all_models import Organization

    failures = []

    def _drop(model, *criteria):
        try:
            db.query(model).filter(*criteria).delete(synchronize_session=False)
        except Exception as exc:  # noqa: BLE001 - report, do not hide
            failures.append(f"{model.__name__}: {type(exc).__name__}")
            db.rollback()

    uid = db.query(User.id).filter(User.org_id == org.id)
    # Rows that point at users.id must go before the users themselves.
    # PerformanceReview has three separate user FKs, and performance_cycles is
    # created by a user, so none of them can be reached through org_id alone.
    _drop(PerformanceReview, PerformanceReview.reviewee_user_id.in_(uid))
    _drop(PerformanceReview, PerformanceReview.reviewer_user_id.in_(uid))
    _drop(PerformanceCycle, PerformanceCycle.created_by_user_id.in_(uid))
    _drop(LeaveRequest, LeaveRequest.approver_user_id.in_(uid))
    _drop(Payroll, Payroll.org_id == org.id)
    _drop(AttendanceSession, AttendanceSession.org_id == org.id)
    _drop(EmploymentRecord, EmploymentRecord.org_id == org.id)
    # Org-scoped tables that do not reference users.
    _drop(LeaveRequest, LeaveRequest.organization_id == org.id)
    _drop(LeaveType, LeaveType.organization_id == org.id)
    _drop(PerformanceReview, PerformanceReview.organization_id == org.id)
    _drop(PerformanceCycle, PerformanceCycle.organization_id == org.id)
    _drop(JobPosition, JobPosition.org_id == org.id)
    _drop(Branch, Branch.org_id == org.id)
    _drop(Department, Department.org_id == org.id)
    _drop(User, User.org_id == org.id)
    _drop(Organization, Organization.id == org.id)
    db.commit()
    assert not failures, f"probe cleanup failed to delete: {failures}"


class TestAnalyticsHasNoDemoDataset:
    """The five analytics series must reflect tenant rows, not constants."""

    def test_empty_org_reports_empty_rather_than_demo_numbers(self, client, db):
        """A tenant with no records must not receive the canned dataset."""
        org = _fresh_org(db)
        user = _make_user(db, org, "OrgAdmin", "empty")

        app.dependency_overrides[deps.get_current_active_user] = lambda: user
        try:
            r = client.get("/api/v1/dashboard/analytics")
            assert r.status_code == 200
            d = r.json()

            # No series may carry the historical demo magnitudes.
            blob = str(d)
            for demo_value in ("Engineering", "San Francisco", "Tech Hub East"):
                assert demo_value not in blob

            # With no rows for the window, every tab reports "not populated".
            for key, populated in d["hasData"].items():
                assert populated is False, (
                    f"{key} claims data for an organization with no rows: "
                    f"{d.get(key)}"
                )

            # Compliance still returns one row per weekday, but all zeros.
            compliance = d["attendanceCompliance"]
            assert len(compliance) == 7
            for row in compliance:
                assert row["onTime"] == 0
                assert row["late"] == 0
                assert row["absent"] == 0

            # Leave rows are present but empty, not invented.
            for row in d["leaveUtilization"]:
                assert row["total"] == 0
                assert row["byType"] == {}

            # Performance buckets must be genuine counts, including real zeros.
            perf = d["performanceDistribution"]
            assert len(perf) == 4
            for bucket in perf:
                assert bucket["count"] == 0, (
                    f"perf bucket {bucket['rating']} invented {bucket['count']}"
                )

            # Payroll: six real periods, all zero, never the 142000 demo value.
            assert len(d["payrollCosts"]) == 6
            for row in d["payrollCosts"]:
                assert row["base"] == 0.0
                assert row["total"] == 0.0

            assert d["openPositions"] == 0
        finally:
            app.dependency_overrides.pop(deps.get_current_active_user, None)
            _drop_probe(db, org)

    def test_real_rows_are_aggregated_not_just_unfabricated(self, client, db):
        """Real tenant rows must actually move the numbers."""
        org = _fresh_org(db)
        user = _make_user(db, org, "OrgAdmin", "agg")

        leave_type = _make_leave_type(db, org)
        session_row = None
        review = None
        payroll = None
        if leave_type:
            session_row = AttendanceSession(
                org_id=org.id,
                user_id=user.id,
                work_date=_dt.date.today(),
                status="LATE",
                check_in=_dt.datetime.now(_dt.timezone.utc),
            )
            now = _dt.datetime.now(_dt.timezone.utc)
            cycle = PerformanceCycle(
                organization_id=org.id,
                name="Probe Cycle",
                cycle_type="annual",
                start_date=_dt.date.today() - _dt.timedelta(days=30),
                end_date=_dt.date.today(),
                status="completed",
                created_by_user_id=user.id,
                created_at=now,
                updated_at=now,
            )
            db.add(cycle)
            db.flush()
            review = PerformanceReview(
                organization_id=org.id,
                cycle_id=cycle.id,
                reviewee_user_id=user.id,
                reviewer_user_id=user.id,
                review_type="annual",
                status="completed",
                overall_score=4.8,
                created_at=now,
                updated_at=now,
            )
            payroll = Payroll(
                user_id=user.id,
                org_id=org.id,
                month=_dt.date.today().month,
                year=_dt.date.today().year,
                base_salary=1000,
                deductions=0,
                reimbursements_total=0,
                total_salary=1000,
                status="draft",
                currency="USD",
                generated_at=_dt.datetime.now(_dt.timezone.utc),
            )
            db.add_all([session_row, review, payroll])
            db.commit()

        app.dependency_overrides[deps.get_current_active_user] = lambda: user
        try:
            d = client.get("/api/v1/dashboard/analytics").json()

            if session_row is not None:
                assert d["hasData"]["attendanceCompliance"] is True
                today_bucket = next(
                    r for r in d["attendanceCompliance"]
                    if r["day"] == _dt.date.today().strftime("%a")
                )
                assert today_bucket["late"] == 1, (
                    "a real LATE session did not reach the compliance series"
                )

                # A real zero must stay zero. The old `count or 14` style
                # expression substituted an invented number here.
                assert d["performanceDistribution"][0]["count"] == 1, (
                    "the 4.5+ review did not land in the exceeds bucket"
                )
                assert d["performanceDistribution"][1]["count"] == 0, (
                    "an empty perf bucket was filled with an invented count"
                )

                month_row = next(
                    r for r in d["payrollCosts"]
                    if r["month"] == _dt.date.today().strftime("%b")
                )
                assert month_row["total"] == 1000.0
        finally:
            app.dependency_overrides.pop(deps.get_current_active_user, None)
            _drop_probe(db, org)

    def test_rejected_leave_is_not_counted_as_consumed(self, client, db):
        """Rejected/cancelled requests must not inflate leave utilization."""
        org = _fresh_org(db)
        user = _make_user(db, org, "OrgAdmin", "rej")
        leave_type = _make_leave_type(db, org)

        row = LeaveRequest(
            organization_id=org.id,
            user_id=user.id,
            leave_type_id=leave_type.id,
            start_date=_dt.date.today(),
            end_date=_dt.date.today(),
            total_days=5,
            status="rejected",
        )
        db.add(row)
        db.commit()

        app.dependency_overrides[deps.get_current_active_user] = lambda: user
        try:
            d = client.get("/api/v1/dashboard/analytics").json()
            assert d["hasData"]["leaveUtilization"] is False, (
                "a rejected leave request was counted as consumed leave"
            )
        finally:
            app.dependency_overrides.pop(deps.get_current_active_user, None)
            _drop_probe(db, org)


class TestWorkforceBreakdownHasNoDemoDataset:
    def test_no_synthetic_departments_or_locations(self, client, db):
        org = _fresh_org(db)
        user = _make_user(db, org, "OrgAdmin", "wf")

        app.dependency_overrides[deps.get_current_active_user] = lambda: user
        try:
            r = client.get("/api/v1/dashboard/workforce-breakdown")
            assert r.status_code == 200
            d = r.json()
            blob = str(d)

            for invented in ("San Francisco", "Tech Hub East", "Remote Global"):
                assert invented not in blob, (
                    f"workforce breakdown still invents '{invented}'"
                )

            # The synthetic headcount ramp overrode the real measurement:
            # every month was passed through max(real, <invented ramp>).
            trends = d.get("headcountTrends") or []
            assert len(trends) == 6
            for row in trends:
                assert row["headcount"] >= 0
                assert row["active"] <= row["headcount"], (
                    "active headcount exceeded total headcount for a month"
                )

            # positionsCount used `count(...) or 12`.
            positions = (d.get("structure") or {}).get("positionsCount")
            real_positions = (
                db.query(JobPosition)
                .filter(JobPosition.org_id == org.id, JobPosition.is_deleted == 0)
                .count()
            )
            assert positions == real_positions, (
                f"positionsCount {positions} != real count {real_positions}"
            )
        finally:
            app.dependency_overrides.pop(deps.get_current_active_user, None)
            _drop_probe(db, org)

    def test_location_counts_are_not_floored_to_one(self, client, db):
        """A branch with no staff must report 0, not the `or 1` floor."""
        org = _fresh_org(db)
        tag = uuid.uuid4().hex[:6]
        user = _make_user(db, org, "OrgAdmin", "loc")
        branch = Branch(
            org_id=org.id,
            name=f"Empty Branch {tag}",
            code=f"EB{tag[:5]}",
            city="",
            country="",
            is_deleted=0,
        )
        db.add(branch)
        db.commit()

        app.dependency_overrides[deps.get_current_active_user] = lambda: user
        try:
            d = client.get("/api/v1/dashboard/workforce-breakdown").json()
            match = next(
                (loc for loc in (d.get("locationDistribution") or [])
                 if loc["name"] == f"Empty Branch {tag}"),
                None,
            )
            assert match is not None, "the new branch should appear in the breakdown"
            assert match["count"] == 0, (
                f"an unstaffed branch reported {match['count']} staff "
                "(the old `count or 1` floor)"
            )
            assert match["city"] == "" and match["country"] == "", (
                "city/country should stay empty rather than defaulting to HQ/US"
            )
        finally:
            app.dependency_overrides.pop(deps.get_current_active_user, None)
            _drop_probe(db, org)
