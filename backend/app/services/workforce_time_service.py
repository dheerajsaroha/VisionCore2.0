"""
workforce_time_service.py — VisionCore 3.0 Workforce Time Tracking & Overtime Services

Provides:
- TimeTrackingService: clock-in/out, break events, idle time
- OvertimeService: overtime computation, approval, comp-off crediting
- BreakService: break lifecycle management

Integrates: audit_service, event_bus, notification_service, workflow_engine,
business_calendar_service (working-day calculations).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.all_models import (
    BreakLog,
    CompOffBalance,
    OvertimeRecord,
    Shift,
    TimeEntry,
    User,
)
from app.services.audit_service import audit_service
from app.services.event_bus import event_bus
from app.services.notification_service import notification_service
from app.services.workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)

BREAK_TYPES = ("LUNCH", "SHORT", "PRAYER", "OTHER")
OT_STATUSES = ("PENDING", "APPROVED", "REJECTED", "COMP_OFF_CREDITED")


def _recompute_net_work_minutes(entry: "TimeEntry") -> None:
    """Recompute net work minutes = (clock_out - clock_in) - total break minutes."""
    if entry.clock_in and entry.clock_out:
        total_mins = max(0.0, (entry.clock_out - entry.clock_in).total_seconds() / 60.0)
        break_total = int(entry.total_break_minutes or 0)
        entry.net_work_minutes = round(max(0, int(total_mins - break_total)))


class TimeTrackingService:
    """Clock-in/out and time entry lifecycle per user per day."""

    def get_or_create_entry(self, db: Session, org_id: UUID, user_id: int, work_date: date) -> TimeEntry:
        entry = db.query(TimeEntry).filter(
            TimeEntry.org_id == org_id,
            TimeEntry.user_id == user_id,
            TimeEntry.work_date == work_date,
        ).first()
        if not entry:
            entry = TimeEntry(org_id=org_id, user_id=user_id, work_date=work_date)
            db.add(entry)
            db.commit()
            db.refresh(entry)
        return entry

    def clock_in(self, db: Session, org_id: UUID, user_id: int, work_date: Optional[date] = None) -> TimeEntry:
        work_date = work_date or datetime.now(timezone.utc).date()
        entry = self.get_or_create_entry(db, org_id, user_id, work_date)
        if entry.clock_in:
            raise ValueError(f"User {user_id} already clocked in on {work_date}")

        clock_in_ts = datetime.now(timezone.utc)
        entry.clock_in = clock_in_ts
        entry.source = entry.source or "web"
        db.commit()
        db.refresh(entry)

        audit_service.record(
            actor_user_id=user_id,
            organization_id=str(org_id),
            module="workforce_time",
            action="clock_in",
            entity_type="time_entry",
            entity_id=str(entry.id),
            summary=f"User {user_id} clocked in on {work_date}",
        )
        event_bus.publish(
            "ClockedIn",
            str(org_id),
            {
                "entry_id": entry.id,
                "user_id": user_id,
                "org_id": str(org_id),
                "work_date": str(work_date),
                "clock_in": clock_in_ts.isoformat(),
            },
            actor_id=user_id,
        )
        return entry

    def clock_out(self, db: Session, org_id: UUID, user_id: int, work_date: Optional[date] = None) -> TimeEntry:
        work_date = work_date or datetime.now(timezone.utc).date()
        entry = self.get_or_create_entry(db, org_id, user_id, work_date)
        if not entry.clock_in:
            raise ValueError(f"User {user_id} has no open clock-in on {work_date}")
        if entry.clock_out:
            raise ValueError(f"User {user_id} already clocked out on {work_date}")

        clock_out_ts = datetime.now(timezone.utc)
        entry.clock_out = clock_out_ts
        _recompute_net_work_minutes(entry)
        db.commit()
        db.refresh(entry)

        audit_service.record(
            actor_user_id=user_id,
            organization_id=str(org_id),
            module="workforce_time",
            action="clock_out",
            entity_type="time_entry",
            entity_id=str(entry.id),
            summary=f"User {user_id} clocked out on {work_date}",
        )
        event_bus.publish(
            "ClockedOut",
            str(org_id),
            {
                "entry_id": entry.id,
                "user_id": user_id,
                "org_id": str(org_id),
                "work_date": str(work_date),
                "clock_out": clock_out_ts.isoformat(),
                "net_work_minutes": entry.net_work_minutes,
            },
            actor_id=user_id,
        )
        return entry

    def list_entries(
        self, db: Session, org_id: UUID, user_id: Optional[int] = None, from_date: Optional[date] = None, to_date: Optional[date] = None
    ) -> List[TimeEntry]:
        q = db.query(TimeEntry).filter(TimeEntry.org_id == org_id)
        if user_id is not None:
            q = q.filter(TimeEntry.user_id == user_id)
        if from_date:
            q = q.filter(TimeEntry.work_date >= from_date)
        if to_date:
            q = q.filter(TimeEntry.work_date <= to_date)
        return q.order_by(TimeEntry.work_date.desc()).all()


class BreakService:
    """Break lifecycle management — start/end events by type."""

    def start_break(self, db: Session, org_id: UUID, user_id: int, work_date: Optional[date] = None, break_type: str = "SHORT") -> BreakLog:
        work_date = work_date or datetime.now(timezone.utc).date()
        if break_type not in BREAK_TYPES:
            break_type = "SHORT"

        entry = db.query(TimeEntry).filter(
            TimeEntry.org_id == org_id, TimeEntry.user_id == user_id, TimeEntry.work_date == work_date
        ).first()
        if not entry:
            raise ValueError("User has no time entry for this date — clock in first")

        open_break = db.query(BreakLog).filter(
            BreakLog.time_entry_id == entry.id, BreakLog.end_time.is_(None)
        ).first()
        if open_break:
            raise ValueError("A break is already active for this user")

        start_ts = datetime.now(timezone.utc)
        log = BreakLog(
            org_id=org_id,
            time_entry_id=entry.id,
            user_id=user_id,
            break_type=break_type,
            start_time=start_ts,
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        event_bus.publish(
            "BreakStarted",
            str(org_id),
            {
                "break_id": log.id,
                "user_id": user_id,
                "org_id": str(org_id),
                "break_type": break_type,
                "start_time": start_ts.isoformat(),
            },
            actor_id=user_id,
        )
        return log

    def end_break(self, db: Session, org_id: UUID, user_id: int, break_id: int) -> BreakLog:
        log = db.query(BreakLog).filter(BreakLog.id == break_id, BreakLog.org_id == org_id).first()
        if not log:
            raise ValueError(f"Break log {break_id} not found")
        if log.end_time:
            raise ValueError("Break already ended")

        end_ts = datetime.now(timezone.utc)
        log.end_time = end_ts
        start_ts = log.start_time if log.start_time is not None else end_ts
        duration_mins = (end_ts - start_ts).total_seconds() / 60.0
        log.duration_minutes = round(max(0, int(duration_mins)))
        db.commit()

        # Update time entry total break minutes
        entry = db.query(TimeEntry).filter(TimeEntry.id == log.time_entry_id).first()
        if entry:
            entry.total_break_minutes = (entry.total_break_minutes or 0) + log.duration_minutes
            _recompute_net_work_minutes(entry)
            db.commit()
            db.refresh(entry)

        db.refresh(log)

        event_bus.publish(
            "BreakEnded",
            str(org_id),
            {
                "break_id": log.id,
                "user_id": user_id,
                "org_id": str(org_id),
                "duration_minutes": log.duration_minutes,
            },
            actor_id=user_id,
        )
        return log

    def list_breaks(self, db: Session, org_id: UUID, time_entry_id: int) -> List[BreakLog]:
        return (
            db.query(BreakLog)
            .filter(BreakLog.org_id == org_id, BreakLog.time_entry_id == time_entry_id)
            .order_by(BreakLog.start_time)
            .all()
        )


class OvertimeService:
    """Overtime computation, approval, and comp-off crediting."""

    def compute_overtime(
        self,
        db: Session,
        org_id: UUID,
        user_id: int,
        work_date: date,
        *,
        entry_id: Optional[int] = None,
        approved_by: Optional[int] = None,
        rate_multiplier: float = 1.50,
    ) -> OvertimeRecord:
        """Compute overtime hours from a time entry vs the user's assigned shift."""
        user = db.query(User).filter(User.id == user_id).first()
        shift: Optional[Shift] = user.shift if user else None
        if not shift:
            raise ValueError("User has no shift assigned — overtime cannot be computed")

        entry = None
        if entry_id:
            entry = db.query(TimeEntry).filter(
                TimeEntry.id == entry_id, TimeEntry.org_id == org_id, TimeEntry.user_id == user_id
            ).first()
        else:
            entry = db.query(TimeEntry).filter(
                TimeEntry.org_id == org_id,
                TimeEntry.user_id == user_id,
                TimeEntry.work_date == work_date,
            ).first()
        if not entry or not entry.net_work_minutes:
            raise ValueError(f"No completed time entry found for user {user_id} on {work_date}")

        # Scheduled shift hours
        start_min = shift.start_time.hour * 60 + shift.start_time.minute
        end_min = shift.end_time.hour * 60 + shift.end_time.minute
        scheduled_hours = (end_min - start_min) / 60.0 if end_min >= start_min else (end_min + 24 * 60 - start_min) / 60.0

        worked_minutes = int(entry.net_work_minutes or 0)
        worked_hours = round(worked_minutes / 60.0, 2)
        overtime_minutes = max(0, worked_minutes - int(round(scheduled_hours * 60)))
        overtime_hours = max(0.0, round(worked_hours - scheduled_hours, 2))

        ot = OvertimeRecord(
            org_id=org_id,
            user_id=user_id,
            work_date=work_date,
            overtime_minutes=overtime_minutes,
            overtime_hours=overtime_hours,
            rate_multiplier=rate_multiplier,
            status="PENDING",
            approver_user_id=approved_by,
        )
        db.add(ot)
        db.commit()
        db.refresh(ot)

        # Workflow submission for approval
        if overtime_hours > 0:
            try:
                wf_req = WorkflowEngine.submit_request(
                    db=db,
                    organization_id=org_id,
                    requester_user_id=user_id,
                    entity_type="overtime",
                    entity_id=str(ot.id),
                    payload={
                        "overtime_hours": overtime_hours,
                        "work_date": str(work_date),
                        "scheduled_hours": scheduled_hours,
                        "actual_hours": worked_hours,
                    },
                    title=f"Overtime #{ot.id} ({overtime_hours}h)",
                )
                ot.workflow_request_id = wf_req.id
                db.commit()
                db.refresh(ot)
            except Exception as exc:
                logger.warning(f"Workflow submission for overtime failed: {exc}")

        audit_service.record(
            actor_user_id=user_id,
            organization_id=str(org_id),
            module="workforce_time",
            action="compute_overtime",
            entity_type="overtime_record",
            entity_id=str(ot.id),
            summary=f"Overtime computed for user {user_id}: {overtime_hours}h on {work_date}",
            details={"scheduled_hours": scheduled_hours, "actual_hours": worked_hours, "overtime_hours": overtime_hours},
        )
        event_bus.publish(
            "OvertimeComputed",
            str(org_id),
            {
                "overtime_id": ot.id,
                "user_id": user_id,
                "org_id": str(org_id),
                "work_date": str(work_date),
                "overtime_hours": overtime_hours,
            },
            actor_id=user_id,
        )
        return ot

    def approve_overtime(self, db: Session, org_id: UUID, overtime_id: int, approver_user_id: int, note: Optional[str] = None) -> OvertimeRecord:
        ot = db.query(OvertimeRecord).filter(OvertimeRecord.id == overtime_id, OvertimeRecord.org_id == org_id).first()
        if not ot:
            raise ValueError(f"Overtime record {overtime_id} not found")
        if ot.status != "PENDING":
            raise ValueError(f"Cannot approve overtime in '{ot.status}' state")

        ot.status = "APPROVED"
        ot.approver_user_id = approver_user_id
        ot.approval_note = note
        db.commit()
        db.refresh(ot)

        audit_service.record(
            actor_user_id=approver_user_id,
            organization_id=str(org_id),
            module="workforce_time",
            action="approve_overtime",
            entity_type="overtime_record",
            entity_id=str(ot.id),
            summary=f"Overtime #{ot.id} approved ({ot.overtime_hours}h)",
        )
        event_bus.publish(
            "OvertimeApproved",
            str(org_id),
            {
                "overtime_id": ot.id,
                "user_id": ot.user_id,
                "org_id": str(org_id),
                "overtime_hours": ot.overtime_hours,
            },
            actor_id=approver_user_id,
        )
        notification_service.send(
            user_id=ot.user_id,
            organization_id=str(org_id),
            title="Overtime Approved",
            message=f"Your overtime of {ot.overtime_hours}h on {ot.work_date} has been approved.",
            source_module="workforce",
            source_event="OvertimeApproved",
            source_id=str(ot.id),
        )
        return ot

    def credit_comp_off(self, db: Session, org_id: UUID, overtime_id: int, actor_user_id: int, multiplier: float = 1.0) -> CompOffBalance:
        """Credit approved overtime minutes into the user's comp-off ledger."""
        ot = db.query(OvertimeRecord).filter(OvertimeRecord.id == overtime_id, OvertimeRecord.org_id == org_id).first()
        if not ot:
            raise ValueError(f"Overtime record {overtime_id} not found")
        if ot.status != "APPROVED":
            raise ValueError("Only approved overtime can be credited as comp-off")

        year = datetime.now(timezone.utc).year
        balance = db.query(CompOffBalance).filter(
            CompOffBalance.user_id == ot.user_id,
            CompOffBalance.org_id == org_id,
            CompOffBalance.year == year,
        ).first()
        if not balance:
            balance = CompOffBalance(
                org_id=org_id,
                user_id=ot.user_id,
                year=year,
                entitled_minutes=0,
                used_minutes=0,
                pending_minutes=0,
                adjusted_minutes=0,
            )
            db.add(balance)

        credit_minutes = (
            max(1, round(int(ot.overtime_minutes) * multiplier))
            if ot.overtime_minutes
            else max(1, round(float(ot.overtime_hours) * 60 * multiplier))
        )
        balance.entitled_minutes += credit_minutes
        ot.status = "COMP_OFF_CREDITED"
        ot.comp_off_balance_id = balance.id if balance.id else None
        db.commit()
        db.refresh(balance)
        db.refresh(ot)
        db.flush()

        event_bus.publish(
            "CompOffCredited",
            str(org_id),
            {
                "overtime_id": ot.id,
                "user_id": ot.user_id,
                "org_id": str(org_id),
                "credit_hours": round(credit_minutes / 60.0, 2),
                "balance_hours": round(balance.available_minutes / 60.0, 2),
            },
            actor_id=actor_user_id,
        )
        return balance

    def list_overtime(
        self, db: Session, org_id: UUID, user_id: Optional[int] = None, status_filter: Optional[str] = None
    ) -> List[OvertimeRecord]:
        q = db.query(OvertimeRecord).filter(OvertimeRecord.org_id == org_id)
        if user_id is not None:
            q = q.filter(OvertimeRecord.user_id == user_id)
        if status_filter:
            q = q.filter(OvertimeRecord.status == status_filter)
        return q.order_by(OvertimeRecord.work_date.desc()).all()


time_tracking_service = TimeTrackingService()
break_service = BreakService()
overtime_service = OvertimeService()

