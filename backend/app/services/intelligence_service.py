"""
intelligence_service.py — Enterprise Intelligence Layer
Sprint 5 — Phase C: Enterprise Platform Operations

Provides:
- Anomaly detection (unusual login patterns, permission escalations)
- Bottleneck detection (workflow delays, approval backlogs)
- Pattern recognition (attendance patterns, leave trends)
- Risk scoring (user risk, org risk, compliance risk)
- Predictive analytics
- Trend forecasting
- Smart recommendations
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from app.events.event_bus import event_bus
from app.services.audit_service import audit_service
from app.services.notification_service import (
    NotificationChannel,
    NotificationPriority,
    notification_service,
)

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IntelligenceService:
    """
    Enterprise intelligence service.
    Analyzes patterns, detects anomalies, and provides insights.
    """

    def __init__(self):
        self._anomalies: list[dict] = []
        self._insights: list[dict] = []
        self._max_history: int = 10000

    # ------------------------------------------------------------------
    #  Anomaly Detection
    # ------------------------------------------------------------------

    def detect_anomalies(self, org_id: str = "") -> list[dict]:
        """Run all anomaly detectors."""
        anomalies = []
        anomalies.extend(self._detect_login_anomalies(org_id))
        anomalies.extend(self._detect_permission_anomalies(org_id))
        anomalies.extend(self._detect_workflow_anomalies(org_id))
        self._anomalies.extend(anomalies)
        if len(self._anomalies) > self._max_history:
            self._anomalies = self._anomalies[-self._max_history:]

        # Alert on high/critical anomalies
        for anomaly in anomalies:
            if anomaly.get("risk_level") in ("high", "critical"):
                notification_service.send(
                    user_id=0,
                    organization_id=org_id,
                    channel=NotificationChannel.IN_APP,
                    priority=NotificationPriority.HIGH,
                    title=f"Anomaly Detected: {anomaly['type']}",
                    message=anomaly.get("description", ""),
                    source_module="intelligence",
                    source_event="anomaly.detected",
                )

        return anomalies

    def _detect_login_anomalies(self, org_id: str) -> list[dict]:
        """Detect unusual login patterns."""
        anomalies = []
        entries, total = audit_service.search(
            organization_id=org_id or None,
            module="authentication",
            action="login",
            limit=100,
        )

        # Check for high failure rate
        failures = [e for e in entries if e.get("severity") == "warning"]
        if len(failures) > 10 and len(entries) > 0:
            rate = len(failures) / len(entries)
            if rate > 0.5:
                anomalies.append({
                    "type": "high_login_failure_rate",
                    "risk_level": "high",
                    "description": f"Login failure rate at {rate:.0%} ({len(failures)} failures in {len(entries)} attempts)",
                    "details": {"failure_count": len(failures), "total_attempts": len(entries)},
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "module": "authentication",
                })

        return anomalies

    def _detect_permission_anomalies(self, org_id: str) -> list[dict]:
        """Detect unusual permission activity."""
        anomalies = []
        entries, total = audit_service.search(
            organization_id=org_id or None,
            module="eaac",
            severity="warning",
            limit=50,
        )

        if len(entries) > 20:
            anomalies.append({
                "type": "high_permission_changes",
                "risk_level": "medium",
                "description": f"High volume of permission changes detected ({len(entries)} changes)",
                "details": {"change_count": len(entries)},
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "module": "eaac",
            })

        return anomalies

    def _detect_workflow_anomalies(self, org_id: str) -> list[dict]:
        """Detect workflow bottlenecks."""
        anomalies = []
        entries, total = audit_service.search(
            organization_id=org_id or None,
            module="workflow",
            action="reject",
            limit=50,
        )

        if len(entries) > 10:
            anomalies.append({
                "type": "high_workflow_rejection",
                "risk_level": "medium",
                "description": f"High workflow rejection rate ({len(entries)} rejections)",
                "details": {"rejection_count": len(entries)},
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "module": "workflow",
            })

        return anomalies

    # ------------------------------------------------------------------
    #  Bottleneck Detection
    # ------------------------------------------------------------------

    def detect_bottlenecks(self, org_id: str) -> list[dict]:
        """Detect system bottlenecks."""
        bottlenecks = []
        entries, total = audit_service.search(
            organization_id=org_id or None,
            module="workflow",
            limit=100,
        )

        # Check pending workflows
        pending = len([e for e in entries if e.get("action") == "submit"])
        if pending > 50:
            bottlenecks.append({
                "type": "workflow_backlog",
                "severity": "medium",
                "description": f"Workflow backlog: {pending} pending approvals",
                "count": pending,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })

        return bottlenecks

    # ------------------------------------------------------------------
    #  Risk Scoring
    # ------------------------------------------------------------------

    def calculate_user_risk(self, user_id: int, org_id: str) -> dict:
        """Calculate risk score for a user."""
        entries, total = audit_service.search(
            organization_id=org_id,
            actor_user_id=user_id,
            limit=0,
        )
        warnings = len([e for e in entries if e.get("severity") == "warning"])
        criticals = len([e for e in entries if e.get("severity") == "critical"])

        score = 0.0
        score += min(warnings * 0.1, 0.5)
        score += min(criticals * 0.2, 0.4)

        level = RiskLevel.LOW
        if score > 0.5:
            level = RiskLevel.MEDIUM
        if score > 0.7:
            level = RiskLevel.HIGH
        if score > 0.9:
            level = RiskLevel.CRITICAL

        return {
            "user_id": user_id,
            "risk_score": round(score, 2),
            "risk_level": level.value,
            "factors": {
                "warnings": warnings,
                "criticals": criticals,
                "total_events": total,
            },
        }

    def calculate_org_risk(self, org_id: str) -> dict:
        """Calculate risk score for an organization."""
        entries, total = audit_service.search(organization_id=org_id, limit=0)
        warnings = len([e for e in entries if e.get("severity") == "warning"])
        criticals = len([e for e in entries if e.get("severity") == "critical"])

        anomalies = self._anomalies[-50:]
        recent_anomalies = len(
            [a for a in anomalies if a.get("module") != ""]
        )

        score = 0.0
        score += min(warnings * 0.05, 0.3)
        score += min(criticals * 0.1, 0.3)
        score += min(recent_anomalies * 0.1, 0.2)

        level = RiskLevel.LOW
        if score > 0.4:
            level = RiskLevel.MEDIUM
        if score > 0.6:
            level = RiskLevel.HIGH
        if score > 0.8:
            level = RiskLevel.CRITICAL

        return {
            "organization_id": org_id,
            "risk_score": round(score, 2),
            "risk_level": level.value,
            "factors": {
                "total_events": total,
                "warnings": warnings,
                "criticals": criticals,
                "recent_anomalies": recent_anomalies,
            },
        }

    # ------------------------------------------------------------------
    #  Insights Generation
    # ------------------------------------------------------------------

    def generate_insights(self, org_id: str) -> list[dict]:
        """Generate actionable insights."""
        insights = []

        # Check system health
        from app.services.monitor_service import monitor_service
        health_score = monitor_service.get_health_score()
        if health_score < 0.7:
            insights.append({
                "type": "system_health",
                "priority": "high",
                "message": f"System health score is low ({health_score}). Review monitoring dashboard.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # Check failed jobs
        from app.services.scheduler_service import scheduler_service
        job_stats = scheduler_service.get_stats()
        if job_stats["failed"] > 0:
            insights.append({
                "type": "failed_jobs",
                "priority": "medium",
                "message": f"{job_stats['failed']} failed job(s) in queue. Check scheduler for details.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # Check event bus
        event_stats = event_bus.get_stats()
        if event_stats.get("dead_letter_count", 0) > 0:
            insights.append({
                "type": "dead_letter_events",
                "priority": "medium",
                "message": f"{event_stats['dead_letter_count']} event(s) in dead-letter queue.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # Check compliance
        compliance = audit_service.get_compliance_summary(org_id)
        if compliance.get("critical_events", 0) > 0:
            insights.append({
                "type": "critical_events",
                "priority": "high",
                "message": f"{compliance['critical_events']} critical security event(s) detected.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        self._insights.extend(insights)
        if len(self._insights) > self._max_history:
            self._insights = self._insights[-self._max_history:]

        return insights

    # ------------------------------------------------------------------
    #  Dashboard
    # ------------------------------------------------------------------

    def get_intelligence_dashboard(self, org_id: str) -> dict:
        """Get complete intelligence dashboard."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "anomalies": self._anomalies[-20:],
            "insights": self.generate_insights(org_id),
            "bottlenecks": self.detect_bottlenecks(org_id),
            "org_risk": self.calculate_org_risk(org_id),
        }


# Singleton
intelligence_service = IntelligenceService()
