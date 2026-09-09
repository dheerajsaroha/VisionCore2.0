"""
retention_engine.py — Enterprise Data Retention Engine & Legal Hold Service
Sprint 9 — Enterprise Intelligence & Analytics Layer

Manages automated retention policies (purge/archive after retention_days) and
evaluates legal holds to prevent data destruction.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.db.models.all_models import (
    RetentionPolicy,
    LegalHold,
    AuditLog,
    AttendanceLog,
)

logger = logging.getLogger(__name__)


class RetentionEngineService:
    """Manages data retention policies and legal hold enforcement."""

    def upsert_retention_policy(
        self,
        db: Session,
        org_id: UUID,
        entity_category: str,
        retention_days: int = 365,
        action_type: str = "ARCHIVE",
    ) -> RetentionPolicy:
        """Creates or updates a data retention policy for an entity category."""
        existing = db.execute(
            select(RetentionPolicy).where(
                and_(
                    RetentionPolicy.organization_id == org_id,
                    RetentionPolicy.entity_category == entity_category,
                )
            )
        ).scalar_one_or_none()

        if existing:
            existing.retention_days = retention_days
            existing.action_type = action_type.upper()
            existing.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing)
            return existing
        else:
            policy = RetentionPolicy(
                organization_id=org_id,
                entity_category=entity_category,
                retention_days=retention_days,
                action_type=action_type.upper(),
                is_active=True,
            )
            db.add(policy)
            db.commit()
            db.refresh(policy)
            return policy

    def list_policies(self, db: Session, org_id: UUID) -> List[RetentionPolicy]:
        """Lists active retention policies for an organization."""
        return list(
            db.scalars(
                select(RetentionPolicy).where(
                    and_(
                        RetentionPolicy.organization_id == org_id,
                        RetentionPolicy.is_active.is_(True),
                    )
                )
            ).all()
        )

    def create_legal_hold(
        self,
        db: Session,
        org_id: UUID,
        placed_by_user_id: int,
        hold_name: str,
        entity_category: str,
        description: Optional[str] = None,
        target_user_id: Optional[int] = None,
    ) -> LegalHold:
        """Places a legal hold to freeze data retention purging."""
        hold = LegalHold(
            organization_id=org_id,
            placed_by_user_id=placed_by_user_id,
            hold_name=hold_name,
            entity_category=entity_category,
            description=description,
            target_user_id=target_user_id,
            is_active=True,
        )
        db.add(hold)
        db.commit()
        db.refresh(hold)
        return hold

    def list_legal_holds(self, db: Session, org_id: UUID) -> List[LegalHold]:
        """Lists active legal holds for an organization."""
        return list(
            db.scalars(
                select(LegalHold).where(
                    and_(
                        LegalHold.organization_id == org_id,
                        LegalHold.is_active.is_(True),
                    )
                )
            ).all()
        )

    def is_legal_hold_active(
        self, db: Session, org_id: UUID, entity_category: str, target_user_id: Optional[int] = None
    ) -> bool:
        """Checks whether an active legal hold covers the requested category/user."""
        filters = [
            LegalHold.organization_id == org_id,
            LegalHold.entity_category == entity_category,
            LegalHold.is_active.is_(True),
        ]
        if target_user_id:
            filters.append(LegalHold.target_user_id == target_user_id)

        active_hold = db.execute(select(LegalHold).where(and_(*filters))).scalar_one_or_none()
        return active_hold is not None

    def evaluate_and_enforce(self, db: Session, org_id: UUID) -> Dict[str, Any]:
        """
        Evaluates retention policies against data records.
        Skips records protected by active legal holds.
        """
        policies = self.list_policies(db, org_id)
        processed_summary = []

        for p in policies:
            # Check legal hold for category
            if self.is_legal_hold_active(db, org_id, p.entity_category):
                processed_summary.append({
                    "category": p.entity_category,
                    "status": "SKIPPED_LEGAL_HOLD",
                    "affected_records": 0,
                })
                continue

            cutoff_date = datetime.now(timezone.utc) - timedelta(days=p.retention_days)
            affected_count = 0

            if p.entity_category == "attendance":
                from app.db.models.all_models import User
                org_user_ids = [u.id for u in db.scalars(select(User).where(User.org_id == org_id)).all()]
                old_logs = db.scalars(
                    select(AttendanceLog).where(
                        and_(
                            AttendanceLog.user_id.in_(org_user_ids),
                            AttendanceLog.check_in < cutoff_date,
                        )
                    )
                ).all()
                affected_count = len(old_logs)
                if p.action_type == "PURGE":
                    for log in old_logs:
                        db.delete(log)
                    db.commit()

            processed_summary.append({
                "category": p.entity_category,
                "retention_days": p.retention_days,
                "action_type": p.action_type,
                "status": "COMPLETED",
                "affected_records": affected_count,
            })

        return {
            "organization_id": str(org_id),
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "summary": processed_summary,
        }


retention_engine_service = RetentionEngineService()
