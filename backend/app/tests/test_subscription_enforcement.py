"""
Tests for subscription plan enforcement and the public pricing catalog.

Covers the industry-standard behaviour implemented in this change:
- business routers are gated on the tenant's plan features
- employee seat limits are enforced on creation
- tenants without a subscription row fall back to the default (free) plan
  rather than being locked out entirely
- the public pricing catalog exposes only the configured plan allowlist and
  omits catalogued-but-unimplemented features
"""
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models.all_models import (
    Organization,
    OrganizationSubscription,
    SubscriptionPlan,
    User,
)
from app.services.subscription_service import subscription_service
from main import app


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def plan_ids(db):
    plans = {p.code: p.id for p in db.query(SubscriptionPlan).all()}
    for required in ("starter", "professional", "enterprise"):
        assert required in plans, f"plan '{required}' must be seeded"
    return plans


def _org_on_plan(db, plan_id, name):
    """Create (or reuse) an org subscribed to the given plan."""
    org = db.query(Organization).filter(Organization.name == name).first()
    if not org:
        org = Organization(name=name, legal_id=f"TEST-{name.upper()}")
        db.add(org)
        db.commit()
        db.refresh(org)

    sub = (
        db.query(OrganizationSubscription)
        .filter(OrganizationSubscription.organization_id == org.id)
        .first()
    )
    if not sub:
        sub = OrganizationSubscription(
            organization_id=org.id,
            subscription_plan_id=plan_id,
            status="active",
            billing_cycle="monthly",
        )
        db.add(sub)
    else:
        sub.subscription_plan_id = plan_id
        sub.status = "active"
    db.commit()
    return org


class TestFeatureGating:
    def test_starter_denies_professional_features(self, db, plan_ids):
        org = _org_on_plan(db, plan_ids["starter"], "Enforce Starter Co")

        for feature in ("payroll", "training", "performance_reviews", "assets"):
            result = subscription_service.check_feature_access(db, org.id, feature)
            assert result["allowed"] is False, (
                f"Starter must not have '{feature}'"
            )
            assert "not available" in result["reason"]

    def test_starter_allows_core_features(self, db, plan_ids):
        org = _org_on_plan(db, plan_ids["starter"], "Enforce Starter Co")

        for feature in ("attendance", "leave_management", "face_recognition"):
            result = subscription_service.check_feature_access(db, org.id, feature)
            assert result["allowed"] is True, (
                f"Starter must include core feature '{feature}'"
            )

    def test_professional_allows_payroll(self, db, plan_ids):
        org = _org_on_plan(db, plan_ids["professional"], "Enforce Pro Co")
        result = subscription_service.check_feature_access(db, org.id, "payroll")
        assert result["allowed"] is True

    def test_enterprise_allows_enterprise_only_features(self, db, plan_ids):
        org = _org_on_plan(db, plan_ids["enterprise"], "Enforce Ent Co")
        for feature in ("payroll", "sso", "custom_roles", "mfa"):
            result = subscription_service.check_feature_access(db, org.id, feature)
            assert result["allowed"] is True, f"Enterprise must include '{feature}'"

    def test_unknown_feature_is_denied_not_allowed(self, db, plan_ids):
        org = _org_on_plan(db, plan_ids["enterprise"], "Enforce Ent Co")
        result = subscription_service.check_feature_access(db, org.id, "not_a_feature")
        assert result["allowed"] is False
        assert "not found" in result["reason"]


class TestLicensingLimits:
    def test_hard_limit_blocks_creation(self, db, plan_ids):
        """Starter caps employees at 50; usage at the cap must be refused."""
        org = _org_on_plan(db, plan_ids["starter"], "Enforce Starter Co")

        under = subscription_service.check_licensing_limit(
            db, org.id, "employees", current_usage=49
        )
        assert under["allowed"] is True

        at_cap = subscription_service.check_licensing_limit(
            db, org.id, "employees", current_usage=50
        )
        assert at_cap["allowed"] is False
        assert "Hard limit" in at_cap["warning"]

    def test_enterprise_seats_are_unlimited(self, db, plan_ids):
        org = _org_on_plan(db, plan_ids["enterprise"], "Enforce Ent Co")
        result = subscription_service.check_licensing_limit(
            db, org.id, "employees", current_usage=100_000
        )
        assert result["allowed"] is True

    def test_soft_limit_warns_without_blocking(self, db, plan_ids):
        """Professional warns at 450 employees but still allows up to 500."""
        org = _org_on_plan(db, plan_ids["professional"], "Enforce Pro Co")

        warned = subscription_service.check_licensing_limit(
            db, org.id, "employees", current_usage=450
        )
        assert warned["allowed"] is True
        assert warned["warning"] is not None

        blocked = subscription_service.check_licensing_limit(
            db, org.id, "employees", current_usage=500
        )
        assert blocked["allowed"] is False


class TestDefaultPlanFallback:
    def test_org_without_subscription_gets_default_plan(self, db, plan_ids):
        """A tenant missing a subscription row must not be locked out.

        Regression guard: hard-denying here broke every gated route for orgs
        provisioned before enforcement existed.
        """
        org = db.query(Organization).filter(
            Organization.name == "Enforce NoSub Co"
        ).first()
        if not org:
            org = Organization(name="Enforce NoSub Co", legal_id="TEST-NOSUB")
            db.add(org)
            db.commit()
            db.refresh(org)

        existing = (
            db.query(OrganizationSubscription)
            .filter(OrganizationSubscription.organization_id == org.id)
            .first()
        )
        if existing:
            db.delete(existing)
            db.commit()

        # Default plan entitlements apply.
        core = subscription_service.check_feature_access(
            db, org.id, "attendance"
        )
        assert core["allowed"] is True

        # But paid features stay closed.
        paid = subscription_service.check_feature_access(db, org.id, "payroll")
        assert paid["allowed"] is False

        limits = subscription_service.check_licensing_limit(
            db, org.id, "employees", current_usage=10
        )
        assert limits["allowed"] is True

    def test_ensure_default_subscription_is_idempotent(self, db, plan_ids):
        org = _org_on_plan(db, plan_ids["professional"], "Enforce Idem Co")
        before = (
            db.query(OrganizationSubscription)
            .filter(OrganizationSubscription.organization_id == org.id)
            .count()
        )
        subscription_service.ensure_default_subscription(db, org.id)
        subscription_service.ensure_default_subscription(db, org.id)
        after = (
            db.query(OrganizationSubscription)
            .filter(OrganizationSubscription.organization_id == org.id)
            .count()
        )
        assert after == before, "provisioning must not create duplicate subscriptions"


class TestPublicCatalog:
    @pytest.fixture(scope="class")
    def catalog(self):
        client = TestClient(app)
        response = client.get("/api/v1/public/plans")
        assert response.status_code == 200
        return response.json()

    def test_requires_no_authentication(self, catalog):
        assert catalog["count"] > 0

    def test_returns_only_allowlisted_plans(self, catalog):
        """test_plan_* and dup_* rows are is_system=true, so an is_system
        filter would leak them onto a public page."""
        allowlist = {
            c.strip() for c in settings.PUBLIC_PLAN_CODES.split(",") if c.strip()
        }
        returned = {p["code"] for p in catalog["plans"]}
        assert returned == allowlist
        assert not any(code.startswith("test_") for code in returned)
        assert not any(code.startswith("dup_") for code in returned)

    def test_exposes_pricing_and_limits(self, catalog):
        for plan in catalog["plans"]:
            assert "monthly_price" in plan
            assert "yearly_price" in plan
            assert "currency" in plan
            assert plan["limits"], "each plan must publish its capacity limits"
            assert "employees" in plan["limits"]

    def test_excludes_unimplemented_features(self, catalog):
        """Deprecated features must never appear on a public pricing page.

        Each of these was catalogued and mapped to paid plans but has no
        router/service implementation, so advertising them is false
        advertising. Verified absent from app/routers, app/services, app/crud.
        """
        deprecated = {
            # No implementation at all
            "marketplace",
            "white_label",
            "visitor_management",
            "referral_program",
            "blockchain_audit",
            "sso",            # auth router has no SSO/OIDC endpoints
            "mfa",            # only a config-center mention
            "geofencing",     # config flag only, no backend enforcement
            "bulk_operations",
            # Model/enum only
            "projects",
        }
        for plan in catalog["plans"]:
            leaked = deprecated.intersection(plan["features"])
            assert not leaked, f"{plan['code']} advertises unimplemented {leaked}"

    def test_leaked_data_check(self, catalog):
        """Catalog must not carry tenant or subscription records."""
        blob = str(catalog)
        assert "organization_id" not in blob
        assert "hashed_password" not in blob


class TestEnforcementToggle:
    def test_flag_present_and_default_true(self):
        assert hasattr(settings, "ENFORCE_SUBSCRIPTION_LIMITS")
        assert settings.ENFORCE_SUBSCRIPTION_LIMITS is True
