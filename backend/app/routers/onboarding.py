"""
onboarding.py — Tenant Self-Service Onboarding Router
Sprint 6 — Phase B: Enterprise Multi-Tenant SaaS Completion

Public endpoints for tenant self-service onboarding.
No authentication required for initial steps.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.onboarding_service import onboarding_service, OnboardingStep
from app.schema.onboarding import (
    OnboardingStartRequest, OnboardingStartResponse,
    VerifyEmailRequest, VerifyOrganizationRequest,
    CreateAdminRequest, SelectPlanRequest,
    SaveBrandingRequest, SaveConfigurationRequest,
    CompleteOnboardingRequest,
    OnboardingProgressResponse, OnboardingSessionResponse,
    AvailablePlanResponse, OnboardingStepResponse,
    EmailVerificationResponse, ProvisioningResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/start", response_model=OnboardingStartResponse, status_code=status.HTTP_201_CREATED)
def start_onboarding(
    request: OnboardingStartRequest,
):
    """Start the onboarding process for a new tenant."""
    session = onboarding_service.create_session(
        email=request.email,
        organization_name=request.organization_name,
    )

    session = onboarding_service.register_organization(
        session,
        organization_name=request.organization_name,
        admin_email=request.email,
    )

    return OnboardingStartResponse(
        session_id=session.session_id,
        organization_name=session.organization_name,
        email=session.email,
        current_step=session.current_step.value,
        expires_at=session.expires_at,
    )


@router.post("/verify-email", response_model=EmailVerificationResponse)
def verify_email(request: VerifyEmailRequest):
    """Verify email address during onboarding."""
    session = onboarding_service.get_session(request.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding session not found or expired"
        )

    try:
        onboarding_service.verify_email(session, request.token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return EmailVerificationResponse(
        session_id=session.session_id,
        email_verified=session.email_verified,
        current_step=session.current_step.value,
    )


@router.post("/resend-verification", response_model=OnboardingStepResponse)
def resend_verification(session_id: str):
    """Resend the verification email."""
    session = onboarding_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding session not found or expired"
        )

    onboarding_service.resend_verification_email(session)

    return OnboardingStepResponse(
        session_id=session.session_id,
        current_step=session.current_step.value,
        next_step=OnboardingStep.ORGANIZATION_VERIFICATION.value,
        message="Verification email resent",
    )


@router.post("/verify-organization", response_model=OnboardingStepResponse)
def verify_organization(request: VerifyOrganizationRequest):
    """Verify organization details."""
    session = onboarding_service.get_session(request.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding session not found or expired"
        )

    if not session.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email must be verified before verifying organization"
        )

    onboarding_service.verify_organization(session, legal_id=request.legal_id or "")

    return OnboardingStepResponse(
        session_id=session.session_id,
        current_step=session.current_step.value,
        next_step=OnboardingStep.ADMIN_CREATION.value,
        message="Organization verified",
    )


@router.post("/create-admin", response_model=ProvisioningResponse)
def create_admin(
    request: CreateAdminRequest,
    db: Session = Depends(get_db),
):
    """Create admin user and provision the tenant."""
    session = onboarding_service.get_session(request.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding session not found or expired"
        )

    if not session.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email must be verified first"
        )

    if not session.org_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization must be verified first"
        )

    try:
        result = onboarding_service.create_admin_and_provision(
            db=db,
            session=session,
            password=request.password,
            full_name=request.full_name,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return ProvisioningResponse(
        organization_id=result.organization_id,
        organization_name=result.organization_name,
        admin_user_id=result.admin_user_id,
        admin_email=result.admin_email,
        subscription_plan=result.subscription_plan_name,
        provisioning_time_ms=result.provisioning_time_ms,
    )


@router.post("/select-plan", response_model=OnboardingStepResponse)
def select_plan(request: SelectPlanRequest):
    """Select a subscription plan during onboarding."""
    session = onboarding_service.get_session(request.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding session not found or expired"
        )

    onboarding_service.select_subscription_plan(session, request.plan_code)

    return OnboardingStepResponse(
        session_id=session.session_id,
        current_step=session.current_step.value,
        next_step=OnboardingStep.BRANDING_WIZARD.value,
        message=f"Plan '{request.plan_code}' selected",
    )


@router.get("/plans", response_model=list[AvailablePlanResponse])
def get_available_plans():
    """Get available subscription plans for onboarding."""
    plans = onboarding_service.get_available_plans()
    return [AvailablePlanResponse(**p) for p in plans]


@router.post("/branding", response_model=OnboardingStepResponse)
def save_branding(request: SaveBrandingRequest):
    """Save branding preferences."""
    session = onboarding_service.get_session(request.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding session not found or expired"
        )

    onboarding_service.save_branding(session, request.branding)

    return OnboardingStepResponse(
        session_id=session.session_id,
        current_step=session.current_step.value,
        next_step=OnboardingStep.CONFIGURATION_WIZARD.value,
        message="Branding saved",
    )


@router.post("/skip-branding", response_model=OnboardingStepResponse)
def skip_branding(session_id: str):
    """Skip the branding wizard."""
    session = onboarding_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding session not found or expired"
        )

    onboarding_service.skip_branding(session)

    return OnboardingStepResponse(
        session_id=session.session_id,
        current_step=session.current_step.value,
        next_step=OnboardingStep.CONFIGURATION_WIZARD.value,
        message="Branding skipped (defaults will be used)",
    )


@router.post("/configuration", response_model=OnboardingStepResponse)
def save_configuration(request: SaveConfigurationRequest):
    """Save configuration preferences."""
    session = onboarding_service.get_session(request.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding session not found or expired"
        )

    onboarding_service.save_configuration(session, request.config)

    return OnboardingStepResponse(
        session_id=session.session_id,
        current_step=session.current_step.value,
        next_step=OnboardingStep.COMPLETION_CHECKLIST.value,
        message="Configuration saved",
    )


@router.post("/skip-configuration", response_model=OnboardingStepResponse)
def skip_configuration(session_id: str):
    """Skip the configuration wizard."""
    session = onboarding_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding session not found or expired"
        )

    onboarding_service.skip_configuration(session)

    return OnboardingStepResponse(
        session_id=session.session_id,
        current_step=session.current_step.value,
        next_step=OnboardingStep.COMPLETION_CHECKLIST.value,
        message="Configuration skipped (defaults will be used)",
    )


@router.post("/complete", response_model=OnboardingStepResponse)
def complete_onboarding(request: CompleteOnboardingRequest):
    """Complete the onboarding process."""
    session = onboarding_service.get_session(request.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding session not found or expired"
        )

    try:
        onboarding_service.complete_onboarding(session)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return OnboardingStepResponse(
        session_id=request.session_id,
        current_step=OnboardingStep.COMPLETED.value,
        message="Onboarding completed successfully! Welcome to VisionCore.",
    )


@router.get("/progress/{session_id}", response_model=OnboardingProgressResponse)
def get_progress(session_id: str):
    """Get the current onboarding progress."""
    session = onboarding_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding session not found or expired"
        )

    progress = onboarding_service.get_progress(session)
    return OnboardingProgressResponse(**progress)


@router.get("/session/{session_id}", response_model=OnboardingSessionResponse)
def get_session(session_id: str):
    """Get the full onboarding session details."""
    session = onboarding_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding session not found or expired"
        )

    return OnboardingSessionResponse(
        session_id=session.session_id,
        email=session.email,
        organization_name=session.organization_name,
        organization_id=session.organization_id,
        current_step=session.current_step.value,
        completed_steps=session.completed_steps,
        email_verified=session.email_verified,
        org_verified=session.org_verified,
        selected_plan_code=session.selected_plan_code,
        checklist=session.checklist,
        created_at=session.created_at,
        updated_at=session.updated_at,
        expires_at=session.expires_at,
    )
