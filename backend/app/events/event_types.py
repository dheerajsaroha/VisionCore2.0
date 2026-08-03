"""
event_types.py — Domain Event Definitions for VisionCore v2.0 Enterprise Event Bus
Sprint 5 — Phase B: Enterprise Platform Integration

Defines all domain events across the platform.
Events are immutable dataclasses used by the EventBus for cross-module communication.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class EventPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class EventStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


@dataclass
class DomainEvent:
    """Base class for all domain events."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_module: str = ""
    organization_id: Optional[str] = None
    actor_user_id: Optional[int] = None
    priority: EventPriority = EventPriority.NORMAL
    metadata: dict = field(default_factory=dict)
    version: int = 1


# =============================================================================
# AUTHENTICATION EVENTS
# =============================================================================

@dataclass
class UserLoginEvent(DomainEvent):
    event_type: str = "auth.user.login"
    source_module: str = "authentication"
    user_id: int = 0
    email: str = ""
    session_id: str = ""
    ip_address: str = ""
    device_info: str = ""
    success: bool = True
    failure_reason: Optional[str] = None


@dataclass
class UserLogoutEvent(DomainEvent):
    event_type: str = "auth.user.logout"
    source_module: str = "authentication"
    user_id: int = 0
    session_id: str = ""


@dataclass
class TokenRefreshedEvent(DomainEvent):
    event_type: str = "auth.token.refreshed"
    source_module: str = "authentication"
    user_id: int = 0
    old_jti: str = ""
    new_jti: str = ""


@dataclass
class TokenRevokedEvent(DomainEvent):
    event_type: str = "auth.token.revoked"
    source_module: str = "authentication"
    user_id: int = 0
    jti: str = ""
    reason: str = ""


# =============================================================================
# ORGANIZATION EVENTS
# =============================================================================

@dataclass
class OrganizationCreatedEvent(DomainEvent):
    event_type: str = "org.created"
    source_module: str = "organization"
    organization_id: str = ""
    org_name: str = ""
    created_by_user_id: int = 0


@dataclass
class OrganizationUpdatedEvent(DomainEvent):
    event_type: str = "org.updated"
    source_module: str = "organization"
    organization_id: str = ""
    updated_fields: list = field(default_factory=list)


# =============================================================================
# EAAC EVENTS
# =============================================================================

@dataclass
class PermissionGrantedEvent(DomainEvent):
    event_type: str = "eaac.permission.granted"
    source_module: str = "eaac"
    user_id: int = 0
    role_id: int = 0
    permission: str = ""
    granted_by_user_id: int = 0


@dataclass
class PermissionRevokedEvent(DomainEvent):
    event_type: str = "eaac.permission.revoked"
    source_module: str = "eaac"
    user_id: int = 0
    role_id: int = 0
    permission: str = ""
    revoked_by_user_id: int = 0


@dataclass
class RoleAssignedEvent(DomainEvent):
    event_type: str = "eaac.role.assigned"
    source_module: str = "eaac"
    user_id: int = 0
    role_id: int = 0
    role_name: str = ""
    assigned_by_user_id: int = 0


@dataclass
class RoleChangedEvent(DomainEvent):
    event_type: str = "eaac.role.changed"
    source_module: str = "eaac"
    role_id: int = 0
    role_name: str = ""
    changed_by_user_id: int = 0
    changes: dict = field(default_factory=dict)


@dataclass
class SubscriptionCreatedEvent(DomainEvent):
    event_type: str = "subscription.created"
    source_module: str = "subscription"
    organization_id: str = ""
    plan_id: int = 0
    plan_name: str = ""


@dataclass
class SubscriptionExpiredEvent(DomainEvent):
    event_type: str = "subscription.expired"
    source_module: str = "subscription"
    organization_id: str = ""
    plan_id: int = 0
    plan_name: str = ""


@dataclass
class SubscriptionPlanChangedEvent(DomainEvent):
    event_type: str = "subscription.plan_changed"
    source_module: str = "subscription"
    organization_id: str = ""
    old_plan_id: int = 0
    new_plan_id: int = 0
    old_plan_name: str = ""
    new_plan_name: str = ""


# =============================================================================
# HR EVENTS
# =============================================================================

@dataclass
class LeaveRequestedEvent(DomainEvent):
    event_type: str = "leave.requested"
    source_module: str = "leave"
    leave_request_id: int = 0
    user_id: int = 0
    leave_type: str = ""
    start_date: str = ""
    end_date: str = ""
    total_days: float = 0.0


@dataclass
class LeaveApprovedEvent(DomainEvent):
    event_type: str = "leave.approved"
    source_module: str = "leave"
    leave_request_id: int = 0
    user_id: int = 0
    approver_user_id: int = 0
    leave_type: str = ""
    total_days: float = 0.0


@dataclass
class LeaveRejectedEvent(DomainEvent):
    event_type: str = "leave.rejected"
    source_module: str = "leave"
    leave_request_id: int = 0
    user_id: int = 0
    approver_user_id: int = 0
    reason: str = ""


@dataclass
class LeaveCancelledEvent(DomainEvent):
    event_type: str = "leave.cancelled"
    source_module: str = "leave"
    leave_request_id: int = 0
    user_id: int = 0


@dataclass
class AttendanceCheckedInEvent(DomainEvent):
    event_type: str = "attendance.checked_in"
    source_module: str = "attendance"
    attendance_log_id: int = 0
    user_id: int = 0
    timestamp: str = ""
    status: str = ""


@dataclass
class AttendanceCheckedOutEvent(DomainEvent):
    event_type: str = "attendance.checked_out"
    source_module: str = "attendance"
    attendance_log_id: int = 0
    user_id: int = 0
    timestamp: str = ""
    duration_hours: float = 0.0


@dataclass
class AttendanceCorrectedEvent(DomainEvent):
    event_type: str = "attendance.corrected"
    source_module: str = "attendance"
    correction_id: int = 0
    user_id: int = 0
    admin_user_id: int = 0
    reason: str = ""


@dataclass
class PayrollGeneratedEvent(DomainEvent):
    event_type: str = "payroll.generated"
    source_module: str = "payroll"
    payroll_id: int = 0
    user_id: int = 0
    month: int = 0
    year: int = 0
    total_salary: float = 0.0


@dataclass
class PayrollPaidEvent(DomainEvent):
    event_type: str = "payroll.paid"
    source_module: str = "payroll"
    payroll_id: int = 0
    user_id: int = 0
    month: int = 0
    year: int = 0


@dataclass
class CandidateAppliedEvent(DomainEvent):
    event_type: str = "recruitment.candidate.applied"
    source_module: str = "recruitment"
    application_id: int = 0
    candidate_id: int = 0
    job_posting_id: int = 0
    candidate_name: str = ""


@dataclass
class CandidateHiredEvent(DomainEvent):
    event_type: str = "recruitment.candidate.hired"
    source_module: str = "recruitment"
    application_id: int = 0
    candidate_id: int = 0
    job_posting_id: int = 0
    candidate_name: str = ""


@dataclass
class InterviewScheduledEvent(DomainEvent):
    event_type: str = "recruitment.interview.scheduled"
    source_module: str = "recruitment"
    interview_id: int = 0
    application_id: int = 0
    candidate_name: str = ""
    interviewer_user_id: int = 0
    scheduled_at: str = ""


# =============================================================================
# PERFORMANCE EVENTS
# =============================================================================

@dataclass
class ReviewSubmittedEvent(DomainEvent):
    event_type: str = "performance.review.submitted"
    source_module: str = "performance"
    review_id: int = 0
    reviewee_user_id: int = 0
    reviewer_user_id: int = 0
    review_type: str = ""
    overall_score: float = 0.0


@dataclass
class ReviewAcknowledgedEvent(DomainEvent):
    event_type: str = "performance.review.acknowledged"
    source_module: str = "performance"
    review_id: int = 0
    reviewee_user_id: int = 0


@dataclass
class PromotionRecommendedEvent(DomainEvent):
    event_type: str = "performance.promotion.recommended"
    source_module: str = "performance"
    promotion_id: int = 0
    user_id: int = 0
    proposed_role: str = ""
    readiness_score: float = 0.0


@dataclass
class PromotionApprovedEvent(DomainEvent):
    event_type: str = "performance.promotion.approved"
    source_module: str = "performance"
    promotion_id: int = 0
    user_id: int = 0
    proposed_role: str = ""
    decided_by_user_id: int = 0


# =============================================================================
# POLICY CENTER EVENTS
# =============================================================================

@dataclass
class PolicyPublishedEvent(DomainEvent):
    event_type: str = "policy.published"
    source_module: str = "policy"
    document_id: int = 0
    title: str = ""
    published_by_user_id: int = 0
    policy_type: str = ""


@dataclass
class PolicyAcknowledgedEvent(DomainEvent):
    event_type: str = "policy.acknowledged"
    source_module: str = "policy"
    document_id: int = 0
    user_id: int = 0
    acknowledged: bool = True


@dataclass
class ComplianceBreachEvent(DomainEvent):
    event_type: str = "compliance.breach"
    source_module: str = "compliance"
    organization_id: str = ""
    breach_type: str = ""
    severity: str = ""
    details: dict = field(default_factory=dict)
    priority: EventPriority = EventPriority.HIGH


# =============================================================================
# ASSET MANAGEMENT EVENTS
# =============================================================================

@dataclass
class AssetAssignedEvent(DomainEvent):
    event_type: str = "asset.assigned"
    source_module: str = "asset"
    asset_id: int = 0
    asset_tag: str = ""
    asset_name: str = ""
    assigned_to_user_id: int = 0
    assigned_by_user_id: int = 0
    assignment_type: str = ""


@dataclass
class AssetReturnedEvent(DomainEvent):
    event_type: str = "asset.returned"
    source_module: str = "asset"
    asset_id: int = 0
    asset_tag: str = ""
    asset_name: str = ""
    returned_by_user_id: int = 0
    condition: str = ""


@dataclass
class AssetMaintenanceDueEvent(DomainEvent):
    event_type: str = "asset.maintenance_due"
    source_module: str = "asset"
    asset_id: int = 0
    asset_tag: str = ""
    asset_name: str = ""
    maintenance_type: str = ""
    priority: EventPriority = EventPriority.HIGH


@dataclass
class AssetLicenseExpiringEvent(DomainEvent):
    event_type: str = "asset.license_expiring"
    source_module: str = "asset"
    license_id: int = 0
    asset_id: int = 0
    license_key: str = ""
    expiry_date: str = ""
    days_remaining: int = 0
    priority: EventPriority = EventPriority.HIGH


# =============================================================================
# WORKFLOW EVENTS
# =============================================================================

@dataclass
class WorkflowStartedEvent(DomainEvent):
    event_type: str = "workflow.started"
    source_module: str = "workflow"
    request_id: int = 0
    requester_user_id: int = 0
    entity_type: str = ""
    entity_id: str = ""
    workflow_name: str = ""


@dataclass
class WorkflowApprovedEvent(DomainEvent):
    event_type: str = "workflow.approved"
    source_module: str = "workflow"
    request_id: int = 0
    actor_user_id: int = 0
    entity_type: str = ""
    entity_id: str = ""
    stage_name: str = ""


@dataclass
class WorkflowRejectedEvent(DomainEvent):
    event_type: str = "workflow.rejected"
    source_module: str = "workflow"
    request_id: int = 0
    actor_user_id: int = 0
    entity_type: str = ""
    entity_id: str = ""
    reason: str = ""


@dataclass
class WorkflowEscalatedEvent(DomainEvent):
    event_type: str = "workflow.escalated"
    source_module: str = "workflow"
    request_id: int = 0
    escalated_to_user_id: int = 0
    entity_type: str = ""
    entity_id: str = ""
    reason: str = ""
    priority: EventPriority = EventPriority.HIGH


# =============================================================================
# TENANT LIFECYCLE EVENTS (Sprint 6 — Phase A)
# =============================================================================

@dataclass
class TenantProvisionedEvent(DomainEvent):
    """Published when a new tenant is fully provisioned."""
    event_type: str = "tenant.provisioned"
    source_module: str = "tenant_provisioning"
    organization_id: str = ""
    org_name: str = ""
    admin_user_id: int = 0
    admin_email: str = ""
    subscription_plan: str = ""
    provisioning_time_ms: float = 0.0


@dataclass
class TenantActivatedEvent(DomainEvent):
    """Published when a tenant is activated."""
    event_type: str = "tenant.activated"
    source_module: str = "tenant_lifecycle"
    organization_id: str = ""
    actor_user_id: Optional[int] = None
    reason: str = ""


@dataclass
class TenantSuspendedEvent(DomainEvent):
    """Published when a tenant is suspended."""
    event_type: str = "tenant.suspended"
    source_module: str = "tenant_lifecycle"
    organization_id: str = ""
    actor_user_id: Optional[int] = None
    reason: str = ""
    priority: EventPriority = EventPriority.HIGH


@dataclass
class TenantArchivedEvent(DomainEvent):
    """Published when a tenant is archived."""
    event_type: str = "tenant.archived"
    source_module: str = "tenant_lifecycle"
    organization_id: str = ""
    actor_user_id: Optional[int] = None
    reason: str = ""


@dataclass
class TenantDeletedEvent(DomainEvent):
    """Published when a tenant is permanently deleted."""
    event_type: str = "tenant.deleted"
    source_module: str = "tenant_lifecycle"
    organization_id: str = ""
    actor_user_id: Optional[int] = None
    reason: str = ""
    priority: EventPriority = EventPriority.HIGH


@dataclass
class TenantRestoredEvent(DomainEvent):
    """Published when a tenant is restored from archived/suspended state."""
    event_type: str = "tenant.restored"
    source_module: str = "tenant_lifecycle"
    organization_id: str = ""
    actor_user_id: Optional[int] = None
    reason: str = ""


@dataclass
class BrandingUpdatedEvent(DomainEvent):
    """Published when tenant branding is updated."""
    event_type: str = "tenant.branding.updated"
    source_module: str = "tenant_branding"
    organization_id: str = ""
    updated_fields: list = field(default_factory=list)
    actor_user_id: Optional[int] = None


@dataclass
class DomainVerifiedEvent(DomainEvent):
    """Published when a custom domain is verified."""
    event_type: str = "tenant.domain.verified"
    source_module: str = "tenant_domain"
    organization_id: str = ""
    domain: str = ""
    actor_user_id: Optional[int] = None


@dataclass
class ConfigurationUpdatedEvent(DomainEvent):
    """Published when tenant configuration is updated."""
    event_type: str = "tenant.config.updated"
    source_module: str = "config_center"
    organization_id: str = ""
    config_key: str = ""
    old_value: str = ""
    new_value: str = ""
    actor_user_id: Optional[int] = None


@dataclass
class SubscriptionChangedEvent(DomainEvent):
    """Published when tenant subscription plan changes."""
    event_type: str = "tenant.subscription.changed"
    source_module: str = "subscription"
    organization_id: str = ""
    old_plan: str = ""
    new_plan: str = ""
    actor_user_id: Optional[int] = None
