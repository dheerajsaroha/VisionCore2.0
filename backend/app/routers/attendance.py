from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Request, Body

from sqlalchemy.orm import Session
from datetime import datetime
from typing import Any, List, Optional
import base64
import logging
import json

from pydantic import BaseModel, Field
from app.schema.attendance import CheckInRequest, AttendanceLogResponse, CheckOutRequest
from app.db.database import get_db
from app.api import deps
from app.db.models.all_models import User, AttendanceLog
from app.services.analytics import analytics_service
from app.services.cache import cache_response
from app.services.attendance_controller import attendance_controller
from app.services.attendance_pipeline.pipeline import LivenessUnavailableError
from app.services.blockchain import background_blockchain_anchor
from app.core.rate_limit import rate_limit_dependency



router = APIRouter(dependencies=[Depends(deps.require_feature("attendance"))])
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
    current_user: User = Depends(deps.require_permission("attendance.history")),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: str = Query(None),
    date_from: datetime = Query(None),
    date_to: datetime = Query(None),
    user_id: Optional[int] = Query(None),
) -> Any:
    """
    Get attendance logs with pagination and optional filtering.
    """
    # Attendance history is personal data. A caller may always request their
    # own history; organization-wide history is reserved for the existing
    # attendance.override capability. Tenant filtering alone is not sufficient
    # because it would still expose colleagues' records to an ordinary user.
    can_view_organization = deps.has_permission(current_user, "attendance.override", db)
    target_user_id = user_id
    if target_user_id is not None and target_user_id != current_user.id and not can_view_organization:
        raise HTTPException(status_code=403, detail="Unauthorized to view another user's attendance history")
    if target_user_id is None and not can_view_organization:
        target_user_id = current_user.id

    query = db.query(AttendanceLog).join(User).filter(
        User.org_id == current_user.org_id,
        AttendanceLog.is_deleted == 0
    )
    if target_user_id is not None:
        query = query.filter(AttendanceLog.user_id == target_user_id)
    if status:
        query = query.filter(AttendanceLog.status == status)
    if date_from:
        query = query.filter(AttendanceLog.check_in >= date_from)
    if date_to:
        query = query.filter(AttendanceLog.check_in <= date_to)

    return query.order_by(AttendanceLog.check_in.desc()).offset(skip).limit(limit).all()


class SyncLogEntry(BaseModel):
    """One queued punch replayed by an edge device.

    `user_id` is accepted only so the caller can correlate its own queue. It is
    never used to establish identity: `handle_check_in` clears it and resolves
    the person from the biometric sample, exactly as for a live check-in.
    """
    user_id: Optional[int] = None
    image_base64: Optional[str] = Field(None, max_length=5000000)
    timestamp: Optional[datetime] = None
    face_embedding: Optional[List[float]] = None
    is_live: int = 0
    emotion: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None


class SyncRequest(BaseModel):
    logs: List[SyncLogEntry] = Field(default_factory=list, max_length=500)


class SyncResultItem(BaseModel):
    index: int
    recorded: bool
    user_id: Optional[int] = None
    log_id: Optional[int] = None
    error: Optional[str] = None


class SyncResponse(BaseModel):
    """Per-entry outcomes, so a device drops only what actually landed.

    A boolean "did you get all of it" is unusable offline: one unreplayable
    entry would either be retried forever or silently discarded with the rest.
    """
    received: int
    recorded: int
    failed: int
    results: List[SyncResultItem] = Field(default_factory=list)


@router.post("/sync", response_model=SyncResponse, summary="Replay queued edge-device punches")
async def sync_attendance_logs(
    *,
    request: Request,
    db: Session = Depends(get_db),
    payload: SyncRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_active_user),
    _: bool = Depends(rate_limit_dependency(max_requests=10, window_seconds=60)),
) -> Any:
    """Ingest punches buffered on a device while it was offline.

    `edge_client.py` buffers failed check-ins locally and posts them here on
    reconnect, but this endpoint did not exist, so every replay 404'd and the
    queue only ever grew.

    Each entry goes through the same `handle_check_in` path as a live check-in.
    That matters: identity comes from the biometric sample and the submitted
    `user_id` is discarded, so a device cannot attribute a punch to someone else
    by editing its own queue.
    """
    if not payload.logs:
        return SyncResponse(received=0, recorded=0, failed=0, results=[])

    request_id = getattr(getattr(request, "state", None), "request_id", None)
    results: List[SyncResultItem] = []
    recorded = 0

    for index, entry in enumerate(payload.logs):
        try:
            req = CheckInRequest(
                user_id=entry.user_id,
                image_base64=entry.image_base64,
                timestamp=entry.timestamp or datetime.now(timezone.utc),
                face_embedding=entry.face_embedding,
                is_live=entry.is_live,
                emotion=entry.emotion,
                source="edge",
                gps_lat=entry.gps_lat,
                gps_lng=entry.gps_lng,
            )
            log = attendance_controller.handle_check_in(
                db,
                req=req,
                current_user=current_user,
                background_tasks=background_tasks,
            )
            recorded += 1
            results.append(
                SyncResultItem(
                    index=index, recorded=True, user_id=log.user_id, log_id=log.id
                )
            )
        except HTTPException:
            raise
        except LivenessUnavailableError as exc:
            # The anti-spoofing backend is down. Retrying the whole batch later
            # is the right response, so this is a server fault, not a bad entry.
            logger.error("Sync aborted, liveness engine unavailable [request_id=%s]: %s", request_id, exc)
            raise HTTPException(
                status_code=503,
                detail={"code": LivenessUnavailableError.code, "message": str(exc)},
            )
        except (ValueError, LookupError, PermissionError) as exc:
            # This entry cannot be replayed. Report it so the device stops
            # retrying it and keeps the rest.
            logger.info(
                "Sync entry %d rejected [request_id=%s]: %s", index, request_id, exc
            )
            results.append(SyncResultItem(index=index, recorded=False, error=str(exc)))
        except Exception as exc:
            # One malformed entry must not discard the whole batch.
            db.rollback()
            logger.exception(
                "Sync entry %d failed unexpectedly [request_id=%s]: %s", index, request_id, exc
            )
            results.append(
                SyncResultItem(index=index, recorded=False, error="Internal error replaying entry")
            )

    return SyncResponse(
        received=len(payload.logs),
        recorded=recorded,
        failed=len(payload.logs) - recorded,
        results=results,
    )


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
        # geofence_pass is derived from the submitted coordinates, never taken
        # from the request body. As a client-supplied field it was trivially
        # spoofable, so a remote punch could assert it was inside a geofence.
        if req.gps_lat is not None and req.gps_lng is not None:
            try:
                from app.services.workforce_attendance_service import geo_attendance_service

                verdict = geo_attendance_service.validate_point(
                    db, current_user.org_id, float(req.gps_lat), float(req.gps_lng)
                )
                req.geofence_pass = 1 if verdict.get("valid") else 0
            except Exception:
                logger.warning("Geofence evaluation failed; recording the punch unchecked")
                req.geofence_pass = None
        else:
            req.geofence_pass = None

        log = attendance_controller.handle_check_in(
            db,
            req=req,
            current_user=current_user,
            background_tasks=background_tasks,
        )
        return log
    except LivenessUnavailableError as e:
        # Anti-spoofing backend missing/broken: a server fault, not a spoof.
        logger.error("Liveness engine unavailable during check-in: %s", e)
        raise HTTPException(
            status_code=503,
            detail={"code": LivenessUnavailableError.code, "message": str(e)},
        )
    except PermissionError as e:
        # Check if error message is a structured JSON
        detail = str(e)
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict) and "code" in parsed:
                raise HTTPException(status_code=403, detail=parsed)
        except json.JSONDecodeError:
            pass
        raise HTTPException(status_code=403, detail=detail)
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
    req: CheckOutRequest = Body(default=CheckOutRequest()),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Check-out endpoint for ending an active attendance session.
    Returns 400 if no active check-in exists.
    """
    try:
        log = attendance_controller.handle_check_out(
            db,
            req=req,
            current_user=current_user,
        )
        return log
    except LivenessUnavailableError as e:
        logger.error("Liveness engine unavailable during check-out: %s", e)
        raise HTTPException(
            status_code=503,
            detail={"code": LivenessUnavailableError.code, "message": str(e)},
        )
    except PermissionError as e:
        # Check if error message is a structured JSON
        detail = str(e)
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict) and "code" in parsed:
                raise HTTPException(status_code=403, detail=parsed)
        except json.JSONDecodeError:
            pass
        raise HTTPException(status_code=403, detail=detail)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        request_id = getattr(getattr(request, "state", None), "request_id", None)
        logger.exception(f"Check-out failed [request_id={request_id}]: {e}")
        raise HTTPException(status_code=500, detail="Check-out processing failed")


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
    if target_user_id != current_user.id:
        if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "Manager"]:
            raise HTTPException(status_code=403, detail="Unauthorized to view summary of other users")
        # STRICT MULTI-TENANCY: Target user must belong to caller's organization
        target_user = db.query(User).filter(
            User.id == target_user_id,
            User.org_id == current_user.org_id,
            User.is_deleted == 0,
        ).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="Identity not found")

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
