"""
distribution_engine.py — Policy Distribution Analytics & Targeting Engine
Sprint 4 — Entity 5
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models.all_models import (
    PolicyDocument, PolicyDistribution, PolicyAcknowledgement, PolicyCategory, User
)
from app.crud.crud_policy import (
    crud_policy_document, crud_policy_distribution, crud_policy_acknowledgement
)


class DistributionEngine:
    """Handles policy distribution targeting, stats, and bulk operations."""

    @staticmethod
    def get_distribution_stats(db: Session, org_id: UUID) -> Dict[str, Any]:
        """Get distribution statistics per policy."""
        total_distributions = db.query(PolicyDistribution).join(
            PolicyDocument, PolicyDistribution.document_id == PolicyDocument.id
        ).filter(
            PolicyDocument.organization_id == org_id
        ).count()

        org_wide = db.query(PolicyDistribution).join(
            PolicyDocument, PolicyDistribution.document_id == PolicyDocument.id
        ).filter(
            PolicyDocument.organization_id == org_id,
            PolicyDistribution.distribution_type == "organization"
        ).count()

        dept_targeted = db.query(PolicyDistribution).join(
            PolicyDocument, PolicyDistribution.document_id == PolicyDocument.id
        ).filter(
            PolicyDocument.organization_id == org_id,
            PolicyDistribution.distribution_type == "department"
        ).count()

        user_targeted = db.query(PolicyDistribution).join(
            PolicyDocument, PolicyDistribution.document_id == PolicyDocument.id
        ).filter(
            PolicyDocument.organization_id == org_id,
            PolicyDistribution.distribution_type == "user"
        ).count()

        # Most distributed policies
        top_policies = db.query(
            PolicyDistribution.document_id,
            func.count(PolicyDistribution.id).label("dist_count")
        ).join(
            PolicyDocument, PolicyDistribution.document_id == PolicyDocument.id
        ).filter(
            PolicyDocument.organization_id == org_id
        ).group_by(PolicyDistribution.document_id).order_by(
            func.count(PolicyDistribution.id).desc()
        ).limit(5).all()

        top_5 = []
        for doc_id, count in top_policies:
            doc = crud_policy_document.get_by_id(db, doc_id)
            if doc:
                top_5.append({"policy_id": doc_id, "title": doc.title, "distributions": count})

        return {
            "total_distributions": total_distributions,
            "org_wide_distributions": org_wide,
            "dept_targeted_distributions": dept_targeted,
            "user_targeted_distributions": user_targeted,
            "top_distributed_policies": top_5
        }

    @staticmethod
    def get_users_for_policy(db: Session, doc_id: int) -> List[Dict[str, Any]]:
        """Get users who should receive a policy based on its distributions."""
        doc = crud_policy_document.get_by_id(db, doc_id)
        if not doc:
            return []

        distributions = crud_policy_distribution.get_for_doc(db, doc_id)
        target_user_ids = set()

        for dist in distributions:
            if dist.distribution_type == "organization":
                users = db.query(User.id, User.full_name, User.email).filter(
                    User.org_id == doc.organization_id,
                    User.is_deleted == 0
                ).all()
                for u in users:
                    target_user_ids.add(u.id)
            elif dist.distribution_type == "department" and dist.target_dept_id:
                users = db.query(User.id).filter(
                    User.dept_id == dist.target_dept_id,
                    User.is_deleted == 0
                ).all()
                for u in users:
                    target_user_ids.add(u.id)
            elif dist.distribution_type == "user" and dist.target_user_id:
                target_user_ids.add(dist.target_user_id)

        acked_user_ids = set()
        acks = crud_policy_acknowledgement.get_for_doc(db, doc_id)
        for a in acks:
            acked_user_ids.add(a.user_id)

        result = []
        for uid in target_user_ids:
            user = db.query(User).filter(User.id == uid).first()
            if user:
                result.append({
                    "user_id": uid,
                    "full_name": user.full_name,
                    "email": user.email,
                    "has_acknowledged": uid in acked_user_ids
                })

        return result

    @staticmethod
    def distribute_policy_to_org(db: Session, doc_id: int, org_id: UUID) -> PolicyDistribution:
        """Distribute a policy organization-wide."""
        existing = db.query(PolicyDistribution).filter(
            PolicyDistribution.document_id == doc_id,
            PolicyDistribution.distribution_type == "organization"
        ).first()
        if existing:
            return existing

        return crud_policy_distribution.create(db, doc_id, {
            "distribution_type": "organization",
            "target_org_id": org_id
        })

    @staticmethod
    def distribute_policy_to_department(db: Session, doc_id: int, dept_id: int) -> PolicyDistribution:
        """Distribute a policy to a specific department."""
        return crud_policy_distribution.create(db, doc_id, {
            "distribution_type": "department",
            "target_dept_id": dept_id
        })

    @staticmethod
    def distribute_policy_to_user(db: Session, doc_id: int, user_id: int) -> PolicyDistribution:
        """Distribute a policy to a specific user."""
        return crud_policy_distribution.create(db, doc_id, {
            "distribution_type": "user",
            "target_user_id": user_id
        })


distribution_engine = DistributionEngine()

