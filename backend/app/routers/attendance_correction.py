from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.db.models.all_models import AttendanceRequest, User
from app.schema.attendance_correction import (
    ApproveAttendanceCorrectionRequest,
    AttendanceApprovalResponse,
    AttendanceCorrectionListResponse,
    AttendanceCorrectionResponse,
    OverrideAttendanceCorrectionRequest,
    RejectAttendanceCorrectionRequest,
    SubmitAttendanceCorrectionRequest,
    TimelineResponse,
)
from app.services.attendance_correction_service import (
    CrossTenantAccessError,
    DuplicatePendingRequestError,
    InvalidWorkflowTransitionError,
    RequestNotFoundError,
    ValidationError,
    attendance_correction_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _handle_service_exception(exc: Exception) -> None:
    """Map internal domain exceptions to the correct HTTP status codes."""
    if isinstance(exc, DuplicatePendingRequestError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, RequestNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, CrossTenantAccessError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, InvalidWorkflowTransitionError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, HTTPException):
        raise exc
    logger.exception("Unhandled error in attendance correction router: %s", exc)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal service error",
    )


def _verify_ownership_or_manager(req: AttendanceRequest, current_user: User) -> None:
    """Ensure caller owns the request or holds a manager/admin role."""
    if str(req.org_id) != str(current_user.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to resource in a different organization",
        )

    if req.employee_user_id == current_user.id:
        return

    if current_user.role:
        role_name = current_user.role.name.strip().lower()
        if role_name in {"admin", "manager", "superadmin", "super admin"}:
            return

        role_perms = current_user.role.permissions or []
        if "attendance_correction:approve" in role_perms:
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied to this request",
    )


def _extract_request_meta(request: Request) -> tuple[str | None, str | None, str | None]:
    """Extract ip_address, user_agent, and correlation_id from an HTTP request."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    correlation_id = request.headers.get("x-correlation-id") or getattr(
        getattr(request, "state", None), "request_id", None
    )
    return ip_address, user_agent, correlation_id


# ---------------------------------------------------------------------------
# Static-path routes MUST come before /{request_id} parameterised routes.
# FastAPI registers routes in declaration order; if /{request_id} comes first,
# the router matches the literal string "pending"/"my" as an integer parameter
# and raises a 422 before the intended handler is ever reached.
# ---------------------------------------------------------------------------


# POST /  — submit a new correction request (employee)
@router.post(
    "",
    response_model=AttendanceCorrectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Attendance Correction",
    description="Employee submits an attendance correction request.",
)
async def submit_correction(
    *,
    request: Request,
    db: Session = Depends(get_db),
    payload: SubmitAttendanceCorrectionRequest,
    current_user: User = Depends(deps.require_permission("attendance_correction:create")),
) -> Any:
    ip_address, user_agent, correlation_id = _extract_request_meta(request)
    try:
        return attendance_correction_service.submit_request(
            db,
            org_id=current_user.org_id,
            employee_user_id=current_user.id,
            attendance_log_id=payload.attendance_log_id,
            request_payload=payload.request_payload,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        _handle_service_exception(exc)


# GET /my  — list own requests (employee) — STATIC path, must precede /{request_id}
@router.get(
    "/my",
    response_model=AttendanceCorrectionListResponse,
    summary="List My Requests",
    description="Returns all correction requests submitted by the authenticated employee.",
)
async def get_my_requests(
    *,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.require_permission("attendance_correction:view_own")),
) -> Any:
    try:
        items = attendance_correction_service.list_employee_requests(
            db,
            org_id=current_user.org_id,
            employee_user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
        return {"requests": items, "total": len(items)}
    except Exception as exc:
        _handle_service_exception(exc)


# GET /pending  — list all pending requests (manager/admin) — STATIC path, must precede /{request_id}
@router.get(
    "/pending",
    response_model=AttendanceCorrectionListResponse,
    summary="List Pending Requests",
    description="Manager/admin view of all pending correction requests within their tenant.",
)
async def get_pending_requests(
    *,
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(deps.require_permission("attendance_correction:approve")),
) -> Any:
    try:
        items = attendance_correction_service.list_pending_requests(
            db,
            org_id=current_user.org_id,
            limit=limit,
            offset=offset,
        )
        return {"requests": items, "total": len(items)}
    except Exception as exc:
        _handle_service_exception(exc)


# ---------------------------------------------------------------------------
# Parameterised routes — /{request_id} and sub-paths
# ---------------------------------------------------------------------------


# GET /{request_id}
@router.get(
    "/{request_id}",
    response_model=AttendanceCorrectionResponse,
    summary="Get Single Request",
    description="Fetch a correction request by ID. Employees see only their own; managers see all.",
)
async def get_single_request(
    *,
    db: Session = Depends(get_db),
    request_id: int,
    current_user: User = Depends(deps.require_permission("attendance_correction:view_own")),
) -> Any:
    try:
        req = attendance_correction_service.get_request(
            db,
            org_id=current_user.org_id,
            request_id=request_id,
        )
        _verify_ownership_or_manager(req, current_user)
        return req
    except Exception as exc:
        _handle_service_exception(exc)


# DELETE /{request_id}  — employee self-cancellation
@router.delete(
    "/{request_id}",
    response_model=AttendanceCorrectionResponse,
    summary="Cancel Request",
    description="Employee cancels their own pending correction request.",
)
async def cancel_correction_request(
    *,
    request: Request,
    db: Session = Depends(get_db),
    request_id: int,
    current_user: User = Depends(deps.require_permission("attendance_correction:create")),
) -> Any:
    ip_address, user_agent, correlation_id = _extract_request_meta(request)
    try:
        req = attendance_correction_service.get_request(
            db,
            org_id=current_user.org_id,
            request_id=request_id,
        )
        if req.employee_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only cancel your own requests.",
            )
        return attendance_correction_service.cancel_request(
            db,
            org_id=current_user.org_id,
            request_id=request_id,
            actor_user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        _handle_service_exception(exc)


# POST /{request_id}/approve
@router.post(
    "/{request_id}/approve",
    response_model=AttendanceApprovalResponse,
    summary="Approve Request",
    description="Manager approves a pending correction request.",
)
async def approve_correction_request(
    *,
    request: Request,
    db: Session = Depends(get_db),
    request_id: int,
    payload: ApproveAttendanceCorrectionRequest,
    current_user: User = Depends(deps.require_permission("attendance_correction:approve")),
) -> Any:
    ip_address, user_agent, correlation_id = _extract_request_meta(request)
    try:
        return attendance_correction_service.approve_request(
            db,
            org_id=current_user.org_id,
            request_id=request_id,
            approver_user_id=current_user.id,
            notes=payload.decision_notes,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        _handle_service_exception(exc)


# POST /{request_id}/reject
@router.post(
    "/{request_id}/reject",
    response_model=AttendanceApprovalResponse,
    summary="Reject Request",
    description="Manager rejects a pending correction request.",
)
async def reject_correction_request(
    *,
    request: Request,
    db: Session = Depends(get_db),
    request_id: int,
    payload: RejectAttendanceCorrectionRequest,
    current_user: User = Depends(deps.require_permission("attendance_correction:reject")),
) -> Any:
    ip_address, user_agent, correlation_id = _extract_request_meta(request)
    try:
        return attendance_correction_service.reject_request(
            db,
            org_id=current_user.org_id,
            request_id=request_id,
            approver_user_id=current_user.id,
            notes=payload.decision_notes,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        _handle_service_exception(exc)


# POST /{request_id}/override
@router.post(
    "/{request_id}/override",
    response_model=AttendanceApprovalResponse,
    summary="Override Request",
    description="Admin overrides an already-decided correction request.",
)
async def override_correction_request(
    *,
    request: Request,
    db: Session = Depends(get_db),
    request_id: int,
    payload: OverrideAttendanceCorrectionRequest,
    current_user: User = Depends(deps.require_permission("attendance_correction:override")),
) -> Any:
    ip_address, user_agent, correlation_id = _extract_request_meta(request)
    try:
        return attendance_correction_service.override_request(
            db,
            org_id=current_user.org_id,
            request_id=request_id,
            approver_user_id=current_user.id,
            override_reason=payload.override_reason,
            notes=payload.decision_notes,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        _handle_service_exception(exc)


# GET /{request_id}/timeline
@router.get(
    "/{request_id}/timeline",
    response_model=TimelineResponse,
    summary="Get Request Timeline",
    description="Full audit timeline of state transitions for a correction request.",
)
async def get_request_timeline(
    *,
    db: Session = Depends(get_db),
    request_id: int,
    current_user: User = Depends(deps.require_permission("attendance_correction:view_own")),
) -> Any:
    try:
        req = attendance_correction_service.get_request(
            db,
            org_id=current_user.org_id,
            request_id=request_id,
        )
        _verify_ownership_or_manager(req, current_user)
        timeline = attendance_correction_service.get_request_timeline(
            db,
            org_id=current_user.org_id,
            request_id=request_id,
        )
        return {
            "timeline": [
                {
                    "kind": item.kind,
                    "status": item.status,
                    "occurred_at": item.occurred_at,
                    "actor_user_id": item.actor_user_id,
                    "actor_role_name": item.actor_role_name,
                    "notes": item.notes,
                }
                for item in timeline
            ]
        }
    except Exception as exc:
        _handle_service_exception(exc)
