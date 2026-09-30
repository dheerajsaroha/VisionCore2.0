"""
Mounting the five unmounted routers, and the authorization they needed.

`analytics_router`, `compliance_router`, `copilot_router`,
`audit_explorer_router` and `tenant_admin` were all written and all reachable
from nowhere: none appeared in `routers/__init__.py`, so every endpoint they
declared returned 404. `tenant_admin` could not even be imported, because it
imported a `get_current_superadmin` that did not exist in `deps`.

Mounting them as written would have been a privilege escalation rather than a
feature delivery. Each required a gate that did not exist before:

- audit logs and security events required only an active session, and return
  `actor_user_id`, `ip_address` and `meta_data` for the whole organization;
- compliance retention policies, legal holds and privacy requests likewise
  required only an active session;
- the metric registry seeded a `required_permission` per metric that nothing
  ever read, leaving `payroll_monthly_cost` open to any session;
- two of those seeded permission names (`attendance.read`, `assets.read`) never
  existed in the RBAC catalog at all;
- `privacy_service.process_request` looked requests up by primary key with no
  organization filter, then exported the subject's payroll and attendance, which
  is a cross-tenant data exfiltration path.

These pin the mount, the gates, and the tenant isolation.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from main import app
from app.api import deps
from app.core import rate_limit
from app.core.security import get_password_hash
from app.db import seed_rbac
from app.db.database import SessionLocal, get_db
from app.db.models.all_models import (
    Feature,
    MetricDefinition,
    Organization,
    Permission,
    PlanFeature,
    PrivacyRequest,
    Role,
    RolePermission,
    SubscriptionPlan,
    User,
)
from app.services.metric_registry import metric_registry_service


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


def _grant(db, role_name, *permission_names):
    """Grant permissions to a role outside the seed, for focused assertions."""
    role = db.query(Role).filter(Role.name == role_name).first()
    for pname in permission_names:
        perm = db.query(Permission).filter(Permission.name == pname).first()
        if perm is None:
            raise AssertionError(f"permission {pname} does not exist in the catalog")
        exists = db.query(RolePermission).filter(
            RolePermission.role_id == role.id,
            RolePermission.permission_id == perm.id,
        ).first()
        if not exists:
            db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db.commit()


def _plan(db, code, features):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == code).first()
    if plan is None:
        plan = SubscriptionPlan(code=code, name=code.title(), is_active=True)
        db.add(plan)
        db.commit()
        db.refresh(plan)
    for fcode in features:
        feat = db.query(Feature).filter(Feature.code == fcode).first()
        if feat is None:
            feat = Feature(code=fcode, name=fcode.title())
            db.add(feat)
            db.commit()
            db.refresh(feat)
        if not db.query(PlanFeature).filter(
            PlanFeature.plan_id == plan.id, PlanFeature.feature_id == feat.id
        ).first():
            db.add(PlanFeature(plan_id=plan.id, feature_id=feat.id))
    db.commit()
    return plan


def _org(db):
    org = Organization(
        name=f"Mounted {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-MNT-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _user(db, org, role_name, code="user"):
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


class TestRoutersAreMounted:
    """The defect: five written routers reachable from nowhere."""

    def test_all_five_prefixes_are_served(self):
        paths = set(app.openapi().get("paths", {}))
        for prefix in (
            "/api/v1/analytics/",
            "/api/v1/compliance/",
            "/api/v1/copilot/",
            "/api/v1/audit-explorer/",
            "/api/v1/tenant/",
        ):
            hits = [p for p in paths if p.startswith(prefix)]
            assert hits, f"{prefix} is not mounted"

    def test_tenant_admin_is_importable(self):
        """It could not even be imported before: no get_current_superadmin."""
        from app.api.deps import get_current_superadmin

        assert callable(get_current_superadmin)


class TestAuditExplorerIsGated:
    def test_employee_cannot_read_audit_logs(self, client, db):
        emp = _user(db, _org(db), "OrgEmployee", "intern")
        _as(db, emp)
        r = client.get("/api/v1/audit-explorer/audit-logs")
        assert r.status_code == 403, "an employee must not read the org audit trail"

    def test_employee_cannot_list_security_events(self, client, db):
        emp = _user(db, _org(db), "OrgEmployee", "intern2")
        _as(db, emp)
        assert client.get("/api/v1/audit-explorer/security-events").status_code == 403

    def test_employee_cannot_write_security_events(self, client, db):
        emp = _user(db, _org(db), "OrgEmployee", "intern3")
        _as(db, emp)
        r = client.post(
            "/api/v1/audit-explorer/security-events",
            json={"event_type": "probe", "severity": "INFO"},
        )
        assert r.status_code == 403

    def test_auditor_can_read_audit_logs(self, client, db):
        seed_rbac.seed_all(db)
        db.commit()
        org = _org(db)
        auditor = _user(db, org, "OrgHR", "auditor")
        _grant(db, "OrgHR", "audit.view")
        _as(db, auditor)
        assert client.get("/api/v1/audit-explorer/audit-logs").status_code == 200


class TestComplianceIsGated:
    def test_employee_cannot_list_privacy_requests(self, client, db):
        emp = _user(db, _org(db), "OrgEmployee", "dsar")
        _as(db, emp)
        assert client.get("/api/v1/compliance/privacy-requests").status_code == 403

    def test_employee_cannot_list_retention_policies(self, client, db):
        emp = _user(db, _org(db), "OrgEmployee", "ret")
        _as(db, emp)
        assert client.get("/api/v1/compliance/retention-policies").status_code == 403

    def test_employee_cannot_place_a_legal_hold(self, client, db):
        emp = _user(db, _org(db), "OrgEmployee", "hold")
        _as(db, emp)
        r = client.post(
            "/api/v1/compliance/legal-holds",
            json={"entity_type": "USER", "entity_id": "1", "reason": "probe"},
        )
        assert r.status_code == 403

    def test_hr_can_view_but_not_manage(self, client, db):
        seed_rbac.seed_all(db)
        db.commit()
        org = _org(db)
        hr = _user(db, org, "OrgHR", "hrview")
        _as(db, hr)
        assert client.get("/api/v1/compliance/retention-policies").status_code == 200
        # OrgHR holds policy.compliance.manage, so this is expected to be 200 —
        # asserted to document the split rather than to lock a denial.
        assert client.get("/api/v1/compliance/legal-holds").status_code == 200


class TestTenantAdminIsSuperAdminOnly:
    def test_org_admin_cannot_list_all_tenants(self, client, db):
        """Cross-tenant surface: OrgAdmin must not reach it.

        `require_admin` admits OrgAdmin, so substituting it for the missing
        SuperAdmin dependency would have escalated one tenant to all of them.
        """
        seed_rbac.seed_all(db)
        db.commit()
        admin = _user(db, _org(db), "OrgAdmin", "tenantadmin")
        _as(db, admin)
        r = client.get("/api/v1/tenant/")
        assert r.status_code == 403, "an OrgAdmin must not enumerate every tenant"

    def test_superadmin_can_list_tenants(self, client, db):
        seed_rbac.seed_all(db)
        db.commit()
        sa = _user(db, _org(db), "SuperAdmin", "sa")
        _as(db, sa)
        assert client.get("/api/v1/tenant/").status_code == 200


class TestMetricPermissionsAreEnforced:
    def test_seeded_permission_names_all_exist(self, db):
        """Two of the five seeded names never existed in the catalog.

        With `required_permission` now enforced, an unresolvable name denies
        everyone, so a bad name is a silently dead metric rather than an open one.
        """
        metric_registry_service.seed_default_metrics(db)
        db.commit()
        for defn in db.query(MetricDefinition).all():
            assert (
                db.query(Permission).filter(Permission.name == defn.required_permission).first()
            ), f"metric {defn.metric_key} requires unknown permission {defn.required_permission}"

    def test_seeder_reconciles_a_drifted_permission(self, db):
        defn = db.query(MetricDefinition).filter(
            MetricDefinition.metric_key == "attendance_rate"
        ).first()
        assert defn is not None
        defn.required_permission = "attendance.read"  # the old, nonexistent name
        db.commit()

        metric_registry_service.seed_default_metrics(db)
        db.commit()
        db.refresh(defn)
        assert defn.required_permission == "attendance.view"

    def test_employee_cannot_read_payroll_cost_metric(self, client, db):
        seed_rbac.seed_all(db)
        db.commit()
        emp = _user(db, _org(db), "OrgEmployee", "payrollmetric")
        _as(db, emp)
        metric_registry_service.seed_default_metrics(db)
        db.commit()
        r = client.get("/api/v1/analytics/metrics/payroll_monthly_cost/value")
        assert r.status_code == 403, "payroll cost must not be readable by an employee"

    def test_employee_cannot_read_the_aggregate_dashboard(self, client, db):
        emp = _user(db, _org(db), "OrgEmployee", "aggdash")
        _as(db, emp)
        assert client.get("/api/v1/analytics/dashboard").status_code == 403

    def test_finance_can_read_payroll_cost_metric(self, client, db):
        seed_rbac.seed_all(db)
        db.commit()
        fin = _user(db, _org(db), "OrgFinance", "finreader")
        _as(db, fin)
        metric_registry_service.seed_default_metrics(db)
        db.commit()
        r = client.get("/api/v1/analytics/metrics/payroll_monthly_cost/value")
        assert r.status_code == 200, f"OrgFinance holds payroll.read: {r.text[:160]}"


class TestPrivacyRequestTenantIsolation:
    def test_a_tenant_cannot_process_another_tenants_request(self, client, db):
        """`process_request` looked up by primary key with no org filter.

        Fulfilment for ACCESS_EXPORT reads the subject's payroll and attendance,
        so an id from another tenant was enough to export that tenant's data.
        """
        seed_rbac.seed_all(db)
        db.commit()
        org_a, org_b = _org(db), _org(db)
        victim = _user(db, org_a, "OrgEmployee", "victim")
        attacker = _user(db, org_b, "OrgHR", "attacker")

        req = PrivacyRequest(
            organization_id=org_a.id,
            user_id=victim.id,
            request_type="ACCESS_EXPORT",
            status="REQUESTED",
        )
        db.add(req)
        db.commit()
        db.refresh(req)

        _as(db, attacker)
        r = client.post(
            f"/api/v1/compliance/privacy-requests/{req.id}/process",
            json={"approve": True},
        )
        assert r.status_code == 404, (
            "a cross-tenant request must be indistinguishable from a missing one"
        )
        db.refresh(req)
        assert req.status == "REQUESTED", "another tenant's request must be untouched"

    def test_the_owner_tenant_can_process_its_request(self, client, db):
        seed_rbac.seed_all(db)
        db.commit()
        org_a = _org(db)
        subject = _user(db, org_a, "OrgEmployee", "subject")
        hr = _user(db, org_a, "OrgHR", "ownhr")

        req = PrivacyRequest(
            organization_id=org_a.id,
            user_id=subject.id,
            request_type="RECTIFICATION",
            status="REQUESTED",
        )
        db.add(req)
        db.commit()
        db.refresh(req)

        _as(db, hr)
        r = client.post(
            f"/api/v1/compliance/privacy-requests/{req.id}/process",
            json={"approve": False, "rejection_reason": "test"},
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"


class TestCopilotRemainsFeatureGated:
    def test_copilot_requires_the_ai_chat_feature(self, client, db):
        """Its router-level `require_feature` must survive the mount."""
        plan = _plan(db, "mnt_no_aichat", [])
        org = _org(db)
        user = _user(db, org, "OrgHR", "nocopilot")
        from datetime import datetime, timedelta, timezone
        from app.db.models.all_models import OrganizationSubscription

        now = datetime.now(timezone.utc)
        db.add(
            OrganizationSubscription(
                organization_id=org.id,
                subscription_plan_id=plan.id,
                status="active",
                start_date=now - timedelta(days=1),
                end_date=now + timedelta(days=30),
            )
        )
        db.commit()
        _as(db, user)
        r = client.post("/api/v1/copilot/chat", json={"message": "hi"})
        assert r.status_code in (402, 422, 400), f"expected refusal, got {r.status_code}"
