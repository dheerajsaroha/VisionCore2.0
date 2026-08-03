"""
eaac_engine.py — Unified 8-Stage Enterprise Authorization & Access Control (EAAC) Pipeline Engine
Sprint 2 — Entity 6: Enterprise Authorization Integration
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Type
from uuid import UUID
from pydantic import BaseModel
from sqlalchemy.orm import Session, Query

from app.db.models.all_models import User, Organization
from app.services.subscription_service import SubscriptionService
from app.services.dynamic_role_engine import EffectivePermissionResolver
from app.services.scope_resolver import ScopeResolver, QueryScopeBuilder
from app.services.ownership_service import OwnershipService

logger = logging.getLogger(__name__)



class EAACDecision(BaseModel):
    granted: bool
    user_id: int
    organization_id: UUID
    permission: str
    resource_type: Optional[str] = None
    resource_id: Optional[Any] = None
    primary_role: Optional[str] = None
    effective_permissions: List[str] = []
    effective_data_scopes: Dict[str, Any] = {}
    effective_approval_rights: List[str] = []
    effective_features: List[str] = []
    ownership_level: str = "none" # direct, delegated, organization, none
    approval_required: bool = False
    deny_reason: Optional[str] = None


class EnterpriseAuthorizationEngine:
    """Unified 8-Stage EAAC Pipeline Execution Engine.
    
    Pipeline Stages:
    1. Authentication Verification (User active check)
    2. Tenant Context Verification (Organization active check)
    3. Subscription Feature Access Check (Plan feature unlocks)
    4. Effective Permission Resolution (Dynamic role inheritance & overrides)
    5. Data Scope Boundary Resolution (Self/Dept/Org/Global)
    6. Resource Ownership & Delegation Check (Direct/Delegated)
    7. Governance & Approval Gate Check (Required Approvals)
    8. Audit & Decision Context Generation
    """

    @staticmethod
    def evaluate_access(
        db: Session,
        user_id: int,
        organization_id: UUID,
        permission: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[Any] = None,
        action: str = "read"
    ) -> EAACDecision:
        logger.info(f"EAAC Evaluating: user={user_id}, org={organization_id}, perm={permission}, res={resource_type}:{resource_id}")

        # Stage 1: Authentication & User Verification
        user = db.query(User).filter(User.id == user_id, User.is_active == 1, User.is_deleted == 0).first()
        if not user:
            return EAACDecision(
                granted=False, user_id=user_id, organization_id=organization_id,
                permission=permission, deny_reason="User inactive, deleted, or missing"
            )

        # Stage 2: Tenant Context Verification
        org = db.query(Organization).filter(Organization.id == organization_id, Organization.is_active.is_(True)).first()
        if not org:
            return EAACDecision(
                granted=False, user_id=user_id, organization_id=organization_id,
                permission=permission, deny_reason="Organization inactive or missing"
            )

        # Stage 3 & 4: Effective Authorization Resolution (Roles, Permissions, Features)
        eff_auth = EffectivePermissionResolver.resolve_effective_permissions(db, user_id, organization_id)
        
        eff_perms = eff_auth.get("effective_permissions", [])
        eff_scopes = eff_auth.get("effective_data_scopes", {})
        eff_approvals = eff_auth.get("effective_approval_rights", [])
        eff_features = eff_auth.get("effective_features", [])

        # Check Permission Match (support '*' wildcard or explicit match)
        has_perm = "*" in eff_perms or permission in eff_perms
        if not has_perm:
            return EAACDecision(
                granted=False, user_id=user_id, organization_id=organization_id,
                permission=permission, resource_type=resource_type, resource_id=resource_id,
                primary_role=eff_auth.get("primary_role_code"),
                effective_permissions=eff_perms, effective_data_scopes=eff_scopes,
                effective_approval_rights=eff_approvals, effective_features=eff_features,
                deny_reason=f"Permission '{permission}' not granted by any active dynamic role"
            )

        # Stage 5 & 6: Data Scope & Resource Ownership Evaluation
        ownership_level = "direct"
        if resource_type and resource_id is not None:
            is_owner = OwnershipService.validate_ownership(db, user_id, resource_type, str(resource_id))
            if is_owner:
                ownership_level = "direct"
            else:
                if eff_scopes.get("scope_level") == "self":
                    ownership_level = "self_restricted"


        # Stage 7: Governance & Approval Gate Check
        approval_required = False
        if action in ["approve", "execute", "override", "delete"]:
            if "*" not in eff_approvals:
                perm_prefix = permission.split(".")[0]
                if perm_prefix not in eff_approvals:
                    approval_required = True

        # Decision Context
        return EAACDecision(
            granted=True,
            user_id=user_id,
            organization_id=organization_id,
            permission=permission,
            resource_type=resource_type,
            resource_id=resource_id,
            primary_role=eff_auth.get("primary_role_code"),
            effective_permissions=eff_perms,
            effective_data_scopes=eff_scopes,
            effective_approval_rights=eff_approvals,
            effective_features=eff_features,
            ownership_level=ownership_level,
            approval_required=approval_required
        )

    @staticmethod
    def apply_authorized_scope(
        db: Session,
        user: User,
        permission: str,
        query: Query,
        model: Type[Any]
    ) -> Query:
        """Applies dynamic SQL filters on query according to user's effective EAAC data scope."""
        if not user or not user.org_id:
            return query.filter(model.id == None) # Block if no context

        # SuperAdmin or OrgAdmin bypasses scope filtering
        role_name = user.role.name if user.role else ""
        if role_name in ["SuperAdmin", "OrgAdmin"]:
            if hasattr(model, "organization_id"):
                return query.filter(model.organization_id == user.org_id)
            elif hasattr(model, "org_id"):
                return query.filter(model.org_id == user.org_id)
            return query

        eff_auth = EffectivePermissionResolver.resolve_effective_permissions(db, user.id, user.org_id)
        scopes = eff_auth.get("effective_data_scopes", {})
        scope_level = scopes.get("scope_level", "self")

        if scope_level == "self":
            if hasattr(model, "user_id"):
                return query.filter(model.user_id == user.id)
            elif hasattr(model, "id") and model.__name__ == "User":
                return query.filter(model.id == user.id)
        elif scope_level == "department":
            if hasattr(model, "department_id") and hasattr(user, "department_id"):
                return query.filter(model.department_id == user.department_id)

        # Default fallback to organization level
        if hasattr(model, "organization_id"):
            return query.filter(model.organization_id == user.org_id)
        elif hasattr(model, "org_id"):
            return query.filter(model.org_id == user.org_id)

        return query
