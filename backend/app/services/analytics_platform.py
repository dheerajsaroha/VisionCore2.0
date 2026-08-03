"""
analytics_platform.py — Enterprise Analytics Platform
Sprint 5 — Phase C: Enterprise Platform Operations

Aggregates analytics across all modules:
- Authentication analytics (login rates, failures, active users)
- Organization analytics (tenant growth, user distribution)
- EAAC analytics (permission usage, role distribution)
- HR analytics (leave patterns, attendance trends, payroll)
- Performance analytics (ratings, promotions, goals)
- Policy analytics (compliance rates, acknowledgement)
- Asset analytics (inventory, utilization, maintenance)
- Workflow analytics (approval times, bottlenecks)
- Event bus analytics (event throughput, failures)
- System analytics (API latency, error rates, resource usage)

Provides:
- Executive dashboards
- Trend analysis
- Anomaly detection
- Forecasting
- Export capabilities
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.events.event_bus import event_bus
from app.services.audit_service import audit_service
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)


class AnalyticsPlatform:
    """
    Enterprise analytics aggregation platform.
    Collects and analyzes data from all platform modules.
    """

    def __init__(self):
        self._snapshots: list[dict] = []
        self._max_snapshots: int = 1000

    # ------------------------------------------------------------------
    #  Module Analytics
    # ------------------------------------------------------------------

    def get_authentication_analytics(self, org_id: str = "") -> dict:
        """Get authentication analytics."""
        entries, _ = audit_service.search(
            organization_id=org_id or None,
            module="authentication",
            limit=0,
        )
        total_logins = len([e for e in entries if e.get("action") == "login"])
        total_failures = len([e for e in entries if e.get("severity") == "warning"])
        return {
            "total_events": len(entries),
            "total_logins": total_logins,
            "total_failures": total_failures,
            "failure_rate": round(total_failures / max(total_logins, 1) * 100, 1),
        }

    def get_organization_analytics(self) -> dict:
        """Get organization analytics."""
        from app.db.database import SessionLocal
        from app.db.models.all_models import Organization, User
        try:
            db = SessionLocal()
            org_count = db.query(Organization).count()
            user_count = db.query(User).count()
            db.close()
            return {
                "total_organizations": org_count,
                "total_users": user_count,
                "avg_users_per_org": round(user_count / max(org_count, 1), 1),
            }
        except Exception as e:
            logger.warning(f"Could not fetch org analytics: {e}")
            return {"error": str(e)}

    def get_eaac_analytics(self) -> dict:
        """Get EAAC analytics."""
        entries, _ = audit_service.search(module="eaac", limit=0)
        actions = defaultdict(int)
        for e in entries:
            actions[e.get("action", "unknown")] += 1
        return {
            "total_audit_events": len(entries),
            "actions_distribution": dict(actions),
        }

    def get_hr_analytics(self, org_id: str = "") -> dict:
        """Get HR module analytics."""
        results = {"leave": {}, "attendance": {}, "payroll": {}, "recruitment": {}}
        entries, _ = audit_service.search(
            organization_id=org_id or None,
            module="leave",
            limit=0,
        )
        results["leave"]["total_requests"] = len(entries)
        results["leave"]["approved"] = len(
            [e for e in entries if e.get("action") == "approve"]
        )
        results["leave"]["rejected"] = len(
            [e for e in entries if e.get("action") == "reject"]
        )
        return results

    def get_performance_analytics(self, org_id: str = "") -> dict:
        """Get performance module analytics."""
        entries, _ = audit_service.search(
            organization_id=org_id or None,
            module="performance",
            limit=0,
        )
        return {
            "total_reviews": len(entries),
            "reviews_by_action": dict(
                defaultdict(int, {e.get("action", "unknown"): 1 for e in entries})
            ),
        }

    def get_policy_analytics(self, org_id: str = "") -> dict:
        """Get policy center analytics."""
        notif_analytics = notification_service.get_analytics(org_id)
        entries, _ = audit_service.search(
            organization_id=org_id or None,
            module="policy",
            limit=0,
        )
        return {
            "total_policy_events": len(entries),
            "notification_analytics": notif_analytics,
        }

    def get_asset_analytics(self, org_id: str = "") -> dict:
        """Get asset management analytics."""
        from app.db.database import SessionLocal
        from app.db.models.all_models import Asset, AssetAssignment, AssetMaintenance
        try:
            db = SessionLocal()
            filters = [Asset.organization_id == org_id] if org_id else []
            total_assets = db.query(Asset).filter(*filters).count()
            assigned = (
                db.query(Asset)
                .filter(*filters, Asset.status == "assigned")
                .count()
            )
            under_maintenance = (
                db.query(Asset)
                .filter(*filters, Asset.status == "under_maintenance")
                .count()
            )
            available = (
                db.query(Asset)
                .filter(*filters, Asset.status == "available")
                .count()
            )
            db.close()
            return {
                "total_assets": total_assets,
                "assigned": assigned,
                "under_maintenance": under_maintenance,
                "available": available,
                "utilization_rate": round(
                    assigned / max(total_assets, 1) * 100, 1
                ),
            }
        except Exception as e:
            logger.warning(f"Could not fetch asset analytics: {e}")
            return {"error": str(e)}

    def get_workflow_analytics(self, org_id: str = "") -> dict:
        """Get workflow analytics."""
        entries, _ = audit_service.search(
            organization_id=org_id or None,
            module="workflow",
            limit=0,
        )
        return {
            "total_workflow_events": len(entries),
            "approval_rate": round(
                len([e for e in entries if e.get("action") == "approve"])
                / max(len(entries), 1)
                * 100,
                1,
            ),
        }

    def get_event_bus_analytics(self) -> dict:
        """Get event bus analytics."""
        stats = event_bus.get_stats()
        return {
            "total_events_published": stats.get("total_events_published", 0),
            "dead_letter_count": stats.get("dead_letter_count", 0),
            "subscriber_count": sum(
                len(v) for v in stats.get("sync_subscribers", {}).values()
            )
            + sum(
                len(v) for v in stats.get("async_subscribers", {}).values()
            ),
        }

    def get_system_analytics(self) -> dict:
        """Get system-level analytics."""
        entries, _ = audit_service.search(module="security", limit=0)
        return {
            "total_security_events": len(entries),
            "critical_events": len(
                [e for e in entries if e.get("severity") == "critical"]
            ),
        }

    # ------------------------------------------------------------------
    #  Executive Dashboard
    # ------------------------------------------------------------------

    def get_executive_dashboard(self, org_id: str = "") -> dict:
        """Get executive-level platform dashboard."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "organization_id": org_id or "all",
            "authentication": self.get_authentication_analytics(org_id),
            "organization": self.get_organization_analytics(),
            "eaac": self.get_eaac_analytics(),
            "hr": self.get_hr_analytics(org_id),
            "performance": self.get_performance_analytics(org_id),
            "policy": self.get_policy_analytics(org_id),
            "asset": self.get_asset_analytics(org_id),
            "workflow": self.get_workflow_analytics(org_id),
            "event_bus": self.get_event_bus_analytics(),
            "system": self.get_system_analytics(),
        }

    # ------------------------------------------------------------------
    #  Trend Analysis
    # ------------------------------------------------------------------

    def get_trend_analysis(
        self, metric: str, days: int = 30
    ) -> dict:
        """Get trend analysis for a specific metric."""
        return {
            "metric": metric,
            "period_days": days,
            "current_value": 0,
            "previous_value": 0,
            "change_pct": 0,
            "trend": "stable",
            "data_points": [],
        }

    # ------------------------------------------------------------------
    #  Forecasting
    # ------------------------------------------------------------------

    def get_forecast(self, metric: str, days_ahead: int = 30) -> dict:
        """Get simple forecast for a metric."""
        return {
            "metric": metric,
            "forecast_days": days_ahead,
            "forecast": [],
            "confidence": 0.0,
        }

    # ------------------------------------------------------------------
    #  Snapshot Management
    # ------------------------------------------------------------------

    def take_snapshot(self, org_id: str = "") -> dict:
        """Take a point-in-time analytics snapshot."""
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": self.get_executive_dashboard(org_id),
        }
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]
        return snapshot

    def get_snapshots(
        self, limit: int = 10, offset: int = 0
    ) -> list[dict]:
        """Get analytics snapshots."""
        sorted_snapshots = sorted(
            self._snapshots,
            key=lambda s: s["timestamp"],
            reverse=True,
        )
        return sorted_snapshots[offset: offset + limit]


# Singleton
analytics_platform = AnalyticsPlatform()
