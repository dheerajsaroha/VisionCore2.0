"""
identity_employment_service.py — VisionCore 3.0 Identity & Employment Services

Encapsulates multi-type enterprise identity lifecycle, employment timeline state transitions,
job position catalog, reporting hierarchy resolution, identity auditing, and domain events.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.all_models import (
    EmploymentRecord,
    IdentityHistory,
    JobPosition,
    User,
    UserSession,
)
from app.services.audit_service import audit_service
from app.services.event_bus import event_bus

logger = logging.getLogger(__name__)

VALID_EMPLOYMENT_TYPES = {
    "EMPLOYEE",
    "CONTRACTOR",
    "CONSULTANT",
    "VENDOR",
    "VISITOR",
    "CANDIDATE",
    "SERVICE_ACCOUNT",
    "SYSTEM_ACCOUNT",
    "ALUMNI",
    "SUPPORT",
}

VALID_IDENTITY_STATUSES = {
    # A hire approved by HR whose onboarding invite has not been accepted yet.
    # The slot is held, so it counts against the position's headcount, but the
    # person has no User account and must not appear as an active employee.
    "PENDING_ONBOARDING",
    "PROBATION",
    "ACTIVE",
    "NOTICE_PERIOD",
    "SUSPENDED",
    "TERMINATED",
    "REHIRED",
}


class IdentityService:
    """Enterprise Identity Lifecycle & History Service."""

    def activate_identity(
        self, db: Session, org_id: UUID, user_id: int, performed_by_id: Optional[int] = None, reason: str = "Account activated"
    ) -> User:
        user = db.query(User).filter(User.org_id == org_id, User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found in org {org_id}")

        prev_active = user.is_active
        user.is_active = 1
        db.add(user)

        # Audit timeline entry
        history = IdentityHistory(
            org_id=org_id,
            user_id=user_id,
            event_type="ACTIVATED",
            previous_state={"is_active": prev_active},
            new_state={"is_active": 1},
            reason=reason,
            performed_by_id=performed_by_id,
        )
        db.add(history)
        db.commit()
        db.refresh(user)

        audit_service.record(
            tenant_id=str(org_id),
            actor_id=str(performed_by_id) if performed_by_id else "system",
            action="identity.activated",
            target_type="user",
            target_id=str(user_id),
            after_state={"user_id": user_id, "is_active": 1},
        )

        event_bus.publish(
            "IdentityActivated",
            {
                "org_id": str(org_id),
                "user_id": user_id,
                "email": user.email,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return user

    def suspend_identity(
        self, db: Session, org_id: UUID, user_id: int, performed_by_id: Optional[int] = None, reason: str = "Administrative suspension"
    ) -> User:
        user = db.query(User).filter(User.org_id == org_id, User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        prev_active = user.is_active
        user.is_active = 0
        db.add(user)

        history = IdentityHistory(
            org_id=org_id,
            user_id=user_id,
            event_type="SUSPENDED",
            previous_state={"is_active": prev_active},
            new_state={"is_active": 0},
            reason=reason,
            performed_by_id=performed_by_id,
        )
        db.add(history)
        db.commit()
        db.refresh(user)

        audit_service.record(
            tenant_id=str(org_id),
            actor_id=str(performed_by_id) if performed_by_id else "system",
            action="identity.suspended",
            target_type="user",
            target_id=str(user_id),
            after_state={"user_id": user_id, "is_active": 0, "reason": reason},
        )

        event_bus.publish(
            "IdentitySuspended",
            {
                "org_id": str(org_id),
                "user_id": user_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return user

    def get_identity_timeline(self, db: Session, org_id: UUID, user_id: int) -> List[IdentityHistory]:
        return (
            db.query(IdentityHistory)
            .filter(IdentityHistory.org_id == org_id, IdentityHistory.user_id == user_id)
            .order_by(IdentityHistory.created_at.desc())
            .all()
        )

    def get_trusted_devices(self, db: Session, user_id: int) -> List[UserSession]:
        return (
            db.query(UserSession)
            .filter(UserSession.user_id == user_id, UserSession.is_active == True)
            .order_by(UserSession.last_activity_at.desc())
            .all()
        )


class PositionService:
    """Enterprise Position & Position Hierarchy Service."""

    def create_position(self, db: Session, org_id: UUID, data: Dict[str, Any]) -> JobPosition:
        position = JobPosition(org_id=org_id, **data)
        db.add(position)
        db.commit()
        db.refresh(position)

        event_bus.publish(
            "PositionCreated",
            {
                "org_id": str(org_id),
                "position_id": position.id,
                "code": position.code,
                "title": position.title,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return position

    def list_positions(self, db: Session, org_id: UUID) -> List[JobPosition]:
        return (
            db.query(JobPosition)
            .filter(JobPosition.org_id == org_id, JobPosition.is_deleted == 0)
            .order_by(JobPosition.title)
            .all()
        )


class EmploymentService:
    """Enterprise Employment Record & Lifecycle Transitions."""

    def hire_employee(
        self, db: Session, org_id: UUID, user_id: int, data: Dict[str, Any]
    ) -> EmploymentRecord:
        record = (
            db.query(EmploymentRecord)
            .filter(EmploymentRecord.org_id == org_id, EmploymentRecord.user_id == user_id)
            .first()
        )
        if not record:
            record = EmploymentRecord(org_id=org_id, user_id=user_id, **data)
        else:
            for k, v in data.items():
                setattr(record, k, v)
        record.status = "ACTIVE"
        db.add(record)

        # Record Identity History
        history = IdentityHistory(
            org_id=org_id,
            user_id=user_id,
            event_type="HIRED",
            new_state={"employment_type": record.employment_type, "status": record.status},
            reason="Employee onboarded/hired",
        )
        db.add(history)
        db.commit()
        db.refresh(record)

        event_bus.publish(
            "EmployeeHired",
            {
                "org_id": str(org_id),
                "user_id": user_id,
                "employment_type": record.employment_type,
                "joining_date": record.joining_date.isoformat() if record.joining_date else None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return record

    def transfer_employee(
        self, db: Session, org_id: UUID, user_id: int, new_dept_id: Optional[int], new_position_id: Optional[int], reason: str
    ) -> EmploymentRecord:
        record = (
            db.query(EmploymentRecord)
            .filter(EmploymentRecord.org_id == org_id, EmploymentRecord.user_id == user_id)
            .first()
        )
        if not record:
            raise ValueError(f"Employment record for user {user_id} not found")

        prev_pos = record.position_id
        if new_position_id:
            record.position_id = new_position_id
        db.add(record)

        # Update User department FK as well for backward compatibility
        user = db.query(User).filter(User.id == user_id).first()
        if user and new_dept_id:
            user.dept_id = new_dept_id
            db.add(user)

        history = IdentityHistory(
            org_id=org_id,
            user_id=user_id,
            event_type="TRANSFERRED",
            previous_state={"position_id": prev_pos},
            new_state={"position_id": new_position_id, "dept_id": new_dept_id},
            reason=reason,
        )
        db.add(history)
        db.commit()
        db.refresh(record)

        event_bus.publish(
            "EmployeeTransferred",
            {
                "org_id": str(org_id),
                "user_id": user_id,
                "new_dept_id": new_dept_id,
                "new_position_id": new_position_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return record

    def promote_employee(
        self, db: Session, org_id: UUID, user_id: int, new_designation: str, new_position_id: Optional[int], reason: str
    ) -> EmploymentRecord:
        record = (
            db.query(EmploymentRecord)
            .filter(EmploymentRecord.org_id == org_id, EmploymentRecord.user_id == user_id)
            .first()
        )
        if not record:
            raise ValueError(f"Employment record for user {user_id} not found")

        prev_desig = record.designation
        record.designation = new_designation
        if new_position_id:
            record.position_id = new_position_id
        db.add(record)

        history = IdentityHistory(
            org_id=org_id,
            user_id=user_id,
            event_type="PROMOTED",
            previous_state={"designation": prev_desig},
            new_state={"designation": new_designation, "position_id": new_position_id},
            reason=reason,
        )
        db.add(history)
        db.commit()
        db.refresh(record)

        event_bus.publish(
            "EmployeePromoted",
            {
                "org_id": str(org_id),
                "user_id": user_id,
                "new_designation": new_designation,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return record

    def exit_employee(
        self, db: Session, org_id: UUID, user_id: int, exit_date: datetime, reason: str
    ) -> EmploymentRecord:
        record = (
            db.query(EmploymentRecord)
            .filter(EmploymentRecord.org_id == org_id, EmploymentRecord.user_id == user_id)
            .first()
        )
        if not record:
            raise ValueError(f"Employment record for user {user_id} not found")

        record.status = "TERMINATED"
        record.exit_date = exit_date
        db.add(record)

        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_active = 0
            db.add(user)

        history = IdentityHistory(
            org_id=org_id,
            user_id=user_id,
            event_type="TERMINATED",
            previous_state={"status": "ACTIVE"},
            new_state={"status": "TERMINATED", "exit_date": exit_date.isoformat()},
            reason=reason,
        )
        db.add(history)
        db.commit()
        db.refresh(record)

        event_bus.publish(
            "EmployeeExited",
            {
                "org_id": str(org_id),
                "user_id": user_id,
                "exit_date": exit_date.isoformat(),
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return record

    def get_employment_record(self, db: Session, org_id: UUID, user_id: int) -> Optional[EmploymentRecord]:
        return (
            db.query(EmploymentRecord)
            .filter(EmploymentRecord.org_id == org_id, EmploymentRecord.user_id == user_id)
            .first()
        )


identity_service = IdentityService()
position_service = PositionService()
employment_service = EmploymentService()
