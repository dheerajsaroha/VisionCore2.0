"""
rating_normalization.py — Performance Rating Normalization & Bell Curve Engine
Sprint 4 — Entity 1: Performance Management System
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.models.all_models import PerformanceRating, PerformanceReview, User, Department


class RatingNormalization:
    """Enterprise rating normalization engine for calibration, bell curve
    distribution, cross-department comparison, and forced distribution."""

    BELL_CURVE_BUCKETS = [
        {"label": "Exceptional (4.5 - 5.0)", "min": 4.5, "max": 5.0, "expected_pct": 10},
        {"label": "Exceeds Expectations (3.8 - 4.4)", "min": 3.8, "max": 4.49, "expected_pct": 20},
        {"label": "Meets Expectations (2.8 - 3.7)", "min": 2.8, "max": 3.79, "expected_pct": 40},
        {"label": "Needs Improvement (2.0 - 2.7)", "min": 2.0, "max": 2.79, "expected_pct": 20},
        {"label": "Unsatisfactory (< 2.0)", "min": 0.0, "max": 1.99, "expected_pct": 10},
    ]

    RATING_LABELS = [
        ("Exceptional", 4.5, 5.0),
        ("Exceeds Expectations", 3.8, 4.49),
        ("Meets Expectations", 2.8, 3.79),
        ("Needs Improvement", 2.0, 2.79),
        ("Unsatisfactory", 0.0, 1.99),
    ]

    @staticmethod
    def resolve_rating_label(final_rating: float) -> str:
        """Map a numeric rating to its text label."""
        for label, low, high in RatingNormalization.RATING_LABELS:
            if low <= final_rating <= high:
                return label
        return "Meets Expectations"

    @staticmethod
    def compute_bell_curve(db: Session, org_id: UUID,
                           cycle_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Compute bell curve distribution of ratings for an org."""
        q = db.query(PerformanceRating).filter(PerformanceRating.organization_id == org_id)
        if cycle_id:
            q = q.filter(PerformanceRating.cycle_id == cycle_id)

        ratings = q.all()
        total = max(1, len(ratings))
        buckets = []

        for bucket in RatingNormalization.BELL_CURVE_BUCKETS:
            count = sum(1 for r in ratings if r.final_rating and
                        bucket["min"] <= float(r.final_rating) <= bucket["max"])
            buckets.append({
                "rating_label": bucket["label"],
                "min": bucket["min"],
                "max": bucket["max"],
                "count": count,
                "pct": round((count / total) * 100, 1),
                "expected_pct": bucket["expected_pct"]
            })

        return buckets

    @staticmethod
    def compute_department_averages(db: Session, org_id: UUID,
                                     cycle_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Compute average performance rating per department."""
        departments = db.query(Department).filter(Department.org_id == org_id, Department.is_deleted == 0).all()

        dept_stats = []
        for dept in departments:
            users = db.query(User.id).filter(User.org_id == org_id, User.dept_id == dept.id).subquery()
            q = db.query(PerformanceRating).filter(
                PerformanceRating.organization_id == org_id,
                PerformanceRating.user_id.in_(db.query(User.id).filter(User.dept_id == dept.id))
            )
            if cycle_id:
                q = q.filter(PerformanceRating.cycle_id == cycle_id)

            ratings = q.all()
            if not ratings:
                continue

            scores = [float(r.final_rating or 3.0) for r in ratings]
            dept_stats.append({
                "department_id": dept.id,
                "department_name": dept.name,
                "avg_rating": round(sum(scores) / len(scores), 2),
                "employee_count": len(ratings),
                "top_rating": round(max(scores), 2),
                "bottom_rating": round(min(scores), 2)
            })

        return sorted(dept_stats, key=lambda x: x["avg_rating"], reverse=True)

    @staticmethod
    def get_top_performers(db: Session, org_id: UUID, cycle_id: Optional[int] = None,
                           limit: int = 10) -> List[Dict[str, Any]]:
        """Get top N performers by final rating."""
        q = db.query(PerformanceRating).filter(PerformanceRating.organization_id == org_id)
        if cycle_id:
            q = q.filter(PerformanceRating.cycle_id == cycle_id)

        ratings = q.order_by(PerformanceRating.final_rating.desc()).limit(limit).all()

        results = []
        for r in ratings:
            user = db.query(User).filter(User.id == r.user_id).first()
            results.append({
                "user_id": r.user_id,
                "user_name": user.full_name if user else "Unknown",
                "department_name": user.department.name if user and user.department else "N/A",
                "final_rating": float(r.final_rating) if r.final_rating else 0.0,
                "rating_label": r.rating_label or "Meets Expectations",
                "kpi_score": float(r.kpi_score) if r.kpi_score else 0.0,
                "goal_score": float(r.goal_score) if r.goal_score else 0.0,
                "competency_score": float(r.competency_score) if r.competency_score else 0.0,
                "is_calibrated": r.is_calibrated
            })

        return results

    @staticmethod
    def get_bottom_performers(db: Session, org_id: UUID, cycle_id: Optional[int] = None,
                              limit: int = 10) -> List[Dict[str, Any]]:
        """Get bottom N performers by final rating."""
        q = db.query(PerformanceRating).filter(PerformanceRating.organization_id == org_id)
        if cycle_id:
            q = q.filter(PerformanceRating.cycle_id == cycle_id)

        ratings = q.order_by(PerformanceRating.final_rating.asc()).limit(limit).all()

        results = []
        for r in ratings:
            user = db.query(User).filter(User.id == r.user_id).first()
            results.append({
                "user_id": r.user_id,
                "user_name": user.full_name if user else "Unknown",
                "department_name": user.department.name if user and user.department else "N/A",
                "final_rating": float(r.final_rating) if r.final_rating else 0.0,
                "rating_label": r.rating_label or "Unsatisfactory",
                "kpi_score": float(r.kpi_score) if r.kpi_score else 0.0,
                "goal_score": float(r.goal_score) if r.goal_score else 0.0,
                "competency_score": float(r.competency_score) if r.competency_score else 0.0,
                "is_calibrated": r.is_calibrated
            })

        return results

    @staticmethod
    def normalize_ratings_across_departments(db: Session, org_id: UUID,
                                              cycle_id: int) -> Dict[str, Any]:
        """Apply cross-department normalization to reduce manager bias."""
        dept_stats = RatingNormalization.compute_department_averages(db, org_id, cycle_id)
        if not dept_stats:
            return {"message": "No data to normalize", "adjustments": []}

        org_avg = sum(d["avg_rating"] for d in dept_stats) / len(dept_stats)
        adjustments = []

        for dept in dept_stats:
            deviation = round(org_avg - dept["avg_rating"], 2)
            adjustments.append({
                "department_id": dept["department_id"],
                "department_name": dept["department_name"],
                "dept_avg": dept["avg_rating"],
                "org_avg": round(org_avg, 2),
                "deviation": deviation,
                "adjustment_direction": "up" if deviation > 0.3 else ("down" if deviation < -0.3 else "none")
            })

        return {
            "org_avg": round(org_avg, 2),
            "departments_analyzed": len(dept_stats),
            "adjustments": adjustments
        }


rating_normalization = RatingNormalization()

