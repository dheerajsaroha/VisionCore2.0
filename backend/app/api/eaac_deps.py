"""
eaac_deps.py — FastAPI Dependency Injectors for Enterprise EAAC Integration
Sprint 2 — Entity 6
"""
from __future__ import annotations
from typing import Callable, Optional, Any
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_active_user
from app.db.models.all_models import User
from app.services.eaac_engine import EnterpriseAuthorizationEngine, EAACDecision


def require_eaac_authorization(
    permission: str,
    resource_type: Optional[str] = None,
    action: str = "read"
) -> Callable:
    """Dependency factory enforcing EAAC pipeline evaluation on FastAPI endpoints."""

    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ) -> EAACDecision:
        # Extract path param resource_id if available
        resource_id = request.path_params.get("id") or request.path_params.get("user_id") or request.path_params.get("ticket_id")

        decision = EnterpriseAuthorizationEngine.evaluate_access(
            db=db,
            user_id=current_user.id,
            organization_id=current_user.org_id,
            permission=permission,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action
        )

        if not decision.granted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"EAAC Access Denied: {decision.deny_reason or 'Unauthorized action'}"
            )

        return decision

    return dependency
