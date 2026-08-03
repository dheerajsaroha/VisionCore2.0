"""
crud_role.py — CRUD operations for roles and permissions.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from app.db.models.all_models import Role, Permission, RolePermission
from app.crud.base import CRUDBase
from app.schema.rbac import RoleCreate, RoleUpdate, PermissionCreate, PermissionUpdate


class CRUDRole(CRUDBase[Role, RoleCreate, RoleUpdate]):
    def get(self, db: Session, id: int) -> Optional[Role]:
        return db.query(Role).options(
            joinedload(Role.role_permissions).joinedload(RolePermission.permission)
        ).filter(Role.id == id).first()

    def get_by_name(self, db: Session, name: str) -> Optional[Role]:
        return db.query(Role).filter(Role.name == name).first()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        tier: Optional[str] = None,
        is_system: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> List[Role]:
        q = db.query(Role)
        if tier:
            q = q.filter(Role.tier == tier)
        if is_system is not None:
            q = q.filter(Role.is_system == is_system)
        if search:
            q = q.filter(Role.name.ilike(f"%{search}%"))
        return q.order_by(Role.tier, Role.name).offset(skip).limit(limit).all()

    def count(
        self,
        db: Session,
        *,
        tier: Optional[str] = None,
        is_system: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> int:
        q = db.query(Role)
        if tier:
            q = q.filter(Role.tier == tier)
        if is_system is not None:
            q = q.filter(Role.is_system == is_system)
        if search:
            q = q.filter(Role.name.ilike(f"%{search}%"))
        return q.count()

    def create(self, db: Session, *, obj_in: RoleCreate) -> Role:
        db_obj = Role(
            name=obj_in.name,
            description=obj_in.description,
            tier=obj_in.tier,
            is_system=obj_in.is_system,
        )
        db.add(db_obj)
        db.flush()

        # Assign initial permissions
        if obj_in.permission_ids:
            for perm_id in obj_in.permission_ids:
                rp = RolePermission(role_id=db_obj.id, permission_id=perm_id)
                db.add(rp)

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_permissions(self, db: Session, *, role_id: int, permission_ids: List[int]) -> Role:
        """Replace all permissions on a role."""
        # Remove existing
        db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()

        # Add new
        for perm_id in permission_ids:
            rp = RolePermission(role_id=role_id, permission_id=perm_id)
            db.add(rp)

        db.commit()
        return self.get(db, id=role_id)

    def add_permission(self, db: Session, *, role_id: int, permission_id: int) -> bool:
        """Add a single permission to a role. Returns True if added."""
        existing = db.query(RolePermission).filter(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        ).first()
        if existing:
            return False
        rp = RolePermission(role_id=role_id, permission_id=permission_id)
        db.add(rp)
        db.commit()
        return True

    def remove_permission(self, db: Session, *, role_id: int, permission_id: int) -> bool:
        """Remove a single permission from a role. Returns True if removed."""
        existing = db.query(RolePermission).filter(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        ).first()
        if not existing:
            return False
        db.delete(existing)
        db.commit()
        return True

    def get_user_permissions(self, db: Session, *, role_id: int) -> List[str]:
        """Get all permission names for a role."""
        perms = (
            db.query(Permission.name)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .filter(RolePermission.role_id == role_id)
            .all()
        )
        return [p[0] for p in perms]

    def clone_role(self, db: Session, *, source_role_id: int, new_name: str,
                   description: Optional[str] = None) -> Optional[Role]:
        """Clone a role with all its permissions."""
        source = self.get(db, id=source_role_id)
        if not source:
            return None

        new_role = Role(
            name=new_name,
            description=description or f"Clone of {source.name}",
            tier=source.tier,
            is_system=False,  # Cloned roles are never system roles
        )
        db.add(new_role)
        db.flush()

        # Copy permissions
        for rp in source.role_permissions:
            new_rp = RolePermission(role_id=new_role.id, permission_id=rp.permission_id)
            db.add(new_rp)

        db.commit()
        db.refresh(new_role)
        return new_role


class CRUDPermission(CRUDBase[Permission, PermissionCreate, PermissionUpdate]):
    def get_by_name(self, db: Session, name: str) -> Optional[Permission]:
        return db.query(Permission).filter(Permission.name == name).first()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        module: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> List[Permission]:
        q = db.query(Permission)
        if module:
            q = q.filter(Permission.module == module)
        if is_active is not None:
            q = q.filter(Permission.is_active == is_active)
        if search:
            q = q.filter(Permission.name.ilike(f"%{search}%"))
        return q.order_by(Permission.module, Permission.name).offset(skip).limit(limit).all()

    def count(
        self,
        db: Session,
        *,
        module: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> int:
        q = db.query(Permission)
        if module:
            q = q.filter(Permission.module == module)
        if is_active is not None:
            q = q.filter(Permission.is_active == is_active)
        if search:
            q = q.filter(Permission.name.ilike(f"%{search}%"))
        return q.count()

    def get_modules(self, db: Session) -> List[str]:
        """Get all distinct module names."""
        results = db.query(Permission.module).distinct().order_by(Permission.module).all()
        return [r[0] for r in results if r[0]]

    def get_multi_advanced(
        self,
        db: Session,
        *,
        search: Optional[str] = None,
        module: Optional[str] = None,
        group: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple:
        """Advanced permission search with multiple filters.

        Returns (permissions_list, total_count).
        """
        q = db.query(Permission)

        if module:
            q = q.filter(Permission.module == module)
        if group:
            q = q.filter(Permission.group == group)
        if is_active is not None:
            q = q.filter(Permission.is_active == is_active)
        if search:
            pattern = f"%{search}%"
            q = q.filter(
                Permission.name.ilike(pattern) |
                Permission.description.ilike(pattern)
            )

        total = q.count()
        items = q.order_by(Permission.module, Permission.name).offset(skip).limit(limit).all()
        return items, total

    def get_role_count(self, db: Session, permission_id: int) -> int:
        """Get the number of roles a permission is assigned to."""
        from app.db.models.all_models import RolePermission
        return db.query(RolePermission).filter(
            RolePermission.permission_id == permission_id
        ).count()


role_crud = CRUDRole(Role)
permission_crud = CRUDPermission(Permission)
