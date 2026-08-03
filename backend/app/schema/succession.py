"""
succession.py — Pydantic Schemas for Enterprise Succession Planning & Career Pathing Engine
Sprint 4 — Entity 3
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# ── KEY POSITION SCHEMAS ──
class KeyPositionBase(BaseModel):
    title: str
    department_id: Optional[int] = None
    criticality_level: str = "critical"  # critical | high | medium
    current_incumbent_user_id: Optional[int] = None
    vacancy_risk_level: str = "low"  # low | medium | high
    impact_rating: float = 4.0  # 1.0 - 5.0


class KeyPositionCreate(KeyPositionBase):
    pass


class KeyPositionResponse(KeyPositionBase):
    id: int
    organization_id: UUID
    department_name: Optional[str] = None
    incumbent_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── SUCCESSION PLAN SCHEMAS ──
class SuccessorCandidateCreate(BaseModel):
    candidate_user_id: int
    readiness_rating: str = "ready_1_year"  # ready_now | ready_1_year | ready_2_years | ready_3_plus_years
    emergency_backup: bool = False
    nomination_notes: Optional[str] = None


class SuccessorCandidateResponse(SuccessorCandidateCreate):
    id: int
    succession_plan_id: int
    candidate_name: Optional[str] = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class SuccessionPlanCreate(BaseModel):
    key_position_id: int
    target_fill_timeline_months: int = 6
    strategy_notes: Optional[str] = None


class SuccessionPlanResponse(BaseModel):
    id: int
    organization_id: UUID
    key_position_id: int
    key_position_title: Optional[str] = None
    target_fill_timeline_months: int
    strategy_notes: Optional[str] = None
    status: str
    created_at: datetime
    candidates: List[SuccessorCandidateResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ── 9-BOX TALENT MATRIX SCHEMAS ──
class NineBoxGridCreate(BaseModel):
    user_id: int
    performance_rating: int = Field(..., ge=1, le=3, description="1=Low, 2=Med, 3=High")
    potential_rating: int = Field(..., ge=1, le=3, description="1=Low, 2=Med, 3=High")
    cycle_id: Optional[int] = None


class NineBoxGridResponse(BaseModel):
    id: int
    organization_id: UUID
    user_id: int
    user_name: Optional[str] = None
    cycle_id: Optional[int] = None
    performance_rating: int
    potential_rating: int
    box_category: str
    evaluated_by_user_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── CAREER PATH & LEVEL SCHEMAS ──
class CareerLevelCreate(BaseModel):
    level_number: int
    level_title: str
    min_experience_years: float = 1.0
    required_skills: Optional[Dict[str, Any]] = None
    target_salary_min: float = 0.0
    target_salary_max: float = 0.0


class CareerLevelResponse(CareerLevelCreate):
    id: int
    career_path_id: int

    model_config = ConfigDict(from_attributes=True)


class CareerPathCreate(BaseModel):
    title: str
    department_id: Optional[int] = None
    description: Optional[str] = None
    total_levels: int = 5
    levels: Optional[List[CareerLevelCreate]] = None


class CareerPathResponse(BaseModel):
    id: int
    organization_id: UUID
    title: str
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    description: Optional[str] = None
    total_levels: int
    levels: List[CareerLevelResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ── INDIVIDUAL DEVELOPMENT PLAN (IDP) SCHEMAS ──
class IDPGoalCreate(BaseModel):
    title: str
    goal_type: str = "skill_acquisition"  # skill_acquisition | training | mentorship | project_assignment
    target_date: Optional[datetime] = None


class IDPGoalResponse(IDPGoalCreate):
    id: int
    idp_id: int
    status: str
    completion_pct: float

    model_config = ConfigDict(from_attributes=True)


class IDPCreate(BaseModel):
    user_id: Optional[int] = None
    target_career_level_id: Optional[int] = None
    target_position_title: Optional[str] = None
    target_completion_date: Optional[datetime] = None
    goals: Optional[List[IDPGoalCreate]] = None


class IDPResponse(BaseModel):
    id: int
    organization_id: UUID
    user_id: int
    user_name: Optional[str] = None
    target_career_level_id: Optional[int] = None
    target_position_title: Optional[str] = None
    status: str
    target_completion_date: Optional[datetime] = None
    created_at: datetime
    goals: List[IDPGoalResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ── FLIGHT RISK ASSESSMENTS ──
class FlightRiskCreate(BaseModel):
    user_id: int
    risk_score: str = "low"  # low | medium | high | critical
    risk_factors: Optional[Dict[str, Any]] = None
    retention_strategy: Optional[str] = None


class FlightRiskResponse(BaseModel):
    id: int
    organization_id: UUID
    user_id: int
    user_name: Optional[str] = None
    risk_score: str
    risk_factors: Optional[Dict[str, Any]] = None
    retention_strategy: Optional[str] = None
    assessed_by_user_id: Optional[int] = None
    assessed_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── MENTORSHIP NETWORK ──
class MentorshipPairCreate(BaseModel):
    mentor_user_id: int
    mentee_user_id: int
    focus_areas: Optional[str] = None


class MentorshipPairResponse(BaseModel):
    id: int
    organization_id: UUID
    mentor_user_id: int
    mentor_name: Optional[str] = None
    mentee_user_id: int
    mentee_name: Optional[str] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    status: str
    focus_areas: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ── ANALYTICS ──
class SuccessionAnalyticsResponse(BaseModel):
    critical_positions_count: int
    succession_readiness_pct: float
    nine_box_stars_count: int
    active_idps_count: int
    high_flight_risk_count: int
    active_mentorships_count: int
    nine_box_distribution: Dict[str, int]
