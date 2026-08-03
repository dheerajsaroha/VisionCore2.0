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
from app.db.database import (
    get_db,
    SessionLocal,
)
from app.services.blockchain import blockchain_service

router = APIRouter()

logger = logging.getLogger(__name__)

DEFAULT_BASE_SALARY = 50000.0
LATE_DEDUCTION_AMOUNT = 10.0


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
    current_user: User = Depends(
        deps.get_current_active_user
    ),
) -> Any:

    if not is_admin_or_manager(current_user):
        return (
            db.query(Payroll)
            .filter(
                Payroll.user_id == current_user.id
            )
            .all()
        )

    return crud_payroll.get_multi_by_org(
        db,
        org_id=current_user.org_id,
        month=month,
        year=year,
    )


@router.post(
    "/generate",
    response_model=List[PayrollResponse],
)
async def generate_payroll(
    *,
    payload: PayrollGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        deps.get_current_active_user
    ),
    background_tasks: BackgroundTasks,
) -> Any:

    month = payload.month
    year = payload.year

    if not is_admin_or_manager(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Manager privileges required.",
        )

    if month < 1 or month > 12:
        raise HTTPException(
            status_code=400,
            detail="Month must be between 1 and 12.",
        )

    try:

        late_counts = (
            db.query(
                AttendanceLog.user_id,
                func.count(
                    AttendanceLog.id
                ).label("count"),
            )
            .join(User)
            .filter(
                User.org_id == current_user.org_id,
                AttendanceLog.status == "late",
                func.extract(
                    "month",
                    AttendanceLog.check_in,
                )
                == month,
                func.extract(
                    "year",
                    AttendanceLog.check_in,
                )
                == year,
            )
            .group_by(
                AttendanceLog.user_id
            )
            .all()
        )

        late_map = {
            row.user_id: row.count
            for row in late_counts
        }

        reimb_sums = (
            db.query(
                Reimbursement.user_id,
                func.sum(
                    Reimbursement.amount
                ).label("total"),
            )
            .filter(
                Reimbursement.org_id
                == current_user.org_id,
                Reimbursement.status
                == "approved",
                func.extract(
                    "month",
                    Reimbursement.submitted_at,
                )
                == month,
                func.extract(
                    "year",
                    Reimbursement.submitted_at,
                )
                == year,
            )
            .group_by(
                Reimbursement.user_id
            )
            .all()
        )

        reimb_map = {
            row.user_id: float(
                row.total or 0
            )
            for row in reimb_sums
        }

        users = (
            db.query(User)
            .filter(
                User.org_id
                == current_user.org_id,
                User.is_deleted == 0,
            )
            .all()
        )

        existing_count = (
            db.query(Payroll)
            .filter(
                Payroll.org_id
                == current_user.org_id,
                Payroll.month == month,
                Payroll.year == year,
            )
            .count()
        )

        if existing_count > 0:
            logger.warning(
                "Regenerating payroll for %s/%s",
                month,
                year,
            )

        existing_payrolls = {
            p.user_id: p
            for p in (
                db.query(Payroll)
                .filter(
                    Payroll.org_id
                    == current_user.org_id,
                    Payroll.month == month,
                    Payroll.year == year,
                )
                .all()
            )
        }

        results = []
        blockchain_jobs = []

        for u in users:

            base_salary = DEFAULT_BASE_SALARY

            deductions = (
                float(
                    late_map.get(u.id, 0)
                )
                * LATE_DEDUCTION_AMOUNT
            )

            reimb_total = reimb_map.get(
                u.id,
                0.0,
            )

            total_salary = (
                base_salary
                - deductions
                + reimb_total
            )

            existing = existing_payrolls.get(
                u.id
            )

            if existing:

                existing.base_salary = (
                    base_salary
                )

                existing.deductions = (
                    deductions
                )

                existing.reimbursements_total = (
                    reimb_total
                )

                existing.total_salary = (
                    total_salary
                )

                payroll_obj = existing

            else:

                payroll_obj = crud_payroll.create(
                    db,
                    obj_in=PayrollCreate(
                        user_id=u.id,
                        month=month,
                        year=year,
                        base_salary=base_salary,
                        deductions=deductions,
                        reimbursements_total=reimb_total,
                        total_salary=total_salary,
                    ),
                    org_id=u.org_id,
                )

            db.flush()

            results.append(
                payroll_obj
            )

            blockchain_jobs.append(
                (
                    payroll_obj.id,
                    {
                        "id": payroll_obj.id,
                        "user": getattr(
                            u,
                            "username",
                            str(u.id),
                        ),
                        "total": total_salary,
                    },
                )
            )

        db.commit()

        for payroll_id, payload in blockchain_jobs:

            background_tasks.add_task(
                background_blockchain_anchor,
                payroll_id,
                payload,
                "payroll",
            )

        return results

    except Exception as exc:

        db.rollback()

        logger.exception(
            "Payroll generation failed: %s",
            str(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payroll generation failed.",
        )


@router.patch(
    "/{payroll_id}",
    response_model=PayrollResponse,
)
def update_payroll_status(
    *,
    db: Session = Depends(get_db),
    payroll_id: int,
    status_in: PayrollUpdate,
    current_user: User = Depends(
        deps.get_current_active_user
    ),
    background_tasks: BackgroundTasks,
) -> Any:

    if not is_admin_or_manager(
        current_user
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Manager privileges required.",
        )

    try:

        payroll_obj = (
            db.query(Payroll)
            .filter(
                Payroll.id == payroll_id,
                Payroll.org_id
                == current_user.org_id,
            )
            .first()
        )

        if not payroll_obj:
            raise HTTPException(
                status_code=404,
                detail="Payroll not found",
            )

<<<<<<< HEAD

# ── PAY GRADES & SALARY STRUCTURE ──
@router.post("/grades")
def create_pay_grade(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """Create a new pay grade."""
    if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

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
    current_user: User = Depends(deps.get_current_active_user)
):
    """Assign or update employee salary structure."""
    if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    from app.db.models.all_models import SalaryStructure
    base = float(payload["base_pay"])
    hra = float(payload.get("hra", base * 0.4))
    special = float(payload.get("special_allowance", 0.0))
    pf = float(payload.get("pf_deduction", base * 0.12))
    tds = float(payload.get("tds_deduction", base * 0.10))
    gross = base + hra + special
    net = gross - pf - tds

    struct = db.query(SalaryStructure).filter(SalaryStructure.user_id == payload["user_id"]).first()
    if not struct:
        struct = SalaryStructure(
            organization_id=current_user.org_id,
            user_id=payload["user_id"],
            pay_grade_id=payload.get("pay_grade_id"),
            base_pay=base,
            hra=hra,
            special_allowance=special,
            pf_deduction=pf,
            tds_deduction=tds,
            gross_salary=gross,
            net_salary=net
        )
        db.add(struct)
    else:
        struct.base_pay = base
        struct.hra = hra
        struct.special_allowance = special
        struct.pf_deduction = pf
        struct.tds_deduction = tds
        struct.gross_salary = gross
        struct.net_salary = net

    db.commit()
    db.refresh(struct)
    return {
        "id": struct.id,
        "user_id": struct.user_id,
        "base_pay": struct.base_pay,
        "gross_salary": struct.gross_salary,
        "net_salary": struct.net_salary
    }


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
    if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "Manager"]:
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
    current_user: User = Depends(deps.get_current_active_user)
):
    """Approve or reject salary advance request."""
    if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "Manager"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    from app.db.models.all_models import PayrollAdvance
    adv = db.query(PayrollAdvance).filter(
        PayrollAdvance.id == advance_id,
        PayrollAdvance.organization_id == current_user.org_id
    ).first()

    if not adv:
        raise HTTPException(status_code=404, detail="Advance request not found")

    adv.status = payload.get("status", "approved")
    adv.approved_by_user_id = current_user.id
    db.commit()
    db.refresh(adv)
    return {"id": adv.id, "status": adv.status}


=======
        updated = crud_payroll.update(
            db=db,
            db_obj=payroll_obj,
            obj_in=status_in,
        )

        db.commit()

        payload = {
            "id": updated.id,
            "status": updated.status,
            "by": getattr(
                current_user,
                "username",
                str(current_user.id),
            ),
        }

        background_tasks.add_task(
            background_blockchain_anchor,
            updated.id,
            payload,
            "payroll",
        )

        return updated

    except HTTPException:
        raise

    except Exception as exc:

        db.rollback()

        logger.exception(
            "Payroll update failed: %s",
            str(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update payroll.",
        )
>>>>>>> refs/remotes/origin/main
