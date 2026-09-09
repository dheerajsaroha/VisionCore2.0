"""
departments.py — Read-only endpoints for departments and shifts.
Used by the frontend for dropdown population in forms.
All queries are tenant-scoped to current_user.org_id.
"""
from typing import Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from app.api import deps
from app.db.models.all_models import Department, Shift, User
from app.db.database import get_db

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class DepartmentResponse(BaseModel):
    id: int
    name: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ShiftResponse(BaseModel):
    id: int
    shift_name: str
    start_time: Any
    end_time: Any
    grace_period_mins: int

    model_config = ConfigDict(from_attributes=True)


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/departments/", response_model=List[DepartmentResponse])
def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("departments.read")),
) -> Any:
    """List all active departments for the current user's organization."""
    return db.query(Department).filter(
        Department.org_id == current_user.org_id,
        Department.is_deleted == 0,
    ).order_by(Department.name).all()


@router.get("/shifts/", response_model=List[ShiftResponse])
def list_shifts(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("shifts.read")),
) -> Any:
    """List all active shifts for the current user's organization."""
    return db.query(Shift).filter(
        Shift.org_id == current_user.org_id,
        Shift.is_deleted == 0,
    ).order_by(Shift.shift_name).all()
