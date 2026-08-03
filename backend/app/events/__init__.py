# Enterprise Event Bus Package
# Centralized domain event architecture for VisionCore v2.0
# Sprint 5 — Phase B: Enterprise Platform Integration

from app.events.event_bus import EventBus, event_bus
from app.events.event_types import (
    DomainEvent,
    EventPriority,
    EventStatus,
    # Auth events
    UserLoginEvent,
    UserLogoutEvent,
    TokenRefreshedEvent,
    TokenRevokedEvent,
    # Organization events
    OrganizationCreatedEvent,
    OrganizationUpdatedEvent,
    # EAAC events
    PermissionGrantedEvent,
    PermissionRevokedEvent,
    RoleAssignedEvent,
    RoleChangedEvent,
    SubscriptionCreatedEvent,
    SubscriptionExpiredEvent,
    SubscriptionPlanChangedEvent,
    # HR events
    LeaveRequestedEvent,
    LeaveApprovedEvent,
    LeaveRejectedEvent,
    LeaveCancelledEvent,
    AttendanceCheckedInEvent,
    AttendanceCheckedOutEvent,
    AttendanceCorrectedEvent,
    PayrollGeneratedEvent,
    PayrollPaidEvent,
    CandidateAppliedEvent,
    CandidateHiredEvent,
    InterviewScheduledEvent,
    # Performance events
    ReviewSubmittedEvent,
    ReviewAcknowledgedEvent,
    PromotionRecommendedEvent,
    PromotionApprovedEvent,
    # Policy events
    PolicyPublishedEvent,
    PolicyAcknowledgedEvent,
    ComplianceBreachEvent,
    # Asset events
    AssetAssignedEvent,
    AssetReturnedEvent,
    AssetMaintenanceDueEvent,
    AssetLicenseExpiringEvent,
    # Workflow events
    WorkflowStartedEvent,
    WorkflowApprovedEvent,
    WorkflowRejectedEvent,
    WorkflowEscalatedEvent,
)

__all__ = [
    "EventBus",
    "event_bus",
    "DomainEvent",
    "EventPriority",
    "EventStatus",
    # Auth
    "UserLoginEvent",
    "UserLogoutEvent",
    "TokenRefreshedEvent",
    "TokenRevokedEvent",
    # Org
    "OrganizationCreatedEvent",
    "OrganizationUpdatedEvent",
    # EAAC
    "PermissionGrantedEvent",
    "PermissionRevokedEvent",
    "RoleAssignedEvent",
    "RoleChangedEvent",
    "SubscriptionCreatedEvent",
    "SubscriptionExpiredEvent",
    "SubscriptionPlanChangedEvent",
    # HR
    "LeaveRequestedEvent",
    "LeaveApprovedEvent",
    "LeaveRejectedEvent",
    "LeaveCancelledEvent",
    "AttendanceCheckedInEvent",
    "AttendanceCheckedOutEvent",
    "AttendanceCorrectedEvent",
    "PayrollGeneratedEvent",
    "PayrollPaidEvent",
    "CandidateAppliedEvent",
    "CandidateHiredEvent",
    "InterviewScheduledEvent",
    # Performance
    "ReviewSubmittedEvent",
    "ReviewAcknowledgedEvent",
    "PromotionRecommendedEvent",
    "PromotionApprovedEvent",
    # Policy
    "PolicyPublishedEvent",
    "PolicyAcknowledgedEvent",
    "ComplianceBreachEvent",
    # Asset
    "AssetAssignedEvent",
    "AssetReturnedEvent",
    "AssetMaintenanceDueEvent",
    "AssetLicenseExpiringEvent",
    # Workflow
    "WorkflowStartedEvent",
    "WorkflowApprovedEvent",
    "WorkflowRejectedEvent",
    "WorkflowEscalatedEvent",
]
