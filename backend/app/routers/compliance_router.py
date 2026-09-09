"""
compliance_router.py — Enterprise Data Governance & Compliance Router
Sprint 9 — Enterprise Intelligence & Analytics Layer

Endpoints:
  POST /api/v1/compliance/retention-policies  — Create/update retention policy
  GET  /api/v1/compliance/retention-policies  — List retention policies
  POST /api/v1/compliance/legal-holds         — Place legal hold
  GET  /api/v1/compliance/legal-holds         — List legal holds
  POST /api/v1/compliance/privacy-requests    — Submit DSAR privacy request
  GET  /api/v1/compliance/privacy-requests    — List privacy requests
  POST /api/v1/compliance/privacy-requests/{id}/process — Process DSAR request
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models.all_models import User
from app.services.retention_engine import retention_engine_service
from app.services.privacy_service import privacy_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class RetentionPolicyCreate(BaseModel):
    entity_category: str = Field(..., min_length=1, max_length=50)
    retention_days: int = Field(365, ge=1, le=3650)
    action_type: str = Field("ARCHIVE", pattern="^(ARCHIVE|PURGE)$")


class LegalHoldCreate(BaseModel):
    hold_name: str = Field(..., min_length=1, max_length=150)
    entity_category: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    target_user_id: Optional[int] = None


class PrivacyRequestCreate(BaseModel):
    request_type: str = Field(..., pattern="^(ACCESS_EXPORT|EXPORT|ANONYMIZATION|DELETION|RECTIFICATION)$")
    details: Optional[str] = None


class PrivacyRequestProcess(BaseModel):
    approve: bool = True
    rejection_reason: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/retention-policies", summary="Create or update retention policy", tags=["compliance"])
async def upsert_retention_policy(
    body: RetentionPolicyCreate,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
):
    """Creates or updates a data retention policy for an entity category."""
    if not current_user.org_id:
        raise HTTPException(status_code=400, detail="User has no organization context.")
    policy = retention_engine_service.upsert_retention_policy(
        db=db,
        org_id=current_user.org_id,
        entity_category=body.entity_category,
        retention_days=body.retention_days,
        action_type=body.action_type,
    )
    return {
        "id": policy.id,
        "entity_category": policy.entity_category,
        "retention_days": policy.retention_days,
        "action_type": policy.action_type,
        "is_active": policy.is_active,
    }


@router.get("/retention-policies", summary="List retention policies", tags=["compliance"])
async def list_retention_policies(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
):
    """Lists data retention policies for organization."""
    if not current_user.org_id:
        raise HTTPException(status_code=400, detail="User has no organization context.")
    policies = retention_engine_service.list_policies(db, current_user.org_id)
    return [
        {
            "id": p.id,
            "entity_category": p.entity_category,
            "retention_days": p.retention_days,
            "action_type": p.action_type,
            "is_active": p.is_active,
            "updated_at": p.updated_at.isoformat() if p.updated_at else "",
        }
        for p in policies
    ]


@router.post("/legal-holds", summary="Place a legal hold", tags=["compliance"])
async def create_legal_hold(
    body: LegalHoldCreate,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
):
    """Places a legal hold on a data category or user."""
    if not current_user.org_id:
        raise HTTPException(status_code=400, detail="User has no organization context.")
    hold = retention_engine_service.create_legal_hold(
        db=db,
        org_id=current_user.org_id,
        placed_by_user_id=current_user.id,
        hold_name=body.hold_name,
        entity_category=body.entity_category,
        description=body.description,
        target_user_id=body.target_user_id,
    )
    return {
        "id": hold.id,
        "hold_name": hold.hold_name,
        "entity_category": hold.entity_category,
        "target_user_id": hold.target_user_id,
        "is_active": hold.is_active,
    }


@router.get("/legal-holds", summary="List active legal holds", tags=["compliance"])
async def list_legal_holds(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
):
    """Lists active legal holds for organization."""
    if not current_user.org_id:
        raise HTTPException(status_code=400, detail="User has no organization context.")
    holds = retention_engine_service.list_legal_holds(db, current_user.org_id)
    return [
        {
            "id": h.id,
            "hold_name": h.hold_name,
            "entity_category": h.entity_category,
            "description": h.description,
            "target_user_id": h.target_user_id,
            "is_active": h.is_active,
            "created_at": h.created_at.isoformat() if h.created_at else "",
        }
        for h in holds
    ]


@router.post("/privacy-requests", summary="Submit a DSAR privacy request", tags=["compliance"])
async def submit_privacy_request(
    body: PrivacyRequestCreate,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
):
    """Submits a GDPR/CCPA data subject access request."""
    if not current_user.org_id:
        raise HTTPException(status_code=400, detail="User has no organization context.")
    req = privacy_service.submit_privacy_request(
        db=db,
        org_id=current_user.org_id,
        user_id=current_user.id,
        request_type=body.request_type,
        details=body.details,
    )
    return {
        "id": req.id,
        "request_type": req.request_type,
        "status": req.status,
        "created_at": req.created_at.isoformat() if req.created_at else "",
    }


@router.get("/privacy-requests", summary="List privacy requests", tags=["compliance"])
async def list_privacy_requests(
    status_filter: Optional[str] = Query(None),
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
):
    """Lists privacy requests for organization."""
    if not current_user.org_id:
        raise HTTPException(status_code=400, detail="User has no organization context.")
    reqs = privacy_service.list_privacy_requests(db, current_user.org_id, status_filter=status_filter)
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "request_type": r.request_type,
            "status": r.status,
            "details": r.details,
            "export_file_url": r.export_file_url,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in reqs
    ]


@router.post("/privacy-requests/{request_id}/process", summary="Process DSAR request", tags=["compliance"])
async def process_privacy_request(
    request_id: int,
    body: PrivacyRequestProcess,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
):
    """Approve or reject a DSAR privacy request."""
    try:
        req = privacy_service.process_request(
            db=db,
            request_id=request_id,
            processed_by_user_id=current_user.id,
            approve=body.approve,
            rejection_reason=body.rejection_reason,
        )
        return {
            "id": req.id,
            "status": req.status,
            "export_file_url": req.export_file_url,
            "completed_at": req.completed_at.isoformat() if req.completed_at else "",
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
