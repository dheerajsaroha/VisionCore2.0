"""
reporting_framework.py — Enterprise Reporting Engine & Scheduled Reports
Sprint 9 — Enterprise Intelligence & Analytics Layer

Provides export generation (CSV/JSON), custom ad-hoc reporting, and
scheduled automated report execution.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.db.models.all_models import (
    ScheduledReport,
    User,
    AttendanceLog,
    Payroll,
    Asset,
    AuditLog,
)

logger = logging.getLogger(__name__)


class ReportingFrameworkService:
    """Generates structured report datasets and formatted file outputs."""

    def generate_report_data(
        self, db: Session, org_id: UUID, report_type: str, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Generates raw dictionary rows for requested report type."""
        report_type = report_type.lower()
        filters = filters or {}

        if report_type == "workforce_census":
            users = db.scalars(
                select(User).where(User.org_id == org_id)
            ).all()
            return [
                {
                    "user_id": u.id,
                    "email": u.email,
                    "full_name": u.full_name,
                    "role_id": u.role_id,
                    "is_active": u.is_active,
                    "created_at": u.created_at.isoformat() if u.created_at else "",
                }
                for u in users
            ]

        elif report_type == "attendance_summary":
            org_user_ids = [u.id for u in db.scalars(select(User).where(User.org_id == org_id)).all()]
            logs = db.scalars(
                select(AttendanceLog).where(AttendanceLog.user_id.in_(org_user_ids))
            ).all()
            return [
                {
                    "id": l.id,
                    "user_id": l.user_id,
                    "check_in": l.check_in.isoformat() if l.check_in else "",
                    "verification_type": getattr(l, "verification_type", "biometric"),
                    "status": getattr(l, "status", "present"),
                }
                for l in logs
            ]

        elif report_type == "payroll_breakdown":
            payrolls = db.scalars(
                select(Payroll).where(Payroll.org_id == org_id)
            ).all()
            return [
                {
                    "id": p.id,
                    "user_id": p.user_id,
                    "month": p.month,
                    "year": p.year,
                    "net_pay": float(getattr(p, "net_pay", 0.0) or 0.0),
                    "status": p.status,
                }
                for p in payrolls
            ]

        elif report_type == "asset_inventory":
            assets = db.scalars(
                select(Asset).where(Asset.organization_id == org_id)
            ).all()
            return [
                {
                    "id": a.id,
                    "asset_name": a.asset_name,
                    "category": a.category,
                    "status": a.status,
                    "assigned_to_user_id": a.assigned_to_user_id,
                }
                for a in assets
            ]

        elif report_type == "audit_events":
            logs = db.scalars(
                select(AuditLog).where(AuditLog.tenant_org_id == org_id).limit(200)
            ).all()
            return [
                {
                    "id": log.id,
                    "action": log.action,
                    "module": log.module,
                    "actor_user_id": log.actor_user_id,
                    "occurred_at": log.occurred_at.isoformat() if log.occurred_at else "",
                }
                for log in logs
            ]

        else:
            return []

    def export_to_csv(self, rows: List[Dict[str, Any]]) -> str:
        """Converts dictionary rows to CSV string format."""
        if not rows:
            return ""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    def export_to_json(self, rows: List[Dict[str, Any]]) -> str:
        """Converts dictionary rows to formatted JSON string."""
        return json.dumps(rows, indent=2)


reporting_framework_service = ReportingFrameworkService()


class ScheduledReportService:
    """Manages scheduled report configurations and execution triggers."""

    def create_scheduled_report(
        self,
        db: Session,
        org_id: UUID,
        created_by_user_id: int,
        report_name: str,
        report_type: str,
        frequency: str = "MONTHLY",
        file_format: str = "CSV",
        filters: Optional[Dict[str, Any]] = None,
        recipient_emails: Optional[List[str]] = None,
    ) -> ScheduledReport:
        """Creates a new scheduled report definition."""
        report = ScheduledReport(
            organization_id=org_id,
            created_by_user_id=created_by_user_id,
            report_name=report_name,
            report_type=report_type,
            frequency=frequency.upper(),
            file_format=file_format.upper(),
            filters=filters or {},
            recipient_emails=recipient_emails or [],
            is_active=True,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    def list_scheduled_reports(self, db: Session, org_id: UUID) -> List[ScheduledReport]:
        """Lists active scheduled reports for an organization."""
        return list(
            db.scalars(
                select(ScheduledReport).where(
                    and_(
                        ScheduledReport.organization_id == org_id,
                        ScheduledReport.is_active.is_(True),
                    )
                )
            ).all()
        )

    def execute_report(self, db: Session, report_id: int) -> Dict[str, Any]:
        """Executes a scheduled report by ID and updates execution timestamps."""
        report = db.execute(
            select(ScheduledReport).where(ScheduledReport.id == report_id)
        ).scalar_one_or_none()
        if not report:
            return {"error": "Report not found"}

        rows = reporting_framework_service.generate_report_data(
            db=db,
            org_id=report.organization_id,
            report_type=report.report_type,
            filters=report.filters,
        )

        if report.file_format == "JSON":
            content = reporting_framework_service.export_to_json(rows)
        else:
            content = reporting_framework_service.export_to_csv(rows)

        report.last_run_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "report_id": report.id,
            "report_name": report.report_name,
            "row_count": len(rows),
            "file_format": report.file_format,
            "content_preview": content[:200],
            "executed_at": report.last_run_at.isoformat(),
        }


scheduled_report_service = ScheduledReportService()
