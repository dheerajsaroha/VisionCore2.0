"""
workforce_shift_service.py — VisionCore 3.0 Workforce Shift & Roster Services

Provides:
- ShiftService: CRUD for shifts and shift templates
- RosterService: roster creation, publishing, roster entry generation
- ShiftSwapService: swap request lifecycle with workflow integration

Integrates: audit_service, event_bus, notification_service, workflow_engine.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.all_models import (
    Roster,
    RosterEntry,
    Shift,
    ShiftAssignment,
    ShiftSwapRequest,
    ShiftTemplate,
    User,
)
from app.services.audit_service import audit_service
from app.services.event_bus import event_bus
from app.services.notification_service import notification_service
from app.services.workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)


class ShiftService:
    """CRUD operations for shifts (legacy) and shift templates."""

    def create_template(self, db: Session, org_id: UUID, data: Dict[str, Any]) -> ShiftTemplate:
        tpl = ShiftTemplate(org_id=org_id, **data)
        db.add(tpl)
        db.commit()
        db.refresh(tpl)
        return tpl

    def list_templates(self, db: Session, org_id: UUID, active_only: bool = True) -> List[ShiftTemplate]:
        q = db.query(ShiftTemplate).filter(ShiftTemplate.org_id == org_id)
        if active_only:
            q = q.filter(ShiftTemplate.is_active.is_(True))
        return q.order_by(ShiftTemplate.name).all()

    def get_template(self, db: Session, template_id: int) -> Optional[ShiftTemplate]:
        return db.query(ShiftTemplate).filter(ShiftTemplate.id == template_id).first()

    def update_template(self, db: Session, tpl: ShiftTemplate, updates: Dict[str, Any]) -> ShiftTemplate:
        for field, value in updates.items():
            if value is not None and hasattr(tpl, field):
                setattr(tpl, field, value)
        db.commit()
        db.refresh(tpl)
        return tpl

    def create_legacy_shift(self, db: Session, org_id: UUID, data: Dict[str, Any]) -> Shift:
        shift = Shift(
            org_id=org_id,
            shift_name=data["shift_name"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            grace_period_mins=data.get("grace_period_mins", 5),
            buffer_mins=data.get("buffer_mins", 15),
            break_deduct_mins=data.get("break_deduct_mins", 0),
            is_deleted=0,
        )
        db.add(shift)
        db.commit()
        db.refresh(shift)
        return shift

    def list_shifts(self, db: Session, org_id: UUID) -> List[Shift]:
        return (
            db.query(Shift)
            .filter(Shift.org_id == org_id, Shift.is_deleted == 0)
            .order_by(Shift.shift_name)
            .all()
        )

    def assign_shift(self, db: Session, org_id: UUID, data: Dict[str, Any]) -> ShiftAssignment:
        """Create a shift mapping for a user over a date range."""
        assignment = ShiftAssignment(org_id=org_id, **data)
        db.add(assignment)
        db.commit()
        db.refresh(assignment)

        audit_service.record(
            organization_id=str(org_id),
            module="workforce_shift",
            action="assign_shift",
            entity_type="shift_assignment",
            entity_id=str(assignment.id),
            summary=f"Shift assigned to user {assignment.user_id} from {assignment.start_date} to {assignment.end_date}",
            details={"user_id": assignment.user_id, "shift_id": assignment.shift_id},
        )
        return assignment

    def list_assignments(
        self, db: Session, org_id: UUID, user_id: Optional[int] = None, active_only: bool = True
    ) -> List[ShiftAssignment]:
        q = db.query(ShiftAssignment).filter(ShiftAssignment.org_id == org_id)
        if user_id is not None:
            q = q.filter(ShiftAssignment.user_id == user_id)
        if active_only:
            q = q.filter(ShiftAssignment.is_active.is_(True))
        return q.order_by(ShiftAssignment.start_date.desc()).all()


class RosterService:
    """Roster creation, publishing, and roster entry generation."""

    def create_roster(self, db: Session, org_id: UUID, data: Dict[str, Any]) -> Roster:
        roster = Roster(org_id=org_id, **data)
        db.add(roster)
        db.commit()
        db.refresh(roster)
        return roster

    def generate_entries(
        self,
        db: Session,
        org_id: UUID,
        roster: Roster,
        assignments: Optional[List[ShiftAssignment]] = None,
    ) -> List[RosterEntry]:
        """Generate per-day roster entries from active shift assignments within the roster window."""
        assignments = assignments or self._active_assignments_in_range(db, org_id, roster)
        entries: List[RosterEntry] = []

        cursor = date.fromisoformat(str(roster.start_date))
        end = date.fromisoformat(str(roster.end_date))
        while cursor <= end:
            for a in assignments:
                if cursor < date.fromisoformat(str(a.start_date)) or cursor > date.fromisoformat(str(a.end_date)):
                    continue
                entry = RosterEntry(
                    org_id=org_id,
                    roster_id=roster.id,
                    user_id=a.user_id,
                    work_date=cursor,
                    shift_template_id=a.shift_template_id,
                    shift_id=a.shift_id,
                )
                if a.shift_template:
                    entry.start_time = a.shift_template.start_time
                    entry.end_time = a.shift_template.end_time
                elif a.shift:
                    entry.start_time = a.shift.start_time
                    entry.end_time = a.shift.end_time
                db.add(entry)
                entries.append(entry)
            cursor += timedelta(days=1)

        db.commit()
        for e in entries:
            db.refresh(e)
        return entries

    def _active_assignments_in_range(self, db: Session, org_id: UUID, roster: Roster) -> List[ShiftAssignment]:
        return (
            db.query(ShiftAssignment)
            .filter(
                ShiftAssignment.org_id == org_id,
                ShiftAssignment.is_active.is_(True),
                ShiftAssignment.start_date <= roster.end_date,
                ShiftAssignment.end_date >= roster.start_date,
            )
            .all()
        )

    def publish_roster(
        self,
        db: Session,
        org_id: UUID,
        roster_id: int,
        published_by_user_id: int,
        auto_generate: bool = True,
    ) -> Roster:
        """Publish a roster and generate entries if not yet created."""
        roster = db.query(Roster).filter(Roster.id == roster_id, Roster.org_id == org_id).first()
        if not roster:
            raise ValueError(f"Roster {roster_id} not found")

        if auto_generate and not roster.entries:
            self.generate_entries(db, org_id, roster)

        roster.status = "PUBLISHED"
        roster.published_by_user_id = published_by_user_id
        roster.published_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(roster)

        audit_service.record(
            actor_user_id=published_by_user_id,
            organization_id=str(org_id),
            module="workforce_shift",
            action="publish_roster",
            entity_type="roster",
            entity_id=str(roster.id),
            summary=f"Roster '{roster.title}' published for {roster.start_date} → {roster.end_date}",
        )

        event_bus.publish(
            "RosterPublished",
            str(org_id),
            {
                "roster_id": roster.id,
                "org_id": str(org_id),
                "title": roster.title,
                "start_date": str(roster.start_date),
                "end_date": str(roster.end_date),
            },
            actor_id=published_by_user_id,
        )

        # Notify affected employees
        employee_ids = {e.user_id for e in roster.entries}
        for uid in employee_ids:
            notification_service.send(
                user_id=uid,
                organization_id=str(org_id),
                title="Roster Published",
                message=f"Your roster '{roster.title}' has been published and is now available to view.",
                source_module="workforce",
                source_event="RosterPublished",
                source_id=str(roster.id),
            )

        return roster

    def list_rosters(
        self, db: Session, org_id: UUID, dept_id: Optional[int] = None, status_filter: Optional[str] = None
    ) -> List[Roster]:
        q = db.query(Roster).filter(Roster.org_id == org_id)
        if dept_id is not None:
            q = q.filter(Roster.dept_id == dept_id)
        if status_filter:
            q = q.filter(Roster.status == status_filter)
        return q.order_by(Roster.start_date.desc()).all()

    def list_entries(self, db: Session, org_id: UUID, roster_id: int) -> List[RosterEntry]:
        return (
            db.query(RosterEntry)
            .filter(RosterEntry.org_id == org_id, RosterEntry.roster_id == roster_id)
            .order_by(RosterEntry.work_date, RosterEntry.user_id)
            .all()
        )


class ShiftSwapService:
    """Shift swap request lifecycle with workflow integration."""

    def create_swap_request(
        self,
        db: Session,
        org_id: UUID,
        requester_user_id: int,
        data: Dict[str, Any],
    ) -> ShiftSwapRequest:
        swap = ShiftSwapRequest(
            org_id=org_id,
            requester_user_id=requester_user_id,
            target_user_id=data.get("target_user_id"),
            shift_assignment_id=data.get("shift_assignment_id"),
            swap_date=data["swap_date"],
            requested_shift_template_id=data.get("requested_shift_template_id"),
            reason=data.get("reason"),
            status="PENDING",
        )
        db.add(swap)
        db.commit()
        db.refresh(swap)

        # Submit to workflow engine
        try:
            wf_req = WorkflowEngine.submit_request(
                db=db,
                organization_id=org_id,
                requester_user_id=requester_user_id,
                entity_type="shift_swap",
                entity_id=str(swap.id),
                payload={"swap_date": str(swap.swap_date)},
                title=f"Shift Swap Request #{swap.id}",
            )
            swap.workflow_request_id = wf_req.id
            db.commit()
            db.refresh(swap)
        except Exception as exc:
            logger.warning(f"Workflow submission for shift swap failed: {exc}")

        event_bus.publish(
            "ShiftSwapRequested",
            str(org_id),
            {
                "swap_id": swap.id,
                "org_id": str(org_id),
                "requester_user_id": requester_user_id,
                "swap_date": str(swap.swap_date),
            },
            actor_id=requester_user_id,
        )
        return swap

    def list_swap_requests(
        self, db: Session, org_id: UUID, status_filter: Optional[str] = None, user_id: Optional[int] = None
    ) -> List[ShiftSwapRequest]:
        q = db.query(ShiftSwapRequest).filter(ShiftSwapRequest.org_id == org_id)
        if status_filter:
            q = q.filter(ShiftSwapRequest.status == status_filter)
        if user_id is not None:
            q = q.filter(
                (ShiftSwapRequest.requester_user_id == user_id)
                | (ShiftSwapRequest.target_user_id == user_id)
            )
        return q.order_by(ShiftSwapRequest.created_at.desc()).all()

    def resolve_swap(
        self,
        db: Session,
        org_id: UUID,
        swap_id: int,
        approver_user_id: int,
        action: str,
        note: Optional[str] = None,
    ) -> ShiftSwapRequest:
        """Approve, reject, or cancel a swap request."""
        swap = db.query(ShiftSwapRequest).filter(ShiftSwapRequest.id == swap_id, ShiftSwapRequest.org_id == org_id).first()
        if not swap:
            raise ValueError(f"Shift swap request {swap_id} not found")
        if swap.status != "PENDING":
            raise ValueError(f"Cannot process swap request in '{swap.status}' state")

        if action == "approve":
            swap.status = "APPROVED"
            swap.approver_user_id = approver_user_id
        elif action == "reject":
            swap.status = "REJECTED"
            swap.approver_user_id = approver_user_id
        elif action == "cancel":
            if approver_user_id != swap.requester_user_id:
                raise ValueError("Only the requester can cancel a swap request")
            swap.status = "CANCELLED"
        else:
            raise ValueError(f"Unknown swap action '{action}'")

        db.commit()
        db.refresh(swap)

        if swap.status == "APPROVED" and swap.target_user_id:
            notification_service.send(
                user_id=swap.target_user_id,
                organization_id=str(org_id),
                title="Shift Swap Approved",
                message=f"Your shift swap request #{swap.id} has been approved.",
                source_module="workforce",
                source_event="ShiftSwapApproved",
                source_id=str(swap.id),
            )

        event_bus.publish(
            "ShiftSwapResolved",
            str(org_id),
            {
                "swap_id": swap.id,
                "org_id": str(org_id),
                "action": action,
                "status": swap.status,
            },
            actor_id=approver_user_id,
        )
        return swap


shift_service = ShiftService()
roster_service = RosterService()
shift_swap_service = ShiftSwapService()

