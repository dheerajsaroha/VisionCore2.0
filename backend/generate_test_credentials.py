#!/usr/bin/env python3
"""
generate_test_credentials.py — VisionCore v2.0
Sprint 2 — Manual Testing Credentials Generator

Audits the database, RBAC seeders, authentication seeders, organization seeders,
and user tables. Generates (or creates if missing) one active test account for
every role with known credentials.

Idempotent — safe to run multiple times.

Deliverables:
  backend/manual_test_credentials.md
  backend/manual_test_credentials.json
"""
from __future__ import annotations

import json
import logging
import os
import sys
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ── Path Setup ──────────────────────────────────────────────────────────────
PYTHONPATH = os.path.join(os.path.dirname(__file__))
if PYTHONPATH not in sys.path:
    sys.path.insert(0, PYTHONPATH)

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models.all_models import (
    User, Role, Organization, SubscriptionPlan, OrganizationSubscription,
)
from app.core.security import get_password_hash, create_access_token
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

PASSWORD = "Vision@123"
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


# =============================================================================
#  Mail-format helpers
# =============================================================================

def _email_for_role(role_name: str) -> str:
    """Convert role name to deterministic email."""
    mapping = {
        "SuperAdmin": "superadmin@test.local",
        "PlatformAdmin": "platformadmin@test.local",
        "PlatformViewer": "platformviewer@test.local",
        "PlatformAuditor": "platformauditor@test.local",
        "PlatformSupport": "platformsupport@test.local",
        "PlatformBilling": "platformbilling@test.local",
        "PlatformDevOps": "platformdevops@test.local",
        "PlatformSecurity": "platformsecurity@test.local",
        "OrgAdmin": "orgadmin@test.local",
        "OrgManager": "manager@test.local",
        "OrgHR": "hr@test.local",
        "OrgFinance": "finance@test.local",
        "OrgSupervisor": "supervisor@test.local",
        "OrgTeamLead": "teamlead@test.local",
        "OrgEmployee": "employee@test.local",
        "OrgContractor": "contractor@test.local",
        "OrgIntern": "intern@test.local",
        "OrgViewer": "viewer@test.local",
        "OrgDepartmentHead": "depthead@test.local",
        "OrgShiftManager": "shiftmanager@test.local",
        "SystemService": "systemservice@test.local",
        "SystemDevice": "systemdevice@test.local",
        "SystemWebhook": "systemwebhook@test.local",
        "SystemCron": "systemcron@test.local",
        "SystemAnalytics": "systemanalytics@test.local",
        "SystemMigration": "systemmigration@test.local",
    }
    return mapping.get(role_name, f"{role_name.lower().replace(' ', '_')}@test.local")


def _username_for_role(role_name: str) -> str:
    """Convert role name to deterministic username."""
    return role_name.lower().replace(" ", "").replace("admin", "admin")


def _employee_id(index: int) -> str:
    """Generate deterministic employee ID."""
    return f"EMP-{index:06d}"


# =============================================================================
#  MAIN GENERATION
# =============================================================================

def main() -> None:
    logger.info("=" * 80)
    logger.info("VISIONCORE v2.0 — MANUAL TESTING CREDENTIALS GENERATOR")
    logger.info("=" * 80)

    db: Session = SessionLocal()

    # ── Step 1: Seed required data (idempotent) ─────────────────────────
    logger.info("\n📦 Step 1: Seeding required data...")

    # Seed RBAC
    from app.db.seed_rbac import seed_all as seed_rbac
    try:
        rbac_stats = seed_rbac(db)
        logger.info(f"  ✅ RBAC seeded: {rbac_stats}")
    except Exception as e:
        logger.error(f"  ❌ RBAC seeding failed: {e}")
        db.close()
        sys.exit(1)

    # Seed subscription
    from app.db.seed_subscription import seed_all as seed_subscription
    try:
        sub_stats = seed_subscription(db)
        logger.info(f"  ✅ Subscription seeded: {sub_stats}")
    except Exception as e:
        logger.error(f"  ❌ Subscription seeding failed: {e}")
        db.close()
        sys.exit(1)

    # ── Step 2: Discover all roles ─────────────────────────────────────
    logger.info("\n📋 Step 2: Discovering roles...")
    roles = db.query(Role).order_by(Role.tier, Role.name).all()
    role_names = [r.name for r in roles]
    logger.info(f"  Found {len(roles)} roles: {', '.join(role_names)}")

    # ── Step 3: Find primary organization ──────────────────────────────
    logger.info("\n🏢 Step 3: Finding/creating organization...")
    org = db.query(Organization).order_by(Organization.created_at).first()
    if not org:
        org = Organization(
            name="VisionCore Demo",
            legal_id=f"VC-DEMO-{uuid_mod.uuid4().hex[:8].upper()}",
            primary_color="#4F46E5",
        )
        db.add(org)
        db.commit()
        db.refresh(org)
        logger.info(f"  ✅ Created organization: {org.name} ({org.id})")
    else:
        logger.info(f"  ✅ Using existing organization: {org.name} ({org.id})")

    # ── Step 4: Ensure subscription assigned to org ────────────────────
    logger.info("\n📄 Step 4: Ensuring subscription assignment...")
    existing_sub = db.query(OrganizationSubscription).filter(
        OrganizationSubscription.organization_id == org.id
    ).first()
    if existing_sub:
        plan_name = existing_sub.plan.name if existing_sub.plan else "Unknown"
        logger.info(f"  ✅ Subscription exists: {plan_name} ({existing_sub.status})")
    else:
        starter_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "starter").first()
        if starter_plan:
            from datetime import datetime, timezone
            new_sub = OrganizationSubscription(
                organization_id=org.id,
                subscription_plan_id=starter_plan.id,
                status="active",
                billing_cycle="monthly",
                start_date=datetime.now(timezone.utc),
                auto_renew=True,
            )
            db.add(new_sub)
            db.commit()
            logger.info(f"  ✅ Assigned Starter plan to organization")
        else:
            logger.warning("  ⚠️ Starter plan not found — no subscription assigned")

    # ── Step 5: Create missing users ───────────────────────────────────
    logger.info("\n👤 Step 5: Creating missing users...")
    created_users: List[Dict[str, Any]] = []
    existing_users: List[Dict[str, Any]] = []
    employee_counter = 1

    for role in roles:
        email = _email_for_role(role.name)
        username = _username_for_role(role.name)

        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            # Update password to ensure consistency
            existing_user.hashed_password = get_password_hash(PASSWORD)
            existing_user.is_active = 1
            existing_user.is_deleted = 0
            db.add(existing_user)
            info = {
                "role": role.name,
                "username": existing_user.username,
                "email": existing_user.email,
                "employee_id": existing_user.employee_id,
                "password": PASSWORD,
                "organization": org.name,
            }
            existing_users.append(info)
            logger.info(f"  ✅ Updated existing: {email} (role={role.name})")
            continue

        # Determine employee ID
        while True:
            emp_id = _employee_id(employee_counter)
            dup = db.query(User).filter(User.employee_id == emp_id).first()
            if not dup:
                break
            employee_counter += 1

        # Create user
        new_user = User(
            org_id=org.id,
            role_id=role.id,
            full_name=f"Test {role.name}",
            username=username,
            email=email,
            employee_id=emp_id,
            hashed_password=get_password_hash(PASSWORD),
            is_active=1,
            is_deleted=0,
        )
        db.add(new_user)
        db.flush()
        info = {
            "role": role.name,
            "username": username,
            "email": email,
            "employee_id": emp_id,
            "password": PASSWORD,
            "organization": org.name,
        }
        created_users.append(info)
        logger.info(f"  ✅ Created: {email} (role={role.name}, emp_id={emp_id})")
        employee_counter += 1

    db.commit()
    logger.info(f"\n  Summary: {len(created_users)} created, {len(existing_users)} updated")

    # ── Step 6: Collect all users ──────────────────────────────────────
    all_users = created_users + existing_users

    # ── Step 7: Verify authentication for every account ────────────────
    logger.info("\n🔐 Step 7: Verifying authentication...")
    verified_users: List[Dict[str, Any]] = []
    failed_users: List[Dict[str, Any]] = []

    for user_info in all_users:
        role_name = user_info["role"]
        email = user_info["email"]

        r = client.post("/api/v1/auth/login", data={
            "username": email,
            "password": PASSWORD,
        })
        if r.status_code == 200:
            token = r.json().get("access_token")
            # Verify /users/me
            r2 = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
            me_ok = r2.status_code == 200

            # Verify permissions resolution
            r3 = client.get("/api/v1/rbac/me/permissions", headers={"Authorization": f"Bearer {token}"})
            perm_count = len(r3.json().get("permissions", [])) if r3.status_code == 200 else 0

            # Verify subscription resolution
            r4 = client.get("/api/v1/subscription/my/subscription", headers={"Authorization": f"Bearer {token}"})
            sub_plan = "Unknown"
            if r4.status_code == 200:
                sub_plan = r4.json().get("plan_name", "Unknown")
            elif r4.status_code == 404:
                sub_plan = "None"

            user_info["auth_status"] = "✅ Active"
            user_info["me_endpoint"] = "✅ OK" if me_ok else "❌ Failed"
            user_info["permission_count"] = perm_count
            user_info["subscription_plan"] = sub_plan
            user_info["status"] = "Active"
            verified_users.append(user_info)
            logger.info(f"  ✅ {email:35s} | JWT ✅ | Permissions: {perm_count:3d} | Plan: {sub_plan}")
        else:
            user_info["auth_status"] = f"❌ Login failed ({r.status_code})"
            user_info["me_endpoint"] = "❌"
            user_info["permission_count"] = 0
            user_info["subscription_plan"] = "Unknown"
            user_info["status"] = "Inactive"
            failed_users.append(user_info)
            logger.error(f"  ❌ {email} — AUTH FAILED (HTTP {r.status_code})")

    # ── Step 8: Build output table ─────────────────────────────────────
    logger.info("\n" + "=" * 80)
    logger.info("MANUAL TESTING CREDENTIALS — COMPLETE")
    logger.info("=" * 80)

    # ── Report failures first ──────────────────────────────────────────
    if failed_users:
        logger.error(f"\n{'!' * 70}")
        logger.error(f"FAILED AUTHENTICATION — {len(failed_users)} account(s)")
        logger.error(f"{'!' * 70}")
        for u in failed_users:
            logger.error(f"  ❌ {u['email']} — {u['auth_status']}")
        logger.error(f"\nRoot cause analysis required before continuing.")
        logger.error(f"Fix the defect, re-run this script, and only then use the credentials.\n")
    else:
        logger.info(f"\n  ✅ All {len(verified_users)} accounts authenticated successfully.\n")

    # ── Credential table ───────────────────────────────────────────────
    table_header = (
        f"| {'Role':25s} | {'Username':20s} | {'Email':30s} | {'Password':12s} | "
        f"{'Organization':20s} | {'Subscription':16s} | {'Status':8s} | {'Permissions':>5s} |"
    )
    table_sep = "| " + "-"*25 + " | " + "-"*20 + " | " + "-"*30 + " | " + "-"*12 + " | " + \
                "-"*20 + " | " + "-"*16 + " | " + "-"*8 + " | " + "-"*5 + " |"

    logger.info(f"\n{table_sep}")
    logger.info(table_header)
    logger.info(table_sep)

    for u in verified_users:
        row = (
            f"| {u['role']:25s} | {u['username']:20s} | {u['email']:30s} | {u['password']:12s} | "
            f"{u['organization']:20s} | {u.get('subscription_plan', 'N/A'):16s} | "
            f"{u['status']:8s} | {u.get('permission_count', 0):5d} |"
        )
        logger.info(row)
    logger.info(table_sep)

    # ── API Testing Information ────────────────────────────────────────
    logger.info(f"\n{'=' * 80}")
    logger.info("API TESTING ENDPOINTS")
    logger.info(f"{'=' * 80}")
    logger.info("""
Authentication:
  POST /api/v1/auth/login      — Login (form data: username, password)
  POST /api/v1/auth/refresh    — Refresh token
  POST /api/v1/auth/logout     — Logout (requires Authorization header)

Current User:
  GET  /api/v1/users/me        — Current user profile

Permissions:
  GET  /api/v1/rbac/me/permissions  — Effective permissions for current user

Subscription:
  GET  /api/v1/subscription/my/subscription  — Current subscription details
  GET  /api/v1/subscription/my/features      — Enabled features

Organization:
  GET  /api/v1/org/current     — Current organization details
""")

    # ── Save credentials ───────────────────────────────────────────────
    md_path = os.path.join(OUTPUT_DIR, "manual_test_credentials.md")
    json_path = os.path.join(OUTPUT_DIR, "manual_test_credentials.json")

    # Markdown
    md_lines = [
        "# VisionCore v2.0 — Manual Testing Credentials",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Password: `{PASSWORD}`",
        "",
        "## Credential Table",
        "",
        table_header.replace("| ", "| "),
        table_sep.replace("| ", "| "),
    ]
    for u in verified_users:
        row = (
            f"| {u['role']} | {u['username']} | {u['email']} | {u['password']} | "
            f"{u['organization']} | {u.get('subscription_plan', 'N/A')} | "
            f"{u['status']} | {u.get('permission_count', 0)} |"
        )
        md_lines.append(row)

    md_lines.extend([
        "",
        "## API Testing Endpoints",
        "",
        "### Authentication",
        "",
        "```",
        "POST /api/v1/auth/login",
        "POST /api/v1/auth/refresh",
        "POST /api/v1/auth/logout",
        "```",
        "",
        "### Current User",
        "",
        "```",
        "GET /api/v1/users/me",
        "```",
        "",
        "### Permissions",
        "",
        "```",
        "GET /api/v1/rbac/me/permissions",
        "```",
        "",
        "### Subscription",
        "",
        "```",
        "GET /api/v1/subscription/my/subscription",
        "GET /api/v1/subscription/my/features",
        "```",
        "",
        "### Organization",
        "",
        "```",
        "GET /api/v1/org/current",
        "```",
        "",
        "---",
        f"*{len(verified_users)} accounts generated — {PASSWORD}*",
    ])
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines) + "\n")

    # JSON
    json_data = {
        "metadata": {
            "suite": "Manual Testing Credentials",
            "sprint": "Sprint 2",
            "entity": "Subscription & Feature Management",
            "password": PASSWORD,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_accounts": len(verified_users),
            "failed_accounts": len(failed_users),
        },
        "accounts": verified_users,
        "failed_accounts": failed_users if failed_users else None,
        "api_endpoints": {
            "auth": {
                "login": "POST /api/v1/auth/login",
                "refresh": "POST /api/v1/auth/refresh",
                "logout": "POST /api/v1/auth/logout",
            },
            "current_user": {
                "me": "GET /api/v1/users/me",
            },
            "permissions": {
                "my_permissions": "GET /api/v1/rbac/me/permissions",
            },
            "subscription": {
                "my_subscription": "GET /api/v1/subscription/my/subscription",
                "my_features": "GET /api/v1/subscription/my/features",
            },
            "organization": {
                "current": "GET /api/v1/org/current",
            },
        },
    }
    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2, default=str)

    logger.info(f"\n📁 Credentials saved to:")
    logger.info(f"  📄 {md_path}")
    logger.info(f"  📄 {json_path}")

    # ── Final validation report ────────────────────────────────────────
    logger.info(f"\n{'=' * 80}")
    logger.info("FINAL VALIDATION REPORT")
    logger.info(f"{'=' * 80}")

    all_ok = True
    for u in verified_users:
        checks = [
            (u.get("auth_status") == "✅ Active", "Authentication"),
            (u.get("me_endpoint") == "✅ OK", "/users/me"),
            (u.get("status") == "Active", "Active status"),
            (u.get("organization") == org.name, "Org assignment"),
        ]
        for ok, check_name in checks:
            if not ok:
                logger.error(f"  ❌ {u['email']} — {check_name} FAILED")
                all_ok = False

    if all_ok:
        logger.info(f"\n  ✅ All {len(verified_users)} accounts validated successfully.")
        logger.info(f"  ✅ Ready for manual UI and API testing.")
    else:
        logger.error(f"\n  ❌ Some accounts failed validation — inspect logs above.")

    db.close()

    if failed_users:
        logger.error(f"\n{'!' * 70}")
        logger.error(f"STOP — {len(failed_users)} accounts failed authentication.")
        logger.error(f"Fix the root cause and re-run this script.")
        logger.error(f"{'!' * 70}")
        sys.exit(1)

    logger.info(f"\n{'=' * 80}")
    logger.info("CREDENTIAL GENERATION COMPLETE")
    logger.info(f"{'=' * 80}")


if __name__ == "__main__":
    main()

