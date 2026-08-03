"""
succession.py — FastAPI Router for Enterprise Succession Planning & Career Pathing Engine
Sprint 4 — Entity 3
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_db, get_current_active_user
from app.db.models.all_models import (
    User, KeyPosition, SuccessionPlan, SuccessorCandidate, NineBoxGrid,
    CareerPath, CareerLevel, IndividualDevelopmentPlan, IDPGoal,
    FlightRiskAssessment, MentorshipPair
)
from app.crud.crud_succession import (
    crud_succession_engine, crud_nine_box_engine, crud_career_engine,
    crud_idp_engine, crud_flight_risk_engine, crud_mentorship_engine
)
from app.schema.succession import (
    KeyPositionCreate, KeyPositionResponse, SuccessionPlanCreate, SuccessionPlanResponse,
    SuccessorCandidateCreate, SuccessorCandidateResponse, NineBoxGridCreate,
    NineBoxGridResponse, CareerPathCreate, CareerPathResponse, IDPCreate, IDPResponse,
    IDPGoalResponse, FlightRiskCreate, FlightRiskResponse, MentorshipPairCreate,
    MentorshipPairResponse, SuccessionAnalyticsResponse
)
from app.db.seed_succession import seed_succession_defaults_for_org

router = APIRouter()


# ── KEY POSITIONS & SUCCESSION PLANS ──
@router.post("/key-positions", response_model=KeyPositionResponse, status_code=status.HTTP_201_CREATED)
def create_key_position(
    payload: KeyPositionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "HR"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    kp = crud_succession_engine.create_key_position(db, current_user.org_id, payload.model_dump())
    return {
        **kp.__dict__,
        "department_name": kp.department.name if kp.department else None,
        "incumbent_name": kp.incumbent.full_name if kp.incumbent else None
    }


@router.get("/key-positions", response_model=List[KeyPositionResponse])
def list_key_positions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    seed_succession_defaults_for_org(db, current_user.org_id, current_user.id)
    positions = crud_succession_engine.get_key_positions(db, current_user.org_id)
    res = []
    for kp in positions:
        res.append({
            **kp.__dict__,
            "department_name": kp.department.name if kp.department else None,
            "incumbent_name": kp.incumbent.full_name if kp.incumbent else None
        })
    return res


@router.get("/plans", response_model=List[SuccessionPlanResponse])
def list_succession_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    seed_succession_defaults_for_org(db, current_user.org_id, current_user.id)
    plans = db.query(SuccessionPlan).filter(SuccessionPlan.organization_id == current_user.org_id).all()
    res = []
    for p in plans:
        cands = []
        for c in p.candidates:
            cands.append({
                **c.__dict__,
                "candidate_name": c.candidate_user.full_name if c.candidate_user else None
            })
        res.append({
            **p.__dict__,
            "key_position_title": p.key_position.title if p.key_position else None,
            "candidates": cands
        })
    return res


@router.post("/plans/{plan_id}/candidates", response_model=SuccessorCandidateResponse, status_code=status.HTTP_201_CREATED)
def nominate_candidate(
    plan_id: int,
    payload: SuccessorCandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "HR", "Manager"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    cand = crud_succession_engine.nominate_successor(db, plan_id, payload.model_dump())
    return {
        **cand.__dict__,
        "candidate_name": cand.candidate_user.full_name if cand.candidate_user else None
    }


# ── 9-BOX TALENT MATRIX ──
@router.post("/nine-box", response_model=NineBoxGridResponse)
def evaluate_nine_box(
    payload: NineBoxGridCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "HR", "Manager"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    grid = crud_nine_box_engine.evaluate_employee(
        db, current_user.org_id, payload.user_id, payload.performance_rating,
        payload.potential_rating, evaluator_id=current_user.id, cycle_id=payload.cycle_id
    )
    return {
        **grid.__dict__,
        "user_name": grid.user.full_name if grid.user else None
    }


@router.get("/nine-box", response_model=List[NineBoxGridResponse])
def get_nine_box_grid(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    evals = crud_nine_box_engine.get_matrix_evaluations(db, current_user.org_id)
    res = []
    for g in evals:
        res.append({
            **g.__dict__,
            "user_name": g.user.full_name if g.user else None
        })
    return res


# ── CAREER PATHS & LEVELS ──
@router.post("/career-paths", response_model=CareerPathResponse, status_code=status.HTTP_201_CREATED)
def create_career_path(
    payload: CareerPathCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "HR"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    cp = crud_career_engine.create_career_path(db, current_user.org_id, payload.model_dump())
    return {
        **cp.__dict__,
        "department_name": cp.department.name if cp.department else None,
        "levels": [l.__dict__ for l in cp.levels]
    }


@router.get("/career-paths", response_model=List[CareerPathResponse])
def list_career_paths(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    seed_succession_defaults_for_org(db, current_user.org_id, current_user.id)
    paths = crud_career_engine.get_career_paths(db, current_user.org_id)
    res = []
    for cp in paths:
        res.append({
            **cp.__dict__,
            "department_name": cp.department.name if cp.department else None,
            "levels": [l.__dict__ for l in cp.levels]
        })
    return res


# ── INDIVIDUAL DEVELOPMENT PLANS (IDP) ──
@router.post("/idp", response_model=IDPResponse, status_code=status.HTTP_201_CREATED)
def create_idp(
    payload: IDPCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    target_user_id = payload.user_id or current_user.id
    idp = crud_idp_engine.create_idp(db, current_user.org_id, target_user_id, payload.model_dump())
    return {
        **idp.__dict__,
        "user_name": idp.user.full_name if idp.user else None,
        "goals": [g.__dict__ for g in idp.goals]
    }


@router.get("/idp", response_model=List[IDPResponse])
def list_idps(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    target_user_id = user_id
    if target_user_id is None and current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "HR"]:
        target_user_id = current_user.id

    q = db.query(IndividualDevelopmentPlan).filter(IndividualDevelopmentPlan.organization_id == current_user.org_id)
    if target_user_id:
        q = q.filter(IndividualDevelopmentPlan.user_id == target_user_id)

    idps = q.all()
    res = []
    for idp in idps:
        res.append({
            **idp.__dict__,
            "user_name": idp.user.full_name if idp.user else None,
            "goals": [g.__dict__ for g in idp.goals]
        })
    return res


# ── FLIGHT RISK ASSESSMENTS ──
@router.post("/flight-risk", response_model=FlightRiskResponse, status_code=status.HTTP_201_CREATED)
def assess_flight_risk(
    payload: FlightRiskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "HR", "Manager"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    risk = crud_flight_risk_engine.assess_flight_risk(
        db, current_user.org_id, payload.user_id, payload.risk_score,
        payload.risk_factors, payload.retention_strategy, assessor_id=current_user.id
    )
    return {
        **risk.__dict__,
        "user_name": risk.user.full_name if risk.user else None
    }


@router.get("/flight-risk", response_model=List[FlightRiskResponse])
def list_flight_risks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    risks = db.query(FlightRiskAssessment).filter(FlightRiskAssessment.organization_id == current_user.org_id).all()
    res = []
    for r in risks:
        res.append({
            **r.__dict__,
            "user_name": r.user.full_name if r.user else None
        })
    return res


# ── MENTORSHIP PAIRS ──
@router.post("/mentorship", response_model=MentorshipPairResponse, status_code=status.HTTP_201_CREATED)
def create_mentorship_pair(
    payload: MentorshipPairCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "HR", "Manager"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    pair = crud_mentorship_engine.create_pair(db, current_user.org_id, payload.mentor_user_id, payload.mentee_user_id, payload.focus_areas)
    return {
        **pair.__dict__,
        "mentor_name": pair.mentor.full_name if pair.mentor else None,
        "mentee_name": pair.mentee.full_name if pair.mentee else None
    }


@router.get("/mentorship", response_model=List[MentorshipPairResponse])
def list_mentorship_pairs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    pairs = db.query(MentorshipPair).filter(MentorshipPair.organization_id == current_user.org_id).all()
    res = []
    for p in pairs:
        res.append({
            **p.__dict__,
            "mentor_name": p.mentor.full_name if p.mentor else None,
            "mentee_name": p.mentee.full_name if p.mentee else None
        })
    return res


# ── ANALYTICS ──
@router.get("/analytics/dashboard", response_model=SuccessionAnalyticsResponse)
def get_succession_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    org_id = current_user.org_id
    kp_count = db.query(KeyPosition).filter(KeyPosition.organization_id == org_id).count()

    plans_with_ready_candidates = db.query(SuccessionPlan).join(SuccessorCandidate).filter(
        SuccessionPlan.organization_id == org_id,
        SuccessorCandidate.readiness_rating == "ready_now"
    ).distinct().count()

    readiness_pct = round((plans_with_ready_candidates / max(1, kp_count)) * 100, 1)

    stars_count = db.query(NineBoxGrid).filter(
        NineBoxGrid.organization_id == org_id,
        NineBoxGrid.performance_rating == 3,
        NineBoxGrid.potential_rating == 3
    ).count()

    idps_count = db.query(IndividualDevelopmentPlan).filter(
        IndividualDevelopmentPlan.organization_id == org_id,
        IndividualDevelopmentPlan.status == "in_progress"
    ).count()

    high_risk_count = db.query(FlightRiskAssessment).filter(
        FlightRiskAssessment.organization_id == org_id,
        FlightRiskAssessment.risk_score.in_(["high", "critical"])
    ).count()

    active_mentorships = db.query(MentorshipPair).filter(
        MentorshipPair.organization_id == org_id,
        MentorshipPair.status == "active"
    ).count()

    grids = db.query(NineBoxGrid).filter(NineBoxGrid.organization_id == org_id).all()
    dist: Dict[str, int] = {}
    for g in grids:
        dist[g.box_category] = dist.get(g.box_category, 0) + 1

    return SuccessionAnalyticsResponse(
        critical_positions_count=kp_count,
        succession_readiness_pct=readiness_pct,
        nine_box_stars_count=stars_count,
        active_idps_count=idps_count,
        high_flight_risk_count=high_risk_count,
        active_mentorships_count=active_mentorships,
        nine_box_distribution=dist
    )
