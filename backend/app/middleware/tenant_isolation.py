"""
tenant_isolation.py — Auto-Inject Tenant Filter Middleware
Sprint 6 — Phase B: Enterprise Multi-Tenant SaaS Completion

FastAPI middleware that automatically injects organization_id
into request state for tenant isolation enforcement.

No frozen modules are modified.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.db.models.all_models import User
from app.core.security import decode_access_token
from app.services.config_center import config_center

logger = logging.getLogger(__name__)


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts the tenant context from the authenticated
    user and injects it into the request state.

    This allows downstream services and queries to automatically
    filter by organization_id without explicit parameter passing.
    """

    # Paths that are tenant-scoped
    TENANT_SCOPED_PATHS = [
        "/api/v1/attendance",
        "/api/v1/leave",
        "/api/v1/payroll",
        "/api/v1/performance",
        "/api/v1/policy",
        "/api/v1/assets",
        "/api/v1/users",
        "/api/v1/hr",
        "/api/v1/org",
        "/api/v1/rbac",
        "/api/v1/subscription",
        "/api/v1/scope",
        "/api/v1/workflow",
        "/api/v1/dynamic-roles",
        "/api/v1/eaac",
        "/api/v1/learning",
        "/api/v1/succession",
        "/api/v1/ticketing",
        "/api/v1/reimbursement",
        "/api/v1/reports",
        "/api/v1/analytics",
        "/api/v1/notifications",
        "/api/v1/audit",
        "/api/v1/operations",
        "/api/v1/enterprise",
        "/api/v1/tenant",
        "/api/v1/billing",
    ]

    # Paths that are public (no tenant context)
    PUBLIC_PATHS = [
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/onboarding",
        "/api/v1/public",
    ]

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Initialize tenant context
        request.state.tenant_id = None
        request.state.user_id = None
        request.state.is_tenant_scoped = False

        # Check if path is tenant-scoped
        path = request.url.path
        is_tenant_scoped = any(
            path.startswith(scoped_path)
            for scoped_path in self.TENANT_SCOPED_PATHS
        )
        is_public = any(
            path.startswith(public_path)
            for public_path in self.PUBLIC_PATHS
        )

        if is_tenant_scoped and not is_public:
            request.state.is_tenant_scoped = True

            # Try to extract tenant from JWT token
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                try:
                    # Decode token to get user info
                    from jose import jwt
                    from app.core.config import settings
                    payload = jwt.decode(
                        token, settings.SECRET_KEY,
                        algorithms=[settings.ALGORITHM]
                    )
                    user_id = payload.get("sub")
                    if user_id:
                        request.state.user_id = int(user_id)

                        # Get tenant from user (lazy load)
                        from app.db.database import SessionLocal
                        db = SessionLocal()
                        try:
                            user = db.query(User).filter(
                                User.id == int(user_id)
                            ).first()
                            if user and user.org_id:
                                request.state.tenant_id = str(user.org_id)
                        except Exception as e:
                            logger.warning(
                                f"Could not resolve tenant for user {user_id}: {e}"
                            )
                        finally:
                            db.close()
                except Exception as e:
                    logger.debug(f"Could not decode token for tenant context: {e}")

        # Log tenant context for debugging
        if request.state.tenant_id:
            logger.debug(
                f"Tenant context: user={request.state.user_id}, "
                f"org={request.state.tenant_id}, path={path}"
            )

        # Process the request
        response = await call_next(request)

        # Add tenant context headers for frontend
        if request.state.tenant_id:
            response.headers["X-Tenant-ID"] = request.state.tenant_id

        return response


def get_current_tenant_id(request: Request) -> Optional[str]:
    """Get the current tenant ID from request state."""
    return getattr(request.state, "tenant_id", None)


def get_current_user_id(request: Request) -> Optional[int]:
    """Get the current user ID from request state."""
    return getattr(request.state, "user_id", None)


def is_tenant_scoped(request: Request) -> bool:
    """Check if the current request is tenant-scoped."""
    return getattr(request.state, "is_tenant_scoped", False)
