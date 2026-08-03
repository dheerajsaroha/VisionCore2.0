"""
performance_analytics.py — Enterprise Performance Analytics Engine
Sprint 4 — Entity 1: Performance Management System
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models.all_models import (
    User, PerformanceCycle, PerformanceReview, PerformanceRating, Goal,
    KPI, KPIAssignment, PerformanceImprovementPlan, PromotionRecommendation,
    Competency, CompetencyRating, Department, Feedback
)
from app.services.rating_normalization import rating_normalization
from app.services.kpi_engine import kpi_engine
from app.services.goal_scoring_engine import goal_scoring_engine


class PerformanceAnalytics:
    """Unified performance analytics engine providing executive dashboards,
    trend analysis, attrition risk indicators, and pipeline analytics."""

    @staticmethod
    def get_dashboard(db: Session, org_id: UUID,
                      cycle_id: Optional[int] = None) -> Dict[str, Any]:
        """Aggregated executive dashboard for Performance Management Center."""
        # Employee count
        total_emp = db.query(User).filter(User.org_id == org_id, User.is_deleted == 0).count()

        # Cycle info
        cycle_query = db.query(PerformanceCycle).filter(PerformanceCycle.organization_id == org_id)
        if cycle_id:
            cycle_query = cycle_query.filter(PerformanceCycle.id == cycle_id)
        active_cycle = cycle_query.first()
        active_cycle_id = cycle_id or (active_cycle.id if active_cycle else None)

        # Review stats
        rev_q = db.query(PerformanceReview).filter(PerformanceReview.organization_id == org_id)
        if active_cycle_id:
            rev_q = rev_q.filter(PerformanceReview.cycle_id == active_cycle_id)

        total_reviews = rev_q.count()
        completed_reviews = rev_q.filter(PerformanceReview.status.in_(["submitted", "acknowledged"])).count()
        pending_reviews = total_reviews - completed_reviews
        rev_completion_pct = round((completed_reviews / max(1, total_reviews)) * 100, 1)

        # Rating stats
        rat_q = db.query(PerformanceRating).filter(PerformanceRating.organization_id == org_id)
        if active_cycle_id:
            rat_q = rat_q.filter(PerformanceRating.cycle_id == active_cycle_id)
        ratings = rat_q.all()
        avg_rating = round(sum(float(r.final_rating or 3.0) for r in ratings) / max(1, len(ratings)), 2) if ratings else 3.5

        # Goal stats
        g_q = db.query(Goal).filter(Goal.organization_id == org_id)
        if active_cycle_id:
            g_q = g_q.filter(Goal.cycle_id == active_cycle_id)
        goals = g_q.all()
        goal_completion_pct = round(
            sum(float(g.completion_pct) for g in goals) / max(1, len(goals)), 1
        ) if goals else 0.0

        # PIPs
        active_pips = db.query(PerformanceImprovementPlan).filter(
            PerformanceImprovementPlan.organization_id == org_id,
            PerformanceImprovementPlan.status == "active"
        ).count()

        # Promotions
        promo_candidates = db.query(PromotionRecommendation).filter(
            PromotionRecommendation.organization_id == org_id,
            PromotionRecommendation.status == "pending"
        ).count()

        # Bell curve
        bell_curve = rating_normalization.compute_bell_curve(db, org_id, active_cycle_id)

        # KPI summary
        kpi_summary = None
        if active_cycle_id:
            kpi_summary = kpi_engine.calculate_org_kpi_summary(db, org_id, active_cycle_id)

        return {
            "total_employees": total_emp,
            "active_cycle_id": active_cycle_id,
            "active_cycle_name": active_cycle.name if active_cycle else None,
            "completed_reviews": completed_reviews,
            "pending_reviews": pending_reviews,
            "review_completion_pct": rev_completion_pct,
            "avg_performance_rating": avg_rating,
            "goal_completion_pct": goal_completion_pct,
            "active_pips": active_pips,
            "promotion_candidates": promo_candidates,
            "bell_curve": bell_curve,
            "kpi_summary": kpi_summary
        }

    @staticmethod
    def get_department_comparison(db: Session, org_id: UUID,
                                   cycle_id: Optional[int] = None) -> Dict[str, Any]:
        """Cross-department performance comparison."""
        dept_stats = rating_normalization.compute_department_averages(db, org_id, cycle_id)

        # Department goal completion
        dept_goals = {}
        for dept_stat in dept_stats:
            dept_id = dept_stat["department_id"]
            goal_q = db.query(Goal).filter(
                Goal.organization_id == org_id,
                Goal.user_id.in_(
                    db.query(User.id).filter(User.dept_id == dept_id)
                )
            )
            if cycle_id:
                goal_q = goal_q.filter(Goal.cycle_id == cycle_id)
            dept_goals[str(dept_id)] = goal_scoring_engine.get_org_goal_summary(db, org_id, cycle_id)

        # Top performing department
        top_dept = max(dept_stats, key=lambda x: x["avg_rating"]) if dept_stats else None

        return {
            "departments": dept_stats,
            "total_departments": len(dept_stats),
            "top_department": top_dept,
            "department_goals": dept_goals
        }

    @staticmethod
    def get_attrition_risk_indicators(db: Session, org_id: UUID,
                                       cycle_id: Optional[int] = None) -> Dict[str, Any]:
        """Attrition risk indicators based on performance data."""
        # Bottom performers (potential flight risk)
        bottom = rating_normalization.get_bottom_performers(db, org_id, cycle_id, limit=10)

        # Active PIP status
        pips = db.query(PerformanceImprovementPlan).filter(
            PerformanceImprovementPlan.organization_id == org_id,
            PerformanceImprovementPlan.status == "active"
        ).all()

        # Low performers who are not on PIP
        rat_q = db.query(PerformanceRating).filter(
            PerformanceRating.organization_id == org_id,
            PerformanceRating.final_rating < 2.0
        )
        if cycle_id:
            rat_q = rat_q.filter(PerformanceRating.cycle_id == cycle_id)
        low_performers = rat_q.count()

        return {
            "bottom_performers": bottom,
            "active_pips_count": len(pips),
            "low_performers_not_on_pip": max(0, low_performers - len(pips)),
            "attrition_risk_count": len(bottom)
        }

    @staticmethod
    def get_review_pipeline(db: Session, org_id: UUID,
                             cycle_id: Optional[int] = None) -> Dict[str, Any]:
        """Get the review completion pipeline status."""
        rev_q = db.query(PerformanceReview).filter(PerformanceReview.organization_id == org_id)
        if cycle_id:
            rev_q = rev_q.filter(PerformanceReview.cycle_id == cycle_id)

        reviews = rev_q.all()
        total = max(1, len(reviews))

        pipeline = {
            "total": len(reviews),
            "pending": sum(1 for r in reviews if r.status == "pending"),
            "in_progress": sum(1 for r in reviews if r.status == "in_progress"),
            "submitted": sum(1 for r in reviews if r.status == "submitted"),
            "acknowledged": sum(1 for r in reviews if r.status == "acknowledged"),
            "completion_pct": round(
                (sum(1 for r in reviews if r.status in ["submitted", "acknowledged"]) / total) * 100, 1
            )
        }

        # Breakdown by review type
        by_type = {}
        for r in reviews:
            by_type[r.review_type] = by_type.get(r.review_type, 0) + 1

        pipeline["by_type"] = by_type
        return pipeline

    @staticmethod
    def get_promotion_pipeline(db: Session, org_id: UUID) -> Dict[str, Any]:
        """Analyze promotion pipeline status."""
        recs = db.query(PromotionRecommendation).filter(
            PromotionRecommendation.organization_id == org_id
        ).all()

        return {
            "total_recommendations": len(recs),
            "pending": sum(1 for r in recs if r.status == "pending"),
            "approved": sum(1 for r in recs if r.status == "approved"),
            "rejected": sum(1 for r in recs if r.status == "rejected"),
            "deferred": sum(1 for r in recs if r.status == "deferred"),
            "avg_readiness_score": round(
                sum(float(r.readiness_score or 3.0) for r in recs) / max(1, len(recs)), 2
            ) if recs else 0.0
        }


performance_analytics = PerformanceAnalytics()

