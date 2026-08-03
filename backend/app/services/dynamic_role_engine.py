"""
dynamic_role_engine.py — Core Engine Services & Effective Authorization Resolvers
Sprint 2 — Entity 5
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from app.crud import crud_dynamic_role
from app.db.models.all_models import (
    DynamicRole, RoleTemplate, RoleInheritance, RoleVersion,
    UserRoleAssignment, RoleAssignmentHistory, RoleAudit, User
)
from app.services.subscription_service import SubscriptionService


logger = logging.getLogger(__name__)


# ── 1. INHERITANCE ENGINE & CYCLE DETECTOR ──
class RoleInheritanceService:
    """DAG Traversal engine with circular dependency detection."""

    @staticmethod
    def detect_cycle(db: Session, parent_role_id: int, child_role_id: int) -> bool:
        """Returns True if establishing parent -> child creates a cycle."""
        if parent_role_id == child_role_id:
            return True

        visited: Set[int] = set()
        queue: List[int] = [parent_role_id]

        while queue:
            curr = queue.pop(0)
            if curr == child_role_id:
                return True
            if curr in visited:
                continue
            visited.add(curr)

            # Find parents of curr
            parents = db.query(RoleInheritance.parent_role_id).filter(
                RoleInheritance.child_role_id == curr
            ).all()
            for p in parents:
                queue.append(p[0])

        return False

    @staticmethod
    def get_all_ancestor_role_ids(db: Session, role_id: int) -> List[int]:
        """Traverses DAG upwards to gather all parent/ancestor role IDs."""
        ancestors: Set[int] = set()
        queue: List[int] = [role_id]

        while queue:
            curr = queue.pop(0)
            parents = db.query(RoleInheritance.parent_role_id).filter(
                RoleInheritance.child_role_id == curr
            ).all()
            for p in parents:
                pid = p[0]
                if pid not in ancestors:
                    ancestors.add(pid)
                    queue.append(pid)

        return list(ancestors)


# ── 2. DYNAMIC ROLE SERVICE ──
class DynamicRoleService:
    """Lifecycle manager for dynamic enterprise roles."""

    @staticmethod
    def create_role_from_template(db: Session, organization_id: UUID, template_code: str, custom_name: Optional[str] = None, custom_code: Optional[str] = None, user_id: Optional[int] = None) -> DynamicRole:
        tmpl = crud_dynamic_role.get_template_by_code(db, template_code)
        if not tmpl:
            raise ValueError(f"Role template '{template_code}' not found")

        cfg = tmpl.template_config
        import uuid
        role_code = custom_code or f"{template_code}_org_{organization_id.hex[:6]}_{uuid.uuid4().hex[:4]}"
        role_name = custom_name or f"{tmpl.name} (Custom)"


        role_data = {
            "code": role_code,
            "name": role_name,
            "description": tmpl.description,
            "tier": "custom",
            "organization_id": organization_id,
            "template_code": template_code,
            "status": "active",
            "permissions_json": cfg.get("permissions", []),
            "data_scopes_json": cfg.get("data_scopes", {}),
            "approval_rights_json": cfg.get("approval_rights", []),
            "features_json": cfg.get("features", [])
        }

        role = crud_dynamic_role.create_role(db, role_data)

        # Audit log
        db.add(RoleAudit(
            organization_id=organization_id, actor_user_id=user_id,
            event_type="role_created_from_template",
            details={"template_code": template_code, "role_id": role.id, "role_code": role.code}
        ))
        db.commit()
        return role

    @staticmethod
    def clone_role(db: Session, source_role_id: int, new_code: str, new_name: str, organization_id: UUID, user_id: Optional[int] = None) -> DynamicRole:
        src = crud_dynamic_role.get_role_by_id(db, source_role_id)
        if not src:
            raise ValueError(f"Source role {source_role_id} not found")

        role_data = {
            "code": new_code,
            "name": new_name,
            "description": f"Cloned from {src.name}",
            "tier": "custom",
            "organization_id": organization_id,
            "parent_role_id": src.parent_role_id,
            "template_code": src.template_code,
            "status": "active",
            "permissions_json": list(src.permissions_json or []),
            "data_scopes_json": dict(src.data_scopes_json or {}),
            "approval_rights_json": list(src.approval_rights_json or []),
            "features_json": list(src.features_json or [])
        }

        new_role = crud_dynamic_role.create_role(db, role_data)
        return new_role

    @staticmethod
    def rollback_role_version(db: Session, role_id: int, target_version: int, user_id: Optional[int] = None) -> DynamicRole:
        role = crud_dynamic_role.get_role_by_id(db, role_id)
        if not role:
            raise ValueError(f"Role {role_id} not found")

        versions = crud_dynamic_role.get_role_versions(db, role_id)
        target_ver_obj = next((v for v in versions if v.version == target_version), None)
        if not target_ver_obj:
            raise ValueError(f"Target version {target_version} not found for role {role_id}")

        snap = target_ver_obj.snapshot_json
        updates = {
            "name": snap.get("name"),
            "description": snap.get("description"),
            "permissions_json": snap.get("permissions_json", []),
            "data_scopes_json": snap.get("data_scopes_json", {}),
            "approval_rights_json": snap.get("approval_rights_json", []),
            "features_json": snap.get("features_json", [])
        }

        updated_role = crud_dynamic_role.update_role(db, role_id, updates, user_id=user_id)
        return updated_role


# ── 3. EFFECTIVE PERMISSION RESOLVER ──
class EffectivePermissionResolver:
    """Aggregates direct, assigned, and inherited permissions bounded by subscription features."""

    @staticmethod
    def resolve_effective_permissions(db: Session, user_id: int, organization_id: UUID) -> Dict[str, Any]:
        user_assignments = crud_dynamic_role.get_user_role_assignments(db, user_id, organization_id)
        if not user_assignments:
            # Fallback to base User.role if no dynamic role assigned
            usr = db.query(User).filter(User.id == user_id).first()
            if usr and usr.role and usr.role.name == "SuperAdmin":
                return {
                    "user_id": user_id, "organization_id": organization_id,
                    "primary_role_code": "SuperAdmin", "assigned_roles": ["SuperAdmin"],
                    "effective_permissions": ["*"], "effective_data_scopes": {"all": "global"},
                    "effective_approval_rights": ["*"], "effective_features": ["*"]
                }
            return {
                "user_id": user_id, "organization_id": organization_id,
                "primary_role_code": None, "assigned_roles": [],
                "effective_permissions": [], "effective_data_scopes": {},
                "effective_approval_rights": [], "effective_features": []
            }

        role_ids = [a.role_id for a in user_assignments]
        primary_asgn = next((a for a in user_assignments if a.is_primary), user_assignments[0])
        primary_role_code = primary_asgn.role.code if primary_asgn.role else None

        # Expand ancestor roles via DAG inheritance
        all_role_ids = set(role_ids)
        for rid in role_ids:
            ancestors = RoleInheritanceService.get_all_ancestor_role_ids(db, rid)
            all_role_ids.update(ancestors)

        roles = db.query(DynamicRole).filter(DynamicRole.id.in_(all_role_ids), DynamicRole.status == "active").all()

        eff_perms: Set[str] = set()
        eff_approval: Set[str] = set()
        eff_features: Set[str] = set()
        eff_scopes: Dict[str, Any] = {}
        assigned_codes: List[str] = []

        for r in roles:
            assigned_codes.append(r.code)
            for p in (r.permissions_json or []):
                eff_perms.add(p)
            for ap in (r.approval_rights_json or []):
                eff_approval.add(ap)
            for ft in (r.features_json or []):
                eff_features.add(ft)
            for k, v in (r.data_scopes_json or {}).items():
                eff_scopes[k] = v

        # Enforce Subscription Constraints
        unlocked_feat_objs = SubscriptionService.get_enabled_features_for_org(db, organization_id)
        unlocked_features = [f.code if hasattr(f, 'code') else str(f) for f in unlocked_feat_objs]
        if "*" not in eff_features:
            bounded_features = [f for f in eff_features if f in unlocked_features]
        else:
            bounded_features = unlocked_features


        return {
            "user_id": user_id,
            "organization_id": organization_id,
            "primary_role_code": primary_role_code,
            "assigned_roles": list(set(assigned_codes)),
            "effective_permissions": sorted(list(eff_perms)),
            "effective_data_scopes": eff_scopes,
            "effective_approval_rights": sorted(list(eff_approval)),
            "effective_features": bounded_features,
            "subscription_unlocked_features": unlocked_features
        }


# ── 4. ROLE VERSION DIFF ENGINE ──
class RoleVersionService:
    """Calculates diffs between role versions."""

    @staticmethod
    def calculate_role_diff(db: Session, role_id: int, v1: int, v2: int) -> Dict[str, Any]:
        versions = crud_dynamic_role.get_role_versions(db, role_id)
        ver1 = next((v for v in versions if v.version == v1), None)
        ver2 = next((v for v in versions if v.version == v2), None)

        if not ver1 or not ver2:
            raise ValueError("Invalid version numbers provided for diff calculation")

        p1 = set(ver1.snapshot_json.get("permissions_json", []))
        p2 = set(ver2.snapshot_json.get("permissions_json", []))

        a1 = set(ver1.snapshot_json.get("approval_rights_json", []))
        a2 = set(ver2.snapshot_json.get("approval_rights_json", []))

        return {
            "role_id": role_id, "v1": v1, "v2": v2,
            "added_permissions": sorted(list(p2 - p1)),
            "removed_permissions": sorted(list(p1 - p2)),
            "added_approval_rights": sorted(list(a2 - a1)),
            "removed_approval_rights": sorted(list(a1 - a2)),
            "scope_changes": {
                "v1_scope": ver1.snapshot_json.get("data_scopes_json", {}),
                "v2_scope": ver2.snapshot_json.get("data_scopes_json", {})
            }
        }
