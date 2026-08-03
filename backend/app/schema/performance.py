"""
performance.py — Pydantic Schemas for Enterprise Performance Management System
Sprint 4 — Entity 1
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# ── PERFORMANCE CYCLE SCHEMAS ──
class PerformanceCycleBase(BaseModel):
    name: str = Field(..., description="Cycle name e.g. FY2025 Annual Review")
    cycle_type: str = Field(..., description="annual|half_year|quarterly|monthly|probation|promotion|exit|custom")
    start_date: datetime
    end_date: datetime
    review_deadline: Optional[datetime] = None
    description: Optional[str] = None


class PerformanceCycleCreate(PerformanceCycleBase):
    pass


class PerformanceCycleUpdate(BaseModel):
    name: Optional[str] = None
    cycle_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    review_deadline: Optional[datetime] = None
    status: Optional[str] = None
    description: Optional[str] = None


class PerformanceCycleResponse(PerformanceCycleBase):
    id: int
    organization_id: UUID
    status: str
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── COMPETENCY SCHEMAS ──
class CompetencyBase(BaseModel):
    name: str
    category: str = Field(..., description="technical|behavioral|leadership|communication|innovation|custom")
    description: Optional[str] = None
    is_active: bool = True


class CompetencyCreate(CompetencyBase):
    pass


class CompetencyResponse(CompetencyBase):
    id: int
    organization_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── KPI SCHEMAS ──
class KPIBase(BaseModel):
    name: str
    department_id: Optional[int] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    kpi_type: str = "individual"
    is_active: bool = True


class KPICreate(KPIBase):
    pass


class KPIResponse(KPIBase):
    id: int
    organization_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KPIAssignmentCreate(BaseModel):
    kpi_id: int
    user_id: int
    cycle_id: int
    target_value: float
    weight: float = 1.0


class KPIAssignmentUpdate(BaseModel):
    actual_value: float


class KPIAssignmentResponse(BaseModel):
    id: int
    organization_id: UUID
    kpi_id: int
    kpi_name: Optional[str] = None
    user_id: int
    cycle_id: int
    target_value: float
    actual_value: Optional[float] = None
    weight: float
    score: Optional[float] = None
    assigned_by_user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── GOAL SCHEMAS ──
class GoalCreate(BaseModel):
    cycle_id: Optional[int] = None
    user_id: Optional[int] = None
    parent_goal_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    goal_type: str = "individual"  # individual|team|organization
    goal_framework: str = "smart"  # okr|smart|personal|stretch
    target_value: Optional[float] = None
    current_value: float = 0.0
    unit: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: str = "medium"


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_value: Optional[float] = None
    current_value: Optional[float] = None
    status: Optional[str] = None
    priority: Optional[str] = None


class GoalProgressLog(BaseModel):
    value: float
    note: Optional[str] = None


class GoalProgressResponse(BaseModel):
    id: int
    goal_id: int
    user_id: int
    value: float
    completion_pct: float
    note: Optional[str] = None
    logged_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GoalResponse(BaseModel):
    id: int
    organization_id: UUID
    cycle_id: Optional[int] = None
    user_id: int
    user_name: Optional[str] = None
    parent_goal_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    goal_type: str
    goal_framework: str
    target_value: Optional[float] = None
    current_value: float
    unit: Optional[str] = None
    due_date: Optional[datetime] = None
    status: str
    priority: str
    completion_pct: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── REVIEW SCHEMAS ──
class CompetencyRatingInput(BaseModel):
    competency_id: int
    rating: float = Field(..., ge=1.0, le=5.0)
    evidence: Optional[str] = None


class CompetencyRatingResponse(BaseModel):
    id: int
    review_id: int
    competency_id: int
    competency_name: Optional[str] = None
    rating: float
    evidence: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PerformanceReviewCreate(BaseModel):
    cycle_id: int
    reviewee_user_id: int
    reviewer_user_id: Optional[int] = None
    review_type: str = "self"  # self|manager|skip_level|hr|peer|360


class PerformanceReviewSubmit(BaseModel):
    overall_score: Optional[float] = Field(None, ge=1.0, le=5.0)
    strengths: Optional[str] = None
    areas_for_improvement: Optional[str] = None
    comments: Optional[str] = None
    competency_ratings: Optional[List[CompetencyRatingInput]] = None


class PerformanceReviewResponse(BaseModel):
    id: int
    organization_id: UUID
    cycle_id: int
    reviewee_user_id: int
    reviewee_name: Optional[str] = None
    reviewer_user_id: Optional[int] = None
    reviewer_name: Optional[str] = None
    review_type: str
    status: str
    overall_score: Optional[float] = None
    strengths: Optional[str] = None
    areas_for_improvement: Optional[str] = None
    comments: Optional[str] = None
    submitted_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    competency_ratings: List[CompetencyRatingResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ── FEEDBACK SCHEMAS ──
class FeedbackCreate(BaseModel):
    receiver_user_id: int
    cycle_id: Optional[int] = None
    feedback_type: str = "peer"  # peer|manager|self|360|anonymous|scheduled
    is_anonymous: bool = False
    content: str
    rating: Optional[float] = Field(None, ge=1.0, le=5.0)


class FeedbackResponse(BaseModel):
    id: int
    organization_id: UUID
    cycle_id: Optional[int] = None
    receiver_user_id: int
    receiver_name: Optional[str] = None
    giver_user_id: Optional[int] = None
    giver_name: Optional[str] = None
    feedback_type: str
    is_anonymous: bool
    content: str
    rating: Optional[float] = None
    is_visible_to_receiver: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── RATING & CALIBRATION SCHEMAS ──
class PerformanceRatingResponse(BaseModel):
    id: int
    organization_id: UUID
    cycle_id: int
    user_id: int
    user_name: Optional[str] = None
    kpi_score: Optional[float] = None
    goal_score: Optional[float] = None
    competency_score: Optional[float] = None
    final_rating: Optional[float] = None
    rating_label: Optional[str] = None
    is_calibrated: bool
    calibrated_rating: Optional[float] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CalibrationSessionCreate(BaseModel):
    cycle_id: int
    notes: Optional[str] = None


class CalibrationUpdate(BaseModel):
    user_id: int
    calibrated_rating: float = Field(..., ge=1.0, le=5.0)


class CalibrationSessionResponse(BaseModel):
    id: int
    organization_id: UUID
    cycle_id: int
    facilitator_user_id: int
    status: str
    notes: Optional[str] = None
    calibration_data: Optional[dict] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── ANALYTICS DETAIL SCHEMAS ──
class TopPerformerResponse(BaseModel):
    user_id: int
    user_name: str
    department_name: str
    final_rating: float
    rating_label: str
    kpi_score: float = 0.0
    goal_score: float = 0.0
    competency_score: float = 0.0
    is_calibrated: bool = False


class DepartmentComparisonResponse(BaseModel):
    department_id: int
    department_name: str
    avg_rating: float
    employee_count: int
    top_rating: float
    bottom_rating: float


class ReviewPipelineResponse(BaseModel):
    total: int
    pending: int
    in_progress: int
    submitted: int
    acknowledged: int
    completion_pct: float
    by_type: Dict[str, int] = {}


class PromotionPipelineResponse(BaseModel):
    total_recommendations: int
    pending: int
    approved: int
    rejected: int
    deferred: int
    avg_readiness_score: float = 0.0


class ReadinessAssessmentResponse(BaseModel):
    user_id: int
    overall_readiness: float
    factors: Dict[str, Any] = {}
    recommendation: str = ""


class ExecutiveSummaryResponse(BaseModel):
    dashboard: PerformanceAnalyticsResponse
    department_comparison: Dict[str, Any] = {}
    review_pipeline: Dict[str, Any] = {}
    promotion_pipeline: Dict[str, Any] = {}
    top_performers: List[TopPerformerResponse] = []
    attrition_risk: Dict[str, Any] = {}
    generated_at: str


# ── PIP SCHEMAS ──
class PIPCreate(BaseModel):
    user_id: int
    title: str
    reason: str
    objectives: Optional[str] = None
    milestones: Optional[List[Dict[str, Any]]] = None
    start_date: datetime
    end_date: datetime


class PIPUpdate(BaseModel):
    title: Optional[str] = None
    reason: Optional[str] = None
    objectives: Optional[str] = None
    milestones: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = None
    outcome: Optional[str] = None
    closure_notes: Optional[str] = None


class PIPResponse(BaseModel):
    id: int
    organization_id: UUID
    user_id: int
    user_name: Optional[str] = None
    manager_user_id: int
    manager_name: Optional[str] = None
    title: str
    reason: str
    objectives: Optional[str] = None
    milestones: Optional[List[Dict[str, Any]]] = None
    start_date: datetime
    end_date: datetime
    status: str
    outcome: Optional[str] = None
    closure_notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── PROMOTION RECOMMENDATION SCHEMAS ──
class PromotionRecommendationCreate(BaseModel):
    user_id: int
    cycle_id: Optional[int] = None
    proposed_role: Optional[str] = None
    proposed_salary_increase_pct: Optional[float] = None
    readiness_score: Optional[float] = Field(None, ge=1.0, le=5.0)
    justification: Optional[str] = None


class PromotionAction(BaseModel):
    status: str = Field(..., description="approved | rejected | deferred")
    decision_notes: Optional[str] = None


class PromotionRecommendationResponse(BaseModel):
    id: int
    organization_id: UUID
    user_id: int
    user_name: Optional[str] = None
    cycle_id: Optional[int] = None
    recommended_by_user_id: int
    recommender_name: Optional[str] = None
    proposed_role: Optional[str] = None
    proposed_salary_increase_pct: Optional[float] = None
    readiness_score: Optional[float] = None
    justification: Optional[str] = None
    status: str
    decision_notes: Optional[str] = None
    decided_by_user_id: Optional[int] = None
    decided_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── ANALYTICS SCHEMAS ──
class BellCurveBucket(BaseModel):
    rating_label: str
    count: int
    pct: float


class PerformanceAnalyticsResponse(BaseModel):
    total_employees_in_cycle: int
    completed_reviews_count: int
    pending_reviews_count: int
    review_completion_pct: float
    avg_performance_rating: float
    goal_completion_pct: float
    active_pips_count: int
    promotion_candidates_count: int
    bell_curve: List[BellCurveBucket]
