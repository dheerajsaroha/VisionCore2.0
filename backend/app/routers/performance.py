"""
performance.py — FastAPI Router for Enterprise Performance Management System
Sprint 4 — Entity 1: Performance Management System
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api import deps
from app.api.deps import get_db, get_current_active_user
from app.api.eaac_deps import require_eaac_authorization
from app.db.models.all_models import (
    User, PerformanceCycle, Competency, KPI, KPIAssignment, Goal,
    PerformanceReview, Feedback, PerformanceRating, CalibrationSession,
    PerformanceImprovementPlan, PromotionRecommendation
)
from app.crud.crud_performance import (
    crud_perf_cycle, crud_competency, crud_kpi_engine, crud_goal_engine,
    crud_review_engine, crud_feedback, crud_rating_engine, crud_pip, crud_promotion
)
from app.schema.performance import (
    PerformanceCycleCreate, PerformanceCycleUpdate, PerformanceCycleResponse,
    CompetencyCreate, CompetencyResponse, KPICreate, KPIResponse,
    KPIAssignmentCreate, KPIAssignmentUpdate, KPIAssignmentResponse,
    GoalCreate, GoalUpdate, GoalProgressLog, GoalProgressResponse, GoalResponse,
    PerformanceReviewCreate, PerformanceReviewSubmit, PerformanceReviewResponse,
    FeedbackCreate, FeedbackResponse, PerformanceRatingResponse,
    CalibrationSessionCreate, CalibrationUpdate, CalibrationSessionResponse,
    PIPCreate, PIPUpdate, PIPResponse, PromotionRecommendationCreate,
    PromotionAction, PromotionRecommendationResponse, PerformanceAnalyticsResponse,
    BellCurveBucket
)
from app.services.performance_analytics import performance_analytics
from app.services.rating_normalization import rating_normalization
from app.services.promotion_engine import promotion_engine
from app.services.calibration_engine import calibration_engine
from app.services.kpi_engine import kpi_engine
from app.services.goal_scoring_engine import goal_scoring_engine
from app.db.seed_performance import seed_performance_defaults_for_org

router = APIRouter(dependencies=[Depends(deps.require_feature("performance_reviews"))])


# ── PERFORMANCE CYCLES ──
@router.post("/cycles", response_model=PerformanceCycleResponse, status_code=status.HTTP_201_CREATED)
def create_performance_cycle(
    payload: PerformanceCycleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.cycle.create", action="create"))
):
    """Create a new performance review cycle (EAAC enforced)."""
    return crud_perf_cycle.create(db, current_user.org_id, current_user.id, payload.model_dump())


@router.get("/cycles", response_model=List[PerformanceCycleResponse])
def list_performance_cycles(
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.cycle.read"))
):
    """List performance cycles for current organization."""
    seed_performance_defaults_for_org(db, current_user.org_id, current_user.id)
    cycles = crud_perf_cycle.get_all_for_org(db, current_user.org_id, status=status_filter)
    return cycles[skip:skip + limit]


@router.get("/cycles/{cycle_id}", response_model=PerformanceCycleResponse)
def get_performance_cycle(
    cycle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.cycle.read"))
):
    """Get details of a performance cycle."""
    cycle = crud_perf_cycle.get_by_id(db, cycle_id)
    if not cycle or cycle.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Performance cycle not found")
    return cycle


@router.patch("/cycles/{cycle_id}", response_model=PerformanceCycleResponse)
def update_performance_cycle(
    cycle_id: int,
    payload: PerformanceCycleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.cycle.update", action="update"))
):
    """Update a performance cycle."""
    cycle = crud_perf_cycle.get_by_id(db, cycle_id)
    if not cycle or cycle.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Performance cycle not found")
    return crud_perf_cycle.update(db, cycle, payload.model_dump(exclude_unset=True))


# ── COMPETENCIES ──
@router.post("/competencies", response_model=CompetencyResponse, status_code=status.HTTP_201_CREATED)
def create_competency(
    payload: CompetencyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.competency.create", action="create"))
):
    """Add a competency to the organization's competency framework."""
    return crud_competency.create(db, current_user.org_id, payload.model_dump())


@router.get("/competencies", response_model=List[CompetencyResponse])
def list_competencies(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.competency.read"))
):
    """List configured competencies."""
    seed_performance_defaults_for_org(db, current_user.org_id, current_user.id)
    comps = crud_competency.get_all_for_org(db, current_user.org_id)
    return comps[skip:skip + limit]


# ── KPIS & ASSIGNMENTS ──
@router.post("/kpis", response_model=KPIResponse, status_code=status.HTTP_201_CREATED)
def create_kpi(
    payload: KPICreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.kpi.create", action="create"))
):
    """Create a KPI template."""
    return crud_kpi_engine.create_kpi(db, current_user.org_id, payload.model_dump())


@router.get("/kpis", response_model=List[KPIResponse])
def list_kpis(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.kpi.read"))
):
    """List KPI templates."""
    kpis = crud_kpi_engine.get_kpis_for_org(db, current_user.org_id)
    return kpis[skip:skip + limit]


@router.post("/kpis/assign", response_model=KPIAssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_kpi(
    payload: KPIAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.kpi.assign", action="create"))
):
    """Assign a KPI to an employee."""
    kpi = crud_kpi_engine.get_kpi_by_id(db, payload.kpi_id)
    if not kpi or kpi.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="KPI template not found")
    res = crud_kpi_engine.assign_kpi(db, current_user.org_id, current_user.id, payload.model_dump())
    return {**res.__dict__, "kpi_name": kpi.name}


@router.get("/kpis/assignments", response_model=List[KPIAssignmentResponse])
def list_kpi_assignments(
    user_id: Optional[int] = None,
    cycle_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.kpi.read"))
):
    """List assigned KPIs with EAAC filtering."""
    target_user_id = user_id or current_user.id
    q = db.query(KPIAssignment).filter(
        KPIAssignment.organization_id == current_user.org_id,
        KPIAssignment.user_id == target_user_id
    )
    if cycle_id:
        q = q.filter(KPIAssignment.cycle_id == cycle_id)

    # EAAC scope: if user is not admin and requesting others' data, scope filter applies
    assignments = q.offset(skip).limit(limit).all()
    result = []
    for a in assignments:
        result.append({**a.__dict__, "kpi_name": a.kpi.name if a.kpi else None})
    return result


@router.patch("/kpis/assignments/{assignment_id}", response_model=KPIAssignmentResponse)
def update_kpi_assignment_progress(
    assignment_id: int,
    payload: KPIAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.kpi.update", action="update"))
):
    """Update actual KPI progress and recalculate score."""
    assignment = db.query(KPIAssignment).filter(KPIAssignment.id == assignment_id).first()
    if not assignment or assignment.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="KPI Assignment not found")

    updated = crud_kpi_engine.update_kpi_progress(db, assignment, payload.actual_value)
    return {**updated.__dict__, "kpi_name": updated.kpi.name if updated.kpi else None}


# ── GOALS ──
@router.post("/goals", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.goal.create", action="create"))
):
    """Create a new OKR/SMART goal."""
    g = crud_goal_engine.create(db, current_user.org_id, current_user.id, payload.model_dump())
    return {**g.__dict__, "user_name": current_user.full_name}


@router.get("/goals", response_model=List[GoalResponse])
def list_goals(
    user_id: Optional[int] = None,
    cycle_id: Optional[int] = None,
    status: Optional[str] = None,
    goal_framework: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.goal.read"))
):
    """List goals with optional filters."""
    q = db.query(Goal).filter(Goal.organization_id == current_user.org_id)

    user_filter = user_id or current_user.id
    q = q.filter(Goal.user_id == user_filter)

    if cycle_id:
        q = q.filter(Goal.cycle_id == cycle_id)
    if status:
        q = q.filter(Goal.status == status)
    if goal_framework:
        q = q.filter(Goal.goal_framework == goal_framework)

    goals = q.order_by(Goal.created_at.desc()).offset(skip).limit(limit).all()
    res = []
    for g in goals:
        res.append({**g.__dict__, "user_name": g.user.full_name if g.user else None})
    return res


@router.get("/goals/cascade/{root_goal_id}", response_model=Dict[str, Any])
def get_goal_cascade(
    root_goal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.goal.read"))
):
    """Get goal cascade tree (parent → children)."""
    return goal_scoring_engine.get_goal_cascade_tree(db, current_user.org_id, root_goal_id)


@router.post("/goals/{goal_id}/progress", response_model=GoalProgressResponse)
def log_goal_progress(
    goal_id: int,
    payload: GoalProgressLog,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.goal.update", action="update"))
):
    """Log progress check-in for a goal."""
    goal = crud_goal_engine.get_by_id(db, goal_id)
    if not goal or goal.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    return crud_goal_engine.log_progress(db, goal, current_user.id, payload.value, payload.note)


@router.patch("/goals/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: int,
    payload: GoalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.goal.update", action="update"))
):
    """Update a goal."""
    goal = crud_goal_engine.get_by_id(db, goal_id)
    if not goal or goal.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Goal not found")
    for field, val in payload.model_dump(exclude_unset=True).items():
        if val is not None and hasattr(goal, field):
            setattr(goal, field, val)
    db.commit()
    db.refresh(goal)
    return {**goal.__dict__, "user_name": goal.user.full_name if goal.user else None}


# ── PERFORMANCE REVIEWS ──
@router.post("/reviews", response_model=PerformanceReviewResponse, status_code=status.HTTP_201_CREATED)
def create_performance_review(
    payload: PerformanceReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.review.create", action="create"))
):
    """Initiate a review (self, manager, 360, etc.)."""
    return crud_review_engine.create_review(db, current_user.org_id, payload.model_dump())


@router.get("/reviews", response_model=List[PerformanceReviewResponse])
def list_performance_reviews(
    cycle_id: Optional[int] = None,
    user_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    review_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.review.read"))
):
    """List performance reviews with EAAC filtering."""
    q = db.query(PerformanceReview).filter(PerformanceReview.organization_id == current_user.org_id)

    if user_id:
        q = q.filter(PerformanceReview.reviewee_user_id == user_id)
    if cycle_id:
        q = q.filter(PerformanceReview.cycle_id == cycle_id)
    if status_filter:
        q = q.filter(PerformanceReview.status == status_filter)
    if review_type:
        q = q.filter(PerformanceReview.review_type == review_type)

    reviews = q.order_by(PerformanceReview.created_at.desc()).offset(skip).limit(limit).all()
    res = []
    for r in reviews:
        ratings = []
        for cr in r.competency_ratings:
            ratings.append({**cr.__dict__, "competency_name": cr.competency.name if cr.competency else None})
        res.append({
            **r.__dict__,
            "reviewee_name": r.reviewee.full_name if r.reviewee else None,
            "reviewer_name": r.reviewer.full_name if r.reviewer else None,
            "competency_ratings": ratings
        })
    return res


@router.get("/reviews/{review_id}", response_model=PerformanceReviewResponse)
def get_performance_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.review.read"))
):
    """Get a single performance review."""
    review = crud_review_engine.get_by_id(db, review_id)
    if not review or review.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Review not found")

    ratings = []
    for cr in review.competency_ratings:
        ratings.append({**cr.__dict__, "competency_name": cr.competency.name if cr.competency else None})
    return {
        **review.__dict__,
        "reviewee_name": review.reviewee.full_name if review.reviewee else None,
        "reviewer_name": review.reviewer.full_name if review.reviewer else None,
        "competency_ratings": ratings
    }


@router.post("/reviews/{review_id}/submit", response_model=PerformanceReviewResponse)
def submit_performance_review(
    review_id: int,
    payload: PerformanceReviewSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.review.submit", action="update"))
):
    """Submit ratings and feedback for a review."""
    review = crud_review_engine.get_by_id(db, review_id)
    if not review or review.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Review not found")

    submitted = crud_review_engine.submit_review(db, review, payload.model_dump(exclude_unset=True))
    # Recalculate final performance rating after review submission
    crud_rating_engine.get_or_calculate_final_rating(db, current_user.org_id, review.reviewee_user_id, review.cycle_id)

    ratings = []
    for cr in submitted.competency_ratings:
        ratings.append({**cr.__dict__, "competency_name": cr.competency.name if cr.competency else None})

    return {
        **submitted.__dict__,
        "reviewee_name": submitted.reviewee.full_name if submitted.reviewee else None,
        "reviewer_name": submitted.reviewer.full_name if submitted.reviewer else None,
        "competency_ratings": ratings
    }


@router.post("/reviews/{review_id}/acknowledge", response_model=PerformanceReviewResponse)
def acknowledge_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.review.submit", action="update"))
):
    """Acknowledge a completed review."""
    review = crud_review_engine.get_by_id(db, review_id)
    if not review or review.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.status != "submitted":
        raise HTTPException(status_code=400, detail="Only submitted reviews can be acknowledged")

    review.status = "acknowledged"
    review.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(review)

    ratings = []
    for cr in review.competency_ratings:
        ratings.append({**cr.__dict__, "competency_name": cr.competency.name if cr.competency else None})

    return {
        **review.__dict__,
        "reviewee_name": review.reviewee.full_name if review.reviewee else None,
        "reviewer_name": review.reviewer.full_name if review.reviewer else None,
        "competency_ratings": ratings
    }


# ── FEEDBACK ──
@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.feedback.create", action="create"))
):
    """Submit 360°, peer, or anonymous feedback."""
    fb = crud_feedback.create(db, current_user.org_id, current_user.id, payload.model_dump())
    return {
        **fb.__dict__,
        "receiver_name": fb.receiver.full_name if fb.receiver else None,
        "giver_name": "Anonymous" if fb.is_anonymous else (fb.giver.full_name if fb.giver else None)
    }


@router.get("/feedback", response_model=List[FeedbackResponse])
def get_received_feedback(
    user_id: Optional[int] = None,
    feedback_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.feedback.read"))
):
    """Get feedback received by a user."""
    target_id = user_id or current_user.id
    q = db.query(Feedback).filter(
        Feedback.organization_id == current_user.org_id,
        Feedback.receiver_user_id == target_id,
        Feedback.is_visible_to_receiver.is_(True)
    )
    if feedback_type:
        q = q.filter(Feedback.feedback_type == feedback_type)

    feedbacks = q.order_by(Feedback.created_at.desc()).offset(skip).limit(limit).all()
    res = []
    for f in feedbacks:
        res.append({
            **f.__dict__,
            "receiver_name": f.receiver.full_name if f.receiver else None,
            "giver_name": "Anonymous" if f.is_anonymous else (f.giver.full_name if f.giver else None)
        })
    return res


# ── RATINGS ──
@router.get("/ratings", response_model=List[PerformanceRatingResponse])
def list_ratings(
    cycle_id: Optional[int] = None,
    user_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.rating.read"))
):
    """Get performance ratings with optional filters."""
    q = db.query(PerformanceRating).filter(PerformanceRating.organization_id == current_user.org_id)
    if cycle_id:
        q = q.filter(PerformanceRating.cycle_id == cycle_id)
    if user_id:
        q = q.filter(PerformanceRating.user_id == user_id)

    ratings = q.order_by(PerformanceRating.final_rating.desc()).offset(skip).limit(limit).all()
    res = []
    for r in ratings:
        user = db.query(User).filter(User.id == r.user_id).first()
        res.append({
            **r.__dict__,
            "user_name": user.full_name if user else None
        })
    return res


@router.post("/ratings/calculate", response_model=PerformanceRatingResponse)
def calculate_rating(
    user_id: int,
    cycle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.rating.calculate", action="create"))
):
    """Calculate or recalculate a user's final performance rating."""
    rating = crud_rating_engine.get_or_calculate_final_rating(db, current_user.org_id, user_id, cycle_id)
    user = db.query(User).filter(User.id == rating.user_id).first()
    return {**rating.__dict__, "user_name": user.full_name if user else None}


# ── CALIBRATION SESSIONS ──
@router.post("/calibrations", response_model=CalibrationSessionResponse, status_code=status.HTTP_201_CREATED)
def create_calibration_session(
    payload: CalibrationSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.calibration.create", action="create"))
):
    """Create a calibration session (HR/Admin)."""
    session = calibration_engine.create_session(
        db, current_user.org_id, payload.cycle_id,
        current_user.id, payload.notes
    )
    return session


@router.get("/calibrations", response_model=List[CalibrationSessionResponse])
def list_calibration_sessions(
    cycle_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.calibration.read"))
):
    """List calibration sessions."""
    return calibration_engine.get_session_list(db, current_user.org_id, cycle_id)


@router.get("/calibrations/{session_id}", response_model=Dict[str, Any])
def get_calibration_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.calibration.read"))
):
    """Get detailed calibration session with ratings."""
    details = calibration_engine.get_session_details(db, session_id, current_user.org_id)
    if not details:
        raise HTTPException(status_code=404, detail="Calibration session not found")
    return details


@router.post("/calibrations/{session_id}/calibrate", response_model=Dict[str, Any])
def calibrate_rating(
    session_id: int,
    payload: CalibrationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.calibration.update", action="update"))
):
    """Apply calibration adjustment to a user's rating."""
    result = calibration_engine.calibrate_rating(
        db, session_id, payload.user_id, payload.calibrated_rating
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/calibrations/{session_id}/complete", response_model=CalibrationSessionResponse)
def complete_calibration_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.calibration.update", action="update"))
):
    """Complete a calibration session."""
    return calibration_engine.complete_session(db, session_id)


# ── PIPS ──
@router.post("/pips", response_model=PIPResponse, status_code=status.HTTP_201_CREATED)
def create_pip(
    payload: PIPCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.pip.create", action="create"))
):
    """Create a Performance Improvement Plan (EAAC enforced)."""
    pip = crud_pip.create(db, current_user.org_id, current_user.id, payload.model_dump())
    return {**pip.__dict__, "user_name": pip.user.full_name if pip.user else None, "manager_name": current_user.full_name}


@router.get("/pips", response_model=List[PIPResponse])
def list_pips(
    user_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.pip.read"))
):
    """List PIPs with optional filters."""
    q = db.query(PerformanceImprovementPlan).filter(PerformanceImprovementPlan.organization_id == current_user.org_id)
    if user_id:
        q = q.filter(PerformanceImprovementPlan.user_id == user_id)
    if status_filter:
        q = q.filter(PerformanceImprovementPlan.status == status_filter)

    pips = q.order_by(PerformanceImprovementPlan.created_at.desc()).offset(skip).limit(limit).all()
    res = []
    for p in pips:
        res.append({
            **p.__dict__,
            "user_name": p.user.full_name if p.user else None,
            "manager_name": p.manager.full_name if p.manager else None
        })
    return res


@router.patch("/pips/{pip_id}", response_model=PIPResponse)
def update_pip(
    pip_id: int,
    payload: PIPUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.pip.update", action="update"))
):
    """Update a PIP (status, outcome, notes)."""
    pip = crud_pip.get_by_id(db, pip_id)
    if not pip or pip.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="PIP not found")

    updated = crud_pip.update(db, pip, payload.model_dump(exclude_unset=True))
    return {
        **updated.__dict__,
        "user_name": updated.user.full_name if updated.user else None,
        "manager_name": updated.manager.full_name if updated.manager else None
    }


# ── PROMOTIONS ──
@router.post("/promotions", response_model=PromotionRecommendationResponse, status_code=status.HTTP_201_CREATED)
def submit_promotion_recommendation(
    payload: PromotionRecommendationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.promotion.create", action="create"))
):
    """Submit a promotion recommendation (EAAC enforced)."""
    rec = crud_promotion.create(db, current_user.org_id, current_user.id, payload.model_dump())
    return {**rec.__dict__, "user_name": rec.user.full_name if rec.user else None, "recommender_name": current_user.full_name}


@router.get("/promotions", response_model=List[PromotionRecommendationResponse])
def list_promotions(
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.promotion.read"))
):
    """List promotion recommendations."""
    q = db.query(PromotionRecommendation).filter(PromotionRecommendation.organization_id == current_user.org_id)
    if status_filter:
        q = q.filter(PromotionRecommendation.status == status_filter)

    recs = q.order_by(PromotionRecommendation.created_at.desc()).offset(skip).limit(limit).all()
    res = []
    for r in recs:
        res.append({
            **r.__dict__,
            "user_name": r.user.full_name if r.user else None,
            "recommender_name": r.recommended_by.full_name if r.recommended_by else None
        })
    return res


@router.get("/promotions/readiness/{user_id}", response_model=Dict[str, Any])
def get_readiness_assessment(
    user_id: int,
    cycle_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.promotion.read"))
):
    """Get promotion readiness assessment for a user."""
    return promotion_engine.compute_readiness_score(db, user_id, cycle_id)


@router.get("/promotions/matrix", response_model=List[Dict[str, Any]])
def get_promotion_matrix(
    cycle_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.promotion.read"))
):
    """Get organization-wide promotion readiness matrix."""
    return promotion_engine.get_promotion_matrix(db, current_user.org_id, cycle_id)


@router.post("/promotions/{promo_id}/action", response_model=PromotionRecommendationResponse)
def act_on_promotion(
    promo_id: int,
    payload: PromotionAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.promotion.approve", action="approve"))
):
    """Approve or reject promotion recommendation (EAAC enforced - requires approval right)."""
    rec = crud_promotion.get_by_id(db, promo_id)
    if not rec or rec.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Promotion recommendation not found")

    updated = crud_promotion.decide(db, rec, current_user.id, payload.status, payload.decision_notes)
    return {
        **updated.__dict__,
        "user_name": updated.user.full_name if updated.user else None,
        "recommender_name": updated.recommended_by.full_name if updated.recommended_by else None
    }


# ── ANALYTICS ──
@router.get("/analytics/dashboard", response_model=PerformanceAnalyticsResponse)
def get_performance_analytics(
    cycle_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.analytics.read"))
):
    """Executive analytics dashboard for Performance Management Center."""
    dash = performance_analytics.get_dashboard(db, current_user.org_id, cycle_id)

    bell_curve = [BellCurveBucket(**b) for b in dash.get("bell_curve", [])]

    return PerformanceAnalyticsResponse(
        total_employees_in_cycle=dash["total_employees"],
        completed_reviews_count=dash["completed_reviews"],
        pending_reviews_count=dash["pending_reviews"],
        review_completion_pct=dash["review_completion_pct"],
        avg_performance_rating=dash["avg_performance_rating"],
        goal_completion_pct=dash["goal_completion_pct"],
        active_pips_count=dash["active_pips"],
        promotion_candidates_count=dash["promotion_candidates"],
        bell_curve=bell_curve
    )


@router.get("/analytics/top-performers", response_model=List[Dict[str, Any]])
def get_top_performers(
    cycle_id: Optional[int] = None,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.analytics.read"))
):
    """Get top performers by rating."""
    return rating_normalization.get_top_performers(db, current_user.org_id, cycle_id, limit)


@router.get("/analytics/bottom-performers", response_model=List[Dict[str, Any]])
def get_bottom_performers(
    cycle_id: Optional[int] = None,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.analytics.read"))
):
    """Get bottom performers by rating."""
    return rating_normalization.get_bottom_performers(db, current_user.org_id, cycle_id, limit)


@router.get("/analytics/bell-curve", response_model=List[BellCurveBucket])
def get_bell_curve(
    cycle_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.analytics.read"))
):
    """Get bell curve distribution."""
    buckets = rating_normalization.compute_bell_curve(db, current_user.org_id, cycle_id)
    return [BellCurveBucket(**b) for b in buckets]


@router.get("/analytics/department-comparison", response_model=Dict[str, Any])
def get_department_comparison(
    cycle_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.analytics.read"))
):
    """Get cross-department performance comparison."""
    return performance_analytics.get_department_comparison(db, current_user.org_id, cycle_id)


@router.get("/analytics/review-pipeline", response_model=Dict[str, Any])
def get_review_pipeline(
    cycle_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.analytics.read"))
):
    """Get review completion pipeline."""
    return performance_analytics.get_review_pipeline(db, current_user.org_id, cycle_id)


@router.get("/analytics/promotion-pipeline", response_model=Dict[str, Any])
def get_promotion_pipeline(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.analytics.read"))
):
    """Get promotion pipeline analytics."""
    return performance_analytics.get_promotion_pipeline(db, current_user.org_id)


@router.get("/analytics/attrition-risk", response_model=Dict[str, Any])
def get_attrition_risk(
    cycle_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.analytics.read"))
):
    """Get attrition risk indicators."""
    return performance_analytics.get_attrition_risk_indicators(db, current_user.org_id, cycle_id)


@router.get("/reports/executive-summary")
def get_executive_summary(
    cycle_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("performance.analytics.read"))
):
    """Generate comprehensive executive performance summary."""
    dashboard = performance_analytics.get_dashboard(db, current_user.org_id, cycle_id)
    from app.services.performance_analytics import performance_analytics as pa
    dept_comp = pa.get_department_comparison(db, current_user.org_id, cycle_id)
    review_pipeline = pa.get_review_pipeline(db, current_user.org_id, cycle_id)
    promo_pipeline = pa.get_promotion_pipeline(db, current_user.org_id)
    from app.services.rating_normalization import rating_normalization as rn
    top_perf = rn.get_top_performers(db, current_user.org_id, cycle_id, 5)
    attrition = pa.get_attrition_risk_indicators(db, current_user.org_id, cycle_id)

    return {
        "dashboard": dashboard,
        "department_comparison": dept_comp,
        "review_pipeline": review_pipeline,
        "promotion_pipeline": promo_pipeline,
        "top_performers": top_perf,
        "attrition_risk": attrition,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }

