"""
leave.py — FastAPI Router for Enterprise Leave Management
Sprint 3 — Module 1
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import get_db, get_current_active_user, require_permission, has_permission
from app.db.models.all_models import User, Team
from app.crud.crud_leave import (
    crud_leave_type, crud_leave_balance, crud_leave_request
)
from app.schema.leave import (
    LeaveTypeCreate, LeaveTypeUpdate, LeaveTypeResponse,
    LeaveBalanceResponse, LeaveRequestCreate, LeaveApprovalAction,
    LeaveRequestResponse, LeaveSummaryResponse, LeavePolicyUpsert
)
from app.db.seed_leave import seed_leave_types_for_org
from app.services import leave_template_service, leave_policy_service

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(deps.require_feature("leave_management"))])


# ── LEAVE TEMPLATES ──
@router.get("/templates")
def list_leave_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Catalogue of starting leave-type sets an organization can adopt.

    Read by any signed-in user so the "no leave types yet" state can offer a
    starting point; applying one is an admin action.
    """
    templates = leave_template_service.list_templates(db)
    current_codes = {
        lt.code for lt in crud_leave_type.get_all_for_org(db, current_user.org_id, active_only=False)
    }
    return [
        {
            "code": t.code,
            "name": t.name,
            "description": t.description,
            "region": t.region,
            "is_default": t.is_default,
            "item_count": len(t.items),
            "already_configured": any(i.code in current_codes for i in t.items),
            "items": [
                {
                    "code": i.code,
                    "name": i.name,
                    "description": i.description,
                    "max_days_per_year": i.max_days_per_year,
                    "max_days_per_request": i.max_days_per_request,
                    "carry_forward": i.carry_forward,
                    "max_carry_forward_days": i.max_carry_forward_days,
                    "requires_document": i.requires_document,
                    "min_notice_days": i.min_notice_days,
                    "is_paid": i.is_paid,
                    "gender_specific": i.gender_specific,
                }
                for i in t.items
            ],
        }
        for t in templates
    ]


@router.post("/templates/{code}/apply")
def apply_leave_template(
    code: str,
    replace: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("leave.manage")),
):
    """Adopt a template's leave types for the organization (HR/Admin).

    Additive by default: existing types are matched on code and left alone, and
    nothing is deleted. `replace=true` re-aligns existing types to the template
    and deactivates types the template does not contain, for moving a tenant onto
    a different region's rules.
    """
    try:
        return leave_template_service.apply_template(db, current_user.org_id, code, replace=replace)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── LEAVE POLICY ──
@router.get("/policy")
def get_leave_policy(
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """The organization's effective leave policy, including defaults."""
    policy = leave_policy_service.get_policy(db, current_user.org_id, year)
    policy["available_accrual_types"] = list(leave_policy_service.ACCRUAL_TYPES)
    return policy


@router.put("/policy")
def update_leave_policy(
    payload: LeavePolicyUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("leave.manage")),
):
    """Set the organization's leave policy for a year (HR/Admin)."""
    try:
        return leave_policy_service.save_policy(
            db,
            current_user.org_id,
            year=payload.year,
            name=payload.name,
            accrual_type=payload.accrual_type,
            allow_negative_balance=payload.allow_negative_balance,
            auto_approve_after_days=payload.auto_approve_after_days,
            policy_config=payload.policy_config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


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
    """List the leave types configured for the current organization.

    No longer seeds a default set: which leave types an organization offers
    depends on its sector and region, so the list starts empty until an admin
    picks a template or creates types. Tenants provisioned before this change
    keep whatever they already have.
    """
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
    year: Optional[int] = Query(default=None, description="Leave ledger year; defaults to the current year"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get leave balances for current user or targeted user."""
    target_user_id = user_id or current_user.id
    if target_user_id != current_user.id:
        if not (
            has_permission(current_user, "leave.view_team", db)
            or has_permission(current_user, "leave.view_org", db)
        ):
            raise HTTPException(status_code=403, detail="Cannot view leave balance of other users")
        # STRICT MULTI-TENANCY: Target user must exist in caller's organization
        target_user = db.query(User).filter(
            User.id == target_user_id,
            User.org_id == current_user.org_id,
            User.is_deleted == 0,
        ).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="Identity not found")

    # Balances are derived from the organization's own leave types, so no default
    # set is injected here. An organization with no types configured has no
    # balances, which is the correct reading of "we have not decided yet".
    crud_leave_balance.initialize_all_balances_for_user(db, target_user_id, current_user.org_id, year)

    balances = crud_leave_balance.get_user_balances(
        db, target_user_id, year, current_user.org_id
    )
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
def _compute_leave_days(
    start_date: datetime, end_date: datetime, org_id, is_half_day: bool
) -> float:
    """
    Working days between two dates, excluding weekends and company holidays.

    A half-day request always resolves to 0.5 regardless of the range, since a
    half-day leave is by definition one half of one working day.
    """
    if is_half_day:
        return 0.5

    start = start_date.date() if isinstance(start_date, datetime) else start_date
    end = end_date.date() if isinstance(end_date, datetime) else end_date
    if end < start:
        return 0.0

    try:
        from app.services.business_calendar_service import business_calendar_service

        return float(
            business_calendar_service.count_working_days(start, end, str(org_id))
        )
    except Exception:
        # Never fail a leave application because the calendar service is
        # unavailable; fall back to weekdays.
        return float(sum(1 for i in range((end - start).days + 1)
                         if (start + timedelta(days=i)).weekday() < 5))


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

    # Derive the day count server-side. Trusting a client-supplied figure would
    # let an employee request 365 days, and the half-day flag has to halve the
    # count — which no code path did before.
    total_days = payload.total_days
    if total_days is None or payload.is_half_day:
        total_days = _compute_leave_days(
            payload.start_date, payload.end_date, current_user.org_id, payload.is_half_day
        )

    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="End date cannot be before start date")

    if total_days <= 0:
        raise HTTPException(
            status_code=400,
            detail="The selected dates contain no working days",
        )

    # Caps and balance are evaluated against the organization's policy rather
    # than hardcoded here, because what an organization permits depends on its
    # own rules: whether a negative balance is allowed, whether a request may
    # exceed the per-request cap, and whether short requests auto-approve.
    bal = crud_leave_balance.get_or_create_balance(db, current_user.id, current_user.org_id, lt)
    verdict = leave_policy_service.evaluate_request(
        db,
        current_user.org_id,
        current_user.id,
        lt,
        total_days,
        bal.available_days,
    )
    if not verdict["allowed"]:
        raise HTTPException(status_code=400, detail="; ".join(verdict["reasons"]))

    req = crud_leave_request.create_request(
        db, current_user.id, current_user.org_id, {**payload.model_dump(), "total_days": total_days}
    )

    # A short request under the organization's auto-approve threshold is granted
    # immediately rather than queued for an approver.
    if verdict["auto_approve"]:
        try:
            req = crud_leave_request.approve_request(db, req, current_user.id, note="Auto-approved by policy")
        except Exception:
            logger.exception("Leave %s could not be auto-approved; left pending", req.id)
            db.rollback()

    # Tell the approvers. A failure here must not lose the request, so it is
    # isolated: the request is already committed by this point.
    try:
        from app.services.notification_service import notify_leave_approvers

        notify_leave_approvers(db, req, actor_id=current_user.id)
    except Exception:
        logger.exception("Leave %s created but approvers could not be notified", req.id)
        db.rollback()

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
        has_permission(current_user, "leave.view_team", db)
        or has_permission(current_user, "leave.view_org", db)
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
    """Approve or reject a leave request (department-scoped for managers, org-scoped for HR/Admin)."""
    req = crud_leave_request.get_by_id(db, request_id)
    if not req or req.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Leave request not found")

    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot process request in '{req.status}' state")

    if req.user_id == current_user.id:
        raise HTTPException(status_code=403, detail="You cannot approve your own leave request")

    # Department-scoped check for managers (OrgManager, OrgSupervisor, OrgDepartmentHead)
    if req.user and current_user.role and req.user.dept_id and current_user.dept_id:
        if req.user.dept_id != current_user.dept_id:
            # Check if user has org-wide approval permission (HR, Admin)
            is_org_approver = has_permission(current_user, "leave.view_org", db) or has_permission(current_user, "leave.manage", db)
            if not is_org_approver:
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


@router.post("/requests/{request_id}/approve-team", response_model=LeaveRequestResponse)
def approve_leave_request_team(
    request_id: int,
    payload: LeaveApprovalAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("leave.approve_team")),
):
    """Approve or reject a leave request for team members only (team-scoped for TeamLeads)."""
    req = crud_leave_request.get_by_id(db, request_id)
    if not req or req.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Leave request not found")

    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot process request in '{req.status}' state")

    if req.user_id == current_user.id:
        raise HTTPException(status_code=403, detail="You cannot approve your own leave request")

    # Team-scoped check: user must be team lead of the requester's team
    if req.user and current_user.id:
        # Check if current_user is a team lead for a team that the requester belongs to
        requester_teams = db.query(Team).filter(Team.dept_id == req.user.dept_id, Team.lead_user_id == current_user.id).all()
        if not requester_teams:
            # Also check if requester is directly in a team led by current_user
            # This assumes there's a team membership relationship or we check via dept + lead
            raise HTTPException(status_code=403, detail="You can only approve leave requests from your team members")

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
    is_admin = has_permission(current_user, "leave.manage", db)

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
