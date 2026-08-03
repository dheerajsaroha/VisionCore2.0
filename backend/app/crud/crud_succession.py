"""
crud_succession.py — CRUD & Engines for Succession Planning & Career Pathing Engine
Sprint 4 — Entity 3
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models.all_models import (
    KeyPosition, SuccessionPlan, SuccessorCandidate, NineBoxGrid, CareerPath,
    CareerLevel, IndividualDevelopmentPlan, IDPGoal, FlightRiskAssessment,
    MentorshipPair, User, Department
)

NINE_BOX_MATRIX = {
    (3, 3): "Star (High Perf / High Pot)",
    (3, 2): "High Professional",
    (3, 1): "Solid Professional",
    (2, 3): "High Potential",
    (2, 2): "Core Player",
    (2, 1): "Effective Performer",
    (1, 3): "Enigma / Question Mark",
    (1, 2): "Dilemma / Misaligned",
    (1, 1): "Underperformer / Risk"
}


class CRUDSuccessionEngine:
    def create_key_position(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> KeyPosition:
        kp = KeyPosition(
            organization_id=org_id,
            title=obj_in["title"],
            department_id=obj_in.get("department_id"),
            criticality_level=obj_in.get("criticality_level", "critical"),
            current_incumbent_user_id=obj_in.get("current_incumbent_user_id"),
            vacancy_risk_level=obj_in.get("vacancy_risk_level", "low"),
            impact_rating=obj_in.get("impact_rating", 4.0)
        )
        db.add(kp)
        db.commit()
        db.refresh(kp)

        # Create empty succession plan container
        plan = SuccessionPlan(organization_id=org_id, key_position_id=kp.id, target_fill_timeline_months=6, status="active")
        db.add(plan)
        db.commit()

        return kp

    def get_key_positions(self, db: Session, org_id: UUID) -> List[KeyPosition]:
        return db.query(KeyPosition).filter(KeyPosition.organization_id == org_id).all()

    def nominate_successor(self, db: Session, plan_id: int, obj_in: Dict[str, Any]) -> SuccessorCandidate:
        candidate = SuccessorCandidate(
            succession_plan_id=plan_id,
            candidate_user_id=obj_in["candidate_user_id"],
            readiness_rating=obj_in.get("readiness_rating", "ready_1_year"),
            emergency_backup=obj_in.get("emergency_backup", False),
            nomination_notes=obj_in.get("nomination_notes"),
            status="nominated"
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        return candidate


class CRUDNineBoxEngine:
    def evaluate_employee(self, db: Session, org_id: UUID, user_id: int, perf: int, pot: int, evaluator_id: Optional[int] = None, cycle_id: Optional[int] = None) -> NineBoxGrid:
        box_cat = NINE_BOX_MATRIX.get((perf, pot), "Core Player")

        grid = db.query(NineBoxGrid).filter(
            NineBoxGrid.organization_id == org_id,
            NineBoxGrid.user_id == user_id,
            NineBoxGrid.cycle_id == cycle_id
        ).first()

        if not grid:
            grid = NineBoxGrid(
                organization_id=org_id,
                user_id=user_id,
                cycle_id=cycle_id,
                performance_rating=perf,
                potential_rating=pot,
                box_category=box_cat,
                evaluated_by_user_id=evaluator_id
            )
            db.add(grid)
        else:
            grid.performance_rating = perf
            grid.potential_rating = pot
            grid.box_category = box_cat
            grid.evaluated_by_user_id = evaluator_id

        db.commit()
        db.refresh(grid)
        return grid

    def get_matrix_evaluations(self, db: Session, org_id: UUID) -> List[NineBoxGrid]:
        return db.query(NineBoxGrid).filter(NineBoxGrid.organization_id == org_id).all()


class CRUDCareerEngine:
    def create_career_path(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> CareerPath:
        cp = CareerPath(
            organization_id=org_id,
            title=obj_in["title"],
            department_id=obj_in.get("department_id"),
            description=obj_in.get("description"),
            total_levels=len(obj_in.get("levels") or [1, 2, 3, 4, 5])
        )
        db.add(cp)
        db.commit()
        db.refresh(cp)

        if obj_in.get("levels"):
            for lvl in obj_in["levels"]:
                cl = CareerLevel(
                    career_path_id=cp.id,
                    level_number=lvl["level_number"],
                    level_title=lvl["level_title"],
                    min_experience_years=lvl.get("min_experience_years", 1.0),
                    required_skills=lvl.get("required_skills"),
                    target_salary_min=lvl.get("target_salary_min", 0.0),
                    target_salary_max=lvl.get("target_salary_max", 0.0)
                )
                db.add(cl)
            db.commit()

        return cp

    def get_career_paths(self, db: Session, org_id: UUID) -> List[CareerPath]:
        return db.query(CareerPath).filter(CareerPath.organization_id == org_id).all()


class CRUDIDPEngine:
    def create_idp(self, db: Session, org_id: UUID, user_id: int, obj_in: Dict[str, Any]) -> IndividualDevelopmentPlan:
        idp = IndividualDevelopmentPlan(
            organization_id=org_id,
            user_id=user_id,
            target_career_level_id=obj_in.get("target_career_level_id"),
            target_position_title=obj_in.get("target_position_title"),
            status="in_progress",
            target_completion_date=obj_in.get("target_completion_date")
        )
        db.add(idp)
        db.commit()
        db.refresh(idp)

        if obj_in.get("goals"):
            for g in obj_in["goals"]:
                goal = IDPGoal(
                    idp_id=idp.id,
                    title=g["title"],
                    goal_type=g.get("goal_type", "skill_acquisition"),
                    target_date=g.get("target_date"),
                    status="pending",
                    completion_pct=0.0
                )
                db.add(goal)
            db.commit()

        return idp

    def update_idp_goal_progress(self, db: Session, goal_id: int, completion_pct: float, status: str) -> IDPGoal:
        goal = db.query(IDPGoal).filter(IDPGoal.id == goal_id).first()
        if goal:
            goal.completion_pct = completion_pct
            goal.status = status
            db.commit()
            db.refresh(goal)
        return goal


class CRUDFlightRiskEngine:
    def assess_flight_risk(self, db: Session, org_id: UUID, user_id: int, risk_score: str, risk_factors: Optional[Dict[str, Any]] = None, strategy: Optional[str] = None, assessor_id: Optional[int] = None) -> FlightRiskAssessment:
        assessment = FlightRiskAssessment(
            organization_id=org_id,
            user_id=user_id,
            risk_score=risk_score,
            risk_factors=risk_factors,
            retention_strategy=strategy,
            assessed_by_user_id=assessor_id,
            assessed_at=datetime.now(timezone.utc)
        )
        db.add(assessment)
        db.commit()
        db.refresh(assessment)
        return assessment


class CRUDMentorshipEngine:
    def create_pair(self, db: Session, org_id: UUID, mentor_id: int, mentee_id: int, focus_areas: Optional[str] = None) -> MentorshipPair:
        pair = MentorshipPair(
            organization_id=org_id,
            mentor_user_id=mentor_id,
            mentee_user_id=mentee_id,
            status="active",
            focus_areas=focus_areas
        )
        db.add(pair)
        db.commit()
        db.refresh(pair)
        return pair


crud_succession_engine = CRUDSuccessionEngine()
crud_nine_box_engine = CRUDNineBoxEngine()
crud_career_engine = CRUDCareerEngine()
crud_idp_engine = CRUDIDPEngine()
crud_flight_risk_engine = CRUDFlightRiskEngine()
crud_mentorship_engine = CRUDMentorshipEngine()
