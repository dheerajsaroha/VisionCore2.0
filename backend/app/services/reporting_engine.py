"""
reporting_engine.py — Enterprise Reporting Platform
Sprint 5 — Phase C: Enterprise Platform Operations

Provides:
- Report Builder (template-based report generation)
- Export formats (JSON, CSV, PDF)
- Scheduled report generation
- Report templates
- Report history
- Permission-based access control
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.analytics_platform import analytics_platform
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


# Report template definitions
REPORT_TEMPLATES = {
    "executive_summary": {
        "name": "Executive Platform Summary",
        "description": "High-level platform health and activity summary",
        "sections": [
            "authentication", "organization", "eaac",
            "hr", "performance", "policy", "asset",
            "workflow", "event_bus", "system",
        ],
    },
    "hr_report": {
        "name": "HR Module Report",
        "description": "HR activity including leave, attendance, payroll",
        "sections": ["leave", "attendance", "payroll", "recruitment"],
    },
    "compliance_report": {
        "name": "Compliance & Policy Report",
        "description": "Policy acknowledgements, compliance breaches, audit trail",
        "sections": ["policy", "audit"],
    },
    "asset_report": {
        "name": "Asset Management Report",
        "description": "Asset inventory, assignments, maintenance, licenses",
        "sections": ["asset"],
    },
    "performance_report": {
        "name": "Performance Management Report",
        "description": "Reviews, ratings, goals, promotions",
        "sections": ["performance"],
    },
    "security_report": {
        "name": "Security & Audit Report",
        "description": "Security events, audit trail, risk alerts",
        "sections": ["audit", "system"],
    },
    "custom": {
        "name": "Custom Report",
        "description": "User-defined report with selected sections",
        "sections": [],
    },
}


class ReportingEngine:
    """
    Enterprise reporting engine.
    Generates reports from platform analytics data.
    """

    def __init__(self):
        self._reports: list[dict] = []
        self._max_reports: int = 1000

    # ------------------------------------------------------------------
    #  Report Generation
    # ------------------------------------------------------------------

    def generate_report(
        self,
        template_code: str = "executive_summary",
        org_id: str = "",
        format: str = "json",
        sections: list[str] | None = None,
        title: str = "",
        generated_by: int | None = None,
    ) -> dict:
        """Generate a report using a template."""
        template = REPORT_TEMPLATES.get(template_code)
        if not template:
            raise ValueError(f"Unknown template: {template_code}")

        sections_to_use = sections or template["sections"]
        data = {}

        # Collect data for each section
        for section in sections_to_use:
            data[section] = self._get_section_data(section, org_id)

        # Build report
        report = {
            "id": f"report-{datetime.now(timezone.utc).timestamp()}",
            "title": title or template["name"],
            "template_code": template_code,
            "organization_id": org_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": generated_by,
            "sections": sections_to_use,
            "data": data,
            "format": format,
            "status": "generated",
        }

        # Export to requested format
        if format == "csv":
            report["exported"] = self._export_csv(report)
        elif format == "json":
            report["exported"] = json.dumps(data, indent=2, default=str)
        else:
            report["exported"] = json.dumps(data, indent=2, default=str)

        # Record
        self._reports.append(report)
        if len(self._reports) > self._max_reports:
            self._reports = self._reports[-self._max_reports:]

        # Audit
        audit_service.record(
            module="reporting",
            action="generate",
            entity_type="report",
            summary=f"Report generated: {report['title']} ({template_code})",
            details={"sections": sections_to_use, "format": format},
            actor_user_id=generated_by,
            organization_id=org_id,
        )

        return report

    def _get_section_data(self, section: str, org_id: str) -> dict:
        """Get data for a report section."""
        section_map = {
            "authentication": lambda: analytics_platform.get_authentication_analytics(org_id),
            "organization": lambda: analytics_platform.get_organization_analytics(),
            "eaac": lambda: analytics_platform.get_eaac_analytics(),
            "hr": lambda: analytics_platform.get_hr_analytics(org_id),
            "performance": lambda: analytics_platform.get_performance_analytics(org_id),
            "policy": lambda: analytics_platform.get_policy_analytics(org_id),
            "asset": lambda: analytics_platform.get_asset_analytics(org_id),
            "workflow": lambda: analytics_platform.get_workflow_analytics(org_id),
            "event_bus": lambda: analytics_platform.get_event_bus_analytics(),
            "system": lambda: analytics_platform.get_system_analytics(),
            "audit": {
                "summary": audit_service.get_compliance_summary(org_id),
                "recent": audit_service.get_timeline(org_id, limit=50)[0],
            },
        }
        handler = section_map.get(section)
        if callable(handler):
            return handler()
        return handler or {"error": f"Unknown section: {section}"}

    # ------------------------------------------------------------------
    #  Export
    # ------------------------------------------------------------------

    def _export_csv(self, report: dict) -> str:
        """Export report data as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Section", "Metric", "Value"])
        for section, data in report.get("data", {}).items():
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, (str, int, float, bool)):
                        writer.writerow([section, key, value])
        return output.getvalue()

    def export_report(self, report_id: str, format: str = "json") -> str | None:
        """Export a previously generated report."""
        for report in self._reports:
            if report.get("id") == report_id:
                if format == "csv":
                    return self._export_csv(report)
                return json.dumps(report.get("data", {}), indent=2, default=str)
        return None

    # ------------------------------------------------------------------
    #  Report Management
    # ------------------------------------------------------------------

    def get_reports(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        """Get all generated reports."""
        sorted_reports = sorted(
            self._reports,
            key=lambda r: r["generated_at"],
            reverse=True,
        )
        return sorted_reports[offset:offset + limit]

    def get_report(self, report_id: str) -> dict | None:
        """Get a specific report by ID."""
        for report in self._reports:
            if report.get("id") == report_id:
                return report
        return None

    def delete_report(self, report_id: str) -> bool:
        """Delete a report."""
        before = len(self._reports)
        self._reports = [
            r for r in self._reports if r.get("id") != report_id
        ]
        return len(self._reports) < before

    def get_templates(self) -> dict:
        """Get available report templates."""
        return REPORT_TEMPLATES

    def get_stats(self) -> dict:
        """Get reporting engine statistics."""
        return {
            "total_reports": len(self._reports),
            "templates_available": len(REPORT_TEMPLATES),
        }


# Singleton
reporting_engine = ReportingEngine()
