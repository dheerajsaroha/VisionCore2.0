from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from app.db.models.all_models import AttendanceApproval, AttendanceLog, AttendanceRequest, User
from app.repositories.attendance_correction_repo import (
    RequestTimelineItem,
    attendance_correction_repo,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exception Design
# ---------------------------------------------------------------------------

class AttendanceCorrectionError(Exception):
    """Base exception for all attendance correction service errors."""
    pass


class ValidationError(AttendanceCorrectionError):
    """Raised when request payload or data validation fails."""
    pass


class RequestNotFoundError(AttendanceCorrectionError):
    """Raised when an attendance correction request is not found."""
    pass


class InvalidWorkflowTransitionError(AttendanceCorrectionError):
    """Raised when an invalid workflow transition is attempted."""
    pass


class CrossTenantAccessError(AttendanceCorrectionError):
    """Raised when cross-tenant access is attempted."""
    pass


class DuplicatePendingRequestError(AttendanceCorrectionError):
    """Raised when a duplicate pending request is submitted."""
    pass


# ---------------------------------------------------------------------------
# Service Implementation
# ---------------------------------------------------------------------------

class AttendanceCorrectionService:
    """Enterprise service layer for attendance correction workflow.

    Encapsulates workflow validation, tenant isolation, transaction boundaries,
    and audit logging.
    """

    def __init__(self, repository=attendance_correction_repo):
        self.repository = repository

    # ---------------------------------------------------------------------------
    # Helper Utilities
    # ---------------------------------------------------------------------------

    def _normalize_uuid(self, val: Any) -> uuid.UUID:
        """Helper to safely convert values to uuid.UUID."""
        if isinstance(val, uuid.UUID):
            return val
        try:
            return uuid.UUID(str(val))
        except (ValueError, TypeError) as exc:
            raise ValidationError("Invalid organization identifier format.") from exc

    @contextmanager
    def _transaction_context(self, db: Session):
        """Provide a transactional scope for atomic operations.

        Supports nested transactions (SAVEPOINT) if an outer transaction is active.
        """
        if db.in_transaction():
            with db.begin_nested():
                yield
        else:
            with db.begin():
                yield

    def _get_and_validate_actor(self, db: Session, user_id: int, org_id: uuid.UUID) -> User:
        """Retrieve and validate that the user exists and belongs to the tenant."""
        actor = db.query(User).filter(User.id == user_id, User.is_deleted == 0).first()
        if not actor:
            raise ValidationError(f"User with ID {user_id} not found.")
        if self._normalize_uuid(actor.org_id) != org_id:
            raise CrossTenantAccessError("User does not belong to the specified tenant/organization.")
        return actor

    def _get_and_validate_request(
        self, db: Session, request_id: int, org_id: uuid.UUID
    ) -> AttendanceRequest:
        """Retrieve and validate that the request exists and belongs to the tenant."""
        # Unscoped query to differentiate between non-existent request and tenant mismatch
        req = db.query(AttendanceRequest).filter(AttendanceRequest.id == request_id).first()
        if not req:
            raise RequestNotFoundError(f"Attendance request with ID {request_id} not found.")

        if self._normalize_uuid(req.org_id) != org_id:
            raise CrossTenantAccessError("Access to this attendance request is forbidden.")

        return req

    def validate_transition(self, current_status: str, target_status: str) -> None:
        """Enforce workflow state machine rules."""
        ALLOWED_TRANSITIONS = {
            "pending": {"approved", "rejected", "cancelled"},
            "approved": {"overridden"},
            "rejected": {"overridden"},
            "cancelled": set(),
            "overridden": set(),
        }
        if target_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
            raise InvalidWorkflowTransitionError(
                f"Invalid workflow transition from '{current_status}' to '{target_status}'"
            )

    # ---------------------------------------------------------------------------
    # Service Operations
    # ---------------------------------------------------------------------------

    def submit_request(
        self,
        db: Session,
        *,
        org_id: Any,
        employee_user_id: int,
        attendance_log_id: Optional[int],
        request_payload: Optional[dict],
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AttendanceRequest:
        """Submit a new attendance correction request.

        Validates employee and log tenant context, prevents duplicates,
        runs atomically, and registers audit logs.
        """
        norm_org_id = self._normalize_uuid(org_id)

        # 1. Validate employee
        employee = self._get_and_validate_actor(db, employee_user_id, norm_org_id)

        # 2. Validate attendance record if provided
        if attendance_log_id is not None:
            log = (
                db.query(AttendanceLog)
                .filter(AttendanceLog.id == attendance_log_id, AttendanceLog.is_deleted == 0)
                .first()
            )
            if not log:
                raise ValidationError(f"Attendance log with ID {attendance_log_id} not found.")
            if log.user_id != employee_user_id:
                raise ValidationError("Attendance record does not belong to the specified employee.")
            # Verify attendance record's user belongs to the tenant
            if self._normalize_uuid(log.user.org_id) != norm_org_id:
                raise CrossTenantAccessError("Attendance record does not belong to this tenant.")

        # 3. Prevent duplicate pending requests
        duplicate = (
            db.query(AttendanceRequest)
            .filter(
                AttendanceRequest.org_id == norm_org_id,
                AttendanceRequest.employee_user_id == employee_user_id,
                AttendanceRequest.attendance_log_id == attendance_log_id,
                AttendanceRequest.status == "pending",
            )
            .first()
        )
        if duplicate:
            raise DuplicatePendingRequestError(
                "A pending correction request already exists for this attendance log/employee."
            )

        # 4. Atomically persist request
        with self._transaction_context(db):
            req = self.repository.create_request(
                db,
                org_id=norm_org_id,
                employee_user_id=employee_user_id,
                attendance_log_id=attendance_log_id,
                request_payload=request_payload,
            )

        logger.info(
            "Created attendance correction request [id=%s] for employee [id=%s] in org [id=%s]",
            req.id,
            employee_user_id,
            norm_org_id,
        )

        # 5. Log audit trail
        audit_service = AuditService(db)
        # Exclude raw request_payload to prevent sensitive info leakage
        after_state = {
            "id": req.id,
            "org_id": str(norm_org_id),
            "employee_user_id": employee_user_id,
            "attendance_log_id": attendance_log_id,
            "status": req.status,
            "submitted_at": req.submitted_at.isoformat() if req.submitted_at else None,
        }
        audit_service.log_create(
            actor=employee,
            action="attendance_request.create",
            target_type="AttendanceRequest",
            target_id=str(req.id),
            after_state=after_state,
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
            tenant_org_id=str(norm_org_id),
        )

        return req

    def approve_request(
        self,
        db: Session,
        *,
        org_id: Any,
        request_id: int,
        approver_user_id: int,
        notes: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> AttendanceApproval:
        """Approve a pending attendance request.

        Performs workflow check, creates immutable approval record, updates request
        status to 'approved' atomically, and writes to audit logs.
        """
        norm_org_id = self._normalize_uuid(org_id)

        # 1. Validate approver
        approver = self._get_and_validate_actor(db, approver_user_id, norm_org_id)

        # 2. Validate request & workflow transition
        req = self._get_and_validate_request(db, request_id, norm_org_id)
        self.validate_transition(req.status, "approved")

        # 3. Process approval atomically
        with self._transaction_context(db):
            approval = self.repository.approve_request(
                db,
                org_id=norm_org_id,
                request_id=request_id,
                approver_user_id=approver_user_id,
                decision_notes=notes,
            )
            # Decorate the approval model with context fields
            if ip_address:
                approval.created_by_ip = ip_address
            if user_agent:
                approval.created_by_user_agent = user_agent
            if correlation_id:
                approval.created_by_correlation_id = correlation_id
            db.flush()

        logger.info(
            "Approved attendance correction request [id=%s] by approver [id=%s] in org [id=%s]",
            request_id,
            approver_user_id,
            norm_org_id,
        )

        # 4. Log audit trail
        audit_service = AuditService(db)
        audit_service.log_update(
            actor=approver,
            action="attendance_request.approve",
            target_type="AttendanceRequest",
            target_id=str(request_id),
            before_state={"status": "pending"},
            after_state={"status": "approved", "approval_id": approval.id},
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
            tenant_org_id=str(norm_org_id),
        )

        return approval

    def reject_request(
        self,
        db: Session,
        *,
        org_id: Any,
        request_id: int,
        approver_user_id: int,
        notes: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> AttendanceApproval:
        """Reject a pending attendance request.

        Performs workflow check, creates immutable rejection record, updates request
        status to 'rejected' atomically, and writes to audit logs.
        """
        norm_org_id = self._normalize_uuid(org_id)

        # 1. Validate rejecter
        rejecter = self._get_and_validate_actor(db, approver_user_id, norm_org_id)

        # 2. Validate request & workflow transition
        req = self._get_and_validate_request(db, request_id, norm_org_id)
        self.validate_transition(req.status, "rejected")

        # 3. Process rejection atomically
        with self._transaction_context(db):
            approval = self.repository.reject_request(
                db,
                org_id=norm_org_id,
                request_id=request_id,
                approver_user_id=approver_user_id,
                decision_notes=notes,
            )
            # Decorate the approval model with context fields
            if ip_address:
                approval.created_by_ip = ip_address
            if user_agent:
                approval.created_by_user_agent = user_agent
            if correlation_id:
                approval.created_by_correlation_id = correlation_id
            db.flush()

        logger.info(
            "Rejected attendance correction request [id=%s] by approver [id=%s] in org [id=%s]",
            request_id,
            approver_user_id,
            norm_org_id,
        )

        # 4. Log audit trail
        audit_service = AuditService(db)
        audit_service.log_update(
            actor=rejecter,
            action="attendance_request.reject",
            target_type="AttendanceRequest",
            target_id=str(request_id),
            before_state={"status": "pending"},
            after_state={"status": "rejected", "approval_id": approval.id},
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
            tenant_org_id=str(norm_org_id),
        )

        return approval

    def override_request(
        self,
        db: Session,
        *,
        org_id: Any,
        request_id: int,
        approver_user_id: int,
        override_reason: str,
        notes: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> AttendanceApproval:
        """Override a completed (approved/rejected) attendance request.

        Performs workflow transition validation, enforces override reason requirement,
        creates immutable override record, and writes to audit logs.
        """
        norm_org_id = self._normalize_uuid(org_id)

        if not override_reason or not override_reason.strip():
            raise ValidationError("Override reason is required for request override.")

        # 1. Validate overriding user
        overrider = self._get_and_validate_actor(db, approver_user_id, norm_org_id)

        # 2. Validate request & workflow transition
        req = self._get_and_validate_request(db, request_id, norm_org_id)
        before_status = req.status
        self.validate_transition(before_status, "overridden")

        # 3. Process override atomically
        with self._transaction_context(db):
            approval = self.repository.override_request(
                db,
                org_id=norm_org_id,
                request_id=request_id,
                approver_user_id=approver_user_id,
                decision_notes=notes,
                override_reason=override_reason,
            )
            # Decorate the approval model with context fields
            if ip_address:
                approval.created_by_ip = ip_address
            if user_agent:
                approval.created_by_user_agent = user_agent
            if correlation_id:
                approval.created_by_correlation_id = correlation_id
            db.flush()

        logger.info(
            "Overrode attendance correction request [id=%s] by approver [id=%s] in org [id=%s]",
            request_id,
            approver_user_id,
            norm_org_id,
        )

        # 4. Log audit trail
        audit_service = AuditService(db)
        audit_service.log_update(
            actor=overrider,
            action="attendance_request.override",
            target_type="AttendanceRequest",
            target_id=str(request_id),
            before_state={"status": before_status},
            after_state={
                "status": "overridden",
                "approval_id": approval.id,
                "override_reason": override_reason,
            },
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
            tenant_org_id=str(norm_org_id),
            reason=override_reason,
        )

        return approval

    def cancel_request(
        self,
        db: Session,
        *,
        org_id: Any,
        request_id: int,
        actor_user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> AttendanceRequest:
        """Cancel a pending attendance request.

        Only pending requests can be cancelled. Updates status to 'cancelled' and
        registers cancellation timestamp.
        """
        norm_org_id = self._normalize_uuid(org_id)

        # 1. Validate request & workflow transition
        req = self._get_and_validate_request(db, request_id, norm_org_id)
        self.validate_transition(req.status, "cancelled")

        # 2. Get and validate actor. If actor_user_id not provided, default to requesting employee.
        if actor_user_id is not None:
            actor = self._get_and_validate_actor(db, actor_user_id, norm_org_id)
        else:
            actor = req.employee

        now = datetime.now(timezone.utc)

        # 3. Process cancellation atomically
        with self._transaction_context(db):
            updated_req = self.repository.cancel_request(
                db,
                org_id=norm_org_id,
                request_id=request_id,
                cancelled_at=now,
            )

        logger.info(
            "Cancelled attendance correction request [id=%s] in org [id=%s]",
            request_id,
            norm_org_id,
        )

        # 4. Log audit trail
        audit_service = AuditService(db)
        audit_service.log_update(
            actor=actor,
            action="attendance_request.cancel",
            target_type="AttendanceRequest",
            target_id=str(request_id),
            before_state={"status": "pending"},
            after_state={"status": "cancelled", "cancelled_at": now.isoformat()},
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
            tenant_org_id=str(norm_org_id),
        )

        return updated_req

    # ---------------------------------------------------------------------------
    # Query / Read Operations
    # ---------------------------------------------------------------------------

    def get_request(
        self,
        db: Session,
        *,
        org_id: Any,
        request_id: int,
    ) -> AttendanceRequest:
        """Fetch a request by ID enforcing tenant isolation."""
        norm_org_id = self._normalize_uuid(org_id)
        return self._get_and_validate_request(db, request_id, norm_org_id)

    def get_request_timeline(
        self,
        db: Session,
        *,
        org_id: Any,
        request_id: int,
    ) -> List[RequestTimelineItem]:
        """Fetch chronologically ordered history timeline for a request."""
        norm_org_id = self._normalize_uuid(org_id)
        # Ensure request exists and belongs to the tenant
        self._get_and_validate_request(db, request_id, norm_org_id)
        return self.repository.get_request_timeline(db, org_id=norm_org_id, request_id=request_id)

    def list_pending_requests(
        self,
        db: Session,
        *,
        org_id: Any,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AttendanceRequest]:
        """List all pending correction requests for a tenant."""
        norm_org_id = self._normalize_uuid(org_id)
        return self.repository.list_pending_requests(
            db, org_id=norm_org_id, limit=limit, offset=offset
        )

    def list_employee_requests(
        self,
        db: Session,
        *,
        org_id: Any,
        employee_user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AttendanceRequest]:
        """List correction requests submitted by a specific employee within a tenant."""
        norm_org_id = self._normalize_uuid(org_id)
        # Verify employee belongs to tenant
        self._get_and_validate_actor(db, employee_user_id, norm_org_id)
        return self.repository.list_employee_requests(
            db,
            org_id=norm_org_id,
            employee_user_id=employee_user_id,
            limit=limit,
            offset=offset,
        )


attendance_correction_service = AttendanceCorrectionService()
