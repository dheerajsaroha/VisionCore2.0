from typing import Any, List
import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    status,
)
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.crud.crud_payroll import payroll as crud_payroll
from app.api import deps
from app.schema.payroll import (
    PayrollResponse,
    PayrollCreate,
    PayrollUpdate,
    PayrollGenerationRequest,
)

from app.db.models.all_models import (
    User,
    Payroll,
    Reimbursement,
    AttendanceLog,
    BlockchainAuditLog,
)
from app.db.database import get_db, SessionLocal
from app.services import payroll_engine
from app.services.audit_service import audit_service

router = APIRouter()
logger = logging.getLogger(__name__)


def is_admin_or_manager(user: User) -> bool:
    if user.role is None:
        return False

    role = user.role.name.strip().lower()

    return role in {
        "admin",
        "manager",
        "superadmin",
        "super admin",
    }


async def background_blockchain_anchor(
    ref_id: int,
    payload: dict,
    ref_type: str,
):
    """
    Background blockchain anchoring.
    """

    db = SessionLocal()

    try:
        tx_hash = blockchain_service.anchor_record(
            ref_id,
            ref_type,
            payload,
        )

        audit = BlockchainAuditLog(
            ref_id=ref_id,
            ref_type=ref_type,
            record_hash=blockchain_service.generate_record_hash(
                payload
            ),
            tx_hash=tx_hash,
        )

        db.add(audit)
        db.commit()

    except Exception:
        db.rollback()

        logger.exception(
            "Blockchain anchoring failed for %s:%s",
            ref_type,
            ref_id,
        )

    finally:
        db.close()


@router.get("/", response_model=List[PayrollResponse])
def read_payrolls(
    db: Session = Depends(get_db),
    month: int | None = None,
    year: int | None = None,
    current_user: User = Depends(deps.require_permission("payroll.view")),
) -> Any:
    if not is_admin_or_manager(current_user):
        return (
            db.query(Payroll)
            .filter(Payroll.user_id == current_user.id)
            .all()
        )
    return crud_payroll.get_multi_by_org(
        db, org_id=current_user.org_id, month=month, year=year,
    )


@router.post("/generate", response_model=List[PayrollResponse])
async def generate_payroll(
    *,
    payload: PayrollGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("payroll.generate")),
    background_tasks: BackgroundTasks,
) -> Any:
    month = payload.month
    year = payload.year

    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12.")

    try:
        results = payroll_engine.generate_payroll_for_org(
            db=db,
            org_id=current_user.org_id,
            month=month,
            year=year,
            executed_by_user_id=current_user.id,
        )
        audit_service.log_event(
            actor=current_user,
            action="generate",
            target_type="payroll",
            target_id=f"{month}/{year}",
            after_state={"month": month, "year": year, "count": len(results)},
        )
        return results
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Payroll generation failed: %s", str(exc))
        raise HTTPException(status_code=500, detail="Payroll generation failed.")


@router.patch("/{payroll_id}", response_model=PayrollResponse)
def update_payroll_status(
    *,
    db: Session = Depends(get_db),
    payroll_id: int,
    status_in: PayrollUpdate,
    current_user: User = Depends(deps.require_permission("payroll.manage")),
    background_tasks: BackgroundTasks,
) -> Any:
    try:
        payroll_obj = (
            db.query(Payroll)
            .filter(Payroll.id == payroll_id, Payroll.org_id == current_user.org_id)
            .first()
        )
        if not payroll_obj:
            raise HTTPException(status_code=404, detail="Payroll not found")

        old_status = payroll_obj.status
        updated = crud_payroll.update(db=db, db_obj=payroll_obj, obj_in=status_in)
        db.commit()

        audit_service.log_event(
            actor=current_user,
            action="update_status",
            target_type="payroll",
            target_id=str(updated.id),
            before_state={"status": old_status},
            after_state={"status": updated.status},
        )
        return updated
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Payroll update failed: %s", str(exc))
        raise HTTPException(status_code=500, detail="Failed to update payroll.")


# ── PAYSLIPS ──
@router.get(
    "/{payroll_id}/payslip",
    response_model=dict,
)
def get_payslip(
    payroll_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """Retrieve payslip details for a given payroll run."""
    from app.db.models.all_models import Payslip
    
    payroll_obj = db.query(Payroll).filter(
        Payroll.id == payroll_id,
        Payroll.org_id == current_user.org_id
    ).first()
    
    if not payroll_obj:
        raise HTTPException(status_code=404, detail="Payroll not found")
        
    if not is_admin_or_manager(current_user) and payroll_obj.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized to view this payslip")

    payslip = db.query(Payslip).filter(Payslip.payroll_id == payroll_id).first()
    
    if not payslip:
        # For now, just return a generated representation if not formally saved
        return {
            "payroll_id": payroll_obj.id,
            "month": payroll_obj.month,
            "year": payroll_obj.year,
            "base_salary": float(payroll_obj.base_salary),
            "total_salary": float(payroll_obj.total_salary),
            "status": payroll_obj.status,
            "message": "Payslip document not yet generated."
        }
        
    return {
        "payroll_id": payslip.payroll_id,
        "file_url": payslip.file_url,
        "generated_at": payslip.generated_at
    }


# ── PAY GRADES & SALARY STRUCTURE ──
@router.post("/grades")
def create_pay_grade(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("payroll.manage")),
):
    """Create a new pay grade."""
    from app.db.models.all_models import PayGrade
    grade = PayGrade(
        organization_id=current_user.org_id,
        grade_name=payload["grade_name"],
        min_salary=payload["min_salary"],
        max_salary=payload["max_salary"]
    )
    db.add(grade)
    db.commit()
    db.refresh(grade)
    return {"id": grade.id, "grade_name": grade.grade_name, "min_salary": grade.min_salary, "max_salary": grade.max_salary}


@router.get("/grades")
def list_pay_grades(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """List pay grades for current org."""
    from app.db.models.all_models import PayGrade
    grades = db.query(PayGrade).filter(PayGrade.organization_id == current_user.org_id).all()
    return [{"id": g.id, "grade_name": g.grade_name, "min_salary": g.min_salary, "max_salary": g.max_salary} for g in grades]


@router.post("/structure")
def create_salary_structure(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("payroll.manage")),
):
    """Assign or update employee salary structure."""
    from app.db.models.all_models import SalaryStructure
    from decimal import Decimal
    base = Decimal(str(payload["base_pay"]))
    hra = Decimal(str(payload.get("hra", base * Decimal("0.4"))))
    special = Decimal(str(payload.get("special_allowance", "0.0")))
    pf = Decimal(str(payload.get("pf_deduction", base * Decimal("0.12"))))
    tds = Decimal(str(payload.get("tds_deduction", base * Decimal("0.10"))))
    gross = base + hra + special
    net = gross - pf - tds

    # Tenant-scoped query: filter by both user_id AND org_id
    struct = db.query(SalaryStructure).filter(
        SalaryStructure.user_id == payload["user_id"],
        SalaryStructure.organization_id == current_user.org_id
    ).first()
    if not struct:
        struct = SalaryStructure(
            organization_id=current_user.org_id,
            user_id=payload["user_id"],
            pay_grade_id=payload.get("pay_grade_id"),
            base_pay=base, hra=hra, special_allowance=special,
            pf_deduction=pf, tds_deduction=tds,
            gross_salary=gross, net_salary=net
        )
        db.add(struct)
    else:
        struct.base_pay=base; struct.hra=hra; struct.special_allowance=special
        struct.pf_deduction=pf; struct.tds_deduction=tds
        struct.gross_salary=gross; struct.net_salary=net

    db.commit()
    db.refresh(struct)
    audit_service.log_event(
        actor=current_user, action="upsert",
        target_type="salary_structure", target_id=str(struct.id),
        after_state={"user_id": struct.user_id, "gross_salary": float(gross)},
    )
    return {"id": struct.id, "user_id": struct.user_id, "base_pay": float(struct.base_pay), "gross_salary": float(struct.gross_salary), "net_salary": float(struct.net_salary)}


# ── PAYROLL ADVANCES ──
@router.post("/advances", status_code=201)
def request_payroll_advance(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """Request salary advance / loan."""
    from app.db.models.all_models import PayrollAdvance
    adv = PayrollAdvance(
        organization_id=current_user.org_id,
        user_id=current_user.id,
        amount=payload["amount"],
        reason=payload["reason"],
        status="pending"
    )
    db.add(adv)
    db.commit()
    db.refresh(adv)
    return {"id": adv.id, "amount": adv.amount, "status": adv.status}


@router.get("/advances")
def list_payroll_advances(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """List payroll advance requests."""
    from app.db.models.all_models import PayrollAdvance
    q = db.query(PayrollAdvance).filter(PayrollAdvance.organization_id == current_user.org_id)
    role_name = current_user.role.name if current_user.role else ""
    if role_name not in ["Admin", "SuperAdmin", "OrgAdmin", "Manager"]:
        q = q.filter(PayrollAdvance.user_id == current_user.id)
    advances = q.order_by(PayrollAdvance.created_at.desc()).all()
    return [{
        "id": a.id,
        "user_id": a.user_id,
        "user_name": a.user.full_name if a.user else f"User #{a.user_id}",
        "amount": a.amount,
        "reason": a.reason,
        "status": a.status,
        "created_at": a.created_at
    } for a in advances]


@router.post("/advances/{advance_id}/approve")
def approve_payroll_advance(
    advance_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("payroll.manage")),
):
    """Approve or reject salary advance request."""
    from app.db.models.all_models import PayrollAdvance
    adv = db.query(PayrollAdvance).filter(
        PayrollAdvance.id == advance_id,
        PayrollAdvance.organization_id == current_user.org_id
    ).first()
    if not adv:
        raise HTTPException(status_code=404, detail="Advance request not found")

    old_status = adv.status
    adv.status = payload.get("status", "approved")
    adv.approved_by_user_id = current_user.id
    db.commit()
    db.refresh(adv)

    audit_service.log_event(
        actor=current_user, action=adv.status,
        target_type="payroll_advance", target_id=str(adv.id),
        before_state={"status": old_status},
        after_state={"status": adv.status},
    )
    return {"id": adv.id, "status": adv.status}
