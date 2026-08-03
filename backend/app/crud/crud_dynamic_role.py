"""
crud_dynamic_role.py — Database Access Layer for Dynamic Roles & Templates
Sprint 2 — Entity 5
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload
from app.db.models.all_models import (
    DynamicRole, RoleTemplate, RoleInheritance, RoleVersion,
    UserRoleAssignment, RoleAssignmentHistory, RoleApproval,
    RoleClone, RoleImportExport, RoleAudit, User, Organization
)


# ── DYNAMIC ROLE CRUD ──
def get_role_by_id(db: Session, role_id: int) -> Optional[DynamicRole]:
    return db.query(DynamicRole).filter(DynamicRole.id == role_id).first()

def get_role_by_code(db: Session, code: str, organization_id: Optional[UUID] = None) -> Optional[DynamicRole]:
    q = db.query(DynamicRole).filter(DynamicRole.code == code)
    if organization_id:
        q = q.filter(or_(DynamicRole.organization_id == organization_id, DynamicRole.organization_id.is_(None)))
    return q.order_by(DynamicRole.organization_id.desc().nullslast()).first()

def get_roles_for_org(db: Session, organization_id: Optional[UUID] = None, tier: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[DynamicRole]:
    q = db.query(DynamicRole)
    if organization_id:
        q = q.filter(or_(DynamicRole.organization_id == organization_id, DynamicRole.organization_id.is_(None)))
    if tier:
        q = q.filter(DynamicRole.tier == tier)
    return q.offset(skip).limit(limit).all()

def create_role(db: Session, role_data: Dict[str, Any]) -> DynamicRole:
    role = DynamicRole(**role_data)
    db.add(role)
    db.commit()
    db.refresh(role)

    # Save initial version snapshot
    create_role_version_snapshot(db, role.id, version=1, created_by_user_id=None, change_summary="Initial creation")
    return role

def update_role(db: Session, role_id: int, updates: Dict[str, Any], user_id: Optional[int] = None) -> Optional[DynamicRole]:
    role = db.query(DynamicRole).filter(DynamicRole.id == role_id).first()
    if not role:
        return None

    for k, v in updates.items():
        if v is not None and hasattr(role, k):
            setattr(role, k, v)

    role.version += 1
    role.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(role)

    # Save version snapshot
    create_role_version_snapshot(db, role.id, version=role.version, created_by_user_id=user_id, change_summary="Updated role config")
    return role

def delete_role(db: Session, role_id: int) -> bool:
    role = db.query(DynamicRole).filter(DynamicRole.id == role_id).first()
    if not role or role.is_system:
        return False
    db.delete(role)
    db.commit()
    return True


# ── ROLE TEMPLATE CRUD ──
def create_template(db: Session, tmpl_data: Dict[str, Any]) -> RoleTemplate:
    tmpl = RoleTemplate(**tmpl_data)
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl

def get_templates(db: Session, category: Optional[str] = None) -> List[RoleTemplate]:
    q = db.query(RoleTemplate)
    if category:
        q = q.filter(RoleTemplate.category == category)
    return q.all()

def get_template_by_code(db: Session, code: str) -> Optional[RoleTemplate]:
    return db.query(RoleTemplate).filter(RoleTemplate.code == code).first()


# ── ROLE INHERITANCE CRUD ──
def create_inheritance(db: Session, parent_role_id: int, child_role_id: int, options: Optional[Dict[str, Any]] = None) -> RoleInheritance:
    opts = options or {}
    inh = RoleInheritance(
        parent_role_id=parent_role_id,
        child_role_id=child_role_id,
        inherit_permissions=opts.get("inherit_permissions", True),
        inherit_scopes=opts.get("inherit_scopes", True),
        inherit_workflows=opts.get("inherit_workflows", True),
        override_rules_json=opts.get("override_rules_json", {})
    )
    db.add(inh)
    db.commit()
    db.refresh(inh)
    return inh

def get_role_inheritances(db: Session, role_id: int) -> List[RoleInheritance]:
    return db.query(RoleInheritance).filter(
        or_(RoleInheritance.parent_role_id == role_id, RoleInheritance.child_role_id == role_id)
    ).all()


# ── ROLE VERSIONING CRUD ──
def create_role_version_snapshot(db: Session, role_id: int, version: int, created_by_user_id: Optional[int] = None, change_summary: Optional[str] = None) -> RoleVersion:
    role = get_role_by_id(db, role_id)
    if not role:
        raise ValueError(f"Role {role_id} not found")

    snapshot = {
        "id": role.id, "code": role.code, "name": role.name,
        "description": role.description, "tier": role.tier,
        "permissions_json": role.permissions_json,
        "data_scopes_json": role.data_scopes_json,
        "approval_rights_json": role.approval_rights_json,
        "features_json": role.features_json,
        "version": version
    }

    rv = RoleVersion(
        role_id=role_id, version=version, snapshot_json=snapshot,
        change_summary=change_summary, created_by_user_id=created_by_user_id
    )
    db.add(rv)
    db.commit()
    db.refresh(rv)
    return rv

def get_role_versions(db: Session, role_id: int) -> List[RoleVersion]:
    return db.query(RoleVersion).filter(RoleVersion.role_id == role_id).order_by(RoleVersion.version.desc()).all()


# ── USER ROLE ASSIGNMENT CRUD ──
def assign_role_to_user(db: Session, user_id: int, role_id: int, organization_id: UUID, is_primary: bool = False, expires_at: Optional[datetime] = None, assigned_by_user_id: Optional[int] = None) -> UserRoleAssignment:
    if is_primary:
        # Clear existing primary flag
        db.query(UserRoleAssignment).filter(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.organization_id == organization_id
        ).update({"is_primary": False})
        db.commit()

    assignment = UserRoleAssignment(
        user_id=user_id, role_id=role_id, organization_id=organization_id,
        is_primary=is_primary, expires_at=expires_at, assigned_by_user_id=assigned_by_user_id,
        is_active=True
    )
    db.add(assignment)
    db.commit()

    # Log audit history
    db.add(RoleAssignmentHistory(
        user_id=user_id, role_id=role_id, action="assigned",
        actor_user_id=assigned_by_user_id, reason="User assigned to dynamic role"
    ))
    db.commit()
    db.refresh(assignment)
    return assignment

def get_user_role_assignments(db: Session, user_id: int, organization_id: Optional[UUID] = None) -> List[UserRoleAssignment]:
    now = datetime.now(timezone.utc)
    q = db.query(UserRoleAssignment).options(joinedload(UserRoleAssignment.role)).filter(
        UserRoleAssignment.user_id == user_id,
        UserRoleAssignment.is_active.is_(True),
        or_(UserRoleAssignment.expires_at.is_(None), UserRoleAssignment.expires_at > now)
    )
    if organization_id:
        q = q.filter(UserRoleAssignment.organization_id == organization_id)
    return q.all()

def remove_user_role_assignment(db: Session, assignment_id: int, actor_user_id: Optional[int] = None) -> bool:
    asgn = db.query(UserRoleAssignment).filter(UserRoleAssignment.id == assignment_id).first()
    if not asgn:
        return False

    asgn.is_active = False
    db.add(RoleAssignmentHistory(
        user_id=asgn.user_id, role_id=asgn.role_id, action="revoked",
        actor_user_id=actor_user_id, reason="Role assignment revoked"
    ))
    db.commit()
    return True
