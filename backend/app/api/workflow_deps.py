"""
workflow_deps.py — Security & Dependency Injectors for Enterprise Workflows
Sprint 2 — Entity 4
"""
from __future__ import annotations
from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_active_user
from app.db.models.all_models import User
from app.services.workflow_engine import ApprovalService
from app.crud import crud_workflow

def require_workflow_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Verifies user has platform or org administration rights for workflow configuration."""
    role_name = current_user.role.name if current_user.role else ""
    if role_name not in ["SuperAdmin", "OrgAdmin", "SystemAdmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workflow management requires SuperAdmin or OrgAdmin permissions"
        )
    return current_user

def require_approver_authorization(request_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> User:
    """Verifies that the authenticated user is an authorized approver for the request."""
    role_name = current_user.role.name if current_user.role else ""
    if role_name == "SuperAdmin":
        return current_user  # SuperAdmin override

    is_authorized = ApprovalService.is_user_authorized_approver(db, current_user.id, request_id)
    if not is_authorized:
        req = crud_workflow.get_request_by_id(db, request_id)
        if req and req.requester_user_id == current_user.id:
            return current_user  # Requester can cancel/view their own request
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user is not an authorized approver for this request"
        )
    return current_user
