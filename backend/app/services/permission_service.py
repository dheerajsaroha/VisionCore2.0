"""
permission_service.py — Permission System Business Logic Layer

Provides:
- Permission name validation (EAAC naming standard)
- Bulk assignment/removal with validation
- Permission activation/deactivation with dependency checks
- Permission audit logging (append-only)
- Permission module statistics
- User effective permission resolution
- Permission dependency conflict detection

This layer is SYNCHRONOUS by design.
Cache integration is handled at the API/deps layer.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.all_models import (
    Permission,
    Role,
    RolePermission,
    SystemSetting,
    User,
)
from app.crud.crud_role import permission_crud
from app.api.deps import normalize_role_name

logger = logging.getLogger(__name__)


class PermissionValidationError(ValueError):
    """Raised when permission validation fails."""
    pass


class PermissionService:
    """Service layer for Permission business logic."""

    NAME_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")
    SCOPE_KEYWORDS = frozenset({
        "self", "department", "organization", "platform",
        "team", "own", "other", "manager", "admin",
        "all", "global", "tenant", "user", "role",
    })

    # ── Permission Name Validation ──────────────────────────────────────────

    @classmethod
    def validate_permission_name(cls, name: str) -> tuple[bool, str]:
        """Validate permission name follows {module}.{action} convention.

        Rules:
        - Must contain exactly one dot separating module and action
        - Module: lowercase letters, underscores (e.g., 'attendance', 'api_key')
        - Action: lowercase letters, underscores (e.g., 'read', 'checkin')
        - No scope encoding (e.g., 'employee.read.self' is INVALID)
        - Minimum length: 3 characters
        - Maximum length: 100 characters
        """
        if not name or len(name) < 3:
            return False, "Permission name must be at least 3 characters"
        if len(name) > 100:
            return False, "Permission name must not exceed 100 characters"

        parts = name.split(".")
        if len(parts) != 2:
            return False, (
                f"Permission name '{name}' must follow {{module}}.{{action}} "
                f"convention with exactly one dot. Found {len(parts)} parts."
            )

        module, action = parts
        if not module:
            return False, "Module part cannot be empty"
        if not action:
            return False, "Action part cannot be empty"

        if not cls.NAME_REGEX.match(module):
            return False, (
                f"Module '{module}' must start with a lowercase letter and "
                f"contain only lowercase letters, digits, and underscores"
            )
        if not cls.NAME_REGEX.match(action):
            return False, (
                f"Action '{action}' must start with a lowercase letter and "
                f"contain only lowercase letters, digits, and underscores"
            )

        # Anti-pattern: scope encoding in permission name
        if action in cls.SCOPE_KEYWORDS:
            return False, (
                f"Action '{action}' looks like a scope keyword. "
                f"Do NOT encode scope in permission name. "
                f"Use permission name + separate scope instead."
            )

        return True, ""

    @staticmethod
    def extract_module(name: str) -> str:
        """Extract module from a permission name (part before the dot)."""
        return name.split(".")[0] if "." in name else name

    # ── Permission Resolution & ABAC Evaluation ───────────────────────────────────

    @staticmethod
    def evaluate_abac_policy(
        user_context: dict,
        resource_context: dict,
        environment_context: dict,
        required_rule: Optional[dict] = None,
    ) -> bool:
        """ABAC policy engine evaluation hook for future fine-grained rule checks."""
        if not required_rule:
            return True
        # Check tenant matching
        if "tenant_id" in required_rule and user_context.get("tenant_id") != required_rule["tenant_id"]:
            return False
        # Check environment restrictions (e.g. business hours, IP ranges)
        if "allowed_ips" in environment_context and environment_context.get("client_ip") not in environment_context["allowed_ips"]:
            return False
        return True

    @staticmethod
    def get_user_effective_permissions(
        db: Session,
        user: User,
    ) -> list[str]:
        """Get all effective permission names for a user based on their role.

        SuperAdmin returns ALL active permissions.
        """
        if not user.role_id:
            return []

        role = db.query(Role).filter(Role.id == user.role_id).first()
        if not role:
            return []

        # SuperAdmin has all active permissions (handles PLATFORM:SuperAdmin variant)
        if normalize_role_name(role.name) == "SuperAdmin":
            all_perms = db.query(Permission.name).filter(
                Permission.is_active == True
            ).all()
            return [p[0] for p in all_perms]

        # Normal permission resolution via RolePermission join
        perms = (
            db.query(Permission.name)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .filter(
                RolePermission.role_id == role.id,
                Permission.is_active == True,
            )
            .all()
        )
        return [p[0] for p in perms]

    @staticmethod
    def has_permission(
        db: Session,
        user: User,
        permission_name: str,
    ) -> bool:
        """Check if a user has a specific permission (supports wildcard module.*)."""
        permissions = PermissionService.get_user_effective_permissions(db, user)
        if permission_name in permissions:
            return True
        module = permission_name.split(".")[0]
        wildcard_name = f"{module}.*"
        return wildcard_name in permissions

    @staticmethod
    def has_any_permission(
        db: Session,
        user: User,
        permission_names: list[str],
    ) -> bool:
        """Check if a user has ANY of the specified permissions."""
        permissions = PermissionService.get_user_effective_permissions(db, user)
        user_set = set(permissions)
        return bool(user_set & set(permission_names))

    @staticmethod
    def has_all_permissions(
        db: Session,
        user: User,
        permission_names: list[str],
    ) -> tuple[bool, list[str]]:
        """Check if a user has ALL specified permissions.

        Returns (has_all: bool, missing: list[str]).
        """
        permissions = PermissionService.get_user_effective_permissions(db, user)
        user_set = set(permissions)
        required_set = set(permission_names)
        missing = list(required_set - user_set)
        return len(missing) == 0, missing

    # ── Bulk Operations ─────────────────────────────────────────────────────

    @staticmethod
    def bulk_assign_permissions(
        db: Session,
        role_id: int,
        permission_ids: list[int],
        actor_user_id: Optional[int] = None,
    ) -> dict:
        """Bulk assign permissions to a role with validation.

        Returns: {
            "assigned": int,
            "skipped": int,
            "errors": list[str],
            "permission_names": list[str],
        }
        """
        result = {"assigned": 0, "skipped": 0, "errors": [],
                  "permission_names": []}

        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            result["errors"].append(f"Role id={role_id} not found")
            return result

        if role.is_system:
            result["errors"].append(
                f"Role '{role.name}' is a system role — "
                f"permissions cannot be modified"
            )
            return result

        for perm_id in permission_ids:
            perm = db.query(Permission).filter(Permission.id == perm_id).first()
            if not perm:
                result["errors"].append(f"Permission id={perm_id} not found")
                continue
            if not perm.is_active:
                result["errors"].append(
                    f"Permission '{perm.name}' is deactivated. "
                    f"Activate it before assigning."
                )
                continue

            existing = db.query(RolePermission).filter(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == perm_id,
            ).first()
            if existing:
                result["skipped"] += 1
                continue

            db.add(RolePermission(role_id=role_id, permission_id=perm_id))
            result["assigned"] += 1
            result["permission_names"].append(perm.name)

            if actor_user_id:
                PermissionService._log_audit(
                    db, "assign", perm.name, role.name, actor_user_id
                )

        db.commit()

        # Invalidate cache via background task
        PermissionService._invalidate_cache(role_id, "all")

        return result

    @staticmethod
    def bulk_remove_permissions(
        db: Session,
        role_id: int,
        permission_ids: list[int],
        actor_user_id: Optional[int] = None,
    ) -> dict:
        """Bulk remove permissions from a role with validation.

        Returns: {
            "removed": int,
            "skipped": int,
            "errors": list[str],
            "permission_names": list[str],
        }
        """
        result = {"removed": 0, "skipped": 0, "errors": [],
                  "permission_names": []}

        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            result["errors"].append(f"Role id={role_id} not found")
            return result

        if role.is_system:
            result["errors"].append(
                f"Role '{role.name}' is a system role — "
                f"permissions cannot be modified"
            )
            return result

        for perm_id in permission_ids:
            perm = db.query(Permission).filter(Permission.id == perm_id).first()
            if not perm:
                result["errors"].append(f"Permission id={perm_id} not found")
                continue

            existing = db.query(RolePermission).filter(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == perm_id,
            ).first()
            if not existing:
                result["skipped"] += 1
                continue

            db.delete(existing)
            result["removed"] += 1
            result["permission_names"].append(perm.name)

            if actor_user_id:
                PermissionService._log_audit(
                    db, "remove", perm.name, role.name, actor_user_id
                )

        db.commit()
        PermissionService._invalidate_cache(role_id, "all")

        return result

    # ── Activation / Deactivation ───────────────────────────────────────────

    @staticmethod
    def deactivate_permission(
        db: Session,
        permission_id: int,
        actor_user_id: Optional[int] = None,
    ) -> dict:
        """Deactivate a permission with dependency validation.

        Returns: {
            "success": bool,
            "warnings": list[str],
            "message": str,
        }
        """
        result = {"success": False, "warnings": [], "message": ""}

        perm = db.query(Permission).filter(Permission.id == permission_id).first()
        if not perm:
            result["message"] = f"Permission id={permission_id} not found"
            return result

        if not perm.is_active:
            result["message"] = f"Permission '{perm.name}' is already deactivated"
            result["success"] = True
            return result

        # Check dependency conflicts
        warnings = PermissionService._check_deactivation_warnings(db, perm)
        if warnings:
            result["warnings"] = warnings
            # We still allow deactivation but warn
            logger.warning(
                "Deactivating permission '%s' with warnings: %s",
                perm.name, warnings
            )

        perm.is_active = False
        db.commit()

        if actor_user_id:
            PermissionService._log_audit(
                db, "deactivate", perm.name, "*", actor_user_id
            )

        PermissionService._invalidate_cache(None, "all")

        result["success"] = True
        result["message"] = f"Permission '{perm.name}' deactivated"
        return result

    @staticmethod
    def activate_permission(
        db: Session,
        permission_id: int,
        actor_user_id: Optional[int] = None,
    ) -> dict:
        """Activate a previously deactivated permission."""
        result = {"success": False, "warnings": [], "message": ""}

        perm = db.query(Permission).filter(Permission.id == permission_id).first()
        if not perm:
            result["message"] = f"Permission id={permission_id} not found"
            return result

        if perm.is_active:
            result["message"] = f"Permission '{perm.name}' is already active"
            result["success"] = True
            return result

        perm.is_active = True
        db.commit()

        if actor_user_id:
            PermissionService._log_audit(
                db, "activate", perm.name, "*", actor_user_id
            )

        PermissionService._invalidate_cache(None, "all")

        result["success"] = True
        result["message"] = f"Permission '{perm.name}' activated"
        return result

    # ── Module Statistics ───────────────────────────────────────────────────

    @staticmethod
    def get_module_statistics(db: Session) -> list[dict]:
        """Get statistics for each permission module.

        Returns: [{
            "module": str,
            "total": int,
            "active": int,
            "inactive": int,
            "permissions": [{"id", "name", "description", "group", "is_active"}]
        }]
        """
        from sqlalchemy import func

        modules = permission_crud.get_modules(db)
        stats = []

        for module in modules:
            total = db.query(func.count(Permission.id)).filter(
                Permission.module == module
            ).scalar() or 0

            active = db.query(func.count(Permission.id)).filter(
                Permission.module == module,
                Permission.is_active == True,
            ).scalar() or 0

            perms = (
                db.query(Permission)
                .filter(Permission.module == module)
                .order_by(Permission.name)
                .all()
            )

            stats.append({
                "module": module,
                "total": total,
                "active": active,
                "inactive": total - active,
                "permissions": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "description": p.description,
                        "group": p.group,
                        "is_active": p.is_active,
                    }
                    for p in perms
                ],
            })

        return stats

    @staticmethod
    def get_module_summary(db: Session) -> list[dict]:
        """Get lightweight module summary (no permission details).

        Returns: [{"module", "total", "active", "inactive"}]
        """
        modules = permission_crud.get_modules(db)
        summaries = []

        for module in modules:
            perms = db.query(Permission).filter(Permission.module == module).all()
            total = len(perms)
            active = sum(1 for p in perms if p.is_active)
            summaries.append({
                "module": module,
                "total": total,
                "active": active,
                "inactive": total - active,
            })

        return summaries

    # ── Advanced Permission Search ──────────────────────────────────────────

    @staticmethod
    def search_permissions_advanced(
        db: Session,
        *,
        search: Optional[str] = None,
        module: Optional[str] = None,
        group: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Permission], int]:
        """Advanced permission search with multiple filters.

        Delegates to CRUD layer for query construction.
        Returns (permissions_list, total_count).
        """
        return permission_crud.get_multi_advanced(
            db,
            search=search,
            module=module,
            group=group,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )

    # ── Permission Audit Log ────────────────────────────────────────────────

    @staticmethod
    def _log_audit(
        db: Session,
        action: str,
        permission_name: str,
        role_name: str,
        actor_user_id: int,
    ) -> None:
        """Append a permission change entry to the audit log."""
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = {
            "action": action,
            "permission": permission_name,
            "role": role_name,
            "actor_user_id": actor_user_id,
            "timestamp": timestamp,
        }

        setting = db.query(SystemSetting).filter(
            SystemSetting.setting_key == "audit.permission_changes"
        ).first()

        if setting:
            try:
                log = json.loads(setting.setting_value)
            except (json.JSONDecodeError, TypeError):
                log = []
            log.append(entry)
            if len(log) > 1000:
                log = log[-1000:]
            setting.setting_value = json.dumps(log, default=str)
            db.add(setting)
        else:
            db.add(SystemSetting(
                setting_key="audit.permission_changes",
                setting_value=json.dumps([entry], default=str),
                description="Permission change audit log (max 1000 entries)",
            ))

    @staticmethod
    def get_audit_log(db: Session, limit: int = 100) -> list[dict]:
        """Retrieve recent permission change audit log entries."""
        setting = db.query(SystemSetting).filter(
            SystemSetting.setting_key == "audit.permission_changes"
        ).first()

        if not setting:
            return []

        try:
            log = json.loads(setting.setting_value)
            return log[-limit:]
        except (json.JSONDecodeError, TypeError):
            return []

    # ── Internal Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _check_deactivation_warnings(db: Session, perm: Permission) -> list[str]:
        """Check for issues that deactivating a permission may cause.

        Returns warning messages (empty = safe to proceed).
        """
        warnings = []
        module = PermissionService.extract_module(perm.name)

        roles_with_perm = (
            db.query(Role)
            .join(RolePermission, Role.id == RolePermission.role_id)
            .filter(RolePermission.permission_id == perm.id)
            .all()
        )

        for role in roles_with_perm:
            module_count = (
                db.query(RolePermission)
                .join(Permission, RolePermission.permission_id == Permission.id)
                .filter(
                    RolePermission.role_id == role.id,
                    Permission.module == module,
                    Permission.is_active == True,
                )
                .count()
            )
            if module_count <= 1:
                warnings.append(
                    f"Role '{role.name}' will have zero permissions "
                    f"in module '{module}' after deactivation"
                )

        return warnings

    @staticmethod
    def _invalidate_cache(role_id: Optional[int], scope: str = "all") -> None:
        """Fire-and-forget cache invalidation.

        Uses asyncio.run_coroutine_threadsafe or loop.run_until_complete.
        Failures are silently ignored since the DB remains the source of truth.
        """
        try:
            import asyncio
            from app.core.cache import (
                invalidate_all_permissions,
                invalidate_all_role_permissions,
                invalidate_role_permissions,
            )

            loop = asyncio.get_event_loop()

            if scope == "all" and role_id is None:
                coro = invalidate_all_permissions()
            elif role_id is not None:
                coro = invalidate_role_permissions(role_id)
            else:
                coro = invalidate_all_role_permissions()

            if loop.is_running():
                asyncio.run_coroutine_threadsafe(coro, loop)
            else:
                loop.run_until_complete(coro)
        except Exception:
            # Cache invalidation is best-effort; DB is always the source of truth
            pass


permission_service = PermissionService()

