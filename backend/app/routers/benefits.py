"""
benefits.py — PI-6 Benefits Management Router

Endpoints:
  - BenefitsPlan CRUD (Admin only for write)
  - BenefitsEnrollment (employees can self-enroll; admin can view all)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.db.models.all_models import (
    BenefitsEnrollment,
    BenefitsPlan,
    User,
)

router = APIRouter()
logger = logging.getLogger(__name__)


from app.services.audit_service import audit_service

# ── Auth helpers ──────────────────────────────────────────────────────────────
# We use deps.require_permission(...) via Depends in the endpoints
# rather than manual role string checks.


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class BenefitsPlanCreate(BaseModel):
    plan_name: str
    plan_type: str = "health"
    description: Optional[str] = None
    employer_contribution: float = 0.0
    employee_contribution: float = 0.0

class BenefitsPlanOut(BaseModel):
    id: int
    plan_name: str
    plan_type: str
    description: Optional[str]
    employer_contribution: float
    employee_contribution: float
    is_active: bool
    class Config: from_attributes = True


class BenefitsEnrollmentCreate(BaseModel):
    plan_id: int
    coverage_tier: str = "individual"
    elected_amount: float = 0.0

class BenefitsEnrollmentOut(BaseModel):
    id: int
    user_id: int
    plan_id: int
    coverage_tier: str
    elected_amount: float
    effective_from: datetime
    effective_to: Optional[datetime]
    status: str
    class Config: from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# Benefits Plans
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/plans", response_model=List[BenefitsPlanOut], tags=["benefits"])
def list_benefits_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("benefits.view")),
) -> Any:
    return (
        db.query(BenefitsPlan)
        .filter(BenefitsPlan.organization_id == current_user.org_id)
        .all()
    )


@router.post("/plans", response_model=BenefitsPlanOut, status_code=201, tags=["benefits"])
def create_benefits_plan(
    payload: BenefitsPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("benefits.manage")),
) -> Any:
    obj = BenefitsPlan(
        organization_id=current_user.org_id,
        **payload.model_dump(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)

    audit_service.log_event(
        actor=current_user,
        action="create",
        target_type="benefits_plan",
        target_id=str(obj.id),
        after_state=payload.model_dump(),
    )
    return obj


@router.patch("/plans/{plan_id}", response_model=BenefitsPlanOut, tags=["benefits"])
def update_benefits_plan(
    plan_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("benefits.manage")),
) -> Any:
    plan = db.query(BenefitsPlan).filter(
        BenefitsPlan.id == plan_id,
        BenefitsPlan.organization_id == current_user.org_id,
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Benefits plan not found.")
        
    before_state = {k: getattr(plan, k) for k in payload.keys() if hasattr(plan, k)}
    allowed = {"plan_name", "description", "employer_contribution", "employee_contribution", "is_active"}
    for key, val in payload.items():
        if key in allowed:
            setattr(plan, key, val)
    db.commit()
    db.refresh(plan)

    audit_service.log_event(
        actor=current_user,
        action="update",
        target_type="benefits_plan",
        target_id=str(plan.id),
        before_state=before_state,
        after_state=payload,
    )
    return plan


@router.delete("/plans/{plan_id}", status_code=204, tags=["benefits"])
def deactivate_benefits_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("benefits.manage")),
) -> None:
    plan = db.query(BenefitsPlan).filter(
        BenefitsPlan.id == plan_id,
        BenefitsPlan.organization_id == current_user.org_id,
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Benefits plan not found.")
    plan.is_active = False
    db.commit()

    audit_service.log_event(
        actor=current_user,
        action="deactivate",
        target_type="benefits_plan",
        target_id=str(plan_id),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Benefits Enrollments
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/enrollments", response_model=List[BenefitsEnrollmentOut], tags=["benefits"])
def list_my_enrollments(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Employees see their own enrollments; admins see all."""
    query = db.query(BenefitsEnrollment).filter(
        BenefitsEnrollment.organization_id == current_user.org_id
    )
    role = (current_user.role.name if current_user.role else "").strip().lower()
    if role not in {"admin", "superadmin", "super admin", "manager"}:
        query = query.filter(BenefitsEnrollment.user_id == current_user.id)
    return query.all()


@router.post("/enrollments", response_model=BenefitsEnrollmentOut, status_code=201, tags=["benefits"])
def enroll_in_plan(
    payload: BenefitsEnrollmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    # Validate plan belongs to org
    plan = db.query(BenefitsPlan).filter(
        BenefitsPlan.id == payload.plan_id,
        BenefitsPlan.organization_id == current_user.org_id,
        BenefitsPlan.is_active.is_(True),
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Active benefits plan not found.")

    # Check if already enrolled in this plan
    existing = db.query(BenefitsEnrollment).filter(
        BenefitsEnrollment.user_id == current_user.id,
        BenefitsEnrollment.plan_id == payload.plan_id,
        BenefitsEnrollment.status == "active",
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already enrolled in this plan.")

    obj = BenefitsEnrollment(
        organization_id=current_user.org_id,
        user_id=current_user.id,
        plan_id=payload.plan_id,
        coverage_tier=payload.coverage_tier,
        elected_amount=payload.elected_amount,
        effective_from=datetime.now(timezone.utc),
        status="active",
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)

    audit_service.log_event(
        actor=current_user,
        action="enroll",
        target_type="benefits_enrollment",
        target_id=str(obj.id),
        after_state=payload.model_dump(),
    )
    return obj


@router.patch("/enrollments/{enrollment_id}/waive", response_model=BenefitsEnrollmentOut, tags=["benefits"])
def waive_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    enrollment = db.query(BenefitsEnrollment).filter(
        BenefitsEnrollment.id == enrollment_id,
        BenefitsEnrollment.organization_id == current_user.org_id,
        BenefitsEnrollment.user_id == current_user.id,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found.")
    enrollment.status = "waived"
    enrollment.effective_to = datetime.now(timezone.utc)
    db.commit()
    db.refresh(enrollment)

    audit_service.log_event(
        actor=current_user,
        action="waive",
        target_type="benefits_enrollment",
        target_id=str(enrollment.id),
        after_state={"status": "waived"},
    )
    return enrollment
