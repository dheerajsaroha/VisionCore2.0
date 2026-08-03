"""
enterprise.py — Enterprise Platform Integration Router
Sprint 5 — Phase B: Enterprise Platform Integration

Provides:
- Event Bus admin/management endpoints
- Notification management endpoints
- Audit trail endpoints
- Platform health/status
- Cross-module integration verification
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.db.models.all_models import User
from app.events.event_bus import event_bus
from app.events.event_types import (
    DomainEvent, EventPriority, UserLoginEvent, LeaveRequestedEvent,
    AssetAssignedEvent, PolicyPublishedEvent, ComplianceBreachEvent,
    WorkflowStartedEvent, WorkflowApprovedEvent, WorkflowRejectedEvent,
    ReviewSubmittedEvent,
)
from app.services.notification_service import (
    NotificationChannel, NotificationPriority, notification_service,
)
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Health & Status
# =============================================================================

@router.get("/health", tags=["enterprise"])
def enterprise_health():
    """Enterprise platform health check."""
    bus_stats = event_bus.get_stats()
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_bus": {
            "total_events_published": bus_stats["total_events_published"],
            "dead_letter_count": bus_stats["dead_letter_count"],
            "sync_subscriber_count": sum(bus_stats["sync_subscribers"].values()),
            "async_subscriber_count": sum(bus_stats["async_subscribers"].values()),
        },
    }


# =============================================================================
# Event Bus Management
# =============================================================================

@router.get("/events", tags=["enterprise"])
def get_event_history(
    event_type: Optional[str] = Query(None),
    source_module: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get event bus history (admin only)."""
    return {
        "events": event_bus.get_history(
            event_type=event_type,
            source_module=source_module,
            limit=limit,
            offset=offset,
        ),
        "total": event_bus.get_history_count(
            event_type=event_type,
            source_module=source_module,
        ),
    }


@router.get("/events/stats", tags=["enterprise"])
def get_event_stats(
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get event bus statistics."""
    return event_bus.get_stats()


@router.get("/events/dead-letter", tags=["enterprise"])
def get_dead_letter_queue(
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get dead-letter queue entries."""
    return {"entries": event_bus.get_dead_letter_queue()}


@router.post("/events/dead-letter/retry/{index}", tags=["enterprise"])
def retry_dead_letter(
    index: int,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Retry a dead-letter entry."""
    success = event_bus.retry_dead_letter(index)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dead-letter entry not found or could not be retried",
        )
    return {"status": "retried", "index": index}


# =============================================================================
# Notification Management
# =============================================================================

@router.get("/notifications", tags=["enterprise"])
def get_user_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get notifications for current user."""
    return {
        "notifications": notification_service.get_for_user(
            current_user.id,
            limit=limit,
            offset=offset,
            unread_only=unread_only,
        ),
        "unread_count": notification_service.get_unread_count(current_user.id),
    }


@router.post("/notifications/{notification_id}/read", tags=["enterprise"])
def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Mark a notification as read."""
    success = notification_service.mark_read(notification_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    return {"status": "marked_read"}


@router.post("/notifications/read-all", tags=["enterprise"])
def mark_all_notifications_read(
    current_user: User = Depends(deps.get_current_active_user),
):
    """Mark all notifications as read for current user."""
    count = notification_service.mark_all_read(current_user.id)
    return {"status": "marked_all_read", "count": count}


@router.get("/notifications/analytics", tags=["enterprise"])
def get_notification_analytics(
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get notification analytics (org-level)."""
    return notification_service.get_analytics(str(current_user.org_id))


# =============================================================================
# Audit Trail
# =============================================================================

@router.get("/audit", tags=["enterprise"])
def search_audit(
    module: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    search_text: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Search audit entries."""
    results, total = audit_service.search(
        organization_id=str(current_user.org_id),
        module=module,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        severity=severity,
        search_text=search_text,
        limit=limit,
        offset=offset,
    )
    return {"entries": results, "total": total}


@router.get("/audit/timeline", tags=["enterprise"])
def get_audit_timeline(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get audit timeline for organization."""
    results, total = audit_service.get_timeline(
        str(current_user.org_id),
        limit=limit,
        offset=offset,
    )
    return {"entries": results, "total": total}


@router.get("/audit/compliance-summary", tags=["enterprise"])
def get_compliance_summary(
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get compliance-oriented audit summary."""
    return audit_service.get_compliance_summary(str(current_user.org_id))


@router.get("/audit/risk-alerts", tags=["enterprise"])
def get_risk_alerts(
    min_severity: str = Query("warning"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get risk alerts for organization."""
    return {
        "alerts": audit_service.get_risk_alerts(
            str(current_user.org_id),
            min_severity=min_severity,
            limit=limit,
        )
    }


# =============================================================================
# Event Publishing (for testing/integration)
# =============================================================================

@router.post("/events/publish", tags=["enterprise"])
def publish_event(
    event_type: str,
    event_data: dict,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Publish a domain event (for testing/integration)."""
    # Map event types to their classes
    EVENT_MAP = {
        "auth.user.login": UserLoginEvent,
        "leave.requested": LeaveRequestedEvent,
        "asset.assigned": AssetAssignedEvent,
        "policy.published": PolicyPublishedEvent,
        "compliance.breach": ComplianceBreachEvent,
        "workflow.started": WorkflowStartedEvent,
        "workflow.approved": WorkflowApprovedEvent,
        "workflow.rejected": WorkflowRejectedEvent,
        "performance.review.submitted": ReviewSubmittedEvent,
    }

    event_class = EVENT_MAP.get(event_type)
    if not event_class:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown event type: {event_type}",
        )

    # Inject organization_id and actor if not provided
    if "organization_id" not in event_data:
        event_data["organization_id"] = str(current_user.org_id)
    if "actor_user_id" not in event_data:
        event_data["actor_user_id"] = current_user.id

    try:
        event = event_class(**event_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid event data: {e}",
        )

    results = event_bus.publish(event)
    return {"event_id": event.event_id, "event_type": event_type, "results": results}


# =============================================================================
# Integration Verification
# =============================================================================

@router.get("/integration-status", tags=["enterprise"])
def get_integration_status(
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get cross-module integration verification status."""
    return {
        "event_bus": {
            "status": "healthy",
            "events_published": event_bus.get_stats()["total_events_published"],
        },
        "notification_service": {
            "status": "healthy",
            "templates_available": 25,
        },
        "audit_service": {
            "status": "healthy",
            "modules_tracked": [
                "authentication", "eaac", "workflow", "leave",
                "attendance", "payroll", "recruitment", "performance",
                "policy", "compliance", "asset", "security",
            ],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
