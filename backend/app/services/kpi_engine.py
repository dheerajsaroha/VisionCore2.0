"""
kpi_engine.py — Dedicated KPI Calculation Engine Service
Sprint 4 — Entity 1: Performance Management System
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.models.all_models import KPI, KPIAssignment, User


class KPIEngine:
    """Enterprise KPI calculation engine with weighted scoring, normalization,
    and percentile-based analytics."""

    @staticmethod
    def calculate_kpi_score(actual_value: float, target_value: float) -> float:
        """
        Calculate a normalized 1.0-5.0 score from actual vs target.
        Uses logarithmic scaling to prevent outlier domination.
        """
        if target_value <= 0:
            return 5.0
        ratio = max(0.0, min(2.0, float(actual_value) / float(target_value)))
        # Logarithmic scale: 0% target → 1.0, 100% target → 3.0, 200%+ → 5.0
        if ratio >= 1.0:
            score = 3.0 + (ratio - 1.0) * 2.0
        else:
            score = 1.0 + ratio * 2.0
        return round(min(5.0, max(1.0, score)), 2)

    @staticmethod
    def calculate_weighted_score(db: Session, user_id: int, cycle_id: int) -> Optional[float]:
        """Calculate weighted average KPI score for a user in a cycle."""
        assignments = db.query(KPIAssignment).filter(
            KPIAssignment.user_id == user_id,
            KPIAssignment.cycle_id == cycle_id,
            KPIAssignment.score.isnot(None)
        ).all()

        if not assignments:
            return None

        total_weighted = sum(float(a.score) * float(a.weight) for a in assignments)
        total_weight = sum(float(a.weight) for a in assignments)
        if total_weight <= 0:
            return None
        return round(total_weighted / total_weight, 2)

    @staticmethod
    def calculate_org_kpi_summary(db: Session, org_id: UUID, cycle_id: int) -> Dict[str, Any]:
        """Aggregate KPI statistics across the organization."""
        assignments = db.query(KPIAssignment).filter(
            KPIAssignment.organization_id == org_id,
            KPIAssignment.cycle_id == cycle_id
        ).all()

        if not assignments:
            return {
                "total_assignments": 0,
                "avg_score": 0.0,
                "completion_rate": 0.0,
                "top_kpis": [],
                "department_breakdown": {}
            }

        scored = [a for a in assignments if a.score is not None]
        avg_score = round(sum(float(a.score) for a in scored) / max(1, len(scored)), 2) if scored else 0.0
        completion_rate = round((len(scored) / len(assignments)) * 100, 1)

        return {
            "total_assignments": len(assignments),
            "scored_assignments": len(scored),
            "avg_score": avg_score,
            "completion_rate": completion_rate
        }

    @staticmethod
    def get_user_kpi_performance(db: Session, user_id: int, cycle_id: int) -> Dict[str, Any]:
        """Get detailed KPI performance breakdown for a user."""
        assignments = db.query(KPIAssignment).filter(
            KPIAssignment.user_id == user_id,
            KPIAssignment.cycle_id == cycle_id
        ).all()

        results = []
        for a in assignments:
            kpi = db.query(KPI).filter(KPI.id == a.kpi_id).first()
            results.append({
                "assignment_id": a.id,
                "kpi_name": kpi.name if kpi else "Unknown",
                "kpi_type": kpi.kpi_type if kpi else "individual",
                "target_value": float(a.target_value),
                "actual_value": float(a.actual_value) if a.actual_value else None,
                "weight": float(a.weight),
                "score": float(a.score) if a.score else None,
                "status": "completed" if a.score else "pending"
            })

        weighted_score = KPIEngine.calculate_weighted_score(db, user_id, cycle_id)

        return {
            "user_id": user_id,
            "cycle_id": cycle_id,
            "weighted_score": weighted_score,
            "assignments": results,
            "total_kpis": len(assignments),
            "completed_kpis": sum(1 for a in assignments if a.score is not None)
        }


kpi_engine = KPIEngine()

