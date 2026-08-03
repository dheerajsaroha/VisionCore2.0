"""
policy.py — Pydantic Schemas for Enterprise Policy Center & Compliance Management System
Sprint 4 — Entity 5
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# ── POLICY CATEGORY SCHEMAS ──
class PolicyCategoryBase(BaseModel):
    name: str = Field(..., description="Category name")
    code: Optional[str] = None
    description: Optional[str] = None
    parent_category_id: Optional[int] = None
    is_active: bool = True


class PolicyCategoryCreate(PolicyCategoryBase):
    pass


class PolicyCategoryUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    parent_category_id: Optional[int] = None
    is_active: Optional[bool] = None


class PolicyCategoryResponse(PolicyCategoryBase):
    id: int
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── POLICY TAG SCHEMAS ──
class PolicyTagCreate(BaseModel):
    name: str
    color: Optional[str] = None


class PolicyTagResponse(BaseModel):
    id: int
    organization_id: UUID
    name: str
    color: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── POLICY DOCUMENT SCHEMAS ──
class PolicyDocumentBase(BaseModel):
    title: str = Field(..., description="Policy document title")
    category_id: Optional[int] = None
    document_number: Optional[str] = None
    owner_user_id: Optional[int] = None
    approver_user_id: Optional[int] = None
    author: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    policy_type: str = "hr_policy"
    is_mandatory: bool = False
    requires_acknowledgement: bool = True
    requires_signature: bool = False
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    tags: Optional[List[Dict[str, Any]]] = None
    meta_data: Optional[Dict[str, Any]] = None


class PolicyDocumentCreate(PolicyDocumentBase):
    pass


class PolicyDocumentUpdate(BaseModel):
    title: Optional[str] = None
    category_id: Optional[int] = None
    document_number: Optional[str] = None
    owner_user_id: Optional[int] = None
    approver_user_id: Optional[int] = None
    author: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    policy_type: Optional[str] = None
    status: Optional[str] = None
    is_mandatory: Optional[bool] = None
    requires_acknowledgement: Optional[bool] = None
    requires_signature: Optional[bool] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    tags: Optional[List[Dict[str, Any]]] = None
    meta_data: Optional[Dict[str, Any]] = None


class PolicyVersionResponse(BaseModel):
    id: int
    document_id: int
    version: int
    version_type: str
    title: str
    content: Optional[str] = None
    change_summary: Optional[str] = None
    status: str
    created_by_user_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PolicyAttachmentResponse(BaseModel):
    id: int
    document_id: int
    version_id: Optional[int] = None
    file_name: str
    file_url: str
    file_type: str
    file_size_bytes: int
    uploaded_by_user_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PolicyDocumentResponse(PolicyDocumentBase):
    id: int
    organization_id: UUID
    status: str
    current_version: int
    workflow_request_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    versions: List[PolicyVersionResponse] = []
    attachments: List[PolicyAttachmentResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ── POLICY VERSION SCHEMAS ──
class PolicyVersionCreate(BaseModel):
    title: str
    content: Optional[str] = None
    change_summary: Optional[str] = None
    version_type: str = "major"


# ── POLICY ATTACHMENT SCHEMAS ──
class PolicyAttachmentCreate(BaseModel):
    file_name: str
    file_url: str
    file_type: str = "pdf"
    file_size_bytes: int = 0
    version_id: Optional[int] = None


# ── POLICY DISTRIBUTION SCHEMAS ──
class PolicyDistributionCreate(BaseModel):
    distribution_type: str = "organization"
    target_org_id: Optional[UUID] = None
    target_dept_id: Optional[int] = None
    target_role_id: Optional[int] = None
    target_user_id: Optional[int] = None


class PolicyDistributionResponse(BaseModel):
    id: int
    document_id: int
    distribution_type: str
    target_org_id: Optional[UUID] = None
    target_dept_id: Optional[int] = None
    target_role_id: Optional[int] = None
    target_user_id: Optional[int] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── ACKNOWLEDGEMENT SCHEMAS ──
class PolicyAcknowledgeRequest(BaseModel):
    version_id: Optional[int] = None
    ip_address: Optional[str] = None
    device_info: Optional[str] = None
    user_agent: Optional[str] = None
    read_duration_seconds: Optional[int] = None


class PolicyAcknowledgementResponse(BaseModel):
    id: int
    document_id: int
    user_id: int
    user_name: Optional[str] = None
    version_id: Optional[int] = None
    is_acknowledged: bool
    acknowledged_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    device_info: Optional[str] = None
    read_duration_seconds: Optional[int] = None
    reminder_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── SIGNATURE SCHEMAS ──
class PolicySignatureCreate(BaseModel):
    acknowledgement_id: Optional[int] = None
    document_id: int
    signature_hash: str
    signature_metadata: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    device_info: Optional[str] = None
    verification_method: str = "click"


class PolicySignatureResponse(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = None
    document_id: int
    signed_at: datetime
    signature_hash: str
    verification_method: str
    is_verified: bool

    model_config = ConfigDict(from_attributes=True)


# ── TEMPLATE SCHEMAS ──
class PolicyTemplateCreate(BaseModel):
    category_id: Optional[int] = None
    name: str
    content: str
    variables: Optional[Dict[str, Any]] = None


class PolicyTemplateResponse(BaseModel):
    id: int
    organization_id: UUID
    category_id: Optional[int] = None
    name: str
    content: str
    variables: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── REMINDER SCHEMAS ──
class PolicyReminderCreate(BaseModel):
    document_id: int
    reminder_type: str = "automated"
    interval_days: int = 7
    max_reminders: int = 3
    escalation_user_id: Optional[int] = None


class PolicyReminderResponse(BaseModel):
    id: int
    organization_id: UUID
    document_id: int
    reminder_type: str
    interval_days: int
    max_reminders: int
    escalation_user_id: Optional[int] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── NOTIFICATION SCHEMAS ──
class PolicyNotificationResponse(BaseModel):
    id: int
    organization_id: UUID
    document_id: Optional[int] = None
    user_id: Optional[int] = None
    notification_type: str
    title: str
    message: Optional[str] = None
    is_read: bool
    sent_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── COMPLIANCE SCHEMAS ──
class ComplianceRuleCreate(BaseModel):
    name: str
    rule_type: str
    policy_type_filter: Optional[str] = None
    description: Optional[str] = None
    grace_period_days: int = 14
    weight: float = 1.0


class ComplianceRuleResponse(BaseModel):
    id: int
    organization_id: UUID
    name: str
    rule_type: str
    policy_type_filter: Optional[str] = None
    description: Optional[str] = None
    grace_period_days: int
    weight: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplianceRecordResponse(BaseModel):
    id: int
    organization_id: UUID
    document_id: int
    document_title: Optional[str] = None
    user_id: int
    user_name: Optional[str] = None
    rule_id: Optional[int] = None
    is_compliant: bool
    compliant_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    status: str
    notes: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── ANALYTICS & DASHBOARD SCHEMAS ──
class PolicyCenterAnalytics(BaseModel):
    total_policies: int
    draft_policies: int
    published_policies: int
    expired_policies: int
    total_categories: int
    pending_acknowledgements: int
    overall_compliance_rate: float
    expiring_soon_count: int
    compliance_breakdown: List[Dict[str, Any]] = []
