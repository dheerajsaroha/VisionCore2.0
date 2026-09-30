"""
workforce_router.py — VisionCore 3.0 Workforce Core Domain REST API Router

Tag-grouped endpoints for:
- attendance          : mark, list sessions, timeline, summary, analytics dashboard
- attendance-devices  : device registry CRUD
- attendance-policies : attendance policy evaluation + CRUD
- geofence            : GPS geofence zone management + validation
- leave               : apply, approve, reject, cancel, balances, accrual, encashment
- shifts              : shift template CRUD, legacy shifts, assignments
- rosters             : roster create, publish, entries
- shift-swaps         : shift swap request lifecycle
- workforce-planning  : headcount plans, vacancies, forecasts, capacity snapshots
- bench               : bench assignment, release, aging report
- overtime            : OT computation, approval, comp-off crediting
- holidays            : holiday calendar CRUD + entries
- corrections         : attendance correction request lifecycle
- time-tracking       : clock in/out, break lifecycle

Integrates the five Workforce Core services:
  workforce_attendance_service, workforce_shift_service, workforce_leave_service,
  workforce_time_service, workforce_planning_service.
"""

from __future__ import annotations

from datetime import date, datetime, time as dtime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user
from app.db.models.all_models import (
    AttendanceCorrection,
    AttendanceDevice,
    AttendancePolicy,
    AttendanceSession,
    AttendanceEvent,
    GeofenceZone,
    Roster,
    RosterEntry,
    Shift,
    ShiftAssignment,
    ShiftSwapRequest,
    ShiftTemplate,
    User,
)
from app.services.workforce_attendance_service import (
    attendance_analytics_service,
    attendance_policy_service,
    attendance_service,
    geo_attendance_service,
)
from app.services.workforce_shift_service import (
    roster_service,
    shift_service,
    shift_swap_service,
)
from app.services.workforce_leave_service import (
    holiday_service,
    leave_accrual_service,
    leave_encashment_service,
    leave_service,
)
from app.services.workforce_planning_service import (
    bench_management_service,
    capacity_planning_service,
    workforce_planning_service,
)
from app.services.workforce_time_service import (
    break_service,
    overtime_service,
    time_tracking_service,
)

router = APIRouter()


# =============================================================================
#  Request / Response Schemas
# =============================================================================

class AttendanceMarkIn(BaseModel):
    user_id: int
    channel: str = "FACE"
    work_date: Optional[date] = None
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    device_id: Optional[int] = None
    device_ref: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    ip_address: Optional[str] = None
    notes: Optional[str] = None


class AttendanceDeviceCreate(BaseModel):
    name: str
    device_type: str = "FACE"
    serial_number: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    location: Optional[str] = None
    channel: Optional[str] = None
    ip_whitelist: Optional[List[str]] = None
    is_trusted: bool = True
    is_active: bool = True
    description: Optional[str] = None


class AttendanceDeviceUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    is_trusted: Optional[bool] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class AttendancePolicyCreate(BaseModel):
    name: str
    grace_period_mins: int = 5
    late_threshold_mins: int = 15
    half_day_hours: float = 4.0
    geofence_radius_meters: float = 300.0
    allow_face: bool = True
    allow_qr: bool = True
    allow_gps: bool = True
    allow_ble: bool = True
    allow_nfc: bool = True
    allow_wifi: bool = False
    allow_kiosk: bool = True
    allow_manual: bool = False
    ip_whitelist: Optional[List[str]] = None
    is_active: bool = True


class GeofenceZoneCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_meters: float = 300.0
    is_active: bool = True
    description: Optional[str] = None


class GeofenceValidateIn(BaseModel):
    lat: float
    lng: float


class LeaveApplyIn(BaseModel):
    leave_type_id: int
    start_date: date
    end_date: date
    reason: Optional[str] = None
    is_half_day: bool = False
    half_day_period: Optional[str] = None


class LeaveDecisionIn(BaseModel):
    note: Optional[str] = None


class EncashmentIn(BaseModel):
    leave_type_id: int
    days_to_encash: float
    daily_rate: float


class ShiftTemplateCreate(BaseModel):
    name: str
    shift_type: str = "FIXED"
    start_time: str = "09:00"
    end_time: str = "18:00"
    duration_hours: Optional[float] = None
    break_minutes: int = 0
    is_active: bool = True
    description: Optional[str] = None


class ShiftTemplateUpdate(BaseModel):
    name: Optional[str] = None
    shift_type: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_hours: Optional[float] = None
    break_minutes: Optional[int] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class LegacyShiftCreate(BaseModel):
    shift_name: str
    start_time: str = "09:00"
    end_time: str = "18:00"
    grace_period_mins: int = 5
    buffer_mins: int = 15
    break_deduct_mins: int = 0


class ShiftAssignmentCreate(BaseModel):
    user_id: int
    shift_template_id: Optional[int] = None
    shift_id: Optional[int] = None
    start_date: date
    end_date: date


class RosterCreate(BaseModel):
    dept_id: int
    title: str
    start_date: date
    end_date: date
    roster_type: str = "WEEKLY"
    notes: Optional[str] = None


class ShiftSwapCreate(BaseModel):
    target_user_id: Optional[int] = None
    shift_assignment_id: Optional[int] = None
    swap_date: date
    requested_shift_template_id: Optional[int] = None
    reason: Optional[str] = None


class ShiftSwapResolveIn(BaseModel):
    action: str  # approve | reject | cancel
    note: Optional[str] = None


class HeadcountPlanCreate(BaseModel):
    dept_id: int
    period_year: int
    period_month: Optional[int] = None
    planned_headcount: int
    approved_headcount: Optional[int] = None
    notes: Optional[str] = None


class ForecastCreate(BaseModel):
    dept_id: Optional[int] = None
    forecast_period: str
    hiring_requirement: int
    attrition_estimate: Optional[int] = None
    notes: Optional[str] = None


class CapacitySnapshotCreate(BaseModel):
    dept_id: Optional[int] = None
    note: Optional[str] = None


class BenchAddIn(BaseModel):
    user_id: int
    reason: Optional[str] = None


class OvertimeComputeIn(BaseModel):
    user_id: int
    work_date: date
    entry_id: Optional[int] = None
    approved_by: Optional[int] = None
    rate_multiplier: float = 1.50


class OvertimeDecisionIn(BaseModel):
    note: Optional[str] = None


class HolidayCalendarCreate(BaseModel):
    name: str
    year: int = 2026
    description: Optional[str] = None
    is_active: bool = True


class HolidayEntryCreate(BaseModel):
    holiday_date: date
    name: str
    holiday_type: str = "NATIONAL"
    is_optional: bool = False
    description: Optional[str] = None


class CorrectionCreate(BaseModel):
    user_id: int
    attendance_log_id: Optional[int] = None
    requested_clock_in: Optional[datetime] = None
    requested_clock_out: Optional[datetime] = None
    reason: str


class CorrectionReviewIn(BaseModel):
    note: Optional[str] = None


class AccrualRunIn(BaseModel):
    frequency: str = "monthly"  # monthly | quarterly | yearly
    year: Optional[int] = None


# Admin role helper
_ADMIN_ROLES = ("Admin", "SuperAdmin", "OrgAdmin")


def _require_admin(user: User) -> None:
    if user.role.name not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Administrator role required")


def _model_to_dict(obj: Any) -> Dict[str, Any]:
    """Best-effort ORM object → dict serialization."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    d = {}
    for c in obj.__table__.columns:
        val = getattr(obj, c.name, None)
        if isinstance(val, (datetime, date, dtime)):
            val = val.isoformat()
        elif isinstance(val, UUID):
            val = str(val)
        d[c.name] = val
    return d


# =============================================================================
#  ATTENDANCE — /workforce/attendance
# =============================================================================

@router.post("/attendance/mark", tags=["attendance"])
def mark_attendance(
    payload: AttendanceMarkIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Mark attendance for a user via any supported channel. Emits AttendanceMarked event."""
    target_user_id = payload.user_id or current_user.id
    if target_user_id != current_user.id:
        _require_admin(current_user)
    try:
        session_obj = attendance_service.mark_attendance(
            db=db,
            org_id=current_user.org_id,
            user_id=target_user_id,
            channel=payload.channel,
            check_in=payload.check_in,
            check_out=payload.check_out,
            work_date=payload.work_date,
            device_id=payload.device_id,
            device_ref=payload.device_ref,
            gps_lat=payload.gps_lat,
            gps_lng=payload.gps_lng,
            ip_address=payload.ip_address,
            notes=payload.notes,
            actor_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _model_to_dict(session_obj)


@router.get("/attendance/sessions", tags=["attendance"])
def list_attendance_sessions(
    user_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    """List attendance sessions with optional filters."""
    target_user_id = user_id
    if current_user.role.name not in _ADMIN_ROLES + ("Manager",) and user_id is None:
        target_user_id = current_user.id
    sessions = attendance_service.get_sessions(
        db, current_user.org_id, user_id=target_user_id,
        start_date=start_date, end_date=end_date, status_filter=status_filter,
        skip=skip, limit=limit,
    )
    return [_model_to_dict(s) for s in sessions]


@router.get("/attendance/timeline/{user_id}", tags=["attendance"])
def get_attendance_timeline(
    user_id: int,
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    """Per-employee day-view timeline of attendance sessions."""
    if user_id != current_user.id and current_user.role.name not in _ADMIN_ROLES + ("Manager",):
        raise HTTPException(status_code=403, detail="Cannot view another user's timeline")
    sessions = attendance_service.get_timeline(db, current_user.org_id, user_id, limit=limit)
    return [_model_to_dict(s) for s in sessions]


@router.get("/attendance/summary", tags=["attendance"])
def get_attendance_summary(
    user_id: Optional[int] = None,
    period: str = "month",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Attendance KPI summary for a user over a period."""
    target_user_id = user_id or current_user.id
    if target_user_id != current_user.id and current_user.role.name not in _ADMIN_ROLES + ("Manager",):
        raise HTTPException(status_code=403, detail="Cannot view another user's summary")
    return attendance_service.get_summary(db, current_user.org_id, target_user_id, period)


@router.get("/attendance/events/{session_id}", tags=["attendance"])
def list_session_events(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    """List individual punch events within an attendance session."""
    events = (
        db.query(AttendanceEvent)
        .filter(AttendanceEvent.session_id == session_id, AttendanceEvent.org_id == current_user.org_id)
        .order_by(AttendanceEvent.event_time)
        .all()
    )
    return [_model_to_dict(e) for e in events]


# =============================================================================
#  ATTENDANCE DEVICES — /workforce/devices
# =============================================================================

@router.get("/devices", tags=["attendance-devices"])
def list_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    """List all attendance devices in the org."""
    devices = (
        db.query(AttendanceDevice)
        .filter(AttendanceDevice.org_id == current_user.org_id)
        .order_by(AttendanceDevice.device_name)
        .all()
    )
    return [_model_to_dict(d) for d in devices]


@router.post("/devices", status_code=status.HTTP_201_CREATED, tags=["attendance-devices"])
def create_device(
    payload: AttendanceDeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Register a new attendance device (Admin)."""
    _require_admin(current_user)
    # API vocabulary is deliberately friendlier than the persisted registry model.
    data = payload.model_dump(exclude_none=True)
    device = AttendanceDevice(
        org_id=current_user.org_id,
        device_name=data["name"],
        device_type=data.get("channel") or data.get("device_type", "FACE"),
        serial_number=data.get("serial_number"),
        model=data.get("model"),
        location=data.get("location"),
        is_trusted=data.get("is_trusted", True),
        is_active=data.get("is_active", True),
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return _model_to_dict(device)


@router.put("/devices/{device_id}", tags=["attendance-devices"])
def update_device(
    device_id: int,
    payload: AttendanceDeviceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Update a device registry entry (Admin)."""
    _require_admin(current_user)
    device = (
        db.query(AttendanceDevice)
        .filter(AttendanceDevice.id == device_id, AttendanceDevice.org_id == current_user.org_id)
        .first()
    )
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(device, "device_name" if field == "name" else field, value)
    db.commit()
    db.refresh(device)
    return _model_to_dict(device)


@router.delete("/devices/{device_id}", tags=["attendance-devices"])
def deactivate_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Deactivate (soft) an attendance device (Admin)."""
    _require_admin(current_user)
    device = (
        db.query(AttendanceDevice)
        .filter(AttendanceDevice.id == device_id, AttendanceDevice.org_id == current_user.org_id)
        .first()
    )
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.is_active = False
    db.commit()
    return {"message": "Device deactivated", "id": device.id}


# =============================================================================
#  ATTENDANCE POLICIES — /workforce/policies + GEOFENCE
# =============================================================================

@router.get("/policies/attendance", tags=["attendance-policies"])
def get_attendance_policy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get the active attendance policy for the org."""
    policy = attendance_policy_service.get_policy(db, current_user.org_id)
    if not policy:
        raise HTTPException(status_code=404, detail="No attendance policy configured")
    return _model_to_dict(policy)


@router.post("/policies/attendance", tags=["attendance-policies"])
def create_attendance_policy(
    payload: AttendancePolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Create/update an attendance policy (Admin)."""
    _require_admin(current_user)
    data = payload.model_dump()
    data["org_id"] = current_user.org_id
    policy = AttendancePolicy(**data)
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return _model_to_dict(policy)


@router.post("/attendance/evaluate-policy", tags=["attendance-policies"])
def evaluate_attendance_policy(
    ctx: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Evaluate an attendance context (check_in, shift_start, channel, IP, GPS) against the org policy."""
    return attendance_policy_service.evaluate_policy(db, current_user.org_id, ctx)


@router.get("/geofence/zones", tags=["geofence"])
def list_geofence_zones(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    zones = geo_attendance_service.list_zones(db, current_user.org_id)
    return [_model_to_dict(z) for z in zones]


@router.post("/geofence/zones", status_code=status.HTTP_201_CREATED, tags=["geofence"])
def create_geofence_zone(
    payload: GeofenceZoneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    _require_admin(current_user)
    data = payload.model_dump()
    data["code"] = "".join(ch if ch.isalnum() else "-" for ch in data["name"].upper()).strip("-")[:50] or "ZONE"
    data["address"] = data.pop("description", None)
    zone = geo_attendance_service.create_zone(db, current_user.org_id, data)
    return _model_to_dict(zone)


@router.post("/geofence/validate", tags=["geofence"])
def validate_geofence_point(
    payload: GeofenceValidateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Validate whether a GPS point falls inside any active geofence zone."""
    return geo_attendance_service.validate_point(db, current_user.org_id, payload.lat, payload.lng)


# =============================================================================
#  LEAVE — /workforce/leave, /workforce/leave/accrual, /workforce/leave/encashment
# =============================================================================

@router.post("/leave/apply", status_code=status.HTTP_201_CREATED, tags=["leave"])
def apply_leave(
    payload: LeaveApplyIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Apply for leave with balance reservation and workflow submission."""
    try:
        req = leave_service.apply_leave(
            db=db,
            org_id=current_user.org_id,
            user_id=current_user.id,
            leave_type_id=payload.leave_type_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            reason=payload.reason,
            is_half_day=payload.is_half_day,
            half_day_period=payload.half_day_period,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _model_to_dict(req)


@router.post("/leave/requests/{request_id}/approve", tags=["leave"])
def approve_leave_request(
    request_id: int,
    payload: LeaveDecisionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Approve a pending leave request (Admin/Manager)."""
    if current_user.role.name not in _ADMIN_ROLES + ("Manager", "DeptHead"):
        raise HTTPException(status_code=403, detail="Unauthorized to approve leave requests")
    try:
        req = leave_service.approve_leave(
            db, current_user.org_id, request_id, current_user.id, payload.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _model_to_dict(req)


@router.post("/leave/requests/{request_id}/reject", tags=["leave"])
def reject_leave_request(
    request_id: int,
    payload: LeaveDecisionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Reject a pending leave request (Admin/Manager)."""
    if current_user.role.name not in _ADMIN_ROLES + ("Manager", "DeptHead"):
        raise HTTPException(status_code=403, detail="Unauthorized to reject leave requests")
    try:
        req = leave_service.reject_leave(
            db, current_user.org_id, request_id, current_user.id, payload.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _model_to_dict(req)


@router.post("/leave/requests/{request_id}/cancel", tags=["leave"])
def cancel_leave_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Cancel a leave request (owner or admin)."""
    try:
        result = leave_service.cancel_leave(
            db, current_user.org_id, request_id, current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _model_to_dict(result)


@router.get("/leave/requests", tags=["leave"])
def list_leave_requests(
    user_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    """List leave requests with optional user/status filters."""
    target_user_id = user_id
    if current_user.role.name not in _ADMIN_ROLES + ("Manager", "DeptHead") and user_id is None:
        target_user_id = current_user.id
    requests = leave_service.list_requests(
        db, current_user.org_id, user_id=target_user_id, status_filter=status_filter,
        skip=skip, limit=limit,
    )
    return [_model_to_dict(r) for r in requests]


@router.get("/leave/balance", tags=["leave"])
def get_leave_balance(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get leave balances for current (or targeted) user."""
    target_user_id = user_id or current_user.id
    if target_user_id != current_user.id and current_user.role.name not in _ADMIN_ROLES + ("Manager",):
        raise HTTPException(status_code=403, detail="Cannot view another user's balance")
    return leave_service.get_balances(db, current_user.org_id, target_user_id)


@router.post("/leave/accrual/run", tags=["leave"])
def run_leave_accrual(
    payload: AccrualRunIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Run periodic leave accrual job (monthly/quarterly/yearly). (Admin)"""
    _require_admin(current_user)
    return leave_accrual_service.run_accrual(
        db, current_user.org_id, frequency=payload.frequency, year=payload.year
    )


@router.post("/leave/encashment/calculate", tags=["leave"])
def calculate_leave_encashment(
    payload: EncashmentIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Calculate encashment value for unused paid leave days."""
    try:
        return leave_encashment_service.calculate_encashment(
            db, current_user.org_id, current_user.id,
            payload.leave_type_id, payload.days_to_encash, payload.daily_rate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# =============================================================================
#  SHIFTS — /workforce/shifts
# =============================================================================

@router.get("/shifts/templates", tags=["shifts"])
def list_shift_templates(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    templates = shift_service.list_templates(db, current_user.org_id, active_only)
    return [_model_to_dict(t) for t in templates]


@router.post("/shifts/templates", status_code=status.HTTP_201_CREATED, tags=["shifts"])
def create_shift_template(
    payload: ShiftTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Create a reusable shift template (Admin)."""
    _require_admin(current_user)
    data = payload.model_dump(exclude_none=True)
    try:
        start_time = datetime.strptime(data.pop("start_time"), "%H:%M").time()
        end_time = datetime.strptime(data.pop("end_time"), "%H:%M").time()
    except (ValueError, KeyError):
        raise HTTPException(status_code=400, detail="start_time/end_time must be HH:MM")
    data["start_time"] = start_time
    data["end_time"] = end_time
    data["total_hours"] = data.pop("duration_hours", None)
    data.pop("break_minutes", None)
    data.pop("description", None)
    tpl = shift_service.create_template(db, current_user.org_id, data)
    return _model_to_dict(tpl)


@router.put("/shifts/templates/{template_id}", tags=["shifts"])
def update_shift_template(
    template_id: int,
    payload: ShiftTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Update a shift template (Admin)."""
    _require_admin(current_user)
    tpl = shift_service.get_template(db, template_id)
    if not tpl or tpl.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Shift template not found")
    data = payload.model_dump(exclude_none=True)
    if "start_time" in data:
        try:
            data["start_time"] = datetime.strptime(data.pop("start_time"), "%H:%M").time()
        except ValueError:
            raise HTTPException(status_code=400, detail="start_time must be HH:MM")
    if "end_time" in data:
        try:
            data["end_time"] = datetime.strptime(data.pop("end_time"), "%H:%M").time()
        except ValueError:
            raise HTTPException(status_code=400, detail="end_time must be HH:MM")
    tpl = shift_service.update_template(db, tpl, data)
    return _model_to_dict(tpl)


@router.get("/shifts", tags=["shifts"])
def list_legacy_shifts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    shifts = shift_service.list_shifts(db, current_user.org_id)
    return [_model_to_dict(s) for s in shifts]


@router.post("/shifts", status_code=status.HTTP_201_CREATED, tags=["shifts"])
def create_legacy_shift(
    payload: LegacyShiftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Create a legacy Shift row (Admin)."""
    _require_admin(current_user)
    try:
        start_time = datetime.strptime(payload.start_time, "%H:%M").time()
        end_time = datetime.strptime(payload.end_time, "%H:%M").time()
    except ValueError:
        raise HTTPException(status_code=400, detail="start_time/end_time must be HH:MM")
    shift = shift_service.create_legacy_shift(db, current_user.org_id, {
        "shift_name": payload.shift_name,
        "start_time": start_time,
        "end_time": end_time,
        "grace_period_mins": payload.grace_period_mins,
        "buffer_mins": payload.buffer_mins,
        "break_deduct_mins": payload.break_deduct_mins,
    })
    return _model_to_dict(shift)


@router.get("/shifts/assignments", tags=["shifts"])
def list_shift_assignments(
    user_id: Optional[int] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    assignments = shift_service.list_assignments(db, current_user.org_id, user_id, active_only)
    return [_model_to_dict(a) for a in assignments]


@router.post("/shifts/assignments", status_code=status.HTTP_201_CREATED, tags=["shifts"])
def assign_shift(
    payload: ShiftAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Map a user to a shift template/shift for a date range (Admin)."""
    _require_admin(current_user)
    assignment = shift_service.assign_shift(db, current_user.org_id, payload.model_dump())
    return _model_to_dict(assignment)


# =============================================================================
#  ROSTERS — /workforce/rosters
# =============================================================================

@router.get("/rosters", tags=["rosters"])
def list_rosters(
    dept_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    rosters = roster_service.list_rosters(db, current_user.org_id, dept_id=dept_id, status_filter=status_filter)
    return [_model_to_dict(r) for r in rosters]


@router.post("/rosters", status_code=status.HTTP_201_CREATED, tags=["rosters"])
def create_roster(
    payload: RosterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Create a roster record for a department (Admin)."""
    _require_admin(current_user)
    data = payload.model_dump(exclude={"notes"})
    roster = roster_service.create_roster(db, current_user.org_id, data)
    return _model_to_dict(roster)


@router.post("/rosters/{roster_id}/publish", tags=["rosters"])
def publish_roster(
    roster_id: int,
    auto_generate: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Publish a roster and generate roster entries (Admin)."""
    _require_admin(current_user)
    try:
        roster = roster_service.publish_roster(
            db, current_user.org_id, roster_id, current_user.id, auto_generate=auto_generate
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _model_to_dict(roster)


@router.get("/rosters/{roster_id}/entries", tags=["rosters"])
def list_roster_entries(
    roster_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    entries = roster_service.list_entries(db, current_user.org_id, roster_id)
    return [_model_to_dict(e) for e in entries]


@router.post("/rosters/{roster_id}/generate", tags=["rosters"])
def generate_roster_entries(
    roster_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Generate roster entries from active shift assignments (Admin)."""
    _require_admin(current_user)
    roster = db.query(Roster).filter(Roster.id == roster_id, Roster.org_id == current_user.org_id).first()
    if not roster:
        raise HTTPException(status_code=404, detail="Roster not found")
    entries = roster_service.generate_entries(db, current_user.org_id, roster)
    return [_model_to_dict(e) for e in entries]


# =============================================================================
#  SHIFT SWAPS — /workforce/shift-swaps
# =============================================================================

@router.get("/shifts/swaps", tags=["shift-swaps"])
def list_shift_swaps(
    status_filter: Optional[str] = Query(None, alias="status"),
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    swaps = shift_swap_service.list_swap_requests(
        db, current_user.org_id, status_filter=status_filter, user_id=user_id
    )
    return [_model_to_dict(s) for s in swaps]


@router.post("/shifts/swaps", status_code=status.HTTP_201_CREATED, tags=["shift-swaps"])
def create_shift_swap(
    payload: ShiftSwapCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Create a shift swap request with workflow submission."""
    swap = shift_swap_service.create_swap_request(
        db, current_user.org_id, current_user.id, payload.model_dump()
    )
    return _model_to_dict(swap)


@router.post("/shifts/swaps/{swap_id}/resolve", tags=["shift-swaps"])
def resolve_shift_swap(
    swap_id: int,
    payload: ShiftSwapResolveIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Approve, reject, or cancel a shift swap request."""
    try:
        swap = shift_swap_service.resolve_swap(
            db, current_user.org_id, swap_id, current_user.id, payload.action, payload.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _model_to_dict(swap)


# =============================================================================
#  WORKFORCE PLANNING — /workforce/planning, /workforce/bench
# =============================================================================

@router.get("/planning/headcount", tags=["workforce-planning"])
def list_headcount_plans(
    dept_id: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    plans = workforce_planning_service.list_headcount_plans(db, current_user.org_id, dept_id=dept_id, year=year)
    return [_model_to_dict(p) for p in plans]


@router.post("/planning/headcount", status_code=status.HTTP_201_CREATED, tags=["workforce-planning"])
def create_headcount_plan(
    payload: HeadcountPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Create a headcount plan for a department/period (Admin)."""
    _require_admin(current_user)
    plan = workforce_planning_service.create_headcount_plan(
        db, current_user.org_id, payload.model_dump(exclude={"notes"})
    )
    return _model_to_dict(plan)


@router.get("/planning/vacancies", tags=["workforce-planning"])
def get_open_vacancies(
    dept_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Compute open vacancies = planned headcount minus active employees."""
    return workforce_planning_service.compute_vacancies(db, current_user.org_id, dept_id=dept_id)


@router.get("/planning/forecasts", tags=["workforce-planning"])
def list_forecasts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    forecasts = workforce_planning_service.list_forecasts(db, current_user.org_id)
    return [_model_to_dict(f) for f in forecasts]


@router.post("/planning/forecasts", status_code=status.HTTP_201_CREATED, tags=["workforce-planning"])
def create_forecast(
    payload: ForecastCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Create a future hiring requirement projection (Admin)."""
    _require_admin(current_user)
    forecast = workforce_planning_service.create_forecast(db, current_user.org_id, payload.model_dump())
    return _model_to_dict(forecast)


@router.get("/planning/capacity", tags=["workforce-planning"])
def list_capacity_snapshots(
    dept_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    snapshots = capacity_planning_service.list_snapshots(db, current_user.org_id, dept_id=dept_id, limit=limit)
    return [_model_to_dict(s) for s in snapshots]


@router.post("/planning/capacity", status_code=status.HTTP_201_CREATED, tags=["workforce-planning"])
def create_capacity_snapshot(
    payload: CapacitySnapshotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Create a point-in-time capacity/utilization snapshot (Admin)."""
    _require_admin(current_user)
    snapshot = capacity_planning_service.create_snapshot(
        db, current_user.org_id, dept_id=payload.dept_id, note=payload.note
    )
    return _model_to_dict(snapshot)


@router.get("/bench", tags=["bench"])
def get_bench_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Bench aging report — active bench members with days on bench."""
    return bench_management_service.bench_report(db, current_user.org_id)


@router.post("/bench/add", status_code=status.HTTP_201_CREATED, tags=["bench"])
def add_to_bench(
    payload: BenchAddIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Add an employee to bench (unallocated capacity). (Admin)"""
    _require_admin(current_user)
    try:
        record = bench_management_service.add_to_bench(
            db, current_user.org_id, payload.user_id, reason=payload.reason, actor_user_id=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _model_to_dict(record)


@router.post("/bench/{bench_id}/release", tags=["bench"])
def release_from_bench(
    bench_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Release an employee from bench (Admin)."""
    _require_admin(current_user)
    try:
        record = bench_management_service.release_from_bench(
            db, current_user.org_id, bench_id, actor_user_id=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _model_to_dict(record)


# =============================================================================
#  OVERTIME — /workforce/overtime
# =============================================================================

@router.post("/overtime/compute", tags=["overtime"])
def compute_overtime(
    payload: OvertimeComputeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Compute overtime hours from a time entry vs the user's shift."""
    try:
        ot = overtime_service.compute_overtime(
            db, current_user.org_id, payload.user_id, payload.work_date,
            entry_id=payload.entry_id, approved_by=payload.approved_by or current_user.id,
            rate_multiplier=payload.rate_multiplier,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _model_to_dict(ot)


@router.get("/overtime", tags=["overtime"])
def list_overtime(
    user_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    records = overtime_service.list_overtime(db, current_user.org_id, user_id=user_id, status_filter=status_filter)
    return [_model_to_dict(r) for r in records]


@router.post("/overtime/{overtime_id}/approve", tags=["overtime"])
def approve_overtime(
    overtime_id: int,
    payload: OvertimeDecisionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Approve an overtime record (Admin/Manager)."""
    if current_user.role.name not in _ADMIN_ROLES + ("Manager", "DeptHead"):
        raise HTTPException(status_code=403, detail="Unauthorized to approve overtime")
    try:
        ot = overtime_service.approve_overtime(
            db, current_user.org_id, overtime_id, current_user.id, payload.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _model_to_dict(ot)


@router.post("/overtime/{overtime_id}/credit-comp-off", tags=["overtime"])
def credit_comp_off(
    overtime_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Credit approved overtime minutes into the user's comp-off ledger (Admin)."""
    _require_admin(current_user)
    try:
        balance = overtime_service.credit_comp_off(
            db, current_user.org_id, overtime_id, current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _model_to_dict(balance)


# =============================================================================
#  HOLIDAYS — /workforce/holidays
# =============================================================================

@router.get("/holidays/calendars", tags=["holidays"])
def list_holiday_calendars(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    calendars = holiday_service.list_calendars(db, current_user.org_id)
    return [_model_to_dict(c) for c in calendars]


@router.post("/holidays/calendars", status_code=status.HTTP_201_CREATED, tags=["holidays"])
def create_holiday_calendar(
    payload: HolidayCalendarCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Create a named holiday calendar (Admin)."""
    _require_admin(current_user)
    calendar = holiday_service.create_calendar(db, current_user.org_id, payload.model_dump(exclude={"year"}))
    return _model_to_dict(calendar)


@router.get("/holidays/entries", tags=["holidays"])
def list_holiday_entries(
    calendar_id: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    entries = holiday_service.list_entries(db, current_user.org_id, calendar_id=calendar_id, year=year)
    return [_model_to_dict(e) for e in entries]


@router.post("/holidays/entries", status_code=status.HTTP_201_CREATED, tags=["holidays"])
def add_holiday_entry(
    payload: HolidayEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Add a holiday entry into a calendar (Admin)."""
    _require_admin(current_user)
    if not payload.holiday_date:
        raise HTTPException(status_code=400, detail="holiday_date is required")
    data = payload.model_dump()
    data["holiday_date"] = payload.holiday_date
    if data.pop("is_optional", False):
        data["holiday_type"] = "OPTIONAL"
    # If calendar_id omitted, fall back to first org calendar
    calendar_id = data.get("calendar_id")
    if not calendar_id:
        calendars = holiday_service.list_calendars(db, current_user.org_id)
        calendar_id = calendars[0].id if calendars else None
        if not calendar_id:
            raise HTTPException(status_code=400, detail="No holiday calendar exists — create one first")
    entry = holiday_service.add_entry(db, current_user.org_id, calendar_id, data)
    return _model_to_dict(entry)


@router.delete("/holidays/entries/{entry_id}", tags=["holidays"])
def delete_holiday_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Delete a holiday entry (Admin)."""
    _require_admin(current_user)
    deleted = holiday_service.delete_entry(db, current_user.org_id, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Holiday entry not found")
    return {"message": "Holiday entry deleted", "id": entry_id}


# =============================================================================
#  CORRECTIONS — /workforce/corrections
# =============================================================================

@router.get("/corrections", tags=["corrections"])
def list_corrections(
    user_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    q = db.query(AttendanceCorrection).filter(AttendanceCorrection.organization_id == current_user.org_id)
    target_user_id = user_id or current_user.id
    if current_user.role.name not in _ADMIN_ROLES + ("Manager",) and user_id is None:
        target_user_id = current_user.id
    if target_user_id and current_user.role.name not in _ADMIN_ROLES + ("Manager",):
        q = q.filter(AttendanceCorrection.user_id == target_user_id)
    elif user_id:
        q = q.filter(AttendanceCorrection.user_id == user_id)
    if status_filter:
        q = q.filter(AttendanceCorrection.status == status_filter)
    corrections = q.order_by(AttendanceCorrection.created_at.desc()).all()
    return [_model_to_dict(c) for c in corrections]


@router.post("/corrections", status_code=status.HTTP_201_CREATED, tags=["corrections"])
def create_correction(
    payload: CorrectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Submit an attendance correction request."""
    data = payload.model_dump()
    data["organization_id"] = current_user.org_id
    data["user_id"] = payload.user_id or current_user.id
    correction = AttendanceCorrection(**data)
    db.add(correction)
    db.commit()
    db.refresh(correction)
    return _model_to_dict(correction)


@router.post("/corrections/{correction_id}/review", tags=["corrections"])
def review_correction(
    correction_id: int,
    action: str = Query(..., description="approve | reject"),
    payload: CorrectionReviewIn = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Review an attendance correction request (Admin/Manager)."""
    if current_user.role.name not in _ADMIN_ROLES + ("Manager", "DeptHead"):
        raise HTTPException(status_code=403, detail="Unauthorized to review corrections")
    correction = (
        db.query(AttendanceCorrection)
        .filter(AttendanceCorrection.id == correction_id, AttendanceCorrection.organization_id == current_user.org_id)
        .first()
    )
    if not correction:
        raise HTTPException(status_code=404, detail="Correction not found")
    if correction.status != "pending":
        raise HTTPException(status_code=400, detail=f"Correction is already {correction.status}")
    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be approve or reject")
    correction.status = "approved" if action == "approve" else "rejected"
    correction.reviewer_user_id = current_user.id
    correction.reviewer_note = payload.note if payload else None
    correction.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(correction)
    return _model_to_dict(correction)


# =============================================================================
#  ANALYTICS — /workforce/analytics
# =============================================================================

@router.get("/analytics/dashboard", tags=["analytics"])
def get_attendance_analytics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Org-wide attendance analytics dashboard: KPIs + trend lines."""
    return attendance_analytics_service.dashboard(db, current_user.org_id, days=days)


@router.get("/analytics/attendance/trends", tags=["analytics"])
def get_attendance_trends(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Present/late/absent rate trend lines over the given period."""
    data = attendance_analytics_service.dashboard(db, current_user.org_id, days=days)
    return {"period_days": days, "trends": data.get("trends", [])}


# =============================================================================
#  TIME TRACKING — /workforce/time
# =============================================================================

@router.post("/time/clock-in", tags=["time-tracking"])
def clock_in(
    work_date: Optional[date] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Clock in for the user (self or proxy). Emits ClockedIn event."""
    target_user_id = user_id or current_user.id
    if target_user_id != current_user.id:
        _require_admin(current_user)
    try:
        entry = time_tracking_service.clock_in(db, current_user.org_id, target_user_id, work_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _model_to_dict(entry)


@router.post("/time/clock-out", tags=["time-tracking"])
def clock_out(
    work_date: Optional[date] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Clock out for the user (self or proxy). Emits ClockedOut event."""
    target_user_id = user_id or current_user.id
    if target_user_id != current_user.id:
        _require_admin(current_user)
    try:
        entry = time_tracking_service.clock_out(db, current_user.org_id, target_user_id, work_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _model_to_dict(entry)


@router.get("/time/entries", tags=["time-tracking"])
def list_time_entries(
    user_id: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    entries = time_tracking_service.list_entries(
        db, current_user.org_id, user_id=user_id, from_date=from_date, to_date=to_date
    )
    return [_model_to_dict(e) for e in entries]


@router.post("/time/breaks/start", tags=["time-tracking"])
def start_break(
    break_type: str = "SHORT",
    work_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Start a break for the current user."""
    try:
        log = break_service.start_break(
            db, current_user.org_id, current_user.id, work_date=work_date, break_type=break_type
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _model_to_dict(log)


@router.post("/time/breaks/{break_id}/end", tags=["time-tracking"])
def end_break(
    break_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """End an active break."""
    try:
        log = break_service.end_break(db, current_user.org_id, current_user.id, break_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _model_to_dict(log)


@router.get("/time/breaks", tags=["time-tracking"])
def list_breaks(
    time_entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    logs = break_service.list_breaks(db, current_user.org_id, time_entry_id)
    return [_model_to_dict(l) for l in logs]


# =============================================================================
#  SCHEDULER-READY: summary endpoint for dashboard widgets
# =============================================================================

@router.get("/attendance/channels", tags=["attendance"])
def list_channels():
    """List supported attendance channels."""
    from app.services.workforce_attendance_service import ATTR_CHANNELS
    return {"channels": list(ATTR_CHANNELS)}
