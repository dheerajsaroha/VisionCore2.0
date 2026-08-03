"""
policy_search_service.py — Full-text Search & Advanced Filtering Service for Policy Center
Sprint 4 — Entity 5
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, cast, String

from app.db.models.all_models import (
    PolicyDocument, PolicyCategory, PolicyVersion, PolicyTag, User
)


class PolicySearchService:
    """Full-text and faceted search across policy documents."""

    @staticmethod
    def search_policies(
        db: Session,
        org_id: UUID,
        query: Optional[str] = None,
        status: Optional[str] = None,
        policy_type: Optional[str] = None,
        category_id: Optional[int] = None,
        tag_id: Optional[int] = None,
        is_mandatory: Optional[bool] = None,
        owner_user_id: Optional[int] = None,
        sort_by: str = "updated_at",
        sort_desc: bool = True,
        skip: int = 0,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Search policies with advanced filtering and full-text search."""
        q = db.query(PolicyDocument).filter(PolicyDocument.organization_id == org_id)

        # Full-text search on title, content, summary, document_number
        if query:
            search_filter = or_(
                PolicyDocument.title.ilike(f"%{query}%"),
                PolicyDocument.content.ilike(f"%{query}%"),
                PolicyDocument.summary.ilike(f"%{query}%"),
                PolicyDocument.document_number.ilike(f"%{query}%"),
                PolicyDocument.author.ilike(f"%{query}%"),
            )
            q = q.filter(search_filter)

        # Filters
        if status:
            q = q.filter(PolicyDocument.status == status)
        if policy_type:
            q = q.filter(PolicyDocument.policy_type == policy_type)
        if category_id:
            q = q.filter(PolicyDocument.category_id == category_id)
        if is_mandatory is not None:
            q = q.filter(PolicyDocument.is_mandatory.is_(is_mandatory))
        if owner_user_id:
            q = q.filter(PolicyDocument.owner_user_id == owner_user_id)

        # Tag filter via JSONB
        if tag_id:
            q = q.filter(PolicyDocument.tags.contains([{"id": tag_id}]))

        # Sorting
        sort_col = getattr(PolicyDocument, sort_by, PolicyDocument.updated_at)
        if sort_desc:
            q = q.order_by(sort_col.desc())
        else:
            q = q.order_by(sort_col.asc())

        total = q.count()

        # Pagination
        items = q.offset(skip).limit(limit).all()

        results = []
        for doc in items:
            category = db.query(PolicyCategory).filter(
                PolicyCategory.id == doc.category_id
            ).first() if doc.category_id else None

            owner = db.query(User).filter(User.id == doc.owner_user_id).first() if doc.owner_user_id else None
            approver = db.query(User).filter(User.id == doc.approver_user_id).first() if doc.approver_user_id else None

            results.append({
                "id": doc.id,
                "title": doc.title,
                "document_number": doc.document_number,
                "policy_type": doc.policy_type,
                "status": doc.status,
                "category": category.name if category else None,
                "summary": doc.summary,
                "is_mandatory": doc.is_mandatory,
                "current_version": doc.current_version,
                "owner_name": owner.full_name if owner else None,
                "approver_name": approver.full_name if approver else None,
                "effective_date": doc.effective_date,
                "expiry_date": doc.expiry_date,
                "published_at": doc.published_at,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
                "tags": doc.tags
            })

        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "results": results
        }

    @staticmethod
    def get_policy_statistics(db: Session, org_id: UUID) -> Dict[str, Any]:
        """Get aggregated statistics about policies."""
        total = db.query(PolicyDocument).filter(
            PolicyDocument.organization_id == org_id
        ).count()

        by_status = db.query(
            PolicyDocument.status,
            func.count(PolicyDocument.id)
        ).filter(
            PolicyDocument.organization_id == org_id
        ).group_by(PolicyDocument.status).all()

        by_type = db.query(
            PolicyDocument.policy_type,
            func.count(PolicyDocument.id)
        ).filter(
            PolicyDocument.organization_id == org_id
        ).group_by(PolicyDocument.policy_type).all()

        by_category = db.query(
            PolicyCategory.name,
            func.count(PolicyDocument.id)
        ).join(
            PolicyCategory, PolicyDocument.category_id == PolicyCategory.id
        ).filter(
            PolicyDocument.organization_id == org_id
        ).group_by(PolicyCategory.name).all()

        mandatory_count = db.query(PolicyDocument).filter(
            PolicyDocument.organization_id == org_id,
            PolicyDocument.is_mandatory.is_(True)
        ).count()

        return {
            "total_policies": total,
            "mandatory_policies": mandatory_count,
            "by_status": {s: c for s, c in by_status},
            "by_type": {t: c for t, c in by_type},
            "by_category": {c: count for c, count in by_category}
        }


policy_search_service = PolicySearchService()

