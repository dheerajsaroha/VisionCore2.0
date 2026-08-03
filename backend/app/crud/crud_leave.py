"""
crud_leave.py — CRUD Operations for Leave Management
Sprint 3 — Module 1
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.models.all_models import (
    LeaveType, LeavePolicy, LeaveBalance, LeaveRequest, LeaveAdjustment, User
)


class CRUDLeaveType:
    def get_by_id(self, db: Session, leave_type_id: int) -> Optional[LeaveType]:
        return db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()

    def get_by_code(self, db: Session, org_id: UUID, code: str) -> Optional[LeaveType]:
        return db.query(LeaveType).filter(
            LeaveType.organization_id == org_id,
            LeaveType.code == code
        ).first()

    def get_all_for_org(self, db: Session, org_id: UUID, active_only: bool = True) -> List[LeaveType]:
        q = db.query(LeaveType).filter(LeaveType.organization_id == org_id)
        if active_only:
            q = q.filter(LeaveType.is_active.is_(True))
        return q.order_by(LeaveType.name.asc()).all()

    def create(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> LeaveType:
        db_obj = LeaveType(
            organization_id=org_id,
            name=obj_in["name"],
            code=obj_in["code"].upper(),
            description=obj_in.get("description"),
            max_days_per_year=obj_in.get("max_days_per_year", 12),
            max_days_per_request=obj_in.get("max_days_per_request", 30),
            carry_forward=obj_in.get("carry_forward", False),
            max_carry_forward_days=obj_in.get("max_carry_forward_days", 0),
            requires_document=obj_in.get("requires_document", False),
            min_notice_days=obj_in.get("min_notice_days", 0),
            is_paid=obj_in.get("is_paid", True),
            is_active=obj_in.get("is_active", True),
            gender_specific=obj_in.get("gender_specific")
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def upsert(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> LeaveType:
        """
        Idempotent upsert: insert a leave type for the organization, or
        update the existing one if a row with the same (organization_id, code)
        already exists.  This prevents IntegrityError / duplicate key violations
        under concurrent requests.
        """
        code = obj_in["code"].upper()
        # Build the values dict matching the model columns
        values = {
            "organization_id": org_id,
            "name": obj_in["name"],
            "code": code,
            "description": obj_in.get("description"),
            "max_days_per_year": obj_in.get("max_days_per_year", 12),
            "max_days_per_request": obj_in.get("max_days_per_request", 30),
            "carry_forward": obj_in.get("carry_forward", False),
            "max_carry_forward_days": obj_in.get("max_carry_forward_days", 0),
            "requires_document": obj_in.get("requires_document", False),
            "min_notice_days": obj_in.get("min_notice_days", 0),
            "is_paid": obj_in.get("is_paid", True),
            "is_active": obj_in.get("is_active", True),
            "gender_specific": obj_in.get("gender_specific"),
        }

        stmt = pg_insert(LeaveType).values(**values)
        # On conflict (org_id, code) do nothing so we never violate the constraint
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["organization_id", "code"],
        )
        db.execute(stmt)
        db.commit()

        # Return the existing (or newly inserted) row
        return self.get_by_code(db, org_id, code)

    def update(self, db: Session, db_obj: LeaveType, updates: Dict[str, Any]) -> LeaveType:
        for field, value in updates.items():
            if value is not None and hasattr(db_obj, field):
                setattr(db_obj, field, value)
        db.commit()
        db.refresh(db_obj)
        return db_obj


class CRUDLeaveBalance:
    def get_user_balance(self, db: Session, user_id: int, leave_type_id: int, year: int = 2025) -> Optional[LeaveBalance]:
        return db.query(LeaveBalance).filter(
            LeaveBalance.user_id == user_id,
            LeaveBalance.leave_type_id == leave_type_id,
            LeaveBalance.year == year
        ).first()

    def get_user_balances(self, db: Session, user_id: int, year: int = 2025) -> List[LeaveBalance]:
        return db.query(LeaveBalance).filter(
            LeaveBalance.user_id == user_id,
            LeaveBalance.year == year
        ).all()

    def get_or_create_balance(self, db: Session, user_id: int, org_id: UUID, leave_type: LeaveType, year: int = 2025) -> LeaveBalance:
        balance = self.get_user_balance(db, user_id, leave_type.id, year)
        if not balance:
            balance = LeaveBalance(
                user_id=user_id,
                organization_id=org_id,
                leave_type_id=leave_type.id,
                year=year,
                entitled_days=float(leave_type.max_days_per_year),
                used_days=0.0,
                pending_days=0.0,
                carried_forward_days=0.0,
                adjusted_days=0.0
            )
            db.add(balance)
            db.commit()
            db.refresh(balance)
        return balance

    def initialize_all_balances_for_user(self, db: Session, user_id: int, org_id: UUID, year: int = 2025) -> List[LeaveBalance]:
        leave_types = crud_leave_type.get_all_for_org(db, org_id, active_only=True)
        results = []
        for lt in leave_types:
            bal = self.get_or_create_balance(db, user_id, org_id, lt, year)
            results.append(bal)
        return results


class CRUDLeaveRequest:
    def get_by_id(self, db: Session, request_id: int) -> Optional[LeaveRequest]:
        return db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()

    def list_requests(
        self,
        db: Session,
        org_id: UUID,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[LeaveRequest]:
        q = db.query(LeaveRequest).filter(LeaveRequest.organization_id == org_id)
        if user_id is not None:
            q = q.filter(LeaveRequest.user_id == user_id)
        if status:
            q = q.filter(LeaveRequest.status == status)
        return q.order_by(LeaveRequest.created_at.desc()).offset(skip).limit(limit).all()

    def create_request(self, db: Session, user_id: int, org_id: UUID, obj_in: Dict[str, Any]) -> LeaveRequest:
        req = LeaveRequest(
            organization_id=org_id,
            user_id=user_id,
            leave_type_id=obj_in["leave_type_id"],
            start_date=obj_in["start_date"],
            end_date=obj_in["end_date"],
            total_days=obj_in["total_days"],
            is_half_day=obj_in.get("is_half_day", False),
            half_day_period=obj_in.get("half_day_period"),
            reason=obj_in.get("reason"),
            document_url=obj_in.get("document_url"),
            status="pending"
        )
        db.add(req)

        # Update pending days in balance ledger
        bal = crud_leave_balance.get_user_balance(db, user_id, obj_in["leave_type_id"])
        if bal:
            bal.pending_days += obj_in["total_days"]
            db.add(bal)

        db.commit()
        db.refresh(req)
        return req

    def approve_request(self, db: Session, req: LeaveRequest, approver_user_id: int, note: Optional[str] = None) -> LeaveRequest:
        req.status = "approved"
        req.approver_user_id = approver_user_id
        req.approver_note = note
        req.approved_at = datetime.now(timezone.utc)

        # Transfer pending_days to used_days in balance
        bal = crud_leave_balance.get_user_balance(db, req.user_id, req.leave_type_id)
        if bal:
            bal.pending_days = max(0.0, bal.pending_days - req.total_days)
            bal.used_days += req.total_days
            db.add(bal)

        db.commit()
        db.refresh(req)
        return req

    def reject_request(self, db: Session, req: LeaveRequest, approver_user_id: int, note: Optional[str] = None) -> LeaveRequest:
        req.status = "rejected"
        req.approver_user_id = approver_user_id
        req.approver_note = note

        # Release pending days in balance
        bal = crud_leave_balance.get_user_balance(db, req.user_id, req.leave_type_id)
        if bal:
            bal.pending_days = max(0.0, bal.pending_days - req.total_days)
            db.add(bal)

        db.commit()
        db.refresh(req)
        return req

    def cancel_request(self, db: Session, req: LeaveRequest) -> LeaveRequest:
        prev_status = req.status
        req.status = "cancelled"

        bal = crud_leave_balance.get_user_balance(db, req.user_id, req.leave_type_id)
        if bal:
            if prev_status == "pending":
                bal.pending_days = max(0.0, bal.pending_days - req.total_days)
            elif prev_status == "approved":
                bal.used_days = max(0.0, bal.used_days - req.total_days)
            db.add(bal)

        db.commit()
        db.refresh(req)
        return req


crud_leave_type = CRUDLeaveType()
crud_leave_balance = CRUDLeaveBalance()
crud_leave_request = CRUDLeaveRequest()
