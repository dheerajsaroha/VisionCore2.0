"""
Learning & Development access for ordinary employees.

Three separate defects made the section unusable for a normal employee, and only
one of them looked like a permissions problem:

1. `learning.view_org` was required by the router but never seeded, so it could
   not be granted to *any* role. The Budget tab and the analytics/budget
   endpoints were unreachable even for OrgAdmin and OrgHR.
2. The page fetched organization-wide analytics and budget alongside the
   employee-visible data in a single `Promise.all`. An employee holds
   `learning.view` but deliberately not `learning.view_org`, so those two calls
   returned 403 and rejected the batch — leaving courses, sessions, quizzes,
   skills and certificates all unrendered, and the error swallowed to the
   console.
3. The default tab was the org-wide overview, which an employee cannot see, so
   even with data loaded the page opened on a panel of zeros.

These cover the permission split and the subscription status that decides
whether the section exists at all.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from main import app
from app.api import deps
from app.core import rate_limit
from app.crud import crud_subscription
from app.core.security import get_password_hash
from app.db import seed_rbac
from app.db.database import SessionLocal, get_db
from app.db.models.all_models import (
    Feature,
    Organization,
    OrganizationSubscription,
    Permission,
    PlanFeature,
    Role,
    RolePermission,
    SubscriptionPlan,
    User,
)
from app.services.subscription_service import subscription_service


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        app.dependency_overrides[get_db] = lambda: db
        try:
            yield c
        finally:
            app.dependency_overrides.clear()
            rate_limit._fallback_windows.clear()


def _plan(db, code, features):
    plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.code == code)
        .first()
    )
    if plan is None:
        plan = SubscriptionPlan(code=code, name=code.title(), is_active=True)
        db.add(plan)
        db.commit()
        db.refresh(plan)
    for code_ in features:
        feat = db.query(Feature).filter(Feature.code == code_).first()
        if feat is None:
            feat = Feature(code=code_, name=code_.title())
            db.add(feat)
            db.commit()
            db.refresh(feat)
        if not db.query(PlanFeature).filter(
            PlanFeature.plan_id == plan.id, PlanFeature.feature_id == feat.id
        ).first():
            db.add(PlanFeature(plan_id=plan.id, feature_id=feat.id))
    db.commit()
    return plan


def _org_with_plan(db, plan, *, end_in_days=30):
    org = Organization(
        name=f"L&D {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-LD-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    now = datetime.now(timezone.utc)
    db.add(
        OrganizationSubscription(
            organization_id=org.id,
            subscription_plan_id=plan.id,
            status="active",
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=end_in_days),
        )
    )
    db.commit()
    return org


def _user(db, org, role_name, code="learner"):
    role = db.query(Role).filter(Role.name == role_name).first()
    slug = f"{code}-{uuid.uuid4().hex[:6]}"
    u = User(
        email=f"{slug}@example.com",
        username=slug,
        employee_id=slug.upper(),
        full_name=code,
        org_id=org.id,
        role_id=role.id,
        is_active=1,
        hashed_password=get_password_hash("Test-Passw0rd!"),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _as(db, user):
    app.dependency_overrides[deps.get_current_active_user] = lambda: user


class TestLearningPermissionCatalog:
    def test_view_org_is_a_real_permission(self, db):
        """It was required by the router but had no row, so nothing could grant it."""
        seed_rbac.seed_all(db)
        db.commit()
        assert (
            db.query(Permission).filter(Permission.name == "learning.view_org").first()
        ), "learning.view_org must exist to be grantable"

    def test_privileged_roles_receive_view_org(self, db):
        seed_rbac.seed_all(db)
        db.commit()
        for role_name in ("OrgAdmin", "OrgHR", "OrgManager"):
            role = db.query(Role).filter(Role.name == role_name).first()
            names = {
                p.name
                for p in db.query(Permission)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .filter(RolePermission.role_id == role.id)
                .all()
            }
            assert "learning.view_org" in names, f"{role_name} needs org-wide learning visibility"

    def test_employee_does_not_receive_view_org(self, db):
        seed_rbac.seed_all(db)
        db.commit()
        role = db.query(Role).filter(Role.name == "OrgEmployee").first()
        names = {
            p.name
            for p in db.query(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .filter(RolePermission.role_id == role.id)
            .all()
        }
        assert "learning.view" in names, "an employee must still see their own learning"
        assert "learning.view_org" not in names, (
            "an employee must not see organization-wide learning spend"
        )


class TestEmployeeReachesLearning:
    """The whole point: a normal employee gets a working section."""

    def test_employee_reads_courses_sessions_and_skills(self, client, db):
        plan = _plan(db, "ld_emp_ok", ["training"])
        org = _org_with_plan(db, plan)
        emp = _user(db, org, "OrgEmployee", "employee")
        _as(db, emp)

        for path in ("/api/v1/learning/courses", "/api/v1/learning/sessions",
                     "/api/v1/learning/skills", "/api/v1/learning/quizzes",
                     "/api/v1/learning/certificates", "/api/v1/learning/categories"):
            r = client.get(path)
            assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:160]}"

    def test_employee_enrollment_is_scoped_to_themself(self, client, db):
        plan = _plan(db, "ld_emp_scope", ["training"])
        org = _org_with_plan(db, plan)
        emp = _user(db, org, "OrgEmployee", "scoped")
        _as(db, emp)

        r = client.get("/api/v1/learning/enrollments")
        assert r.status_code == 200
        # The router falls back to the caller's own id without view_org, so an
        # employee must not be handed the whole organization's enrollments.
        rows = r.json()
        assert all(
            row.get("user_id") in (None, emp.id) for row in rows
        ), "an employee must only see their own enrollments"

    def test_employee_is_still_blocked_from_org_wide_spend(self, client, db):
        """The permission split is real, not cosmetic."""
        plan = _plan(db, "ld_emp_denied", ["training"])
        org = _org_with_plan(db, plan)
        emp = _user(db, org, "OrgEmployee", "denied")
        _as(db, emp)

        for path in ("/api/v1/learning/budget", "/api/v1/learning/analytics/dashboard"):
            assert client.get(path).status_code == 403, f"{path} must stay closed to employees"

    def test_hr_reaches_the_org_wide_endpoints(self, client, db):
        plan = _plan(db, "ld_hr_ok", ["training"])
        org = _org_with_plan(db, plan)
        hr = _user(db, org, "OrgHR", "hruser")
        _as(db, hr)

        for path in ("/api/v1/learning/budget", "/api/v1/learning/analytics/dashboard"):
            r = client.get(path)
            assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:160]}"


class TestSubscriptionExpiry:
    def test_lapsed_subscription_is_marked_expired(self, db):
        """A row past its end_date kept status='active' forever.

        Feature enforcement date-filtered it away, so the organization silently
        dropped to the default plan while its own screens still reported it
        active and on the paid tier.
        """
        plan = _plan(db, "ld_lapsed", ["training"])
        org = _org_with_plan(db, plan, end_in_days=-5)

        sub = (
            db.query(OrganizationSubscription)
            .filter(OrganizationSubscription.organization_id == org.id)
            .first()
        )
        assert sub.status == "active", "precondition: the row still claims to be active"

        assert crud_subscription.org_subscription_crud.get_active_by_org(db, org.id) is None
        db.refresh(sub)
        assert sub.status == "expired", "the stored status must not keep claiming active"

    def test_current_subscription_is_untouched(self, db):
        plan = _plan(db, "ld_current", ["training"])
        org = _org_with_plan(db, plan, end_in_days=30)

        sub = crud_subscription.org_subscription_crud.get_active_by_org(db, org.id)
        assert sub is not None
        assert sub.status == "active"

    def test_open_ended_subscription_stays_active(self, db):
        plan = _plan(db, "ld_open", ["training"])
        org = _org_with_plan(db, plan, end_in_days=30)
        sub = db.query(OrganizationSubscription).filter(
            OrganizationSubscription.organization_id == org.id
        ).first()
        sub.end_date = None
        db.commit()

        found = crud_subscription.org_subscription_crud.get_active_by_org(db, org.id)
        assert found is not None
        assert found.status == "active"


class TestFeatureGateHonoursPlan:
    def test_plan_without_training_still_refuses(self, client, db):
        """The expiry fix must not become a way to grant revoked features."""
        plan = _plan(db, "ld_no_training", [])
        org = _org_with_plan(db, plan, end_in_days=-5)
        emp = _user(db, org, "OrgEmployee", "nogate")
        _as(db, emp)

        r = client.get("/api/v1/learning/courses")
        assert r.status_code == 402
        assert r.headers.get("X-Subscription-Feature") == "training"

    def test_employee_on_a_covered_plan_is_served(self, client, db):
        plan = _plan(db, "ld_covered", ["training"])
        org = _org_with_plan(db, plan)
        emp = _user(db, org, "OrgEmployee", "covered")
        _as(db, emp)
        assert client.get("/api/v1/learning/courses").status_code == 200
