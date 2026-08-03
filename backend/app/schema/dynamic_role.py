"""
dynamic_role.py — Pydantic Schemas for Enterprise Dynamic Roles & Role Templates
Sprint 2 — Entity 5
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# ── DYNAMIC ROLE SCHEMAS ──
class DynamicRoleBase(BaseModel):
    code: str = Field(..., description="Unique role code e.g. hr_manager_v1")
    name: str = Field(..., description="Human-readable role name")
    description: Optional[str] = None
    tier: str = Field("organization", description="platform, organization, system, custom")
    organization_id: Optional[UUID] = None
    parent_role_id: Optional[int] = None
    template_code: Optional[str] = None
    status: str = Field("active", description="active, disabled, archived, draft")
    is_system: bool = False
    permissions_json: List[str] = Field(default_factory=list, description="Assigned permission strings e.g. ['employee.read', 'payroll.approve']")
    data_scopes_json: Dict[str, Any] = Field(default_factory=dict, description="Scope boundaries e.g. {'department': 'self', 'level': 'dept'}")
    approval_rights_json: List[str] = Field(default_factory=list, description="Approval authority codes e.g. ['leave', 'expense']")
    features_json: List[str] = Field(default_factory=list, description="Feature access codes")

class DynamicRoleCreate(DynamicRoleBase):
    pass

class DynamicRoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_role_id: Optional[int] = None
    status: Optional[str] = None
    permissions_json: Optional[List[str]] = None
    data_scopes_json: Optional[Dict[str, Any]] = None
    approval_rights_json: Optional[List[str]] = None
    features_json: Optional[List[str]] = None

class DynamicRoleResponse(DynamicRoleBase):
    id: int
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DynamicRoleListResponse(BaseModel):
    total: int
    roles: List[DynamicRoleResponse]


# ── ROLE TEMPLATE SCHEMAS ──
class RoleTemplateBase(BaseModel):
    code: str
    name: str
    category: str = "hr"
    description: Optional[str] = None
    is_system: bool = True
    template_config: Dict[str, Any] = Field(default_factory=dict)

class RoleTemplateCreate(RoleTemplateBase):
    pass

class RoleTemplateResponse(RoleTemplateBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── ROLE INHERITANCE SCHEMAS ──
class RoleInheritanceCreate(BaseModel):
    parent_role_id: int
    child_role_id: int
    inherit_permissions: bool = True
    inherit_scopes: bool = True
    inherit_workflows: bool = True
    override_rules_json: Dict[str, Any] = Field(default_factory=dict)

class RoleInheritanceResponse(RoleInheritanceCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── USER ROLE ASSIGNMENT SCHEMAS ──
class UserRoleAssignmentCreate(BaseModel):
    user_id: int
    role_id: int
    organization_id: Optional[UUID] = None
    is_primary: bool = False
    effective_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None

class UserRoleAssignmentResponse(BaseModel):
    id: int
    user_id: int
    role_id: int
    organization_id: UUID
    is_primary: bool
    effective_from: datetime
    expires_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── VERSIONING & DIFF SCHEMAS ──
class RoleVersionResponse(BaseModel):
    id: int
    role_id: int
    version: int
    snapshot_json: Dict[str, Any]
    change_summary: Optional[str] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class RoleDiffResponse(BaseModel):
    role_id: int
    v1: int
    v2: int
    added_permissions: List[str]
    removed_permissions: List[str]
    added_approval_rights: List[str]
    removed_approval_rights: List[str]
    scope_changes: Dict[str, Any]


# ── EFFECTIVE RESOLUTION SCHEMAS ──
class EffectiveAuthorizationResponse(BaseModel):
    user_id: int
    organization_id: UUID
    primary_role_code: Optional[str] = None
    assigned_roles: List[str] = Field(default_factory=list)
    effective_permissions: List[str] = Field(default_factory=list)
    effective_data_scopes: Dict[str, Any] = Field(default_factory=dict)
    effective_approval_rights: List[str] = Field(default_factory=list)
    effective_features: List[str] = Field(default_factory=list)
    subscription_unlocked_features: List[str] = Field(default_factory=list)

