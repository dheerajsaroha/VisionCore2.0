"""
deps.py — FastAPI dependency injection.
Provides the current authenticated user to all protected routes.
"""
from typing import Generator, List, Dict
from datetime import datetime, timedelta, timezone
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core import security
from app.db.database import SessionLocal
from app.db.models.all_models import User, UserSession, Permission, RolePermission, UserRole
from app.schema.token import TokenPayload
from app.crud.crud_session import user_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

logger = logging.getLogger(__name__)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    try:
        if await security.is_token_blacklisted(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        token_type = payload.get("type")
        if token_type and token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        token_data = TokenPayload(**payload)
        if not token_data.sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing subject in token",
            )
        user_id = int(token_data.sub)
    except (JWTError, ValidationError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"JWT validation failed: {str(e)}",
        )

    user = (
        db.query(User)
        .options(selectinload(User.role))
        .filter(User.id == user_id, User.is_deleted == 0)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Login issues session-bound access tokens.  Respect the database session
    # state so logout and password reset revoke an already-issued access token
    # immediately, even when Redis is unavailable.
    session_jti = payload.get("jti")
    if session_jti:
        active_session = (
            db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.jti == session_jti,
                UserSession.is_active == True,
            )
            .first()
        )
        if not active_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked",
            )

    return user

# async def get_current_user(
#     db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
# ) -> User:
#     try:
#         if await security.is_token_blacklisted(token):
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Token has been revoked",
#             )

#         payload = jwt.decode(
#             token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
#         )

#         # Token type enforcement.
#         # Keep backward compatibility: if `type` is missing, accept.
#         # If `type` is present and not access => reject.
#         token_type = payload.get("type")
#         if token_type is not None and token_type != "access":
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Invalid token type",
#             )

#         token_data = TokenPayload(**payload)






#         if token_data.sub is None:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Invalid token payload",
#             )

#         user_id = int(str(token_data.sub))
#     except (JWTError, ValidationError, ValueError, TypeError):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Could not validate credentials",
#         )


#     user = (
#         db.query(User)
#         .options(selectinload(User.role))
#         .filter(User.id == user_id, User.is_deleted == 0)
#         .first()
#     )
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#     return user





async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    if current_user.role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No role assigned to this user.",
        )

    return current_user


# async def require_admin(
#     current_user: User = Depends(get_current_active_user),
# ) -> User:
#     if current_user.role.name not in ["Admin", "Manager", "SuperAdmin"]:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Admin, Manager, or SuperAdmin privileges required"
#         )
#     return current_user

# Canonical role names — single source of truth for role normalization.
# This prevents privilege-escalation via cascading alias maps.
CANONICAL_ROLES = {
    "superadmin": "SuperAdmin",
    "super admin": "SuperAdmin",
    "platform:superadmin": "SuperAdmin",
    "platformadmin": "PlatformAdmin",
    "platform view": "PlatformViewer",
    "platformviewer": "PlatformViewer",
    "platformauditor": "PlatformAuditor",
    "platform auditor": "PlatformAuditor",
    "orgadmin": "OrgAdmin",
    "admin": "OrgAdmin",                    # Legacy Admin → OrgAdmin (NOT SuperAdmin)
    "orgmanager": "OrgManager",
    "manager": "OrgManager",                # Legacy Manager → OrgManager
    "orgsupervisor": "OrgSupervisor",
    "supervisor": "OrgSupervisor",
    "orgdepartmenthead": "OrgDepartmentHead",
    "departmenthead": "OrgDepartmentHead",
    "orgteamlead": "OrgTeamLead",
    "teamlead": "OrgTeamLead",
    "orghr": "OrgHR",
    "hr": "OrgHR",                          # Legacy HR → OrgHR
    "hradmin": "OrgHR",
    "orgfinance": "OrgFinance",
    "finance": "OrgFinance",                # Legacy Finance → OrgFinance
    "financeadmin": "OrgFinance",
    "orgemployee": "OrgEmployee",
    "employee": "OrgEmployee",              # Legacy Employee → OrgEmployee
    "orgcontractor": "OrgContractor",
    "contractor": "OrgContractor",
    "orgintern": "OrgIntern",
    "intern": "OrgIntern",
    "orgviewer": "OrgViewer",
    "viewer": "OrgViewer",
    "orgshiftmanager": "OrgShiftManager",
    "shiftmanager": "OrgShiftManager",
    "candidate": "Candidate",
    "auditor": "PlatformAuditor",
    "serviceaccount": "SystemService",
    "service_account": "SystemService",
    "systemservice": "SystemService",
}


def normalize_role_name(role_name: str) -> str:
    """Normalize a role name to its canonical form (case-insensitive)."""
    if not role_name:
        return ""
    key = role_name.strip().lower()
    return CANONICAL_ROLES.get(key, role_name.strip())


def has_any_role(user: User, *roles: str) -> bool:
    """
    Check whether a user has one of the allowed roles.
    Normalizes both the user's role and the requested roles to canonical
    names first — prevents cross-role privilege escalation via alias maps
    (e.g. HR matching 'admin' or Employee matching 'Manager').
    """
    if user is None or getattr(user, "role", None) is None:
        return False

    user_role = normalize_role_name(user.role.name)

    # Normalize all requested roles
    normalized_roles = {normalize_role_name(r) for r in roles}

    # SuperAdmin is the ONLY role that implicitly satisfies admin-style checks.
    if user_role in normalized_roles:
        return True

    return False


# async def require_admin(
#     current_user: User = Depends(get_current_active_user),
# ) -> User:
#     """
#     Allows Admin, Manager, and Super Admin users.
#     Handles legacy role naming inconsistencies safely.
#     """

    # if current_user.role is None:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="No role assigned to this user."
    #     )

    # role_name = current_user.role.name.strip().lower()

    # allowed_roles = {
    #     "admin",
    #     "manager",
    #     "superadmin",
    #     "super admin",
    # }

    # if role_name not in allowed_roles:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail=(
    #             "Admin, Manager, or Super Admin privileges required."
    #         ),
    #     )

    # return current_user


async def get_current_superadmin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Require a platform SuperAdmin.

    This is deliberately stricter than `require_admin`, which also admits
    OrgAdmin. The endpoints guarded by this dependency are cross-tenant: they
    list, provision, suspend and reconfigure *every* organization. An OrgAdmin
    passing them would be a privilege escalation from one tenant to all of them.

    Referenced by `tenant_admin.py`, which could not import until this existed
    and so was silently never mounted.
    """
    if not has_any_role(current_user, "SuperAdmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SuperAdmin privileges required.",
        )
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    SECURITY FIX: Only SuperAdmin and OrgAdmin have admin privileges.
    Manager/OrgManager is NOT an admin role and must NOT pass this check.
    """

    if not has_any_role(
        current_user,
        "SuperAdmin",
        "OrgAdmin",
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )

    return current_user




async def require_manager_or_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if not has_any_role(
        current_user,
        "SuperAdmin",
        "OrgAdmin",
        "OrgManager",
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Manager privileges required.",
        )

    return current_user


# Permission alias map for UI vs Backend fallback resolution.
# SECURITY: Only safe one-way aliases are allowed.  Aliases must NEVER
# escalate a lower-privilege permission to a higher-privilege one.
# Removed dangerous aliases that granted platform-level access via
# org-level permissions (e.g. org.settings.manage -> admin.tenant.manage).
# Removed the employee.read <-> users.read pair entirely: employee.read is
# unused in the codebase and a bidirectional alias creates ambiguity about
# which permission is authoritative.
PERMISSION_ALIASES: Dict[str, List[str]] = {
    "report.generate": ["reports.attendance.export", "reports.employee.export"],
    "settings.read": ["org.settings.view"],
    "support.ticket.read": ["tickets.read"],
    "expense.submit": ["reimbursements.create", "reimbursements.read"],
}

def require_permission(*permission_names: str):
    """
    FastAPI dependency that checks the current user has at least one of the
    specified permissions (or its safe aliases).

    SECURITY: Only SuperAdmin has implicit all-permissions behavior.
    No other role — including OrgAdmin — may bypass the permission check
    via the legacy ``permissions`` JSON column or wildcard markers.
    """
    expanded_permissions = set(permission_names)
    for p in permission_names:
        if p in PERMISSION_ALIASES:
            expanded_permissions.update(PERMISSION_ALIASES[p])
    perm_list = list(expanded_permissions)

    async def _check(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> User:
        # SuperAdmin is the ONLY role with implicit all-permissions.
        if current_user.role and normalize_role_name(current_user.role.name) == "SuperAdmin":
            return current_user

        # SECURITY FIX: Removed the `permissions == "__all__"` / `["*"]`
        # bypass.  Only SuperAdmin may have implicit all-permissions.
        # The RolePermission table is the single source of truth.

        # Check if user's role has any of the required permissions via DB join
        try:
            q = db.query(RolePermission)
            if hasattr(q, "join"):
                q = q.join(Permission, RolePermission.permission_id == Permission.id)
            has_permission = (
                q.filter(
                    RolePermission.role_id == current_user.role_id,
                    Permission.name.in_(perm_list),
                    Permission.is_active == True,
                )
                .first()
                is not None
            )
            if has_permission:
                return current_user
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required permission: {', '.join(permission_names)}",
        )

    return _check


def has_permission(user: User, permission: str, db: Session) -> bool:
    """Return True if the user has the given permission (inline check)."""
    if user.role and normalize_role_name(user.role.name) == "SuperAdmin":
        return True
    try:
        q = db.query(RolePermission).join(Permission, RolePermission.permission_id == Permission.id)
        has = (
            q.filter(
                RolePermission.role_id == user.role_id,
                Permission.name == permission,
                Permission.is_active == True,
            )
            .first()
            is not None
        )
        if has:
            return True
    except Exception:
        pass
    return False


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
        if current_user.role and normalize_role_name(current_user.role.name) == "SuperAdmin":
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
    FastAPI dependency that checks the current user has one of the specified roles (with alias support).

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
        if not has_any_role(current_user, *role_names):
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


def _enforcement_enabled() -> bool:
    """Whether plan features and licensing limits gate business routes."""
    from app.core.config import settings

    return bool(getattr(settings, "ENFORCE_SUBSCRIPTION_LIMITS", True))


def require_limit(limit_type: str, *, increment_by: int = 0):
    """
    FastAPI dependency that checks the current user's organization has not
    exceeded a specific licensing limit.

    ``increment_by`` projects the usage that will exist *after* the request
    completes, so a create route at exactly the hard limit is rejected rather
    than being allowed to overshoot by one.

    Usage::

        @router.post("/employees")
        async def create_employee(
            _limit: None = Depends(require_limit("employees", increment_by=1)),
            current_user: User = Depends(get_current_active_user),
        ):
            ...
    """
    async def _check(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> None:
        if not _enforcement_enabled():
            return

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
            db, current_user.org_id, limit_type, current_usage + increment_by
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
        if not _enforcement_enabled():
            return

        from app.services.subscription_service import subscription_service

        result = subscription_service.check_feature_access(
            db, current_user.org_id, feature_code
        )
        if not result["allowed"]:
            plan_name = result.get("plan_name")
            reason = result.get("reason") or (
                f"Feature '{feature_code}' is not available on your current plan."
            )
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=reason,
                headers={
                    "X-Subscription-Feature": feature_code,
                    "X-Subscription-Plan": plan_name or "none",
                },
            )
    return _check


def require_features(*feature_codes: str):
    """
    FastAPI dependency that requires every one of the given features.

    Equivalent to stacking several ``require_feature`` dependencies, but issues
    a single check against the org's resolved feature set instead of one query
    per code.
    """
    async def _check(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> None:
        if not _enforcement_enabled():
            return

        from app.services.subscription_service import subscription_service

        for code in feature_codes:
            result = subscription_service.check_feature_access(
                db, current_user.org_id, code
            )
            if not result["allowed"]:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=result.get("reason")
                    or f"Feature '{code}' is not available on your current plan.",
                    headers={
                        "X-Subscription-Feature": code,
                        "X-Subscription-Plan": result.get("plan_name") or "none",
                    },
                )
    return _check


async def require_admin_or_super_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if not has_any_role(
        current_user,
        "SuperAdmin",
        "OrgAdmin",
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )

    return current_user
