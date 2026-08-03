"""
scope_deps.py — FastAPI Scope & Ownership Authorization Dependencies (Sprint 2, Entity 3)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.db.models.all_models import User
from app.services.scope_resolver import ScopeResolver, EffectiveScope
from app.services.ownership_service import OwnershipService

logger = logging.getLogger(__name__)


def require_scope(permission_code: str, min_scope_level: int = 10):
    """Dependency verifying user has permission AND required data scope level."""
    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        current_user: User = Depends(deps.require_permission(permission_code)),
    ) -> EffectiveScope:
        eff_scope = ScopeResolver.resolve_effective_scope(db, current_user, permission_code)
        if eff_scope.scope_level < min_scope_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient data scope level ({eff_scope.scope_level} < required {min_scope_level})",
            )
        request.state.effective_scope = eff_scope
        return eff_scope
    return dependency


def require_scope_level(min_level: int):
    """Dependency restricting endpoint by scope level."""
    def dependency(
        db: Session = Depends(get_db),
        current_user: User = Depends(deps.get_current_active_user),
    ) -> User:
        role_name = current_user.role.name if current_user.role else ""
        role_tier = current_user.role.tier if current_user.role else "organization"
        is_platform = role_name == "SuperAdmin" or role_tier == "platform"
        if is_platform:
            return current_user
        scope_level = 10
        if role_name == "OrgAdmin":
            scope_level = 80
        elif role_name == "DepartmentManager":
            scope_level = 60
        if scope_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User scope level {scope_level} is below required level {min_level}",
            )
        return current_user
    return dependency


def require_ownership(entity_type: str, entity_id_param: str = "id"):
    """Dependency restricting access to resource owners or delegates."""
    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        current_user: User = Depends(deps.get_current_active_user),
    ) -> User:
        entity_id = request.path_params.get(entity_id_param) or request.query_params.get(entity_id_param)
        if not entity_id:
            return current_user

        role_name = current_user.role.name if current_user.role else ""
        role_tier = current_user.role.tier if current_user.role else ""
        if role_name in ("SuperAdmin", "OrgAdmin") or role_tier == "platform":
            return current_user

        is_owner = OwnershipService.validate_ownership(db, current_user.id, entity_type, str(entity_id))
        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not own or have delegated access to {entity_type} resource '{entity_id}'",
            )
        return current_user
    return dependency


def require_self_or_scope(permission_code: str):
    """Allows self-access OR requires higher scope permission."""
    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        current_user: User = Depends(deps.get_current_active_user),
    ) -> EffectiveScope:
        target_user_id = request.path_params.get("user_id") or request.path_params.get("id")
        eff_scope = ScopeResolver.resolve_effective_scope(db, current_user, permission_code)
        if target_user_id and str(current_user.id) == str(target_user_id):
            return eff_scope
        if eff_scope.scope_level <= 10 and not eff_scope.is_org_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Self-scope user cannot access other users' resources",
            )
        return eff_scope
    return dependency


def require_department_scope():
    return require_scope_level(60)


def require_hierarchy_scope():
    return require_scope_level(20)


def require_org_scope():
    return require_scope_level(80)


def require_platform_scope():
    return require_scope_level(100)
