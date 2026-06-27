from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class SubmitAttendanceCorrectionRequest(BaseModel):
    """Payload for submitting a new attendance correction request."""

    attendance_log_id: Optional[int] = Field(
        default=None,
        description="ID of the attendance log being corrected. Omit for missing-log requests.",
    )
    request_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Free-form JSON with correction details (reason, expected times, etc.).",
    )


class ApproveAttendanceCorrectionRequest(BaseModel):
    """Payload for approving a pending correction request."""

    decision_notes: Optional[str] = Field(
        default=None,
        description="Optional notes explaining the approval decision.",
    )


class RejectAttendanceCorrectionRequest(BaseModel):
    """Payload for rejecting a pending correction request."""

    decision_notes: Optional[str] = Field(
        default=None,
        description="Optional notes explaining the rejection reason.",
    )


class OverrideAttendanceCorrectionRequest(BaseModel):
    """Payload for admin override of an already-decided correction request."""

    override_reason: str = Field(
        ...,
        min_length=1,
        description="Mandatory rationale for the override (stored in the approval record).",
    )
    decision_notes: Optional[str] = Field(
        default=None,
        description="Optional supplementary notes for the override decision.",
    )


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------

class AttendanceCorrectionResponse(BaseModel):
    """Serialised view of an AttendanceRequest ORM object."""

    id: int
    org_id: uuid.UUID
    employee_user_id: int
    attendance_log_id: Optional[int] = None
    request_payload: Optional[Dict[str, Any]] = None
    status: str
    submitted_at: datetime
    cancelled_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AttendanceApprovalResponse(BaseModel):
    """Serialised view of an AttendanceApproval ORM object."""

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

    class Config:
        from_attributes = True


class AttendanceCorrectionListResponse(BaseModel):
    """Paginated list of correction requests."""

    requests: List[AttendanceCorrectionResponse]
    total: int


class TimelineItem(BaseModel):
    """A single entry in the correction-request audit timeline."""

    kind: str
    status: str
    occurred_at: datetime
    actor_user_id: Optional[int] = None
    actor_role_name: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class TimelineResponse(BaseModel):
    """Full audit timeline for a correction request."""

    timeline: List[TimelineItem]
