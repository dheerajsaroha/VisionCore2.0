"""
crud_subscription.py — CRUD operations for Subscription & Feature Management (Sprint 2, Entity 2)

Covers CRUD for all 6 subscription entities:
- SubscriptionPlan
- OrganizationSubscription
- Feature
- PlanFeature
- FeatureFlag
- LicensingLimit
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, or_

from app.db.models.all_models import (
    SubscriptionPlan,
    OrganizationSubscription,
    Feature,
    PlanFeature,
    FeatureFlag,
    LicensingLimit,
    Organization,
)
from app.crud.base import CRUDBase
from app.schema.subscription import (
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
    OrganizationSubscriptionCreate,
    OrganizationSubscriptionUpdate,
    FeatureCreate,
    FeatureUpdate,
    PlanFeatureCreate,
    PlanFeatureUpdate,
    FeatureFlagCreate,
    FeatureFlagUpdate,
    LicensingLimitCreate,
    LicensingLimitUpdate,
)


# =============================================================================
#  SubscriptionPlan CRUD
# =============================================================================

class CRUDSubscriptionPlan(CRUDBase[SubscriptionPlan, SubscriptionPlanCreate, SubscriptionPlanUpdate]):

    def get_by_code(self, db: Session, code: str) -> Optional[SubscriptionPlan]:
        """Get a plan by its unique code."""
        return db.query(SubscriptionPlan).filter(
            SubscriptionPlan.code == code
        ).first()

    def get_active(self, db: Session) -> List[SubscriptionPlan]:
        """Get all active plans ordered by tier ascending."""
        return db.query(SubscriptionPlan).filter(
            SubscriptionPlan.is_active == True
        ).order_by(SubscriptionPlan.tier).all()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> List[SubscriptionPlan]:
        """List plans with optional filtering."""
        q = db.query(SubscriptionPlan)
        if is_active is not None:
            q = q.filter(SubscriptionPlan.is_active == is_active)
        if search:
            q = q.filter(
                SubscriptionPlan.name.ilike(f"%{search}%") |
                SubscriptionPlan.code.ilike(f"%{search}%")
            )
        return q.order_by(SubscriptionPlan.tier).offset(skip).limit(limit).all()

    def count(
        self,
        db: Session,
        *,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> int:
        """Count plans with optional filtering."""
        q = db.query(func.count(SubscriptionPlan.id))
        if is_active is not None:
            q = q.filter(SubscriptionPlan.is_active == is_active)
        if search:
            q = q.filter(
                SubscriptionPlan.name.ilike(f"%{search}%") |
                SubscriptionPlan.code.ilike(f"%{search}%")
            )
        return q.scalar() or 0

    def get_with_features(self, db: Session, plan_id: int) -> Optional[SubscriptionPlan]:
        """Get a plan eagerly loaded with features and limits."""
        return db.query(SubscriptionPlan).options(
            joinedload(SubscriptionPlan.plan_features).joinedload(PlanFeature.feature),
            joinedload(SubscriptionPlan.licensing_limits),
        ).filter(SubscriptionPlan.id == plan_id).first()


# =============================================================================
#  OrganizationSubscription CRUD
# =============================================================================

class CRUDOrganizationSubscription(
    CRUDBase[OrganizationSubscription, OrganizationSubscriptionCreate, OrganizationSubscriptionUpdate]
):

    def get_by_org(self, db: Session, org_id: UUID) -> Optional[OrganizationSubscription]:
        """Get the current subscription for an organization eagerly loaded with plan."""
        return db.query(OrganizationSubscription).options(
            joinedload(OrganizationSubscription.plan)
        ).filter(
            OrganizationSubscription.organization_id == org_id
        ).order_by(OrganizationSubscription.created_at.desc()).first()

    def get_active_by_org(self, db: Session, org_id: UUID) -> Optional[OrganizationSubscription]:
        """Get the active subscription for an organization."""
        now = datetime.now(timezone.utc)
        return db.query(OrganizationSubscription).options(
            joinedload(OrganizationSubscription.plan)
        ).filter(
            OrganizationSubscription.organization_id == org_id,
            OrganizationSubscription.status == "active",
            OrganizationSubscription.start_date <= now,
            or_(
                OrganizationSubscription.end_date.is_(None),
                OrganizationSubscription.end_date >= now,
            ),
        ).order_by(OrganizationSubscription.created_at.desc()).first()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        plan_id: Optional[int] = None,
        org_id: Optional[UUID] = None,
    ) -> List[OrganizationSubscription]:
        """List subscriptions with optional filtering."""
        q = db.query(OrganizationSubscription).options(
            joinedload(OrganizationSubscription.plan)
        )
        if status:
            q = q.filter(OrganizationSubscription.status == status)
        if plan_id is not None:
            q = q.filter(OrganizationSubscription.subscription_plan_id == plan_id)
        if org_id is not None:
            q = q.filter(OrganizationSubscription.organization_id == org_id)
        return q.order_by(OrganizationSubscription.created_at.desc()).offset(skip).limit(limit).all()

    def count(
        self,
        db: Session,
        *,
        status: Optional[str] = None,
        plan_id: Optional[int] = None,
    ) -> int:
        """Count subscriptions with optional filtering."""
        q = db.query(func.count(OrganizationSubscription.id))
        if status:
            q = q.filter(OrganizationSubscription.status == status)
        if plan_id is not None:
            q = q.filter(OrganizationSubscription.subscription_plan_id == plan_id)
        return q.scalar() or 0

    def get_expiring_soon(
        self, db: Session, days: int = 30
    ) -> List[OrganizationSubscription]:
        """Get subscriptions that are expiring within the given number of days."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        threshold = now + timedelta(days=days)
        return db.query(OrganizationSubscription).options(
            joinedload(OrganizationSubscription.plan)
        ).filter(
            OrganizationSubscription.status == "active",
            OrganizationSubscription.end_date.isnot(None),
            OrganizationSubscription.end_date.between(now, threshold),
        ).all()


# =============================================================================
#  Feature CRUD
# =============================================================================

class CRUDFeature(CRUDBase[Feature, FeatureCreate, FeatureUpdate]):

    def get_by_code(self, db: Session, code: str) -> Optional[Feature]:
        """Get a feature by its unique code."""
        return db.query(Feature).filter(Feature.code == code).first()

    def get_by_module(self, db: Session, module: str) -> List[Feature]:
        """Get all features in a module."""
        return db.query(Feature).filter(
            Feature.module == module
        ).order_by(Feature.code).all()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        module: Optional[str] = None,
        category: Optional[str] = None,
        deprecated: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> List[Feature]:
        """List features with optional filtering."""
        q = db.query(Feature)
        if module:
            q = q.filter(Feature.module == module)
        if category:
            q = q.filter(Feature.category == category)
        if deprecated is not None:
            q = q.filter(Feature.deprecated == deprecated)
        if search:
            q = q.filter(
                Feature.name.ilike(f"%{search}%") |
                Feature.code.ilike(f"%{search}%") |
                Feature.description.ilike(f"%{search}%")
            )
        return q.order_by(Feature.module, Feature.code).offset(skip).limit(limit).all()

    def count(
        self,
        db: Session,
        *,
        module: Optional[str] = None,
        category: Optional[str] = None,
        deprecated: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> int:
        """Count features with optional filtering."""
        q = db.query(func.count(Feature.id))
        if module:
            q = q.filter(Feature.module == module)
        if category:
            q = q.filter(Feature.category == category)
        if deprecated is not None:
            q = q.filter(Feature.deprecated == deprecated)
        if search:
            pattern = f"%{search}%"
            q = q.filter(
                Feature.name.ilike(pattern) |
                Feature.code.ilike(pattern) |
                Feature.description.ilike(pattern)
            )
        return q.scalar() or 0

    def get_modules(self, db: Session) -> List[str]:
        """Get distinct module names."""
        results = db.query(Feature.module).distinct().order_by(Feature.module).all()
        return [r[0] for r in results if r[0]]

    def get_by_plan_id(self, db: Session, plan_id: int) -> List[Feature]:
        """Get all features enabled for a plan."""
        return (
            db.query(Feature)
            .join(PlanFeature, Feature.id == PlanFeature.feature_id)
            .filter(
                PlanFeature.plan_id == plan_id,
                PlanFeature.enabled == True,
                Feature.deprecated == False,
            )
            .order_by(Feature.module, Feature.code)
            .all()
        )


# =============================================================================
#  PlanFeature CRUD
# =============================================================================

class CRUDPlanFeature(CRUDBase[PlanFeature, PlanFeatureCreate, PlanFeatureUpdate]):

    def get_by_plan_and_feature(
        self, db: Session, plan_id: int, feature_id: int
    ) -> Optional[PlanFeature]:
        """Get a specific plan-feature mapping."""
        return db.query(PlanFeature).filter(
            PlanFeature.plan_id == plan_id,
            PlanFeature.feature_id == feature_id,
        ).first()

    def bulk_set(
        self, db: Session, plan_id: int, feature_ids: List[int], enabled: bool = True
    ) -> int:
        """Bulk enable/disable features for a plan. Returns count of changes."""
        count = 0
        for fid in feature_ids:
            existing = self.get_by_plan_and_feature(db, plan_id, fid)
            if existing:
                if existing.enabled != enabled:
                    existing.enabled = enabled
                    db.add(existing)
                    count += 1
            else:
                db.add(PlanFeature(plan_id=plan_id, feature_id=fid, enabled=enabled))
                count += 1
        db.commit()
        return count


# =============================================================================
#  FeatureFlag CRUD
# =============================================================================

class CRUDFeatureFlag(CRUDBase[FeatureFlag, FeatureFlagCreate, FeatureFlagUpdate]):

    def get_by_org_and_feature(
        self, db: Session, org_id: UUID, feature_id: int
    ) -> Optional[FeatureFlag]:
        """Get the feature flag for a specific org and feature."""
        return db.query(FeatureFlag).filter(
            FeatureFlag.organization_id == org_id,
            FeatureFlag.feature_id == feature_id,
        ).first()

    def get_enabled_for_org(self, db: Session, org_id: UUID) -> List[FeatureFlag]:
        """Get all enabled feature flags for an organization."""
        now = datetime.now(timezone.utc)
        return db.query(FeatureFlag).options(
            joinedload(FeatureFlag.feature)
        ).filter(
            FeatureFlag.organization_id == org_id,
            FeatureFlag.enabled == True,
            or_(
                FeatureFlag.expires_at.is_(None),
                FeatureFlag.expires_at > now,
            ),
        ).all()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        org_id: Optional[UUID] = None,
        feature_id: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> List[FeatureFlag]:
        """List feature flags with optional filtering."""
        q = db.query(FeatureFlag).options(joinedload(FeatureFlag.feature))
        if org_id is not None:
            q = q.filter(FeatureFlag.organization_id == org_id)
        if feature_id is not None:
            q = q.filter(FeatureFlag.feature_id == feature_id)
        if enabled is not None:
            q = q.filter(FeatureFlag.enabled == enabled)
        return q.order_by(FeatureFlag.created_at.desc()).offset(skip).limit(limit).all()

    def count(
        self,
        db: Session,
        *,
        org_id: Optional[UUID] = None,
        feature_id: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> int:
        """Count feature flags with optional filtering."""
        q = db.query(func.count(FeatureFlag.id))
        if org_id is not None:
            q = q.filter(FeatureFlag.organization_id == org_id)
        if feature_id is not None:
            q = q.filter(FeatureFlag.feature_id == feature_id)
        if enabled is not None:
            q = q.filter(FeatureFlag.enabled == enabled)
        return q.scalar() or 0


# =============================================================================
#  LicensingLimit CRUD
# =============================================================================

class CRUDLicensingLimit(
    CRUDBase[LicensingLimit, LicensingLimitCreate, LicensingLimitUpdate]
):

    def get_by_plan_and_type(
        self, db: Session, plan_id: int, limit_type: str
    ) -> Optional[LicensingLimit]:
        """Get a specific limit for a plan."""
        return db.query(LicensingLimit).filter(
            LicensingLimit.plan_id == plan_id,
            LicensingLimit.limit_type == limit_type,
        ).first()

    def get_by_plan(self, db: Session, plan_id: int) -> List[LicensingLimit]:
        """Get all licensing limits for a plan."""
        return db.query(LicensingLimit).filter(
            LicensingLimit.plan_id == plan_id
        ).order_by(LicensingLimit.limit_type).all()

    def check_limit(
        self, db: Session, plan_id: int, limit_type: str, current_usage: int
    ) -> tuple[bool, Optional[str]]:
        """Check if a limit has been reached.

        Returns (allowed: bool, warning: Optional[str]).
        """
        limit = self.get_by_plan_and_type(db, plan_id, limit_type)
        if not limit:
            return True, None  # No limit defined = allowed

        hard_limit = limit.hard_limit
        soft_limit = limit.soft_limit

        if hard_limit is not None and hard_limit > 0 and current_usage >= hard_limit:
            return False, f"Hard limit reached: {current_usage}/{hard_limit} for {limit_type}"

        if soft_limit is not None and soft_limit > 0 and current_usage >= soft_limit:
            return True, f"Approaching limit: {current_usage}/{hard_limit or 'unlimited'} for {limit_type}"

        return True, None


# =============================================================================
#  Instance Exports
# =============================================================================

subscription_plan_crud = CRUDSubscriptionPlan(SubscriptionPlan)
org_subscription_crud = CRUDOrganizationSubscription(OrganizationSubscription)
feature_crud = CRUDFeature(Feature)
plan_feature_crud = CRUDPlanFeature(PlanFeature)
feature_flag_crud = CRUDFeatureFlag(FeatureFlag)
licensing_limit_crud = CRUDLicensingLimit(LicensingLimit)
