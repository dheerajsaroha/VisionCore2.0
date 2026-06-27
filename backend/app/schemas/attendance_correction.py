from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class SubmitAttendanceCorrectionRequest(BaseModel):
    attendance_log_id: Optional[int] = None
    request_payload: Optional[dict] = None


class ApproveAttendanceCorrectionRequest(BaseModel):
    decision_notes: Optional[str] = None


class RejectAttendanceCorrectionRequest(BaseModel):
    decision_notes: Optional[str] = None


class OverrideAttendanceCorrectionRequest(BaseModel):
    decision_notes: Optional[str] = None
    override_reason: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------

class AttendanceCorrectionResponse(BaseModel):
    id: int
    org_id: uuid.UUID
    employee_user_id: int
    attendance_log_id: Optional[int] = None
    request_payload: Optional[dict] = None
    status: str
    submitted_at: datetime
    cancelled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AttendanceApprovalResponse(BaseModel):
    id: int
    attendance_request_id: int
    org_id: uuid.UUID
    approver_user_id: Optional[int] = None
    approval_status: str
    decision_notes: Optional[str] = None
    override_reason: Optional[str] = None
    decided_at: datetime
    created_by_ip: Optional[str] = None
    created_by_user_agent: Optional[str] = None
    created_by_correlation_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AttendanceCorrectionListResponse(BaseModel):
    requests: List[AttendanceCorrectionResponse]
    total: int


class TimelineResponseItem(BaseModel):
    kind: str
    status: str
    occurred_at: datetime
    actor_user_id: Optional[int] = None
    actor_role_name: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TimelineResponse(BaseModel):
    timeline: List[TimelineResponseItem]
