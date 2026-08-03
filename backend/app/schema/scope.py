"""
scope.py — Pydantic Schemas for Enterprise Data Scope & Resource Ownership System (Sprint 2, Entity 3)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
#  DataScope Schemas
# =============================================================================

class DataScopeBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="Data scope code")
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    scope_level: int = Field(10, ge=0, le=100, description="Scope hierarchy level (0-100)")
    is_active: bool = True


class DataScopeCreate(DataScopeBase):
    pass


class DataScopeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scope_level: Optional[int] = Field(None, ge=0, le=100)
    is_active: Optional[bool] = None


class DataScopeResponse(DataScopeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DataScopeListResponse(BaseModel):
    total: int
    data_scopes: List[DataScopeResponse]


# =============================================================================
#  RoleDataScope Schemas
# =============================================================================

class RoleDataScopeBase(BaseModel):
    role_id: int
    data_scope_id: int
    permission_id: Optional[int] = None
    organization_id: Optional[UUID] = None
    scope_parameters: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class RoleDataScopeCreate(RoleDataScopeBase):
    pass


class RoleDataScopeUpdate(BaseModel):
    data_scope_id: Optional[int] = None
    scope_parameters: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class RoleDataScopeResponse(RoleDataScopeBase):
    id: int
    role_name: Optional[str] = None
    data_scope_code: Optional[str] = None
    permission_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoleDataScopeListResponse(BaseModel):
    total: int
    role_data_scopes: List[RoleDataScopeResponse]


# =============================================================================
#  ResourceOwnership Schemas
# =============================================================================

class ResourceOwnershipBase(BaseModel):
    entity_type: str = Field(..., min_length=1, max_length=50)
    entity_id: str = Field(..., min_length=1, max_length=100)
    owner_type: str = Field("creator", description="creator|assignee|subject|reviewer|approver|manager|organization|delegate")
    owner_user_id: Optional[int] = None
    owner_org_id: Optional[UUID] = None
    is_primary: bool = True
    is_active: bool = True
    meta_data: Dict[str, Any] = Field(default_factory=dict)


class ResourceOwnershipCreate(ResourceOwnershipBase):
    pass


class ResourceOwnershipUpdate(BaseModel):
    owner_type: Optional[str] = None
    owner_user_id: Optional[UUID] = None
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None
    meta_data: Optional[Dict[str, Any]] = None


class ResourceOwnershipResponse(ResourceOwnershipBase):
    id: int
    owner_email: Optional[str] = None
    owner_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResourceOwnershipListResponse(BaseModel):
    total: int
    ownerships: List[ResourceOwnershipResponse]


# =============================================================================
#  OwnershipHistory Schemas
# =============================================================================

class OwnershipHistoryResponse(BaseModel):
    id: int
    resource_ownership_id: Optional[int] = None
    entity_type: str
    entity_id: str
    action: str
    previous_owner_user_id: Optional[int] = None
    new_owner_user_id: Optional[int] = None
    previous_owner_type: Optional[str] = None
    new_owner_type: Optional[str] = None
    actor_user_id: Optional[int] = None
    reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OwnershipHistoryListResponse(BaseModel):
    total: int
    history: List[OwnershipHistoryResponse]


# =============================================================================
#  OwnershipDelegation Schemas
# =============================================================================

class OwnershipDelegationBase(BaseModel):
    delegator_user_id: int
    delegatee_user_id: int
    organization_id: UUID
    entity_type: Optional[str] = None
    permission_code: Optional[str] = None
    start_date: datetime
    end_date: datetime
    is_active: bool = True
    reason: Optional[str] = None


class OwnershipDelegationCreate(OwnershipDelegationBase):
    pass


class OwnershipDelegationUpdate(BaseModel):
    end_date: Optional[datetime] = None
    is_active: Optional[bool] = None
    reason: Optional[str] = None


class OwnershipDelegationResponse(OwnershipDelegationBase):
    id: int
    delegator_name: Optional[str] = None
    delegatee_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OwnershipDelegationListResponse(BaseModel):
    total: int
    delegations: List[OwnershipDelegationResponse]


# =============================================================================
#  OwnershipRule Schemas
# =============================================================================

class OwnershipRuleBase(BaseModel):
    entity_type: str
    name: str
    default_owner_type: str = "creator"
    auto_assign_creator: bool = True
    auto_assign_manager: bool = False
    rule_config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class OwnershipRuleCreate(OwnershipRuleBase):
    pass


class OwnershipRuleUpdate(BaseModel):
    default_owner_type: Optional[str] = None
    auto_assign_creator: Optional[bool] = None
    auto_assign_manager: Optional[bool] = None
    rule_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class OwnershipRuleResponse(OwnershipRuleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OwnershipRuleListResponse(BaseModel):
    total: int
    rules: List[OwnershipRuleResponse]


# =============================================================================
#  OwnershipPolicy Schemas
# =============================================================================

class OwnershipPolicyBase(BaseModel):
    organization_id: Optional[UUID] = None
    name: str
    max_delegation_days: int = 30
    allow_cross_dept_delegation: bool = True
    require_approval_for_transfer: bool = False
    policy_config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class OwnershipPolicyCreate(OwnershipPolicyBase):
    pass


class OwnershipPolicyUpdate(BaseModel):
    max_delegation_days: Optional[int] = None
    allow_cross_dept_delegation: Optional[bool] = None
    require_approval_for_transfer: Optional[bool] = None
    policy_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class OwnershipPolicyResponse(OwnershipPolicyBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OwnershipPolicyListResponse(BaseModel):
    total: int
    policies: List[OwnershipPolicyResponse]


# =============================================================================
#  OwnershipException Schemas
# =============================================================================

class OwnershipExceptionBase(BaseModel):
    user_id: int
    entity_type: str
    entity_id: str
    permission_code: str
    granted_by_user_id: Optional[int] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True
    reason: Optional[str] = None


class OwnershipExceptionCreate(OwnershipExceptionBase):
    pass


class OwnershipExceptionResponse(OwnershipExceptionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OwnershipExceptionListResponse(BaseModel):
    total: int
    exceptions: List[OwnershipExceptionResponse]


# =============================================================================
#  Composite & Action Requests
# =============================================================================

class OwnershipTransferRequest(BaseModel):
    entity_type: str
    entity_id: str
    new_owner_user_id: int
    new_owner_type: str = "assignee"
    reason: Optional[str] = "Ownership transferred by administrator"


class EffectiveScopeResponse(BaseModel):
    user_id: int
    organization_id: Optional[UUID] = None
    permission_code: str
    scope_code: str
    scope_level: int
    department_ids: List[int] = Field(default_factory=list)
    subordinate_user_ids: List[int] = Field(default_factory=list)
    owned_entity_ids: List[str] = Field(default_factory=list)
    is_platform_admin: bool = False
    is_org_admin: bool = False
    active_delegations: List[int] = Field(default_factory=list)
    exceptions_granted: List[int] = Field(default_factory=list)


class AuthorizationInspectorRequest(BaseModel):
    user_id: int
    organization_id: UUID
    permission_code: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None


class AuthorizationInspectorResult(BaseModel):
    allowed: bool
    permission_code: str
    user_id: int
    has_permission: bool
    resolved_scope_code: str
    resolved_scope_level: int
    ownership_matched: bool
    owner_type: Optional[str] = None
    delegation_active: bool
    exception_active: bool
    denial_reason: Optional[str] = None
