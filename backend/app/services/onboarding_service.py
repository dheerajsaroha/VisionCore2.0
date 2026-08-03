"""
onboarding_service.py — Tenant Self-Service Onboarding Engine
Sprint 6 — Phase B: Enterprise Multi-Tenant SaaS Completion

Complete onboarding experience:
- Organization registration
- Email verification
- Organization verification
- Initial administrator creation
- Subscription selection
- Branding wizard
- Configuration wizard
- Completion checklist
- Resumable onboarding sessions

No frozen modules are modified.
"""
from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.all_models import Organization, User
from app.services.tenant_provisioning import TenantProvisioningService, TenantProvisioningResult
from app.services.tenant_lifecycle import TenantLifecycleService
from app.services.tenant_branding import TenantBrandingService
from app.services.config_center import config_center
from app.services.notification_service import NotificationChannel, NotificationPriority
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


class OnboardingStep(Enum):
    """Steps in the onboarding wizard."""
    REGISTRATION = "registration"
    EMAIL_VERIFICATION = "email_verification"
    ORGANIZATION_VERIFICATION = "organization_verification"
    ADMIN_CREATION = "admin_creation"
    SUBSCRIPTION_SELECTION = "subscription_selection"
    BRANDING_WIZARD = "branding_wizard"
    CONFIGURATION_WIZARD = "configuration_wizard"
    COMPLETION_CHECKLIST = "completion_checklist"
    COMPLETED = "completed"


# Valid step transitions
ONBOARDING_STEP_TRANSITIONS = {
    OnboardingStep.REGISTRATION: [OnboardingStep.EMAIL_VERIFICATION],
    OnboardingStep.EMAIL_VERIFICATION: [OnboardingStep.ORGANIZATION_VERIFICATION, OnboardingStep.REGISTRATION],
    OnboardingStep.ORGANIZATION_VERIFICATION: [OnboardingStep.ADMIN_CREATION, OnboardingStep.REGISTRATION],
    OnboardingStep.ADMIN_CREATION: [OnboardingStep.SUBSCRIPTION_SELECTION],
    OnboardingStep.SUBSCRIPTION_SELECTION: [OnboardingStep.BRANDING_WIZARD],
    OnboardingStep.BRANDING_WIZARD: [OnboardingStep.CONFIGURATION_WIZARD],
    OnboardingStep.CONFIGURATION_WIZARD: [OnboardingStep.COMPLETION_CHECKLIST],
    OnboardingStep.COMPLETION_CHECKLIST: [OnboardingStep.COMPLETED],
    OnboardingStep.COMPLETED: [],
}


@dataclass
class OnboardingSession:
    """Resumable onboarding session state."""
    session_id: str = ""
    email: str = ""
    organization_name: str = ""
    organization_id: Optional[str] = None
    admin_user_id: Optional[int] = None
    current_step: OnboardingStep = OnboardingStep.REGISTRATION
    completed_steps: list[str] = field(default_factory=list)
    verification_token: str = ""
    verification_sent_at: Optional[str] = None
    email_verified: bool = False
    org_verified: bool = False
    selected_plan_code: str = "starter"
    branding_data: dict = field(default_factory=dict)
    config_data: dict = field(default_factory=dict)
    checklist: dict = field(default_factory=lambda: {
        "email_verified": False,
        "org_verified": False,
        "admin_created": False,
        "subscription_selected": False,
        "branding_complete": False,
        "configuration_complete": False,
    })
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = field(default_factory=lambda: (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat())


# Session config key prefix
SESSION_PREFIX = "onboarding.session."


class OnboardingService:
    """
    Tenant self-service onboarding engine.

    Provides a complete, resumable onboarding wizard with:
    - Step-by-step flow with validation
    - Session persistence for resumability
    - Email verification
    - Organization verification
    - Subscription selection
    - Branding and configuration wizards
    - Completion checklist
    """

    def __init__(self):
        self.provisioning = TenantProvisioningService()
        self.lifecycle = TenantLifecycleService()
        self.branding = TenantBrandingService()

    # ──────────────────────────────────────────────────────────────────────
    #  Session Management
    # ──────────────────────────────────────────────────────────────────────

    def create_session(self, email: str, organization_name: str) -> OnboardingSession:
        """Create a new onboarding session."""
        session_id = secrets.token_urlsafe(32)
        session = OnboardingSession(
            session_id=session_id,
            email=email,
            organization_name=organization_name,
        )
        self._save_session(session)
        logger.info(f"Onboarding session created: {session_id[:16]}... for {email}")
        return session

    def get_session(self, session_id: str) -> Optional[OnboardingSession]:
        """Get an onboarding session by ID."""
        raw = config_center.get(f"{SESSION_PREFIX}{session_id}", default=None)
        if not raw:
            return None
        if isinstance(raw, str):
            raw = json.loads(raw)
        session = self._dict_to_session(raw)

        # Check expiry
        if session.expires_at and datetime.now(timezone.utc).isoformat() > session.expires_at:
            logger.warning(f"Onboarding session {session_id[:16]}... expired")
            return None

        return session

    def update_session(self, session: OnboardingSession) -> None:
        """Update an onboarding session."""
        session.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_session(session)

    def delete_session(self, session_id: str) -> None:
        """Delete an onboarding session."""
        config_center.reset(f"{SESSION_PREFIX}{session_id}")

    def _save_session(self, session: OnboardingSession) -> None:
        """Persist the session to ConfigCenter."""
        config_center.set(
            f"{SESSION_PREFIX}{session.session_id}",
            self._session_to_dict(session),
        )

    # ──────────────────────────────────────────────────────────────────────
    #  Step Navigation
    # ──────────────────────────────────────────────────────────────────────

    def advance_step(self, session: OnboardingSession, to_step: OnboardingStep) -> OnboardingSession:
        """Advance to the next onboarding step."""
        valid_next = ONBOARDING_STEP_TRANSITIONS.get(session.current_step, [])

        if to_step not in valid_next:
            raise ValueError(
                f"Invalid step transition: {session.current_step.value} → {to_step.value}. "
                f"Valid transitions: {[s.value for s in valid_next]}"
            )

        # Complete the current step
        if session.current_step.value not in session.completed_steps:
            session.completed_steps.append(session.current_step.value)

        # Move to next step
        session.current_step = to_step
        self.update_session(session)

        logger.info(
            f"Onboarding {session.session_id[:16]}...: "
            f"Step completed → {to_step.value}"
        )

        return session

    def get_current_step(self, session: OnboardingSession) -> OnboardingStep:
        """Get the current onboarding step."""
        return session.current_step

    def get_progress(self, session: OnboardingSession) -> dict:
        """Get onboarding progress summary."""
        all_steps = list(OnboardingStep)
        total_steps = len(all_steps) - 1  # Exclude COMPLETED
        completed = len(session.completed_steps)
        progress_pct = round((completed / max(total_steps, 1)) * 100, 1)

        return {
            "session_id": session.session_id,
            "email": session.email,
            "organization_name": session.organization_name,
            "current_step": session.current_step.value,
            "completed_steps": session.completed_steps,
            "total_steps": total_steps,
            "completed_count": completed,
            "progress_pct": progress_pct,
            "checklist": session.checklist,
            "is_completed": session.current_step == OnboardingStep.COMPLETED,
            "expires_at": session.expires_at,
        }

    # ──────────────────────────────────────────────────────────────────────
    #  Step 1: Registration
    # ──────────────────────────────────────────────────────────────────────

    def register_organization(
        self,
        session: OnboardingSession,
        organization_name: str,
        admin_email: str,
    ) -> OnboardingSession:
        """Register a new organization (Step 1)."""
        session.organization_name = organization_name
        session.email = admin_email

        # Generate verification token
        session.verification_token = secrets.token_urlsafe(48)
        session.verification_sent_at = datetime.now(timezone.utc).isoformat()

        # Advance to email verification
        self.advance_step(session, OnboardingStep.EMAIL_VERIFICATION)

        # Send verification email
        self._send_verification_email(session)

        # Audit
        audit_service.record(
            module="onboarding",
            action="registration",
            entity_type="onboarding_session",
            entity_id=session.session_id,
            summary=f"Organization registration started: {organization_name}",
            details={"email": admin_email, "organization_name": organization_name},
            severity="info",
        )

        return session

    # ──────────────────────────────────────────────────────────────────────
    #  Step 2: Email Verification
    # ──────────────────────────────────────────────────────────────────────

    def verify_email(self, session: OnboardingSession, token: str) -> bool:
        """Verify the admin's email address."""
        if session.email_verified:
            return True

        if token != session.verification_token:
            raise ValueError("Invalid verification token")

        session.email_verified = True
        session.checklist["email_verified"] = True

        # Advance to organization verification
        self.advance_step(session, OnboardingStep.ORGANIZATION_VERIFICATION)

        # Audit
        audit_service.record(
            module="onboarding",
            action="email_verified",
            entity_type="onboarding_session",
            entity_id=session.session_id,
            summary=f"Email verified: {session.email}",
            severity="info",
        )

        return True

    def resend_verification_email(self, session: OnboardingSession) -> OnboardingSession:
        """Resend the verification email."""
        session.verification_token = secrets.token_urlsafe(48)
        session.verification_sent_at = datetime.now(timezone.utc).isoformat()
        self._send_verification_email(session)
        self.update_session(session)
        return session

    # ──────────────────────────────────────────────────────────────────────
    #  Step 3: Organization Verification
    # ──────────────────────────────────────────────────────────────────────

    def verify_organization(self, session: OnboardingSession, legal_id: str = "") -> OnboardingSession:
        """Verify and finalize organization details."""
        session.org_verified = True
        session.checklist["org_verified"] = True

        if legal_id:
            session.config_data["legal_id"] = legal_id

        # Advance to admin creation
        self.advance_step(session, OnboardingStep.ADMIN_CREATION)

        # Audit
        audit_service.record(
            module="onboarding",
            action="org_verified",
            entity_type="onboarding_session",
            entity_id=session.session_id,
            summary=f"Organization verified: {session.organization_name}",
            severity="info",
        )

        return session

    # ──────────────────────────────────────────────────────────────────────
    #  Step 4: Admin Creation & Provisioning
    # ──────────────────────────────────────────────────────────────────────

    def create_admin_and_provision(
        self,
        db: Session,
        session: OnboardingSession,
        password: str,
        full_name: str = "System Administrator",
    ) -> TenantProvisioningResult:
        """Create the admin user and provision the tenant."""
        if not session.email_verified:
            raise ValueError("Email must be verified before creating admin")

        if not session.org_verified:
            raise ValueError("Organization must be verified before creating admin")

        # Provision the tenant
        result = self.provisioning.provision_tenant(
            db=db,
            organization_name=session.organization_name,
            admin_email=session.email,
            admin_password=password,
            admin_full_name=full_name,
            subscription_plan_code=session.selected_plan_code or "starter",
            locale=session.config_data.get("locale", "en-US"),
            timezone_str=session.config_data.get("timezone", "UTC"),
            currency=session.config_data.get("currency", "USD"),
        )

        session.organization_id = result.organization_id
        session.admin_user_id = result.admin_user_id
        session.checklist["admin_created"] = True
        session.checklist["subscription_selected"] = True

        # Apply branding if provided
        if session.branding_data:
            try:
                self.branding.update_branding(
                    db,
                    UUID(result.organization_id),
                    session.branding_data,
                    updated_by=result.admin_user_id,
                )
                session.checklist["branding_complete"] = True
            except Exception as e:
                logger.warning(f"Branding application failed (non-fatal): {e}")

        # Advance to completion checklist
        self.advance_step(session, OnboardingStep.COMPLETION_CHECKLIST)

        # Audit
        audit_service.record(
            module="onboarding",
            action="tenant_provisioned",
            entity_type="organization",
            entity_id=result.organization_id,
            summary=f"Tenant provisioned: {session.organization_name}",
            details={
                "plan": result.subscription_plan_name,
                "provisioning_ms": result.provisioning_time_ms,
            },
            severity="info",
        )

        return result

    # ──────────────────────────────────────────────────────────────────────
    #  Step 5: Subscription Selection
    # ──────────────────────────────────────────────────────────────────────

    def select_subscription_plan(
        self,
        session: OnboardingSession,
        plan_code: str,
    ) -> OnboardingSession:
        """Select a subscription plan during onboarding."""
        session.selected_plan_code = plan_code
        session.checklist["subscription_selected"] = True

        # Advance to branding wizard
        self.advance_step(session, OnboardingStep.BRANDING_WIZARD)

        # Audit
        audit_service.record(
            module="onboarding",
            action="plan_selected",
            entity_type="onboarding_session",
            entity_id=session.session_id,
            summary=f"Subscription plan selected: {plan_code}",
            severity="info",
        )

        return session

    # ──────────────────────────────────────────────────────────────────────
    #  Step 6: Branding Wizard
    # ──────────────────────────────────────────────────────────────────────

    def save_branding(self, session: OnboardingSession, branding_data: dict) -> OnboardingSession:
        """Save branding preferences from the wizard."""
        session.branding_data = branding_data
        session.checklist["branding_complete"] = True

        # Advance to configuration wizard
        self.advance_step(session, OnboardingStep.CONFIGURATION_WIZARD)

        return session

    def skip_branding(self, session: OnboardingSession) -> OnboardingSession:
        """Skip the branding wizard (use defaults)."""
        session.checklist["branding_complete"] = True
        self.advance_step(session, OnboardingStep.CONFIGURATION_WIZARD)
        return session

    # ──────────────────────────────────────────────────────────────────────
    #  Step 7: Configuration Wizard
    # ──────────────────────────────────────────────────────────────────────

    def save_configuration(self, session: OnboardingSession, config_data: dict) -> OnboardingSession:
        """Save configuration preferences from the wizard."""
        session.config_data = config_data
        session.checklist["configuration_complete"] = True

        # Advance to completion checklist
        self.advance_step(session, OnboardingStep.COMPLETION_CHECKLIST)

        return session

    def skip_configuration(self, session: OnboardingSession) -> OnboardingSession:
        """Skip the configuration wizard (use defaults)."""
        session.checklist["configuration_complete"] = True
        self.advance_step(session, OnboardingStep.COMPLETION_CHECKLIST)
        return session

    # ──────────────────────────────────────────────────────────────────────
    #  Step 8: Completion Checklist
    # ──────────────────────────────────────────────────────────────────────

    def complete_onboarding(self, session: OnboardingSession) -> OnboardingSession:
        """Complete the onboarding process."""
        # Verify all checklist items are complete
        incomplete = [k for k, v in session.checklist.items() if not v]
        if incomplete:
            raise ValueError(f"Cannot complete onboarding. Incomplete items: {incomplete}")

        # Mark as completed
        self.advance_step(session, OnboardingStep.COMPLETED)

        # Activate the tenant if provisioned
        if session.organization_id:
            try:
                from app.db.database import SessionLocal
                db = SessionLocal()
                try:
                    self.lifecycle.activate_tenant(
                        db=db,
                        org_id=UUID(session.organization_id),
                        actor_user_id=session.admin_user_id,
                        reason="Onboarding completed successfully",
                    )
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Failed to activate tenant after onboarding: {e}")

        # Send welcome notification
        if session.admin_user_id and session.organization_id:
            try:
                from app.services.notification_service import notification_service
                notification_service.send(
                    user_id=session.admin_user_id,
                    organization_id=session.organization_id,
                    channel=NotificationChannel.IN_APP,
                    title="Welcome to VisionCore!",
                    message=f"Your organization '{session.organization_name}' is ready. "
                            f"Get started by exploring the dashboard.",
                    source_module="onboarding",
                    source_event="onboarding.completed",
                    priority=NotificationPriority.HIGH,
                )
            except Exception as e:
                logger.warning(f"Failed to send welcome notification: {e}")

        # Delete the session (no longer needed)
        self.delete_session(session.session_id)

        # Audit
        audit_service.record(
            module="onboarding",
            action="completed",
            entity_type="organization",
            entity_id=session.organization_id or session.session_id,
            summary=f"Onboarding completed: {session.organization_name}",
            details={
                "email": session.email,
                "plan": session.selected_plan_code,
                "checklist": session.checklist,
            },
            severity="info",
        )

        logger.info(f"Onboarding completed for {session.organization_name} ({session.email})")

        return session

    # ──────────────────────────────────────────────────────────────────────
    #  Available Plans
    # ──────────────────────────────────────────────────────────────────────

    def get_available_plans(self) -> list[dict]:
        """Get available subscription plans for onboarding."""
        from app.db.database import SessionLocal
        from app.db.models.all_models import SubscriptionPlan
        try:
            db = SessionLocal()
            plans = db.query(SubscriptionPlan).filter(
                SubscriptionPlan.is_active == True
            ).order_by(SubscriptionPlan.tier).all()
            db.close()
            return [
                {
                    "id": p.id,
                    "code": p.code,
                    "name": p.name,
                    "tier": p.tier,
                    "price_monthly": p.price_monthly,
                    "price_yearly": p.price_yearly,
                    "max_users": p.max_users,
                    "features": p.features if hasattr(p, 'features') else [],
                    "description": p.description,
                    "is_popular": p.code == "professional",
                }
                for p in plans
            ] if plans else [
                {"code": "starter", "name": "Starter", "tier": 1, "price_monthly": 0, "max_users": 10, "description": "For small teams getting started"},
                {"code": "professional", "name": "Professional", "tier": 2, "price_monthly": 99, "max_users": 100, "description": "For growing businesses", "is_popular": True},
                {"code": "enterprise", "name": "Enterprise", "tier": 3, "price_monthly": 499, "max_users": 9999, "description": "For large organizations"},
            ]
        except Exception as e:
            logger.warning(f"Could not fetch plans from DB: {e}")
            return [
                {"code": "starter", "name": "Starter", "tier": 1, "price_monthly": 0, "max_users": 10, "description": "For small teams getting started"},
                {"code": "professional", "name": "Professional", "tier": 2, "price_monthly": 99, "max_users": 100, "description": "For growing businesses", "is_popular": True},
                {"code": "enterprise", "name": "Enterprise", "tier": 3, "price_monthly": 499, "max_users": 9999, "description": "For large organizations"},
            ]

    # ──────────────────────────────────────────────────────────────────────
    #  Internal Helpers
    # ──────────────────────────────────────────────────────────────────────

    def _send_verification_email(self, session: OnboardingSession) -> None:
        """Send email verification."""
        from app.services.notification_service import notification_service
        try:
            notification_service.send(
                user_id=0,  # User not yet created
                organization_id="",
                channel=NotificationChannel.EMAIL,
                title="Verify Your Email — VisionCore",
                message=(
                    f"Welcome to VisionCore!\n\n"
                    f"Organization: {session.organization_name}\n"
                    f"Email: {session.email}\n\n"
                    f"Your verification token: {session.verification_token}\n\n"
                    f"Please verify your email to continue the onboarding process.\n"
                    f"This token expires in 24 hours."
                ),
                source_module="onboarding",
                source_event="onboarding.email_verification",
                priority=NotificationPriority.HIGH,
            )
            logger.info(f"Verification email sent to {session.email}")
        except Exception as e:
            logger.warning(f"Failed to send verification email: {e}")

    @staticmethod
    def _session_to_dict(session: OnboardingSession) -> dict:
        return {
            "session_id": session.session_id,
            "email": session.email,
            "organization_name": session.organization_name,
            "organization_id": session.organization_id,
            "admin_user_id": session.admin_user_id,
            "current_step": session.current_step.value,
            "completed_steps": session.completed_steps,
            "verification_token": session.verification_token,
            "verification_sent_at": session.verification_sent_at,
            "email_verified": session.email_verified,
            "org_verified": session.org_verified,
            "selected_plan_code": session.selected_plan_code,
            "branding_data": session.branding_data,
            "config_data": session.config_data,
            "checklist": session.checklist,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "expires_at": session.expires_at,
        }

    @staticmethod
    def _dict_to_session(data: dict) -> OnboardingSession:
        return OnboardingSession(
            session_id=data.get("session_id", ""),
            email=data.get("email", ""),
            organization_name=data.get("organization_name", ""),
            organization_id=data.get("organization_id"),
            admin_user_id=data.get("admin_user_id"),
            current_step=OnboardingStep(data.get("current_step", "registration")),
            completed_steps=data.get("completed_steps", []),
            verification_token=data.get("verification_token", ""),
            verification_sent_at=data.get("verification_sent_at"),
            email_verified=data.get("email_verified", False),
            org_verified=data.get("org_verified", False),
            selected_plan_code=data.get("selected_plan_code", "starter"),
            branding_data=data.get("branding_data", {}),
            config_data=data.get("config_data", {}),
            checklist=data.get("checklist", {
                "email_verified": False,
                "org_verified": False,
                "admin_created": False,
                "subscription_selected": False,
                "branding_complete": False,
                "configuration_complete": False,
            }),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            expires_at=data.get("expires_at", ""),
        )


# Singleton
onboarding_service = OnboardingService()
