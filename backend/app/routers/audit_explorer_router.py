"""
audit_explorer_router.py — Enterprise Audit Explorer & Compliance Router
Sprint 9 — Enterprise Intelligence & Analytics Layer

Endpoints:
  GET  /api/v1/compliance/audit-logs     — Deep search audit trail
  POST /api/v1/compliance/security-events — Log & classify security event
  GET  /api/v1/compliance/security-events — List classified security events
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.api import deps
from app.db.models.all_models import User, SecurityEventLog, AuditLog
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)
router = APIRouter()


# Audit and security-event records expose who did what, from which IP, with what
# payload. This router previously required only an active session, so mounting
# it unchanged would have handed the full audit trail to every employee in the
# organization, including interns and viewers. `audit.view` / `audit.write` are
# held only by platform roles, which is the correct boundary: an organization's
# payroll edits and permission grants are a platform-audit concern.
_can_view_audit = deps.require_permission("audit.view")
_can_write_audit = deps.require_permission("audit.write")


class SecurityEventCreate(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=80)
    severity: str = Field("INFO", pattern="^(INFO|WARNING|ERROR|CRITICAL)$")
    ip_address: Optional[str] = None
    correlation_id: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None


@router.get(
    "/audit-logs",
    summary="Search audit log records with filters",
    tags=["compliance"],
)
async def search_audit_logs(
    module: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(_can_view_audit),
    db: Session = Depends(deps.get_db),
):
    """Searches tamper-evident platform audit logs for tenant."""
    org_id_str = str(current_user.org_id) if current_user.org_id else None
    logs, total = audit_service.search(
        organization_id=org_id_str,
        module=module,
        limit=limit,
    )
    return {
        "total": total,
        "logs": logs,
    }


@router.post(
    "/security-events",
    summary="Classify and log a security event",
    tags=["compliance"],
)
async def create_security_event(
    body: SecurityEventCreate,
    current_user: User = Depends(_can_write_audit),
    db: Session = Depends(deps.get_db),
):
    """Records a classified security event (e.g., failed auth, policy breach)."""
    event = SecurityEventLog(
        organization_id=current_user.org_id,
        actor_user_id=current_user.id,
        event_type=body.event_type,
        severity=body.severity,
        ip_address=body.ip_address,
        correlation_id=body.correlation_id,
        meta_data=body.meta_data or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return {
        "id": event.id,
        "event_type": event.event_type,
        "severity": event.severity,
        "created_at": event.created_at.isoformat() if event.created_at else "",
    }


@router.get(
    "/security-events",
    summary="List security event logs",
    tags=["compliance"],
)
async def list_security_events(
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(_can_view_audit),
    db: Session = Depends(deps.get_db),
):
    """Retrieves classified security event logs for organization."""
    filters = []
    if current_user.org_id:
        filters.append(SecurityEventLog.organization_id == current_user.org_id)
    if severity:
        filters.append(SecurityEventLog.severity == severity.upper())

    stmt = select(SecurityEventLog).where(and_(*filters)).order_by(
        SecurityEventLog.created_at.desc()
    ).limit(limit)
    events = db.scalars(stmt).all()

    return [
        {
            "id": e.id,
            "organization_id": str(e.organization_id) if e.organization_id else None,
            "actor_user_id": e.actor_user_id,
            "event_type": e.event_type,
            "severity": e.severity,
            "ip_address": e.ip_address,
            "correlation_id": e.correlation_id,
            "created_at": e.created_at.isoformat() if e.created_at else "",
        }
        for e in events
    ]
