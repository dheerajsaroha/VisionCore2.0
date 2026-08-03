"""
tenant_context.py — VisionCore 3.0 Unified Tenant Context & Isolation Provider

Exposes thread-local and request-contextual tenant scoping for SQLAlchemy queries
and FastAPI dependencies across all 12 Platform Domains.
"""

import logging
from typing import Optional, Generator
from contextvars import ContextVar

from fastapi import Request, Depends, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.middleware.tenant_isolation import TenantIsolationMiddleware, get_current_tenant_id

logger = logging.getLogger("visioncore.tenant_context")

# ContextVar for thread-safe async tenant context propagation
_tenant_context_var: ContextVar[Optional[str]] = ContextVar("current_tenant_id", default=None)
_user_context_var: ContextVar[Optional[int]] = ContextVar("current_user_id", default=None)


def set_current_tenant_context(tenant_id: Optional[str], user_id: Optional[int] = None):
    """Sets current tenant and user context for the active async execution context."""
    _tenant_context_var.set(tenant_id)
    _user_context_var.set(user_id)


def get_current_tenant_context() -> Optional[str]:
    """Retrieves current tenant ID from async context or None."""
    return _tenant_context_var.get()


def get_current_user_context() -> Optional[int]:
    """Retrieves current user ID from async context or None."""
    return _user_context_var.get()


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Unified Tenant Context Middleware for VisionCore 3.0.
    Integrates JWT claim resolution, X-Tenant-ID / X-Organization-ID headers,
    and sets thread-safe ContextVar for downstream DB queries.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # 1. Resolve header fallback
        explicit_tenant = request.headers.get("X-Tenant-ID") or request.headers.get("X-Organization-ID")
        
        # 2. Extract tenant context via base tenant isolation logic
        state_tenant = getattr(request.state, "tenant_id", None)
        effective_tenant = state_tenant or explicit_tenant
        user_id = getattr(request.state, "user_id", None)

        if effective_tenant:
            request.state.tenant_id = effective_tenant
            set_current_tenant_context(effective_tenant, user_id)
            logger.debug(f"TenantContext active: tenant_id={effective_tenant}, user_id={user_id}")
        else:
            set_current_tenant_context(None, None)

        try:
            response = await call_next(request)
            if effective_tenant:
                response.headers["X-Tenant-ID"] = str(effective_tenant)
            return response
        finally:
            set_current_tenant_context(None, None)


def require_tenant_context(request: Request) -> str:
    """
    FastAPI dependency that enforces the presence of a valid tenant_id context.
    Raises HTTP 403 Forbidden if no tenant context is set.
    """
    tenant_id = get_current_tenant_id(request) or get_current_tenant_context()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context required for this enterprise operation"
        )
    return str(tenant_id)
