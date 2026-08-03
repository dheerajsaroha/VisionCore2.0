"""
policy_engine.py — Policy Center & Compliance Management Engine
Sprint 4 — Entity 5
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.db.models.all_models import (
    PolicyDocument, PolicyAcknowledgement, PolicyDistribution, PolicyVersion,
    ComplianceRule, ComplianceRecord, ComplianceAudit, PolicyNotification, User
)


class PolicyCenterEngine:
    """Business logic engine for Policy Center operations."""

    @staticmethod
    def get_dashboard_analytics(db: Session, org_id: UUID) -> Dict[str, Any]:
        """Compute policy center dashboard metrics."""
        now = datetime.now(timezone.utc)

        # Policy counts by status
        total_policies = db.query(PolicyDocument).filter(
            PolicyDocument.organization_id == org_id
        ).count()

        draft = db.query(PolicyDocument).filter(
            PolicyDocument.organization_id == org_id,
            PolicyDocument.status == "draft"
        ).count()

        published = db.query(PolicyDocument).filter(
            PolicyDocument.organization_id == org_id,
            PolicyDocument.status == "published"
        ).count()

        expired = db.query(PolicyDocument).filter(
            PolicyDocument.organization_id == org_id,
            PolicyDocument.status == "expired"
        ).count()

        # Categories
        total_categories = db.query(func.count(PolicyDocument.id.distinct())).filter(
            PolicyDocument.organization_id == org_id,
            PolicyDocument.category_id.isnot(None)
        ).scalar() or 0

        # Pending acknowledgements
        pending_acks = db.query(PolicyAcknowledgement).join(
            PolicyDocument, PolicyAcknowledgement.document_id == PolicyDocument.id
        ).filter(
            PolicyDocument.organization_id == org_id,
            PolicyAcknowledgement.is_acknowledged == False
        ).count()

        # Expiring soon (within 30 days)
        expiring_soon = db.query(PolicyDocument).filter(
            PolicyDocument.organization_id == org_id,
            PolicyDocument.status == "published",
            PolicyDocument.expiry_date.isnot(None),
            PolicyDocument.expiry_date <= now + timedelta(days=30),
            PolicyDocument.expiry_date > now
        ).count()

        # Compliance rate
        compliance_records = db.query(ComplianceRecord).filter(
            ComplianceRecord.organization_id == org_id
        ).all()
        total_comp = len(compliance_records)
        compliant_comp = sum(1 for r in compliance_records if r.is_compliant)
        comp_rate = round((compliant_comp / max(1, total_comp)) * 100, 1) if total_comp > 0 else 0.0

        # Compliance breakdown by status
        breakdown = db.query(
            ComplianceRecord.status,
            func.count(ComplianceRecord.id)
        ).filter(
            ComplianceRecord.organization_id == org_id
        ).group_by(ComplianceRecord.status).all()

        compliance_breakdown = [
            {"status": s, "count": c} for s, c in breakdown
        ]

        return {
            "total_policies": total_policies,
            "draft_policies": draft,
            "published_policies": published,
            "expired_policies": expired,
            "total_categories": total_categories,
            "pending_acknowledgements": pending_acks,
            "overall_compliance_rate": comp_rate,
            "expiring_soon_count": expiring_soon,
            "compliance_breakdown": compliance_breakdown
        }

    @staticmethod
    def get_user_pending_acknowledgements(db: Session, org_id: UUID, user_id: int) -> List[Dict[str, Any]]:
        """Get list of policies pending acknowledgement for a user."""
        now = datetime.now(timezone.utc)

        # Find policies distributed to this user
        distributed_policies = db.query(PolicyDocument.id).join(
            PolicyDistribution, PolicyDistribution.document_id == PolicyDocument.id
        ).filter(
            PolicyDocument.organization_id == org_id,
            PolicyDocument.status.in_(["published", "effective"]),
            PolicyDocument.requires_acknowledgement == True,
            PolicyDocument.effective_date <= now,
            or_(
                PolicyDistribution.distribution_type == "organization",
                PolicyDistribution.target_user_id == user_id,
                PolicyDistribution.target_org_id == org_id,
                PolicyDistribution.distribution_type == "all"
            )
        ).scalar_subquery()

        # Already acknowledged
        acked = db.query(PolicyAcknowledgement.document_id).filter(
            PolicyAcknowledgement.user_id == user_id,
            PolicyAcknowledgement.is_acknowledged == True
        ).scalar_subquery()

        pending = db.query(PolicyDocument).filter(
            PolicyDocument.id.in_(distributed_policies),
            ~PolicyDocument.id.in_(acked)
        ).all()

        return [
            {
                "id": p.id,
                "title": p.title,
                "document_number": p.document_number,
                "policy_type": p.policy_type,
                "published_at": p.published_at,
                "effective_date": p.effective_date,
                "requires_signature": p.requires_signature,
                "current_version": p.current_version
            }
            for p in pending
        ]

    @staticmethod
    def run_compliance_check(db: Session, org_id: UUID, user_id: int) -> Dict[str, Any]:
        """Run compliance checks for a user against all active rules."""
        rules = db.query(ComplianceRule).filter(
            ComplianceRule.organization_id == org_id,
            ComplianceRule.is_active.is_(True)
        ).all()

        now = datetime.now(timezone.utc)
        results = []
        total_weight = 0.0
        weighted_compliant = 0.0

        for rule in rules:
            # Determine policies governed by this rule
            q = db.query(PolicyDocument).filter(
                PolicyDocument.organization_id == org_id,
                PolicyDocument.status.in_(["published", "effective"])
            )
            if rule.policy_type_filter:
                q = q.filter(PolicyDocument.policy_type == rule.policy_type_filter)

            policies = q.all()

            for policy in policies:
                # Check if policy is distributed to this user
                distribution = db.query(PolicyDistribution).filter(
                    PolicyDistribution.document_id == policy.id,
                    PolicyDistribution.is_active.is_(True),
                    or_(
                        PolicyDistribution.distribution_type == "organization",
                        PolicyDistribution.target_user_id == user_id,
                        PolicyDistribution.distribution_type == "all"
                    )
                ).first()

                if not distribution:
                    continue

                if rule.rule_type == "acknowledgement_required":
                    ack = db.query(PolicyAcknowledgement).filter(
                        PolicyAcknowledgement.document_id == policy.id,
                        PolicyAcknowledgement.user_id == user_id
                    ).first()

                    is_compliant = ack is not None and ack.is_acknowledged
                    due = now + timedelta(days=rule.grace_period_days) if not is_compliant else None

                    from app.crud.crud_policy import crud_compliance_record
                    crud_compliance_record.create_or_update(
                        db, org_id, policy.id, user_id, rule.id, is_compliant, due
                    )

                    if is_compliant:
                        weighted_compliant += rule.weight
                    total_weight += rule.weight

                    results.append({
                        "policy_id": policy.id,
                        "policy_title": policy.title,
                        "rule_name": rule.name,
                        "rule_type": rule.rule_type,
                        "is_compliant": is_compliant,
                        "due_date": due
                    })

                elif rule.rule_type == "mandatory_read":
                    ack = db.query(PolicyAcknowledgement).filter(
                        PolicyAcknowledgement.document_id == policy.id,
                        PolicyAcknowledgement.user_id == user_id
                    ).first()
                    is_compliant = ack is not None

                    if is_compliant:
                        weighted_compliant += rule.weight
                    total_weight += rule.weight

                    results.append({
                        "policy_id": policy.id,
                        "policy_title": policy.title,
                        "rule_name": rule.name,
                        "rule_type": rule.rule_type,
                        "is_compliant": is_compliant
                    })

        overall_score = round((weighted_compliant / max(1.0, total_weight)) * 100, 1) if total_weight > 0 else 100.0

        # Log audit
        audit = ComplianceAudit(
            organization_id=org_id,
            user_id=user_id,
            audit_type="compliance_check",
            description=f"Compliance check completed. Score: {overall_score}%",
            meta_data={"results": results, "score": overall_score}
        )
        db.add(audit)
        db.commit()

        return {
            "user_id": user_id,
            "overall_compliance_score": overall_score,
            "total_rules_evaluated": len(results),
            "compliant_count": sum(1 for r in results if r["is_compliant"]),
            "non_compliant_count": sum(1 for r in results if not r["is_compliant"]),
            "details": results
        }

    @staticmethod
    def get_expiring_policies(db: Session, org_id: UUID, days: int = 30) -> List[PolicyDocument]:
        """Get policies expiring within the specified number of days."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days)
        return db.query(PolicyDocument).filter(
            PolicyDocument.organization_id == org_id,
            PolicyDocument.status == "published",
            PolicyDocument.expiry_date.isnot(None),
            PolicyDocument.expiry_date <= cutoff,
            PolicyDocument.expiry_date > now
        ).all()


policy_engine = PolicyCenterEngine()

