"""
users.py — RBAC-protected user management router.
All queries are scoped to current_user.org_id for strict multi-tenancy.
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.crud.crud_user import user as crud_user
from app.api import deps
from app.schema.user import UserResponse, UserCreate, UserUpdate, UserListResponse, FaceEnroll
from app.db.models.all_models import User
import base64
from app.services.face_engine import face_engine
from app.db.database import get_db

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def read_user_me(current_user: User = Depends(deps.get_current_active_user)) -> Any:
    return current_user


@router.get("/", response_model=UserListResponse)
def read_users(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    role: Optional[str] = Query(None, description="Filter by role name"),
    is_active: Optional[int] = Query(None, description="Filter by active status: 1=active, 0=inactive"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """STRICT MULTI-TENANCY: Admins/Managers only see users in their own org.
    Supports filtering by role, active status, and search term. Returns paginated results."""
    if current_user.role.name not in ["Admin", "Manager", "SuperAdmin", "OrgAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    query = db.query(User).filter(
        User.org_id == current_user.org_id,
        User.is_deleted == 0,
    )

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    if role:
        from app.db.models.all_models import Role
        query = query.join(Role, User.role_id == Role.id).filter(Role.name == role)

    if search:
        term = f"%{search}%"
        query = query.filter(
            (User.full_name.ilike(term)) | (User.email.ilike(term)) | (User.employee_id.ilike(term))
        )

    total = query.with_entities(func.count(User.id)).scalar()
    users = query.offset(skip).limit(limit).all()

    return {"total": total, "users": users}


@router.post("/", response_model=UserResponse)
def create_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if current_user.role.name not in ["Admin", "Manager", "SuperAdmin", "OrgAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Enforce org_id
    user_in.org_id = current_user.org_id
    user_in.organization = current_user.organization.name if current_user.organization else "default"

    existing = crud_user.get_by_email(db, email=user_in.email)
    if existing:
        raise HTTPException(status_code=400, detail="Identity already registered.")

    return crud_user.create(db, obj_in=user_in.model_dump())


@router.get("/{user_id}", response_model=UserResponse)
def read_user_by_id(
    user_id: int,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    # SECURE: filter by org prevents cross-tenant ID enumeration
    user = db.query(User).filter(
        User.id == user_id,
        User.org_id == current_user.org_id,
        User.is_deleted == 0,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Identity not found")
    if current_user.id != user_id and current_user.role.name not in ["Admin", "Manager", "SuperAdmin", "OrgAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    *,
    db: Session = Depends(get_db),
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update an employee's profile (name, role, dept, shift, active status).
    Admin only. Tenant-scoped."""
    if current_user.role.name not in ["Admin", "Manager", "SuperAdmin", "OrgAdmin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    updated = crud_user.update(
        db,
        user_id=user_id,
        org_id=current_user.org_id,
        obj_in=user_in.model_dump(exclude_none=True),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Identity not found")
    return updated


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft-delete an employee. Sets is_deleted=1. Admin only. Self-deletion is blocked."""
    if current_user.role.name not in ["Admin", "SuperAdmin"]:
        raise HTTPException(status_code=403, detail="Only Admins can delete employees")
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    deleted = crud_user.soft_delete(db, user_id=user_id, org_id=current_user.org_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Identity not found")
    return {"detail": f"Employee {user_id} has been deactivated and archived."}


@router.post("/{user_id}/enroll")
def enroll_user_face(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    enroll_in: FaceEnroll,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    # SECURE: multi-tenant + role check
    user = db.query(User).filter(
        User.id == user_id,
        User.org_id == current_user.org_id,
        User.is_deleted == 0,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Identity not found")
    if current_user.role.name not in ["Admin", "Manager", "SuperAdmin", "OrgAdmin"] and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    embedding = enroll_in.face_embedding
    if not embedding and enroll_in.image_base64:
        try:
            image_bytes = base64.b64decode(enroll_in.image_base64)
            embedding = face_engine.get_embedding(image_bytes)
            if not embedding:
                raise HTTPException(status_code=400, detail="No face detected in submitted image")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed base64 image data")

    if not embedding:
        raise HTTPException(status_code=400, detail="Either face_embedding or image_base64 is required")

    crud_user.enroll_face(db, user_id=user_id, embedding=embedding)
    return {"status": "success", "message": "Neural identity registered."}
