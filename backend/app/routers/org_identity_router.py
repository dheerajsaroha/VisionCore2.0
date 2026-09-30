"""
org_identity_router.py — VisionCore 3.0 Organization & Identity REST API Router

Provides standardized API endpoints for Organization Provisioning, Organizational Structure,
Positions, Multi-Type Identities, Employment Lifecycles, and Organizational Hierarchy Trees.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.db.models.all_models import User
from app.schema.user import UserResponse
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


class IdentityTimelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    org_id: UUID
    user_id: int
    event_type: str
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    performed_by_id: Optional[int] = None
    created_at: datetime


class UserSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: int
    session_name: Optional[str] = None
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    browser: Optional[str] = None
    browser_version: Optional[str] = None
    operating_system: Optional[str] = None
    operating_system_version: Optional[str] = None
    ip_address: Optional[str] = None
    login_at: datetime
    last_activity_at: datetime
    is_active: bool = True


# ── Organization & Provisioning Endpoints ─────────────────────────────────────


@router.post("/organizations/provision")
def provision_organization(
    req: ProvisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("org.create")),
) -> Any:
    """Trigger complete stateful organization provisioning workflow."""
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
    current_user: User = Depends(deps.require_permission("org.view")),
) -> Any:
    """Get complete visual hierarchy tree for current user's organization."""
    return hierarchy_service.build_org_tree(db=db, org_id=current_user.org_id)


@router.post("/organizations/state-transition")
def transition_organization_state(
    req: StateTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("org.manage")),
) -> Any:
    """Transition organization lifecycle state."""
    return organization_provisioning_service.transition_state(
        db=db, org_id=current_user.org_id, new_state=req.new_state
    )


# ── Structural Entities Endpoints ─────────────────────────────────────────────


@router.get("/legal-entities")
def list_legal_entities(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("org.view")),
) -> Any:
    return legal_entity_service.list(db, current_user.org_id)


@router.post("/legal-entities")
def create_legal_entity(
    req: LegalEntityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("org.create")),
) -> Any:
    return legal_entity_service.create(db, current_user.org_id, req.model_dump())


@router.get("/business-units")
def list_business_units(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("departments.read")),
) -> Any:
    return business_unit_service.list(db, current_user.org_id)


@router.post("/business-units")
def create_business_unit(
    req: BusinessUnitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("departments.create")),
) -> Any:
    return business_unit_service.create(db, current_user.org_id, req.model_dump())


@router.get("/branches")
def list_branches(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("org.view")),
) -> Any:
    return branch_service.list(db, current_user.org_id)


@router.post("/branches")
def create_branch(
    req: BranchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("org.create")),
) -> Any:
    return branch_service.create(db, current_user.org_id, req.model_dump())


@router.get("/teams")
def list_teams(
    dept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("departments.read")),
) -> Any:
    return team_service.list_by_dept(db, current_user.org_id, dept_id)


@router.post("/teams")
def create_team(
    req: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("departments.create")),
) -> Any:
    return team_service.create(db, current_user.org_id, req.model_dump())


@router.get("/cost-centers")
def list_cost_centers(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("org.view")),
) -> Any:
    return cost_center_service.list(db, current_user.org_id)


@router.post("/cost-centers")
def create_cost_center(
    req: CostCenterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("org.create")),
) -> Any:
    return cost_center_service.create(db, current_user.org_id, req.model_dump())


# ── Position Endpoints ────────────────────────────────────────────────────────


@router.get("/positions")
def list_positions(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("departments.read")),
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
    current_user: User = Depends(deps.require_permission("departments.create")),
) -> Any:
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


# ── Employment Endpoints ──────────────────────────────────────────────────────


@router.get("/employment/{user_id}")
def get_employment_record(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("users.read")),
) -> Any:
    target_user = (
        db.query(User)
        .filter(User.id == user_id, User.org_id == current_user.org_id, User.is_deleted == 0)
        .first()
    )
    if not target_user:
        raise HTTPException(status_code=404, detail="Identity not found")
    rec = employment_service.get_employment_record(db, current_user.org_id, user_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Employment record not found")
    return rec


@router.post("/employment/{user_id}/hire")
def hire_employee(
    user_id: int,
    req: HireEmployeeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("users.create")),
) -> Any:
    target_user = (
        db.query(User)
        .filter(User.id == user_id, User.org_id == current_user.org_id, User.is_deleted == 0)
        .first()
    )
    if not target_user:
        raise HTTPException(status_code=404, detail="Identity not found")
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
    current_user: User = Depends(deps.require_permission("users.update")),
) -> Any:
    target_user = (
        db.query(User)
        .filter(User.id == user_id, User.org_id == current_user.org_id, User.is_deleted == 0)
        .first()
    )
    if not target_user:
        raise HTTPException(status_code=404, detail="Identity not found")
    return employment_service.transfer_employee(
        db, current_user.org_id, user_id, req.new_dept_id, req.new_position_id, req.reason
    )


@router.post("/employment/{user_id}/promote")
def promote_employee(
    user_id: int,
    req: PromoteEmployeeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("users.update")),
) -> Any:
    target_user = (
        db.query(User)
        .filter(User.id == user_id, User.org_id == current_user.org_id, User.is_deleted == 0)
        .first()
    )
    if not target_user:
        raise HTTPException(status_code=404, detail="Identity not found")
    return employment_service.promote_employee(
        db, current_user.org_id, user_id, req.new_designation, req.new_position_id, req.reason
    )


# ── Identity Lifecycle Endpoints ──────────────────────────────────────────────


@router.post("/identity/{user_id}/activate", response_model=UserResponse)
def activate_identity(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("users.update")),
) -> Any:
    target_user = (
        db.query(User)
        .filter(User.id == user_id, User.org_id == current_user.org_id, User.is_deleted == 0)
        .first()
    )
    if not target_user:
        raise HTTPException(status_code=404, detail="Identity not found")
    try:
        return identity_service.activate_identity(
            db, current_user.org_id, user_id, performed_by_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/identity/{user_id}/suspend", response_model=UserResponse)
def suspend_identity(
    user_id: int,
    req: SuspendIdentityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("users.update")),
) -> Any:
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot suspend your own account")

    target_user = db.query(User).filter(User.org_id == current_user.org_id, User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Identity not found")

    from app.db.models.all_models import Role
    from app.crud.crud_session import user_session
    admin_roles = ["Admin", "OrgAdmin"]
    if target_user.role and target_user.role.name in admin_roles:
        admin_count = db.query(User).join(Role, User.role_id == Role.id).filter(
            User.org_id == current_user.org_id,
            User.is_deleted == 0,
            User.is_active == 1,
            Role.name.in_(admin_roles)
        ).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot suspend the organization's sole administrator")

    res = identity_service.suspend_identity(
        db, current_user.org_id, user_id, performed_by_id=current_user.id, reason=req.reason
    )
    # Immediately revoke active sessions upon administrative suspension
    user_session.revoke_all_for_user(db, user_id=user_id, reason="identity_suspended", logout=True)
    return res


@router.get("/identity/{user_id}/timeline", response_model=List[IdentityTimelineResponse])
def get_identity_timeline(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("users.read")),
) -> Any:
    target_user = (
        db.query(User)
        .filter(User.id == user_id, User.org_id == current_user.org_id, User.is_deleted == 0)
        .first()
    )
    if not target_user:
        raise HTTPException(status_code=404, detail="Identity not found")
    return identity_service.get_identity_timeline(db, current_user.org_id, user_id)


@router.get("/identity/{user_id}/trusted-devices", response_model=List[UserSessionResponse])
def get_trusted_devices(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("users.read")),
) -> Any:
    target_user = (
        db.query(User)
        .filter(User.id == user_id, User.org_id == current_user.org_id, User.is_deleted == 0)
        .first()
    )
    if not target_user:
        raise HTTPException(status_code=404, detail="Identity not found")
    return identity_service.get_trusted_devices(db, user_id)