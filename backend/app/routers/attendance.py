from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Request, Body

from sqlalchemy.orm import Session
from datetime import datetime
from typing import Any, List, Optional
import base64
import logging

from app.schema.attendance import CheckInRequest, AttendanceLogResponse, CheckOutRequest
from app.db.database import get_db
from app.api import deps
from app.db.models.all_models import User, AttendanceLog
from app.services.analytics import analytics_service
from app.services.cache import cache_response
from app.services.attendance_controller import attendance_controller
from app.services.blockchain import background_blockchain_anchor
from app.services.attendance_pipeline.pipeline import LivenessFailedError
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

    logs = query.order_by(AttendanceLog.check_in.desc()).offset(skip).limit(limit).all()
    results = []
    for log in logs:
        item = AttendanceLogResponse.model_validate(log)
        if log.user:
            item.user_name = log.user.full_name
            item.user_email = log.user.email
        else:
            item.user_name = f"User #{log.user_id}"
        results.append(item)
    return results



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
    except LivenessFailedError as e:
        raise HTTPException(
            status_code=403,
            detail={
                "code": getattr(e, "code", "LIVENESS_FAILED"),
                "message": str(e),
                "score": getattr(e, "score", 0.0),
            },
        )
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


@router.post("/check-out", response_model=AttendanceLogResponse)
async def check_out(
    *,
    request: Request,
    db: Session = Depends(get_db),
    req: Optional[CheckOutRequest] = Body(None),
    current_user: User = Depends(deps.get_current_active_user),
    _: bool = Depends(rate_limit_dependency(max_requests=10, window_seconds=60)),
) -> Any:
    """
    First-class check-out endpoint.
    SECURE: Requires authenticated user. Optionally re-verifies identity via face recognition.
    Enforces that an active check-in exists and prevents duplicate check-outs.
    """
    from app.crud.crud_attendance import attendance as crud_attendance

    user_id = req.user_id if req and req.user_id else current_user.id
    timestamp = req.timestamp if req else None

    if req and req.image_base64:
        image_bytes = attendance_controller.extract_image_bytes(req.image_base64)
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Invalid image for check-out verification")

        try:
            pipeline_result = attendance_controller.run_face_pipeline(
                db,
                image_bytes=image_bytes,
                existing_user_id=current_user.id,
                org_id=current_user.org_id,
            )
            if pipeline_result.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Face verification failed for check-out")
        except LivenessFailedError as e:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": getattr(e, "code", "LIVENESS_FAILED"),
                    "message": str(e),
                    "score": getattr(e, "score", 0.0),
                },
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            request_id = getattr(getattr(request, "state", None), "request_id", None)
            logger.exception(f"Check-out biometric failed [request_id={request_id}]: {e}")
            raise HTTPException(status_code=500, detail="Check-out verification failed")

    try:
        log = crud_attendance.log_check_out(db, user_id=user_id, timestamp=timestamp)
        res = AttendanceLogResponse.model_validate(log)
        res.user_name = current_user.full_name
        res.user_email = current_user.email
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Check-out failed for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Check-out processing failed")


@router.post("/break-start", response_model=AttendanceLogResponse)
async def break_start(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
    _: bool = Depends(rate_limit_dependency(max_requests=20, window_seconds=60)),
) -> Any:
    """Start a break for the current user's active attendance session."""
    from app.crud.crud_attendance import attendance as crud_attendance
    try:
        log = crud_attendance.log_break_start(db, user_id=current_user.id)
        res = AttendanceLogResponse.model_validate(log)
        res.user_name = current_user.full_name
        res.user_email = current_user.email
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Break start failed for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Break start processing failed")


@router.post("/break-end", response_model=AttendanceLogResponse)
async def break_end(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
    _: bool = Depends(rate_limit_dependency(max_requests=20, window_seconds=60)),
) -> Any:
    """End the current user's active break."""
    from app.crud.crud_attendance import attendance as crud_attendance
    try:
        log = crud_attendance.log_break_end(db, user_id=current_user.id)
        res = AttendanceLogResponse.model_validate(log)
        res.user_name = current_user.full_name
        res.user_email = current_user.email
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Break end failed for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Break end processing failed")


@router.patch("/logs/{log_id}", response_model=AttendanceLogResponse)
def update_attendance_log(
    *,
    db: Session = Depends(get_db),
    log_id: int,
    status: str,
    current_user: User = Depends(deps.require_permission("attendance.override")),
    background_tasks: BackgroundTasks
) -> Any:
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

    try:
        from app.routers.notifications import push_notification, push_notification_to_org_managers
        push_notification(
            str(current_user.org_id),
            current_user.id,
            title="Attendance Correction Submitted",
            message=f"Your regularization request for '{payload.get('reason', '')}' is pending review.",
            notif_type="info",
            action_url="/dashboard/workforce/leave-requests",
            source_event="attendance_correction.submitted"
        )
        push_notification_to_org_managers(
            db,
            current_user.org_id,
            title="Pending Attendance Correction",
            message=f"{current_user.full_name} submitted an attendance correction request: '{payload.get('reason', '')}'.",
            notif_type="warning",
            action_url="/dashboard/workforce/leave-requests",
            source_event="attendance_correction.manager_alert",
            exclude_user_id=current_user.id
        )
    except Exception as err:
        logger.warning(f"Failed to push notification for correction submit: {err}")

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
    role_name = current_user.role.name if current_user.role else ""
    if role_name not in ["Admin", "SuperAdmin", "OrgAdmin", "Manager", "OrgManager"]:
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
    if not deps.has_any_role(current_user, "Admin", "SuperAdmin", "OrgAdmin", "Manager", "OrgManager"):
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

    if status_action == "approved" and corr.attendance_log:
        if corr.requested_clock_in:
            corr.attendance_log.check_in = corr.requested_clock_in
        if corr.requested_clock_out:
            corr.attendance_log.check_out = corr.requested_clock_out
        corr.attendance_log.status = "on_time"
        db.add(corr.attendance_log)

    db.commit()
    db.refresh(corr)

    try:
        from app.routers.notifications import push_notification
        push_notification(
            str(corr.organization_id),
            corr.user_id,
            title=f"Attendance Correction {status_action.capitalize()}",
            message=f"Your attendance correction request was {status_action} by {current_user.full_name}.",
            notif_type="success" if status_action == "approved" else "warning",
            action_url="/dashboard/workforce/leave-requests",
            source_event="attendance_correction.reviewed"
        )
    except Exception as err:
        logger.warning(f"Failed to push notification for correction review: {err}")

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
    role_name = current_user.role.name if current_user.role else ""
    if target_user_id != current_user.id and role_name not in ["Admin", "SuperAdmin", "OrgAdmin", "Manager", "OrgManager"]:
        raise HTTPException(status_code=403, detail="Unauthorized to view summary of other users")

    logs = db.query(AttendanceLog).filter(
        AttendanceLog.user_id == target_user_id,
        AttendanceLog.is_deleted == 0
    ).all()

    filtered_logs = [l for l in logs if l.check_in and l.check_in.month == month and l.check_in.year == year]

    total_present = len([l for l in filtered_logs if l.status in ["on_time", "early"]])
    total_late = len([l for l in filtered_logs if l.status == "late"])

    return {
        "user_id": target_user_id,
        "month": month,
        "year": year,
        "total_days_logged": len(filtered_logs),
        "present_count": total_present,
        "late_count": total_late,
        "attendance_rate_pct": round((total_present / max(1, len(filtered_logs))) * 100, 1)
    }
