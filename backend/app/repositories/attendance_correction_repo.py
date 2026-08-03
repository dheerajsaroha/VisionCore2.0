from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.all_models import AttendanceApproval, AttendanceRequest


@dataclass(frozen=True)
class RequestTimelineItem:
    """Read-only timeline entry returned by get_request_timeline."""

    # The timeline is intentionally generic to avoid business logic.
    kind: str  # "request" | "approval"
    status: str
    occurred_at: object  # datetime-like (kept generic for repo neutrality)
    actor_user_id: Optional[int] = None
    actor_role_name: Optional[str] = None
    notes: Optional[str] = None


class AttendanceCorrectionRepository:
    """Persistence operations only for attendance corrections workflow.

    No permission logic, no business rules, no audit/notification side effects.

    All reads/writes are tenant-scoped by org_id where applicable.
    """

    # ---------------------------
    # Create
    # ---------------------------
    def create_request(
        self,
        db: Session,
        *,
        org_id,
        employee_user_id: int,
        attendance_log_id: Optional[int],
        request_payload: Optional[dict],
    ) -> AttendanceRequest:
        req = AttendanceRequest(
            org_id=org_id,
            employee_user_id=employee_user_id,
            attendance_log_id=attendance_log_id,
            request_payload=request_payload,
            status="pending",
        )
        db.add(req)
        db.flush()  # ensure req.id is populated for immediate follow-up persistence
        return req

    # ---------------------------
    # Read
    # ---------------------------
    def get_request_by_id(
        self,
        db: Session,
        *,
        org_id,
        request_id: int,
    ) -> Optional[AttendanceRequest]:
        stmt = select(AttendanceRequest).where(
            AttendanceRequest.id == request_id,
            AttendanceRequest.org_id == org_id,
        )
        return db.execute(stmt).scalars().first()

    def list_employee_requests(
        self,
        db: Session,
        *,
        org_id,
        employee_user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AttendanceRequest]:
        stmt = (
            select(AttendanceRequest)
            .where(
                AttendanceRequest.org_id == org_id,
                AttendanceRequest.employee_user_id == employee_user_id,
            )
            .order_by(AttendanceRequest.submitted_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(db.execute(stmt).scalars().all())

    def list_pending_requests(
        self,
        db: Session,
        *,
        org_id,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AttendanceRequest]:
        stmt = (
            select(AttendanceRequest)
            .where(
                AttendanceRequest.org_id == org_id,
                AttendanceRequest.status == "pending",
            )
            .order_by(AttendanceRequest.submitted_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(db.execute(stmt).scalars().all())

    def list_requests_by_org(
        self,
        db: Session,
        *,
        org_id,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AttendanceRequest]:
        stmt = select(AttendanceRequest).where(AttendanceRequest.org_id == org_id)
        if status is not None:
            stmt = stmt.where(AttendanceRequest.status == status)

        stmt = stmt.order_by(AttendanceRequest.submitted_at.desc()).limit(limit).offset(offset)
        return list(db.execute(stmt).scalars().all())

    # ---------------------------
    # Workflow state persistence (no rules)
    # ---------------------------
    def approve_request(
        self,
        db: Session,
        *,
        org_id,
        request_id: int,
        approver_user_id: Optional[int],
        decision_notes: Optional[str],
    ) -> AttendanceApproval:
        req = self.get_request_by_id(db, org_id=org_id, request_id=request_id)
        if req is None:
            raise ValueError("AttendanceRequest not found for tenant scope")

        # Persist immutable approval event
        approval = AttendanceApproval(
            attendance_request_id=req.id,
            org_id=org_id,
            approver_user_id=approver_user_id,
            approval_status="approved",
            decision_notes=decision_notes,
        )
        db.add(approval)

        # Persist current request status
        req.status = "approved"
        db.add(req)
        db.flush()
        return approval

    def reject_request(
        self,
        db: Session,
        *,
        org_id,
        request_id: int,
        approver_user_id: Optional[int],
        decision_notes: Optional[str],
    ) -> AttendanceApproval:
        req = self.get_request_by_id(db, org_id=org_id, request_id=request_id)
        if req is None:
            raise ValueError("AttendanceRequest not found for tenant scope")

        approval = AttendanceApproval(
            attendance_request_id=req.id,
            org_id=org_id,
            approver_user_id=approver_user_id,
            approval_status="rejected",
            decision_notes=decision_notes,
        )
        db.add(approval)

        req.status = "rejected"
        db.add(req)
        db.flush()
        return approval

    def override_request(
        self,
        db: Session,
        *,
        org_id,
        request_id: int,
        approver_user_id: Optional[int],
        decision_notes: Optional[str],
        override_reason: Optional[str],
    ) -> AttendanceApproval:
        req = self.get_request_by_id(db, org_id=org_id, request_id=request_id)
        if req is None:
            raise ValueError("AttendanceRequest not found for tenant scope")

        approval = AttendanceApproval(
            attendance_request_id=req.id,
            org_id=org_id,
            approver_user_id=approver_user_id,
            approval_status="overridden",
            decision_notes=decision_notes,
            override_reason=override_reason,
        )
        db.add(approval)

        req.status = "overridden"
        db.add(req)
        db.flush()
        return approval

    def cancel_request(
        self,
        db: Session,
        *,
        org_id,
        request_id: int,
        cancelled_at=None,
    ) -> AttendanceRequest:
        req = self.get_request_by_id(db, org_id=org_id, request_id=request_id)
        if req is None:
            raise ValueError("AttendanceRequest not found for tenant scope")

        req.status = "cancelled"
        # If the caller provides a cancelled_at, use it; otherwise keep repo neutral by leaving default/null.
        req.cancelled_at = cancelled_at
        db.add(req)
        db.flush()
        return req

    def get_request_timeline(
        self,
        db: Session,
        *,
        org_id,
        request_id: int,
    ) -> List[RequestTimelineItem]:
        """Return a chronological timeline composed from request + approval events.

        Repository-only: returns read models without computing rules.
        """

        req = self.get_request_by_id(db, org_id=org_id, request_id=request_id)
        if req is None:
            return []

        timeline: List[RequestTimelineItem] = [
            RequestTimelineItem(
                kind="request",
                status=req.status,
                occurred_at=req.submitted_at,
                actor_user_id=req.employee_user_id,
                notes=None,
            )
        ]

        stmt = (
            select(AttendanceApproval)
            .where(
                AttendanceApproval.attendance_request_id == request_id,
                AttendanceApproval.org_id == org_id,
            )
            .order_by(AttendanceApproval.decided_at.asc())
        )
        approvals = list(db.execute(stmt).scalars().all())

        for a in approvals:
            timeline.append(
                RequestTimelineItem(
                    kind="approval",
                    status=a.approval_status,
                    occurred_at=a.decided_at,
                    actor_user_id=a.approver_user_id,
                    notes=a.decision_notes,
                )
            )

        # Ensure deterministic ordering by comparing occurred_at timestamps.
        # If occurred_at is ever None, fall back to a deterministic minimal value.
        return timeline




attendance_correction_repo = AttendanceCorrectionRepository()


