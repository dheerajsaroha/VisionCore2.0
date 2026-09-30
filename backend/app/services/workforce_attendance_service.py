"""
workforce_attendance_service.py — VisionCore 3.0 Workforce Core Attendance Services

Provides:
- AttendanceService: multi-channel attendance marking, session status computation, AttendanceMarked event
- AttendancePolicyService: policy evaluation (grace period, geofence, IP whitelist, device trust)
- GeoAttendanceService: geofence zone validation and GPS-based attendance
- AttendanceAnalyticsService: aggregate KPI dashboards (present/late/absent rates, trend lines)

All services integrate:
- audit_service.record()
- event_bus.publish()
- notification_service.send()
- business_calendar_service (working-day calculations)
- policy_engine (policy evaluation hooks)
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.all_models import (
    AttendanceDevice,
    AttendanceEvent,
    AttendanceLog,
    AttendancePolicy,
    AttendanceSession,
    GeofenceZone,
    LeaveRequest,
    User,
)
from app.services.audit_service import audit_service
from app.services.business_calendar_service import business_calendar_service
from app.services.event_bus import event_bus
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

# Canonical session status values
SESSION_STATUS = (
    "PRESENT", "LATE", "ABSENT", "HALF_DAY", "HOLIDAY", "WEEKEND",
    "WFH", "BUSINESS_TRAVEL", "ON_LEAVE", "MISSED_PUNCH",
)

# Canonical device channels
ATTR_CHANNELS = ("FACE", "QR", "GPS", "BLE", "NFC", "WiFi", "KIOSK", "MANUAL")


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine distance between two lat/lng points in kilometers."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class AttendancePolicyService:
    """Evaluates attendance policies: grace, geofence, IP whitelist, device trust."""

    def get_policy(self, db: Session, org_id: UUID) -> Optional[AttendancePolicy]:
        return (
            db.query(AttendancePolicy)
            .filter(AttendancePolicy.org_id == org_id, AttendancePolicy.is_active.is_(True))
            .order_by(AttendancePolicy.id.desc())
            .first()
        )

    def evaluate_policy(self, db: Session, org_id: UUID, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate an attendance policy evaluation context against the active org policy."""
        policy = self.get_policy(db, org_id)
        if not policy:
            # Default safe policy when none configured. Populate with the same
            # defaults declared on the AttendancePolicy model so the in-memory
            # fallback behaves identically to a freshly-persisted policy (the
            # database server_defaults below are only applied on INSERT, so an
            # un-flushed instance would otherwise leave numeric fields as None,
            # breaking threshold comparisons — see P6 defect at line ~138).
            policy = AttendancePolicy(
                org_id=org_id,
                name="__default__",
                grace_period_mins=5,
                late_threshold_mins=15,
                half_day_hours=4.0,
                overtime_trigger_mins=60,
                overtime_rate_multiplier=1.50,
                geofence_radius_meters=200,
                allow_gps=True,
                allow_face=True,
                allow_qr=True,
                allow_ble=False,
                allow_nfc=False,
                allow_wifi=True,
                allow_kiosk=True,
                allow_manual=True,
                ip_whitelist=[],
                is_active=True,
            )

        check_in = context.get("check_in")
        shift_start = context.get("shift_start")
        channel = context.get("channel", "FACE")
        ip_address = context.get("ip_address")
        device_trusted = context.get("device_trusted", True)

        results: Dict[str, Any] = {
            "policy_id": policy.id,
            "is_late": False,
            "is_early": False,
            "grace_period_mins": policy.grace_period_mins,
            "late_threshold_mins": policy.late_threshold_mins,
            "channel_allowed": True,
            "ip_allowed": True,
            "device_trusted": device_trusted,
            "within_geofence": True,
        }

        # Channel allow-check
        channel_map = {
            "FACE": policy.allow_face,
            "QR": policy.allow_qr,
            "GPS": policy.allow_gps,
            "BLE": policy.allow_ble,
            "NFC": policy.allow_nfc,
            "WiFi": policy.allow_wifi,
            "KIOSK": policy.allow_kiosk,
            "MANUAL": policy.allow_manual,
        }
        results["channel_allowed"] = bool(channel_map.get(channel, True))

        # IP whitelist check
        if ip_address and policy.ip_whitelist:
            whitelist = policy.ip_whitelist or []
            results["ip_allowed"] = ip_address in whitelist

        # Late / early evaluation
        if check_in and shift_start:
            if isinstance(shift_start, str):
                from datetime import time as dtime
                try:
                    hour, minute = (int(x) for x in shift_start.split(":")[:2])
                    shift_start = dtime(hour, minute)
                except Exception:
                    shift_start = None

            if shift_start is not None:
                if isinstance(shift_start, type(check_in)):
                    # Both datetimes → compare absolute
                    delta = (check_in - shift_start).total_seconds() / 60.0
                else:
                    reference_ts = check_in.replace(hour=0, minute=0, second=0, microsecond=0)
                    delta = (
                        (check_in - reference_ts).total_seconds() / 60.0
                        - (shift_start.hour * 60 + shift_start.minute)
                    )
                results["is_late"] = delta > policy.grace_period_mins
                results["is_early"] = delta < -15

        # Geofence (if GPS channel provided)
        lat = context.get("gps_lat")
        lng = context.get("gps_lng")
        if lat is not None and lng is not None:
            zones = (
                db.query(GeofenceZone)
                .filter(GeofenceZone.org_id == org_id, GeofenceZone.is_active.is_(True))
                .all()
            )
            inside = False
            for z in zones:
                dist_m = _haversine_km(float(lat), float(lng), float(z.latitude), float(z.longitude)) * 1000
                if dist_m <= float(z.radius_meters or policy.geofence_radius_meters):
                    inside = True
                    results["geofence_zone"] = z.name
                    break
            results["within_geofence"] = inside

        return results


class GeoAttendanceService:
    """Geofence zone validation and GPS-based attendance."""

    def create_zone(self, db: Session, org_id: UUID, data: Dict[str, Any]) -> GeofenceZone:
        zone = GeofenceZone(org_id=org_id, **data)
        db.add(zone)
        db.commit()
        db.refresh(zone)
        return zone

    def list_zones(self, db: Session, org_id: UUID) -> List[GeofenceZone]:
        return (
            db.query(GeofenceZone)
            .filter(GeofenceZone.org_id == org_id)
            .order_by(GeofenceZone.name)
            .all()
        )

    def validate_point(self, db: Session, org_id: UUID, lat: float, lng: float) -> Dict[str, Any]:
        """Check if a GPS point is inside any active geofence zone."""
        zones = self.list_zones(db, org_id)
        active = [z for z in zones if z.is_active]
        for z in active:
            dist_m = _haversine_km(lat, lng, float(z.latitude), float(z.longitude)) * 1000
            if dist_m <= float(z.radius_meters):
                return {
                    "valid": True,
                    "zone_id": z.id,
                    "zone_name": z.name,
                    "distance_meters": round(dist_m, 2),
                }
        return {"valid": False, "zone_id": None, "zone_name": None, "distance_meters": None}


class AttendanceService:
    """Multi-channel attendance marking, session status computation, event emission."""

    def __init__(self) -> None:
        self.policy_service = AttendancePolicyService()
        self.geo_service = GeoAttendanceService()

    def _get_or_create_session(
        self, db: Session, org_id: UUID, user_id: int, work_date: date
    ) -> AttendanceSession:
        session_obj = (
            db.query(AttendanceSession)
            .filter(
                AttendanceSession.org_id == org_id,
                AttendanceSession.user_id == user_id,
                AttendanceSession.work_date == work_date,
            )
            .first()
        )
        if not session_obj:
            session_obj = AttendanceSession(
                org_id=org_id,
                user_id=user_id,
                work_date=work_date,
                status="MISSED_PUNCH",
            )
            db.add(session_obj)
            db.commit()
            db.refresh(session_obj)
        return session_obj

    def compute_session_status(
        self,
        db: Session,
        org_id: UUID,
        user_id: int,
        work_date: date,
        check_in: Optional[datetime],
        policy_eval: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Compute canonical session status from policy evaluation and day context."""
        policy_eval = policy_eval or {}

        # Leave check
        on_leave = (
            db.query(LeaveRequest)
            .filter(
                LeaveRequest.organization_id == org_id,
                LeaveRequest.user_id == user_id,
                LeaveRequest.status == "approved",
                LeaveRequest.start_date <= datetime.combine(work_date, datetime.min.time(), tzinfo=timezone.utc),
                LeaveRequest.end_date >= datetime.combine(work_date, datetime.max.time(), tzinfo=timezone.utc),
            )
            .first()
        )
        if on_leave:
            return "ON_LEAVE"

        # Weekend / holiday via business calendar
        is_working = business_calendar_service.is_working_day(work_date, str(org_id)) \
            if hasattr(business_calendar_service, "is_working_day") else True
        if not is_working and work_date.weekday() >= 5:
            return "WEEKEND"
        if not is_working:
            return "HOLIDAY"

        if not check_in:
            return "ABSENT"

        if policy_eval.get("is_late"):
            return "LATE"

        # Half-day heuristic: less than half_day_hours worked
        session_obj = (
            db.query(AttendanceSession)
            .filter(
                AttendanceSession.org_id == org_id,
                AttendanceSession.user_id == user_id,
                AttendanceSession.work_date == work_date,
            )
            .first()
        )
        if session_obj and session_obj.work_hours is not None:
            policy = self.policy_service.get_policy(db, org_id)
            half_day_hours = float(policy.half_day_hours if policy else 4.0)
            if session_obj.work_hours < half_day_hours:
                return "HALF_DAY"

        return "PRESENT"

    def mark_attendance(
        self,
        db: Session,
        org_id: UUID,
        user_id: int,
        channel: str = "FACE",
        *,
        check_in: Optional[datetime] = None,
        check_out: Optional[datetime] = None,
        work_date: Optional[date] = None,
        device_id: Optional[int] = None,
        device_ref: Optional[str] = None,
        gps_lat: Optional[float] = None,
        gps_lng: Optional[float] = None,
        ip_address: Optional[str] = None,
        notes: Optional[str] = None,
        actor_id: Optional[int] = None,
    ) -> AttendanceSession:
        """Mark attendance for a user via any channel. Emits AttendanceMarked event."""
        work_date = work_date or datetime.now(timezone.utc).date()
        if channel not in ATTR_CHANNELS:
            channel = "MANUAL"

        # Device trust resolution
        device_trusted = True
        resolved_device_id = device_id
        if device_id:
            dev = db.query(AttendanceDevice).filter(AttendanceDevice.id == device_id).first()
            if dev:
                device_trusted = bool(dev.is_trusted and dev.is_active)
                device_ref = dev.serial_number
        elif device_ref:
            dev = (
                db.query(AttendanceDevice)
                .filter(
                    AttendanceDevice.org_id == org_id,
                    AttendanceDevice.serial_number == device_ref,
                )
                .first()
            )
            if dev:
                resolved_device_id = dev.id
                device_trusted = bool(dev.is_trusted and dev.is_active)

        # Policy evaluation
        shift_start = None
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.shift:
            shift_start = user.shift.start_time

        policy_eval = self.policy_service.evaluate_policy(
            db,
            org_id,
            {
                "check_in": check_in,
                "shift_start": shift_start,
                "channel": channel,
                "ip_address": ip_address,
                "device_trusted": device_trusted,
                "gps_lat": gps_lat,
                "gps_lng": gps_lng,
            },
        )

        if not policy_eval.get("channel_allowed"):
            raise ValueError(f"Channel '{channel}' is not permitted by the active attendance policy")
        if not policy_eval.get("device_trusted"):
            raise ValueError("Attendance device is not trusted / active")

        session_obj = self._get_or_create_session(db, org_id, user_id, work_date)

        is_check_in = check_in is not None
        is_check_out = check_out is not None

        if is_check_in:
            session_obj.check_in = check_in
            session_obj.channel = channel
            session_obj.device_id = resolved_device_id
            session_obj.device_ref = device_ref
            session_obj.notes = notes or session_obj.notes
            # Record IN event
            db.add(AttendanceEvent(
                org_id=org_id,
                session_id=session_obj.id,
                user_id=user_id,
                event_type="IN",
                event_time=check_in,
                channel=channel,
                device_id=resolved_device_id,
                gps_lat=gps_lat,
                gps_lng=gps_lng,
            ))

        if is_check_out:
            session_obj.check_out = check_out
            db.add(AttendanceEvent(
                org_id=org_id,
                session_id=session_obj.id,
                user_id=user_id,
                event_type="OUT",
                event_time=check_out,
                channel=channel,
                device_id=resolved_device_id,
                gps_lat=gps_lat,
                gps_lng=gps_lng,
            ))

        # Compute work hours
        if session_obj.check_in and session_obj.check_out:
            worked = (session_obj.check_out - session_obj.check_in).total_seconds() / 3600.0
            session_obj.work_hours = round(max(0.0, worked), 2)

        # Persist legacy AttendanceLog for backward compatibility
        if is_check_in:
            status_label = "late" if policy_eval.get("is_late") else "on_time"
            log = AttendanceLog(
                user_id=user_id,
                check_in=check_in,
                check_out=check_out,
                status=status_label,
                source="manual" if channel == "MANUAL" else "edge",
                geofence_pass=1 if policy_eval.get("within_geofence") else 0,
                gps_lat=gps_lat,
                gps_lng=gps_lng,
            )
            db.add(log)
            db.flush()
            session_obj.attendance_log_id = log.id

        session_obj.status = self.compute_session_status(
            db, org_id, user_id, work_date, session_obj.check_in, policy_eval
        )
        db.commit()
        db.refresh(session_obj)

        # Audit
        audit_service.record(
            actor_user_id=actor_id or user_id,
            organization_id=str(org_id),
            module="workforce_attendance",
            action="mark_attendance",
            entity_type="attendance_session",
            entity_id=str(session_obj.id),
            summary=f"Attendance marked for user {user_id} via {channel}: {session_obj.status}",
            details={
                "work_date": str(work_date),
                "channel": channel,
                "status": session_obj.status,
                "device_id": resolved_device_id,
            },
        )

        # Domain event
        event_bus.publish(
            "AttendanceMarked",
            str(org_id),
            {
                "session_id": session_obj.id,
                "user_id": user_id,
                "org_id": str(org_id),
                "work_date": str(work_date),
                "channel": channel,
                "status": session_obj.status,
            },
            actor_id=actor_id or user_id,
        )

        # Notification (only on check-in)
        if is_check_in:
            notification_service.send(
                user_id=user_id,
                organization_id=str(org_id),
                title="Attendance Recorded",
                message=f"Your attendance for {work_date} has been recorded as {session_obj.status}.",
                source_module="workforce",
                source_event="AttendanceMarked",
                source_id=str(session_obj.id),
            )

        return session_obj

    def get_sessions(
        self,
        db: Session,
        org_id: UUID,
        user_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AttendanceSession]:
        q = db.query(AttendanceSession).filter(AttendanceSession.org_id == org_id)
        if user_id is not None:
            q = q.filter(AttendanceSession.user_id == user_id)
        if start_date:
            q = q.filter(AttendanceSession.work_date >= start_date)
        if end_date:
            q = q.filter(AttendanceSession.work_date <= end_date)
        if status_filter:
            q = q.filter(AttendanceSession.status == status_filter)
        return q.order_by(AttendanceSession.work_date.desc()).offset(skip).limit(limit).all()

    def get_timeline(self, db: Session, org_id: UUID, user_id: int, limit: int = 30) -> List[AttendanceSession]:
        return (
            db.query(AttendanceSession)
            .filter(AttendanceSession.org_id == org_id, AttendanceSession.user_id == user_id)
            .order_by(AttendanceSession.work_date.desc())
            .limit(limit)
            .all()
        )

    def get_summary(
        self, db: Session, org_id: UUID, user_id: int, period: str = "month"
    ) -> Dict[str, Any]:
        """Summarize attendance sessions for a user over a period."""
        sessions = self.get_sessions(db, org_id, user_id=user_id, limit=500)
        counts: Dict[str, int] = {}
        total_hours = 0.0
        late_days = 0
        for s in sessions:
            counts[s.status] = counts.get(s.status, 0) + 1
            if s.work_hours:
                total_hours += float(s.work_hours)
            if s.status == "LATE":
                late_days += 1

        total = sum(counts.values())
        return {
            "user_id": user_id,
            "period": period,
            "total_sessions": total,
            "present_count": counts.get("PRESENT", 0),
            "late_count": counts.get("LATE", 0),
            "absent_count": counts.get("ABSENT", 0),
            "half_day_count": counts.get("HALF_DAY", 0),
            "wfh_count": counts.get("WFH", 0),
            "on_leave_count": counts.get("ON_LEAVE", 0),
            "total_work_hours": round(total_hours, 2),
            "present_rate": round(counts.get("PRESENT", 0) / max(total, 1) * 100, 1),
            "late_rate": round(counts.get("LATE", 0) / max(total, 1) * 100, 1),
            "absent_rate": round(counts.get("ABSENT", 0) / max(total, 1) * 100, 1),
        }


class AttendanceAnalyticsService:
    """Aggregate dashboards — present rate, late rate, absent rate, trend lines."""

    def dashboard(self, db: Session, org_id: UUID, days: int = 30) -> Dict[str, Any]:
        since = date.today() - timedelta(days=days)
        sessions = (
            db.query(AttendanceSession)
            .filter(AttendanceSession.org_id == org_id, AttendanceSession.work_date >= since)
            .all()
        )

        total = len(sessions)
        counts: Dict[str, int] = {}
        for s in sessions:
            counts[s.status] = counts.get(s.status, 0) + 1

        # Trend by day
        trend_map: Dict[str, Dict[str, int]] = {}
        for s in sessions:
            day_key = s.work_date.isoformat()
            bucket = trend_map.setdefault(day_key, {"PRESENT": 0, "LATE": 0, "ABSENT": 0, "total": 0})
            bucket[s.status] = bucket.get(s.status, 0) + 1
            bucket["total"] += 1

        trends = []
        for day_key in sorted(trend_map.keys()):
            b = trend_map[day_key]
            trends.append({
                "date": day_key,
                "present": b.get("PRESENT", 0),
                "late": b.get("LATE", 0),
                "absent": b.get("ABSENT", 0),
                "present_rate": round(b.get("PRESENT", 0) / max(b["total"], 1) * 100, 1),
                "late_rate": round(b.get("LATE", 0) / max(b["total"], 1) * 100, 1),
                "absent_rate": round(b.get("ABSENT", 0) / max(b["total"], 1) * 100, 1),
            })

        return {
            "org_id": str(org_id),
            "period_days": days,
            "total_sessions": total,
            "present_count": counts.get("PRESENT", 0),
            "late_count": counts.get("LATE", 0),
            "absent_count": counts.get("ABSENT", 0),
            "half_day_count": counts.get("HALF_DAY", 0),
            "holiday_count": counts.get("HOLIDAY", 0),
            "weekend_count": counts.get("WEEKEND", 0),
            "wfh_count": counts.get("WFH", 0),
            "on_leave_count": counts.get("ON_LEAVE", 0),
            "missed_punch_count": counts.get("MISSED_PUNCH", 0),
            "present_rate": round(counts.get("PRESENT", 0) / max(total, 1) * 100, 1),
            "late_rate": round(counts.get("LATE", 0) / max(total, 1) * 100, 1),
            "absent_rate": round(counts.get("ABSENT", 0) / max(total, 1) * 100, 1),
            "trends": trends,
        }


attendance_policy_service = AttendancePolicyService()
geo_attendance_service = GeoAttendanceService()
attendance_service = AttendanceService()
attendance_analytics_service = AttendanceAnalyticsService()

