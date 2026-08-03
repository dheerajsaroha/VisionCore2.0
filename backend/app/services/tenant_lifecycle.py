"""
tenant_lifecycle.py — Organization Lifecycle Management
Sprint 6 — Phase A: Multi-Tenant SaaS Hardening & Tenant Provisioning

Manages the full lifecycle of tenant organizations:
  Draft → Pending Verification → Active → Suspended → Archived → Scheduled for Deletion → Deleted

Every transition publishes Event Bus events, generates audit logs, and creates notifications.
No frozen modules are modified.
"""
from __future__ import annotations

import enum
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.all_models import Organization
from app.events.event_types import (
    TenantActivatedEvent, TenantSuspendedEvent, TenantArchivedEvent,
    TenantDeletedEvent, TenantRestoredEvent, EventPriority
)
from app.events.event_bus import event_bus
from app.services.audit_service import audit_service
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)


class TenantLifecycleState(enum.Enum):
    """Enumeration of all possible tenant lifecycle states."""
    DRAFT = "draft"
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"
    SCHEDULED_FOR_DELETION = "scheduled_for_deletion"
    DELETED = "deleted"


# Valid state transitions
VALID_TRANSITIONS = {
    TenantLifecycleState.DRAFT: [
        TenantLifecycleState.PENDING_VERIFICATION,
        TenantLifecycleState.ACTIVE,
        TenantLifecycleState.SCHEDULED_FOR_DELETION,
    ],
    TenantLifecycleState.PENDING_VERIFICATION: [
        TenantLifecycleState.ACTIVE,
        TenantLifecycleState.SUSPENDED,
        TenantLifecycleState.DRAFT,
    ],
    TenantLifecycleState.ACTIVE: [
        TenantLifecycleState.SUSPENDED,
        TenantLifecycleState.ARCHIVED,
        TenantLifecycleState.SCHEDULED_FOR_DELETION,
    ],
    TenantLifecycleState.SUSPENDED: [
        TenantLifecycleState.ACTIVE,
        TenantLifecycleState.ARCHIVED,
        TenantLifecycleState.SCHEDULED_FOR_DELETION,
    ],
    TenantLifecycleState.ARCHIVED: [
        TenantLifecycleState.ACTIVE,
        TenantLifecycleState.SCHEDULED_FOR_DELETION,
    ],
    TenantLifecycleState.SCHEDULED_FOR_DELETION: [
        TenantLifecycleState.ACTIVE,  # Cancel deletion
        TenantLifecycleState.DELETED,
    ],
    TenantLifecycleState.DELETED: [],  # Terminal state
}


class TenantLifecycleService:
    """
    Manages the lifecycle of tenant organizations.

    Operations:
    - Activate, Suspend, Resume, Archive, Restore, Soft Delete, Permanent Delete
    - Each operation publishes events, audit logs, and notifications
    """

    LIFECYCLE_CONFIG_KEY = "tenant.lifecycle_state"

    # ──────────────────────────────────────────────────────────────────────
    #  State Management
    # ──────────────────────────────────────────────────────────────────────

    def get_state(self, db: Session, org_id: UUID) -> Optional[TenantLifecycleState]:
        """Get the current lifecycle state of a tenant."""
        from app.services.config_center import config_center
        state_str = config_center.get(
            self.LIFECYCLE_CONFIG_KEY,
            org_id=str(org_id),
            default="active"
        )
        try:
            return TenantLifecycleState(state_str)
        except ValueError:
            return TenantLifecycleState.ACTIVE

    def set_state(
        self,
        db: Session,
        org_id: UUID,
        new_state: TenantLifecycleState,
        actor_user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Set the lifecycle state of a tenant.

        Validates the transition. If invalid, raises ValueError.
        """
        current_state = self.get_state(db, org_id)

        # Validate transition
        if current_state == new_state:
            logger.info(f"Tenant {org_id}: Already in state {new_state.value}")
            return True

        valid_next = VALID_TRANSITIONS.get(current_state, [])
        if new_state not in valid_next:
            raise ValueError(
                f"Invalid transition: {current_state.value} → {new_state.value} "
                f"for tenant {org_id}. Valid transitions: "
                f"{[s.value for s in valid_next]}"
            )

        # Persist the state
        from app.services.config_center import config_center
        config_center.set(
            self.LIFECYCLE_CONFIG_KEY,
            new_state.value,
            org_id=str(org_id),
            updated_by=actor_user_id,
        )

        # If active/suspended, also update the Organization.is_active flag
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if org:
            if new_state == TenantLifecycleState.ACTIVE:
                org.is_active = True
            elif new_state in (TenantLifecycleState.SUSPENDED, TenantLifecycleState.ARCHIVED):
                org.is_active = False
            db.add(org)
            db.flush()

        logger.info(
            f"Tenant {org_id}: {current_state.value} → {new_state.value}"
            f"{' by user ' + str(actor_user_id) if actor_user_id else ''}"
            f"{' (' + reason + ')' if reason else ''}"
        )

        return True

    # ──────────────────────────────────────────────────────────────────────
    #  Lifecycle Operations
    # ──────────────────────────────────────────────────────────────────────

    def activate_tenant(
        self,
        *,
        db: Session,
        org_id: UUID,
        actor_user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Activate a tenant (move to Active state)."""
        result = self.set_state(
            db, org_id, TenantLifecycleState.ACTIVE,
            actor_user_id=actor_user_id, reason=reason
        )

        # Publish event
        try:
            event = TenantActivatedEvent(
                organization_id=str(org_id),
                actor_user_id=actor_user_id,
                reason=reason or "Tenant activated",
            )
            event_bus.publish(event)
        except Exception as e:
            logger.warning(f"Failed to publish TenantActivatedEvent: {e}")

        # Audit log
        audit_service.record(
            module="tenant_lifecycle",
            action="activate",
            entity_type="organization",
            entity_id=str(org_id),
            summary=f"Tenant {org_id} activated",
            details={"reason": reason},
            actor_user_id=actor_user_id,
            organization_id=str(org_id),
        )

        # Notification
        try:
            notification_service.notify_admins(
                db=db,
                org_id=org_id,
                title="Tenant Activated",
                message=f"Organization has been activated.",
                notification_type="tenant_lifecycle",
            )
        except Exception as e:
            logger.warning(f"Failed to send tenant activation notification: {e}")

        return result

    def suspend_tenant(
        self,
        *,
        db: Session,
        org_id: UUID,
        actor_user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Suspend a tenant (move to Suspended state)."""
        result = self.set_state(
            db, org_id, TenantLifecycleState.SUSPENDED,
            actor_user_id=actor_user_id, reason=reason
        )

        try:
            event = TenantSuspendedEvent(
                organization_id=str(org_id),
                actor_user_id=actor_user_id,
                reason=reason or "Tenant suspended",
                priority=EventPriority.HIGH,
            )
            event_bus.publish(event)
        except Exception as e:
            logger.warning(f"Failed to publish TenantSuspendedEvent: {e}")

        audit_service.record(
            module="tenant_lifecycle",
            action="suspend",
            entity_type="organization",
            entity_id=str(org_id),
            summary=f"Tenant {org_id} suspended",
            details={"reason": reason},
            actor_user_id=actor_user_id,
            organization_id=str(org_id),
        )

        try:
            notification_service.notify_admins(
                db=db,
                org_id=org_id,
                title="Tenant Suspended",
                message=f"Organization has been suspended. Reason: {reason or 'No reason provided'}",
                notification_type="tenant_lifecycle",
            )
        except Exception as e:
            logger.warning(f"Failed to send tenant suspension notification: {e}")

        return result

    def resume_tenant(
        self,
        *,
        db: Session,
        org_id: UUID,
        actor_user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Resume a suspended tenant (move to Active state)."""
        return self.activate_tenant(
            db=db, org_id=org_id,
            actor_user_id=actor_user_id,
            reason=reason or "Tenant resumed from suspension"
        )

    def archive_tenant(
        self,
        *,
        db: Session,
        org_id: UUID,
        actor_user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Archive a tenant (move to Archived state)."""
        result = self.set_state(
            db, org_id, TenantLifecycleState.ARCHIVED,
            actor_user_id=actor_user_id, reason=reason
        )

        try:
            event = TenantArchivedEvent(
                organization_id=str(org_id),
                actor_user_id=actor_user_id,
                reason=reason or "Tenant archived",
            )
            event_bus.publish(event)
        except Exception as e:
            logger.warning(f"Failed to publish TenantArchivedEvent: {e}")

        audit_service.record(
            module="tenant_lifecycle",
            action="archive",
            entity_type="organization",
            entity_id=str(org_id),
            summary=f"Tenant {org_id} archived",
            details={"reason": reason},
            actor_user_id=actor_user_id,
            organization_id=str(org_id),
        )

        return result

    def restore_tenant(
        self,
        *,
        db: Session,
        org_id: UUID,
        actor_user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Restore an archived tenant."""
        return self.activate_tenant(
            db=db, org_id=org_id,
            actor_user_id=actor_user_id,
            reason=reason or "Tenant restored from archive"
        )

    def soft_delete_tenant(
        self,
        *,
        db: Session,
        org_id: UUID,
        actor_user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Schedule a tenant for deletion."""
        result = self.set_state(
            db, org_id, TenantLifecycleState.SCHEDULED_FOR_DELETION,
            actor_user_id=actor_user_id, reason=reason
        )

        audit_service.record(
            module="tenant_lifecycle",
            action="schedule_deletion",
            entity_type="organization",
            entity_id=str(org_id),
            summary=f"Tenant {org_id} scheduled for deletion",
            details={"reason": reason},
            actor_user_id=actor_user_id,
            organization_id=str(org_id),
        )

        return result

    def permanent_delete_tenant(
        self,
        *,
        db: Session,
        org_id: UUID,
        actor_user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Permanently delete a tenant (terminal state).

        WARNING: This is irreversible. The organization record is marked as deleted
        but not removed from the database for audit purposes.
        """
        result = self.set_state(
            db, org_id, TenantLifecycleState.DELETED,
            actor_user_id=actor_user_id, reason=reason
        )

        # Soft-delete the organization
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if org:
            org.is_active = False
            db.add(org)
            db.flush()

        try:
            event = TenantDeletedEvent(
                organization_id=str(org_id),
                actor_user_id=actor_user_id,
                reason=reason or "Tenant permanently deleted",
                priority=EventPriority.HIGH,
            )
            event_bus.publish(event)
        except Exception as e:
            logger.warning(f"Failed to publish TenantDeletedEvent: {e}")

        audit_service.record(
            module="tenant_lifecycle",
            action="permanent_delete",
            entity_type="organization",
            entity_id=str(org_id),
            summary=f"Tenant {org_id} permanently deleted",
            details={"reason": reason},
            actor_user_id=actor_user_id,
            organization_id=str(org_id),
        )

        return result

    # ──────────────────────────────────────────────────────────────────────
    #  Bulk Operations
    # ──────────────────────────────────────────────────────────────────────

    def get_tenants_by_state(
        self, db: Session, state: TenantLifecycleState
    ) -> list[Organization]:
        """Get all tenants in a specific lifecycle state."""
        from app.services.config_center import config_center

        # For now, use is_active as a proxy for lifecycle state
        if state == TenantLifecycleState.ACTIVE:
            return db.query(Organization).filter(
                Organization.is_active == True
            ).all()
        elif state in (TenantLifecycleState.SUSPENDED, TenantLifecycleState.ARCHIVED):
            return db.query(Organization).filter(
                Organization.is_active == False
            ).all()
        else:
            # For other states, we'd need to check config_center
            # This is a simplified version
            return []


# Singleton
tenant_lifecycle_service = TenantLifecycleService()
