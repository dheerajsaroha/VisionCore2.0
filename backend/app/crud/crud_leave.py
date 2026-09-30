"""
crud_leave.py — CRUD Operations for Leave Management
Sprint 3 — Module 1
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.models.all_models import (
    LeaveType, LeavePolicy, LeaveBalance, LeaveRequest, LeaveAdjustment, User
)


def _ledger_year(year: Optional[int] = None) -> int:
    """The leave ledger year to act on, defaulting to the current calendar year.

    Resolved per call rather than as a default argument, because a default is
    evaluated once at import and would pin every balance to the year the
    process happened to start in.
    """
    return year if year is not None else date.today().year


def leave_type_applies_to_user(leave_type: LeaveType, user: User) -> bool:
    """Whether a leave type is applicable to a given employee.

    A leave type may carry `gender_specific` ('male' or 'female'), which scopes
    life-event entitlements such as maternity and paternity. The field existed
    and was seeded correctly but was never read, so every employee was granted
    every leave type.

    A life-event type is never part of an annual balance: it is a statutory
    entitlement drawn on a qualifying event, not a quota accrued across the
    year. So:

      - a gender-scoped type never applies here, regardless of the user's
        gender, because these are granted explicitly on a request rather than
        pre-seeded as a balance;
      - every other type applies.

    Request-level validation uses `gender_restriction_error` to allow an
    explicitly-requested life-event entitlement through when the employee
    matches, so a genuine maternity request is not blocked.
    """
    if not leave_type:
        return False
    scope = (leave_type.gender_specific or "").strip().lower()
    if scope in ("male", "female"):
        return False
    return True


def gender_restriction_error(leave_type: LeaveType, user: User) -> Optional[str]:
    """Reason this employee may not take this leave type, or None if they may.

    Used when a request is submitted rather than when a balance is seeded, so
    that an explicitly-requested life-event entitlement is still permitted for
    an employee it applies to.
    """
    scope = (getattr(leave_type, "gender_specific", None) or "").strip().lower()
    if scope not in ("male", "female"):
        return None
    user_gender = (getattr(user, "gender", None) or "").strip().lower()
    if not user_gender:
        # Gender is unstated. Do not block on a guess; the approver decides.
        return None
    if user_gender != scope:
        return (
            f"{leave_type.name} is available to {scope} employees only."
        )
    return None


def _year_of(value: Any) -> int:
    """Ledger year implied by a leave request's own start date."""
    if isinstance(value, datetime):
        return value.year
    if isinstance(value, date):
        return value.year
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10]).year
        except ValueError:
            pass
    return _ledger_year()


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
    def get_user_balance(self, db: Session, user_id: int, leave_type_id: int, year: Optional[int] = None) -> Optional[LeaveBalance]:
        return db.query(LeaveBalance).filter(
            LeaveBalance.user_id == user_id,
            LeaveBalance.leave_type_id == leave_type_id,
            LeaveBalance.year == _ledger_year(year)
        ).first()

    def get_user_balances(self, db: Session, user_id: int, year: Optional[int] = None,
                          org_id: Optional[UUID] = None) -> List[LeaveBalance]:
        query = db.query(LeaveBalance).filter(
            LeaveBalance.user_id == user_id,
            LeaveBalance.year == _ledger_year(year),
        )
        if org_id is not None:
            query = query.filter(LeaveBalance.organization_id == org_id)
        return query.all()

    def get_or_create_balance(self, db: Session, user_id: int, org_id: UUID, leave_type: LeaveType, year: Optional[int] = None, entitled_days: Optional[float] = None) -> LeaveBalance:
        year = _ledger_year(year)
        balance = self.get_user_balance(db, user_id, leave_type.id, year)
        if not balance:
            balance = LeaveBalance(
                user_id=user_id,
                organization_id=org_id,
                leave_type_id=leave_type.id,
                year=year,
                # A policy-aware entitlement is supplied by the seeder; direct
                # callers fall back to the type's full annual allowance.
                entitled_days=float(leave_type.max_days_per_year if entitled_days is None else entitled_days),
                used_days=0.0,
                pending_days=0.0,
                carried_forward_days=0.0,
                adjusted_days=0.0
            )
            db.add(balance)
            db.commit()
            db.refresh(balance)
        elif entitled_days is not None and balance.entitled_days == 0 and balance.used_days == 0:
            # A previously zero-entitlement balance (an unlimited-policy type)
            # can become meaningful if the organization changes its policy.
            balance.entitled_days = float(entitled_days)
            db.commit()
            db.refresh(balance)
        return balance

    def initialize_all_balances_for_user(self, db: Session, user_id: int, org_id: UUID, year: Optional[int] = None) -> List[LeaveBalance]:
        year = _ledger_year(year)
        user = db.query(User).filter(User.id == user_id).first()
        leave_types = crud_leave_type.get_all_for_org(db, org_id, active_only=True)

        # The organization's policy decides how much an entitlement is worth at a
        # point in the year. Under the default annual grant this is the full
        # year's days, which is how the ledger behaved before policy existed.
        from app.services.leave_policy_service import entitlement_for, get_policy

        policy = get_policy(db, org_id, year)

        results = []
        for lt in leave_types:
            # Gender-scoped types (maternity, paternity) are life-event
            # entitlements, not annual quotas. Seeding them for everyone is what
            # gave a male employee a 180-day maternity balance.
            if not leave_type_applies_to_user(lt, user):
                continue
            entitled = entitlement_for(lt, policy, month=date.today().month if year == date.today().year else None)
            bal = self.get_or_create_balance(db, user_id, org_id, lt, year, entitled_days=entitled)
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
        # A life-event entitlement is not pre-seeded as a balance, so a genuine
        # request against one must still be accepted. Reject only the request
        # when the employee is known not to be eligible for it.
        leave_type = db.query(LeaveType).filter(LeaveType.id == obj_in["leave_type_id"]).first()
        if leave_type is not None:
            requester = db.query(User).filter(User.id == user_id).first()
            problem = gender_restriction_error(leave_type, requester)
            if problem:
                raise ValueError(problem)

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
        bal = crud_leave_balance.get_user_balance(
            db, user_id, obj_in["leave_type_id"], _year_of(obj_in.get("start_date"))
        )
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
        bal = crud_leave_balance.get_user_balance(
            db, req.user_id, req.leave_type_id, _year_of(getattr(req, "start_date", None))
        )
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
        bal = crud_leave_balance.get_user_balance(
            db, req.user_id, req.leave_type_id, _year_of(getattr(req, "start_date", None))
        )
        if bal:
            bal.pending_days = max(0.0, bal.pending_days - req.total_days)
            db.add(bal)

        db.commit()
        db.refresh(req)
        return req

    def cancel_request(self, db: Session, req: LeaveRequest) -> LeaveRequest:
        prev_status = req.status
        req.status = "cancelled"

        bal = crud_leave_balance.get_user_balance(
            db, req.user_id, req.leave_type_id, _year_of(getattr(req, "start_date", None))
        )
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
