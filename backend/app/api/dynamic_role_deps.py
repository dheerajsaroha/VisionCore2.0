"""
dynamic_role_deps.py — Security & Dependency Injectors for Enterprise Dynamic Roles
Sprint 2 — Entity 5
"""
from __future__ import annotations
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_active_user
from app.db.models.all_models import User

def require_role_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Verifies user has SuperAdmin or OrgAdmin privileges to manage dynamic roles."""
    role_name = current_user.role.name if current_user.role else ""
    if role_name not in ["SuperAdmin", "OrgAdmin", "SystemAdmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dynamic role management requires SuperAdmin or OrgAdmin privileges"
        )
    return current_user
