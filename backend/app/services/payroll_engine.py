"""
payroll_engine.py — PI-6 Finance & Payroll Domain

Deterministic, auditable payroll calculation engine.

Calculation formula per employee:
    gross_salary     = base_pay + hra + special_allowance + custom_earnings
    statutory_deductions = pf_deduction + tds_deduction (from SalaryStructure or StatutoryRule)
    attendance_deductions = (unpaid_leave_days / working_days_in_month) * base_pay
    late_deductions  = late_count * per_late_deduction_amount  (configurable)
    loan_deductions  = sum of pending LoanRepayments scheduled this month
    net_pay          = gross_salary - statutory_deductions - attendance_deductions
                       - late_deductions - loan_deductions + approved_reimbursements
"""
from __future__ import annotations

import logging
from calendar import monthrange
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.db.models.all_models import (
    AttendanceLog,
    LoanRepayment,
    Payroll,
    PayrollAdvance,
    PayrollLineItem,
    PayrollRun,
    Reimbursement,
    SalaryStructure,
    StatutoryRule,
    User,
)

logger = logging.getLogger(__name__)

# ── Constants (configurable via StatutoryRule in future) ──────────────────────
DEFAULT_BASE_SALARY = Decimal("50000.00")
DEFAULT_LATE_DEDUCTION = Decimal("100.00")  # per late day; previously ₹10 hardcode
CENTS = Decimal("0.01")


def _to_decimal(value: Any) -> Decimal:
    """Safely coerce float/Decimal/str → Decimal."""
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


# ─────────────────────────────────────────────────────────────────────────────
# Core single-employee calculation
# ─────────────────────────────────────────────────────────────────────────────

def _get_salary_structure(db: Session, user_id: int, org_id, month: int, year: int) -> Optional[SalaryStructure]:
    """Return the active salary structure for a user applicable to the given month/year."""
    _, last_day = monthrange(year, month)
    period_start = datetime(year, month, 1, tzinfo=timezone.utc)
    period_end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

    return (
        db.query(SalaryStructure)
        .filter(
            SalaryStructure.user_id == user_id,
            SalaryStructure.organization_id == org_id,
            SalaryStructure.is_active.is_(True),
            SalaryStructure.effective_from <= period_end,
            (SalaryStructure.effective_to >= period_start) | (SalaryStructure.effective_to.is_(None))
        )
        .order_by(SalaryStructure.effective_from.desc())
        .first()
    )


def _get_statutory_rules(db: Session, org_id) -> List[StatutoryRule]:
    """Return active statutory rules for an org as of today."""
    now = datetime.now(timezone.utc)
    return (
        db.query(StatutoryRule)
        .filter(
            StatutoryRule.organization_id == org_id,
            StatutoryRule.is_active.is_(True),
            StatutoryRule.effective_from <= now,
        )
        .all()
    )


def _attendance_data(
    db: Session, user_id: int, org_id, month: int, year: int
) -> Tuple[int, int]:
    """
    Returns (late_count, unpaid_leave_days).
    Late count from AttendanceLogs; unpaid leave can be extended later.
    """
    late_count = (
        db.query(func.count(AttendanceLog.id))
        .join(User, AttendanceLog.user_id == User.id)
        .filter(
            User.org_id == org_id,
            AttendanceLog.user_id == user_id,
            AttendanceLog.status == "late",
            extract("month", AttendanceLog.check_in) == month,
            extract("year", AttendanceLog.check_in) == year,
        )
        .scalar()
        or 0
    )
    # Unpaid leave integration point — placeholder; extend with LeaveRequest model
    unpaid_leave_days = 0
    return late_count, unpaid_leave_days


def _pending_loan_repayments(
    db: Session, user_id: int, month: int, year: int
) -> Decimal:
    """Sum pending loan repayments scheduled in the given pay month."""
    advances = (
        db.query(PayrollAdvance.id)
        .filter(PayrollAdvance.user_id == user_id)
        .all()
    )
    advance_ids = [a.id for a in advances]
    if not advance_ids:
        return Decimal("0.00")

    total = (
        db.query(func.sum(LoanRepayment.amount))
        .filter(
            LoanRepayment.advance_id.in_(advance_ids),
            LoanRepayment.status == "pending",
            extract("month", LoanRepayment.scheduled_date) == month,
            extract("year", LoanRepayment.scheduled_date) == year,
        )
        .scalar()
    )
    return _to_decimal(total)


def _approved_reimbursements(
    db: Session, user_id: int, org_id, month: int, year: int
) -> Decimal:
    """Sum approved (unpaid) reimbursements for the pay period."""
    total = (
        db.query(func.sum(Reimbursement.amount))
        .filter(
            Reimbursement.user_id == user_id,
            Reimbursement.org_id == org_id,
            Reimbursement.status == "approved",
            extract("month", Reimbursement.submitted_at) == month,
            extract("year", Reimbursement.submitted_at) == year,
        )
        .scalar()
    )
    return _to_decimal(total)


def calculate_for_user(
    db: Session,
    user: User,
    month: int,
    year: int,
    per_late_deduction: Decimal = DEFAULT_LATE_DEDUCTION,
) -> Dict[str, Any]:
    """
    Compute the complete payroll breakdown for a single user for a given period.
    Returns a dict with all components and the final net_pay using Decimal.
    """
    ss = _get_salary_structure(db, user.id, user.org_id, month, year)

    # ── Earnings ──────────────────────────────────────────────────────────────
    base_pay          = _to_decimal(ss.base_pay if ss else DEFAULT_BASE_SALARY)
    hra               = _to_decimal(ss.hra if ss else Decimal("0.00"))
    special_allowance = _to_decimal(ss.special_allowance if ss else Decimal("0.00"))
    gross_salary      = base_pay + hra + special_allowance

    # ── Statutory deductions (from SalaryStructure or StatutoryRule engine) ───
    pf_deduction  = _to_decimal(ss.pf_deduction if ss else Decimal("0.00"))
    tds_deduction = _to_decimal(ss.tds_deduction if ss else Decimal("0.00"))
    statutory_total = pf_deduction + tds_deduction

    # ── Attendance-based deductions ────────────────────────────────────────────
    late_count, unpaid_leave_days = _attendance_data(db, user.id, user.org_id, month, year)
    working_days = monthrange(year, month)[1]  # calendar days; refine if needed
    late_deduction = _to_decimal(late_count) * per_late_deduction
    unpaid_leave_deduction = (
        (_to_decimal(unpaid_leave_days) / _to_decimal(working_days)) * base_pay
        if working_days > 0
        else Decimal("0.00")
    )

    # ── Loan repayment deductions ──────────────────────────────────────────────
    loan_deduction = _pending_loan_repayments(db, user.id, month, year)

    # ── Reimbursements (additions) ─────────────────────────────────────────────
    reimb_total = _approved_reimbursements(db, user.id, user.org_id, month, year)

    # ── Net ───────────────────────────────────────────────────────────────────
    total_deductions = (
        statutory_total + late_deduction + unpaid_leave_deduction + loan_deduction
    ).quantize(CENTS, rounding=ROUND_HALF_UP)

    net_pay = (gross_salary - total_deductions + reimb_total).quantize(
        CENTS, rounding=ROUND_HALF_UP
    )

    return {
        "user_id":             user.id,
        "month":               month,
        "year":                year,
        "base_salary":         base_pay,
        "hra":                 hra,
        "special_allowance":   special_allowance,
        "gross_salary":        gross_salary,
        "pf_deduction":        pf_deduction,
        "tds_deduction":       tds_deduction,
        "late_count":          late_count,
        "late_deduction":      late_deduction,
        "unpaid_leave_days":   unpaid_leave_days,
        "unpaid_leave_deduction": unpaid_leave_deduction,
        "loan_deduction":      loan_deduction,
        "deductions":          total_deductions,
        "reimbursements_total": reimb_total,
        "total_salary":        net_pay,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Batch payroll generation (replaces the legacy generate endpoint logic)
# ─────────────────────────────────────────────────────────────────────────────

def generate_payroll_for_org(
    db: Session,
    org_id,
    month: int,
    year: int,
    executed_by_user_id: int,
    payroll_run: Optional[PayrollRun] = None,
) -> List[Payroll]:
    """
    Generate (or regenerate) Payroll records for all active users in an org.
    Writes PayrollLineItems for full auditability.
    Idempotent: updates existing rows instead of creating duplicates.
    """
    users = (
        db.query(User)
        .filter(User.org_id == org_id, User.is_deleted == 0)
        .all()
    )

    existing_map: Dict[int, Payroll] = {
        p.user_id: p
        for p in db.query(Payroll).filter(
            Payroll.org_id == org_id,
            Payroll.month == month,
            Payroll.year == year,
        ).all()
    }

    results: List[Payroll] = []
    run_total_gross = Decimal("0.00")
    run_total_deductions = Decimal("0.00")
    run_total_net = Decimal("0.00")

    try:
        for user in users:
            data = calculate_for_user(db, user, month, year)
            
            if user.id in existing_map:
                rec = existing_map[user.id]
                rec.base_salary         = data["base_salary"]
                rec.deductions          = data["deductions"]
                rec.reimbursements_total = data["reimbursements_total"]
                rec.total_salary        = data["total_salary"]
                rec.status              = "pending"
                # Delete old line items and recreate
                db.query(PayrollLineItem).filter(
                    PayrollLineItem.payroll_id == rec.id
                ).delete(synchronize_session=False)
            else:
                rec = Payroll(
                    user_id=user.id,
                    org_id=org_id,
                    month=month,
                    year=year,
                    base_salary=data["base_salary"],
                    deductions=data["deductions"],
                    reimbursements_total=data["reimbursements_total"],
                    total_salary=data["total_salary"],
                    status="pending",
                )
                db.add(rec)
                db.flush()  # get rec.id
            
            # Persist line items for audit
            line_items = [
                PayrollLineItem(payroll_id=rec.id, component_name="Basic Pay",         component_type="earning",    amount=data["base_salary"]),
                PayrollLineItem(payroll_id=rec.id, component_name="HRA",               component_type="earning",    amount=data["hra"]),
                PayrollLineItem(payroll_id=rec.id, component_name="Special Allowance", component_type="earning",    amount=data["special_allowance"]),
                PayrollLineItem(payroll_id=rec.id, component_name="Provident Fund",    component_type="statutory",  amount=-data["pf_deduction"]),
                PayrollLineItem(payroll_id=rec.id, component_name="TDS",               component_type="tax",        amount=-data["tds_deduction"]),
                PayrollLineItem(payroll_id=rec.id, component_name="Late Deduction",    component_type="deduction",  amount=-data["late_deduction"],       description=f"{data['late_count']} late days"),
                PayrollLineItem(payroll_id=rec.id, component_name="Unpaid Leave",      component_type="deduction",  amount=-data["unpaid_leave_deduction"],description=f"{data['unpaid_leave_days']} unpaid day(s)"),
                PayrollLineItem(payroll_id=rec.id, component_name="Loan Repayment",    component_type="deduction",  amount=-data["loan_deduction"]),
                PayrollLineItem(payroll_id=rec.id, component_name="Reimbursements",    component_type="earning",    amount=data["reimbursements_total"]),
            ]
            for li in line_items:
                db.add(li)

            # Mark approved reimbursements as paid
            db.query(Reimbursement).filter(
                Reimbursement.user_id == user.id,
                Reimbursement.org_id == org_id,
                Reimbursement.status == "approved",
                extract("month", Reimbursement.submitted_at) == month,
                extract("year", Reimbursement.submitted_at) == year,
            ).update({"status": "paid"}, synchronize_session=False)

            # Mark due loan repayments as paid
            if data["loan_deduction"] > 0:
                advances = db.query(PayrollAdvance.id).filter(
                    PayrollAdvance.user_id == user.id
                ).all()
                advance_ids = [a.id for a in advances]
                if advance_ids:
                    db.query(LoanRepayment).filter(
                        LoanRepayment.advance_id.in_(advance_ids),
                        LoanRepayment.status == "pending",
                        extract("month", LoanRepayment.scheduled_date) == month,
                        extract("year", LoanRepayment.scheduled_date) == year,
                    ).update({"status": "paid", "payroll_id": rec.id}, synchronize_session=False)

            run_total_gross       += data["gross_salary"]
            run_total_deductions  += data["deductions"]
            run_total_net         += data["total_salary"]
            results.append(rec)

        db.commit()

        # Update PayrollRun totals
        if payroll_run:
            payroll_run.total_gross      = run_total_gross
            payroll_run.total_deductions = run_total_deductions
            payroll_run.total_net        = run_total_net
            payroll_run.status           = "calculated"
            db.commit()

        logger.info(
            "PayrollEngine: generated %d payslips for org=%s month=%s/%s",
            len(results), org_id, month, year,
        )
        return results

    except Exception as e:
        db.rollback()
        logger.exception("PayrollEngine: calculation failed for org_id=%s, month=%s, year=%s", org_id, month, year)
        if payroll_run:
            try:
                # Need a new session context to update the run status without committing broken state
                payroll_run.status = "failed"
                db.add(payroll_run)
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("PayrollEngine: Failed to update PayrollRun status to failed")
        raise e
