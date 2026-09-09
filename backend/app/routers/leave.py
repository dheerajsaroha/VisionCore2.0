"""
leave.py — FastAPI Router for Enterprise Leave Management
Sprint 3 — Module 1
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user, require_permission, has_permission
from app.db.models.all_models import User
from app.crud.crud_leave import (
    crud_leave_type, crud_leave_balance, crud_leave_request
)
from app.schema.leave import (
    LeaveTypeCreate, LeaveTypeUpdate, LeaveTypeResponse,
    LeaveBalanceResponse, LeaveRequestCreate, LeaveApprovalAction,
    LeaveRequestResponse, LeaveSummaryResponse
)
from app.db.seed_leave import seed_leave_types_for_org

router = APIRouter()


# ── LEAVE TYPES ──
@router.post("/types", response_model=LeaveTypeResponse, status_code=status.HTTP_201_CREATED)
def create_leave_type(
    payload: LeaveTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("leave.manage")),
):
    """Create a new leave type configuration (HR/Admin)."""
    existing = crud_leave_type.get_by_code(db, current_user.org_id, payload.code)
    if existing:
        raise HTTPException(status_code=400, detail=f"Leave type with code '{payload.code}' already exists")

    return crud_leave_type.create(db, current_user.org_id, payload.model_dump())


@router.get("/types", response_model=List[LeaveTypeResponse])
def get_leave_types(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all configured leave types for current organization."""
    seed_leave_types_for_org(db, current_user.org_id)
    return crud_leave_type.get_all_for_org(db, current_user.org_id, active_only=active_only)


@router.put("/types/{type_id}", response_model=LeaveTypeResponse)
def update_leave_type(
    type_id: int,
    payload: LeaveTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("leave.manage")),
):
    """Update leave type configuration (HR/Admin)."""
    lt = crud_leave_type.get_by_id(db, type_id)
    if not lt or lt.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Leave type not found")

    return crud_leave_type.update(db, lt, payload.model_dump(exclude_unset=True))


# ── LEAVE BALANCES ──
@router.get("/balance", response_model=List[LeaveBalanceResponse])
def get_user_leave_balances(
    user_id: Optional[int] = None,
    year: int = 2025,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get leave balances for current user or targeted user."""
    target_user_id = user_id or current_user.id
    if target_user_id != current_user.id and not (
        has_permission(db, current_user, "leave.view_team")
        or has_permission(db, current_user, "leave.view_org")
    ):
        raise HTTPException(status_code=403, detail="Cannot view leave balance of other users")

    seed_leave_types_for_org(db, current_user.org_id)
    crud_leave_balance.initialize_all_balances_for_user(db, target_user_id, current_user.org_id, year)

    balances = crud_leave_balance.get_user_balances(db, target_user_id, year)
    result = []
    for b in balances:
        b_dict = {
            "id": b.id,
            "user_id": b.user_id,
            "organization_id": b.organization_id,
            "leave_type_id": b.leave_type_id,
            "leave_type_name": b.leave_type.name if b.leave_type else None,
            "leave_type_code": b.leave_type.code if b.leave_type else None,
            "year": b.year,
            "entitled_days": b.entitled_days,
            "used_days": b.used_days,
            "pending_days": b.pending_days,
            "carried_forward_days": b.carried_forward_days,
            "adjusted_days": b.adjusted_days,
            "available_days": b.available_days,
            "updated_at": b.updated_at
        }
        result.append(b_dict)
    return result


# ── LEAVE REQUESTS ──
@router.post("/requests", response_model=LeaveRequestResponse, status_code=status.HTTP_201_CREATED)
def submit_leave_request(
    payload: LeaveRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("leave.apply")),
):
    """Submit a new leave application."""
    lt = crud_leave_type.get_by_id(db, payload.leave_type_id)
    if not lt or lt.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Invalid leave type selected")

    if not lt.is_active:
        raise HTTPException(status_code=400, detail="This leave type is currently disabled")

    if payload.total_days > lt.max_days_per_request:
        raise HTTPException(status_code=400, detail=f"Request exceeds max single request limit of {lt.max_days_per_request} days")

    bal = crud_leave_balance.get_or_create_balance(db, current_user.id, current_user.org_id, lt)
    if bal.available_days < payload.total_days:
        raise HTTPException(status_code=400, detail=f"Insufficient leave balance. Available: {bal.available_days} days, Requested: {payload.total_days} days")

    req = crud_leave_request.create_request(db, current_user.id, current_user.org_id, payload.model_dump())

    return {
        **req.__dict__,
        "user_name": current_user.full_name,
        "user_email": current_user.email,
        "leave_type_name": lt.name,
        "leave_type_code": lt.code
    }


@router.get("/requests", response_model=List[LeaveRequestResponse])
def list_leave_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    user_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List leave requests with status filtering."""
    target_user_id = user_id
    if target_user_id != current_user.id and not (
        has_permission(db, current_user, "leave.view_team")
        or has_permission(db, current_user, "leave.view_org")
    ):
        target_user_id = current_user.id

    requests = crud_leave_request.list_requests(
        db, current_user.org_id, user_id=target_user_id, status=status_filter, skip=skip, limit=limit
    )

    result = []
    for r in requests:
        r_dict = {
            **r.__dict__,
            "user_name": r.user.full_name if r.user else f"User #{r.user_id}",
            "user_email": r.user.email if r.user else None,
            "leave_type_name": r.leave_type.name if r.leave_type else None,
            "leave_type_code": r.leave_type.code if r.leave_type else None,
            "approver_name": r.approver.full_name if r.approver else None
        }
        result.append(r_dict)
    return result


@router.post("/requests/{request_id}/approve", response_model=LeaveRequestResponse)
def approve_leave_request(
    request_id: int,
    payload: LeaveApprovalAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("leave.approve")),
):
    """Approve or reject a leave request."""
    req = crud_leave_request.get_by_id(db, request_id)
    if not req or req.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Leave request not found")

    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot process request in '{req.status}' state")

    if req.user_id == current_user.id:
        raise HTTPException(status_code=403, detail="You cannot approve your own leave request")

    if req.user and current_user.role and req.user.dept_id and current_user.dept_id:
        if req.user.dept_id != current_user.dept_id:
            raise HTTPException(status_code=403, detail="You can only approve leave requests from your department")

    if payload.status == "approved":
        updated_req = crud_leave_request.approve_request(db, req, current_user.id, payload.note)
    elif payload.status == "rejected":
        updated_req = crud_leave_request.reject_request(db, req, current_user.id, payload.note)
    else:
        raise HTTPException(status_code=400, detail="Invalid status action")

    return {
        **updated_req.__dict__,
        "user_name": updated_req.user.full_name if updated_req.user else None,
        "user_email": updated_req.user.email if updated_req.user else None,
        "leave_type_name": updated_req.leave_type.name if updated_req.leave_type else None,
        "leave_type_code": updated_req.leave_type.code if updated_req.leave_type else None,
        "approver_name": current_user.full_name
    }


@router.post("/requests/{request_id}/cancel", response_model=LeaveRequestResponse)
def cancel_leave_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Cancel a leave request (by owner or admin)."""
    req = crud_leave_request.get_by_id(db, request_id)
    if not req or req.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Leave request not found")

    is_owner = req.user_id == current_user.id
    is_admin = has_permission(db, current_user, "leave.manage")

    if not is_owner and not is_admin:
        raise HTTPException(status_code=403, detail="Cannot cancel leave requests of another user")

    if req.status in ["cancelled", "rejected"]:
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}")

    updated = crud_leave_request.cancel_request(db, req)
    return {
        **updated.__dict__,
        "user_name": updated.user.full_name if updated.user else None,
        "leave_type_name": updated.leave_type.name if updated.leave_type else None,
        "leave_type_code": updated.leave_type.code if updated.leave_type else None
    }
