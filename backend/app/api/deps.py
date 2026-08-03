"""
deps.py — FastAPI dependency injection.
Provides the current authenticated user to all protected routes.
"""
from typing import Generator, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core import security
from app.db.database import SessionLocal
from datetime import datetime, timedelta, timezone

from app.db.models.all_models import User, RolePermission, Permission
from app.schema.token import TokenPayload
from app.crud.crud_session import user_session


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:

    try:
        if await security.is_token_blacklisted(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError) as e:
        import logging
        logging.getLogger(__name__).warning(f"[DEBUG /users/me] jwt/validation failed type={type(e)} err={e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    if payload.get("type") != "access" or not payload.get("jti"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    jti = payload["jti"]

    session_obj = user_session.get_for_user_by_jti(db, user_id=int(token_data.sub), jti=jti)
    now = datetime.now(timezone.utc)
    if not session_obj or not session_obj.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is inactive")
    if session_obj.expires_at and session_obj.expires_at <= now:
        user_session.revoke_by_session(
            db, user_id=int(token_data.sub), jti=jti, reason="session_expired")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has expired")
    if session_obj.last_activity_at <= now - timedelta(minutes=settings.SESSION_IDLE_TIMEOUT_MINUTES):
        user_session.revoke_by_session(
            db, user_id=int(token_data.sub), jti=jti, reason="idle_timeout")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has expired due to inactivity")

    user = db.query(User).options(selectinload(User.role)).filter(
        User.id == token_data.sub, User.is_deleted == 0
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_session.update_last_activity(db, session_obj=session_obj, now=now)
    return user





async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Account is inactive")
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.role.name not in ["Admin", "Manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Manager privileges required"
        )
    return current_user


async def require_manager_or_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Reusable dependency for routes restricted to Admin or Manager roles."""
    if current_user.role.name not in ["Admin", "Manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden"
        )
    return current_user


# =============================================================================
#  Permission-based Authorization (RBAC)
# =============================================================================

def require_permission(*permission_names: str):
    """
    FastAPI dependency that checks the current user has at least one of the
    specified permissions.

    Usage::

        @router.get("/users")
        async def list_users(
            current_user: User = Depends(require_permission("users.read", "users.manage")),
        ):
            ...

    Permission resolution order:
    1. SuperAdmin role has ALL permissions (short-circuit).
    2. Check the user's role via the RolePermission join table.
    """
    async def _check(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> User:
        # SuperAdmin has all permissions
        if current_user.role.name == "SuperAdmin":
            return current_user

        # Check if user's role has any of the required permissions
        has_permission = (
            db.query(RolePermission)
            .join(Permission, RolePermission.permission_id == Permission.id)
            .filter(
                RolePermission.role_id == current_user.role_id,
                Permission.name.in_(permission_names),
                Permission.is_active == True,
            )
            .first()
            is not None
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {', '.join(permission_names)}",
            )
        return current_user

    return _check


def require_all_permissions(*permission_names: str):
    """
    FastAPI dependency that checks the current user has ALL specified permissions.

    Usage::

        @router.post("/payroll/generate")
        async def generate_payroll(
            current_user: User = Depends(require_all_permissions("payroll.generate", "payroll.approve")),
        ):
            ...
    """
    async def _check(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> User:
        # SuperAdmin has all permissions
        if current_user.role.name == "SuperAdmin":
            return current_user

        # Check if user's role has ALL required permissions
        missing = []
        for perm_name in permission_names:
            has = (
                db.query(RolePermission)
                .join(Permission, RolePermission.permission_id == Permission.id)
                .filter(
                    RolePermission.role_id == current_user.role_id,
                    Permission.name == perm_name,
                    Permission.is_active == True,
                )
                .first()
                is not None
            )
            if not has:
                missing.append(perm_name)

        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {', '.join(missing)}",
            )
        return current_user

    return _check


def require_role(*role_names: str):
    """
    FastAPI dependency that checks the current user has one of the specified roles.

    Usage::

        @router.get("/admin/dashboard")
        async def admin_dashboard(
            current_user: User = Depends(require_role("SuperAdmin", "OrgAdmin")),
        ):
            ...
    """
    async def _check(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.role.name not in role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of these roles: {', '.join(role_names)}",
            )
        return current_user

    return _check


# =============================================================================
#  Subscription & Feature-based Authorization (Sprint 2, Entity 2)
# =============================================================================

def require_active_subscription():
    """
    FastAPI dependency that checks the current user's organization has
    an active subscription.

    Usage::

        @router.get("/payroll")
        async def get_payroll(
            _sub: None = Depends(require_active_subscription()),
            current_user: User = Depends(get_current_active_user),
        ):
            ...
    """
    async def _check(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> None:
        from app.crud.crud_subscription import org_subscription_crud

        sub = org_subscription_crud.get_active_by_org(db, current_user.org_id)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="No active subscription. Please subscribe to a plan.",
            )
    return _check


def require_subscription():
    """
    Alias for require_active_subscription - FastAPI dependency that checks
    the current user's organization has an active subscription.

    Usage::

        @router.get("/protected")
        async def protected_route(
            _sub: None = Depends(require_subscription()),
            current_user: User = Depends(get_current_active_user),
        ):
            ...
    """
    return require_active_subscription()


def require_plan(*plan_codes: str):
    """
    FastAPI dependency that checks the current user's organization has
    a subscription to one of the specified plan codes.

    Usage::

        @router.post("/ai/analytics")
        async def ai_analytics(
            _plan: None = Depends(require_plan("enterprise")),
            current_user: User = Depends(get_current_active_user),
        ):
            ...
    """
    async def _check(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> None:
        from app.crud.crud_subscription import org_subscription_crud, subscription_plan_crud

        sub = org_subscription_crud.get_active_by_org(db, current_user.org_id)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="No active subscription.",
            )

        plan = subscription_plan_crud.get(db, id=sub.subscription_plan_id)
        if not plan or plan.code not in plan_codes:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Requires one of these plans: {', '.join(plan_codes)}",
            )
    return _check


def require_trial():
    """
    FastAPI dependency that checks the current user's organization is
    currently in trial period.

    Usage::

        @router.get("/trial-info")
        async def trial_info(
            _trial: None = Depends(require_trial()),
            current_user: User = Depends(get_current_active_user),
        ):
            ...
    """
    async def _check(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> None:
        from app.crud.crud_subscription import org_subscription_crud

        sub = org_subscription_crud.get_by_org(db, current_user.org_id)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="No subscription found.",
            )
        if sub.status != "trialing":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Organization is not in trial period.",
            )
        if sub.trial_end and sub.trial_end < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Trial period has expired.",
            )
    return _check


def require_limit(limit_type: str):
    """
    FastAPI dependency that checks the current user's organization has not
    exceeded a specific licensing limit.

    Usage::

        @router.post("/employees")
        async def create_employee(
            _limit: None = Depends(require_limit("employees")),
            current_user: User = Depends(get_current_active_user),
        ):
            ...
    """
    async def _check(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> None:
        from app.services.subscription_service import subscription_service
        from app.db.models.all_models import User

        # Count current usage
        if limit_type == "employees":
            current_usage = db.query(User).filter(
                User.org_id == current_user.org_id,
                User.is_deleted == 0,
            ).count()
        else:
            current_usage = 0

        result = subscription_service.check_licensing_limit(
            db, current_user.org_id, limit_type, current_usage
        )
        if not result["allowed"]:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=result.get("warning", f"Licensing limit exceeded for '{limit_type}'."),
            )
    return _check


def require_feature(feature_code: str):
    """
    FastAPI dependency that checks the current user's organization has
    access to a specific feature (via subscription plan + optional flag override).

    Usage::

        @router.get("/payroll")
        async def get_payroll(
            _feature: None = Depends(require_feature("payroll")),
            current_user: User = Depends(get_current_active_user),
        ):
            ...
    """
    async def _check(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> None:
        from app.services.subscription_service import subscription_service

        result = subscription_service.check_feature_access(
            db, current_user.org_id, feature_code
        )
        if not result["allowed"]:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=result.get("reason", f"Feature '{feature_code}' is not available on your current plan."),
            )
    return _check
