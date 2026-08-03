"""
ownership_service.py — Reusable Ownership Engine (Sprint 2, Entity 3)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.crud.crud_scope import (
    resource_ownership_crud,
    ownership_history_crud,
    ownership_delegation_crud,
)
from app.db.models.all_models import (
    ResourceOwnership,
    OwnershipDelegation,
    User,
)

logger = logging.getLogger(__name__)


class OwnershipService:
    @staticmethod
    def assign_ownership(
        db: Session,
        entity_type: str,
        entity_id: str,
        owner_user_id: Optional[Any],
        owner_type: str = "creator",
        owner_org_id: Optional[UUID] = None,
        actor_user_id: Optional[Any] = None,
        is_primary: bool = True,
        meta_data: Optional[Dict[str, Any]] = None,
    ) -> ResourceOwnership:
        """Assign ownership of a resource."""
        rec = resource_ownership_crud.create(db, {
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "owner_type": owner_type,
            "owner_user_id": owner_user_id,
            "owner_org_id": owner_org_id,
            "is_primary": is_primary,
            "is_active": True,
            "meta_data": meta_data or {},
        })
        ownership_history_crud.create(db, {
            "resource_ownership_id": rec.id,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "action": "assigned",
            "previous_owner_user_id": None,
            "new_owner_user_id": owner_user_id,
            "previous_owner_type": None,
            "new_owner_type": owner_type,
            "actor_user_id": actor_user_id or owner_user_id,
            "reason": f"Initial ownership assignment ({owner_type})",
        })
        return rec

    @staticmethod
    def transfer_ownership(
        db: Session,
        entity_type: str,
        entity_id: str,
        new_owner_user_id: Any,
        new_owner_type: str = "assignee",
        actor_user_id: Optional[Any] = None,
        reason: Optional[str] = "Ownership transfer",
    ) -> ResourceOwnership:
        """Transfer ownership with audit trail."""
        existing_list = resource_ownership_crud.get_ownerships(db, entity_type, str(entity_id), active_only=True)
        prev_user_id = None
        prev_owner_type = None

        if existing_list:
            primary = existing_list[0]
            prev_user_id = primary.owner_user_id
            prev_owner_type = primary.owner_type
            resource_ownership_crud.update(db, primary, {"is_active": False})

        new_ownership = resource_ownership_crud.create(db, {
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "owner_type": new_owner_type,
            "owner_user_id": new_owner_user_id,
            "is_primary": True,
            "is_active": True,
            "meta_data": {"transferred_at": datetime.now(timezone.utc).isoformat()},
        })
        ownership_history_crud.create(db, {
            "resource_ownership_id": new_ownership.id,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "action": "transferred",
            "previous_owner_user_id": prev_user_id,
            "new_owner_user_id": new_owner_user_id,
            "previous_owner_type": prev_owner_type,
            "new_owner_type": new_owner_type,
            "actor_user_id": actor_user_id,
            "reason": reason,
        })
        return new_ownership

    @staticmethod
    def create_delegation(
        db: Session,
        delegator_user_id: Any,
        delegatee_user_id: Any,
        organization_id: UUID,
        start_date: datetime,
        end_date: datetime,
        entity_type: Optional[str] = None,
        permission_code: Optional[str] = None,
        reason: Optional[str] = "Temporary ownership delegation",
    ) -> OwnershipDelegation:
        """Create temporary delegation with audit."""
        del_rec = ownership_delegation_crud.create(db, {
            "delegator_user_id": delegator_user_id,
            "delegatee_user_id": delegatee_user_id,
            "organization_id": organization_id,
            "entity_type": entity_type,
            "permission_code": permission_code,
            "start_date": start_date,
            "end_date": end_date,
            "is_active": True,
            "reason": reason,
        })
        ownership_history_crud.create(db, {
            "entity_type": entity_type or "*",
            "entity_id": "*",
            "action": "delegated",
            "previous_owner_user_id": delegator_user_id,
            "new_owner_user_id": delegatee_user_id,
            "previous_owner_type": "owner",
            "new_owner_type": "delegate",
            "actor_user_id": delegator_user_id,
            "reason": reason,
        })
        return del_rec

    @staticmethod
    def validate_ownership(
        db: Session,
        user_id: Any,
        entity_type: str,
        entity_id: str,
    ) -> bool:
        """Check if user owns or has active delegation for a resource."""
        is_direct = resource_ownership_crud.is_user_owner(db, entity_type, str(entity_id), user_id)
        if is_direct:
            return True
        # Check for active delegation on entity_type
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.org_id:
            delegations = db.query(OwnershipDelegation).filter(
                OwnershipDelegation.delegatee_user_id == user_id,
                OwnershipDelegation.organization_id == user.org_id,
                OwnershipDelegation.is_active.is_(True),
                OwnershipDelegation.start_date <= now,
                OwnershipDelegation.end_date >= now,
            ).all()
            if delegations:
                return True
        return False

    @staticmethod
    def revoke_delegation(db: Session, delegation_id: int, actor_user_id: Any = None) -> bool:
        """Revoke an active delegation."""
        delegation = db.query(OwnershipDelegation).filter(OwnershipDelegation.id == delegation_id).first()
        if delegation:
            delegation.is_active = False
            db.add(delegation)
            ownership_history_crud.create(db, {
                "entity_type": delegation.entity_type or "*",
                "entity_id": "*",
                "action": "revoked",
                "previous_owner_user_id": delegation.delegatee_user_id,
                "new_owner_user_id": delegation.delegator_user_id,
                "previous_owner_type": "delegate",
                "new_owner_type": "owner",
                "actor_user_id": actor_user_id,
                "reason": "Delegation revoked",
            })
            db.commit()
            return True
        return False
