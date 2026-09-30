"""
copilot_router.py — Enterprise AI Copilot REST API
Sprint 8 — Enterprise AI Copilot Expansion

Endpoints:
  POST /api/v1/copilot/chat         — Submit a natural language query
  GET  /api/v1/copilot/capabilities — List available copilot tools
  GET  /api/v1/copilot/history      — Retrieve conversation history (in-memory)

Security:
  - Requires authenticated user (JWT)
  - Tenant context from current_user.org_id
  - RBAC permissions resolved before tool execution
  - No parallel authentication mechanism
  - All queries audited
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models.all_models import User, RolePermission, Permission
from app.services.ai.copilot_orchestrator import copilot_orchestrator
from app.services.ai.copilot_tools import list_tools

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(deps.require_feature("ai_chat"))])


# ── Schemas ───────────────────────────────────────────────────────────────────

class CopilotChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="Natural language question")
    conversation_id: Optional[str] = Field(None, description="Optional conversation thread ID")
    tool_kwargs: Optional[dict[str, Any]] = Field(None, description="Optional extra tool parameters")


class CopilotChatResponse(BaseModel):
    success: bool
    answer: str
    intent: Optional[str] = None
    tool: Optional[str] = None
    data: list[Any] = []
    summary: str = ""
    suggestions: list[str] = []
    actions: list[dict] = []
    correlation_id: str
    timestamp: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_user_permissions(db: Session, user: User) -> list[str]:
    """Resolve permission names for the current user from RBAC tables."""
    if user.role and user.role.name in ("SuperAdmin", "Super Admin"):
        return ["*"]  # Wildcard — all permissions granted
    try:
        rows = (
            db.query(Permission.name)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .filter(
                RolePermission.role_id == user.role_id,
                Permission.is_active == True,
            )
            .all()
        )
        return [r.name for r in rows]
    except Exception:
        return []


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=CopilotChatResponse,
    summary="Submit a natural language query to the AI Copilot",
    tags=["copilot"],
)
async def copilot_chat(
    body: CopilotChatRequest,
    request: Request,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
):
    """
    Process a natural language query through the permission-aware Copilot.

    The copilot:
    - Classifies intent
    - Validates permissions BEFORE data access
    - Executes controlled tools only
    - Returns structured response with suggested follow-ups
    """
    correlation_id = f"cop-{uuid.uuid4().hex[:12]}"
    org_id = current_user.org_id

    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No organization context found.",
        )

    # Resolve permissions from RBAC
    user_permissions = _resolve_user_permissions(db, current_user)
    user_role = current_user.role.name if current_user.role else ""

    result = copilot_orchestrator.process(
        db=db,
        query=body.query,
        org_id=org_id,
        actor_user_id=current_user.id,
        user_permissions=user_permissions,
        user_role=user_role,
        correlation_id=correlation_id,
        tool_kwargs=body.tool_kwargs or {},
    )
    return CopilotChatResponse(**result)


@router.get(
    "/capabilities",
    summary="List available AI Copilot tools and their required permissions",
    tags=["copilot"],
)
async def copilot_capabilities(
    current_user: User = Depends(deps.get_current_active_user),
):
    """Return the list of available copilot tools and their permission requirements."""
    tools = list_tools()
    return {
        "tools": tools,
        "total": len(tools),
    }
