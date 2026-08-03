"""
tenant_provisioning.py — Enterprise Tenant Provisioning Engine
Sprint 6 — Phase A: Multi-Tenant SaaS Hardening & Tenant Provisioning

Atomic, transaction-safe organization bootstrap pipeline:
  Organization → Departments → Roles → Permissions → Subscription → Branding → Config → Admin

Any failure rolls back the entire transaction.
No frozen modules are modified.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.security import get_password_hash, validate_password_strength
from app.db.models.all_models import (
    Organization, Department, Role, User, SubscriptionPlan, OrganizationSubscription,
    SystemSetting, Permission, RolePermission
)
from app.services.organization_service import organization_service
from app.services.tenant_lifecycle import TenantLifecycleService, TenantLifecycleState
from app.services.tenant_branding import TenantBrandingService
from app.services.config_center import config_center
from app.events.event_types import (
    OrganizationCreatedEvent, TenantProvisionedEvent
)
from app.events.event_bus import event_bus

logger = logging.getLogger(__name__)


@dataclass
class TenantProvisioningResult:
    """Result of a successful tenant provisioning operation."""
    organization_id: str
    organization_name: str
    admin_user_id: int
    admin_email: str
    admin_username: str
    subscription_plan_id: int
    subscription_plan_name: str
    provisioning_time_ms: float = 0.0
    created_entities: dict = field(default_factory=lambda: {
        "organization": False,
        "departments": [],
        "roles": [],
        "permissions": [],
        "subscription": False,
        "branding": False,
        "config": False,
        "admin_user": False,
    })


class TenantProvisioningService:
    """
    Enterprise Tenant Provisioning Engine.

    Provides atomic, transaction-safe provisioning of new organizations.
    Uses the existing OrganizationService, EventBus, ConfigCenter, and
    subscription infrastructure without modifying any frozen modules.
    """

    def __init__(self):
        self.lifecycle = TenantLifecycleService()
        self.branding = TenantBrandingService()

    # ──────────────────────────────────────────────────────────────────────
    #  Core Provisioning Pipeline
    # ──────────────────────────────────────────────────────────────────────

    def provision_tenant(
        self,
        *,
        db: Session,
        organization_name: str,
        admin_email: str,
        admin_password: str,
        admin_full_name: str,
        admin_username: Optional[str] = None,
        legal_id: Optional[str] = None,
        subscription_plan_code: str = "starter",
        locale: str = "en-US",
        timezone_str: str = "UTC",
        currency: str = "USD",
    ) -> TenantProvisioningResult:
        """
        Atomically provision a complete multi-tenant organization.

        Steps:
        1. Create Organization
        2. Seed default Departments
        3. Seed default Roles & Permissions
        4. Assign default Subscription
        5. Set default Branding
        6. Set default Configuration
        7. Create Admin User
        8. Publish TenantProvisionedEvent

        If any step fails, the entire transaction is rolled back.
        """
        import time
        start_time = time.time()

        result = TenantProvisioningResult(
            organization_name=organization_name,
            admin_email=admin_email,
        )

        # Validate password strength
        pw_ok, pw_err = validate_password_strength(admin_password)
        if not pw_ok:
            raise ValueError(f"Invalid admin password: {pw_err}")

        try:
            # ── Step 1: Create Organization ──
            if not legal_id:
                legal_id = f"TENANT-{organization_name.upper()[:6]}-{int(datetime.now(timezone.utc).timestamp())}"

            org = organization_service.create_organization(db=db, org_in={
                "name": organization_name,
                "legal_id": legal_id,
                "is_active": True,
                "primary_color": "#4F46E5",
            })
            org_id = org.id
            result.organization_id = str(org_id)
            result.created_entities["organization"] = True
            logger.info(f"Tenant: Created organization {org_id} ({organization_name})")

            # Set lifecycle to Draft
            self.lifecycle.set_state(db, org_id, TenantLifecycleState.DRAFT, actor_user_id=None)

            # ── Step 2: Seed Default Departments ──
            default_depts = [
                ("Operations", "Default operations department"),
                ("Human Resources", "Default HR department"),
                ("Finance", "Default finance department"),
                ("Engineering", "Default engineering department"),
                ("Sales & Marketing", "Default sales and marketing department"),
            ]
            dept_ids = []
            for dept_name, dept_desc in default_depts:
                dept = Department(
                    org_id=org_id,
                    name=dept_name,
                    description=dept_desc,
                    is_deleted=0,
                )
                db.add(dept)
                db.flush()
                dept_ids.append(dept.id)
                result.created_entities["departments"].append(dept_name)
            logger.info(f"Tenant: Seeded {len(default_depts)} departments")

            # ── Step 3: Seed Default Roles & Permissions ──
            # Use existing OrganizationService's seed_default_permissions
            organization_service.initialize_workspace(db=db, org_id=org_id)
            result.created_entities["roles"] = ["SuperAdmin", "Admin", "Manager", "Employee"]
            result.created_entities["permissions"] = True
            logger.info(f"Tenant: Seeded default roles and permissions")

            # ── Step 4: Assign Default Subscription Plan ──
            plan = db.query(SubscriptionPlan).filter(
                SubscriptionPlan.code == subscription_plan_code,
                SubscriptionPlan.is_active == True
            ).first()

            if not plan:
                # Fallback to first available plan
                plan = db.query(SubscriptionPlan).filter(
                    SubscriptionPlan.is_active == True
                ).order_by(SubscriptionPlan.tier).first()

            if plan:
                sub = OrganizationSubscription(
                    organization_id=org_id,
                    subscription_plan_id=plan.id,
                    status="trialing",
                    billing_cycle="monthly",
                    start_date=datetime.now(timezone.utc),
                    trial_end=datetime.now(timezone.utc).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ).replace(day=min(28, datetime.now(timezone.utc).day + 14)),
                    auto_renew=True,
                )
                db.add(sub)
                db.flush()
                result.subscription_plan_id = plan.id
                result.subscription_plan_name = plan.name
                result.created_entities["subscription"] = True
                logger.info(f"Tenant: Assigned subscription plan '{plan.code}'")
            else:
                logger.warning(f"Tenant: No subscription plan found for '{subscription_plan_code}'")

            # ── Step 5: Set Default Branding ──
            self.branding.initialize_defaults(db, org_id)
            result.created_entities["branding"] = True
            logger.info(f"Tenant: Initialized default branding")

            # ── Step 6: Set Default Configuration ──
            # Use ConfigCenter for tenant-specific configs
            org_configs = {
                "locale": locale,
                "timezone": timezone_str,
                "currency": currency,
                "attendance.grace_period_minutes": 15,
                "attendance.checkin_cooldown_minutes": 5,
                "system.session_timeout_minutes": 60,
                "system.password_min_length": 8,
                "security.require_mfa": False,
                "notifications.rate_limit_per_user": 100,
            }
            for key, value in org_configs.items():
                try:
                    config_center.set(key, value, org_id=str(org_id))
                except ValueError:
                    pass  # Skip unknown config keys
            result.created_entities["config"] = True
            logger.info(f"Tenant: Applied default configuration")

            # ── Step 7: Create Admin User ──
            # Use the existing create_workspace_owner method
            try:
                owner_context = organization_service.create_workspace_owner_and_seed(
                    db=db,
                    workspace_name=organization_name,
                    owner_name=admin_full_name,
                    owner_email=admin_email,
                    password=admin_password,
                )
                result.admin_user_id = owner_context.owner_user_id
                result.admin_username = admin_email.split("@")[0]
                result.created_entities["admin_user"] = True
                logger.info(f"Tenant: Created admin user {admin_email} (id={owner_context.owner_user_id})")
            except ValueError as e:
                logger.error(f"Tenant: Failed to create admin user: {e}")
                raise

            # ── Step 8: Move lifecycle to Pending Verification ──
            self.lifecycle.set_state(
                db, org_id, TenantLifecycleState.PENDING_VERIFICATION,
                actor_user_id=result.admin_user_id,
                reason="Tenant provisioned, pending verification"
            )

            # ── Step 9: Publish Events ──
            provisioning_ms = (time.time() - start_time) * 1000
            result.provisioning_time_ms = round(provisioning_ms, 2)

            try:
                # Publish OrganizationCreatedEvent
                org_created = OrganizationCreatedEvent(
                    organization_id=str(org_id),
                    org_name=organization_name,
                    created_by_user_id=result.admin_user_id,
                )
                event_bus.publish(org_created)

                # Publish TenantProvisionedEvent
                provisioned = TenantProvisionedEvent(
                    organization_id=str(org_id),
                    org_name=organization_name,
                    admin_user_id=result.admin_user_id,
                    admin_email=admin_email,
                    subscription_plan=result.subscription_plan_name,
                    provisioning_time_ms=result.provisioning_time_ms,
                )
                event_bus.publish(provisioned)
            except Exception as e:
                logger.warning(f"Tenant: Event publishing failed (non-fatal): {e}")

            # Commit the transaction
            db.commit()
            logger.info(
                f"Tenant: Provisioning complete for {organization_name} "
                f"({result.provisioning_time_ms}ms)"
            )

            return result

        except IntegrityError as e:
            db.rollback()
            logger.error(f"Tenant: Integrity error during provisioning: {e}")
            raise ValueError(f"Tenant provisioning failed due to uniqueness constraint: {e}") from e

        except Exception as e:
            db.rollback()
            logger.error(f"Tenant: Provisioning failed, transaction rolled back: {e}")
            raise

    # ──────────────────────────────────────────────────────────────────────
    #  Helper: Quick Provision (CLI-friendly)
    # ──────────────────────────────────────────────────────────────────────

    def quick_provision(
        self,
        *,
        db: Session,
        company_name: str,
        admin_email: str,
        admin_password: str,
    ) -> TenantProvisioningResult:
        """
        Simplified provisioning for development/testing/CLI.

        Uses sensible defaults for all optional parameters.
        """
        return self.provision_tenant(
            db=db,
            organization_name=company_name,
            admin_email=admin_email,
            admin_password=admin_password,
            admin_full_name="System Administrator",
        )

    # ──────────────────────────────────────────────────────────────────────
    #  Tenant Verification
    # ──────────────────────────────────────────────────────────────────────

    def verify_tenant(self, *, db: Session, org_id: str) -> dict:
        """
        Verify that a tenant is fully provisioned and all required
        entities exist.
        """
        from uuid import UUID
        org_uuid = UUID(org_id)

        org = db.query(Organization).filter(Organization.id == org_uuid).first()
        if not org:
            return {"verified": False, "error": "Organization not found"}

        dept_count = db.query(Department).filter(
            Department.org_id == org_uuid, Department.is_deleted == 0
        ).count()

        user_count = db.query(User).filter(
            User.org_id == org_uuid, User.is_deleted == 0
        ).count()

        sub = db.query(OrganizationSubscription).filter(
            OrganizationSubscription.organization_id == org_uuid
        ).first()

        issues = []
        if dept_count == 0:
            issues.append("No departments found")
        if user_count == 0:
            issues.append("No users found")
        if not sub:
            issues.append("No subscription assigned")

        # Check lifecycle state
        state = self.lifecycle.get_state(db, org_uuid)

        return {
            "verified": len(issues) == 0,
            "organization_id": str(org.id),
            "organization_name": org.name,
            "lifecycle_state": state.value if state else "unknown",
            "departments": dept_count,
            "users": user_count,
            "has_subscription": sub is not None,
            "subscription_plan": sub.plan.name if sub else None,
            "issues": issues,
        }


# Singleton
tenant_provisioning_service = TenantProvisioningService()
