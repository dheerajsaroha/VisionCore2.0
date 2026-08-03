"""
scope_resolver.py — Scope Resolution & Query Builder Engines (Sprint 2, Entity 3)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.crud.crud_scope import (
    role_data_scope_crud,
    resource_ownership_crud,
    ownership_delegation_crud,
)
from app.db.models.all_models import (
    User,
    Permission,
    RoleDataScope,
    ResourceOwnership,
    OwnershipDelegation,
)

logger = logging.getLogger(__name__)


@dataclass
class EffectiveScope:
    """Resolved data scope container for a specific user & permission."""
    user_id: int
    organization_id: Optional[UUID]
    permission_code: str
    scope_code: str
    scope_level: int
    department_ids: List[int] = field(default_factory=list)
    subordinate_user_ids: List[int] = field(default_factory=list)
    owned_entity_ids: List[str] = field(default_factory=list)
    is_platform_admin: bool = False
    is_org_admin: bool = False
    active_delegations: List[int] = field(default_factory=list)
    exceptions_granted: List[int] = field(default_factory=list)

    @property
    def is_global(self) -> bool:
        return self.scope_code == "platform" or self.is_platform_admin

    @property
    def is_org_wide(self) -> bool:
        return self.scope_code in ("organization", "multi_org", "platform") or self.is_org_admin


class HierarchyResolver:
    """Resolves organizational hierarchy via department membership."""
    @staticmethod
    def get_dept_members(db: Session, dept_id: int) -> List[int]:
        users = db.query(User.id).filter(
            User.dept_id == dept_id,
            User.is_deleted == 0,
        ).all()
        return [u[0] for u in users]


class DepartmentResolver:
    """Resolves user's department IDs."""
    @staticmethod
    def get_user_department_ids(db: Session, user: User) -> List[int]:
        if user.dept_id:
            return [user.dept_id]
        return []


class OwnershipResolver:
    """Resolves resource-level ownerships and active delegations."""
    @staticmethod
    def get_owned_entity_ids(db: Session, entity_type: str, user_id: int) -> List[str]:
        rows = db.query(ResourceOwnership.entity_id).filter(
            ResourceOwnership.entity_type == entity_type,
            ResourceOwnership.owner_user_id == user_id,
            ResourceOwnership.is_active.is_(True),
        ).all()
        return [r[0] for r in rows]

    @staticmethod
    def get_active_delegations(db: Session, delegatee_user_id: int, org_id: UUID) -> List[OwnershipDelegation]:
        now = datetime.now(timezone.utc)
        return db.query(OwnershipDelegation).filter(
            OwnershipDelegation.delegatee_user_id == delegatee_user_id,
            OwnershipDelegation.organization_id == org_id,
            OwnershipDelegation.is_active.is_(True),
            OwnershipDelegation.start_date <= now,
            OwnershipDelegation.end_date >= now,
        ).all()


class ScopeResolver:
    """Core Scope Resolver engine."""
    @staticmethod
    def resolve_effective_scope(
        db: Session,
        user: User,
        permission_code: str,
        organization_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
    ) -> EffectiveScope:
        # User model uses org_id, dept_id, role_id
        org_id = organization_id or user.org_id

        role_name = user.role.name if user.role else ""
        role_tier = user.role.tier if user.role else "organization"
        is_platform = role_name == "SuperAdmin" or role_tier == "platform"
        is_org_admin = role_name == "OrgAdmin"

        if is_platform:
            return EffectiveScope(
                user_id=user.id,
                organization_id=org_id,
                permission_code=permission_code,
                scope_code="platform",
                scope_level=100,
                is_platform_admin=True,
                is_org_admin=True,
            )

        # Explicit RoleDataScope lookup
        perm = db.query(Permission).filter(Permission.name == permission_code).first()
        perm_id = perm.id if perm else None

        rds_list: List[RoleDataScope] = []
        if user.role_id:
            rds_list = role_data_scope_crud.get_for_role(db, user.role_id, perm_id, org_id)

        chosen_scope_code = "self"
        chosen_scope_level = 10

        if rds_list:
            top = rds_list[0]
            if top.data_scope:
                chosen_scope_code = top.data_scope.code
                chosen_scope_level = top.data_scope.scope_level
        elif is_org_admin:
            chosen_scope_code = "organization"
            chosen_scope_level = 80
        elif role_name == "DepartmentManager":
            chosen_scope_code = "department"
            chosen_scope_level = 60

        # Active delegations
        delegations = OwnershipResolver.get_active_delegations(db, user.id, org_id) if org_id else []
        delegation_ids = [d.id for d in delegations]

        dept_ids = DepartmentResolver.get_user_department_ids(db, user) if chosen_scope_code in ("department", "team", "reporting_hierarchy") else []
        sub_user_ids: List[int] = []
        if dept_ids and chosen_scope_code in ("department", "reporting_hierarchy"):
            for did in dept_ids:
                members = HierarchyResolver.get_dept_members(db, did)
                sub_user_ids.extend([uid for uid in members if uid != user.id])

        owned_ids: List[str] = []
        if entity_type:
            owned_ids = OwnershipResolver.get_owned_entity_ids(db, entity_type, user.id)

        return EffectiveScope(
            user_id=user.id,
            organization_id=org_id,
            permission_code=permission_code,
            scope_code=chosen_scope_code,
            scope_level=chosen_scope_level,
            department_ids=dept_ids,
            subordinate_user_ids=sub_user_ids,
            owned_entity_ids=owned_ids,
            is_platform_admin=is_platform,
            is_org_admin=is_org_admin,
            active_delegations=delegation_ids,
        )


class QueryScopeBuilder:
    """Automatic query scope filter injector."""
    @staticmethod
    def apply_scope_filter(
        query: Query,
        model_cls: Any,
        effective_scope: EffectiveScope,
        user_id_col_name: str = "user_id",
        dept_id_col_name: str = "dept_id",
        org_id_col_name: str = "org_id",
    ) -> Query:
        """Inject SQL filters based on resolved Data Scope without router changes."""
        if effective_scope.is_global:
            return query

        if hasattr(model_cls, org_id_col_name) and effective_scope.organization_id:
            query = query.filter(
                getattr(model_cls, org_id_col_name) == effective_scope.organization_id
            )

        if effective_scope.is_org_wide:
            return query

        if effective_scope.scope_code == "department":
            conds = []
            if hasattr(model_cls, dept_id_col_name) and effective_scope.department_ids:
                conds.append(getattr(model_cls, dept_id_col_name).in_(effective_scope.department_ids))
            if hasattr(model_cls, user_id_col_name) and effective_scope.subordinate_user_ids:
                user_ids = [effective_scope.user_id] + effective_scope.subordinate_user_ids
                conds.append(getattr(model_cls, user_id_col_name).in_(user_ids))
            if conds:
                query = query.filter(or_(*conds))
            return query

        if effective_scope.scope_code == "reporting_hierarchy":
            if hasattr(model_cls, user_id_col_name):
                user_ids = [effective_scope.user_id] + effective_scope.subordinate_user_ids
                query = query.filter(getattr(model_cls, user_id_col_name).in_(user_ids))
            return query

        # Self level
        if effective_scope.scope_code == "self":
            conds = []
            if hasattr(model_cls, user_id_col_name):
                conds.append(getattr(model_cls, user_id_col_name) == effective_scope.user_id)
            if effective_scope.owned_entity_ids and hasattr(model_cls, "id"):
                conds.append(getattr(model_cls, "id").in_(effective_scope.owned_entity_ids))
            if conds:
                query = query.filter(or_(*conds))

        return query
