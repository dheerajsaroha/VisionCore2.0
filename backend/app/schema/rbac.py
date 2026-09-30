"""
rbac.py — Pydantic schemas for RBAC (roles, permissions, assignments).
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ── Permission Schemas ────────────────────────────────────────────────────────
# Permission names are namespaced: "<module><separator><action>", where the
# separator is "." or ":". Both separators and underscores inside the module
# segment occur in the seeded catalog and are referenced verbatim by
# require_permission() guards, so validation must accept them:
#   users.read, reports.attendance.export, ai_governance.manage,
#   attendance_correction:approve
# The previous pattern rejected the latter two shapes, which made
# GET /rbac/permissions fail response validation with a 500.
PERMISSION_NAME_PATTERN = r"^[a-z][a-z0-9_]*[.:][a-z][a-z0-9_]*([.:][a-z][a-z0-9_]*)*$"


class PermissionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, pattern=PERMISSION_NAME_PATTERN,
                      description="Namespaced name: e.g. 'users.read', 'attendance.checkin', "
                                  "'attendance_correction:approve'")
    description: Optional[str] = Field(None, max_length=500)
    module: Optional[str] = Field(None, max_length=50)
    group: Optional[str] = Field(None, max_length=50)
    is_active: bool = True


class PermissionCreate(PermissionBase):
    pass


class PermissionUpdate(BaseModel):
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PermissionResponse(PermissionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PermissionListResponse(BaseModel):
    total: int
    permissions: List[PermissionResponse]


# ── Role Schemas ──────────────────────────────────────────────────────────────
class RoleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z][A-Za-z0-9_]*$",
                      description="Role name must start with a letter")
    description: Optional[str] = Field(None, max_length=500)
    tier: str = Field("organization", pattern=r"^(platform|organization|system)$")
    is_system: bool = False


class RoleCreate(RoleBase):
    permission_ids: List[int] = Field(default_factory=list, description="Initial permission IDs to assign")


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_system: Optional[bool] = None


class RoleResponse(RoleBase):
    # Existing roles may use display names with spaces; the identifier
    # constraint applies to role creation, not serialization of stored data.
    name: str = Field(..., min_length=1, max_length=50)
    id: int
    created_at: datetime
    permission_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class RoleListResponse(BaseModel):
    total: int
    roles: List[RoleResponse]


class RoleDetailResponse(RoleResponse):
    permissions: List[PermissionResponse] = []


# ── Assignment Schemas ────────────────────────────────────────────────────────
class RoleAssignment(BaseModel):
    user_id: int
    role_id: int


class BulkRoleAssignment(BaseModel):
    assignments: List[RoleAssignment]


class RolePermissionAssignment(BaseModel):
    permission_ids: List[int]


class UserRoleResponse(BaseModel):
    user_id: int
    role_id: int
    role_name: str
    assigned_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Data Access Scope Schemas ─────────────────────────────────────────────────
class DataAccessScope(BaseModel):
    scope: str = Field(..., pattern=r"^(platform|organization|department|team|self|custom)$")
    org_id: Optional[UUID] = None
    department_id: Optional[int] = None
    team_id: Optional[int] = None
    custom_filter: Optional[dict] = None


# ── Feature Flag Schemas ──────────────────────────────────────────────────────
class FeatureFlag(BaseModel):
    feature_key: str = Field(..., min_length=1, max_length=100)
    enabled: bool = False
    org_id: Optional[UUID] = None


# ── Seed Status ───────────────────────────────────────────────────────────────
class SeedStatus(BaseModel):
    permissions: int
    roles: int
    links: int
    total: int


# =============================================================================
#  Permission System — Enhanced Schemas (Sprint 2, EAAC)
# =============================================================================

# ── Permission Validation ─────────────────────────────────────────────────────
class PermissionNameValidation(BaseModel):
    """Result of validating a permission name against EAAC naming standard."""
    name: str
    valid: bool
    message: str


class PermissionValidateNames(BaseModel):
    """Request to validate one or more permission names."""
    names: List[str] = Field(..., min_length=1, max_length=100)


class PermissionValidateNamesResponse(BaseModel):
    """Response with validation results for each name."""
    results: List[PermissionNameValidation]


# ── Bulk Operations ──────────────────────────────────────────────────────────
class BulkPermissionAssignRequest(BaseModel):
    """Request to bulk assign permissions to a role."""
    role_id: int
    permission_ids: List[int] = Field(..., min_length=1, max_length=500)


class BulkPermissionRemoveRequest(BaseModel):
    """Request to bulk remove permissions from a role."""
    role_id: int
    permission_ids: List[int] = Field(..., min_length=1, max_length=500)


class BulkPermissionResponse(BaseModel):
    """Response from a bulk permission operation."""
    assigned: int = 0
    removed: int = 0
    skipped: int = 0
    errors: List[str] = []
    permission_names: List[str] = []


# ── Activation / Deactivation ────────────────────────────────────────────────
class PermissionActivateRequest(BaseModel):
    """Request to activate/deactivate a permission."""
    is_active: bool


class PermissionActivateResponse(BaseModel):
    """Response from an activation/deactivation operation."""
    success: bool
    warnings: List[str] = []
    message: str
    permission_id: Optional[int] = None


# ── Permission Detail ─────────────────────────────────────────────────────────
class PermissionDetailResponse(PermissionResponse):
    """Extended permission response with additional metadata."""
    role_count: int = 0
    module: Optional[str] = None
    group: Optional[str] = None


# ── Module Statistics ─────────────────────────────────────────────────────────
class PermissionModuleItem(BaseModel):
    """A single permission within a module."""
    id: int
    name: str
    description: Optional[str] = None
    group: Optional[str] = None
    is_active: bool


class PermissionModuleStats(BaseModel):
    """Statistics for a single permission module."""
    module: str
    total: int
    active: int
    inactive: int
    permissions: List[PermissionModuleItem]


class PermissionModuleSummary(BaseModel):
    """Lightweight module summary (no permission details)."""
    module: str
    total: int
    active: int
    inactive: int


class PermissionModuleListResponse(BaseModel):
    """Response containing module statistics."""
    modules: List[PermissionModuleStats]
    total_modules: int


class PermissionModuleSummaryResponse(BaseModel):
    """Response containing module summaries."""
    modules: List[PermissionModuleSummary]
    total_modules: int


# ── Advanced Search ──────────────────────────────────────────────────────────
class PermissionSearchRequest(BaseModel):
    """Advanced permission search parameters."""
    search: Optional[str] = Field(None, max_length=200)
    module: Optional[str] = Field(None, max_length=50)
    group: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None
    skip: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=500)


class PermissionSearchResponse(BaseModel):
    """Response from an advanced permission search."""
    total: int
    permissions: List[PermissionResponse]
    filters_applied: dict = {}


# ── Permission Audit ─────────────────────────────────────────────────────────
class PermissionAuditEntry(BaseModel):
    """A single permission audit log entry."""
    action: str
    permission: str
    role: str
    actor_user_id: int
    timestamp: str


class PermissionAuditResponse(BaseModel):
    """Response containing permission audit log entries."""
    entries: List[PermissionAuditEntry]
    total: int


# ── User Effective Permissions ───────────────────────────────────────────────
class UserEffectivePermissions(BaseModel):
    """Effective permissions for a user."""
    user_id: int
    role_id: int
    role_name: str
    permissions: List[str]
    permission_count: int
