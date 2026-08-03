"""
workforce_planning_service.py — VisionCore 3.0 Workforce Planning & Capacity Services

Provides:
- WorkforcePlanningService: headcount plans, vacancy tracking, hiring forecasts
- CapacityPlanningService: capacity snapshots, utilization metrics
- BenchManagementService: bench assignment, bench aging reports

Integrates: audit_service, event_bus, notification_service, business_calendar_service.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.all_models import (
    BenchRecord,
    CapacitySnapshot,
    HeadcountPlan,
    User,
    WorkforceForcast,
)
from app.services.audit_service import audit_service
from app.services.event_bus import event_bus

logger = logging.getLogger(__name__)


class WorkforcePlanningService:
    """Headcount plans, vacancy tracking, and hiring forecasts."""

    def create_headcount_plan(self, db: Session, org_id: UUID, data: Dict[str, Any]) -> HeadcountPlan:
        plan = HeadcountPlan(org_id=org_id, **data)
        db.add(plan)
        db.commit()
        db.refresh(plan)

        audit_service.record(
            organization_id=str(org_id),
            module="workforce_planning",
            action="create_headcount_plan",
            entity_type="headcount_plan",
            entity_id=str(plan.id),
            summary=(
                f"Headcount plan created for dept {plan.dept_id}, "
                f"period {plan.period_year}-{plan.period_month or '*'}"
            ),
            details={"planned_headcount": plan.planned_headcount},
        )
        event_bus.publish(
            "HeadcountPlanCreated",
            str(org_id),
            {
                "plan_id": plan.id,
                "org_id": str(org_id),
                "dept_id": plan.dept_id,
                "period_year": plan.period_year,
                "period_month": plan.period_month,
                "planned_headcount": plan.planned_headcount,
            },
        )
        return plan

    def list_headcount_plans(
        self, db: Session, org_id: UUID, dept_id: Optional[int] = None, year: Optional[int] = None
    ) -> List[HeadcountPlan]:
        q = db.query(HeadcountPlan).filter(HeadcountPlan.org_id == org_id)
        if dept_id is not None:
            q = q.filter(HeadcountPlan.dept_id == dept_id)
        if year:
            q = q.filter(HeadcountPlan.period_year == year)
        return q.order_by(HeadcountPlan.period_year.desc(), HeadcountPlan.period_month.desc()).all()

    def compute_vacancies(self, db: Session, org_id: UUID, dept_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Compute open vacancies as planned headcount minus active employees."""
        plans = self.list_headcount_plans(db, org_id, dept_id=dept_id)
        vacancies = []
        for plan in plans:
            active_count = (
                db.query(User)
                .filter(User.org_id == org_id, User.dept_id == plan.dept_id, User.is_deleted == 0, User.is_active == 1)
                .count()
            )
            vacancies.append({
                "plan_id": plan.id,
                "dept_id": plan.dept_id,
                "period_year": plan.period_year,
                "period_month": plan.period_month,
                "planned_headcount": plan.planned_headcount,
                "approved_headcount": plan.approved_headcount,
                "active_employees": active_count,
                "open_vacancies": max(0, int(plan.planned_headcount) - active_count),
            })
        return vacancies

    def create_forecast(self, db: Session, org_id: UUID, data: Dict[str, Any]) -> WorkforceForcast:
        forecast = WorkforceForcast(org_id=org_id, **data)
        db.add(forecast)
        db.commit()
        db.refresh(forecast)

        audit_service.record(
            organization_id=str(org_id),
            module="workforce_planning",
            action="create_forecast",
            entity_type="workforce_forecast",
            entity_id=str(forecast.id),
            summary=f"Workforce forecast created for period {forecast.forecast_period}",
            details={"hiring_requirement": forecast.hiring_requirement},
        )
        return forecast

    def list_forecasts(self, db: Session, org_id: UUID) -> List[WorkforceForcast]:
        return (
            db.query(WorkforceForcast)
            .filter(WorkforceForcast.org_id == org_id)
            .order_by(WorkforceForcast.forecast_period.desc())
            .all()
        )


class CapacityPlanningService:
    """Capacity snapshots, utilization metrics, and bench tracking."""

    def create_snapshot(self, db: Session, org_id: UUID, dept_id: Optional[int] = None, note: Optional[str] = None) -> CapacitySnapshot:
        """Create a point-in-time capacity snapshot for a department."""
        active_users = (
            db.query(User)
            .filter(User.org_id == org_id, User.is_deleted == 0, User.is_active == 1)
            .all()
        )
        if dept_id is not None:
            active_users = [u for u in active_users if u.dept_id == dept_id]

        assigned = len(active_users)
        # Bench members are users with an active bench record (unallocated capacity)
        bench_user_ids = {
            b.user_id
            for b in db.query(BenchRecord).filter(
                BenchRecord.org_id == org_id, BenchRecord.status == "ON_BENCH"
            ).all()
        }
        bench_count = len([u for u in active_users if u.id in bench_user_ids])

        capacity = float(self._dept_capacity(db, org_id, dept_id))
        allocated = max(0, assigned - bench_count)
        utilization = round(allocated / max(capacity, 1) * 100, 1)

        snapshot = CapacitySnapshot(
            org_id=org_id,
            dept_id=dept_id,
            snapshot_date=datetime.now(timezone.utc).date(),
            total_capacity=capacity,
            allocated_count=allocated,
            available_count=max(0, int(capacity) - allocated),
            bench_count=bench_count,
            utilization_pct=utilization,
            snapshot_metadata={"note": note} if note else {},
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        audit_service.record(
            organization_id=str(org_id),
            module="workforce_planning",
            action="create_snapshot",
            entity_type="capacity_snapshot",
            entity_id=str(snapshot.id),
            summary=f"Capacity snapshot captured for dept {dept_id}: {utilization}% utilized",
            details={
                "total_capacity": capacity,
                "allocated_count": allocated,
                "bench_count": bench_count,
                "utilization_pct": utilization,
            },
        )
        event_bus.publish(
            "CapacitySnapshotCreated",
            str(org_id),
            {
                "snapshot_id": snapshot.id,
                "org_id": str(org_id),
                "dept_id": dept_id,
                "utilization_pct": utilization,
                "bench_count": bench_count,
            },
        )
        return snapshot

    def list_snapshots(
        self, db: Session, org_id: UUID, dept_id: Optional[int] = None, limit: int = 50
    ) -> List[CapacitySnapshot]:
        q = db.query(CapacitySnapshot).filter(CapacitySnapshot.org_id == org_id)
        if dept_id is not None:
            q = q.filter(CapacitySnapshot.dept_id == dept_id)
        return q.order_by(CapacitySnapshot.snapshot_date.desc()).limit(limit).all()

    def _dept_capacity(self, db: Session, org_id: UUID, dept_id: Optional[int]) -> int:
        """Estimate capacity from the latest headcount plan for the department."""
        q = (
            db.query(HeadcountPlan)
            .filter(HeadcountPlan.org_id == org_id)
            .order_by(HeadcountPlan.period_year.desc(), HeadcountPlan.period_month.desc())
        )
        if dept_id is not None:
            q = q.filter(HeadcountPlan.dept_id == dept_id)
        latest = q.first()
        if latest:
            return int(latest.planned_headcount)
        # Fallback: default capacity = active count * 1.2 (safe buffer)
        active_count = (
            db.query(User)
            .filter(User.org_id == org_id, User.is_deleted == 0, User.is_active == 1)
            .count()
        )
        return max(active_count, 1)


class BenchManagementService:
    """Bench assignment, aging, and release."""

    def add_to_bench(self, db: Session, org_id: UUID, user_id: int, reason: Optional[str] = None, actor_user_id: Optional[int] = None) -> BenchRecord:
        user = db.query(User).filter(User.id == user_id, User.org_id == org_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found in org")

        existing = db.query(BenchRecord).filter(
            BenchRecord.org_id == org_id,
            BenchRecord.user_id == user_id,
            BenchRecord.status == "ON_BENCH",
        ).first()
        if existing:
            raise ValueError(f"User {user_id} is already on bench")

        record = BenchRecord(
            org_id=org_id,
            user_id=user_id,
            dept_id=user.dept_id,
            bench_start_date=datetime.now(timezone.utc).date(),
            reason=reason,
            status="ON_BENCH",
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        audit_service.record(
            actor_user_id=actor_user_id,
            organization_id=str(org_id),
            module="workforce_planning",
            action="bench_add",
            entity_type="bench_record",
            entity_id=str(record.id),
            summary=f"User {user_id} added to bench",
        )
        event_bus.publish(
            "BenchAssigned",
            str(org_id),
            {
                "bench_id": record.id,
                "user_id": user_id,
                "org_id": str(org_id),
                "start_date": str(record.bench_start_date),
            },
            actor_id=actor_user_id,
        )
        return record

    def release_from_bench(self, db: Session, org_id: UUID, bench_id: int, actor_user_id: Optional[int] = None) -> BenchRecord:
        record = db.query(BenchRecord).filter(BenchRecord.id == bench_id, BenchRecord.org_id == org_id).first()
        if not record:
            raise ValueError(f"Bench record {bench_id} not found")
        if record.status != "ON_BENCH":
            raise ValueError("Bench record is not currently ON_BENCH")

        record.status = "RELEASED"
        record.bench_end_date = datetime.now(timezone.utc).date()
        record.days_on_bench = max(
            0, (record.bench_end_date - record.bench_start_date).days
        )
        db.commit()
        db.refresh(record)

        audit_service.record(
            actor_user_id=actor_user_id,
            organization_id=str(org_id),
            module="workforce_planning",
            action="bench_release",
            entity_type="bench_record",
            entity_id=str(record.id),
            summary=f"User {record.user_id} released from bench",
        )
        return record

    def bench_report(self, db: Session, org_id: UUID) -> Dict[str, Any]:
        """Bench aging report — active bench members with days on bench."""
        records = (
            db.query(BenchRecord)
            .filter(BenchRecord.org_id == org_id, BenchRecord.status == "ON_BENCH")
            .order_by(BenchRecord.bench_start_date)
            .all()
        )
        today = datetime.now(timezone.utc).date()
        items = []
        total_days = 0
        for r in records:
            days_on_bench = (today - r.bench_start_date).days if r.bench_start_date else 0
            total_days += max(0, days_on_bench)
            items.append({
                "bench_id": r.id,
                "user_id": r.user_id,
                "user_name": r.user.full_name if r.user else None,
                "dept_id": r.dept_id,
                "bench_start_date": str(r.bench_start_date),
                "days_on_bench": max(0, days_on_bench),
                "reason": r.reason,
            })

        items.sort(key=lambda x: x["days_on_bench"], reverse=True)
        return {
            "org_id": str(org_id),
            "total_on_bench": len(items),
            "total_bench_days": total_days,
            "avg_bench_days": round(total_days / max(len(items), 1), 1),
            "records": items,
        }


workforce_planning_service = WorkforcePlanningService()
capacity_planning_service = CapacityPlanningService()
bench_management_service = BenchManagementService()

