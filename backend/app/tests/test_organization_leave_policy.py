"""
Tests for organization-defined leave policy.

Leave types were a hardcoded six-item list injected into every tenant on first
access, and `LeavePolicy` was a dead table — created with the right columns,
imported into the service, then never read. Every organization therefore ran
against the same rules regardless of sector or region.

These cover the two things the organization now owns: the starting set of leave
types, and the policy those types are administered under.
"""
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from main import app
from app.api import deps
from app.core import rate_limit
from app.crud import crud_leave
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
from app.services import leave_policy_service, leave_template_service


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
        name=f"Leave Policy {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-LPOL-{uuid.uuid4().hex[:8].upper()}",
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


def _user(db, org, role="OrgEmployee"):
    r = db.query(Role).filter(Role.name == role).first()
    u = User(
        org_id=org.id,
        role_id=r.id,
        full_name="Leave Policy User",
        username=f"lp-{uuid.uuid4().hex[:8]}",
        email=f"lp-{uuid.uuid4().hex[:8]}@example.com",
        employee_id=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        hashed_password="x",
        is_active=1,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        app.dependency_overrides[get_db] = lambda: db
        try:
            yield c
        finally:
            app.dependency_overrides.clear()
            rate_limit._fallback_windows.clear()


def _as(db, user):
    app.dependency_overrides[deps.get_current_active_user] = (
        lambda: db.query(User).filter(User.id == user.id).first()
    )


def _leave_type(db, org, code, name, per_year=18.0, per_request=6.0):
    lt = LeaveType(
        organization_id=org.id, code=code, name=name,
        max_days_per_year=per_year, max_days_per_request=per_request, is_active=1,
    )
    db.add(lt)
    db.commit()
    db.refresh(lt)
    return lt


class TestTemplateCatalogue:
    def test_seeded_idempotently(self, db):
        leave_template_service.seed_leave_templates(db)
        first = leave_template_service.seed_leave_templates(db)
        assert first == 0, "re-seeding must not duplicate templates"

    def test_catalogue_covers_multiple_regions(self, db):
        leave_template_service.seed_leave_templates(db)
        regions = {t.region for t in leave_template_service.list_templates(db)}
        assert {"IN", "UK", "US"} <= regions

    def test_every_template_has_items(self, db):
        leave_template_service.seed_leave_templates(db)
        for t in leave_template_service.list_templates(db):
            assert t.items, f"{t.code} has no leave types"

    def test_exactly_one_default(self, db):
        leave_template_service.seed_leave_templates(db)
        defaults = [t for t in leave_template_service.list_templates(db) if t.is_default]
        assert len(defaults) == 1


class TestApplyingTemplate:
    def test_creates_the_templates_types(self, db, org):
        leave_template_service.seed_leave_templates(db)
        result = leave_template_service.apply_template(db, org.id, "MINIMAL")

        assert result["created"] == ["UNPAID"]
        types = crud_leave.crud_leave_type.get_all_for_org(db, org.id)
        assert [t.code for t in types] == ["UNPAID"]

    def test_organization_gets_only_what_it_chooses(self, db, org):
        """The original defect: every org received the same six types."""
        leave_template_service.seed_leave_templates(db)
        leave_template_service.apply_template(db, org.id, "UK_STANDARD")

        codes = {t.code for t in crud_leave.crud_leave_type.get_all_for_org(db, org.id)}
        assert codes == {"HOLIDAY", "SICK", "FAMILY"}
        # Notably not the maternity type the hardcoded seed forced on everyone.
        assert "MATERNITY" not in codes

    def test_different_organizations_get_different_sets(self, db, org):
        other = Organization(
            name=f"Leave Policy Other {uuid.uuid4().hex[:6]}",
            legal_id=f"TEST-LPOL-{uuid.uuid4().hex[:8].upper()}",
        )
        db.add(other)
        db.commit()
        db.refresh(other)
        leave_template_service.seed_leave_templates(db)

        leave_template_service.apply_template(db, org.id, "IN_STATUTORY")
        leave_template_service.apply_template(db, other.id, "TECH_EXEMPT")

        mine = {t.code for t in crud_leave.crud_leave_type.get_all_for_org(db, org.id)}
        theirs = {t.code for t in crud_leave.crud_leave_type.get_all_for_org(db, other.id)}
        assert mine != theirs
        assert "EL" in mine and "PTO" not in mine
        assert "PTO" in theirs and "EL" not in theirs

    def test_is_idempotent(self, db, org):
        leave_template_service.seed_leave_templates(db)
        leave_template_service.apply_template(db, org.id, "UK_STANDARD")
        before = len(crud_leave.crud_leave_type.get_all_for_org(db, org.id))
        result = leave_template_service.apply_template(db, org.id, "UK_STANDARD")
        assert result["created"] == []
        assert len(crud_leave.crud_leave_type.get_all_for_org(db, org.id)) == before

    def test_never_deletes_existing_types(self, db, org):
        leave_template_service.seed_leave_templates(db)
        existing = _leave_type(db, org, "CUSTOM", "Bereavement Leave", per_year=5.0)
        leave_template_service.apply_template(db, org.id, "UK_STANDARD")
        assert db.query(LeaveType).filter(LeaveType.id == existing.id).first() is not None

    def test_replace_deactivates_types_outside_the_template(self, db, org):
        leave_template_service.seed_leave_templates(db)
        stale = _leave_type(db, org, "OLD", "Old Policy Type")
        leave_template_service.apply_template(db, org.id, "UK_STANDARD")
        result = leave_template_service.apply_template(db, org.id, "UK_STANDARD", replace=True)

        assert "OLD" in result["deactivated"]
        db.refresh(stale)
        assert stale.is_active == 0

    def test_unknown_template_is_rejected(self, db, org):
        with pytest.raises(ValueError):
            leave_template_service.apply_template(db, org.id, "NOPE")


class TestNewOrgStartsEmpty:
    def test_no_types_are_injected(self, db, org, client):
        user = _user(db, org)
        _as(db, user)
        resp = client.get("/api/v1/leave/types")
        assert resp.status_code == 200
        assert resp.json() == [], "a new tenant must not be force-seeded a leave set"

    def test_balances_are_empty_until_types_are_configured(self, db, org, client):
        user = _user(db, org)
        _as(db, user)
        assert client.get("/api/v1/leave/balance").json() == []


class TestPolicyDefaults:
    def test_defaults_are_permissive(self, db, org):
        p = leave_policy_service.get_policy(db, org.id)
        assert p["is_default"] is True
        assert p["allow_negative_balance"] is True
        assert p["auto_approve_after_days"] is None

    def test_policy_is_scoped_to_its_year(self, db, org):
        """This year's rules must not silently apply next year."""
        leave_policy_service.save_policy(
            db, org.id, year=2026, accrual_type="monthly_accrual", allow_negative_balance=False
        )
        assert leave_policy_service.get_policy(db, org.id, 2026)["allow_negative_balance"] is False
        assert leave_policy_service.get_policy(db, org.id, 2027)["is_default"] is True

    def test_saving_is_idempotent(self, db, org):
        leave_policy_service.save_policy(db, org.id, year=2026, name="First")
        leave_policy_service.save_policy(db, org.id, year=2026, name="Second")
        rows = [
            r for r in db.query(type(leave_policy_service.get_policy(db, org.id)) and None)
        ] if False else None
        from app.db.models.all_models import LeavePolicy
        assert db.query(LeavePolicy).filter(LeavePolicy.organization_id == org.id).count() == 1
        assert leave_policy_service.get_policy(db, org.id, 2026)["name"] == "Second"

    def test_rejects_unknown_accrual_type(self, db, org):
        with pytest.raises(ValueError):
            leave_policy_service.save_policy(db, org.id, accrual_type="whenever")

    def test_rejects_unknown_config_keys(self, db, org):
        with pytest.raises(ValueError):
            leave_policy_service.save_policy(db, org.id, policy_config={"not_a_real_key": 1})


class TestAccrual:
    def test_annual_grant_awards_the_whole_year(self, db, org):
        leave_template_service.seed_leave_templates(db)
        leave_template_service.apply_template(db, org.id, "IN_STATUTORY")
        lt = crud_leave.crud_leave_type.get_by_code(db, org.id, "EL")
        p = leave_policy_service.get_policy(db, org.id)
        assert leave_policy_service.entitlement_for(lt, p, month=3) == 18.0

    def test_monthly_accrual_awards_a_fraction(self, db, org):
        leave_template_service.seed_leave_templates(db)
        leave_template_service.apply_template(db, org.id, "IN_STATUTORY")
        lt = crud_leave.crud_leave_type.get_by_code(db, org.id, "EL")
        leave_policy_service.save_policy(db, org.id, accrual_type="monthly_accrual")

        p = leave_policy_service.get_policy(db, org.id)
        assert leave_policy_service.entitlement_for(lt, p, month=6) == 9.0
        assert leave_policy_service.entitlement_for(lt, p, month=12) == 18.0

    def test_seeder_uses_the_policy(self, db, org):
        leave_template_service.seed_leave_templates(db)
        leave_template_service.apply_template(db, org.id, "IN_STATUTORY")
        leave_policy_service.save_policy(db, org.id, accrual_type="monthly_accrual")
        user = _user(db, org)

        crud_leave.crud_leave_balance.initialize_all_balances_for_user(db, user.id, org.id)
        bal = crud_leave.crud_leave_balance.get_user_balance(
            db, user.id,
            crud_leave.crud_leave_type.get_by_code(db, org.id, "EL").id,
            date.today().year,
        )
        # September: 18 * 9/12.
        assert 13 < bal.entitled_days <= 14


class TestRequestEvaluation:
    def test_negative_balance_refused_when_policy_forbids_it(self, db, org):
        lt = _leave_type(db, org, "EL", "Earned", per_year=18.0, per_request=30.0)
        leave_policy_service.save_policy(db, org.id, allow_negative_balance=False)
        v = leave_policy_service.evaluate_request(db, org.id, 1, lt, 10.0, 2.0)
        assert v["allowed"] is False
        assert any("negative balance" in r for r in v["reasons"])

    def test_negative_balance_permitted_by_default(self, db, org):
        lt = _leave_type(db, org, "EL", "Earned", per_year=18.0, per_request=30.0)
        v = leave_policy_service.evaluate_request(db, org.id, 1, lt, 10.0, 2.0)
        assert v["allowed"] is True

    def test_per_request_cap_enforced(self, db, org):
        lt = _leave_type(db, org, "EL", "Earned", per_year=18.0, per_request=5.0)
        v = leave_policy_service.evaluate_request(db, org.id, 1, lt, 7.0, 20.0)
        assert v["allowed"] is False
        assert any("single request" in r for r in v["reasons"])

    def test_unlimited_accrual_waives_the_balance_cap(self, db, org):
        """Unlimited accrual means no balance to exhaust.

        It does not waive a per-request cap: that is a separate, deliberate
        per-type setting, and the templates express "no cap" as a NULL
        per-request limit rather than through the policy.
        """
        lt = _leave_type(db, org, "PTO", "Paid Time Off", per_year=0.0, per_request=30.0)
        leave_policy_service.save_policy(db, org.id, accrual_type="unlimited")
        v = leave_policy_service.evaluate_request(db, org.id, 1, lt, 20.0, 0.0)
        assert v["allowed"] is True

    def test_unlimited_still_respects_an_explicit_per_request_cap(self, db, org):
        lt = _leave_type(db, org, "PTO", "Paid Time Off", per_year=0.0, per_request=5.0)
        leave_policy_service.save_policy(db, org.id, accrual_type="unlimited")
        v = leave_policy_service.evaluate_request(db, org.id, 1, lt, 20.0, 0.0)
        assert v["allowed"] is False
        assert any("single request" in r for r in v["reasons"])

    def test_null_per_request_cap_does_not_crash(self, db, org):
        """An unlimited type has no per-request cap; the old check raised TypeError."""
        lt = _leave_type(db, org, "UNL", "Unlimited", per_year=0.0)
        lt.max_days_per_request = None
        db.commit()
        v = leave_policy_service.evaluate_request(db, org.id, 1, lt, 30.0, 30.0)
        assert v["allowed"] is True

    def test_auto_approve_within_threshold(self, db, org):
        lt = _leave_type(db, org, "EL", "Earned", per_year=18.0, per_request=10.0)
        leave_policy_service.save_policy(db, org.id, auto_approve_after_days=2)
        assert leave_policy_service.evaluate_request(db, org.id, 1, lt, 1.0, 5.0)["auto_approve"] is True

    def test_no_auto_approve_above_threshold(self, db, org):
        lt = _leave_type(db, org, "EL", "Earned", per_year=18.0, per_request=10.0)
        leave_policy_service.save_policy(db, org.id, auto_approve_after_days=2)
        assert leave_policy_service.evaluate_request(db, org.id, 1, lt, 4.0, 5.0)["auto_approve"] is False

    def test_a_refused_request_never_auto_approves(self, db, org):
        lt = _leave_type(db, org, "EL", "Earned", per_year=18.0, per_request=10.0)
        leave_policy_service.save_policy(
            db, org.id, auto_approve_after_days=5, allow_negative_balance=False
        )
        v = leave_policy_service.evaluate_request(db, org.id, 1, lt, 5.0, 1.0)
        assert v["allowed"] is False
        assert v["auto_approve"] is False

    def test_zero_days_refused(self, db, org):
        lt = _leave_type(db, org, "EL", "Earned")
        v = leave_policy_service.evaluate_request(db, org.id, 1, lt, 0.0, 5.0)
        assert v["allowed"] is False


class TestPolicyApi:
    def test_get_returns_defaults(self, db, org, client):
        user = _user(db, org, "OrgHR")
        _as(db, user)
        resp = client.get("/api/v1/leave/policy")
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_default"] is True
        assert "available_accrual_types" in body

    def test_hr_can_save_policy(self, db, org, client):
        user = _user(db, org, "OrgHR")
        _as(db, user)
        resp = client.put("/api/v1/leave/policy", json={
            "name": "Studio policy",
            "accrual_type": "monthly_accrual",
            "allow_negative_balance": False,
            "auto_approve_after_days": 1,
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["accrual_type"] == "monthly_accrual"

    def test_invalid_accrual_type_is_a_400(self, db, org, client):
        user = _user(db, org, "OrgHR")
        _as(db, user)
        assert client.put("/api/v1/leave/policy", json={"accrual_type": "nope"}).status_code == 400

    def test_employee_cannot_change_policy(self, db, org, client):
        user = _user(db, org, "OrgEmployee")
        _as(db, user)
        assert client.put("/api/v1/leave/policy", json={"name": "mine"}).status_code == 403

    def test_policy_does_not_leak_across_tenants(self, db, org, client):
        other = Organization(
            name=f"Leave Policy Other {uuid.uuid4().hex[:6]}",
            legal_id=f"TEST-LPOL-{uuid.uuid4().hex[{8}].upper()}" if False else f"TEST-LPOL-{uuid.uuid4().hex[:8].upper()}",
        )
        db.add(other)
        db.commit()
        db.refresh(other)

        hr = _user(db, org, "OrgHR")
        leave_policy_service.save_policy(db, org.id, name="Private")
        _as(db, hr)
        assert client.get("/api/v1/leave/policy").json()["name"] == "Private"

        other_hr = _user(db, other, "OrgHR")
        _as(db, other_hr)
        assert client.get("/api/v1/leave/policy").json()["is_default"] is True

    def test_templates_listed_to_any_employee(self, db, org, client):
        leave_template_service.seed_leave_templates(db)
        user = _user(db, org, "OrgEmployee")
        _as(db, user)
        resp = client.get("/api/v1/leave/templates")
        assert resp.status_code == 200
        assert len(resp.json()) >= 5

    def test_employee_cannot_apply_a_template(self, db, org, client):
        leave_template_service.seed_leave_templates(db)
        user = _user(db, org, "OrgEmployee")
        _as(db, user)
        resp = client.post("/api/v1/leave/templates/UK_STANDARD/apply")
        assert resp.status_code == 403

    def test_hr_can_apply_a_template(self, db, org, client):
        leave_template_service.seed_leave_templates(db)
        user = _user(db, org, "OrgHR")
        _as(db, user)
        resp = client.post("/api/v1/leave/templates/UK_STANDARD/apply")
        assert resp.status_code == 200, resp.text
        assert client.get("/api/v1/leave/types").json()

    def test_applying_a_template_is_tenant_scoped(self, db, org, client):
        leave_template_service.seed_leave_templates(db)
        other = Organization(
            name=f"Leave Policy Other {uuid.uuid4().hex[:6]}",
            legal_id=f"TEST-LPOL-{uuid.uuid4().hex[:8].upper()}",
        )
        db.add(other)
        db.commit()
        db.refresh(other)

        user = _user(db, org, "OrgHR")
        _as(db, user)
        client.post("/api/v1/leave/templates/UK_STANDARD/apply")

        other_hr = _user(db, other, "OrgHR")
        _as(db, other_hr)
        assert client.get("/api/v1/leave/types").json() == []
