"""
EAAC authorization: the static/dynamic permission reconciliation.

The reported symptom was an OrgAdmin receiving

    EAAC Access Denied: Permission 'performance.analytics.read' not granted
    by any active dynamic role

on the Performance Management Center. The message was accurate but the cause
was not specific to that one permission, and it was not a missing grant.

Two independent defects stacked:

1. `resolve_effective_permissions` consulted `UserRoleAssignment` and nothing
   else. Authority that comes from the static `RolePermission` table -- which
   is what `deps.require_permission` uses, and therefore what authorises the
   rest of the application -- resolved to an *empty* permission set. The whole
   dynamic-role subsystem was therefore "base SuperAdmin only".

2. 75 of the 85 permissions the EAAC-guarded routers demand were never
   registered at all, so no role could have held them.

The tests here cover both, plus the drift guard that stops a new
EAAC-guarded endpoint from demanding a permission nobody registered.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text as sql_text

from app.db.database import SessionLocal
from app.db.models.all_models import (
    DynamicRole,
    Organization,
    OrganizationSubscription,
    Permission,
    Role,
    RolePermission,
    SubscriptionPlan,
    User,
    UserRoleAssignment,
    UserSession,
)
from app.services.dynamic_role_engine import EffectivePermissionResolver
from app.services.eaac_engine import EnterpriseAuthorizationEngine

REPO_BACKEND = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _role(db, name: str) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    assert role, f"seeded role {name} is missing"
    return role


def _user_for_role(db, role_name: str) -> User:
    """A real, seeded user holding `role_name`.

    Deliberately not a fixture-created user: the bug was that *existing*
    seeded users resolved to nothing, so a synthetic user with hand-granted
    permissions would have passed straight over it.
    """
    user = (
        db.query(User)
        .join(Role, User.role_id == Role.id)
        .filter(
            Role.name == role_name,
            User.is_deleted == 0,
            User.is_active == 1,
            User.org_id.isnot(None),
        )
        .first()
    )
    assert user, f"no seeded active user holds {role_name}"
    return user


def _granted(db, user: User, permission: str) -> bool:
    decision = EnterpriseAuthorizationEngine.evaluate_access(
        db=db, user_id=user.id, organization_id=user.org_id,
        permission=permission,
    )
    return decision.granted


def _eaac_permissions_demanded_by_routers() -> set[str]:
    demanded: set[str] = set()
    for path in (REPO_BACKEND / "app" / "routers").glob("*.py"):
        demanded |= set(re.findall(
            r'require_eaac_authorization\(\s*"([^"]+)"',
            # Explicit UTF-8 with replacement avoids cp1252 UnicodeDecodeError
            # on Windows when router files contain non-ASCII bytes.
            path.read_text(encoding="utf-8", errors="replace")))
    return demanded


def _registered_permissions() -> set[str]:
    db = SessionLocal()
    try:
        return {row[0] for row in db.query(Permission.name).all()}
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# the reported bug
# --------------------------------------------------------------------------- #

class TestReportedSymptom:
    def test_org_admin_can_read_performance_analytics(self, db):
        user = _user_for_role(db, "OrgAdmin")
        decision = EnterpriseAuthorizationEngine.evaluate_access(
            db=db, user_id=user.id, organization_id=user.org_id,
            permission="performance.analytics.read",
        )
        assert decision.granted, (
            f"OrgAdmin was denied performance.analytics.read: "
            f"{decision.deny_reason}"
        )

    @pytest.mark.parametrize("role_name", ["OrgAdmin", "OrgHR", "OrgManager"])
    def test_oversight_roles_can_read_performance_analytics(self, db, role_name):
        assert _granted(db, _user_for_role(db, role_name),
                        "performance.analytics.read"), (
            f"{role_name} cannot read the performance analytics dashboard"
        )

    def test_an_employee_still_cannot(self, db):
        """The fix must not have turned performance into an open door."""
        assert not _granted(db, _user_for_role(db, "OrgEmployee"),
                            "performance.analytics.read")

    def test_an_employee_cannot_read_the_whole_orgs_reviews(self, db):
        """`GET /performance/reviews` returns every review in the tenant unless
        a `user_id` narrows it, so this must stay out of employee hands."""
        assert not _granted(db, _user_for_role(db, "OrgEmployee"),
                            "performance.review.read")

    def test_an_employee_cannot_read_another_persons_feedback(self, db):
        """`GET /performance/feedback?user_id=<other>` returns that person's
        feedback, so the read permission must not reach employees."""
        assert not _granted(db, _user_for_role(db, "OrgEmployee"),
                            "performance.feedback.read")

    def test_an_employee_keeps_self_scoped_performance_access(self, db):
        """These endpoints default to `user_id or current_user.id`, so granting
        them is what makes the employee Performance page work at all."""
        for permission in ("performance.goal.read", "performance.goal.update",
                           "performance.review.submit", "performance.feedback.create"):
            assert _granted(db, _user_for_role(db, "OrgEmployee"), permission), (
                f"employees lost {permission}, which the self-service page needs"
            )


# --------------------------------------------------------------------------- #
# the systemic cause
# --------------------------------------------------------------------------- #

class TestStaticRoleIsAFallbackNotAnAfterthought:
    def test_a_user_with_no_dynamic_assignment_resolves_their_static_role(self, db):
        user = _user_for_role(db, "OrgAdmin")
        assert db.query(UserRoleAssignment).filter(
            UserRoleAssignment.user_id == user.id).count() == 0, (
            "this test needs a user with no dynamic role assigned"
        )
        resolved = EffectivePermissionResolver.resolve_effective_permissions(
            db, user.id, user.org_id
        )
        assert resolved["resolution_source"] == "static_role"
        assert len(resolved["effective_permissions"]) > 0, (
            "a user with no dynamic role resolved to zero permissions, which "
            "denied every EAAC-guarded endpoint"
        )

    def test_the_fallback_matches_what_require_permission_would_grant(self, db):
        """The two authorisation systems must not disagree.

        EAAC now reads the same `RolePermission` table as
        `deps.require_permission`, so an endpoint reachable by one is reachable
        by the other for the same permission.
        """
        user = _user_for_role(db, "OrgHR")
        resolved = set(EffectivePermissionResolver.resolve_effective_permissions(
            db, user.id, user.org_id)["effective_permissions"])
        static = {
            row[0]
            for row in db.query(Permission.name)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .filter(RolePermission.role_id == user.role_id,
                    Permission.is_active.is_(True))
            .all()
        }
        assert resolved == static

    def test_superadmin_still_holds_implicit_everything(self, db):
        resolved = EffectivePermissionResolver.resolve_effective_permissions(
            db, _user_for_role(db, "SuperAdmin").id,
            _user_for_role(db, "SuperAdmin").org_id,
        )
        assert "*" in resolved["effective_permissions"]

    def test_a_dynamic_role_assignment_still_wins(self, db):
        """The fallback must not hijack users who *do* have a dynamic role."""
        org = Organization(name=f"EAAC dyn {uuid.uuid4().hex[:4]}",
                           legal_id=f"EAACDYN-{uuid.uuid4().hex[:8].upper()}")
        db.add(org)
        db.commit()
        db.refresh(org)
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.code == "enterprise").first()
        db.add(OrganizationSubscription(
            organization_id=org.id, subscription_plan_id=plan.id,
            status="active", billing_cycle="yearly"))
        db.commit()

        role = _role(db, "OrgEmployee")
        user = User(
            email=f"dyn_{uuid.uuid4().hex[:8]}@example.com",
            username=f"dyn_{uuid.uuid4().hex[:6]}",
            employee_id=f"DYN{uuid.uuid4().hex[:6].upper()}",
            full_name="Dyn User", org_id=org.id, role_id=role.id,
            is_active=1, is_deleted=0, hashed_password="x",
        )
        db.add(user)
        db.flush()
        dyn = DynamicRole(
            code=f"dyn_{uuid.uuid4().hex[:8]}", name="Dyn", tier="custom",
            organization_id=org.id, status="active",
            permissions_json=["some.dynamic.permission"],
            data_scopes_json={}, approval_rights_json=[], features_json=[],
        )
        db.add(dyn)
        db.flush()
        db.add(UserRoleAssignment(
            organization_id=org.id, user_id=user.id, role_id=dyn.id,
            is_primary=True, is_active=True,
        ))
        db.commit()
        try:
            resolved = EffectivePermissionResolver.resolve_effective_permissions(
                db, user.id, org.id
            )
            assert "some.dynamic.permission" in resolved["effective_permissions"]
            assert "attendance.checkin" not in resolved["effective_permissions"], (
                "the static role leaked in despite an explicit dynamic role"
            )
        finally:
            db.query(UserRoleAssignment).filter(
                UserRoleAssignment.user_id == user.id).delete()
            db.query(DynamicRole).filter(DynamicRole.id == dyn.id).delete()
            db.query(UserSession).filter(UserSession.user_id == user.id).delete()
            db.query(User).filter(User.id == user.id).delete()
            db.query(OrganizationSubscription).filter(
                OrganizationSubscription.organization_id == org.id).delete()
            db.query(Organization).filter(Organization.id == org.id).delete()
            db.commit()


# --------------------------------------------------------------------------- #
# drift guard
# --------------------------------------------------------------------------- #

class TestNoUnregisteredEaacPermissions:
    def test_every_guarded_permission_is_registered(self):
        """The original second defect: 75 permissions the routers demanded were
        never defined, so no role could hold them and the endpoints were
        unreachable. A newly guarded endpoint must not be able to reintroduce
        that silently."""
        missing = sorted(_eaac_permissions_demanded_by_routers()
                         - _registered_permissions())
        assert not missing, (
            f"{len(missing)} EAAC-guarded permissions are not registered; the "
            f"endpoints requiring them will deny every user: {missing}"
        )

    def test_the_guard_is_actually_finding_permissions(self):
        """Guards against the test passing because the extraction broke."""
        demanded = _eaac_permissions_demanded_by_routers()
        assert len(demanded) > 50, (
            f"only {len(demanded)} EAAC permissions detected; the extraction is "
            "probably wrong, which would make the test above vacuous"
        )
        assert "performance.analytics.read" in demanded
        assert "asset.read" in demanded

    def test_the_registered_permission_count_covers_the_demand(self):
        db = SessionLocal()
        try:
            total = db.query(Permission).count()
        finally:
            db.close()
        assert total >= len(_eaac_permissions_demanded_by_routers())


class TestNoStrayUniqueOrphanedPermissions:
    def test_permissions_are_active(self):
        """An inactive permission is one the resolver filters out, which would
        reproduce the denial for a different reason."""
        db = SessionLocal()
        try:
            inactive = [
                row[0] for row in db.query(Permission.name)
                .filter(Permission.is_active.isnot(True)).all()
            ]
        finally:
            db.close()
        eaac = _eaac_permissions_demanded_by_routers()
        assert not (set(inactive) & eaac), (
            f"EAAC-guarded permissions exist but are inactive: "
            f"{sorted(set(inactive) & eaac)}"
        )
