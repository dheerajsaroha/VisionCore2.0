"""
crud_performance.py — CRUD Operations & Scoring Engines for Performance Management
Sprint 4 — Entity 1
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models.all_models import (
    PerformanceCycle, Competency, KPI, KPIAssignment, Goal, GoalProgress,
    PerformanceReview, CompetencyRating, Feedback, PerformanceRating,
    CalibrationSession, PerformanceImprovementPlan, PromotionRecommendation, User
)


class CRUDPerformanceCycle:
    def get_by_id(self, db: Session, cycle_id: int) -> Optional[PerformanceCycle]:
        return db.query(PerformanceCycle).filter(PerformanceCycle.id == cycle_id).first()

    def get_all_for_org(self, db: Session, org_id: UUID, status: Optional[str] = None) -> List[PerformanceCycle]:
        q = db.query(PerformanceCycle).filter(PerformanceCycle.organization_id == org_id)
        if status:
            q = q.filter(PerformanceCycle.status == status)
        return q.order_by(PerformanceCycle.created_at.desc()).all()

    def create(self, db: Session, org_id: UUID, user_id: int, obj_in: Dict[str, Any]) -> PerformanceCycle:
        db_obj = PerformanceCycle(
            organization_id=org_id,
            created_by_user_id=user_id,
            name=obj_in["name"],
            cycle_type=obj_in["cycle_type"],
            start_date=obj_in["start_date"],
            end_date=obj_in["end_date"],
            review_deadline=obj_in.get("review_deadline"),
            description=obj_in.get("description"),
            status="draft"
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: PerformanceCycle, updates: Dict[str, Any]) -> PerformanceCycle:
        for field, val in updates.items():
            if val is not None and hasattr(db_obj, field):
                setattr(db_obj, field, val)
        db.commit()
        db.refresh(db_obj)
        return db_obj


class CRUDCompetency:
    def get_by_id(self, db: Session, comp_id: int) -> Optional[Competency]:
        return db.query(Competency).filter(Competency.id == comp_id).first()

    def get_all_for_org(self, db: Session, org_id: UUID, active_only: bool = True) -> List[Competency]:
        q = db.query(Competency).filter(Competency.organization_id == org_id)
        if active_only:
            q = q.filter(Competency.is_active.is_(True))
        return q.order_by(Competency.category.asc(), Competency.name.asc()).all()

    def create(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> Competency:
        db_obj = Competency(
            organization_id=org_id,
            name=obj_in["name"],
            category=obj_in.get("category", "technical"),
            description=obj_in.get("description"),
            is_active=obj_in.get("is_active", True)
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


class CRUDKPIEngine:
    def get_kpi_by_id(self, db: Session, kpi_id: int) -> Optional[KPI]:
        return db.query(KPI).filter(KPI.id == kpi_id).first()

    def get_kpis_for_org(self, db: Session, org_id: UUID) -> List[KPI]:
        return db.query(KPI).filter(KPI.organization_id == org_id, KPI.is_active.is_(True)).all()

    def create_kpi(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> KPI:
        db_obj = KPI(
            organization_id=org_id,
            department_id=obj_in.get("department_id"),
            name=obj_in["name"],
            description=obj_in.get("description"),
            unit=obj_in.get("unit"),
            kpi_type=obj_in.get("kpi_type", "individual"),
            is_active=obj_in.get("is_active", True)
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def assign_kpi(self, db: Session, org_id: UUID, assigned_by_user_id: int, obj_in: Dict[str, Any]) -> KPIAssignment:
        assignment = KPIAssignment(
            organization_id=org_id,
            kpi_id=obj_in["kpi_id"],
            user_id=obj_in["user_id"],
            cycle_id=obj_in["cycle_id"],
            target_value=obj_in["target_value"],
            weight=obj_in.get("weight", 1.0),
            assigned_by_user_id=assigned_by_user_id
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        return assignment

    def update_kpi_progress(self, db: Session, assignment: KPIAssignment, actual_value: float) -> KPIAssignment:
        assignment.actual_value = actual_value
        # Score calculation: 1.0 - 5.0 scaled based on actual vs target
        if assignment.target_value and assignment.target_value > 0:
            ratio = min(2.0, max(0.0, float(actual_value) / float(assignment.target_value)))
            assignment.score = round(min(5.0, max(1.0, ratio * 5.0)), 2)
        else:
            assignment.score = 5.0
        db.commit()
        db.refresh(assignment)
        return assignment

    def calculate_weighted_kpi_score(self, db: Session, user_id: int, cycle_id: int) -> Optional[float]:
        assignments = db.query(KPIAssignment).filter(
            KPIAssignment.user_id == user_id,
            KPIAssignment.cycle_id == cycle_id,
            KPIAssignment.score.isnot(None)
        ).all()

        if not assignments:
            return None

        total_weighted_score = sum(float(a.score) * float(a.weight) for a in assignments)
        total_weight = sum(float(a.weight) for a in assignments)
        if total_weight <= 0:
            return None
        return round(total_weighted_score / total_weight, 2)


class CRUDGoalEngine:
    def get_by_id(self, db: Session, goal_id: int) -> Optional[Goal]:
        return db.query(Goal).filter(Goal.id == goal_id).first()

    def get_user_goals(self, db: Session, org_id: UUID, user_id: int, cycle_id: Optional[int] = None) -> List[Goal]:
        q = db.query(Goal).filter(Goal.organization_id == org_id, Goal.user_id == user_id)
        if cycle_id:
            q = q.filter(Goal.cycle_id == cycle_id)
        return q.order_by(Goal.created_at.desc()).all()

    def create(self, db: Session, org_id: UUID, user_id: int, obj_in: Dict[str, Any]) -> Goal:
        target = obj_in.get("target_value")
        current = obj_in.get("current_value", 0.0)
        pct = 0.0
        if target and target > 0:
            pct = min(100.0, max(0.0, (current / target) * 100))

        db_obj = Goal(
            organization_id=org_id,
            user_id=obj_in.get("user_id") or user_id,
            cycle_id=obj_in.get("cycle_id"),
            parent_goal_id=obj_in.get("parent_goal_id"),
            title=obj_in["title"],
            description=obj_in.get("description"),
            goal_type=obj_in.get("goal_type", "individual"),
            goal_framework=obj_in.get("goal_framework", "smart"),
            target_value=target,
            current_value=current,
            unit=obj_in.get("unit"),
            due_date=obj_in.get("due_date"),
            priority=obj_in.get("priority", "medium"),
            completion_pct=round(pct, 2)
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def log_progress(self, db: Session, goal: Goal, user_id: int, value: float, note: Optional[str] = None) -> GoalProgress:
        goal.current_value = value
        if goal.target_value and float(goal.target_value) > 0:
            pct = min(100.0, max(0.0, (value / float(goal.target_value)) * 100))
            goal.completion_pct = round(pct, 2)
            if goal.completion_pct >= 100.0:
                goal.status = "completed"

        progress = GoalProgress(
            goal_id=goal.id,
            user_id=user_id,
            value=value,
            completion_pct=goal.completion_pct,
            note=note
        )
        db.add(goal)
        db.add(progress)
        db.commit()
        db.refresh(progress)
        return progress

    def compute_user_goal_score(self, db: Session, user_id: int, cycle_id: Optional[int] = None) -> Optional[float]:
        goals = self.get_user_goals(db, db.query(Goal).first().organization_id if db.query(Goal).first() else None, user_id, cycle_id)
        if not goals:
            return None
        avg_pct = sum(float(g.completion_pct) for g in goals) / len(goals)
        # Scale 0-100% to 1.0-5.0
        return round(min(5.0, max(1.0, 1.0 + (avg_pct / 100.0) * 4.0)), 2)


class CRUDReviewEngine:
    def get_by_id(self, db: Session, review_id: int) -> Optional[PerformanceReview]:
        return db.query(PerformanceReview).filter(PerformanceReview.id == review_id).first()

    def get_reviews(self, db: Session, org_id: UUID, cycle_id: Optional[int] = None, user_id: Optional[int] = None) -> List[PerformanceReview]:
        q = db.query(PerformanceReview).filter(PerformanceReview.organization_id == org_id)
        if cycle_id:
            q = q.filter(PerformanceReview.cycle_id == cycle_id)
        if user_id:
            q = q.filter(PerformanceReview.reviewee_user_id == user_id)
        return q.order_by(PerformanceReview.created_at.desc()).all()

    def create_review(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> PerformanceReview:
        review = PerformanceReview(
            organization_id=org_id,
            cycle_id=obj_in["cycle_id"],
            reviewee_user_id=obj_in["reviewee_user_id"],
            reviewer_user_id=obj_in.get("reviewer_user_id"),
            review_type=obj_in.get("review_type", "self"),
            status="pending"
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        return review

    def submit_review(self, db: Session, review: PerformanceReview, obj_in: Dict[str, Any]) -> PerformanceReview:
        review.overall_score = obj_in.get("overall_score")
        review.strengths = obj_in.get("strengths")
        review.areas_for_improvement = obj_in.get("areas_for_improvement")
        review.comments = obj_in.get("comments")
        review.status = "submitted"
        review.submitted_at = datetime.now(timezone.utc)

        # Clear existing ratings and write new
        if obj_in.get("competency_ratings"):
            db.query(CompetencyRating).filter(CompetencyRating.review_id == review.id).delete()
            for cr in obj_in["competency_ratings"]:
                rating = CompetencyRating(
                    review_id=review.id,
                    competency_id=cr["competency_id"],
                    rating=cr["rating"],
                    evidence=cr.get("evidence")
                )
                db.add(rating)

            # Auto-calculate overall_score if not supplied
            if not review.overall_score:
                ratings_list = [cr["rating"] for cr in obj_in["competency_ratings"]]
                review.overall_score = round(sum(ratings_list) / len(ratings_list), 2)

        db.commit()
        db.refresh(review)
        return review


class CRUDFeedback:
    def create(self, db: Session, org_id: UUID, giver_user_id: int, obj_in: Dict[str, Any]) -> Feedback:
        giver_id = None if obj_in.get("is_anonymous") else giver_user_id
        fb = Feedback(
            organization_id=org_id,
            cycle_id=obj_in.get("cycle_id"),
            receiver_user_id=obj_in["receiver_user_id"],
            giver_user_id=giver_id,
            feedback_type=obj_in.get("feedback_type", "peer"),
            is_anonymous=obj_in.get("is_anonymous", False),
            content=obj_in["content"],
            rating=obj_in.get("rating")
        )
        db.add(fb)
        db.commit()
        db.refresh(fb)
        return fb

    def get_feedback_for_user(self, db: Session, org_id: UUID, user_id: int) -> List[Feedback]:
        return db.query(Feedback).filter(
            Feedback.organization_id == org_id,
            Feedback.receiver_user_id == user_id,
            Feedback.is_visible_to_receiver.is_(True)
        ).order_by(Feedback.created_at.desc()).all()


class CRUDRatingEngine:
    def get_or_calculate_final_rating(self, db: Session, org_id: UUID, user_id: int, cycle_id: int) -> PerformanceRating:
        rating = db.query(PerformanceRating).filter(
            PerformanceRating.organization_id == org_id,
            PerformanceRating.user_id == user_id,
            PerformanceRating.cycle_id == cycle_id
        ).first()

        kpi_score = crud_kpi_engine.calculate_weighted_kpi_score(db, user_id, cycle_id)
        goal_score = crud_goal_engine.compute_user_goal_score(db, user_id, cycle_id)

        # Average completed review scores for user
        reviews = db.query(PerformanceReview).filter(
            PerformanceReview.organization_id == org_id,
            PerformanceReview.reviewee_user_id == user_id,
            PerformanceReview.cycle_id == cycle_id,
            PerformanceReview.status == "submitted"
        ).all()
        comp_score = None
        if reviews:
            scores = [float(r.overall_score) for r in reviews if r.overall_score]
            if scores:
                comp_score = round(sum(scores) / len(scores), 2)

        # Combine component scores
        components = [s for s in [kpi_score, goal_score, comp_score] if s is not None]
        final = round(sum(components) / len(components), 2) if components else 3.0

        label = "Meets Expectations"
        if final >= 4.5:
            label = "Exceptional"
        elif final >= 3.8:
            label = "Exceeds Expectations"
        elif final >= 2.8:
            label = "Meets Expectations"
        elif final >= 2.0:
            label = "Needs Improvement"
        else:
            label = "Unsatisfactory"

        if not rating:
            rating = PerformanceRating(
                organization_id=org_id,
                cycle_id=cycle_id,
                user_id=user_id,
                kpi_score=kpi_score,
                goal_score=goal_score,
                competency_score=comp_score,
                final_rating=final,
                rating_label=label
            )
            db.add(rating)
        else:
            rating.kpi_score = kpi_score
            rating.goal_score = goal_score
            rating.competency_score = comp_score
            rating.final_rating = final if not rating.is_calibrated else rating.calibrated_rating
            rating.rating_label = label

        db.commit()
        db.refresh(rating)
        return rating


class CRUDPIP:
    def get_by_id(self, db: Session, pip_id: int) -> Optional[PerformanceImprovementPlan]:
        return db.query(PerformanceImprovementPlan).filter(PerformanceImprovementPlan.id == pip_id).first()

    def create(self, db: Session, org_id: UUID, manager_id: int, obj_in: Dict[str, Any]) -> PerformanceImprovementPlan:
        pip = PerformanceImprovementPlan(
            organization_id=org_id,
            user_id=obj_in["user_id"],
            manager_user_id=manager_id,
            title=obj_in["title"],
            reason=obj_in["reason"],
            objectives=obj_in.get("objectives"),
            milestones=obj_in.get("milestones"),
            start_date=obj_in["start_date"],
            end_date=obj_in["end_date"],
            status="active"
        )
        db.add(pip)
        db.commit()
        db.refresh(pip)
        return pip

    def update(self, db: Session, pip: PerformanceImprovementPlan, updates: Dict[str, Any]) -> PerformanceImprovementPlan:
        for field, val in updates.items():
            if val is not None and hasattr(pip, field):
                setattr(pip, field, val)
        db.commit()
        db.refresh(pip)
        return pip


class CRUDPromotion:
    def get_by_id(self, db: Session, promo_id: int) -> Optional[PromotionRecommendation]:
        return db.query(PromotionRecommendation).filter(PromotionRecommendation.id == promo_id).first()

    def create(self, db: Session, org_id: UUID, recommender_id: int, obj_in: Dict[str, Any]) -> PromotionRecommendation:
        rec = PromotionRecommendation(
            organization_id=org_id,
            user_id=obj_in["user_id"],
            cycle_id=obj_in.get("cycle_id"),
            recommended_by_user_id=recommender_id,
            proposed_role=obj_in.get("proposed_role"),
            proposed_salary_increase_pct=obj_in.get("proposed_salary_increase_pct"),
            readiness_score=obj_in.get("readiness_score"),
            justification=obj_in.get("justification"),
            status="pending"
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec

    def decide(self, db: Session, rec: PromotionRecommendation, decided_by_id: int, status: str, notes: Optional[str] = None) -> PromotionRecommendation:
        rec.status = status
        rec.decided_by_user_id = decided_by_id
        rec.decision_notes = notes
        rec.decided_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(rec)
        return rec


crud_perf_cycle = CRUDPerformanceCycle()
crud_competency = CRUDCompetency()
crud_kpi_engine = CRUDKPIEngine()
crud_goal_engine = CRUDGoalEngine()
crud_review_engine = CRUDReviewEngine()
crud_feedback = CRUDFeedback()
crud_rating_engine = CRUDRatingEngine()
crud_pip = CRUDPIP()
crud_promotion = CRUDPromotion()
