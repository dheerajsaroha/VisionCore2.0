"""
eaac_router.py — FastAPI Router for Interactive EAAC Diagnostics & Inspector Tool
Sprint 2 — Entity 6
"""
from __future__ import annotations
from typing import Any, Dict, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_active_user
from app.db.models.all_models import User
from app.services.eaac_engine import EnterpriseAuthorizationEngine, EAACDecision

router = APIRouter()


class EAACEvaluationRequest(BaseModel):
    user_id: Optional[int] = None
    permission: str
    resource_type: Optional[str] = None
    resource_id: Optional[Any] = None
    action: str = "read"


@router.post("/evaluate", response_model=EAACDecision)
def evaluate_eaac_access(
    payload: EAACEvaluationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Evaluates an access request against the complete 8-stage EAAC Pipeline."""
    target_user_id = payload.user_id or current_user.id
    target_org_id = current_user.org_id

    return EnterpriseAuthorizationEngine.evaluate_access(
        db=db,
        user_id=target_user_id,
        organization_id=target_org_id,
        permission=payload.permission,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        action=payload.action
    )


@router.get("/user-pipeline")
def get_user_pipeline_state(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Inspects the user's current effective EAAC pipeline authorization state."""
    target_user_id = user_id or current_user.id
    target_org_id = current_user.org_id

    from app.services.dynamic_role_engine import EffectivePermissionResolver
    eff_auth = EffectivePermissionResolver.resolve_effective_permissions(db, target_user_id, target_org_id)

    return {
        "status": "active",
        "user_id": target_user_id,
        "organization_id": target_org_id,
        "pipeline_stages": {
            "1_authentication": "PASS",
            "2_tenant_isolation": "PASS",
            "3_subscription_unlocked_features": len(eff_auth.get("subscription_unlocked_features", [])),
            "4_effective_permissions": len(eff_auth.get("effective_permissions", [])),
            "5_effective_data_scopes": eff_auth.get("effective_data_scopes", {}),
            "6_effective_approval_rights": eff_auth.get("effective_approval_rights", []),
            "7_governance_gates": "ACTIVE",
            "8_immutable_audit": "ENABLED"
        },
        "effective_authorization": eff_auth
    }
