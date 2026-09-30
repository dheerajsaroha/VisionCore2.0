"""
Seed one user for every role, across every subscription tier, and print the
credentials.

Existing provisioners only covered a single flat set of personas
(`provision_test_users.py` -> 8 users in one Enterprise org, `seed.py` -> 4
users in one org, `seed_comprehensive.py` -> 4 more in another). None of them
covered the other two plans, so there was no way to exercise tier gating, and
there was no single place to read off working logins.

This seeder is idempotent: every organization is keyed by `legal_id` and every
user by `email` / `username` / `employee_id`, all of which carry unique
indexes. Re-running it updates in place rather than duplicating.

Layout produced:

  * one "Platform Operations" org -> every `platform` role and every `system`
    role (service accounts, not human logins)
  * one org per plan (starter / professional / enterprise) -> every
    `organization` role, each on that org's subscription
  * a few deliberate account-state variants (suspended, soft-deleted) so the
    423 "Account is suspended" and deleted-user paths can be exercised

Usage:
    cd backend && PYTHONPATH=$PWD ../.venv/bin/python -m app.db.seed_tier_users
    SEED_TIER_PASSWORD='...' PYTHONPATH=$PWD ../.venv/bin/python -m app.db.seed_tier_users
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.database import SessionLocal
from app.db.models.all_models import (
    Department,
    Organization,
    OrganizationSubscription,
    Role,
    Shift,
    SubscriptionPlan,
    User,
)

DEFAULT_PASSWORD = os.getenv("SEED_TIER_PASSWORD", "Password123!")

# The three sellable plans, keyed by SubscriptionPlan.code.
TIERS: List[Dict[str, str]] = [
    {
        "code": "starter",
        "prefix": "st",
        "org_name": "Tier Demo - Starter",
        "legal_id": "TIERDEMO-STARTER",
        "billing_cycle": "monthly",
    },
    {
        "code": "professional",
        "prefix": "pr",
        "org_name": "Tier Demo - Professional",
        "legal_id": "TIERDEMO-PROFESSIONAL",
        "billing_cycle": "monthly",
    },
    {
        "code": "enterprise",
        "prefix": "en",
        "org_name": "Tier Demo - Enterprise",
        "legal_id": "TIERDEMO-ENTERPRISE",
        "billing_cycle": "yearly",
    },
]

PLATFORM_ORG = {
    "org_name": "Tier Demo - Platform Operations",
    "legal_id": "TIERDEMO-PLATFORM",
}

# Human-facing organization roles. These are the ones a real person logs in as;
# the platform/system roles below are operational.
# (role_name, display label, department)
ORG_PERSONAS: List[Tuple[str, str, str]] = [
    ("OrgAdmin", "Organization Admin", "Administration"),
    ("Admin", "Tenant Admin", "Administration"),
    ("OrgHR", "HR Manager", "Human Resources"),
    ("OrgFinance", "Finance Manager", "Finance"),
    ("OrgManager", "Department Manager", "Operations"),
    ("OrgDepartmentHead", "Department Head", "Operations"),
    ("OrgSupervisor", "Team Supervisor", "Operations"),
    ("OrgTeamLead", "Team Lead", "Operations"),
    ("OrgShiftManager", "Shift Manager", "Operations"),
    ("OrgEmployee", "Employee", "Operations"),
    ("OrgContractor", "Contractor", "Operations"),
    ("OrgIntern", "Intern", "Operations"),
    ("OrgViewer", "Read-only Viewer", "Administration"),
]

# Platform operators. Each has a deliberately narrow remit in the RBAC seed.
PLATFORM_PERSONAS: List[Tuple[str, str]] = [
    ("SuperAdmin", "Super Administrator"),
    ("PlatformAdmin", "Platform Administrator"),
    ("PlatformViewer", "Platform Viewer"),
    ("PlatformAuditor", "Platform Auditor"),
    ("PlatformSupport", "Platform Support"),
    ("PlatformBilling", "Platform Billing"),
    ("PlatformDevOps", "Platform DevOps"),
    ("PlatformSecurity", "Platform Security"),
]

# Non-human service accounts. Created for completeness because they are real
# roles with real permissions, but they are not presented as logins.
SYSTEM_SERVICE_ACCOUNTS: List[Tuple[str, str]] = [
    ("SystemService", "Service Account - Core Service"),
    ("SystemDevice", "Service Account - Biometric Device"),
    ("SystemWebhook", "Service Account - Webhook Delivery"),
    ("SystemCron", "Service Account - Scheduled Jobs"),
    ("SystemAnalytics", "Service Account - Analytics Pipeline"),
    ("SystemMigration", "Service Account - Data Migration"),
]

# Deliberate non-happy-path accounts, so the auth failure branches are
# reachable without hand-editing the database.
ACCOUNT_STATE_VARIANTS: List[Dict[str, Any]] = [
    {
        "role": "OrgEmployee",
        "label": "Suspended Employee",
        "is_active": 0,
        "is_deleted": 0,
        "note": "is_active=0 -> login returns 423 'Account is suspended'",
    },
    {
        "role": "OrgViewer",
        "label": "Soft-deleted Viewer",
        "is_active": 1,
        "is_deleted": 1,
        "note": "is_deleted=1 -> login returns 401, row is excluded from all queries",
    },
]

DEPARTMENTS = [
    "Administration",
    "Human Resources",
    "Finance",
    "Operations",
]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _role(db: Session, name: str) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if not role:
        raise RuntimeError(
            f"Role '{name}' is missing. Run the RBAC seeder first:\n"
            f"  PYTHONPATH=$PWD ../.venv/bin/python -c "
            f"'from app.db import seed_rbac; from app.db.database import "
            f"SessionLocal; db=SessionLocal(); seed_rbac.seed_all(db); db.commit()'"
        )
    return role


def _get_or_create_org(db: Session, name: str, legal_id: str) -> Organization:
    org = db.query(Organization).filter(Organization.legal_id == legal_id).first()
    if org:
        org.name = name
        org.is_active = True
        db.commit()
        db.refresh(org)
        return org
    org = Organization(name=name, legal_id=legal_id, is_active=True, status="ACTIVE")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _ensure_departments(db: Session, org: Organization) -> Dict[str, Department]:
    out: Dict[str, Department] = {}
    for dept_name in DEPARTMENTS:
        dept = (
            db.query(Department)
            .filter(Department.org_id == org.id, Department.name == dept_name)
            .first()
        )
        if not dept:
            dept = Department(org_id=org.id, name=dept_name)
            db.add(dept)
            db.flush()
        out[dept_name] = dept
    db.commit()
    return out


def _ensure_shift(db: Session, org: Organization) -> Optional[Shift]:
    shift = (
        db.query(Shift)
        .filter(Shift.org_id == org.id, Shift.shift_name == "General Day")
        .first()
    )
    if shift:
        return shift
    shift = Shift(
        org_id=org.id,
        shift_name="General Day",
        start_time="09:00:00",
        end_time="18:00:00",
        grace_period_mins=10,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


def _attach_subscription(
    db: Session, org: Organization, plan: SubscriptionPlan, billing_cycle: str
) -> OrganizationSubscription:
    """Ensure the org has an active subscription on `plan`.

    `organization_id` carries a unique constraint (one subscription per org),
    so this updates the existing row in place rather than adding a second.
    """
    sub = (
        db.query(OrganizationSubscription)
        .filter(OrganizationSubscription.organization_id == org.id)
        .first()
    )
    now = _now()
    if not sub:
        sub = OrganizationSubscription(
            organization_id=org.id,
            subscription_plan_id=plan.id,
            status="active",
            billing_cycle=billing_cycle,
            start_date=now,
            next_renewal=now + timedelta(days=30 if billing_cycle == "monthly" else 365),
            auto_renew=True,
        )
        db.add(sub)
    else:
        sub.subscription_plan_id = plan.id
        sub.status = "active"
        sub.billing_cycle = billing_cycle
        sub.next_renewal = now + timedelta(
            days=30 if billing_cycle == "monthly" else 365
        )
    db.commit()
    db.refresh(sub)
    return sub


def _upsert_user(
    db: Session,
    *,
    org: Organization,
    role: Role,
    dept: Optional[Department],
    shift: Optional[Shift],
    username: str,
    email: str,
    full_name: str,
    employee_id: str,
    password: str,
    is_active: int = 1,
    is_deleted: int = 0,
) -> Tuple[User, str]:
    """Create or update a user. Returns (user, 'created'|'updated')."""
    user = db.query(User).filter(User.email == email).first()
    action = "updated"
    if not user:
        user = User(email=email)
        db.add(user)
        action = "created"

    user.username = username
    user.full_name = full_name
    user.employee_id = employee_id
    user.org_id = org.id
    user.role_id = role.id
    user.dept_id = dept.id if dept else None
    user.shift_id = shift.id if shift else None
    user.hashed_password = get_password_hash(password)
    user.is_active = is_active
    user.is_deleted = is_deleted
    user.enrollment_token = None
    db.commit()
    db.refresh(user)
    return user, action


# --------------------------------------------------------------------------- #
# seeding
# --------------------------------------------------------------------------- #
def _seed_prerequisites(db: Session) -> Dict[str, SubscriptionPlan]:
    """Make sure RBAC and the three plans exist before touching users."""
    from app.db import seed_rbac, seed_subscription

    seed_rbac.seed_all(db)
    db.commit()
    seed_subscription.seed_all(db)
    db.commit()

    plans = {p.code: p for p in db.query(SubscriptionPlan).all()}
    missing = [t["code"] for t in TIERS if t["code"] not in plans]
    if missing:
        raise RuntimeError(f"plans missing after seeding: {missing}")
    return plans


def seed_tier_users(password: str = DEFAULT_PASSWORD) -> List[Dict[str, str]]:
    """Seed every role on every tier. Returns the credential manifest."""
    db = SessionLocal()
    manifest: List[Dict[str, str]] = []
    try:
        plans = _seed_prerequisites(db)

        # ---- platform operators + service accounts (one global org) ------
        plat_org = _get_or_create_org(
            db, PLATFORM_ORG["org_name"], PLATFORM_ORG["legal_id"]
        )
        plat_depts = _ensure_departments(db, plat_org)
        plat_shift = _ensure_shift(db, plat_org)
        # Platform staff are not billed against a customer plan; put them on
        # the unlimited tier so no licence cap can bite during testing.
        _attach_subscription(db, plat_org, plans["enterprise"], "yearly")

        idx = 0
        for role_name, label in PLATFORM_PERSONAS:
            idx += 1
            user, action = _upsert_user(
                db,
                org=plat_org,
                role=_role(db, role_name),
                dept=plat_depts["Administration"],
                shift=plat_shift,
                username=f"pl_{role_name.lower()}",
                email=f"{role_name.lower()}@platform.tierdemo.test",
                full_name=label,
                employee_id=f"TIER-PL-{idx:03d}",
                password=password,
            )
            manifest.append(
                _entry(
                    group="Platform",
                    plan="enterprise (unlimited)",
                    role=role_name,
                    label=label,
                    user=user,
                    action=action,
                    note="platform-wide, not scoped to a customer tenant",
                )
            )

        for role_name, label in SYSTEM_SERVICE_ACCOUNTS:
            idx += 1
            user, action = _upsert_user(
                db,
                org=plat_org,
                role=_role(db, role_name),
                dept=None,
                shift=None,
                username=f"svc_{role_name.lower()}",
                email=f"{role_name.lower()}@service.tierdemo.test",
                full_name=label,
                employee_id=f"TIER-SVC-{idx:03d}",
                password=password,
            )
            manifest.append(
                _entry(
                    group="System (non-human)",
                    plan="enterprise (unlimited)",
                    role=role_name,
                    label=label,
                    user=user,
                    action=action,
                    note="service account, not intended for interactive login",
                )
            )

        # ---- one org per subscription tier, every org role on it ---------
        for tier in TIERS:
            plan = plans[tier["code"]]
            org = _get_or_create_org(db, tier["org_name"], tier["legal_id"])
            depts = _ensure_departments(db, org)
            shift = _ensure_shift(db, org)
            _attach_subscription(db, org, plan, tier["billing_cycle"])

            n = 0
            for role_name, label, dept_name in ORG_PERSONAS:
                n += 1
                username = f"{tier['prefix']}_{role_name.lower()}"
                user, action = _upsert_user(
                    db,
                    org=org,
                    role=_role(db, role_name),
                    dept=depts[dept_name],
                    shift=shift,
                    username=username,
                    email=f"{username}@tierdemo.test",
                    full_name=f"{label} ({tier['code'].title()})",
                    employee_id=f"TIER-{tier['prefix'].upper()}-{n:03d}",
                    password=password,
                )
                manifest.append(
                    _entry(
                        group=f"Organization / {tier['code']}",
                        plan=f"{plan.name} (${plan.monthly_price}/{tier['billing_cycle'][:3]})",
                        role=role_name,
                        label=label,
                        user=user,
                        action=action,
                        note="",
                    )
                )

            # account-state variants, only on the enterprise tenant
            if tier["code"] == "enterprise":
                for variant in ACCOUNT_STATE_VARIANTS:
                    n += 1
                    username = f"{tier['prefix']}_{variant['role'].lower()}_{'susp' if not variant['is_active'] else 'del'}"
                    user, action = _upsert_user(
                        db,
                        org=org,
                        role=_role(db, variant["role"]),
                        dept=depts["Operations"],
                        shift=shift,
                        username=username,
                        email=f"{username}@tierdemo.test",
                        full_name=f"{variant['label']} (Enterprise)",
                        employee_id=f"TIER-{tier['prefix'].upper()}-{n:03d}",
                        password=password,
                        is_active=variant["is_active"],
                        is_deleted=variant["is_deleted"],
                    )
                    manifest.append(
                        _entry(
                            group="Organization / enterprise",
                            plan=f"{plan.name} (account state)",
                            role=variant["role"],
                            label=variant["label"],
                            user=user,
                            action=action,
                            note=variant["note"],
                        )
                    )
        return manifest
    finally:
        db.close()


def _entry(**kw: Any) -> Dict[str, str]:
    user: User = kw["user"]
    return {
        "group": kw["group"],
        "plan": kw["plan"],
        "role": kw["role"],
        "label": kw["label"],
        "username": user.username,
        "email": user.email,
        "employee_id": user.employee_id,
        "org": user.organization.name if user.organization else "",
        "user_id": str(user.id),
        "action": kw["action"],
        "note": kw["note"],
    }


def print_manifest(manifest: List[Dict[str, str]], password: str) -> None:
    line = "=" * 108
    print(f"\n{line}\nSEED MANIFEST  ({len(manifest)} accounts)\n{line}")
    print(f"{'GROUP':<32} {'ROLE':<20} {'USERNAME':<24} {'EMAIL'}")
    print("-" * 108)
    current = None
    for e in manifest:
        if e["group"] != current:
            current = e["group"]
            print(f"\n[{current}]  plan: {e['plan']}")
        print(f"  {e['role']:<28} {e['username']:<24} {e['email']}")
        if e["note"]:
            print(f"      note: {e['note']}")
    print(f"\n{line}")
    print(f"Password for every account above: {password}")
    print(f"Login: POST /api/v1/auth/login  (form fields: username, password)")
    print(f"  The `username` form field matches either the email OR the username above.")
    print(f"Login page: POST /api/v1/auth/login -> returns a JWT access token.")
    print(f"{line}\n")


def main() -> int:
    try:
        manifest = seed_tier_users()
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"seeding failed: {exc}", file=sys.stderr)
        return 1
    print_manifest(manifest, DEFAULT_PASSWORD)
    created = sum(1 for e in manifest if e["action"] == "created")
    print(f"created={created} updated={len(manifest) - created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
