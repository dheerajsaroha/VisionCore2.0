"""
promotion_engine.py — Promotion Recommendation & Readiness Assessment Engine
Sprint 4 — Entity 1: Performance Management System
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db.models.all_models import (
    User, PromotionRecommendation, PerformanceRating, PerformanceReview,
    Competency, CompetencyRating, NineBoxGrid
)
from app.services.rating_normalization import rating_normalization


class PromotionEngine:
    """Enterprise promotion engine with readiness assessment,
    salary recommendation modeling, and historical analytics."""

    @staticmethod
    def compute_readiness_score(db: Session, user_id: int,
                                cycle_id: Optional[int] = None) -> Dict[str, Any]:
        """Compute multi-factor readiness score (1-5) for promotion."""
        factors = {}
        scores = []

        # 1. Performance rating factor (weight: 40%)
        rat_q = db.query(PerformanceRating).filter(PerformanceRating.user_id == user_id)
        if cycle_id:
            rat_q = rat_q.filter(PerformanceRating.cycle_id == cycle_id)
        rating = rat_q.first()

        perf_score = float(rating.final_rating) if rating and rating.final_rating else 3.0
        factors["performance_rating"] = {"score": perf_score, "weight": 0.40}
        scores.append(perf_score * 0.40)

        # 2. Nine-box potential factor (weight: 30%)
        box = db.query(NineBoxGrid).filter(NineBoxGrid.user_id == user_id).first()
        if box:
            # Convert 9-box to 1-5: (perf + potential) / 2 * 5/3
            potential_score = round(((box.performance_rating + box.potential_rating) / 2.0) * (5.0 / 3.0), 2)
            factors["nine_box_potential"] = {"score": potential_score, "weight": 0.30}
            scores.append(potential_score * 0.30)
        else:
            factors["nine_box_potential"] = {"score": 3.0, "weight": 0.30}
            scores.append(3.0 * 0.30)

        # 3. Competency growth factor (weight: 20%)
        avg_comp = db.query(CompetencyRating.rating).join(
            PerformanceReview, CompetencyRating.review_id == PerformanceReview.id
        ).filter(
            PerformanceReview.reviewee_user_id == user_id
        ).all()

        if avg_comp:
            comp_score = round(sum(float(c[0]) for c in avg_comp) / len(avg_comp), 2)
        else:
            comp_score = 3.0
        factors["competency_growth"] = {"score": comp_score, "weight": 0.20}
        scores.append(comp_score * 0.20)

        # 4. Tenure / stability factor (weight: 10%)
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.created_at:
            months_tenure = (datetime.now(timezone.utc) - user.created_at).days / 30.0
            tenure_score = round(min(5.0, max(1.0, months_tenure / 6.0)), 2)
        else:
            tenure_score = 3.0
        factors["tenure_stability"] = {"score": tenure_score, "weight": 0.10}
        scores.append(tenure_score * 0.10)

        overall = round(sum(scores), 2)

        return {
            "user_id": user_id,
            "overall_readiness": overall,
            "factors": factors,
            "recommendation": "Ready Now" if overall >= 4.0 else (
                "Ready in 6 Months" if overall >= 3.0 else (
                    "Ready in 12+ Months" if overall >= 2.0 else "Not Ready"
                )
            )
        }

    @staticmethod
    def recommend_salary_increase(current_salary: float, readiness_score: float,
                                   performance_rating: float) -> Dict[str, Any]:
        """Recommend salary increase percentage based on readiness and performance."""
        # Base increase: 5-15% range
        base_pct = 5.0 + (readiness_score / 5.0) * 10.0

        # Performance bonus
        perf_bonus = max(0.0, (performance_rating - 3.0) * 2.0)

        # Total recommendation
        recommended_pct = round(base_pct + perf_bonus, 1)

        # Cap at reasonable ranges
        recommended_pct = min(30.0, max(5.0, recommended_pct))

        recommended_amount = round(current_salary * (recommended_pct / 100.0), 2)
        new_salary = round(current_salary + recommended_amount, 2)

        return {
            "current_salary": current_salary,
            "recommended_increase_pct": recommended_pct,
            "recommended_amount": recommended_amount,
            "new_salary_proposed": new_salary,
            "rationale": f"Readiness score {readiness_score}/5.0 with performance rating {performance_rating}/5.0"
        }

    @staticmethod
    def get_promotion_matrix(db: Session, org_id: UUID,
                              cycle_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Build promotion matrix - readiness scores for all employees."""
        users = db.query(User).filter(User.org_id == org_id, User.is_deleted == 0).all()

        matrix = []
        for user in users:
            readiness = PromotionEngine.compute_readiness_score(db, user.id, cycle_id)

            # Get current role info
            current_role = user.role.name if user.role else "Employee"

            matrix.append({
                "user_id": user.id,
                "user_name": user.full_name,
                "current_role": current_role,
                "department_name": user.department.name if user.department else "N/A",
                "readiness_score": readiness["overall_readiness"],
                "recommendation": readiness["recommendation"],
                "factors": readiness["factors"]
            })

        return sorted(matrix, key=lambda x: x["readiness_score"], reverse=True)

    @staticmethod
    def get_historical_decisions(db: Session, org_id: UUID,
                                  limit: int = 20) -> List[Dict[str, Any]]:
        """Get historical promotion decisions."""
        recs = db.query(PromotionRecommendation).filter(
            PromotionRecommendation.organization_id == org_id
        ).order_by(PromotionRecommendation.created_at.desc()).limit(limit).all()

        results = []
        for r in recs:
            user = db.query(User).filter(User.id == r.user_id).first()
            results.append({
                "id": r.id,
                "user_name": user.full_name if user else "Unknown",
                "proposed_role": r.proposed_role,
                "salary_increase_pct": float(r.proposed_salary_increase_pct) if r.proposed_salary_increase_pct else None,
                "readiness_score": float(r.readiness_score) if r.readiness_score else None,
                "status": r.status,
                "decision_notes": r.decision_notes,
                "decided_at": r.decided_at.isoformat() if r.decided_at else None,
                "created_at": r.created_at.isoformat()
            })

        return results


promotion_engine = PromotionEngine()

