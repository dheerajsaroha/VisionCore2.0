"""
onboarding.py — Pydantic Schemas for Tenant Self-Service Onboarding
Sprint 6 — Phase B: Enterprise Multi-Tenant SaaS Completion
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
import re


class OnboardingStartRequest(BaseModel):
    """Start the onboarding process."""
    email: EmailStr
    organization_name: str = Field(..., min_length=2, max_length=200)

    @field_validator("organization_name")
    @classmethod
    def validate_org_name(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[a-zA-Z0-9\s\-&.,()]+$", v):
            raise ValueError("Organization name contains invalid characters")
        return v


class OnboardingStartResponse(BaseModel):
    """Response after starting onboarding."""
    session_id: str
    organization_name: str
    email: str
    current_step: str
    message: str = "Onboarding started. Please verify your email."
    expires_at: Optional[str] = None


class VerifyEmailRequest(BaseModel):
    """Verify email during onboarding."""
    session_id: str = Field(..., min_length=1)
    token: str = Field(..., min_length=1)


class VerifyOrganizationRequest(BaseModel):
    """Verify organization details."""
    session_id: str = Field(..., min_length=1)
    legal_id: Optional[str] = Field(None, max_length=100)


class CreateAdminRequest(BaseModel):
    """Create admin user and provision tenant."""
    session_id: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=200)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class SelectPlanRequest(BaseModel):
    """Select a subscription plan."""
    session_id: str = Field(..., min_length=1)
    plan_code: str = Field(..., min_length=1, max_length=50)


class SaveBrandingRequest(BaseModel):
    """Save branding preferences."""
    session_id: str = Field(..., min_length=1)
    branding: dict = Field(default_factory=dict)


class SaveConfigurationRequest(BaseModel):
    """Save configuration preferences."""
    session_id: str = Field(..., min_length=1)
    config: dict = Field(default_factory=dict)


class CompleteOnboardingRequest(BaseModel):
    """Complete the onboarding process."""
    session_id: str = Field(..., min_length=1)


class OnboardingProgressResponse(BaseModel):
    """Onboarding progress summary."""
    session_id: str
    email: str
    organization_name: str
    current_step: str
    completed_steps: list[str]
    total_steps: int
    completed_count: int
    progress_pct: float
    checklist: dict
    is_completed: bool
    expires_at: Optional[str] = None


class OnboardingSessionResponse(BaseModel):
    """Full onboarding session details."""
    session_id: str
    email: str
    organization_name: str
    organization_id: Optional[str] = None
    current_step: str
    completed_steps: list[str]
    email_verified: bool
    org_verified: bool
    selected_plan_code: str
    checklist: dict
    created_at: str
    updated_at: str
    expires_at: Optional[str] = None


class AvailablePlanResponse(BaseModel):
    """Available subscription plan for onboarding."""
    code: str
    name: str
    tier: int
    price_monthly: float
    price_yearly: Optional[float] = None
    max_users: int
    description: str
    is_popular: bool = False


class OnboardingStepResponse(BaseModel):
    """Generic step completion response."""
    success: bool = True
    session_id: str
    current_step: str
    next_step: Optional[str] = None
    message: str = ""


class EmailVerificationResponse(BaseModel):
    """Response after email verification."""
    success: bool = True
    session_id: str
    email_verified: bool
    current_step: str
    message: str = "Email verified successfully"


class ProvisioningResponse(BaseModel):
    """Response after tenant provisioning."""
    success: bool = True
    organization_id: str
    organization_name: str
    admin_user_id: int
    admin_email: str
    subscription_plan: str
    provisioning_time_ms: float = 0.0
    message: str = "Tenant provisioned successfully"
