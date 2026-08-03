"""
tenant.py — Pydantic schemas for the Tenant Administration module
Sprint 6 — Phase A: Multi-Tenant SaaS Hardening & Tenant Provisioning
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


# =============================================================================
#  Tenant Provisioning
# =============================================================================

class TenantProvisionRequest(BaseModel):
    """Request to provision a new tenant."""
    organization_name: str = Field(..., min_length=1, max_length=200, description="Company/Organization name")
    admin_email: str = Field(..., max_length=150, description="Admin user email address")
    admin_password: str = Field(..., min_length=8, max_length=128, description="Admin user password")
    admin_full_name: str = Field(..., min_length=1, max_length=100, description="Admin user full name")
    admin_username: Optional[str] = Field(None, max_length=80, description="Admin username (defaults to email prefix)")
    legal_id: Optional[str] = Field(None, max_length=100, description="Legal entity ID")
    subscription_plan_code: Optional[str] = Field("starter", description="Subscription plan code")
    locale: Optional[str] = Field("en-US", description="Default locale")
    timezone: Optional[str] = Field("UTC", description="Default timezone")
    currency: Optional[str] = Field("USD", description="Default currency")

    @field_validator("organization_name", "admin_full_name", mode="before")
    @classmethod
    def normalize_names(cls, value: str) -> str:
        return value.strip()

    @field_validator("admin_email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("Invalid email address")
        return value


class TenantProvisionResponse(BaseModel):
    """Response from a successful tenant provisioning."""
    success: bool = True
    organization_id: str = ""
    organization_name: str = ""
    admin_user_id: int = 0
    admin_email: str = ""
    provisioning_time_ms: float = 0.0
    message: str = ""


# =============================================================================
#  Tenant List & Detail
# =============================================================================

class TenantDetailResponse(BaseModel):
    """Detailed tenant information for admin console."""
    id: str = ""
    name: str = ""
    legal_id: str = ""
    lifecycle_state: str = "unknown"
    is_active: bool = True
    user_count: int = 0
    created_at: str = ""
    branding: Optional[dict] = None
    domains: Optional[list] = None
    subscription_plan: Optional[str] = None
    subscription_status: Optional[str] = None


class TenantListResponse(BaseModel):
    """Paginated tenant list response."""
    total: int = 0
    page: int = 1
    per_page: int = 20
    tenants: list[TenantDetailResponse] = []


# =============================================================================
#  Tenant Lifecycle
# =============================================================================

class TenantLifecycleAction(BaseModel):
    """Request to perform a lifecycle action on a tenant."""
    action: str = Field(..., description="activate|suspend|resume|archive|restore|schedule_deletion|permanent_delete")
    reason: Optional[str] = Field(None, description="Reason for the action")

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        valid_actions = [
            "activate", "suspend", "resume", "archive",
            "restore", "schedule_deletion", "permanent_delete"
        ]
        if value not in valid_actions:
            raise ValueError(f"Invalid action. Must be one of: {', '.join(valid_actions)}")
        return value


# =============================================================================
#  Tenant Branding
# =============================================================================

class TenantBrandingUpdate(BaseModel):
    """Partial update for tenant branding."""
    logo_url: Optional[str] = None
    logo_dark_url: Optional[str] = None
    login_background_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    font_family: Optional[str] = None
    heading_font: Optional[str] = None
    email_logo_url: Optional[str] = None
    email_primary_color: Optional[str] = None
    email_footer_text: Optional[str] = None
    email_from_name: Optional[str] = None
    report_logo_url: Optional[str] = None
    report_primary_color: Optional[str] = None
    report_footer_text: Optional[str] = None
    pdf_logo_url: Optional[str] = None
    pdf_primary_color: Optional[str] = None
    pdf_footer_text: Optional[str] = None

    @field_validator("primary_color", "secondary_color", "accent_color",
                     "email_primary_color", "report_primary_color", "pdf_primary_color")
    @classmethod
    def validate_color(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if not value.startswith("#") or len(value) != 7:
            raise ValueError("Color must be a hex code (e.g., #4F46E5)")
        return value


# =============================================================================
#  Tenant Domains
# =============================================================================

class TenantDomainAdd(BaseModel):
    """Request to add a custom domain."""
    domain: str = Field(..., description="Custom domain (e.g., hr.company.com)")
    is_primary: bool = False
    redirect_to: Optional[str] = None

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        value = value.strip().lower()
        import re
        if not re.match(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$", value):
            raise ValueError(f"Invalid domain format: {value}")
        return value


class TenantDomainVerify(BaseModel):
    """Request to verify a domain."""
    verification_token: str = Field(..., description="Verification token from DNS TXT record")


# =============================================================================
#  Tenant Configuration
# =============================================================================

class TenantConfigUpdate(BaseModel):
    """Request to update a single configuration value."""
    key: str = Field(..., description="Configuration key")
    value: Any = Field(..., description="Configuration value")


# =============================================================================
#  Tenant Analytics
# =============================================================================

class TenantAnalyticsResponse(BaseModel):
    """Platform-wide tenant analytics."""
    total_tenants: int = 0
    active_tenants: int = 0
    suspended_tenants: int = 0
    total_users: int = 0
    avg_users_per_tenant: float = 0.0
    recent_tenants: list[dict] = []
