"""
crud_scope.py — CRUD Data Access Layer for Enterprise Data Scope & Resource Ownership System (Sprint 2, Entity 3)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session, joinedload

from app.db.models.all_models import (
    DataScope,
    RoleDataScope,
    ResourceOwnership,
    OwnershipHistory,
    OwnershipDelegation,
    OwnershipRule,
    OwnershipPolicy,
    OwnershipException,
    Role,
    Permission,
    User,
    Organization,
)


class DataScopeCRUD:
    def get_by_id(self, db: Session, scope_id: int) -> Optional[DataScope]:
        return db.query(DataScope).filter(DataScope.id == scope_id).first()

    def get_by_code(self, db: Session, code: str) -> Optional[DataScope]:
        return db.query(DataScope).filter(DataScope.code == code).first()

    def get_multi(self, db: Session, skip: int = 0, limit: int = 100, active_only: bool = True) -> Tuple[List[DataScope], int]:
        q = db.query(DataScope)
        if active_only:
            q = q.filter(DataScope.is_active.is_(True))
        total = q.count()
        scopes = q.order_by(DataScope.scope_level.desc()).offset(skip).limit(limit).all()
        return scopes, total

    def create(self, db: Session, obj_in: Dict[str, Any]) -> DataScope:
        db_obj = DataScope(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: DataScope, obj_in: Dict[str, Any]) -> DataScope:
        for k, v in obj_in.items():
            if v is not None and hasattr(db_obj, k):
                setattr(db_obj, k, v)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


class RoleDataScopeCRUD:
    def get_by_id(self, db: Session, rds_id: int) -> Optional[RoleDataScope]:
        return db.query(RoleDataScope).options(
            joinedload(RoleDataScope.role),
            joinedload(RoleDataScope.data_scope),
            joinedload(RoleDataScope.permission),
        ).filter(RoleDataScope.id == rds_id).first()

    def get_for_role(
        self,
        db: Session,
        role_id: int,
        permission_id: Optional[int] = None,
        organization_id: Optional[UUID] = None,
    ) -> List[RoleDataScope]:
        q = db.query(RoleDataScope).options(
            joinedload(RoleDataScope.data_scope),
            joinedload(RoleDataScope.permission),
        ).filter(
            RoleDataScope.role_id == role_id,
            RoleDataScope.is_active.is_(True),
        )
        if permission_id:
            q = q.filter(or_(RoleDataScope.permission_id == permission_id, RoleDataScope.permission_id.is_(None)))
        if organization_id:
            q = q.filter(or_(RoleDataScope.organization_id == organization_id, RoleDataScope.organization_id.is_(None)))
        return q.order_by(RoleDataScope.permission_id.desc().nullslast()).all()

    def get_multi(self, db: Session, skip: int = 0, limit: int = 100, role_id: Optional[int] = None, organization_id: Optional[UUID] = None) -> Tuple[List[RoleDataScope], int]:
        q = db.query(RoleDataScope).options(
            joinedload(RoleDataScope.role),
            joinedload(RoleDataScope.data_scope),
            joinedload(RoleDataScope.permission),
        )
        if role_id:
            q = q.filter(RoleDataScope.role_id == role_id)
        if organization_id:
            q = q.filter(RoleDataScope.organization_id == organization_id)
        total = q.count()
        items = q.order_by(RoleDataScope.id.desc()).offset(skip).limit(limit).all()
        return items, total

    def create(self, db: Session, obj_in: Dict[str, Any]) -> RoleDataScope:
        db_obj = RoleDataScope(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: RoleDataScope, obj_in: Dict[str, Any]) -> RoleDataScope:
        for k, v in obj_in.items():
            if v is not None and hasattr(db_obj, k):
                setattr(db_obj, k, v)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, rds_id: int) -> bool:
        db_obj = db.query(RoleDataScope).filter(RoleDataScope.id == rds_id).first()
        if db_obj:
            db.delete(db_obj)
            db.commit()
            return True
        return False


class ResourceOwnershipCRUD:
    def get_by_id(self, db: Session, ownership_id: int) -> Optional[ResourceOwnership]:
        return db.query(ResourceOwnership).options(
            joinedload(ResourceOwnership.owner_user),
            joinedload(ResourceOwnership.owner_org),
        ).filter(ResourceOwnership.id == ownership_id).first()

    def get_ownerships(self, db: Session, entity_type: str, entity_id: str, active_only: bool = True) -> List[ResourceOwnership]:
        q = db.query(ResourceOwnership).filter(
            ResourceOwnership.entity_type == entity_type,
            ResourceOwnership.entity_id == str(entity_id),
        )
        if active_only:
            q = q.filter(ResourceOwnership.is_active.is_(True))
        return q.all()

    def is_user_owner(self, db: Session, entity_type: str, entity_id: str, user_id: UUID) -> bool:
        rec = db.query(ResourceOwnership).filter(
            ResourceOwnership.entity_type == entity_type,
            ResourceOwnership.entity_id == str(entity_id),
            ResourceOwnership.owner_user_id == user_id,
            ResourceOwnership.is_active.is_(True),
        ).first()
        return rec is not None

    def get_user_owned_entity_ids(self, db: Session, entity_type: str, user_id: UUID) -> List[str]:
        rows = db.query(ResourceOwnership.entity_id).filter(
            ResourceOwnership.entity_type == entity_type,
            ResourceOwnership.owner_user_id == user_id,
            ResourceOwnership.is_active.is_(True),
        ).all()
        return [r[0] for r in rows]

    def create(self, db: Session, obj_in: Dict[str, Any]) -> ResourceOwnership:
        db_obj = ResourceOwnership(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: ResourceOwnership, obj_in: Dict[str, Any]) -> ResourceOwnership:
        for k, v in obj_in.items():
            if v is not None and hasattr(db_obj, k):
                setattr(db_obj, k, v)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi(self, db: Session, skip: int = 0, limit: int = 100, entity_type: Optional[str] = None, user_id: Optional[UUID] = None) -> Tuple[List[ResourceOwnership], int]:
        q = db.query(ResourceOwnership).options(
            joinedload(ResourceOwnership.owner_user),
        )
        if entity_type:
            q = q.filter(ResourceOwnership.entity_type == entity_type)
        if user_id:
            q = q.filter(ResourceOwnership.owner_user_id == user_id)
        total = q.count()
        items = q.order_by(ResourceOwnership.id.desc()).offset(skip).limit(limit).all()
        return items, total


class OwnershipHistoryCRUD:
    def create(self, db: Session, obj_in: Dict[str, Any]) -> OwnershipHistory:
        db_obj = OwnershipHistory(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi(self, db: Session, skip: int = 0, limit: int = 100, entity_type: Optional[str] = None, entity_id: Optional[str] = None) -> Tuple[List[OwnershipHistory], int]:
        q = db.query(OwnershipHistory)
        if entity_type:
            q = q.filter(OwnershipHistory.entity_type == entity_type)
        if entity_id:
            q = q.filter(OwnershipHistory.entity_id == str(entity_id))
        total = q.count()
        items = q.order_by(OwnershipHistory.created_at.desc()).offset(skip).limit(limit).all()
        return items, total


class OwnershipDelegationCRUD:
    def get_active_delegations_for_user(self, db: Session, delegatee_user_id: UUID, organization_id: UUID) -> List[OwnershipDelegation]:
        now = datetime.now(timezone.utc)
        return db.query(OwnershipDelegation).filter(
            OwnershipDelegation.delegatee_user_id == delegatee_user_id,
            OwnershipDelegation.organization_id == organization_id,
            OwnershipDelegation.is_active.is_(True),
            OwnershipDelegation.start_date <= now,
            OwnershipDelegation.end_date >= now,
        ).all()

    def get_multi(self, db: Session, skip: int = 0, limit: int = 100, organization_id: Optional[UUID] = None, delegator_id: Optional[UUID] = None, delegatee_id: Optional[UUID] = None) -> Tuple[List[OwnershipDelegation], int]:
        q = db.query(OwnershipDelegation).options(
            joinedload(OwnershipDelegation.delegator),
            joinedload(OwnershipDelegation.delegatee),
        )
        if organization_id:
            q = q.filter(OwnershipDelegation.organization_id == organization_id)
        if delegator_id:
            q = q.filter(OwnershipDelegation.delegator_user_id == delegator_id)
        if delegatee_id:
            q = q.filter(OwnershipDelegation.delegatee_user_id == delegatee_id)
        total = q.count()
        items = q.order_by(OwnershipDelegation.id.desc()).offset(skip).limit(limit).all()
        return items, total

    def create(self, db: Session, obj_in: Dict[str, Any]) -> OwnershipDelegation:
        db_obj = OwnershipDelegation(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: OwnershipDelegation, obj_in: Dict[str, Any]) -> OwnershipDelegation:
        for k, v in obj_in.items():
            if v is not None and hasattr(db_obj, k):
                setattr(db_obj, k, v)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


class OwnershipRuleCRUD:
    def get_by_entity(self, db: Session, entity_type: str) -> Optional[OwnershipRule]:
        return db.query(OwnershipRule).filter(
            OwnershipRule.entity_type == entity_type,
            OwnershipRule.is_active.is_(True),
        ).first()

    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> Tuple[List[OwnershipRule], int]:
        q = db.query(OwnershipRule)
        total = q.count()
        items = q.order_by(OwnershipRule.id.asc()).offset(skip).limit(limit).all()
        return items, total

    def create(self, db: Session, obj_in: Dict[str, Any]) -> OwnershipRule:
        db_obj = OwnershipRule(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: OwnershipRule, obj_in: Dict[str, Any]) -> OwnershipRule:
        for k, v in obj_in.items():
            if v is not None and hasattr(db_obj, k):
                setattr(db_obj, k, v)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


class OwnershipPolicyCRUD:
    def get_for_org(self, db: Session, organization_id: Optional[UUID]) -> Optional[OwnershipPolicy]:
        if organization_id:
            policy = db.query(OwnershipPolicy).filter(
                OwnershipPolicy.organization_id == organization_id,
                OwnershipPolicy.is_active.is_(True),
            ).first()
            if policy:
                return policy
        return db.query(OwnershipPolicy).filter(
            OwnershipPolicy.organization_id.is_(None),
            OwnershipPolicy.is_active.is_(True),
        ).first()

    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> Tuple[List[OwnershipPolicy], int]:
        q = db.query(OwnershipPolicy)
        total = q.count()
        items = q.order_by(OwnershipPolicy.id.asc()).offset(skip).limit(limit).all()
        return items, total

    def create(self, db: Session, obj_in: Dict[str, Any]) -> OwnershipPolicy:
        db_obj = OwnershipPolicy(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


class OwnershipExceptionCRUD:
    def has_active_exception(self, db: Session, user_id: UUID, entity_type: str, entity_id: str, permission_code: str) -> bool:
        now = datetime.now(timezone.utc)
        rec = db.query(OwnershipException).filter(
            OwnershipException.user_id == user_id,
            OwnershipException.entity_type == entity_type,
            OwnershipException.entity_id == str(entity_id),
            OwnershipException.permission_code == permission_code,
            OwnershipException.is_active.is_(True),
            or_(OwnershipException.expires_at.is_(None), OwnershipException.expires_at > now),
        ).first()
        return rec is not None

    def get_multi(self, db: Session, skip: int = 0, limit: int = 100, user_id: Optional[UUID] = None) -> Tuple[List[OwnershipException], int]:
        q = db.query(OwnershipException)
        if user_id:
            q = q.filter(OwnershipException.user_id == user_id)
        total = q.count()
        items = q.order_by(OwnershipException.id.desc()).offset(skip).limit(limit).all()
        return items, total

    def create(self, db: Session, obj_in: Dict[str, Any]) -> OwnershipException:
        db_obj = OwnershipException(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


# Global CRUD instances
data_scope_crud = DataScopeCRUD()
role_data_scope_crud = RoleDataScopeCRUD()
resource_ownership_crud = ResourceOwnershipCRUD()
ownership_history_crud = OwnershipHistoryCRUD()
ownership_delegation_crud = OwnershipDelegationCRUD()
ownership_rule_crud = OwnershipRuleCRUD()
ownership_policy_crud = OwnershipPolicyCRUD()
ownership_exception_crud = OwnershipExceptionCRUD()
