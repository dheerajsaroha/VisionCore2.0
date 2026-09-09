"""
org_identity_router.py — VisionCore 3.0 Organization & Identity REST API Router

Provides standardized API endpoints for Organization Provisioning, Organizational Structure,
Positions, Multi-Type Identities, Employment Lifecycles, and Organizational Hierarchy Trees.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.db.models.all_models import User
from app.services.identity_employment_service import (
    employment_service,
    identity_service,
    position_service,
)
from app.services.organization_domain_service import (
    branch_service,
    business_unit_service,
    cost_center_service,
    hierarchy_service,
    legal_entity_service,
    organization_provisioning_service,
    team_service,
)

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ProvisionRequest(BaseModel):
    org_name: str
    legal_id: str
    admin_email: str
    admin_name: str
    primary_color: str = "#4F46E5"


class StateTransitionRequest(BaseModel):
    new_state: str
    reason: Optional[str] = None


class LegalEntityCreate(BaseModel):
    name: str
    legal_name: str
    registration_number: str
    tax_id: Optional[str] = None
    country: str = "India"
    currency: str = "INR"


class BusinessUnitCreate(BaseModel):
    code: str
    name: str
    legal_entity_id: Optional[UUID] = None
    description: Optional[str] = None


class BranchCreate(BaseModel):
    code: str
    name: str
    branch_type: str = "HQ"
    address: Optional[str] = None
    city: Optional[str] = None
    timezone: str = "Asia/Kolkata"


class TeamCreate(BaseModel):
    dept_id: int
    name: str
    description: Optional[str] = None


class CostCenterCreate(BaseModel):
    code: str
    name: str
    annual_budget: float = 0.0


class PositionCreate(BaseModel):
    code: str
    title: str
    dept_id: Optional[int] = None
    reporting_position_id: Optional[int] = None
    grade: Optional[str] = None
    band: Optional[str] = None
    min_salary: Optional[float] = None
    max_salary: Optional[float] = None
    headcount_capacity: int = 1


class HireEmployeeRequest(BaseModel):
    employment_type: str = "EMPLOYEE"
    joining_date: str
    designation: Optional[str] = None
    position_id: Optional[int] = None
    business_unit_id: Optional[int] = None
    branch_id: Optional[int] = None
    cost_center_id: Optional[int] = None


class TransferEmployeeRequest(BaseModel):
    new_dept_id: Optional[int] = None
    new_position_id: Optional[int] = None
    reason: str


class PromoteEmployeeRequest(BaseModel):
    new_designation: str
    new_position_id: Optional[int] = None
    reason: str


class SuspendIdentityRequest(BaseModel):
    reason: str


# ── Organization & Provisioning Endpoints ─────────────────────────────────────

@router.post("/organizations/provision")
def provision_organization(
    req: ProvisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Trigger complete stateful organization provisioning workflow."""
    if current_user.role.name not in ["Admin", "SuperAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return organization_provisioning_service.execute_full_provisioning_workflow(
        db=db,
        org_name=req.org_name,
        legal_id=req.legal_id,
        admin_email=req.admin_email,
        admin_name=req.admin_name,
        primary_color=req.primary_color,
    )


@router.get("/organizations/hierarchy")
def get_organization_hierarchy(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get complete visual hierarchy tree for current user's organization."""
    return hierarchy_service.build_org_tree(db=db, org_id=current_user.org_id)


@router.post("/organizations/state-transition")
def transition_organization_state(
    req: StateTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Transition organization lifecycle state."""
    if current_user.role.name != "SuperAdmin":
        raise HTTPException(status_code=403, detail="SuperAdmin role required")
    return organization_provisioning_service.transition_state(
        db=db, org_id=current_user.org_id, new_state=req.new_state
    )


# ── Structural Entities Endpoints ─────────────────────────────────────────────

@router.get("/legal-entities")
def list_legal_entities(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return legal_entity_service.list(db, current_user.org_id)


@router.post("/legal-entities")
def create_legal_entity(
    req: LegalEntityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if current_user.role.name not in ["Admin", "SuperAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return legal_entity_service.create(db, current_user.org_id, req.model_dump())


@router.get("/business-units")
def list_business_units(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return business_unit_service.list(db, current_user.org_id)


@router.post("/business-units")
def create_business_unit(
    req: BusinessUnitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if current_user.role.name not in ["Admin", "SuperAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return business_unit_service.create(db, current_user.org_id, req.model_dump())


@router.get("/branches")
def list_branches(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return branch_service.list(db, current_user.org_id)


@router.post("/branches")
def create_branch(
    req: BranchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if current_user.role.name not in ["Admin", "SuperAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return branch_service.create(db, current_user.org_id, req.model_dump())


@router.get("/teams")
def list_teams(
    dept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return team_service.list_by_dept(db, current_user.org_id, dept_id)


@router.post("/teams")
def create_team(
    req: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if current_user.role.name not in ["Admin", "SuperAdmin", "Manager"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return team_service.create(db, current_user.org_id, req.model_dump())


@router.get("/cost-centers")
def list_cost_centers(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return cost_center_service.list(db, current_user.org_id)


@router.post("/cost-centers")
def create_cost_center(
    req: CostCenterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if current_user.role.name not in ["Admin", "SuperAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return cost_center_service.create(db, current_user.org_id, req.model_dump())


# ── Position Endpoints ────────────────────────────────────────────────────────

@router.get("/positions")
def list_positions(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    positions = position_service.list_positions(db, current_user.org_id)
    return [
        {
            "id": p.id,
            "code": p.code,
            "title": p.title,
            "dept_id": p.dept_id,
            "reporting_position_id": p.reporting_position_id,
            "grade": p.grade,
            "band": p.band,
            "min_salary": float(p.min_salary) if p.min_salary is not None else None,
            "max_salary": float(p.max_salary) if p.max_salary is not None else None,
            "headcount_capacity": p.headcount_capacity,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in positions
    ]


@router.post("/positions", status_code=201)
def create_position(
    req: PositionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if current_user.role.name not in ["Admin", "SuperAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    p = position_service.create_position(db, current_user.org_id, req.model_dump())
    return {
        "id": p.id,
        "code": p.code,
        "title": p.title,
        "dept_id": p.dept_id,
        "reporting_position_id": p.reporting_position_id,
        "grade": p.grade,
        "band": p.band,
        "min_salary": float(p.min_salary) if p.min_salary is not None else None,
        "max_salary": float(p.max_salary) if p.max_salary is not None else None,
        "headcount_capacity": p.headcount_capacity,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


# ── Employment Endpoints ────────────────────────────────----------------──────

@router.get("/employment/{user_id}")
def get_employment_record(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    rec = employment_service.get_employment_record(db, current_user.org_id, user_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Employment record not found")
    return rec


@router.post("/employment/{user_id}/hire")
def hire_employee(
    user_id: int,
    req: HireEmployeeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if current_user.role.name not in ["Admin", "SuperAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    data = req.model_dump()
    data["joining_date"] = (
        data["joining_date"] if "joining_date" in data else None
    )
    return employment_service.hire_employee(db, current_user.org_id, user_id, data)


@router.post("/employment/{user_id}/transfer")
def transfer_employee(
    user_id: int,
    req: TransferEmployeeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if current_user.role.name not in ["Admin", "SuperAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return employment_service.transfer_employee(
        db, current_user.org_id, user_id, req.new_dept_id, req.new_position_id, req.reason
    )


@router.post("/employment/{user_id}/promote")
def promote_employee(
    user_id: int,
    req: PromoteEmployeeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if current_user.role.name not in ["Admin", "SuperAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return employment_service.promote_employee(
        db, current_user.org_id, user_id, req.new_designation, req.new_position_id, req.reason
    )


# ── Identity Lifecycle Endpoints ──────────────────────────────────────────────

@router.post("/identity/{user_id}/activate")
def activate_identity(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if current_user.role.name not in ["Admin", "SuperAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return identity_service.activate_identity(
        db, current_user.org_id, user_id, performed_by_id=current_user.id
    )


@router.post("/identity/{user_id}/suspend")
def suspend_identity(
    user_id: int,
    req: SuspendIdentityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if current_user.role.name not in ["Admin", "SuperAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return identity_service.suspend_identity(
        db, current_user.org_id, user_id, performed_by_id=current_user.id, reason=req.reason
    )


@router.get("/identity/{user_id}/timeline")
def get_identity_timeline(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return identity_service.get_identity_timeline(db, current_user.org_id, user_id)


@router.get("/identity/{user_id}/trusted-devices")
def get_trusted_devices(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return identity_service.get_trusted_devices(db, user_id)
