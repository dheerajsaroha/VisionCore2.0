"""
Tests for gender-scoped leave entitlement.

`leave_types.gender_specific` existed and was seeded correctly ('female' on
maternity, 'male' on paternity) but nothing read it, and `User` had no gender to
read against. `initialize_all_balances_for_user` therefore granted every active
leave type to every employee, so a male employee held a 180-day Maternity Leave
balance alongside his Paternity Leave.

Two rules are enforced here:

  - a gender-scoped type is never pre-seeded as an annual balance, because it is
    a life-event entitlement, not an accrued quota;
  - an explicitly requested life-event entitlement is still permitted for an
    employee it applies to, and refused for one it does not.
"""
import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from main import app
from app.api import deps
from app.core import rate_limit
from app.crud import crud_leave
from app.crud.crud_leave import gender_restriction_error, leave_type_applies_to_user
from app.db.database import SessionLocal, get_db
from app.db.models.all_models import (
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
        name=f"Gender Leave {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-GL-{uuid.uuid4().hex[:8].upper()}",
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


def _user(db, org, gender=None):
    role = db.query(Role).filter(Role.name == "OrgEmployee").first()
    user = User(
        org_id=org.id,
        role_id=role.id,
        full_name=f"Gender Emp {gender or 'none'}",
        username=f"gl-{uuid.uuid4().hex[:8]}",
        email=f"gl-{uuid.uuid4().hex[:8]}@example.com",
        employee_id=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        hashed_password="x",
        is_active=1,
        gender=gender,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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


class TestApplicabilityPredicate:
    def test_gender_scoped_type_never_counts_as_an_annual_entitlement(self, db, org):
        maternity = _leave_type(db, org, "MAT1", "Maternity Leave",
                                gender_specific="female", max_days=180.0)
        female = _user(db, org, "female")
        male = _user(db, org, "male")
        unknown = _user(db, org, None)

        # A life-event entitlement is granted on a qualifying event, never
        # pre-seeded, so gender must not change the answer here.
        for user in (female, male, unknown):
            assert leave_type_applies_to_user(maternity, user) is False

    def test_ordinary_types_always_apply(self, db, org):
        annual = _leave_type(db, org, "ANN1", "Annual Leave", max_days=18.0)
        for gender in ("male", "female", None):
            assert leave_type_applies_to_user(annual, _user(db, org, gender)) is True


class TestRequestValidation:
    def test_matching_gender_is_permitted(self, db, org):
        maternity = _leave_type(db, org, "MAT2", "Maternity Leave",
                                gender_specific="female", max_days=180.0)
        female = _user(db, org, "female")
        assert gender_restriction_error(maternity, female) is None

    def test_mismatched_gender_is_refused(self, db, org):
        maternity = _leave_type(db, org, "MAT3", "Maternity Leave",
                                gender_specific="female", max_days=180.0)
        male = _user(db, org, "male")
        error = gender_restriction_error(maternity, male)
        assert error is not None
        assert "female" in error

    def test_unstated_gender_is_not_blocked(self, db, org):
        """Do not refuse a statutory entitlement on a guess."""
        maternity = _leave_type(db, org, "MAT4", "Maternity Leave",
                                gender_specific="female", max_days=180.0)
        unknown = _user(db, org, None)
        assert gender_restriction_error(maternity, unknown) is None

    def test_non_scoped_types_are_never_refused(self, db, org):
        sick = _leave_type(db, org, "SICK1", "Sick Leave", max_days=12.0)
        assert gender_restriction_error(sick, _user(db, org, "male")) is None


class TestSeeding:
    def test_seeder_skips_life_event_entitlements(self, db, org):
        annual = _leave_type(db, org, "ANN2", "Annual Leave", max_days=18.0)
        _leave_type(db, org, "MAT5", "Maternity Leave",
                    gender_specific="female", max_days=180.0)
        _leave_type(db, org, "PAT5", "Paternity Leave",
                    gender_specific="male", max_days=15.0)
        user = _user(db, org, "male")

        seeded = crud_leave.crud_leave_balance.initialize_all_balances_for_user(
            db, user.id, org.id
        )
        seeded_types = {b.leave_type_id for b in seeded}
        assert annual.id in seeded_types
        assert len(seeded) == 1, "only the annual type should be pre-seeded"

    def test_a_male_employee_ends_with_no_maternity_balance(self, db, org):
        """The reported symptom: a male employee holding a maternity balance."""
        _leave_type(db, org, "ANN3", "Annual Leave", max_days=18.0)
        maternity = _leave_type(db, org, "MAT6", "Maternity Leave",
                                gender_specific="female", max_days=180.0)
        _leave_type(db, org, "PAT6", "Paternity Leave",
                    gender_specific="male", max_days=15.0)
        male = _user(db, org, "male")

        crud_leave.crud_leave_balance.initialize_all_balances_for_user(db, male.id, org.id)

        balances = crud_leave.crud_leave_balance.get_user_balances(
            db, male.id, date.today().year, org.id
        )
        assert all(b.leave_type_id != maternity.id for b in balances)
        assert all(b.entitled_days <= 30 for b in balances), \
            "a life-event entitlement leaked into an annual balance"

    def test_repeated_seeding_does_not_reintroduce_them(self, db, org):
        _leave_type(db, org, "ANN4", "Annual Leave", max_days=18.0)
        _leave_type(db, org, "MAT7", "Maternity Leave",
                    gender_specific="female", max_days=180.0)
        user = _user(db, org, "female")

        for _ in range(3):
            crud_leave.crud_leave_balance.initialize_all_balances_for_user(db, user.id, org.id)

        balances = crud_leave.crud_leave_balance.get_user_balances(
            db, user.id, date.today().year, org.id
        )
        assert len(balances) == 1


class TestGenderColumn:
    def test_user_gender_persists(self, db, org):
        user = _user(db, org, "female")
        db.expire_all()
        assert db.query(User).filter(User.id == user.id).first().gender == "female"

    def test_gender_is_optional(self, db, org):
        user = _user(db, org, None)
        assert user.gender is None
