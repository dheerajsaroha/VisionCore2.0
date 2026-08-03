"""
dynamic_roles.py — FastAPI Router for Enterprise Dynamic Roles & Role Templates
Sprint 2 — Entity 5
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_active_user
from app.api.dynamic_role_deps import require_role_admin
from app.crud import crud_dynamic_role
from app.db.models.all_models import User, DynamicRole
from app.db.seed_dynamic_roles import seed_role_templates
from app.schema.dynamic_role import (
    DynamicRoleCreate, DynamicRoleUpdate, DynamicRoleResponse, DynamicRoleListResponse,
    RoleTemplateResponse, RoleInheritanceCreate, RoleInheritanceResponse,
    UserRoleAssignmentCreate, UserRoleAssignmentResponse, RoleVersionResponse,
    RoleDiffResponse, EffectiveAuthorizationResponse
)
from app.services.dynamic_role_engine import (
    DynamicRoleService, RoleInheritanceService, EffectivePermissionResolver, RoleVersionService
)

router = APIRouter()


# ── TEMPLATE ENDPOINTS ──
@router.post("/seed", status_code=status.HTTP_200_OK)
def seed_templates(db: Session = Depends(get_db), current_user: User = Depends(require_role_admin)):
    seeded = seed_role_templates(db)
    return {"message": "Role templates seeded successfully", "seeded_count": seeded}

@router.get("/templates", response_model=List[RoleTemplateResponse])
def get_templates(category: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return crud_dynamic_role.get_templates(db, category=category)

@router.get("/templates/{code}", response_model=RoleTemplateResponse)
def get_template(code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    tmpl = crud_dynamic_role.get_template_by_code(db, code)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tmpl


# ── ROLE CRUD ENDPOINTS ──
@router.post("/roles", response_model=DynamicRoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(payload: DynamicRoleCreate, db: Session = Depends(get_db), current_user: User = Depends(require_role_admin)):
    org_id = payload.organization_id or current_user.org_id
    role_data = payload.model_dump()
    role_data["organization_id"] = org_id

    # Check code uniqueness
    existing = crud_dynamic_role.get_role_by_code(db, payload.code, org_id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Role with code '{payload.code}' already exists")

    return crud_dynamic_role.create_role(db, role_data)

@router.get("/roles", response_model=DynamicRoleListResponse)
def list_roles(tier: Optional[str] = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    roles = crud_dynamic_role.get_roles_for_org(db, organization_id=current_user.org_id, tier=tier, skip=skip, limit=limit)
    return {"total": len(roles), "roles": roles}

@router.get("/roles/{role_id}", response_model=DynamicRoleResponse)
def get_role(role_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    role = crud_dynamic_role.get_role_by_id(db, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role

@router.put("/roles/{role_id}", response_model=DynamicRoleResponse)
def update_role(role_id: int, payload: DynamicRoleUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_role_admin)):
    updates = payload.model_dump(exclude_unset=True)
    role = crud_dynamic_role.update_role(db, role_id, updates, user_id=current_user.id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role

@router.delete("/roles/{role_id}", status_code=status.HTTP_200_OK)
def delete_role(role_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role_admin)):
    success = crud_dynamic_role.delete_role(db, role_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete system role or role not found")
    return {"message": "Role deleted successfully"}


# ── ROLE TEMPLATE & CLONE OPERATIONS ──
@router.post("/roles/from-template", response_model=DynamicRoleResponse, status_code=status.HTTP_201_CREATED)
def create_role_from_template(template_code: str, custom_name: Optional[str] = None, custom_code: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(require_role_admin)):
    try:
        return DynamicRoleService.create_role_from_template(
            db, organization_id=current_user.org_id, template_code=template_code,
            custom_name=custom_name, custom_code=custom_code, user_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/roles/{role_id}/clone", response_model=DynamicRoleResponse, status_code=status.HTTP_201_CREATED)
def clone_role(role_id: int, new_code: str, new_name: str, db: Session = Depends(get_db), current_user: User = Depends(require_role_admin)):
    try:
        return DynamicRoleService.clone_role(
            db, source_role_id=role_id, new_code=new_code, new_name=new_name,
            organization_id=current_user.org_id, user_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── ROLE INHERITANCE ──
@router.post("/roles/inheritance", response_model=RoleInheritanceResponse, status_code=status.HTTP_201_CREATED)
def create_inheritance(payload: RoleInheritanceCreate, db: Session = Depends(get_db), current_user: User = Depends(require_role_admin)):
    # Check circular inheritance cycle
    if RoleInheritanceService.detect_cycle(db, payload.parent_role_id, payload.child_role_id):
        raise HTTPException(status_code=400, detail="Circular inheritance detected! Operation aborted.")

    return crud_dynamic_role.create_inheritance(
        db, parent_role_id=payload.parent_role_id, child_role_id=payload.child_role_id,
        options=payload.model_dump()
    )


# ── USER ASSIGNMENTS ──
@router.post("/roles/assign", response_model=UserRoleAssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_role(payload: UserRoleAssignmentCreate, db: Session = Depends(get_db), current_user: User = Depends(require_role_admin)):
    org_id = payload.organization_id or current_user.org_id
    return crud_dynamic_role.assign_role_to_user(
        db, user_id=payload.user_id, role_id=payload.role_id, organization_id=org_id,
        is_primary=payload.is_primary, expires_at=payload.expires_at, assigned_by_user_id=current_user.id
    )

@router.delete("/roles/assignment/{assignment_id}", status_code=status.HTTP_200_OK)
def remove_assignment(assignment_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role_admin)):
    success = crud_dynamic_role.remove_user_role_assignment(db, assignment_id, actor_user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Role assignment not found")
    return {"message": "Role assignment revoked successfully"}


# ── VERSIONING & ROLLBACK ──
@router.get("/roles/{role_id}/versions", response_model=List[RoleVersionResponse])
def get_role_versions(role_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return crud_dynamic_role.get_role_versions(db, role_id)

@router.post("/roles/{role_id}/rollback/{target_version}", response_model=DynamicRoleResponse)
def rollback_version(role_id: int, target_version: int, db: Session = Depends(get_db), current_user: User = Depends(require_role_admin)):
    try:
        return DynamicRoleService.rollback_role_version(db, role_id, target_version, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/roles/{role_id}/diff", response_model=RoleDiffResponse)
def get_role_diff(role_id: int, v1: int = Query(...), v2: int = Query(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    try:
        return RoleVersionService.calculate_role_diff(db, role_id, v1, v2)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── EFFECTIVE AUTHORIZATION RESOLUTION ──
@router.get("/effective-authorization", response_model=EffectiveAuthorizationResponse)
def resolve_effective_authorization(user_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    target_user_id = user_id or current_user.id
    org_id = current_user.org_id
    return EffectivePermissionResolver.resolve_effective_permissions(db, target_user_id, org_id)
