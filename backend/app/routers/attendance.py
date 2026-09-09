from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Request

from sqlalchemy.orm import Session
from datetime import datetime
from typing import Any, List
import base64
import logging

from app.schema.attendance import CheckInRequest, AttendanceLogResponse
from app.db.database import get_db
from app.api import deps
from app.db.models.all_models import User, AttendanceLog
from app.services.analytics import analytics_service
from app.services.cache import cache_response
from app.services.attendance_controller import attendance_controller
from app.services.blockchain import background_blockchain_anchor
from app.core.rate_limit import rate_limit_dependency



router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/wellness-heatmap")
@cache_response(expire=300)
async def get_wellness_heatmap(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("attendance.view")),
) -> Any:
    """
    STRICT MULTI-TENANCY: Uses org_id from authenticated user.
    """
    return analytics_service.get_wellness_heatmap(db, current_user.org_id)


@router.get("/productivity-report")
def get_productivity_report(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return analytics_service.get_productivity_growth(db, current_user.org_id)


@router.get("/logs", response_model=List[AttendanceLogResponse])
def get_logs(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: str = Query(None),
    date_from: datetime = Query(None),
    date_to: datetime = Query(None),
) -> Any:
    """
    Get attendance logs with pagination and optional filtering.
    """
    query = db.query(AttendanceLog).join(User).filter(
        User.org_id == current_user.org_id,
        AttendanceLog.is_deleted == 0
    )
    if status:
        query = query.filter(AttendanceLog.status == status)
    if date_from:
        query = query.filter(AttendanceLog.check_in >= date_from)
    if date_to:
        query = query.filter(AttendanceLog.check_in <= date_to)

    return query.order_by(AttendanceLog.check_in.desc()).offset(skip).limit(limit).all()


@router.post("/check-in", response_model=AttendanceLogResponse)
async def check_in(
    *,
    request: Request,
    db: Session = Depends(get_db),
    req: CheckInRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_active_user),
    _: bool = Depends(rate_limit_dependency(max_requests=10, window_seconds=60)),
) -> Any:

    """
    Refactored check-in with robust error handling and async anchoring.
    SECURE: Requires authenticated user. Users can only check in as themselves
    unless Admin/Manager.
    """
    try:
        log = attendance_controller.handle_check_in(
            db,
            req=req,
            current_user=current_user,
            background_tasks=background_tasks,
        )
        return log
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        request_id = getattr(getattr(request, "state", None), "request_id", None)
        logger.exception(f"Check-in failed [request_id={request_id}]: {e}")
        raise HTTPException(status_code=500, detail="Biometric processing failed")


@router.patch("/logs/{log_id}", response_model=AttendanceLogResponse)
def update_attendance_log(
    *,
    db: Session = Depends(get_db),
    log_id: int,
    status: str,
    current_user: User = Depends(deps.require_permission("attendance.override")),
    background_tasks: BackgroundTasks
) -> Any:

    # SECURE: Ensure the log belongs to the admin's organization
    log = db.query(AttendanceLog).join(User).filter(
        AttendanceLog.id == log_id,
        User.org_id == current_user.org_id
    ).first()

    if not log:
        raise HTTPException(status_code=404, detail="Log not found in your organization")

    log.status = status
    db.commit()
    db.refresh(log)

    payload = {"log_id": log.id, "new_status": log.status, "by": current_user.username}
    background_tasks.add_task(background_blockchain_anchor, log.id, payload, "manual_override")

    return log


# ── ATTENDANCE CORRECTION & REGULARIZATION ──
@router.post("/corrections", status_code=201)
def submit_attendance_correction(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """Submit an attendance regularization/correction request."""
    from app.db.models.all_models import AttendanceCorrection

    correction = AttendanceCorrection(
        organization_id=current_user.org_id,
        user_id=current_user.id,
        attendance_log_id=payload.get("attendance_log_id"),
        requested_clock_in=datetime.fromisoformat(payload["requested_clock_in"]) if payload.get("requested_clock_in") else None,
        requested_clock_out=datetime.fromisoformat(payload["requested_clock_out"]) if payload.get("requested_clock_out") else None,
        reason=payload["reason"],
        status="pending"
    )
    db.add(correction)
    db.commit()
    db.refresh(correction)
    return {
        "id": correction.id,
        "status": correction.status,
        "reason": correction.reason,
        "created_at": correction.created_at
    }


@router.get("/corrections")
def list_attendance_corrections(
    status: str = Query(None),
    user_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """List regularization requests for current organization."""
    from app.db.models.all_models import AttendanceCorrection

    q = db.query(AttendanceCorrection).filter(AttendanceCorrection.organization_id == current_user.org_id)
    if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "Manager"]:
        q = q.filter(AttendanceCorrection.user_id == current_user.id)
    elif user_id:
        q = q.filter(AttendanceCorrection.user_id == user_id)

    if status:
        q = q.filter(AttendanceCorrection.status == status)

    results = q.order_by(AttendanceCorrection.created_at.desc()).all()
    out = []
    for r in results:
        out.append({
            "id": r.id,
            "user_id": r.user_id,
            "user_name": r.user.full_name if r.user else f"User #{r.user_id}",
            "requested_clock_in": r.requested_clock_in,
            "requested_clock_out": r.requested_clock_out,
            "reason": r.reason,
            "status": r.status,
            "reviewer_note": r.reviewer_note,
            "created_at": r.created_at
        })
    return out


@router.post("/corrections/{correction_id}/approve")
def approve_attendance_correction(
    correction_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """Approve or reject an attendance correction request."""
    if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "Manager"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    from app.db.models.all_models import AttendanceCorrection

    corr = db.query(AttendanceCorrection).filter(
        AttendanceCorrection.id == correction_id,
        AttendanceCorrection.organization_id == current_user.org_id
    ).first()

    if not corr:
        raise HTTPException(status_code=404, detail="Correction request not found")

    status_action = payload.get("status", "approved")
    corr.status = status_action
    corr.reviewer_user_id = current_user.id
    corr.reviewer_note = payload.get("note")
    corr.reviewed_at = datetime.now()

    # If approved and log exists, update log
    if status_action == "approved" and corr.attendance_log:
        if corr.requested_clock_in:
            corr.attendance_log.check_in = corr.requested_clock_in
        if corr.requested_clock_out:
            corr.attendance_log.check_out = corr.requested_clock_out
        corr.attendance_log.status = "on_time"
        db.add(corr.attendance_log)

    db.commit()
    db.refresh(corr)
    return {"id": corr.id, "status": corr.status, "reviewed_at": corr.reviewed_at}


@router.get("/summary")
def get_attendance_summary(
    month: int = Query(datetime.now().month),
    year: int = Query(datetime.now().year),
    user_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """Get aggregated monthly attendance statistics."""
    target_user_id = user_id or current_user.id
    if target_user_id != current_user.id and current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "Manager"]:
        raise HTTPException(status_code=403, detail="Unauthorized to view summary of other users")

    logs = db.query(AttendanceLog).filter(
        AttendanceLog.user_id == target_user_id,
        AttendanceLog.is_deleted == 0
    ).all()

    filtered_logs = [l for l in logs if l.check_in and l.check_in.month == month and l.check_in.year == year]

    total_present = len([l for l in filtered_logs if l.status in ["on_time", "early"]])
    total_late = len([l for l in filtered_logs if l.status == "late"])
    total_absent = 0  # Can be calculated against working days

    return {
        "user_id": target_user_id,
        "month": month,
        "year": year,
        "total_days_logged": len(filtered_logs),
        "present_count": total_present,
        "late_count": total_late,
    }
