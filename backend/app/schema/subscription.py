"""
subscription.py — Pydantic schemas for Subscription & Feature Management (Sprint 2, Entity 2)

Covers:
- SubscriptionPlan
- OrganizationSubscription
- Feature
- PlanFeature
- FeatureFlag
- LicensingLimit
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
#  SubscriptionPlan
# =============================================================================

class SubscriptionPlanBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50,
                      description="Unique plan code — e.g. 'starter', 'professional', 'enterprise'")
    name: str = Field(..., min_length=1, max_length=100,
                      description="Display name e.g. 'Starter', 'Professional', 'Enterprise'")
    description: Optional[str] = Field(None, max_length=1000)
    tier: int = Field(..., ge=0, le=100,
                      description="Numeric tier — higher = more features (0=Starter, 1=Pro, 2=Enterprise)")
    monthly_price: float = Field(0, ge=0, description="Monthly price in currency units")
    yearly_price: float = Field(0, ge=0, description="Yearly price (annual discount)")
    currency: str = Field("USD", max_length=3, description="ISO 4217 currency code")
    trial_days: int = Field(14, ge=0, le=365, description="Number of free trial days")
    is_active: bool = True
    is_system: bool = True
    display_order: int = Field(0, ge=0, description="Sort order for plan listing")


class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass


class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    monthly_price: Optional[float] = None
    yearly_price: Optional[float] = None
    is_active: Optional[bool] = None
    trial_days: Optional[int] = None
    display_order: Optional[int] = None


class SubscriptionPlanResponse(SubscriptionPlanBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionPlanListResponse(BaseModel):
    total: int
    plans: List[SubscriptionPlanResponse]


# =============================================================================
#  OrganizationSubscription
# =============================================================================

class OrganizationSubscriptionBase(BaseModel):
    organization_id: UUID
    subscription_plan_id: int
    status: str = Field("active", pattern=r"^(active|trialing|canceled|expired|past_due|paused)$")
    billing_cycle: str = Field("monthly", pattern=r"^(monthly|yearly)$")
    auto_renew: bool = True
    start_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_date: Optional[datetime] = None


class OrganizationSubscriptionCreate(OrganizationSubscriptionBase):
    pass


class OrganizationSubscriptionUpdate(BaseModel):
    subscription_plan_id: Optional[int] = None
    status: Optional[str] = None
    billing_cycle: Optional[str] = None
    auto_renew: Optional[bool] = None
    end_date: Optional[datetime] = None


class OrganizationSubscriptionResponse(OrganizationSubscriptionBase):
    id: int
    created_at: datetime
    updated_at: datetime
    plan_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OrganizationSubscriptionListResponse(BaseModel):
    total: int
    subscriptions: List[OrganizationSubscriptionResponse]


# =============================================================================
#  Feature
# =============================================================================

class FeatureBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=100,
                      description="Unique feature code — e.g. 'attendance', 'payroll', 'ai_chat'")
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    module: str = Field(..., min_length=1, max_length=100,
                        description="Module this feature belongs to — e.g. 'HR', 'Finance', 'AI'")
    category: str = Field("core", min_length=1, max_length=100,
                          description="Category — e.g. 'Core', 'Premium', 'Add-on', 'Compliance'")
    visibility: str = Field("public", pattern=r"^(public|hidden|internal|admin)$",
                           description="Visibility level: public|hidden|internal|admin")
    dependencies: Optional[dict] = Field(None, description="JSON dict of dependencies, e.g. {'depends_on': ['attendance']}")
    deprecated: bool = False


class FeatureCreate(FeatureBase):
    pass


class FeatureUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = None
    deprecated: Optional[bool] = None
    dependencies: Optional[dict] = None


class FeatureResponse(FeatureBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FeatureListResponse(BaseModel):
    total: int
    features: List[FeatureResponse]


# =============================================================================
#  PlanFeature (Join Table)
# =============================================================================

class PlanFeatureBase(BaseModel):
    plan_id: int
    feature_id: int
    enabled: bool = True


class PlanFeatureCreate(PlanFeatureBase):
    pass


class PlanFeatureUpdate(BaseModel):
    enabled: Optional[bool] = None


class PlanFeatureResponse(PlanFeatureBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanFeatureListResponse(BaseModel):
    total: int
    plan_features: List[PlanFeatureResponse]


# =============================================================================
#  FeatureFlag (Per-Organization Override)
# =============================================================================

class FeatureFlagBase(BaseModel):
    organization_id: UUID
    feature_id: int
    enabled: bool = True
    expires_at: Optional[datetime] = None


class FeatureFlagCreate(FeatureFlagBase):
    pass


class FeatureFlagUpdate(BaseModel):
    enabled: Optional[bool] = None
    expires_at: Optional[datetime] = None


class FeatureFlagResponse(FeatureFlagBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeatureFlagListResponse(BaseModel):
    total: int
    feature_flags: List[FeatureFlagResponse]


# =============================================================================
#  LicensingLimit
# =============================================================================

class LicensingLimitBase(BaseModel):
    plan_id: Optional[int] = None
    limit_type: str = Field(..., min_length=1, max_length=100,
                            description="Limit type — e.g. 'max_employees', 'max_storage_gb', 'api_rate_limit'")
    soft_limit: Optional[int] = Field(None, ge=0, description="Soft-limit (warning threshold)")
    hard_limit: Optional[int] = Field(None, ge=0, description="Hard-limit (enforcement threshold)")
    is_unlimited: bool = Field(False, description="No limit on this resource")
    description: Optional[str] = Field(None, max_length=500)


class LicensingLimitCreate(LicensingLimitBase):
    pass


class LicensingLimitUpdate(BaseModel):
    soft_limit: Optional[int] = None
    hard_limit: Optional[int] = None
    is_unlimited: Optional[bool] = None
    description: Optional[str] = None


class LicensingLimitResponse(LicensingLimitBase):
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LicensingLimitListResponse(BaseModel):
    total: int
    limits: List[LicensingLimitResponse]


# =============================================================================
#  Composite / Convenience Schemas
# =============================================================================

class PlanWithFeaturesResponse(SubscriptionPlanResponse):
    """A plan enriched with its features and licensing limits."""
    features: List[FeatureResponse] = []
    limits: List[LicensingLimitResponse] = []


class OrgSubscriptionDetailResponse(OrganizationSubscriptionResponse):
    """Organization subscription with plan details."""
    plan: Optional[PlanWithFeaturesResponse] = None
    enabled_features: List[str] = []
    usage_stats: Optional[dict] = None
    org_name: Optional[str] = Field(None, description="Organization display name")
    cancelled_at: Optional[datetime] = Field(None, description="When cancellation was requested")


class SubscriptionUpgradeRequest(BaseModel):
    """Request to change an org's subscription plan."""
    plan_id: int
    billing_cycle: Optional[str] = None
    immediate: bool = True
    reason: Optional[str] = None


class SubscriptionCancelRequest(BaseModel):
    reason: Optional[str] = None
    immediate: bool = False


class FeatureEnforcementResult(BaseModel):
    """Result of checking whether an organization can use a feature."""
    allowed: bool
    reason: Optional[str] = None
    limit_warning: Optional[str] = None
    plan_name: Optional[str] = None


class LicenseUsageResponse(BaseModel):
    """Current license usage stats for an organization."""
    org_id: str = Field(..., alias="organization_id")
    plan_name: str
    plan_tier: int
    status: str
    limits: List[LicensingLimitResponse] = []
    current_usage: dict = {}
    warnings: List[str] = []
    blocks: List[str] = []

    model_config = ConfigDict(populate_by_name=True)


class SubscriptionSeedResponse(BaseModel):
    """Response from seeding subscription data."""
    plans: int = 0
    features: int = 0
    plan_features: int = 0
    licensing_limits: int = 0
    total: int = 0
