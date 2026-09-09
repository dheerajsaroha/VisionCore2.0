"""
metric_registry.py — Centralized Metric Registry Service
Sprint 9 — Enterprise Intelligence & Analytics Layer

Provides definition management, computation, snapshotting, and querying
for platform-wide KPIs and operational metrics.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.db.models.all_models import (
    MetricDefinition,
    MetricSnapshot,
    User,
    AttendanceLog,
    Payroll,
    Asset,
    AuditLog,
)

logger = logging.getLogger(__name__)


STANDARD_METRICS = [
    {
        "metric_key": "workforce_headcount",
        "name": "Total Active Headcount",
        "description": "Total number of active employee accounts in organization",
        "category": "workforce",
        "required_permission": "analytics.read",
        "unit": "count",
    },
    {
        "metric_key": "attendance_rate",
        "name": "Daily Attendance Rate",
        "description": "Percentage of active employees present today",
        "category": "attendance",
        "required_permission": "attendance.read",
        "unit": "percent",
    },
    {
        "metric_key": "payroll_monthly_cost",
        "name": "Total Monthly Payroll Cost",
        "description": "Sum of net payouts for current monthly payroll cycle",
        "category": "payroll",
        "required_permission": "payroll.read",
        "unit": "currency",
    },
    {
        "metric_key": "asset_utilization",
        "name": "Asset Utilization Rate",
        "description": "Percentage of organization assets currently assigned to active employees",
        "category": "assets",
        "required_permission": "assets.read",
        "unit": "percent",
    },
    {
        "metric_key": "security_login_failures",
        "name": "Login Failure Frequency",
        "description": "Total login failure events recorded in audit log in last 24h",
        "category": "security",
        "required_permission": "security.read",
        "unit": "count",
    },
]


class MetricRegistryService:
    """
    Centralized service for managing and calculating enterprise metrics.
    """

    def seed_default_metrics(self, db: Session) -> int:
        """Seeds default system metrics into metric_definitions table if missing."""
        seeded = 0
        for item in STANDARD_METRICS:
            existing = db.execute(
                select(MetricDefinition).where(MetricDefinition.metric_key == item["metric_key"])
            ).scalar_one_or_none()
            if not existing:
                defn = MetricDefinition(
                    metric_key=item["metric_key"],
                    name=item["name"],
                    description=item["description"],
                    category=item["category"],
                    required_permission=item["required_permission"],
                    unit=item["unit"],
                    is_active=True,
                )
                db.add(defn)
                seeded += 1
        if seeded > 0:
            db.commit()
            logger.info(f"Seeded {seeded} metric definitions into MetricRegistry.")
        return seeded

    def list_metric_definitions(
        self, db: Session, category: Optional[str] = None
    ) -> List[MetricDefinition]:
        """Lists defined metrics, optionally filtered by category."""
        stmt = select(MetricDefinition).where(MetricDefinition.is_active.is_(True))
        if category:
            stmt = stmt.where(MetricDefinition.category == category)
        return list(db.scalars(stmt).all())

    def get_metric_definition(self, db: Session, metric_key: str) -> Optional[MetricDefinition]:
        """Retrieves a single metric definition by key."""
        return db.execute(
            select(MetricDefinition).where(MetricDefinition.metric_key == metric_key)
        ).scalar_one_or_none()

    def record_snapshot(
        self,
        db: Session,
        org_id: UUID,
        metric_key: str,
        value: float,
        dimensions: Optional[Dict[str, Any]] = None,
        snapshot_date: Optional[datetime] = None,
    ) -> MetricSnapshot:
        """Records a new historical metric snapshot for an organization."""
        snapshot = MetricSnapshot(
            organization_id=org_id,
            metric_key=metric_key,
            metric_value=value,
            dimensions=dimensions or {},
            snapshot_date=snapshot_date or datetime.now(timezone.utc),
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return snapshot

    def get_snapshots(
        self,
        db: Session,
        org_id: UUID,
        metric_key: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[MetricSnapshot]:
        """Queries historical metric snapshots for an organization."""
        filters = [MetricSnapshot.organization_id == org_id]
        if metric_key:
            filters.append(MetricSnapshot.metric_key == metric_key)
        if start_date:
            filters.append(MetricSnapshot.snapshot_date >= start_date)
        if end_date:
            filters.append(MetricSnapshot.snapshot_date <= end_date)

        stmt = select(MetricSnapshot).where(and_(*filters)).order_by(
            MetricSnapshot.snapshot_date.desc()
        ).limit(limit)
        return list(db.scalars(stmt).all())

    def calculate_metric(self, db: Session, org_id: UUID, metric_key: str) -> float:
        """Calculates realtime value for a supported metric_key."""
        if metric_key == "workforce_headcount":
            stmt = select(User).where(
                and_(User.org_id == org_id, User.is_active.is_(True))
            )
            return float(len(db.scalars(stmt).all()))

        elif metric_key == "attendance_rate":
            total_users = len(
                db.scalars(
                    select(User).where(
                        and_(User.org_id == org_id, User.is_active.is_(True))
                    )
                ).all()
            )
            if total_users == 0:
                return 0.0
            now = datetime.now(timezone.utc)
            start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
            # AttendanceLog has no org column — filter via org users
            org_user_ids = [
                u.id for u in db.scalars(
                    select(User).where(User.org_id == org_id)
                ).all()
            ]
            present_logs = db.scalars(
                select(AttendanceLog).where(
                    and_(
                        AttendanceLog.user_id.in_(org_user_ids),
                        AttendanceLog.check_in >= start_of_day,
                    )
                )
            ).all()
            unique_present = len({log.user_id for log in present_logs})
            return round((unique_present / total_users) * 100.0, 2)

        elif metric_key == "payroll_monthly_cost":
            payrolls = db.scalars(
                select(Payroll).where(Payroll.org_id == org_id)
            ).all()
            total_cost = sum(getattr(p, "net_pay", getattr(p, "basic_salary", 0.0)) or 0.0 for p in payrolls)
            return float(total_cost)

        elif metric_key == "asset_utilization":
            assets = db.scalars(
                select(Asset).where(Asset.organization_id == org_id)
            ).all()
            if not assets:
                return 0.0
            assigned = sum(1 for a in assets if getattr(a, "status", None) == "assigned")
            return round((assigned / len(assets)) * 100.0, 2)

        elif metric_key == "security_login_failures":
            logs = db.scalars(
                select(AuditLog).where(
                    and_(
                        AuditLog.tenant_org_id == org_id,
                        AuditLog.action.ilike("%login%failure%"),
                    )
                )
            ).all()
            return float(len(logs))

        else:
            # Fall back to latest snapshot value if available
            latest = db.execute(
                select(MetricSnapshot)
                .where(
                    and_(
                        MetricSnapshot.organization_id == org_id,
                        MetricSnapshot.metric_key == metric_key,
                    )
                )
                .order_by(MetricSnapshot.snapshot_date.desc())
            ).scalar_one_or_none()
            return float(latest.metric_value) if latest else 0.0


metric_registry_service = MetricRegistryService()
