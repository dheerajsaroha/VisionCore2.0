"""
subscription.py — Subscription & Feature Management API Router (Sprint 2, Entity 2)

Endpoints:
- SubscriptionPlan CRUD
- OrganizationSubscription management (assign, upgrade, cancel, renew)
- Feature catalog
- Plan-Feature mapping
- Feature Flag management (per-org overrides)
- Licensing Limit management
- Feature access checks
- Usage statistics
- Seeding
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.db.models.all_models import (
    User,
    SubscriptionPlan,
    OrganizationSubscription,
    Feature,
    PlanFeature,
    FeatureFlag,
    LicensingLimit,
    Organization,
)
from app.schema.subscription import (
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
    SubscriptionPlanResponse,
    SubscriptionPlanListResponse,
    OrganizationSubscriptionCreate,
    OrganizationSubscriptionUpdate,
    OrganizationSubscriptionResponse,
    OrganizationSubscriptionListResponse,
    FeatureCreate,
    FeatureUpdate,
    FeatureResponse,
    FeatureListResponse,
    PlanFeatureCreate,
    PlanFeatureUpdate,
    PlanFeatureResponse,
    PlanFeatureListResponse,
    FeatureFlagCreate,
    FeatureFlagUpdate,
    FeatureFlagResponse,
    FeatureFlagListResponse,
    LicensingLimitCreate,
    LicensingLimitUpdate,
    LicensingLimitResponse,
    LicensingLimitListResponse,
    PlanWithFeaturesResponse,
    OrgSubscriptionDetailResponse,
    SubscriptionUpgradeRequest,
    SubscriptionCancelRequest,
    FeatureEnforcementResult,
    LicenseUsageResponse,
    SubscriptionSeedResponse,
)
from app.crud.crud_subscription import (
    subscription_plan_crud,
    org_subscription_crud,
    feature_crud,
    plan_feature_crud,
    feature_flag_crud,
    licensing_limit_crud,
)
from app.services.subscription_service import subscription_service
from sqlalchemy.orm import joinedload

from app.schema.subscription import (
    FeatureResponse as FeatureResp,
    LicensingLimitResponse as LicensingLimitResp,
)

router = APIRouter()


# =============================================================================
#  Helper: Build subscription detail response
# =============================================================================

def _build_subscription_detail_response(
    sub: OrganizationSubscription,
    db: Session,
    org_id: UUID,
) -> OrgSubscriptionDetailResponse:
    """Build a detailed subscription response with plan, features, and usage.

    Shared between admin org lookup and self-service my/subscription endpoints.
    """
    enabled_features = subscription_service.get_enabled_features_for_org(db, org_id)
    enabled_codes = [f.code for f in enabled_features]
    usage = subscription_service.get_org_usage_stats(db, org_id)

    # Convert plan features and limits to Pydantic responses
    plan_response = None
    if sub.plan:
        plan_response = PlanWithFeaturesResponse(
            id=sub.plan.id,
            code=sub.plan.code,
            name=sub.plan.name,
            description=sub.plan.description,
            tier=sub.plan.tier,
            monthly_price=float(sub.plan.monthly_price) if sub.plan.monthly_price else 0,
            yearly_price=float(sub.plan.yearly_price) if sub.plan.yearly_price else 0,
            currency=sub.plan.currency,
            trial_days=sub.plan.trial_days,
            is_active=sub.plan.is_active,
            is_system=sub.plan.is_system,
            display_order=sub.plan.display_order,
            created_at=sub.plan.created_at,
            updated_at=sub.plan.updated_at,
            features=[
                FeatureResponse(
                    id=pf.feature.id,
                    code=pf.feature.code,
                    name=pf.feature.name,
                    description=pf.feature.description,
                    module=pf.feature.module,
                    category=pf.feature.category,
                    visibility=pf.feature.visibility,
                    dependencies=pf.feature.dependencies,
                    deprecated=pf.feature.deprecated,
                    created_at=pf.feature.created_at,
                    updated_at=pf.feature.created_at,
                )
                for pf in sub.plan.plan_features if pf.feature
            ],
            limits=[
                LicensingLimitResponse(
                    id=getattr(ll, "id", ll.get("id") if isinstance(ll, dict) else None),
                    plan_id=getattr(ll, "plan_id", ll.get("plan_id") if isinstance(ll, dict) else None),
                    limit_type=getattr(ll, "limit_type", ll.get("limit_type") if isinstance(ll, dict) else ""),
                    soft_limit=getattr(ll, "soft_limit", ll.get("soft_limit") if isinstance(ll, dict) else None),
                    hard_limit=getattr(ll, "hard_limit", ll.get("hard_limit") if isinstance(ll, dict) else None),
                    is_unlimited=getattr(ll, "is_unlimited", ll.get("is_unlimited", False) if isinstance(ll, dict) else False),
                    description=getattr(ll, "description", ll.get("description") if isinstance(ll, dict) else None),
                    created_at=getattr(ll, "created_at", ll.get("created_at") if isinstance(ll, dict) else None),
                )
                for ll in (sub.plan.licensing_limits or [])
            ],
        )

    return OrgSubscriptionDetailResponse(
        id=sub.id,
        organization_id=sub.organization_id,
        subscription_plan_id=sub.subscription_plan_id,
        org_name=sub.organization.name if sub.organization else None,
        plan_name=sub.plan.name if sub.plan else None,
        status=sub.status,
        billing_cycle=sub.billing_cycle,
        auto_renew=sub.auto_renew,
        start_date=sub.start_date,
        end_date=sub.end_date,
        cancelled_at=sub.cancelled_at,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
        plan=plan_response,
        enabled_features=enabled_codes,
        usage_stats=usage,
    )


# =============================================================================
#  Seeding
# =============================================================================

@router.post("/seed", response_model=SubscriptionSeedResponse)
def seed_subscription_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("platform.settings.manage")),
) -> Any:
    """Seed subscription plans, features, plan-feature mappings, and licensing limits.
    Requires platform.settings.manage permission. Idempotent."""
    stats = subscription_service.seed_subscription_data(db)
    return SubscriptionSeedResponse(**stats)


# =============================================================================
#  SubscriptionPlan CRUD
# =============================================================================

@router.get("/plans", response_model=SubscriptionPlanListResponse)
def list_plans(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(deps.require_permission("billing.view")),
) -> Any:
    """List all subscription plans."""
    plans = subscription_plan_crud.get_multi(
        db, skip=skip, limit=limit, is_active=is_active, search=search
    )
    total = subscription_plan_crud.count(db, is_active=is_active, search=search)
    return {"total": total, "plans": plans}


@router.get("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.view")),
) -> Any:
    """Get a single subscription plan."""
    plan = subscription_plan_crud.get(db, id=plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.get("/plans/{plan_id}/detail", response_model=PlanWithFeaturesResponse)
def get_plan_detail(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.view")),
) -> Any:
    """Get a plan with its features and licensing limits."""
    plan = subscription_plan_crud.get_with_features(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    features = [
        FeatureResp(
            id=pf.feature.id,
            code=pf.feature.code,
            name=pf.feature.name,
            description=pf.feature.description,
            module=pf.feature.module,
            category=pf.feature.category,
            visibility=pf.feature.visibility,
            dependencies=pf.feature.dependencies,
            deprecated=pf.feature.deprecated,
            created_at=pf.feature.created_at,
        )
        for pf in plan.plan_features if pf.feature
    ]
    limits = [
        LicensingLimitResp(
            id=getattr(ll, "id", ll.get("id") if isinstance(ll, dict) else None),
            plan_id=getattr(ll, "plan_id", ll.get("plan_id") if isinstance(ll, dict) else None),
            limit_type=getattr(ll, "limit_type", ll.get("limit_type") if isinstance(ll, dict) else ""),
            soft_limit=getattr(ll, "soft_limit", ll.get("soft_limit") if isinstance(ll, dict) else None),
            hard_limit=getattr(ll, "hard_limit", ll.get("hard_limit") if isinstance(ll, dict) else None),
            is_unlimited=getattr(ll, "is_unlimited", ll.get("is_unlimited", False) if isinstance(ll, dict) else False),
            description=getattr(ll, "description", ll.get("description") if isinstance(ll, dict) else None),
            created_at=getattr(ll, "created_at", ll.get("created_at") if isinstance(ll, dict) else None),
        )
        for ll in (plan.licensing_limits or [])
    ]

    return PlanWithFeaturesResponse(
        id=plan.id,
        code=plan.code,
        name=plan.name,
        description=plan.description,
        tier=plan.tier,
        monthly_price=float(plan.monthly_price) if plan.monthly_price else 0,
        yearly_price=float(plan.yearly_price) if plan.yearly_price else 0,
        currency=plan.currency,
        trial_days=plan.trial_days,
        is_active=plan.is_active,
        is_system=plan.is_system,
        display_order=plan.display_order,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        features=features,
        limits=limits,
    )


@router.post("/plans", response_model=SubscriptionPlanResponse)
def create_plan(
    plan_in: SubscriptionPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """Create a new subscription plan."""
    existing = subscription_plan_crud.get_by_code(db, code=plan_in.code)
    if existing:
        raise HTTPException(status_code=409, detail="Plan code already exists")
    return subscription_plan_crud.create(db, obj_in=plan_in)


@router.put("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
def update_plan(
    plan_id: int,
    plan_in: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """Update a subscription plan."""
    plan = subscription_plan_crud.get(db, id=plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    update_data = plan_in.model_dump(exclude_unset=True)
    return subscription_plan_crud.update(db, db_obj=plan, obj_in=update_data)


@router.delete("/plans/{plan_id}")
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """Delete a subscription plan."""
    plan = subscription_plan_crud.get(db, id=plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    subscription_plan_crud.remove(db, id=plan_id)
    return {"detail": "Plan deleted"}


# =============================================================================
#  OrganizationSubscription Management
# =============================================================================

@router.get("/orgs/{org_id}/subscription", response_model=OrgSubscriptionDetailResponse)
def get_org_subscription(
    org_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.view")),
) -> Any:
    """Get the current subscription for an organization."""
    # Eagerly load organization + plan relationships to avoid N+1 queries
    sub = org_subscription_crud.get_by_org(db, org_id)
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found for this organization")

    return _build_subscription_detail_response(sub, db, org_id)


@router.get("/subscriptions", response_model=OrganizationSubscriptionListResponse)
def list_subscriptions(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    status: Optional[str] = Query(None),
    plan_id: Optional[int] = Query(None),
    current_user: User = Depends(deps.require_permission("billing.view")),
) -> Any:
    """List all organization subscriptions."""
    subs = org_subscription_crud.get_multi(
        db, skip=skip, limit=limit, status=status, plan_id=plan_id
    )
    total = org_subscription_crud.count(db, status=status, plan_id=plan_id)
    return {"total": total, "subscriptions": subs}


@router.post("/orgs/{org_id}/subscription/assign")
def assign_plan_to_org(
    org_id: UUID,
    plan_id: int = Query(..., description="Plan ID to assign"),
    billing_cycle: str = Query("monthly", pattern="^(monthly|yearly)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """Assign a subscription plan to an organization."""
    result = subscription_service.assign_plan_to_org(
        db, org_id=org_id, plan_id=plan_id,
        billing_cycle=billing_cycle,
        actor_user_id=current_user.id,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    if result.get("subscription"):
        result["subscription"] = OrganizationSubscriptionResponse.model_validate(result["subscription"]).model_dump(mode="json")
    return result


@router.post("/orgs/{org_id}/subscription/upgrade")
def upgrade_org_plan(
    org_id: UUID,
    req: SubscriptionUpgradeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """Upgrade or downgrade an organization's subscription."""
    result = subscription_service.upgrade_org_plan(
        db, org_id=org_id, new_plan_id=req.plan_id,
        immediate=req.immediate,
        actor_user_id=current_user.id,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    if result.get("subscription"):
        result["subscription"] = OrganizationSubscriptionResponse.model_validate(result["subscription"]).model_dump(mode="json")
    return result


@router.post("/orgs/{org_id}/subscription/cancel")
def cancel_org_subscription(
    org_id: UUID,
    req: SubscriptionCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """Cancel an organization's subscription."""
    result = subscription_service.cancel_subscription(
        db, org_id=org_id, immediate=req.immediate,
        reason=req.reason,
        actor_user_id=current_user.id,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/orgs/{org_id}/subscription/renew")
def renew_org_subscription(
    org_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """Renew an expired or cancelled subscription."""
    result = subscription_service.renew_subscription(
        db, org_id=org_id, actor_user_id=current_user.id,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


# =============================================================================
#  Feature Catalog
# =============================================================================

@router.get("/features", response_model=FeatureListResponse)
def list_features(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    module: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    deprecated: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(deps.require_permission("billing.view")),
) -> Any:
    """List all features with optional filtering."""
    features = feature_crud.get_multi(
        db, skip=skip, limit=limit,
        module=module, category=category,
        deprecated=deprecated, search=search,
    )
    total = feature_crud.count(
        db, module=module, category=category,
        deprecated=deprecated, search=search,
    )
    return {"total": total, "features": features}


@router.get("/features/modules")
def list_feature_modules(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.view")),
) -> Any:
    """List distinct feature modules."""
    modules = feature_crud.get_modules(db)
    return {"modules": modules}


@router.post("/features", response_model=FeatureResponse)
def create_feature(
    feature_in: FeatureCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """Create a new feature."""
    existing = feature_crud.get_by_code(db, code=feature_in.code)
    if existing:
        raise HTTPException(status_code=409, detail="Feature code already exists")
    return feature_crud.create(db, obj_in=feature_in)


@router.get("/features/{feature_id}", response_model=FeatureResponse)
def get_feature(
    feature_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.view")),
) -> Any:
    """Get a single feature."""
    feature = feature_crud.get(db, id=feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    return feature


@router.put("/features/{feature_id}", response_model=FeatureResponse)
def update_feature(
    feature_id: int,
    feature_in: FeatureUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """Update a feature."""
    feature = feature_crud.get(db, id=feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    update_data = feature_in.model_dump(exclude_unset=True)
    return feature_crud.update(db, db_obj=feature, obj_in=update_data)


# =============================================================================
#  Plan-Feature Mapping
# =============================================================================

@router.get("/plans/{plan_id}/features", response_model=PlanFeatureListResponse)
def list_plan_features(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.view")),
) -> Any:
    """List all feature mappings for a plan."""
    plan = subscription_plan_crud.get(db, id=plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan_features = db.query(PlanFeature).filter(
        PlanFeature.plan_id == plan_id
    ).all()
    return {"total": len(plan_features), "plan_features": plan_features}


@router.post("/plans/{plan_id}/features/bulk")
def bulk_set_plan_features(
    plan_id: int,
    feature_ids: List[int],
    enabled: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """Bulk enable/disable features for a plan."""
    plan = subscription_plan_crud.get(db, id=plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    count = plan_feature_crud.bulk_set(db, plan_id=plan_id, feature_ids=feature_ids, enabled=enabled)
    return {"updated": count, "plan_id": plan_id, "enabled": enabled}


# =============================================================================
#  Feature Flag (Per-Organization Override)
# =============================================================================

@router.get("/feature-flags", response_model=FeatureFlagListResponse)
def list_feature_flags(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    org_id: Optional[UUID] = Query(None),
    feature_id: Optional[int] = Query(None),
    enabled: Optional[bool] = Query(None),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """List feature flags with optional filtering."""
    flags = feature_flag_crud.get_multi(
        db, skip=skip, limit=limit,
        org_id=org_id, feature_id=feature_id, enabled=enabled,
    )
    total = feature_flag_crud.count(
        db, org_id=org_id, feature_id=feature_id, enabled=enabled,
    )
    return {"total": total, "feature_flags": flags}


@router.post("/feature-flags", response_model=FeatureFlagResponse)
def create_feature_flag(
    flag_in: FeatureFlagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """Create or update a feature flag override for an organization."""
    existing = feature_flag_crud.get_by_org_and_feature(
        db, org_id=flag_in.organization_id, feature_id=flag_in.feature_id
    )
    if existing:
        existing.enabled = flag_in.enabled
        existing.expires_at = flag_in.expires_at
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    return feature_flag_crud.create(db, obj_in=flag_in)


@router.put("/feature-flags/{flag_id}", response_model=FeatureFlagResponse)
def update_feature_flag(
    flag_id: int,
    flag_in: FeatureFlagUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """Update a feature flag."""
    flag = feature_flag_crud.get(db, id=flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Feature flag not found")
    update_data = flag_in.model_dump(exclude_unset=True)
    return feature_flag_crud.update(db, db_obj=flag, obj_in=update_data)


@router.delete("/feature-flags/{flag_id}")
def delete_feature_flag(
    flag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """Delete a feature flag override."""
    flag = feature_flag_crud.get(db, id=flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Feature flag not found")
    feature_flag_crud.remove(db, id=flag_id)
    return {"detail": "Feature flag deleted"}


# =============================================================================
#  Licensing Limits
# =============================================================================

@router.get("/limits", response_model=LicensingLimitListResponse)
def list_limits(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    plan_id: Optional[int] = Query(None),
    current_user: User = Depends(deps.require_permission("billing.view")),
) -> Any:
    """List licensing limits."""
    if plan_id:
        limits = licensing_limit_crud.get_by_plan(db, plan_id)
        return {"total": len(limits), "limits": limits}
    return {"total": 0, "limits": []}


@router.post("/limits", response_model=LicensingLimitResponse)
def create_limit(
    limit_in: LicensingLimitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """Create a licensing limit for a plan."""
    existing = licensing_limit_crud.get_by_plan_and_type(
        db, plan_id=limit_in.plan_id, limit_type=limit_in.limit_type
    )
    if existing:
        raise HTTPException(status_code=409, detail="Limit already exists for this plan and type")
    return licensing_limit_crud.create(db, obj_in=limit_in)


@router.put("/limits/{limit_id}", response_model=LicensingLimitResponse)
def update_limit(
    limit_id: int,
    limit_in: LicensingLimitUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.manage")),
) -> Any:
    """Update a licensing limit."""
    limit = licensing_limit_crud.get(db, id=limit_id)
    if not limit:
        raise HTTPException(status_code=404, detail="Licensing limit not found")
    update_data = limit_in.model_dump(exclude_unset=True)
    return licensing_limit_crud.update(db, db_obj=limit, obj_in=update_data)


# =============================================================================
#  Feature Access & Usage
# =============================================================================

@router.get("/check/{feature_code}", response_model=FeatureEnforcementResult)
def check_feature_access(
    feature_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Check if the current user's organization can access a feature.
    No admin permission required — accessible to all authenticated users."""
    result = subscription_service.check_feature_access(
        db, current_user.org_id, feature_code
    )
    return FeatureEnforcementResult(**result)


@router.get("/orgs/{org_id}/usage", response_model=LicenseUsageResponse)
def get_org_usage(
    org_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.view")),
) -> Any:
    """Get licensing usage statistics for an organization."""
    usage = subscription_service.get_org_usage_stats(db, org_id)
    return LicenseUsageResponse(**usage)


@router.get("/module-summary")
def get_module_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("billing.view")),
) -> Any:
    """Get summary of features grouped by module."""
    summaries = subscription_service.get_module_summary(db)
    return {"modules": summaries, "total_modules": len(summaries)}


# =============================================================================
#  My Organization Subscription (Self-Service)
# =============================================================================

@router.get("/my/subscription", response_model=OrgSubscriptionDetailResponse)
def get_my_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get the current user's organization subscription.
    No admin permission required."""
    sub = org_subscription_crud.get_by_org(db, current_user.org_id)
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found for your organization")

    return _build_subscription_detail_response(sub, db, current_user.org_id)


@router.get("/my/features")
def get_my_features(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get enabled features for the current user's organization.
    No admin permission required."""
    features = subscription_service.get_enabled_features_for_org(db, current_user.org_id)
    return {
        "features": [f.code for f in features],
        "count": len(features),
    }
