"""
rbac.py — RBAC Management Router

Endpoints for managing roles, permissions, and role assignments.
All endpoints protected by permission checks.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models.all_models import User, Permission, Role, RolePermission
from app.schema.rbac import (
    BulkPermissionAssignRequest,
    BulkPermissionRemoveRequest,
    BulkPermissionResponse,
    PermissionActivateRequest,
    PermissionActivateResponse,
    PermissionAuditEntry,
    PermissionAuditResponse,
    PermissionCreate,
    PermissionDetailResponse,
    PermissionListResponse,
    PermissionModuleItem,
    PermissionModuleListResponse,
    PermissionModuleStats,
    PermissionModuleSummary,
    PermissionModuleSummaryResponse,
    PermissionNameValidation,
    PermissionResponse,
    PermissionSearchResponse,
    PermissionUpdate,
    PermissionValidateNames,
    PermissionValidateNamesResponse,
    RoleCreate,
    RoleDetailResponse,
    RoleListResponse,
    RolePermissionAssignment,
    RoleResponse,
    RoleUpdate,
    SeedStatus,
    UserEffectivePermissions,
)
from app.crud.crud_role import role_crud, permission_crud
from app.services.permission_service import permission_service
from app.db.database import get_db
from app.db.seed_rbac import seed_all, validate_rbac_seed

router = APIRouter()


# =============================================================================
#  RBAC Seeding
# =============================================================================

@router.post("/seed", response_model=SeedStatus)
def seed_rbac_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("platform.settings.manage")),
) -> Any:
    """Seed the RBAC system with predefined roles, permissions, and mappings.
    Requires platform.settings.manage permission. Idempotent."""
    stats = seed_all(db)
    issues = validate_rbac_seed(db)
    if issues:
        raise HTTPException(status_code=500, detail=f"RBAC validation failed: {'; '.join(issues)}")
    return stats


@router.get("/seed/validate")
def validate_rbac_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("platform.settings.view")),
) -> Any:
    """Validate the current RBAC seed state. Returns any issues found."""
    issues = validate_rbac_seed(db)
    return {
        "valid": len(issues) == 0,
        "issues": issues,
    }


# =============================================================================
#  Permission Endpoints
# =============================================================================

@router.get("/permissions", response_model=PermissionListResponse)
def list_permissions(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    module: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(deps.require_permission("roles.view")),
) -> Any:
    """List all permissions with optional filtering."""
    permissions = permission_crud.get_multi(
        db, skip=skip, limit=limit, module=module, is_active=is_active, search=search
    )
    total = permission_crud.count(db, module=module, is_active=is_active, search=search)
    return {"total": total, "permissions": permissions}


@router.get("/permissions/modules")
def list_permission_modules(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.view")),
) -> Any:
    """List all distinct permission modules."""
    modules = permission_crud.get_modules(db)
    return {"modules": modules}


# ── Permission Audit Log ──────────────────────────────────────────────────
# IMPORTANT: This must be defined BEFORE `/permissions/{permission_id}`
# to avoid FastAPI route matching `audit` as a permission ID integer.

@router.get("/permissions/audit", response_model=PermissionAuditResponse)
def get_permission_audit_log(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("audit.view")),
) -> Any:
    """Get permission change audit log (assignments, removals, activations).
    Requires audit.view permission."""
    entries = permission_service.get_audit_log(db, limit=limit)
    return PermissionAuditResponse(
        entries=[PermissionAuditEntry(**e) for e in entries],
        total=len(entries),
    )


# ── Permission Export ─────────────────────────────────────────────────────
# IMPORTANT: Must be defined BEFORE `/permissions/{permission_id}`

@router.get("/permissions/export")
def export_permissions(
    format: str = Query("json", pattern="^(json|csv)$"),
    module: Optional[str] = Query(None, max_length=50),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.view")),
) -> Any:
    """Export permissions in JSON or CSV format.
    Supports optional filtering by module and active status.
    Requires roles.view permission."""
    query = db.query(Permission).order_by(Permission.module, Permission.name)
    if module:
        query = query.filter(Permission.module == module)
    if is_active is not None:
        query = query.filter(Permission.is_active == is_active)

    perms = query.all()

    if format == "csv":
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "name", "description", "module", "group", "is_active", "created_at"])
        for p in perms:
            writer.writerow([
                p.id, p.name, p.description, p.module,
                p.group, p.is_active, p.created_at.isoformat(),
            ])
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=permissions.csv"},
        )

    return {
        "total": len(perms),
        "permissions": [
            {
                "id": p.id, "name": p.name, "description": p.description,
                "module": p.module, "group": p.group, "is_active": p.is_active,
                "created_at": p.created_at.isoformat(),
            }
            for p in perms
        ],
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/permissions/{permission_id}", response_model=PermissionResponse)
def get_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.view")),
) -> Any:
    """Get a single permission by ID."""
    perm = permission_crud.get(db, id=permission_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    return perm


@router.post("/permissions", response_model=PermissionResponse)
def create_permission(
    perm_in: PermissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.create")),
) -> Any:
    """Create a new permission. Requires roles.create permission."""
    existing = permission_crud.get_by_name(db, name=perm_in.name)
    if existing:
        raise HTTPException(status_code=409, detail="Permission already exists")
    return permission_crud.create(db, obj_in=perm_in)


@router.patch("/permissions/{permission_id}", response_model=PermissionResponse)
def update_permission(
    permission_id: int,
    perm_in: PermissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.update")),
) -> Any:
    """Update a permission. Requires roles.update permission."""
    perm = permission_crud.get(db, id=permission_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    return permission_crud.update(db, db_obj=perm, obj_in=perm_in)


@router.delete("/permissions/{permission_id}")
def delete_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.delete")),
) -> Any:
    """Delete a permission. Requires roles.delete permission."""
    perm = permission_crud.get(db, id=permission_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    permission_crud.remove(db, id=permission_id)
    return {"detail": "Permission deleted"}


# =============================================================================
#  PERMISSION SYSTEM — Enhanced Endpoints (Sprint 2, EAAC)
# =============================================================================

# ── Permission Name Validation ──────────────────────────────────────────────

@router.post("/permissions/validate", response_model=PermissionValidateNamesResponse)
def validate_permission_names(
    req: PermissionValidateNames,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.view")),
) -> Any:
    """Validate one or more permission names against EAAC naming standard.
    Does NOT check for existence — only format validation.
    Requires roles.view permission."""
    results = []
    for name in req.names:
        valid, message = permission_service.validate_permission_name(name)
        results.append(PermissionNameValidation(name=name, valid=valid, message=message))
    return PermissionValidateNamesResponse(results=results)


# ── Bulk Permission Operations ──────────────────────────────────────────────

@router.post("/permissions/bulk/assign", response_model=BulkPermissionResponse)
def bulk_assign_permissions(
    req: BulkPermissionAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.update")),
) -> Any:
    """Bulk assign permissions to a role.
    Skips already-assigned permissions.
    Validates all permissions exist and are active.
    Requires roles.update permission."""
    result = permission_service.bulk_assign_permissions(
        db, role_id=req.role_id, permission_ids=req.permission_ids,
        actor_user_id=current_user.id,
    )
    return BulkPermissionResponse(**result)


@router.post("/permissions/bulk/remove", response_model=BulkPermissionResponse)
def bulk_remove_permissions(
    req: BulkPermissionRemoveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.update")),
) -> Any:
    """Bulk remove permissions from a role.
    Skips permissions not currently assigned.
    Requires roles.update permission."""
    result = permission_service.bulk_remove_permissions(
        db, role_id=req.role_id, permission_ids=req.permission_ids,
        actor_user_id=current_user.id,
    )
    return BulkPermissionResponse(**result)


# ── Permission Detail (with role count) ────────────────────────────────────

@router.get("/permissions/{permission_id}/detail", response_model=PermissionDetailResponse)
def get_permission_detail(
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.view")),
) -> Any:
    """Get a single permission with additional metadata (role_count).
    Requires roles.view permission."""
    perm = permission_crud.get(db, id=permission_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")

    role_count = permission_crud.get_role_count(db, permission_id=permission_id)
    return PermissionDetailResponse(
        id=perm.id,
        name=perm.name,
        description=perm.description,
        module=perm.module,
        group=perm.group,
        is_active=perm.is_active,
        created_at=perm.created_at,
        role_count=role_count,
    )


# ── Permission Activation / Deactivation ────────────────────────────────────

@router.patch("/permissions/{permission_id}/status", response_model=PermissionActivateResponse)
def update_permission_status(
    permission_id: int,
    req: PermissionActivateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.update")),
) -> Any:
    """Activate or deactivate a permission.
    Deactivation checks for dependency conflicts (roles with only this module perm).
    Requires roles.update permission."""
    if req.is_active:
        result = permission_service.activate_permission(
            db, permission_id=permission_id, actor_user_id=current_user.id,
        )
    else:
        result = permission_service.deactivate_permission(
            db, permission_id=permission_id, actor_user_id=current_user.id,
        )
    return PermissionActivateResponse(
        success=result["success"],
        warnings=result.get("warnings", []),
        message=result.get("message", ""),
        permission_id=permission_id if result["success"] else None,
    )


# ── Module Statistics ──────────────────────────────────────────────────────

@router.get("/permissions/modules/stats", response_model=PermissionModuleListResponse)
def get_permission_module_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.view")),
) -> Any:
    """Get detailed statistics for each permission module.
    Includes all permissions grouped by module.
    Requires roles.view permission."""
    stats = permission_service.get_module_statistics(db)
    return PermissionModuleListResponse(
        modules=[PermissionModuleStats(**m) for m in stats],
        total_modules=len(stats),
    )


@router.get("/permissions/modules/summary", response_model=PermissionModuleSummaryResponse)
def get_permission_module_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.view")),
) -> Any:
    """Get lightweight module summaries (counts only, no permission details).
    Requires roles.view permission."""
    summaries = permission_service.get_module_summary(db)
    return PermissionModuleSummaryResponse(
        modules=[PermissionModuleSummary(**s) for s in summaries],
        total_modules=len(summaries),
    )


# ── Advanced Permission Search ─────────────────────────────────────────────

@router.get("/permissions/search/advanced", response_model=PermissionSearchResponse)
def search_permissions_advanced(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, max_length=200),
    module: Optional[str] = Query(None, max_length=50),
    group: Optional[str] = Query(None, max_length=50),
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(deps.require_permission("roles.view")),
) -> Any:
    """Advanced permission search with multiple filters.
    Supports: search text, module, group, active status, pagination.
    Requires roles.view permission."""
    perms, total = permission_service.search_permissions_advanced(
        db, search=search, module=module, group=group,
        is_active=is_active, skip=skip, limit=limit,
    )
    return PermissionSearchResponse(
        total=total,
        permissions=[
            PermissionResponse(
                id=p.id, name=p.name, description=p.description,
                module=p.module, group=p.group, is_active=p.is_active,
                created_at=p.created_at,
            )
            for p in perms
        ],
        filters_applied={
            "search": search,
            "module": module,
            "group": group,
            "is_active": is_active,
        },
    )


# ── User Effective Permissions ─────────────────────────────────────────────

@router.get("/user/{user_id}/permissions", response_model=UserEffectivePermissions)
def get_user_effective_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.view")),
) -> Any:
    """Get all effective permissions for a user based on their role.
    SuperAdmin returns ALL active permissions.
    Requires roles.view permission."""
    target_user = db.query(User).filter(User.id == user_id, User.is_deleted == 0).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    perms = permission_service.get_user_effective_permissions(db, target_user)
    role = db.query(Role).filter(Role.id == target_user.role_id).first() if target_user.role_id else None

    return UserEffectivePermissions(
        user_id=target_user.id,
        role_id=target_user.role_id or 0,
        role_name=role.name if role else "None",
        permissions=perms,
        permission_count=len(perms),
    )


@router.get("/me/permissions")
def get_my_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get effective permissions for the current authenticated user.
    No extra permissions required — users can always see their own permissions."""
    perms = permission_service.get_user_effective_permissions(db, current_user)
    role = db.query(Role).filter(Role.id == current_user.role_id).first() if current_user.role_id else None

    return {
        "user_id": current_user.id,
        "role_id": current_user.role_id,
        "role_name": role.name if role else "None",
        "permissions": perms,
        "permission_count": len(perms),
    }


# =============================================================================
#  Role Endpoints
# =============================================================================

@router.get("/roles", response_model=RoleListResponse)
def list_roles(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    tier: Optional[str] = Query(None, pattern=r"^(platform|organization|system)$"),
    is_system: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(deps.require_permission("roles.view")),
) -> Any:
    """List all roles with optional filtering by tier, system status, and search."""
    roles = role_crud.get_multi(db, skip=skip, limit=limit, tier=tier,
                                 is_system=is_system, search=search)
    total = role_crud.count(db, tier=tier, is_system=is_system, search=search)
    # Attach permission count
    result = []
    for role in roles:
        perm_count = len(role.permissions) if hasattr(role, 'permissions') and role.permissions else 0
        if hasattr(role, 'role_permissions'):
            perm_count = len(role.role_permissions)
        resp = RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            tier=role.tier,
            is_system=role.is_system,
            created_at=role.created_at,
            permission_count=perm_count,
        )
        result.append(resp)
    return {"total": total, "roles": result}


@router.get("/roles/{role_id}", response_model=RoleDetailResponse)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.view")),
) -> Any:
    """Get a single role with its permissions."""
    role = role_crud.get(db, id=role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    permissions = []
    for rp in role.role_permissions:
        perm = rp.permission
        permissions.append(PermissionResponse(
            id=perm.id,
            name=perm.name,
            description=perm.description,
            module=perm.module,
            group=perm.group,
            is_active=perm.is_active,
            created_at=perm.created_at,
        ))

    return RoleDetailResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        tier=role.tier,
        is_system=role.is_system,
        created_at=role.created_at,
        permission_count=len(permissions),
        permissions=permissions,
    )


@router.post("/roles", response_model=RoleDetailResponse)
def create_role(
    role_in: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.create")),
) -> Any:
    """Create a new role with optional initial permissions."""
    existing = role_crud.get_by_name(db, name=role_in.name)
    if existing:
        raise HTTPException(status_code=409, detail="Role already exists")

    role = role_crud.create(db, obj_in=role_in)

    # Build response
    permissions = []
    for rp in role.role_permissions:
        perm = rp.permission
        permissions.append(PermissionResponse(
            id=perm.id,
            name=perm.name,
            description=perm.description,
            module=perm.module,
            group=perm.group,
            is_active=perm.is_active,
            created_at=perm.created_at,
        ))

    return RoleDetailResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        tier=role.tier,
        is_system=role.is_system,
        created_at=role.created_at,
        permission_count=len(permissions),
        permissions=permissions,
    )


@router.put("/roles/{role_id}", response_model=RoleDetailResponse)
def update_role(
    role_id: int,
    role_in: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.update")),
) -> Any:
    """Update a role's metadata. System roles cannot be modified."""
    role = role_crud.get(db, id=role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="System roles cannot be modified")

    update_data = role_in.model_dump(exclude_unset=True)
    updated = role_crud.update(db, db_obj=role, obj_in=update_data)

    permissions = []
    for rp in updated.role_permissions:
        perm = rp.permission
        permissions.append(PermissionResponse(
            id=perm.id,
            name=perm.name,
            description=perm.description,
            module=perm.module,
            group=perm.group,
            is_active=perm.is_active,
            created_at=perm.created_at,
        ))

    return RoleDetailResponse(
        id=updated.id,
        name=updated.name,
        description=updated.description,
        tier=updated.tier,
        is_system=updated.is_system,
        created_at=updated.created_at,
        permission_count=len(permissions),
        permissions=permissions,
    )


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.delete")),
) -> Any:
    """Delete a role. System roles cannot be deleted."""
    role = role_crud.get(db, id=role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="System roles cannot be deleted")

    role_crud.remove(db, id=role_id)
    return {"detail": "Role deleted"}


# =============================================================================
#  Role-Permission Assignment
# =============================================================================

@router.put("/roles/{role_id}/permissions", response_model=RoleDetailResponse)
def update_role_permissions(
    role_id: int,
    assignment: RolePermissionAssignment,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.update")),
) -> Any:
    """Replace all permissions on a role."""
    role = role_crud.get(db, id=role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="System role permissions cannot be modified")

    updated = role_crud.update_permissions(db, role_id=role_id, permission_ids=assignment.permission_ids)

    permissions = []
    for rp in updated.role_permissions:
        perm = rp.permission
        permissions.append(PermissionResponse(
            id=perm.id,
            name=perm.name,
            description=perm.description,
            module=perm.module,
            group=perm.group,
            is_active=perm.is_active,
            created_at=perm.created_at,
        ))

    return RoleDetailResponse(
        id=updated.id,
        name=updated.name,
        description=updated.description,
        tier=updated.tier,
        is_system=updated.is_system,
        created_at=updated.created_at,
        permission_count=len(permissions),
        permissions=permissions,
    )


@router.post("/roles/{role_id}/permissions/{permission_id}")
def add_role_permission(
    role_id: int,
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.update")),
) -> Any:
    """Add a single permission to a role."""
    role = role_crud.get(db, id=role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="System role permissions cannot be modified")

    perm = permission_crud.get(db, id=permission_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")

    added = role_crud.add_permission(db, role_id=role_id, permission_id=permission_id)
    if not added:
        raise HTTPException(status_code=409, detail="Permission already assigned to this role")

    return {"detail": "Permission added to role"}


@router.delete("/roles/{role_id}/permissions/{permission_id}")
def remove_role_permission(
    role_id: int,
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.update")),
) -> Any:
    """Remove a single permission from a role."""
    role = role_crud.get(db, id=role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="System role permissions cannot be modified")

    perm = permission_crud.get(db, id=permission_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")

    removed = role_crud.remove_permission(db, role_id=role_id, permission_id=permission_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Permission not assigned to this role")

    return {"detail": "Permission removed from role"}


# =============================================================================
#  Role Clone
# =============================================================================

@router.post("/roles/{role_id}/clone", response_model=RoleDetailResponse)
def clone_role(
    role_id: int,
    new_name: str = Query(..., min_length=1, max_length=50),
    description: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("roles.create")),
) -> Any:
    """Clone an existing role with all its permissions."""
    source = role_crud.get(db, id=role_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source role not found")

    existing = role_crud.get_by_name(db, name=new_name)
    if existing:
        raise HTTPException(status_code=409, detail="A role with this name already exists")

    cloned = role_crud.clone_role(db, source_role_id=role_id, new_name=new_name, description=description)
    if not cloned:
        raise HTTPException(status_code=500, detail="Failed to clone role")

    permissions = []
    for rp in cloned.role_permissions:
        perm = rp.permission
        permissions.append(PermissionResponse(
            id=perm.id,
            name=perm.name,
            description=perm.description,
            module=perm.module,
            group=perm.group,
            is_active=perm.is_active,
            created_at=perm.created_at,
        ))

    return RoleDetailResponse(
        id=cloned.id,
        name=cloned.name,
        description=cloned.description,
        tier=cloned.tier,
        is_system=cloned.is_system,
        created_at=cloned.created_at,
        permission_count=len(permissions),
        permissions=permissions,
    )
