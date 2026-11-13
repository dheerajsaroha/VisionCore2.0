# Dependency utilities for authentication, permissions, and feature flags

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.api import deps as api_deps
from app.crud.crud_user import user as crud_user


def require_active_user(
    token: dict = Depends(get_current_user),
    db: Session = Depends(api_deps.get_db),
) -> dict:
    """Validate JWT payload, fetch the user from DB and ensure the account is active.
    Returns the full SQLAlchemy user object (or a Pydantic model) for downstream use.
    """
    user_id = token.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = crud_user.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if getattr(user, "is_active", True) is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended",
        )
    return user


def require_permission(permission: str):
    """Factory that checks a user has a specific permission string.
    Assumes the User model has an attribute `permissions` (list/set of strings).
    """

    async def _check(user=Depends(require_active_user)):
        perms = getattr(user, "permissions", set())
        if permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission}",
            )
        return user

    return _check


def require_feature(feature_name: str):
    """Simple feature‑flag guard – raise 404 if the feature is disabled.
    For now we look at a global setting dict `settings.FEATURES`.
    """
    from app.core.config import settings

    async def _check(user=Depends(require_active_user)):
        enabled = settings.FEATURES.get(feature_name, True)
        if not enabled:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature disabled")
        return user

    return _check
