"""
Create (or update) a single named SuperAdmin account.

A SuperAdmin is a `platform`-tier role, but `users.org_id` is NOT NULL, so the
account still has to hang off some organization. Platform operators are put in
the platform-operations tenant on the unlimited plan, so no licence cap can
interfere with platform-level testing.

`users.email`, `users.username` and `users.employee_id` all carry unique
indexes, so re-running updates the same row rather than failing or duplicating.

Usage:
    cd backend
    PYTHONPATH=$PWD ../.venv/bin/python -m app.db.create_superadmin
    PYTHONPATH=$PWD ../.venv/bin/python -m app.db.create_superadmin \\
        --email root@visioncore.com --username root --password 'S3cret!Pass'
"""
from __future__ import annotations

import argparse
import sys
import uuid
from typing import Optional

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

DEFAULT_USERNAME = "superadmin.ops"
DEFAULT_EMAIL = "superadmin@visioncore.com"
DEFAULT_PASSWORD = "SuperAdmin@2026!"
DEFAULT_FULL_NAME = "Super Administrator"

# Reuse the platform tenant created by `seed_tier_users` when it exists, so
# SuperAdmins are not scattered across unrelated test organizations.
PLATFORM_LEGAL_ID = "TIERDEMO-PLATFORM"
FALLBACK_ORG_NAME = "Platform Operations"


def _ensure_platform_org(db: Session) -> Organization:
    org = db.query(Organization).filter(Organization.legal_id == PLATFORM_LEGAL_ID).first()
    if not org:
        org = Organization(
            name=FALLBACK_ORG_NAME,
            legal_id=PLATFORM_LEGAL_ID,
            is_active=True,
            status="ACTIVE",
        )
        db.add(org)
        db.commit()
        db.refresh(org)

    # Platform staff are not billed to a customer; park them on the unlimited
    # tier so licensing limits cannot mask a real authorization bug.
    plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.code == "enterprise")
        .first()
    )
    if plan:
        sub = (
            db.query(OrganizationSubscription)
            .filter(OrganizationSubscription.organization_id == org.id)
            .first()
        )
        if not sub:
            sub = OrganizationSubscription(
                organization_id=org.id,
                subscription_plan_id=plan.id,
                status="active",
                billing_cycle="yearly",
            )
            db.add(sub)
        else:
            sub.subscription_plan_id = plan.id
            sub.status = "active"
        db.commit()
    return org


def _superadmin_role(db: Session) -> Role:
    from app.db import seed_rbac

    role = db.query(Role).filter(Role.name == "SuperAdmin").first()
    if not role:
        seed_rbac.seed_all(db)
        db.commit()
        role = db.query(Role).filter(Role.name == "SuperAdmin").first()
    if not role:
        raise RuntimeError("could not resolve the SuperAdmin role")
    return role


def create_superadmin(
    *,
    email: str = DEFAULT_EMAIL,
    username: str = DEFAULT_USERNAME,
    password: str = DEFAULT_PASSWORD,
    full_name: str = DEFAULT_FULL_NAME,
) -> dict[str, str]:
    db = SessionLocal()
    try:
        org = _ensure_platform_org(db)
        role = _superadmin_role(db)

        dept = (
            db.query(Department)
            .filter(Department.org_id == org.id, Department.name == "Administration")
            .first()
        )
        if not dept:
            dept = Department(org_id=org.id, name="Administration")
            db.add(dept)
            db.flush()

        shift = (
            db.query(Shift)
            .filter(Shift.org_id == org.id, Shift.shift_name == "General Day")
            .first()
        )
        if not shift:
            shift = Shift(
                org_id=org.id,
                shift_name="General Day",
                start_time="09:00:00",
                end_time="18:00:00",
            )
            db.add(shift)
            db.flush()

        user = db.query(User).filter(User.email == email).first()
        action = "updated"
        if not user:
            user = User(email=email)
            db.add(user)
            action = "created"

        clash = (
            db.query(User)
            .filter(User.username == username, User.email != email)
            .first()
        )
        if clash:
            raise RuntimeError(
                f"username '{username}' is already used by {clash.email}. "
                f"Pass a different --username."
            )

        user.username = username
        user.full_name = full_name
        user.hashed_password = get_password_hash(password)
        user.org_id = org.id
        user.role_id = role.id
        user.dept_id = dept.id
        user.shift_id = shift.id
        user.is_active = 1
        user.is_deleted = 0
        # A pre-set enrolment token would block face re-enrolment.
        user.enrollment_token = None
        if not user.employee_id or db.query(User).filter(
            User.employee_id == (user.employee_id or ""), User.email != email
        ).first():
            user.employee_id = f"SA-{uuid.uuid4().hex[:8].upper()}"
        db.commit()
        db.refresh(user)
        # Resolve the display values now: the session is closed in `finally`,
        # and touching `user.role` / `user.organization` afterwards would
        # raise DetachedInstanceError.
        return {
            "action": action,
            "user_id": str(user.id),
            "full_name": user.full_name,
            "username": user.username,
            "email": user.email,
            "employee_id": user.employee_id,
            "role": role.name,
            "role_tier": role.tier,
            "org": org.name,
        }
    finally:
        db.close()


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Create/update a SuperAdmin account")
    p.add_argument("--email", default=DEFAULT_EMAIL)
    p.add_argument("--username", default=DEFAULT_USERNAME)
    p.add_argument("--password", default=DEFAULT_PASSWORD)
    p.add_argument("--full-name", default=DEFAULT_FULL_NAME)
    args = p.parse_args(argv)

    try:
        info = create_superadmin(
            email=args.email,
            username=args.username,
            password=args.password,
            full_name=args.full_name,
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"failed: {exc}", file=sys.stderr)
        return 1

    print(f"SuperAdmin {info['action']}:")
    print(f"  user id     : {info['user_id']}")
    print(f"  full name   : {info['full_name']}")
    print(f"  username    : {info['username']}")
    print(f"  email       : {info['email']}")
    print(f"  password    : {args.password}")
    print(f"  employee id : {info['employee_id']}")
    print(f"  role        : {info['role']} (tier={info['role_tier']})")
    print(f"  org         : {info['org']}")
    print(f"\n  login: POST /api/v1/auth/login  "
          f"username={info['username']} (or {info['email']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
