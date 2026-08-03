"""
scope.py — Enterprise Data Scope & Resource Ownership Router (Sprint 2, Entity 3)

Endpoints:
- Data Scopes catalog management
- Role Data Scope mapping
- Resource Ownership CRUD & Transfers
- Temporary Ownership Delegations
- Ownership Rules & Governance Policies
- Effective Scope & Authorization Inspector
- Seeding
"""
from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.db.models.all_models import User
from app.crud.crud_scope import (
    data_scope_crud,
    role_data_scope_crud,
    resource_ownership_crud,
    ownership_history_crud,
    ownership_delegation_crud,
    ownership_rule_crud,
    ownership_policy_crud,
    ownership_exception_crud,
)
from app.schema.scope import (
    DataScopeCreate,
    DataScopeUpdate,
    DataScopeResponse,
    DataScopeListResponse,
    RoleDataScopeCreate,
    RoleDataScopeUpdate,
    RoleDataScopeResponse,
    RoleDataScopeListResponse,
    ResourceOwnershipCreate,
    ResourceOwnershipResponse,
    ResourceOwnershipListResponse,
    OwnershipHistoryResponse,
    OwnershipHistoryListResponse,
    OwnershipDelegationCreate,
    OwnershipDelegationResponse,
    OwnershipDelegationListResponse,
    OwnershipRuleCreate,
    OwnershipRuleResponse,
    OwnershipRuleListResponse,
    OwnershipPolicyCreate,
    OwnershipPolicyResponse,
    OwnershipPolicyListResponse,
    OwnershipTransferRequest,
    EffectiveScopeResponse,
    AuthorizationInspectorRequest,
    AuthorizationInspectorResult,
)
from app.services.scope_resolver import ScopeResolver
from app.services.ownership_service import OwnershipService
from app.db.seed_scope import seed_all_scope_data

router = APIRouter()


# =============================================================================
#  DataScope Catalog Endpoints
# =============================================================================

@router.get("/data-scopes", response_model=DataScopeListResponse)
def list_data_scopes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """List available enterprise data scopes."""
    items, total = data_scope_crud.get_multi(db, skip=skip, limit=limit)
    return DataScopeListResponse(
        total=total,
        data_scopes=[DataScopeResponse.model_validate(i) for i in items],
    )


@router.post("/data-scopes", response_model=DataScopeResponse, status_code=status.HTTP_201_CREATED)
def create_data_scope(
    scope_in: DataScopeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("platform.settings.manage")),
):
    """Create a new data scope catalog entry (SuperAdmin only)."""
    existing = data_scope_crud.get_by_code(db, scope_in.code)
    if existing:
        raise HTTPException(status_code=409, detail=f"Data scope code '{scope_in.code}' already exists")
    scope = data_scope_crud.create(db, scope_in.model_dump())
    return DataScopeResponse.model_validate(scope)


# =============================================================================
#  Role Data Scope Bindings Endpoints
# =============================================================================

@router.get("/role-data-scopes", response_model=RoleDataScopeListResponse)
def list_role_data_scopes(
    role_id: Optional[int] = None,
    organization_id: Optional[UUID] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """List role-to-data-scope mappings."""
    items, total = role_data_scope_crud.get_multi(db, skip=skip, limit=limit, role_id=role_id, organization_id=organization_id)
    resp_items = []
    for item in items:
        r = RoleDataScopeResponse.model_validate(item)
        r.role_name = item.role.name if item.role else None
        r.data_scope_code = item.data_scope.code if item.data_scope else None
        r.permission_name = item.permission.name if item.permission else None
        resp_items.append(r)
    return RoleDataScopeListResponse(total=total, role_data_scopes=resp_items)


@router.post("/role-data-scopes", response_model=RoleDataScopeResponse, status_code=status.HTTP_201_CREATED)
def create_role_data_scope(
    rds_in: RoleDataScopeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("platform.settings.manage")),
):
    """Bind a role (and optional permission) to a Data Scope."""
    rec = role_data_scope_crud.create(db, rds_in.model_dump())
    full_rec = role_data_scope_crud.get_by_id(db, rec.id)
    r = RoleDataScopeResponse.model_validate(full_rec)
    r.role_name = full_rec.role.name if full_rec.role else None
    r.data_scope_code = full_rec.data_scope.code if full_rec.data_scope else None
    return r


@router.delete("/role-data-scopes/{rds_id}")
def delete_role_data_scope(
    rds_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("platform.settings.manage")),
):
    """Delete a role data scope binding."""
    ok = role_data_scope_crud.delete(db, rds_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Role data scope binding not found")
    return {"message": "Role data scope deleted successfully"}


# =============================================================================
#  Resource Ownership Endpoints
# =============================================================================

@router.get("/ownerships", response_model=ResourceOwnershipListResponse)
def list_resource_ownerships(
    entity_type: Optional[str] = None,
    user_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """List resource ownership entries."""
    items, total = resource_ownership_crud.get_multi(db, skip=skip, limit=limit, entity_type=entity_type, user_id=user_id)
    resp_items = []
    for item in items:
        r = ResourceOwnershipResponse.model_validate(item)
        r.owner_email = item.owner_user.email if item.owner_user else None
        r.owner_name = item.owner_user.full_name if item.owner_user else None
        resp_items.append(r)
    return ResourceOwnershipListResponse(total=total, ownerships=resp_items)


@router.post("/ownerships", response_model=ResourceOwnershipResponse, status_code=status.HTTP_201_CREATED)
def assign_resource_ownership(
    ownership_in: ResourceOwnershipCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Assign resource ownership."""
    rec = OwnershipService.assign_ownership(
        db,
        entity_type=ownership_in.entity_type,
        entity_id=ownership_in.entity_id,
        owner_user_id=ownership_in.owner_user_id,
        owner_type=ownership_in.owner_type,
        owner_org_id=ownership_in.owner_org_id,
        actor_user_id=current_user.id,
        is_primary=ownership_in.is_primary,
        meta_data=ownership_in.meta_data,
    )
    full_rec = resource_ownership_crud.get_by_id(db, rec.id)
    r = ResourceOwnershipResponse.model_validate(full_rec)
    if full_rec and full_rec.owner_user:
        r.owner_email = full_rec.owner_user.email
        r.owner_name = full_rec.owner_user.full_name
    return r


@router.post("/ownerships/transfer", response_model=ResourceOwnershipResponse)
def transfer_resource_ownership(
    req: OwnershipTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Transfer resource ownership to another user."""
    rec = OwnershipService.transfer_ownership(
        db,
        entity_type=req.entity_type,
        entity_id=req.entity_id,
        new_owner_user_id=req.new_owner_user_id,
        new_owner_type=req.new_owner_type,
        actor_user_id=current_user.id,
        reason=req.reason,
    )
    full_rec = resource_ownership_crud.get_by_id(db, rec.id)
    r = ResourceOwnershipResponse.model_validate(full_rec)
    if full_rec and full_rec.owner_user:
        r.owner_email = full_rec.owner_user.email
        r.owner_name = full_rec.owner_user.full_name
    return r


@router.get("/ownerships/history", response_model=OwnershipHistoryListResponse)
def list_ownership_history(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """List ownership audit trail history."""
    items, total = ownership_history_crud.get_multi(db, skip=skip, limit=limit, entity_type=entity_type, entity_id=entity_id)
    return OwnershipHistoryListResponse(
        total=total,
        history=[OwnershipHistoryResponse.model_validate(i) for i in items],
    )


# =============================================================================
#  Ownership Delegations Endpoints
# =============================================================================

@router.get("/delegations", response_model=OwnershipDelegationListResponse)
def list_ownership_delegations(
    organization_id: Optional[UUID] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """List ownership delegations."""
    org_id = organization_id or current_user.org_id
    items, total = ownership_delegation_crud.get_multi(db, skip=skip, limit=limit, organization_id=org_id)
    resp_items = []
    for item in items:
        r = OwnershipDelegationResponse.model_validate(item)
        r.delegator_name = item.delegator.full_name if item.delegator else None
        r.delegatee_name = item.delegatee.full_name if item.delegatee else None
        resp_items.append(r)
    return OwnershipDelegationListResponse(total=total, delegations=resp_items)


@router.post("/delegations", response_model=OwnershipDelegationResponse, status_code=status.HTTP_201_CREATED)
def create_ownership_delegation(
    del_in: OwnershipDelegationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Create a temporary ownership/permission delegation."""
    rec = OwnershipService.create_delegation(
        db,
        delegator_user_id=del_in.delegator_user_id,
        delegatee_user_id=del_in.delegatee_user_id,
        organization_id=del_in.organization_id,
        start_date=del_in.start_date,
        end_date=del_in.end_date,
        entity_type=del_in.entity_type,
        permission_code=del_in.permission_code,
        reason=del_in.reason,
    )
    r = OwnershipDelegationResponse.model_validate(rec)
    return r


# =============================================================================
#  Rules & Policies Endpoints
# =============================================================================

@router.get("/rules", response_model=OwnershipRuleListResponse)
def list_ownership_rules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """List declarative ownership rules."""
    items, total = ownership_rule_crud.get_multi(db, skip=skip, limit=limit)
    return OwnershipRuleListResponse(
        total=total,
        rules=[OwnershipRuleResponse.model_validate(i) for i in items],
    )


@router.post("/rules", response_model=OwnershipRuleResponse, status_code=status.HTTP_201_CREATED)
def create_ownership_rule(
    rule_in: OwnershipRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("platform.settings.manage")),
):
    """Create an ownership rule."""
    rec = ownership_rule_crud.create(db, rule_in.model_dump())
    return OwnershipRuleResponse.model_validate(rec)


@router.get("/policies", response_model=OwnershipPolicyListResponse)
def list_ownership_policies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """List enterprise ownership policies."""
    items, total = ownership_policy_crud.get_multi(db, skip=skip, limit=limit)
    return OwnershipPolicyListResponse(
        total=total,
        policies=[OwnershipPolicyResponse.model_validate(i) for i in items],
    )


# =============================================================================
#  Effective Scope & Inspector Endpoints
# =============================================================================

@router.get("/effective-scope", response_model=EffectiveScopeResponse)
def get_effective_scope(
    permission: str = Query(..., description="Permission code (e.g. 'attendance.read')"),
    organization_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Inspect effective Data Scope for current user and permission context."""
    eff = ScopeResolver.resolve_effective_scope(db, current_user, permission, organization_id)
    return EffectiveScopeResponse(
        user_id=eff.user_id,
        organization_id=eff.organization_id,
        permission_code=eff.permission_code,
        scope_code=eff.scope_code,
        scope_level=eff.scope_level,
        department_ids=eff.department_ids,
        subordinate_user_ids=eff.subordinate_user_ids,
        owned_entity_ids=eff.owned_entity_ids,
        is_platform_admin=eff.is_platform_admin,
        is_org_admin=eff.is_org_admin,
        active_delegations=eff.active_delegations,
        exceptions_granted=eff.exceptions_granted,
    )


@router.post("/inspect", response_model=AuthorizationInspectorResult)
def inspect_authorization(
    req: AuthorizationInspectorRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Interactive authorization evaluation inspector testing Permission + Scope + Ownership."""
    target_user = db.query(User).filter(User.id == req.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    eff = ScopeResolver.resolve_effective_scope(db, target_user, req.permission_code, req.organization_id, req.entity_type)

    owned = False
    if req.entity_type and req.entity_id:
        owned = OwnershipService.validate_ownership(db, req.user_id, req.entity_type, req.entity_id)

    allowed = eff.is_platform_admin or eff.is_org_admin or eff.scope_level >= 20 or owned

    return AuthorizationInspectorResult(
        allowed=allowed,
        permission_code=req.permission_code,
        user_id=req.user_id,
        has_permission=True,
        resolved_scope_code=eff.scope_code,
        resolved_scope_level=eff.scope_level,
        ownership_matched=owned,
        owner_type="creator" if owned else None,
        delegation_active=len(eff.active_delegations) > 0,
        exception_active=False,
        denial_reason=None if allowed else "Scope level insufficient and resource ownership not matched",
    )


# =============================================================================
#  Seeding Endpoint
# =============================================================================

@router.post("/seed")
def seed_scope_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("platform.settings.manage")),
):
    """Seed data scopes, default role scopes, ownership rules, and policies."""
    scope_map = seed_all_scope_data(db)
    return {"message": "Data Scope and Resource Ownership seeded successfully", "scopes_seeded": len(scope_map)}
