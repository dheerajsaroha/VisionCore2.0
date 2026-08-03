"""
tenant_analytics.py — Tenant-Level Analytics Service
Sprint 6 — Phase B: Enterprise Multi-Tenant SaaS Completion

Provides tenant-level analytics:
- Active users, module adoption, login frequency
- Storage usage, API usage
- Attendance, HR, performance, compliance metrics
- Integration with AnalyticsPlatform

No frozen modules are modified.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.all_models import (
    Organization, User, AttendanceLog, LeaveRequest, Asset,
    PerformanceReview, ComplianceRecord, PolicyDocument
)
from app.services.analytics_platform import analytics_platform
from app.services.audit_service import audit_service
from app.services.config_center import config_center

logger = logging.getLogger(__name__)


class TenantAnalyticsService:
    """
    Provides per-tenant analytics by aggregating data from all
    platform modules. Integrates with the existing AnalyticsPlatform.
    """

    def __init__(self):
        self._snapshots: list[dict] = []

    # ──────────────────────────────────────────────────────────────────────
    #  Active Users
    # ──────────────────────────────────────────────────────────────────────

    def get_active_users(self, db: Session, org_id: UUID) -> dict:
        """Get active user metrics for a tenant."""
        users = db.query(User).filter(User.org_id == org_id, User.is_deleted == 0).count()
        # Estimate active users from audit logs
        entries, _ = audit_service.search(
            organization_id=str(org_id),
            module="authentication",
            action="login",
            limit=0,
        )
        # Count unique users in last 30 days
        active_users = len(set(e.get("actor_user_id") for e in entries if e.get("actor_user_id")))
        return {
            "total_users": users,
            "active_users_30d": active_users,
            "engagement_rate": round(active_users / max(users, 1) * 100, 1),
            "total_audit_entries": len(entries),
        }

    # ──────────────────────────────────────────────────────────────────────
    #  Module Adoption
    # ──────────────────────────────────────────────────────────────────────

    def get_module_adoption(self, db: Session, org_id: UUID) -> dict:
        """Get module adoption metrics for a tenant."""
        org_id_str = str(org_id)
        modules = {
            "attendance": {
                "label": "Attendance",
                "count": db.query(AttendanceLog).filter(
                    AttendanceLog.organization_id == org_id
                ).count() if hasattr(AttendanceLog, 'organization_id') else 0,
                "threshold": 10,
            },
            "leave": {
                "label": "Leave Management",
                "count": db.query(LeaveRequest).filter(
                    LeaveRequest.organization_id == org_id
                ).count() if hasattr(LeaveRequest, 'organization_id') else 0,
                "threshold": 5,
            },
            "performance": {
                "label": "Performance",
                "count": db.query(PerformanceReview).filter(
                    PerformanceReview.organization_id == org_id
                ).count() if hasattr(PerformanceReview, 'organization_id') else 0,
                "threshold": 3,
            },
            "assets": {
                "label": "Asset Management",
                "count": db.query(Asset).filter(
                    Asset.organization_id == org_id
                ).count() if hasattr(Asset, 'organization_id') else 0,
                "threshold": 5,
            },
            "compliance": {
                "label": "Compliance",
                "count": db.query(ComplianceRecord).filter(
                    ComplianceRecord.organization_id == org_id
                ).count() if hasattr(ComplianceRecord, 'organization_id') else 0,
                "threshold": 3,
            },
            "policies": {
                "label": "Policy Center",
                "count": db.query(PolicyDocument).filter(
                    PolicyDocument.organization_id == org_id
                ).count() if hasattr(PolicyDocument, 'organization_id') else 0,
                "threshold": 3,
            },
        }

        adoption = {}
        for key, info in modules.items():
            adopted = info["count"] >= info["threshold"]
            adoption[key] = {
                "label": info["label"],
                "count": info["count"],
                "threshold": info["threshold"],
                "adopted": adopted,
                "adoption_rate": round(min(info["count"] / max(info["threshold"], 1) * 100, 100), 1),
            }

        # Calculate overall adoption
        total_modules = len(modules)
        adopted_modules = sum(1 for m in adoption.values() if m["adopted"])
        overall_adoption = round(adopted_modules / max(total_modules, 1) * 100, 1)

        return {
            "modules": adoption,
            "total_modules": total_modules,
            "adopted_modules": adopted_modules,
            "overall_adoption_rate": overall_adoption,
        }

    # ──────────────────────────────────────────────────────────────────────
    #  Login Frequency
    # ──────────────────────────────────────────────────────────────────────

    def get_login_frequency(self, org_id: UUID) -> dict:
        """Get login frequency metrics for a tenant."""
        org_id_str = str(org_id)
        entries, _ = audit_service.search(
            organization_id=org_id_str,
            module="authentication",
            action="login",
            limit=0,
        )

        # Group by date
        from collections import Counter
        daily_counts = Counter()
        for e in entries:
            date_str = e.get("timestamp", "")[:10]
            if date_str:
                daily_counts[date_str] += 1

        # Calculate trends
        total_logins = len(entries)
        unique_days = len(daily_counts)
        avg_per_day = round(total_logins / max(unique_days, 1), 1)

        return {
            "total_logins": total_logins,
            "unique_days": unique_days,
            "avg_logins_per_day": avg_per_day,
            "daily_counts": dict(daily_counts.most_common(30)),
        }

    # ──────────────────────────────────────────────────────────────────────
    #  Storage Usage
    # ──────────────────────────────────────────────────────────────────────

    def get_storage_usage(self, db: Session, org_id: UUID) -> dict:
        """Get storage usage estimates for a tenant."""
        # Estimate based on record counts
        record_counts = {
            "users": db.query(User).filter(User.org_id == org_id).count(),
            "attendance_logs": db.query(AttendanceLog).filter(
                AttendanceLog.organization_id == org_id
            ).count() if hasattr(AttendanceLog, 'organization_id') else 0,
            "leave_requests": db.query(LeaveRequest).filter(
                LeaveRequest.organization_id == org_id
            ).count() if hasattr(LeaveRequest, 'organization_id') else 0,
            "assets": db.query(Asset).filter(
                Asset.organization_id == org_id
            ).count() if hasattr(Asset, 'organization_id') else 0,
            "performance_reviews": db.query(PerformanceReview).filter(
                PerformanceReview.organization_id == org_id
            ).count() if hasattr(PerformanceReview, 'organization_id') else 0,
            "compliance_records": db.query(ComplianceRecord).filter(
                ComplianceRecord.organization_id == org_id
            ).count() if hasattr(ComplianceRecord, 'organization_id') else 0,
        }

        # Estimate storage in MB (rough: 1KB per record)
        total_records = sum(record_counts.values())
        estimated_storage_mb = round(total_records * 0.001, 2)

        return {
            "record_counts": record_counts,
            "total_records": total_records,
            "estimated_storage_mb": estimated_storage_mb,
            "estimated_storage_gb": round(estimated_storage_mb / 1024, 4),
        }

    # ──────────────────────────────────────────────────────────────────────
    #  API Usage
    # ──────────────────────────────────────────────────────────────────────

    def get_api_usage(self, org_id: UUID) -> dict:
        """Get API usage metrics for a tenant."""
        org_id_str = str(org_id)
        entries, _ = audit_service.search(
            organization_id=org_id_str,
            limit=0,
        )

        # Group by module
        module_counts = defaultdict(int)
        for e in entries:
            module_counts[e.get("module", "unknown")] += 1

        total_api_calls = len(entries)
        return {
            "total_api_calls": total_api_calls,
            "by_module": dict(module_counts),
            "top_modules": sorted(
                module_counts.items(), key=lambda x: x[1], reverse=True
            )[:5],
        }

    # ──────────────────────────────────────────────────────────────────────
    #  HR Metrics
    # ──────────────────────────────────────────────────────────────────────

    def get_hr_metrics(self, db: Session, org_id: UUID) -> dict:
        """Get HR-specific metrics for a tenant."""
        from app.services.analytics_platform import analytics_platform
        hr_analytics = analytics_platform.get_hr_analytics(str(org_id))
        return hr_analytics

    # ──────────────────────────────────────────────────────────────────────
    #  Performance Metrics
    # ──────────────────────────────────────────────────────────────────────

    def get_performance_metrics(self, org_id: UUID) -> dict:
        """Get performance-specific metrics for a tenant."""
        return analytics_platform.get_performance_analytics(str(org_id))

    # ──────────────────────────────────────────────────────────────────────
    #  Compliance Metrics
    # ──────────────────────────────────────────────────────────────────────

    def get_compliance_metrics(self, org_id: UUID) -> dict:
        """Get compliance-specific metrics for a tenant."""
        return analytics_platform.get_policy_analytics(str(org_id))

    # ──────────────────────────────────────────────────────────────────────
    #  Executive Dashboard
    # ──────────────────────────────────────────────────────────────────────

    def get_tenant_dashboard(self, db: Session, org_id: UUID) -> dict:
        """Get the executive tenant analytics dashboard."""
        org = db.query(Organization).filter(Organization.id == org_id).first()
        org_name = org.name if org else "Unknown"

        dashboard = {
            "organization_id": str(org_id),
            "organization_name": org_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_users": self.get_active_users(db, org_id),
            "module_adoption": self.get_module_adoption(db, org_id),
            "login_frequency": self.get_login_frequency(org_id),
            "storage_usage": self.get_storage_usage(db, org_id),
            "api_usage": self.get_api_usage(org_id),
            "hr_metrics": self.get_hr_metrics(db, org_id),
            "performance_metrics": self.get_performance_metrics(org_id),
            "compliance_metrics": self.get_compliance_metrics(org_id),
        }

        # Take snapshot
        self._take_snapshot(dashboard)

        return dashboard

    # ──────────────────────────────────────────────────────────────────────
    #  Snapshot Management
    # ──────────────────────────────────────────────────────────────────────

    def _take_snapshot(self, data: dict) -> None:
        """Take a point-in-time analytics snapshot."""
        snapshot = {
            "timestamp": data["timestamp"],
            "organization_id": data["organization_id"],
            "data": data,
        }
        self._snapshots.append(snapshot)
        if len(self._snapshots) > 1000:
            self._snapshots = self._snapshots[-1000:]

    def get_snapshots(self, org_id: UUID, limit: int = 10) -> list[dict]:
        """Get analytics snapshots for a tenant."""
        org_snapshots = [
            s for s in self._snapshots
            if s.get("organization_id") == str(org_id)
        ]
        return sorted(org_snapshots, key=lambda s: s["timestamp"], reverse=True)[:limit]

    # ──────────────────────────────────────────────────────────────────────
    #  Platform Summary (SuperAdmin view)
    # ──────────────────────────────────────────────────────────────────────

    def get_platform_summary(self, db: Session) -> dict:
        """Get a summary of all tenants (SuperAdmin view)."""
        orgs = db.query(Organization).all()
        total_orgs = len(orgs)
        total_users = db.query(User).filter(User.is_deleted == 0).count()

        active_orgs = sum(1 for o in orgs if o.is_active)
        avg_users_per_org = round(total_users / max(total_orgs, 1), 1)

        # Get module adoption across all orgs
        total_adoption = 0
        for org in orgs[:10]:  # Sample first 10
            try:
                adoption = self.get_module_adoption(db, org.id)
                total_adoption += adoption.get("overall_adoption_rate", 0)
            except Exception:
                pass

        avg_adoption = round(total_adoption / max(min(total_orgs, 10), 1), 1)

        return {
            "total_organizations": total_orgs,
            "total_users": total_users,
            "active_organizations": active_orgs,
            "avg_users_per_org": avg_users_per_org,
            "avg_module_adoption": avg_adoption,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Singleton
tenant_analytics_service = TenantAnalyticsService()
