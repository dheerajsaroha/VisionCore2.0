"""
workflow.py — Enterprise Approval Workflow Pydantic Schemas
Sprint 2 — Entity 4
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


# ── Approver Schemas ──
class ApproverBase(BaseModel):
    approver_type: str = Field(..., description="role|user|manager|dept_head")
    approver_user_id: Optional[int] = None
    approver_role_id: Optional[int] = None
    sequence_order: int = Field(1, ge=1)
    is_mandatory: bool = True

class ApproverCreate(ApproverBase):
    pass

class ApproverResponse(ApproverBase):
    id: int
    stage_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── Stage Schemas ──
class StageBase(BaseModel):
    stage_order: int = Field(1, ge=1)
    name: str = Field(..., min_length=1, max_length=100)
    approval_type: str = Field("single", description="single|parallel|sequential")
    min_approvals: int = Field(1, ge=1)
    sla_hours: Optional[int] = Field(None, ge=1)
    allow_rework: bool = True
    auto_approve_condition: dict = Field(default_factory=dict)
    is_active: bool = True

class StageCreate(StageBase):
    approvers: List[ApproverCreate] = Field(default_factory=list)

class StageUpdate(BaseModel):
    name: Optional[str] = None
    approval_type: Optional[str] = None
    min_approvals: Optional[int] = None
    sla_hours: Optional[int] = None
    allow_rework: Optional[bool] = None
    auto_approve_condition: Optional[dict] = None
    is_active: Optional[bool] = None

class StageResponse(StageBase):
    id: int
    workflow_id: int
    approvers: List[ApproverResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Workflow Schemas ──
class WorkflowBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    entity_type: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = None
    trigger_event: str = Field("on_create")
    version: int = Field(1, ge=1)
    is_active: bool = True
    auto_approval_enabled: bool = False
    workflow_config: dict = Field(default_factory=dict)

class WorkflowCreate(WorkflowBase):
    organization_id: Optional[UUID] = None
    stages: List[StageCreate] = Field(default_factory=list)

class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_event: Optional[str] = None
    is_active: Optional[bool] = None
    auto_approval_enabled: Optional[bool] = None
    workflow_config: Optional[dict] = None

class WorkflowResponse(WorkflowBase):
    id: int
    organization_id: Optional[UUID] = None
    stages: List[StageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class WorkflowListResponse(BaseModel):
    total: int
    workflows: List[WorkflowResponse]


# ── Template Schemas ──
class TemplateCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    entity_type: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = None
    template_json: dict = Field(default_factory=dict)
    is_system: bool = True
    is_active: bool = True

class TemplateResponse(BaseModel):
    id: int
    code: str
    name: str
    entity_type: str
    description: Optional[str] = None
    template_json: dict
    is_system: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Request Schemas ──
class RequestSubmit(BaseModel):
    workflow_code: Optional[str] = None
    organization_id: Optional[UUID] = None
    entity_type: str = Field(..., min_length=2, max_length=50)
    entity_id: str = Field(..., min_length=1, max_length=100)
    priority: str = Field("medium", description="low|medium|high|urgent")
    title: Optional[str] = None
    summary: Optional[str] = None
    request_payload: dict = Field(default_factory=dict)

class ActionSubmit(BaseModel):
    action: str = Field(..., description="approve|reject|return|reassign|delegate|escalate")
    comments: Optional[str] = None
    reassign_user_id: Optional[int] = None
    meta_data: dict = Field(default_factory=dict)

class ActionResponse(BaseModel):
    id: int
    request_id: int
    stage_id: Optional[int] = None
    actor_user_id: int
    action: str
    comments: Optional[str] = None
    meta_data: dict
    created_at: datetime

    class Config:
        from_attributes = True

class RequestResponse(BaseModel):
    id: int
    workflow_id: int
    organization_id: UUID
    requester_user_id: int
    entity_type: str
    entity_id: str
    current_stage_id: Optional[int] = None
    current_stage_order: int
    status: str
    priority: str
    request_payload: dict
    title: Optional[str] = None
    summary: Optional[str] = None
    submitted_at: datetime
    completed_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    actions: List[ActionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class RequestListResponse(BaseModel):
    total: int
    requests: List[RequestResponse]


# ── History & Audit Schemas ──
class HistoryResponse(BaseModel):
    id: int
    request_id: int
    from_status: Optional[str] = None
    to_status: str
    from_stage_order: Optional[int] = None
    to_stage_order: Optional[int] = None
    actor_user_id: Optional[int] = None
    reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Delegation & Escalation Schemas ──
class DelegationCreate(BaseModel):
    delegatee_user_id: int
    organization_id: Optional[UUID] = None
    entity_type: Optional[str] = None
    start_date: datetime
    end_date: datetime
    reason: Optional[str] = None

class DelegationResponse(BaseModel):
    id: int
    delegator_user_id: int
    delegatee_user_id: int
    organization_id: UUID
    entity_type: Optional[str] = None
    start_date: datetime
    end_date: datetime
    is_active: bool
    reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class EscalationCreate(BaseModel):
    workflow_id: int
    stage_id: Optional[int] = None
    timeout_hours: int = 24
    target_type: str = "role"
    target_user_id: Optional[int] = None
    target_role_id: Optional[int] = None

class EscalationResponse(BaseModel):
    id: int
    workflow_id: int
    stage_id: Optional[int] = None
    timeout_hours: int
    target_type: str
    target_user_id: Optional[int] = None
    target_role_id: Optional[int] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Analytics & Inspection Schemas ──
class WorkflowAnalyticsResponse(BaseModel):
    total_workflows: int
    total_requests: int
    pending_requests: int
    approved_requests: int
    rejected_requests: int
    avg_approval_time_hours: float
    sla_compliance_rate: float

class WorkflowInspectorResult(BaseModel):
    workflow_found: bool
    workflow_id: Optional[int] = None
    workflow_code: Optional[str] = None
    applicable_stages: List[dict] = Field(default_factory=list)
    auto_approvable: bool = False
    next_approver_user_ids: List[int] = Field(default_factory=list)
    next_approver_role_ids: List[int] = Field(default_factory=list)
