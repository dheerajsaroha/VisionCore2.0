"""
compliance_engine.py — Compliance Scoring, Monitoring & Reporting Engine
Sprint 4 — Entity 5
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case, Integer

from app.db.models.all_models import (
    PolicyDocument, PolicyDistribution, PolicyAcknowledgement, PolicySignature,
    ComplianceRule, ComplianceRecord, ComplianceAudit, User
)
from app.crud.crud_policy import (
    crud_policy_document, crud_compliance_rule, crud_compliance_record
)


class ComplianceEngine:
    """Compliance monitoring, scoring, and breach detection."""

    @staticmethod
    def get_org_compliance_summary(db: Session, org_id: UUID) -> Dict[str, Any]:
        """Get organization-wide compliance summary."""
        now = datetime.now(timezone.utc)

        total_rules = db.query(ComplianceRule).filter(
            ComplianceRule.organization_id == org_id,
            ComplianceRule.is_active.is_(True)
        ).count()

        total_employees = db.query(User).filter(
            User.org_id == org_id,
            User.is_deleted == 0
        ).count()

        records = db.query(ComplianceRecord).filter(
            ComplianceRecord.organization_id == org_id
        ).all()

        total_records = len(records)
        compliant = sum(1 for r in records if r.is_compliant)
        non_compliant = sum(1 for r in records if not r.is_compliant)
        pending = sum(1 for r in records if r.status == "pending")

        # Department breakdown
        dept_breakdown = db.query(
            User.dept_id,
            func.count(ComplianceRecord.id).label("total"),
            func.sum(case((ComplianceRecord.is_compliant == True, 1), else_=0)).label("compliant")
        ).join(
            ComplianceRecord, ComplianceRecord.user_id == User.id
        ).filter(
            ComplianceRecord.organization_id == org_id
        ).group_by(User.dept_id).all()

        departments = []
        for dept_id, total, compliant_count in dept_breakdown:
            rate = round((compliant_count / max(1, total)) * 100, 1) if total else 0.0
            departments.append({
                "dept_id": dept_id,
                "total_records": total or 0,
                "compliant_records": compliant_count or 0,
                "compliance_rate": rate
            })

        overall_rate = round((compliant / max(1, total_records)) * 100, 1) if total_records > 0 else 100.0

        return {
            "organization_id": str(org_id),
            "total_rules": total_rules,
            "total_employees": total_employees,
            "total_records": total_records,
            "compliant_records": compliant,
            "non_compliant_records": non_compliant,
            "pending_records": pending,
            "overall_compliance_rate": overall_rate,
            "department_breakdown": departments
        }

    @staticmethod
    def get_user_compliance_history(db: Session, org_id: UUID, user_id: int) -> List[Dict[str, Any]]:
        """Get compliance history for a specific user."""
        records = db.query(ComplianceRecord).filter(
            ComplianceRecord.organization_id == org_id,
            ComplianceRecord.user_id == user_id
        ).order_by(ComplianceRecord.updated_at.desc()).all()

        result = []
        for r in records:
            doc = crud_policy_document.get_by_id(db, r.document_id) if r.document_id else None
            result.append({
                "id": r.id,
                "document_id": r.document_id,
                "document_title": doc.title if doc else "Unknown",
                "is_compliant": r.is_compliant,
                "status": r.status,
                "compliant_at": r.compliant_at,
                "due_date": r.due_date,
                "notes": r.notes,
                "updated_at": r.updated_at
            })
        return result

    @staticmethod
    def detect_compliance_breaches(db: Session, org_id: UUID) -> List[Dict[str, Any]]:
        """Detect users who are non-compliant and past their due dates."""
        now = datetime.now(timezone.utc)

        breaches = db.query(ComplianceRecord).filter(
            ComplianceRecord.organization_id == org_id,
            ComplianceRecord.is_compliant == False,
            ComplianceRecord.due_date.isnot(None),
            ComplianceRecord.due_date < now
        ).all()

        result = []
        for br in breaches:
            user = db.query(User).filter(User.id == br.user_id).first()
            doc = crud_policy_document.get_by_id(db, br.document_id) if br.document_id else None
            result.append({
                "record_id": br.id,
                "user_id": br.user_id,
                "user_name": user.full_name if user else "Unknown",
                "document_id": br.document_id,
                "document_title": doc.title if doc else "Unknown",
                "due_date": br.due_date,
                "days_overdue": (now - br.due_date).days if br.due_date else 0
            })

        return result

    @staticmethod
    def get_compliance_trend(db: Session, org_id: UUID, days: int = 90) -> List[Dict[str, Any]]:
        """Get compliance rate trend over time."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days)

        audits = db.query(ComplianceAudit).filter(
            ComplianceAudit.organization_id == org_id,
            ComplianceAudit.audit_type == "compliance_check",
            ComplianceAudit.created_at >= cutoff
        ).order_by(ComplianceAudit.created_at.asc()).all()

        trend = []
        for audit in audits:
            score = audit.meta_data.get("score", 0) if audit.meta_data else 0
            trend.append({
                "date": audit.created_at.isoformat(),
                "score": score,
                "summary": audit.description
            })

        return trend


compliance_engine = ComplianceEngine()

