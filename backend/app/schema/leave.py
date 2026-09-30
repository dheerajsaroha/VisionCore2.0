"""
leave.py — Pydantic Schemas for Enterprise Leave Management
Sprint 3 — Module 1
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# ── LEAVE TYPE SCHEMAS ──
class LeaveTypeBase(BaseModel):
    name: str = Field(..., description="Leave type display name e.g. Annual Leave")
    code: str = Field(..., description="Unique code e.g. ANNUAL, SICK, CASUAL")
    description: Optional[str] = None
    max_days_per_year: int = Field(12, description="Max annual quota")
    max_days_per_request: int = Field(30, description="Max single request days")
    carry_forward: bool = False
    max_carry_forward_days: int = 0
    requires_document: bool = False
    min_notice_days: int = 0
    is_paid: bool = True
    is_active: bool = True
    gender_specific: Optional[str] = None


class LeaveTypeCreate(LeaveTypeBase):
    pass


class LeaveTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_days_per_year: Optional[int] = None
    max_days_per_request: Optional[int] = None
    carry_forward: Optional[bool] = None
    max_carry_forward_days: Optional[int] = None
    requires_document: Optional[bool] = None
    min_notice_days: Optional[int] = None
    is_paid: Optional[bool] = None
    is_active: Optional[bool] = None
    gender_specific: Optional[str] = None


class LeaveTypeResponse(LeaveTypeBase):
    id: int
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── LEAVE BALANCE SCHEMAS ──
class LeaveBalanceResponse(BaseModel):
    id: int
    user_id: int
    organization_id: UUID
    leave_type_id: int
    leave_type_name: Optional[str] = None
    leave_type_code: Optional[str] = None
    year: int
    entitled_days: float
    used_days: float
    pending_days: float
    carried_forward_days: float
    adjusted_days: float
    available_days: float
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── LEAVE REQUEST SCHEMAS ──
class LeaveRequestCreate(BaseModel):
    leave_type_id: int
    start_date: datetime
    end_date: datetime
    # Optional: the server derives the day count from the date range and the
    # half-day flag, so a client cannot ask for an arbitrary number of days.
    # A supplied value is still accepted for callers that already computed it.
    total_days: Optional[float] = Field(
        default=None, gt=0, description="Leave days; derived from the date range when omitted"
    )
    is_half_day: bool = False
    half_day_period: Optional[str] = None  # "morning" | "afternoon"
    reason: Optional[str] = None
    document_url: Optional[str] = None


class LeaveApprovalAction(BaseModel):
    status: str = Field(..., description="approved | rejected | returned")
    note: Optional[str] = None


class LeaveRequestResponse(BaseModel):
    id: int
    organization_id: UUID
    user_id: int
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    leave_type_id: int
    leave_type_name: Optional[str] = None
    leave_type_code: Optional[str] = None
    start_date: datetime
    end_date: datetime
    total_days: float
    is_half_day: bool
    half_day_period: Optional[str] = None
    reason: Optional[str] = None
    document_url: Optional[str] = None
    status: str
    approver_user_id: Optional[int] = None
    approver_name: Optional[str] = None
    approver_note: Optional[str] = None
    approved_at: Optional[datetime] = None
    workflow_request_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── LEAVE ADJUSTMENT SCHEMAS ──
class LeaveAdjustmentCreate(BaseModel):
    user_id: int
    leave_type_id: int
    year: int = 2025
    adjustment_days: float = Field(..., description="Positive for credit, negative for debit")
    reason: str


class LeaveAdjustmentResponse(BaseModel):
    id: int
    organization_id: UUID
    user_id: int
    leave_type_id: int
    year: int
    adjustment_days: float
    reason: str
    adjusted_by_user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── SUMMARY & ANALYTICS SCHEMAS ──
class LeaveSummaryResponse(BaseModel):
    total_balances: List[LeaveBalanceResponse]
    pending_requests_count: int
    approved_requests_count: int
    rejected_requests_count: int
    upcoming_leaves_count: int


class LeavePolicyUpsert(BaseModel):
    """Organization-level leave rules. Every field is optional so a partial
    update keeps the values the organization already saved."""
    year: Optional[int] = None
    name: Optional[str] = None
    accrual_type: Optional[str] = Field(
        default=None,
        description="annual_grant | monthly_accrual | per_payroll | unlimited",
    )
    allow_negative_balance: Optional[bool] = None
    auto_approve_after_days: Optional[int] = Field(
        default=None,
        description="Auto-approve requests up to this many days. None leaves it manual.",
    )
    policy_config: Optional[Dict[str, Any]] = None
