"""
subscription_service.py — Subscription & Feature Management Business Logic Layer (Sprint 2, Entity 2)

Provides:
- Plan assignment/upgrade/downgrade
- Subscription cancel/renew
- Feature resolution for an organization
- Licensing limit enforcement
- Feature dependency checking
- Subscription status management
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.all_models import (
    SubscriptionPlan,
    OrganizationSubscription,
    Feature,
    PlanFeature,
    FeatureFlag,
    LicensingLimit,
    Organization,
)
from app.crud.crud_subscription import (
    subscription_plan_crud,
    org_subscription_crud,
    feature_crud,
    feature_flag_crud,
    licensing_limit_crud,
)
from app.db.seed_subscription import seed_all as seed_subscription_data

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service layer for subscription and feature management business logic."""

    # ── Plan Operations ──────────────────────────────────────────────────────

    @staticmethod
    def assign_plan_to_org(
        db: Session,
        org_id: UUID,
        plan_id: int,
        billing_cycle: str = "monthly",
        actor_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Assign a subscription plan to an organization.

        If an active subscription exists, it will be ended first.
        """
        result = {"success": False, "message": "", "subscription": None}

        # Check org exists
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            result["message"] = f"Organization {org_id} not found"
            return result

        # Check plan exists
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == plan_id, SubscriptionPlan.is_active == True
        ).first()
        if not plan:
            result["message"] = f"Plan id={plan_id} not found or inactive"
            return result

        # Check existing subscription for this org
        existing = org_subscription_crud.get_by_org(db, org_id)
        now = datetime.now(timezone.utc)
        end_date = None
        if billing_cycle == "monthly":
            end_date = now + timedelta(days=30)
        elif billing_cycle == "yearly":
            end_date = now + timedelta(days=365)

        if existing:
            existing.subscription_plan_id = plan_id
            existing.status = "active"
            existing.billing_cycle = billing_cycle
            existing.auto_renew = True
            existing.start_date = now
            existing.end_date = end_date
            existing.cancelled_at = None
            existing.cancellation_reason = None
            existing.renewed_at = now
            db.add(existing)
            db.commit()
            db.refresh(existing)
            new_sub = existing
        else:
            new_sub = OrganizationSubscription(
                organization_id=org_id,
                subscription_plan_id=plan_id,
                status="active",
                billing_cycle=billing_cycle,
                auto_renew=True,
                start_date=now,
                end_date=end_date,
            )
            db.add(new_sub)
            db.commit()
            db.refresh(new_sub)

        logger.info(
            "Assigned plan '%s' (id=%s) to org '%s' by user %s",
            plan.name, plan_id, org_id, actor_user_id
        )

        result["success"] = True
        result["message"] = f"Plan '{plan.name}' assigned to '{org.name}'"
        result["subscription"] = new_sub
        return result

    @staticmethod
    def upgrade_org_plan(
        db: Session,
        org_id: UUID,
        new_plan_id: int,
        immediate: bool = True,
        actor_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Upgrade or downgrade an organization's subscription plan.

        Returns warning if downgrading (potential feature loss).
        """
        result = {"success": False, "message": "", "warnings": [], "subscription": None}

        current_sub = org_subscription_crud.get_active_by_org(db, org_id)
        if not current_sub:
            # No active subscription — just assign
            return SubscriptionService.assign_plan_to_org(
                db, org_id, new_plan_id, actor_user_id=actor_user_id
            )

        current_plan = current_sub.plan
        new_plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == new_plan_id, SubscriptionPlan.is_active == True
        ).first()
        if not new_plan:
            result["message"] = f"Target plan id={new_plan_id} not found or inactive"
            return result

        # Check if it's a downgrade
        if new_plan.tier < current_plan.tier:
            # Identify features that will be lost
            current_features = set(
                f.feature.code for f in current_plan.plan_features
                if f.enabled
            )
            new_features = set(
                f.feature.code for f in new_plan.plan_features
                if f.enabled
            )
            lost_features = current_features - new_features
            if lost_features:
                result["warnings"].append(
                    f"Downgrading will disable features: {', '.join(sorted(lost_features))}"
                )

        if immediate:
            now = datetime.now(timezone.utc)
            current_sub.subscription_plan_id = new_plan_id
            current_sub.status = "active"
            current_sub.start_date = now
            current_sub.end_date = now + timedelta(days=30 if current_sub.billing_cycle == "monthly" else 365)
            current_sub.cancelled_at = None
            current_sub.cancellation_reason = None
            db.add(current_sub)
            db.commit()
            db.refresh(current_sub)
            result["subscription"] = current_sub
        else:
            # Schedule at end of current period
            current_sub.subscription_plan_id = new_plan_id
            db.add(current_sub)
            db.commit()
            db.refresh(current_sub)
            result["subscription"] = current_sub

        result["success"] = True
        result["message"] = f"Plan changed from '{current_plan.name}' to '{new_plan.name}'"
        logger.info(
            "Org %s plan changed: %s -> %s by user %s",
            org_id, current_plan.name, new_plan.name, actor_user_id
        )
        return result

    @staticmethod
    def cancel_subscription(
        db: Session,
        org_id: UUID,
        immediate: bool = False,
        reason: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Cancel an organization's subscription."""
        result = {"success": False, "message": ""}

        sub = org_subscription_crud.get_active_by_org(db, org_id)
        if not sub:
            result["message"] = "No active subscription found"
            return result

        sub.status = "canceled"
        if immediate:
            sub.end_date = datetime.now(timezone.utc)
        sub.cancelled_at = datetime.now(timezone.utc)
        db.add(sub)
        db.commit()

        result["success"] = True
        result["message"] = f"Subscription cancelled{' (immediate)' if immediate else ''}"
        if reason:
            result["message"] += f" — {reason}"

        logger.info(
            "Subscription cancelled for org %s (immediate=%s, user=%s): %s",
            org_id, immediate, actor_user_id, reason
        )
        return result

    @staticmethod
    def renew_subscription(
        db: Session,
        org_id: UUID,
        actor_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Renew an expired or cancelled subscription."""
        result = {"success": False, "message": ""}

        sub = org_subscription_crud.get_by_org(db, org_id)
        if not sub:
            result["message"] = "No subscription found"
            return result

        if sub.status == "active":
            result["message"] = "Subscription is already active"
            result["success"] = True
            return result

        now = datetime.now(timezone.utc)
        sub.status = "active"
        sub.start_date = now
        sub.end_date = now + timedelta(
            days=30 if sub.billing_cycle == "monthly" else 365
        )
        sub.renewed_at = now
        sub.cancelled_at = None
        db.add(sub)
        db.commit()

        result["success"] = True
        result["message"] = "Subscription renewed"
        logger.info("Subscription renewed for org %s by user %s", org_id, actor_user_id)
        return result

    # ── Plan Resolution ────────────────────────────────────────────────────

    @staticmethod
    def _resolve_plan_for_org(db: Session, org_id: UUID) -> Optional[SubscriptionPlan]:
        """Resolve the plan whose entitlements apply to an org.

        Prefers the org's active subscription. When there is none — a tenant
        provisioned before subscription enforcement existed, or one mid-signup —
        falls back to the configured default plan so the org receives free-tier
        entitlements instead of being locked out of every feature. Denying
        outright here would turn enforcement into a total outage for any org
        missing a row.

        Returns None only when no plan exists at all (unseeded install).
        """
        sub = org_subscription_crud.get_active_by_org(db, org_id)
        if sub and sub.plan:
            return sub.plan

        from app.core.config import settings

        plan = subscription_plan_crud.get_by_code(db, settings.DEFAULT_PLAN_CODE)
        if plan:
            return plan

        return (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.is_active == True)  # noqa: E712
            .order_by(SubscriptionPlan.tier.asc(), SubscriptionPlan.id.asc())
            .first()
        )

    # ── Feature Resolution ──────────────────────────────────────────────────

    @staticmethod
    def get_enabled_features_for_org(
        db: Session, org_id: UUID
    ) -> List[Feature]:
        """Resolve all enabled features for an organization.

        Resolution order:
        1. Get the org's active subscription plan
        2. Get features enabled by that plan
        3. Check per-org feature flag overrides
        4. Filter by feature dependency satisfaction
        """
        sub = org_subscription_crud.get_active_by_org(db, org_id)
        plan = SubscriptionService._resolve_plan_for_org(db, org_id)
        if not plan:
            logger.warning("No subscription and no default plan available for org %s", org_id)
            return []

        # Features from plan
        plan_features = feature_crud.get_by_plan_id(db, plan.id)
        feature_map = {f.code: f for f in plan_features}

        # Per-org feature flag overrides
        flags = feature_flag_crud.get_enabled_for_org(db, org_id)
        for flag in flags:
            if flag.feature and flag.feature.code not in feature_map:
                # Feature flag enables a feature not in the plan
                feature_map[flag.feature.code] = flag.feature
            elif flag.feature and not flag.enabled:
                # Feature flag disables a plan feature
                feature_map.pop(flag.feature.code, None)

        # Check dependencies
        resolved = []
        for feature in feature_map.values():
            if SubscriptionService._check_feature_dependencies(feature, feature_map):
                resolved.append(feature)

        return resolved

    @staticmethod
    def _get_feature_dependency_codes(feature: Feature) -> List[str]:
        """Extract dependency feature codes from a Feature's JSONB dependencies field.

        Dependencies are stored as JSONB with format:
            {"depends_on": ["feature_code_1", "feature_code_2"]}
        or None if no dependencies.
        Returns an empty list if no dependencies.
        """
        if not feature.dependencies:
            return []
        deps = feature.dependencies
        if isinstance(deps, dict):
            raw = deps.get("depends_on", deps.get("dependencies", []))
            if isinstance(raw, str):
                return [raw]
            if isinstance(raw, list):
                return raw
        if isinstance(deps, list):
            return deps
        if isinstance(deps, str):
            return [deps]
        return []

    @staticmethod
    def check_feature_access(
        db: Session, org_id: UUID, feature_code: str
    ) -> Dict[str, Any]:
        """Check if an organization can access a specific feature.

        Returns {
            "allowed": bool,
            "reason": Optional[str],
            "limit_warning": Optional[str],
            "plan_name": Optional[str],
        }
        """
        result = {"allowed": False, "reason": None, "limit_warning": None, "plan_name": None}

        plan = SubscriptionService._resolve_plan_for_org(db, org_id)
        if not plan:
            result["reason"] = "No active subscription"
            return result

        result["plan_name"] = plan.name

        # Check if feature is in plan
        feature = feature_crud.get_by_code(db, feature_code)
        if not feature:
            result["reason"] = f"Feature '{feature_code}' not found"
            return result

        # Check plan-feature mapping
        plan_feature = (
            db.query(PlanFeature)
            .filter(
                PlanFeature.plan_id == plan.id,
                PlanFeature.feature_id == feature.id,
                PlanFeature.enabled == True,
            )
            .first()
        )

        if not plan_feature:
            # Check if there's a per-org override
            flag = feature_flag_crud.get_by_org_and_feature(db, org_id, feature.id)
            if not flag or not flag.enabled:
                result["reason"] = (
                    f"Feature '{feature_code}' not available on {plan.name} plan"
                )
                return result

        # Check dependencies
        dep_codes = SubscriptionService._get_feature_dependency_codes(feature)
        for dep_code in dep_codes:
            dep_result = SubscriptionService.check_feature_access(
                db, org_id, dep_code
            )
            if not dep_result["allowed"]:
                result["reason"] = (
                    f"Feature '{feature_code}' requires '{dep_code}'"
                )
                return result

        result["allowed"] = True
        return result

    @staticmethod
    def _check_feature_dependencies(
        feature: Feature, available_features: Dict[str, Feature]
    ) -> bool:
        """Check if a feature's dependencies are satisfied."""
        dep_codes = SubscriptionService._get_feature_dependency_codes(feature)
        if not dep_codes:
            return True
        return all(dep in available_features for dep in dep_codes)

    # ── Licensing Limit Enforcement ─────────────────────────────────────────

    @staticmethod
    def check_licensing_limit(
        db: Session,
        org_id: UUID,
        limit_type: str,
        current_usage: int,
    ) -> Dict[str, Any]:
        """Check if an organization has reached a licensing limit.

        Returns {
            "allowed": bool,
            "warning": Optional[str],
            "soft_limit": int,
            "hard_limit": int,
        }
        """
        result = {
            "allowed": True,
            "warning": None,
            "soft_limit": 0,
            "hard_limit": 0,
        }

        plan = SubscriptionService._resolve_plan_for_org(db, org_id)
        if not plan:
            result["allowed"] = False
            result["warning"] = "No active subscription"
            return result

        limit = licensing_limit_crud.get_by_plan_and_type(
            db, plan.id, limit_type
        )
        if not limit:
            return result  # No limit defined = allowed

        result["soft_limit"] = limit.soft_limit or 0
        result["hard_limit"] = limit.hard_limit or 0

        hard_limit = limit.hard_limit
        soft_limit = limit.soft_limit

        if hard_limit is not None and hard_limit > 0 and current_usage >= hard_limit:
            result["allowed"] = False
            result["warning"] = (
                f"Hard limit reached: {current_usage}/{hard_limit} "
                f"for {limit_type}"
            )
        elif soft_limit is not None and soft_limit > 0 and current_usage >= soft_limit:
            result["warning"] = (
                f"Approaching limit: {current_usage}/{hard_limit or 'unlimited'} "
                f"for {limit_type}"
            )

        return result

    @staticmethod
    def get_org_usage_stats(
        db: Session, org_id: UUID
    ) -> Dict[str, Any]:
        """Get usage statistics and limit warnings for an organization."""
        from app.db.models.all_models import User, Department

        sub = org_subscription_crud.get_active_by_org(db, org_id)
        plan = SubscriptionService._resolve_plan_for_org(db, org_id)
        if not plan:
            return {"status": "no_subscription", "warnings": [], "blocks": []}

        # Compute current usage
        user_count = db.query(User).filter(
            User.org_id == org_id, User.is_deleted == 0
        ).count()

        dept_count = db.query(Department).filter(
            Department.org_id == org_id, Department.is_deleted == 0
        ).count()

        # Check limits
        warnings = []
        blocks = []

        for limit_type, usage in [
            ("employees", user_count),
            ("departments", dept_count),
        ]:
            check = SubscriptionService.check_licensing_limit(
                db, org_id, limit_type, usage
            )
            if not check["allowed"]:
                blocks.append(check["warning"])
            elif check["warning"]:
                warnings.append(check["warning"])

        limits = licensing_limit_crud.get_by_plan(db, plan.id)

        return {
            "org_id": str(org_id),
            "plan_name": plan.name,
            "plan_tier": plan.tier,
            "status": sub.status if sub else "default_plan",
            "limits": [
                {
                    "limit_type": l.limit_type,
                    "soft_limit": l.soft_limit,
                    "hard_limit": l.hard_limit,
                    "description": l.description,
                }
                for l in limits
            ],
            "current_usage": {
                "users": user_count,
                "departments": dept_count,
            },
            "warnings": warnings,
            "blocks": blocks,
        }

    # ── Seeding ─────────────────────────────────────────────────────────────

    @staticmethod
    def seed_subscription_data(db: Session) -> Dict[str, int]:
        """Seed initial subscription plans, features, and limits."""
        logger.info("=== Subscription Seeding Started ===")
        stats = seed_subscription_data(db)
        logger.info("=== Subscription Seeding Complete ===")
        return stats

    # ── Default Provisioning ───────────────────────────────────────────────

    @staticmethod
    def ensure_default_subscription(db: Session, org_id: UUID) -> Optional[OrganizationSubscription]:
        """Guarantee an org has an active subscription, provisioning the default
        plan when it has none.

        Called at tenant provisioning time. Without this, an org with no
        subscription fails every feature check with "No active subscription",
        which turns enforcement into a total lockout rather than a paid upgrade.
        Idempotent: returns the existing subscription when one is already active.
        """
        existing = org_subscription_crud.get_active_by_org(db, org_id)
        if existing:
            return existing

        from app.core.config import settings

        plan = subscription_plan_crud.get_by_code(db, settings.DEFAULT_PLAN_CODE)
        if not plan:
            # Fall back to the lowest active tier so provisioning never hard-fails.
            plan = (
                db.query(SubscriptionPlan)
                .filter(SubscriptionPlan.is_active == True)  # noqa: E712
                .order_by(SubscriptionPlan.tier.asc(), SubscriptionPlan.id.asc())
                .first()
            )
        if not plan:
            logger.error("No active subscription plan available for org %s", org_id)
            return None

        now = datetime.now(timezone.utc)
        sub = OrganizationSubscription(
            organization_id=org_id,
            subscription_plan_id=plan.id,
            status="active",
            billing_cycle="monthly",
            start_date=now,
            trial_end=now + timedelta(days=plan.trial_days or settings.DEFAULT_TRIAL_DAYS),
            next_renewal=now + timedelta(days=30),
            auto_renew=True,
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
        logger.info("Provisioned default plan '%s' for org %s", plan.code, org_id)
        return sub

    # ── Public Catalog ─────────────────────────────────────────────────────

    @staticmethod
    def get_public_plans(db: Session) -> List[Dict[str, Any]]:
        """Return the sellable plan catalog for public pricing surfaces.

        Restricted to PUBLIC_PLAN_CODES and is_active plans. Returns only
        non-deprecated features, so features that are catalogued but not
        implemented are never advertised.
        """
        from app.core.config import settings

        codes = [c.strip() for c in settings.PUBLIC_PLAN_CODES.split(",") if c.strip()]
        if not codes:
            return []

        plans = (
            db.query(SubscriptionPlan)
            .filter(
                SubscriptionPlan.code.in_(codes),
                SubscriptionPlan.is_active == True,  # noqa: E712
            )
            .order_by(SubscriptionPlan.tier.asc(), SubscriptionPlan.display_order.asc())
            .all()
        )

        catalog: List[Dict[str, Any]] = []
        for plan in plans:
            features = feature_crud.get_by_plan_id(db, plan.id)
            limits = licensing_limit_crud.get_by_plan(db, plan.id)

            limit_map = {limit.limit_type: limit for limit in limits}
            employees = limit_map.get("employees")

            catalog.append(
                {
                    "code": plan.code,
                    "name": plan.name,
                    "description": plan.description,
                    "tier": plan.tier,
                    "monthly_price": float(plan.monthly_price or 0),
                    "yearly_price": float(plan.yearly_price or 0),
                    "currency": plan.currency,
                    "trial_days": plan.trial_days,
                    "features": sorted(
                        f.code for f in features if not f.deprecated
                    ),
                    "limits": {
                        limit_type: (
                            None
                            if limit.is_unlimited
                            else {
                                "soft": limit.soft_limit,
                                "hard": limit.hard_limit,
                            }
                        )
                        for limit_type, limit in limit_map.items()
                        if not limit.limit_type.startswith("test_")
                    },
                    "is_unlimited_seats": bool(
                        employees and employees.is_unlimited
                    ),
                }
            )
        return catalog

    # ── Module Summary ─────────────────────────────────────────────────────

    @staticmethod
    def get_module_summary(db: Session) -> List[Dict]:
        """Get summary of features grouped by module."""
        modules = feature_crud.get_modules(db)
        summaries = []
        for module in modules:
            features = feature_crud.get_by_module(db, module)
            active_count = sum(1 for f in features if not f.deprecated)
            summaries.append({
                "module": module,
                "total": len(features),
                "active": active_count,
                "inactive": len(features) - active_count,
            })
        return summaries


subscription_service = SubscriptionService()
