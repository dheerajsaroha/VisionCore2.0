"""
compensation.py — Pydantic Schemas for Compensation & Benefits Management System
Sprint 4 — Entity 4
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# ── COMPENSATION GRADES & BANDS ──
class CompensationBandCreate(BaseModel):
    band_label: str
    band_min: float
    band_max: float
    target_pct_of_midpoint: float = 100.0


class CompensationBandResponse(CompensationBandCreate):
    id: int
    grade_id: int
    model_config = ConfigDict(from_attributes=True)


class CompensationGradeCreate(BaseModel):
    grade_code: str
    grade_name: str
    salary_min: float
    salary_mid: float
    salary_max: float
    currency: str = "INR"
    bands: Optional[List[CompensationBandCreate]] = None


class CompensationGradeResponse(BaseModel):
    id: int
    organization_id: UUID
    grade_code: str
    grade_name: str
    salary_min: float
    salary_mid: float
    salary_max: float
    currency: str
    is_active: bool
    bands: List[CompensationBandResponse] = []
    model_config = ConfigDict(from_attributes=True)


# ── SALARY REVISIONS ──
class SalaryRevisionCreate(BaseModel):
    user_id: int
    revision_type: str = "merit"
    previous_salary: float
    proposed_salary: float
    justification: Optional[str] = None
    performance_review_id: Optional[int] = None


class SalaryRevisionApprove(BaseModel):
    status: str  # approved | rejected
    justification: Optional[str] = None


class SalaryRevisionResponse(BaseModel):
    id: int
    organization_id: UUID
    user_id: int
    user_name: Optional[str] = None
    revision_type: str
    previous_salary: float
    proposed_salary: float
    increase_pct: float
    status: str
    justification: Optional[str] = None
    effective_date: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── BENEFITS PLANS ──
class BenefitsPlanCreate(BaseModel):
    plan_name: str
    plan_type: str = "health"
    description: Optional[str] = None
    employer_contribution_pct: float = 0.0
    employee_contribution_pct: float = 0.0
    max_coverage_amount: float = 0.0
    is_mandatory: bool = False


class BenefitsPlanResponse(BenefitsPlanCreate):
    id: int
    organization_id: UUID
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


# ── BENEFITS ENROLLMENTS ──
class BenefitsEnrollmentCreate(BaseModel):
    plan_id: int
    user_id: Optional[int] = None
    coverage_tier: str = "individual"
    elected_amount: float = 0.0


class BenefitsEnrollmentResponse(BaseModel):
    id: int
    organization_id: UUID
    user_id: int
    user_name: Optional[str] = None
    plan_id: int
    plan_name: Optional[str] = None
    plan_type: Optional[str] = None
    coverage_tier: str
    elected_amount: float
    status: str
    effective_from: datetime
    model_config = ConfigDict(from_attributes=True)


# ── EQUITY GRANTS ──
class EquityGrantCreate(BaseModel):
    user_id: int
    grant_type: str = "rsu"
    total_shares: int
    strike_price: float = 0.0
    cliff_months: int = 12
    vesting_months: int = 48


class EquityVestingEventResponse(BaseModel):
    id: int
    grant_id: int
    scheduled_date: datetime
    shares_vesting: int
    vested: bool
    vested_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class EquityGrantResponse(BaseModel):
    id: int
    organization_id: UUID
    user_id: int
    user_name: Optional[str] = None
    grant_type: str
    total_shares: int
    vested_shares: int
    strike_price: float
    cliff_months: int
    vesting_months: int
    status: str
    grant_date: datetime
    vesting_events: List[EquityVestingEventResponse] = []
    model_config = ConfigDict(from_attributes=True)


# ── TOTAL REWARDS STATEMENT ──
class TotalRewardsResponse(BaseModel):
    id: int
    organization_id: UUID
    user_id: int
    user_name: Optional[str] = None
    grade_code: Optional[str] = None
    fiscal_year: int
    base_salary: float
    total_benefits_value: float
    equity_fmv: float
    bonus_paid: float
    total_comp: float
    compa_ratio: float
    generated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── COMPENSATION REVIEW ──
class CompensationReviewCreate(BaseModel):
    review_name: str
    fiscal_year: int = 2025
    total_budget: float = 0.0


class CompensationReviewResponse(BaseModel):
    id: int
    organization_id: UUID
    review_name: str
    fiscal_year: int
    status: str
    total_budget: float
    used_budget: float
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── ANALYTICS ──
class CompensationAnalyticsResponse(BaseModel):
    avg_compa_ratio: float
    pending_salary_revisions: int
    active_benefits_enrollments: int
    unvested_equity_grants: int
    total_benefits_cost_monthly: float
    pay_equity_gap_pct: float
    grade_distribution: Dict[str, int]
