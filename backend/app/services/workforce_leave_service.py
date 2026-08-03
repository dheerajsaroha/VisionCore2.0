"""
workforce_leave_service.py — VisionCore 3.0 Workforce Leave & Holiday Services

Provides:
- LeaveService: apply, cancel, approve/reject with balance deduction
- HolidayService: holiday calendar CRUD, holiday type management
- LeaveAccrualService: periodic accrual jobs (monthly/quarterly/yearly)
- LeaveEncashmentService: encashment calculations

Integrates: audit_service, event_bus, notification_service, workflow_engine,
business_calendar_service (working-day calculations).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.all_models import (
    HolidayCalendar,
    HolidayEntry,
    LeaveBalance,
    LeavePolicy,
    LeaveRequest,
    LeaveType,
    User,
)
from app.services.audit_service import audit_service
from app.services.business_calendar_service import business_calendar_service
from app.services.event_bus import event_bus
from app.services.notification_service import notification_service
from app.services.workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)

LEAVE_STATUSES = ("PENDING", "APPROVED", "REJECTED", "CANCELLED")


class LeaveService:
    """Apply, cancel, approve/reject leave with balance deduction."""

    def apply_leave(
        self,
        db: Session,
        org_id: UUID,
        user_id: int,
        leave_type_id: int,
        start_date: date,
        end_date: date,
        *,
        reason: Optional[str] = None,
        is_half_day: bool = False,
        half_day_period: Optional[str] = None,
    ) -> LeaveRequest:
        """Create a leave request, reserve balance, and submit to workflow."""
        leave_type = db.query(LeaveType).filter(
            LeaveType.id == leave_type_id, LeaveType.organization_id == org_id
        ).first()
        if not leave_type:
            raise ValueError(f"Leave type {leave_type_id} not found for org")
        if not leave_type.is_active:
            raise ValueError(f"Leave type '{leave_type.code}' is inactive")

        total_days = self._compute_leave_days(db, org_id, start_date, end_date)
        if total_days <= 0:
            raise ValueError("Leave duration spans no working days")
        if total_days > float(leave_type.max_days_per_request):
            raise ValueError(
                f"Request exceeds max single request limit of {leave_type.max_days_per_request} days"
            )

        # Verify balance availability
        balance = self._get_or_create_balance(db, org_id, user_id, leave_type)
        if balance.available_days < total_days:
            raise ValueError(
                f"Insufficient leave balance. Available: {balance.available_days} days, Requested: {total_days} days"
            )

        request = LeaveRequest(
            organization_id=org_id,
            user_id=user_id,
            leave_type_id=leave_type_id,
            start_date=datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc),
            end_date=datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc),
            total_days=total_days,
            is_half_day=is_half_day,
            half_day_period=half_day_period,
            reason=reason,
            status="pending",
        )
        db.add(request)
        db.flush()

        # Reserve pending days
        balance.pending_days += total_days
        db.add(balance)
        db.commit()
        db.refresh(request)

        # Workflow submission
        try:
            wf_req = WorkflowEngine.submit_request(
                db=db,
                organization_id=org_id,
                requester_user_id=user_id,
                entity_type="leave",
                entity_id=str(request.id),
                payload={
                    "leave_type": leave_type.code,
                    "total_days": total_days,
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                },
                title=f"Leave Request #{request.id} ({leave_type.code})",
            )
            request.workflow_request_id = wf_req.id
            db.commit()
            db.refresh(request)
        except Exception as exc:
            logger.warning(f"Workflow submission for leave request failed: {exc}")

        # Audit
        audit_service.record(
            actor_user_id=user_id,
            organization_id=str(org_id),
            module="workforce_leave",
            action="apply_leave",
            entity_type="leave_request",
            entity_id=str(request.id),
            summary=f"Leave requested for {leave_type.name} ({total_days} days)",
            details={
                "leave_type_id": leave_type_id,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "total_days": total_days,
            },
        )

        # Event & notification
        event_bus.publish(
            "LeaveRequested",
            str(org_id),
            {
                "request_id": request.id,
                "user_id": user_id,
                "org_id": str(org_id),
                "leave_type": leave_type.code,
                "total_days": total_days,
                "start_date": str(start_date),
                "end_date": str(end_date),
            },
            actor_id=user_id,
        )
        notification_service.send(
            user_id=user_id,
            organization_id=str(org_id),
            title="Leave Request Submitted",
            message=f"Your {leave_type.name} request ({total_days} days) has been submitted.",
            source_module="workforce",
            source_event="LeaveRequested",
            source_id=str(request.id),
        )
        return request

    def approve_leave(
        self, db: Session, org_id: UUID, request_id: int, approver_user_id: int, note: Optional[str] = None
    ) -> LeaveRequest:
        """Approve a pending leave request and commit balance deduction."""
        request = self._get_request(db, org_id, request_id)
        if request.status != "pending":
            raise ValueError(f"Cannot approve request in '{request.status}' state")

        request.status = "approved"
        request.approver_user_id = approver_user_id
        request.approver_note = note
        request.approved_at = datetime.now(timezone.utc)

        # A relationship may be unloaded when a request is obtained through a
        # repository/query path that does not eager-load LeaveType. The foreign
        # key remains the authoritative reference, so resolve it explicitly.
        leave_type = request.leave_type
        if leave_type is None:
            leave_type = db.query(LeaveType).filter(
                LeaveType.id == request.leave_type_id,
                LeaveType.organization_id == org_id,
            ).first()
        if leave_type is None:
            raise ValueError(f"Leave type {request.leave_type_id} not found for request {request.id}")

        balance = self._get_or_create_balance(db, org_id, request.user_id, leave_type)
        balance.pending_days = max(0.0, balance.pending_days - request.total_days)
        balance.used_days += request.total_days
        db.add(balance)
        db.commit()
        db.refresh(request)

        audit_service.record(
            actor_user_id=approver_user_id,
            organization_id=str(org_id),
            module="workforce_leave",
            action="approve_leave",
            entity_type="leave_request",
            entity_id=str(request.id),
            summary=f"Leave request #{request.id} approved",
            details={"total_days": request.total_days},
        )
        event_bus.publish(
            "LeaveApproved",
            str(org_id),
            {
                "request_id": request.id,
                "user_id": request.user_id,
                "org_id": str(org_id),
                "total_days": request.total_days,
            },
            actor_id=approver_user_id,
        )
        notification_service.send(
            user_id=request.user_id,
            organization_id=str(org_id),
            title="Leave Approved",
            message=f"Your leave request #{request.id} has been approved.",
            source_module="workforce",
            source_event="LeaveApproved",
            source_id=str(request.id),
        )
        return request

    def reject_leave(
        self, db: Session, org_id: UUID, request_id: int, approver_user_id: int, note: Optional[str] = None
    ) -> LeaveRequest:
        """Reject a pending leave request and release reserved balance."""
        request = self._get_request(db, org_id, request_id)
        if request.status != "pending":
            raise ValueError(f"Cannot reject request in '{request.status}' state")

        request.status = "rejected"
        request.approver_user_id = approver_user_id
        request.approver_note = note

        balance = self._get_or_create_balance(db, org_id, request.user_id, request.leave_type)
        balance.pending_days = max(0.0, balance.pending_days - request.total_days)
        db.add(balance)
        db.commit()
        db.refresh(request)

        audit_service.record(
            actor_user_id=approver_user_id,
            organization_id=str(org_id),
            module="workforce_leave",
            action="reject_leave",
            entity_type="leave_request",
            entity_id=str(request.id),
            summary=f"Leave request #{request.id} rejected",
        )
        event_bus.publish(
            "LeaveRejected",
            str(org_id),
            {
                "request_id": request.id,
                "user_id": request.user_id,
                "org_id": str(org_id),
            },
            actor_id=approver_user_id,
        )
        return request

    def cancel_leave(self, db: Session, org_id: UUID, request_id: int, cancelled_by_user_id: int) -> LeaveRequest:
        """Cancel a leave request and restore balance."""
        request = self._get_request(db, org_id, request_id)
        if request.status in ("cancelled", "rejected"):
            raise ValueError(f"Request is already {request.status}")

        previous_status = request.status
        request.status = "cancelled"

        balance = self._get_or_create_balance(db, org_id, request.user_id, request.leave_type)
        if previous_status == "pending":
            balance.pending_days = max(0.0, balance.pending_days - request.total_days)
        elif previous_status == "approved":
            balance.used_days = max(0.0, balance.used_days - request.total_days)
        db.add(balance)
        db.commit()
        db.refresh(request)

        audit_service.record(
            actor_user_id=cancelled_by_user_id,
            organization_id=str(org_id),
            module="workforce_leave",
            action="cancel_leave",
            entity_type="leave_request",
            entity_id=str(request.id),
            summary=f"Leave request #{request.id} cancelled",
        )
        return request

    def get_balances(self, db: Session, org_id: UUID, user_id: int) -> List[Dict[str, Any]]:
        """Return per-type leave balances for a user."""
        balances = (
            db.query(LeaveBalance)
            .filter(LeaveBalance.organization_id == org_id, LeaveBalance.user_id == user_id)
            .all()
        )
        result = []
        for b in balances:
            result.append({
                "id": b.id,
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
            })
        return result

    def list_requests(
        self,
        db: Session,
        org_id: UUID,
        user_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[LeaveRequest]:
        q = db.query(LeaveRequest).filter(LeaveRequest.organization_id == org_id)
        if user_id is not None:
            q = q.filter(LeaveRequest.user_id == user_id)
        if status_filter:
            q = q.filter(LeaveRequest.status == status_filter)
        return q.order_by(LeaveRequest.created_at.desc()).offset(skip).limit(limit).all()

    def _get_request(self, db: Session, org_id: UUID, request_id: int) -> LeaveRequest:
        req = db.query(LeaveRequest).filter(
            LeaveRequest.id == request_id, LeaveRequest.organization_id == org_id
        ).first()
        if not req:
            raise ValueError(f"Leave request {request_id} not found")
        return req

    def _get_or_create_balance(self, db: Session, org_id: UUID, user_id: int, leave_type: LeaveType) -> LeaveBalance:
        balance = db.query(LeaveBalance).filter(
            LeaveBalance.user_id == user_id,
            LeaveBalance.leave_type_id == leave_type.id,
        ).first()
        if not balance:
            balance = LeaveBalance(
                user_id=user_id,
                organization_id=org_id,
                leave_type_id=leave_type.id,
                year=datetime.now(timezone.utc).year,
                entitled_days=float(leave_type.max_days_per_year),
                used_days=0.0,
                pending_days=0.0,
                carried_forward_days=0.0,
                adjusted_days=0.0,
            )
            db.add(balance)
            db.commit()
            db.refresh(balance)
        return balance

    def _compute_leave_days(self, db: Session, org_id: UUID, start_date: date, end_date: date) -> float:
        """Count working days in [start, end] via business calendar."""
        if start_date > end_date:
            raise ValueError("start_date must be before end_date")
        count = 0
        cursor = start_date
        while cursor <= end_date:
            is_working = business_calendar_service.is_working_day(cursor, str(org_id)) \
                if hasattr(business_calendar_service, "is_working_day") else cursor.weekday() < 5
            if is_working:
                count += 1
            cursor += timedelta(days=1)
        return float(count)


class HolidayService:
    """Holiday calendar CRUD and holiday type management."""

    def create_calendar(self, db: Session, org_id: UUID, data: Dict[str, Any]) -> HolidayCalendar:
        cal = HolidayCalendar(org_id=org_id, **data)
        db.add(cal)
        db.commit()
        db.refresh(cal)
        return cal

    def list_calendars(self, db: Session, org_id: UUID) -> List[HolidayCalendar]:
        return (
            db.query(HolidayCalendar)
            .filter(HolidayCalendar.org_id == org_id)
            .order_by(HolidayCalendar.name)
            .all()
        )

    def add_entry(self, db: Session, org_id: UUID, calendar_id: int, data: Dict[str, Any]) -> HolidayEntry:
        entry = HolidayEntry(org_id=org_id, calendar_id=calendar_id, **data)
        db.add(entry)
        db.commit()
        db.refresh(entry)

        # Sync into business calendar service for working-day computations
        try:
            from app.services.business_calendar_service import HolidayEntry as BcHoliday, DayType
            dt = datetime.fromisoformat(str(entry.holiday_date)).date()
            business_calendar_service.add_holiday(
                str(org_id),
                BcHoliday(dt.isoformat(), entry.name, DayType.HOLIDAY),
            )
        except Exception as exc:
            logger.warning(f"Failed to sync holiday into business calendar: {exc}")

        audit_service.record(
            organization_id=str(org_id),
            module="workforce_leave",
            action="add_holiday",
            entity_type="holiday_entry",
            entity_id=str(entry.id),
            summary=f"Holiday '{entry.name}' added on {entry.holiday_date}",
        )
        return entry

    def list_entries(
        self, db: Session, org_id: UUID, calendar_id: Optional[int] = None, year: Optional[int] = None
    ) -> List[HolidayEntry]:
        q = db.query(HolidayEntry).filter(HolidayEntry.org_id == org_id)
        if calendar_id is not None:
            q = q.filter(HolidayEntry.calendar_id == calendar_id)
        entries = q.order_by(HolidayEntry.holiday_date).all()
        if year:
            entries = [e for e in entries if e.holiday_date.year == year]
        return entries

    def delete_entry(self, db: Session, org_id: UUID, entry_id: int) -> bool:
        entry = db.query(HolidayEntry).filter(
            HolidayEntry.id == entry_id, HolidayEntry.org_id == org_id
        ).first()
        if not entry:
            return False
        db.delete(entry)
        db.commit()
        return True


class LeaveAccrualService:
    """Periodic leave accrual jobs — monthly/quarterly/yearly."""

    def run_accrual(
        self, db: Session, org_id: UUID, frequency: str = "monthly", year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Accrue leave balance for all users per active leave types."""
        year = year or datetime.now(timezone.utc).year
        leave_types = (
            db.query(LeaveType)
            .filter(LeaveType.organization_id == org_id, LeaveType.is_active.is_(True))
            .all()
        )
        users = db.query(User).filter(User.org_id == org_id, User.is_deleted == 0).all()

        accrued = 0
        for leave_type in leave_types:
            if leave_type.max_days_per_year <= 0:
                continue
            for user in users:
                balance = db.query(LeaveBalance).filter(
                    LeaveBalance.user_id == user.id,
                    LeaveBalance.leave_type_id == leave_type.id,
                    LeaveBalance.year == year,
                ).first()
                if not balance:
                    balance = LeaveBalance(
                        user_id=user.id,
                        organization_id=org_id,
                        leave_type_id=leave_type.id,
                        year=year,
                        entitled_days=0.0,
                        used_days=0.0,
                        pending_days=0.0,
                        carried_forward_days=0.0,
                        adjusted_days=0.0,
                    )
                    db.add(balance)

                if frequency == "yearly":
                    increment = float(leave_type.max_days_per_year)
                elif frequency == "quarterly":
                    increment = float(leave_type.max_days_per_year) / 4.0
                else:  # monthly
                    increment = float(leave_type.max_days_per_year) / 12.0

                balance.entitled_days += round(increment, 2)
                accrued += 1
                db.add(balance)

        db.commit()

        event_bus.publish(
            "LeaveAccrued",
            str(org_id),
            {
                "org_id": str(org_id),
                "frequency": frequency,
                "year": year,
                "balance_records_updated": accrued,
            },
        )
        return {
            "org_id": str(org_id),
            "frequency": frequency,
            "year": year,
            "balance_records_updated": accrued,
        }


class LeaveEncashmentService:
    """Encashment calculations for encashable paid leave."""

    def calculate_encashment(
        self,
        db: Session,
        org_id: UUID,
        user_id: int,
        leave_type_id: int,
        days_to_encash: float,
        daily_rate: float,
    ) -> Dict[str, Any]:
        """Compute encashment value for unused leave days."""
        balance = db.query(LeaveBalance).filter(
            LeaveBalance.user_id == user_id,
            LeaveBalance.leave_type_id == leave_type_id,
            LeaveBalance.organization_id == org_id,
        ).first()
        if not balance:
            raise ValueError("Leave balance not found for user/type")

        leave_type = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
        encashable = min(days_to_encash, balance.available_days)
        if leave_type and not leave_type.is_paid:
            raise ValueError("Unpaid leave types cannot be encashed")

        amount = round(encashable * daily_rate, 2)
        return {
            "user_id": user_id,
            "leave_type_id": leave_type_id,
            "leave_type_name": leave_type.name if leave_type else None,
            "available_days": balance.available_days,
            "days_to_encash": days_to_encash,
            "days_encashable": encashable,
            "daily_rate": daily_rate,
            "encashment_amount": amount,
        }


leave_service = LeaveService()
holiday_service = HolidayService()
leave_accrual_service = LeaveAccrualService()
leave_encashment_service = LeaveEncashmentService()
