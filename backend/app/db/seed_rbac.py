"""
seed_rbac.py — Enterprise RBAC Seeder

Seeds 26 roles across 3 tiers (Platform / Organization / System)
with full permission-to-role mappings.

This is designed to be idempotent — safe to run multiple times.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from app.db.models.all_models import (
    Permission,
    Role,
    RolePermission,
)

logger = logging.getLogger(__name__)

# =============================================================================
#  TIER 1 — PLATFORM ROLES (8 roles — cross-tenant, platform-level)
# =============================================================================
PLATFORM_ROLES: Dict[str, Dict] = {
    "SuperAdmin": {
        "description": "Full platform access — all tenants, all features, all settings",
        "is_system": True,
        "permissions": "__all__",  # Special marker: ALL permissions
    },
    "PlatformAdmin": {
        "description": "Platform-level operations — tenant management, billing, platform settings",
        "is_system": True,
        "permissions": [
            "org.view", "org.create", "org.update", "org.delete", "org.deactivate", "org.restore",
            "org.settings.view", "org.settings.manage",
            "billing.view", "billing.manage",
            "audit.view", "audit.export",
            "platform.settings.view", "platform.settings.manage",
            "users.impersonate",
            "notifications.platform",
        ],
    },
    "PlatformViewer": {
        "description": "Read-only platform access — dashboards, audit logs, tenant list",
        "is_system": True,
        "permissions": [
            "org.view", "org.settings.view",
            "audit.view",
            "platform.settings.view",
            "billing.view",
        ],
    },
    "PlatformAuditor": {
        "description": "Audit-specific access — read-only logs, no operational changes",
        "is_system": True,
        "permissions": [
            "audit.view", "audit.export",
            "org.view",
        ],
    },
    "PlatformSupport": {
        "description": "Support-tier access — can impersonate users, view orgs, manage tickets",
        "is_system": True,
        "permissions": [
            "org.view",
            "users.impersonate",
            "tickets.read", "tickets.update",
            "audit.view",
            "notifications.platform",
        ],
    },
    "PlatformBilling": {
        "description": "Billing operations — invoices, subscriptions, payment methods",
        "is_system": True,
        "permissions": [
            "billing.view", "billing.manage",
            "org.view", "org.settings.view",
            "reports.billing",
        ],
    },
    "PlatformDevOps": {
        "description": "Infrastructure & deployment access — feature flags, system settings, maintenance",
        "is_system": True,
        "permissions": [
            "platform.settings.view", "platform.settings.manage",
            "system.maintenance",
            "audit.view",
            "features.manage",
        ],
    },
    "PlatformSecurity": {
        "description": "Security operations — audit logs, security settings, incident management",
        "is_system": True,
        "permissions": [
            "audit.view", "audit.export",
            "security.manage",
            "org.view",
            "users.impersonate",
            "incidents.manage",
            "notifications.platform",
        ],
    },
}

# =============================================================================
#  TIER 2 — ORGANIZATION ROLES (12 roles — tenant-scoped)
# =============================================================================
ORGANIZATION_ROLES: Dict[str, Dict] = {
    "OrgAdmin": {
        "description": "Full organization administration — users, settings, departments, shifts, payroll, policy center",
        "is_system": False,
        "permissions": "__org_admin__",  # All org-level permissions
    },
    "OrgManager": {
        "description": "Organization management — user management, reports, attendance oversight, documents",
        "is_system": False,
        "permissions": [
            "users.read", "users.create", "users.update",
            "attendance.checkin", "attendance.checkout", "attendance.history", "attendance.corrections",
            "departments.read", "departments.update",
            "shifts.read", "shifts.update",
            "reports.attendance.export", "reports.employee.export",
            "tickets.read", "tickets.create", "tickets.update",
            "reimbursements.read", "reimbursements.create", "reimbursements.approve",
            "payroll.generate", "payroll.approve",
            "notifications.read",
            "org.settings.view",
            "policy.read", "policy.acknowledge", "policy.compliance.view",
            "leave.view_self", "leave.view_team", "leave.approve",
        ],
    },
    "OrgHR": {
        "description": "HR operations — employee management, payroll, reimbursements, reports, policy center",
        "is_system": False,
        "permissions": [
            "users.read", "users.create", "users.update",
            "departments.read",
            "shifts.read",
            "reports.attendance.export", "reports.payroll.export", "reports.employee.export",
            "payroll.generate", "payroll.approve", "payroll.export",
            "reimbursements.read", "reimbursements.create", "reimbursements.approve",
            "tickets.read",
            "notifications.read",
            "policy.read", "policy.create", "policy.update", "policy.publish",
            "policy.archive", "policy.acknowledge", "policy.compliance.view",
            "policy.compliance.manage", "policy.reminders.manage", "policy.distribute",
            "policy.analytics.view", "policy.versions.view", "policy.attachments.manage",
            "leave.view_self", "leave.view_team", "leave.view_org", "leave.approve", "leave.manage",
        ],
    },
    "OrgFinance": {
        "description": "Financial operations — payroll, reimbursements, billing reports",
        "is_system": False,
        "permissions": [
            "payroll.generate", "payroll.approve", "payroll.export",
            "reimbursements.read", "reimbursements.create", "reimbursements.approve", "reimbursements.reject",
            "reports.payroll.export",
            "users.read",
            "notifications.read",
        ],
    },
    "OrgSupervisor": {
        "description": "Team supervision — attendance oversight, shift management, team reports",
        "is_system": False,
        "permissions": [
            "attendance.checkin", "attendance.checkout", "attendance.history", "attendance.corrections",
            "shifts.read",
            "departments.read",
            "reports.attendance.export",
            "tickets.read", "tickets.create", "tickets.update",
            "users.read",
            "notifications.read",
            "leave.view_self", "leave.view_team", "leave.approve",
        ],
    },
    "OrgTeamLead": {
        "description": "Team lead — view team attendance, manage tickets, limited reports",
        "is_system": False,
        "permissions": [
            "attendance.history",
            "reports.attendance.export",
            "tickets.read", "tickets.create", "tickets.update",
            "users.read",
            "notifications.read",
            "leave.view_self", "leave.view_team",
        ],
    },
    "OrgEmployee": {
        "description": "Standard employee — self-service attendance, tickets, reimbursements",
        "is_system": False,
        "permissions": [
            "attendance.checkin", "attendance.checkout", "attendance.history",
            "tickets.read", "tickets.create",
            "reimbursements.read", "reimbursements.create",
            "notifications.read",
            "leave.apply", "leave.view_self",
        ],
    },
    "OrgContractor": {
        "description": "External contractor — limited attendance, no payroll access",
        "is_system": False,
        "permissions": [
            "attendance.checkin", "attendance.checkout", "attendance.history",
            "tickets.read", "tickets.create",
            "notifications.read",
            "leave.view_self",
        ],
    },
    "OrgIntern": {
        "description": "Intern — attendance only, read-only tickets",
        "is_system": False,
        "permissions": [
            "attendance.checkin", "attendance.checkout", "attendance.history",
            "tickets.read",
            "notifications.read",
            "leave.view_self",
        ],
    },
    "OrgViewer": {
        "description": "Read-only organization access — dashboards, reports, no mutations",
        "is_system": False,
        "permissions": [
            "attendance.history",
            "reports.attendance.export",
            "tickets.read",
            "users.read",
            "notifications.read",
            "leave.view_self",
        ],
    },
    "OrgDepartmentHead": {
        "description": "Department head — full department oversight, reports, attendance corrections, policies",
        "is_system": False,
        "permissions": [
            "users.read", "users.update",
            "attendance.checkin", "attendance.checkout", "attendance.history", "attendance.corrections",
            "departments.read", "departments.update",
            "shifts.read",
            "reports.attendance.export", "reports.employee.export",
            "tickets.read", "tickets.create", "tickets.update",
            "reimbursements.read", "reimbursements.approve",
            "notifications.read",
            "policy.read", "policy.acknowledge", "policy.compliance.view",
        ],
    },
    "OrgShiftManager": {
        "description": "Shift management — create, update shifts, view attendance",
        "is_system": False,
        "permissions": [
            "shifts.read", "shifts.create", "shifts.update", "shifts.delete",
            "attendance.history",
            "users.read",
            "notifications.read",
        ],
    },
}

# =============================================================================
#  TIER 3 — SYSTEM ROLES (6 roles — internal system accounts)
# =============================================================================
SYSTEM_ROLES: Dict[str, Dict] = {
    "SystemService": {
        "description": "Internal service account — backend-to-backend communication",
        "is_system": True,
        "permissions": [
            "system.health",
            "system.maintenance",
            "attendance.checkin", "attendance.checkout",
            "users.read",
            "audit.write",
        ],
    },
    "SystemDevice": {
        "description": "Edge device account — camera/kiosk check-in only",
        "is_system": True,
        "permissions": [
            "attendance.checkin", "attendance.checkout",
            "users.read",
            "system.health",
        ],
    },
    "SystemWebhook": {
        "description": "Webhook integration — receive and dispatch events",
        "is_system": True,
        "permissions": [
            "system.health",
            "attendance.history",
            "users.read",
            "notifications.read",
        ],
    },
    "SystemCron": {
        "description": "Scheduled job account — payroll generation, report computation, cleanup",
        "is_system": True,
        "permissions": [
            "payroll.generate",
            "reports.attendance.export", "reports.payroll.export",
            "attendance.history",
            "users.read",
            "system.health",
        ],
    },
    "SystemAnalytics": {
        "description": "Analytics engine — read-only data export for BI tools",
        "is_system": True,
        "permissions": [
            "attendance.history",
            "reports.attendance.export", "reports.payroll.export", "reports.employee.export",
            "users.read",
            "system.health",
        ],
    },
    "SystemMigration": {
        "description": "Data migration account — bulk import/export during tenant onboarding",
        "is_system": True,
        "permissions": [
            "users.read", "users.create", "users.update",
            "attendance.history",
            "departments.read", "departments.create", "departments.update",
            "shifts.read", "shifts.create", "shifts.update",
            "system.health",
        ],
    },
}

# =============================================================================
#  ALL PERMISSION DEFINITIONS (organized by module)
# =============================================================================
ALL_PERMISSIONS: Dict[str, Dict[str, List[Tuple[str, str]]]] = {
    "auth": {
        "Platform": [
            ("auth.login", "Authenticate and receive tokens"),
            ("auth.refresh", "Refresh access token"),
            ("auth.logout", "Revoke current session"),
            ("auth.change_password", "Change own password"),
            ("auth.register", "Self-service registration"),
        ],
    },
    "users": {
        "Platform": [
            ("users.read", "View user profiles"),
            ("users.create", "Create new users"),
            ("users.update", "Update user profiles"),
            ("users.delete", "Soft-delete users"),
            ("users.impersonate", "Impersonate another user"),
            ("users.manage", "Full user management"),
        ],
    },
    "org": {
        "Platform": [
            ("org.view", "View organization details"),
            ("org.create", "Create new organizations"),
            ("org.update", "Update organization settings"),
            ("org.delete", "Delete organizations"),
            ("org.deactivate", "Deactivate/restore organizations"),
            ("org.restore", "Restore deactivated organizations"),
            ("org.settings.view", "View organization settings"),
            ("org.settings.manage", "Manage organization settings"),
            ("org.api_keys.manage", "Manage API keys"),
        ],
    },
    "departments": {
        "Platform": [
            ("departments.read", "View departments"),
            ("departments.create", "Create departments"),
            ("departments.update", "Update departments"),
            ("departments.delete", "Delete departments"),
        ],
    },
    "shifts": {
        "Platform": [
            ("shifts.read", "View shifts"),
            ("shifts.create", "Create shifts"),
            ("shifts.update", "Update shifts"),
            ("shifts.delete", "Delete shifts"),
        ],
    },
    "attendance": {
        "Platform": [
            ("attendance.checkin", "Check in"),
            ("attendance.checkout", "Check out"),
            ("attendance.history", "View attendance history"),
            ("attendance.corrections", "Correct attendance records"),
            ("attendance.export", "Export attendance data"),
        ],
    },
    "payroll": {
        "Platform": [
            ("payroll.generate", "Generate payroll"),
            ("payroll.approve", "Approve payroll"),
            ("payroll.export", "Export payroll data"),
            ("payroll.manage", "Full payroll management"),
        ],
    },
    "reimbursements": {
        "Platform": [
            ("reimbursements.read", "View reimbursements"),
            ("reimbursements.create", "Submit reimbursements"),
            ("reimbursements.approve", "Approve reimbursements"),
            ("reimbursements.reject", "Reject reimbursements"),
        ],
    },
    "tickets": {
        "Platform": [
            ("tickets.read", "View tickets"),
            ("tickets.create", "Create tickets"),
            ("tickets.update", "Update tickets"),
            ("tickets.delete", "Delete tickets"),
        ],
    },
    "reports": {
        "Platform": [
            ("reports.attendance.export", "Export attendance reports"),
            ("reports.payroll.export", "Export payroll reports"),
            ("reports.employee.export", "Export employee reports"),
            ("reports.billing", "View billing reports"),
        ],
    },
    "notifications": {
        "Platform": [
            ("notifications.read", "View notifications"),
            ("notifications.send", "Send notifications"),
            ("notifications.platform", "Platform-wide notifications"),
            ("notifications.manage", "Manage notification settings"),
        ],
    },
    "billing": {
        "Platform": [
            ("billing.view", "View billing information"),
            ("billing.manage", "Manage billing and subscriptions"),
        ],
    },
    "audit": {
        "Platform": [
            ("audit.view", "View audit logs"),
            ("audit.export", "Export audit logs"),
            ("audit.write", "Write audit log entries"),
        ],
    },
    "platform": {
        "Platform": [
            ("platform.settings.view", "View platform settings"),
            ("platform.settings.manage", "Manage platform settings"),
            ("features.manage", "Manage feature flags"),
            ("system.maintenance", "System maintenance operations"),
            ("system.health", "System health check"),
        ],
    },
    "security": {
        "Platform": [
            ("security.manage", "Manage security settings"),
            ("incidents.manage", "Manage security incidents"),
        ],
    },
    "roles": {
        "Platform": [
            ("roles.view", "View roles and permissions"),
            ("roles.create", "Create custom roles"),
            ("roles.update", "Update role permissions"),
            ("roles.delete", "Delete custom roles"),
            ("roles.assign", "Assign roles to users"),
        ],
    },
    "policy": {
        "Platform": [
            ("policy.create", "Create policy documents"),
            ("policy.read", "View policy documents"),
            ("policy.update", "Update policy documents"),
            ("policy.delete", "Delete policy documents"),
            ("policy.publish", "Publish policy documents"),
            ("policy.archive", "Archive policy documents"),
            ("policy.acknowledge", "Acknowledge policy documents"),
            ("policy.sign", "Digitally sign policy documents"),
            ("policy.distribute", "Distribute policy documents"),
            ("policy.compliance.view", "View compliance records"),
            ("policy.compliance.manage", "Manage compliance rules"),
            ("policy.reminders.manage", "Manage policy reminders"),
            ("policy.templates.manage", "Manage policy templates"),
            ("policy.versions.view", "View policy version history"),
            ("policy.attachments.manage", "Manage policy attachments"),
            ("policy.categories.manage", "Manage policy categories"),
            ("policy.tags.manage", "Manage policy tags"),
            ("policy.analytics.view", "View policy analytics"),
        ],
    },
    "asset": {
        "Platform": [
            ("asset.create", "Create new assets in inventory"),
            ("asset.read", "View asset details and inventory"),
            ("asset.update", "Update asset information"),
            ("asset.delete", "Remove assets from inventory"),
            ("asset.assign", "Assign assets to employees/departments"),
            ("asset.transfer", "Transfer assets between assignments"),
            ("asset.return", "Process asset returns"),
            ("asset.maintenance", "Manage asset maintenance and repairs"),
            ("asset.audit", "Perform and manage asset audits"),
            ("asset.export", "Export asset data and reports"),
            ("asset.manage", "Full asset management access"),
        ],
    },
    "leave": {
        "Platform": [
            ("leave.apply", "Submit leave request"),
            ("leave.view_self", "View own leave requests"),
            ("leave.view_team", "View team leave requests"),
            ("leave.view_org", "View organization leave"),
            ("leave.approve", "Approve leave requests"),
            ("leave.reject", "Reject leave requests"),
            ("leave.cancel", "Cancel leave requests"),
            ("leave.manage", "Full leave management"),
        ],
    },
    "succession": {
        "Platform": [
            ("succession.view", "View succession plans"),
            ("succession.create", "Create succession plans"),
            ("succession.update", "Update succession plans"),
            ("succession.manage", "Full succession management"),
        ],
    },
    "learning": {
        "Platform": [
            ("learning.view", "View courses and enrollments"),
            ("learning.create", "Create courses"),
            ("learning.update", "Update courses"),
            ("learning.manage", "Full learning management"),
        ],
    },
    "performance": {
        "Platform": [
            ("performance.view", "View performance data"),
            ("performance.create", "Create performance cycles"),
            ("performance.update", "Update performance reviews"),
            ("performance.manage", "Full performance management"),
        ],
    },
    "recruitment": {
        "Platform": [
            ("recruitment.view", "View recruitment data"),
            ("recruitment.create", "Create job postings"),
            ("recruitment.update", "Update recruitment records"),
            ("recruitment.manage", "Full recruitment management"),
        ],
    },
    "hcm": {
        "Platform": [
            ("hcm.view", "View HCM data"),
            ("hcm.update", "Update HCM records"),
            ("hcm.manage", "Full HCM management"),
        ],
    },
    "workforce": {
        "Platform": [
            ("workforce.view", "View workforce data"),
            ("workforce.manage", "Manage workforce operations"),
        ],
    },
}

# =============================================================================
#  FLAT PERMISSION LIST (for validation and all-permission assignment)
# =============================================================================
def _flatten_permissions() -> List[str]:
    """Return a flat list of all permission names."""
    flat = []
    for module, groups in ALL_PERMISSIONS.items():
        for _group, perms in groups.items():
            for perm_name, _desc in perms:
                flat.append(perm_name)
    return sorted(set(flat))


# =============================================================================
#  ORG-ADMIN PERMISSION LIST (all org-level permissions)
# =============================================================================
def _org_admin_permissions() -> List[str]:
    """Return all permissions that are org-scoped (not platform-only)."""
    platform_only = {
        "org.create", "org.delete", "org.deactivate", "org.restore",
        "billing.view", "billing.manage",
        "audit.view", "audit.export", "audit.write",
        "platform.settings.view", "platform.settings.manage",
        "features.manage",
        "system.maintenance", "system.health",
        "security.manage", "incidents.manage",
        "users.impersonate",
        "notifications.platform",
        "reports.billing",
    }
    return [p for p in _flatten_permissions() if p not in platform_only]


ALL_PERMISSION_NAMES = _flatten_permissions()
ORG_ADMIN_PERMISSION_NAMES = _org_admin_permissions()


# =============================================================================
#  SEEDING FUNCTIONS
# =============================================================================
def seed_permissions(db: Session) -> Dict[str, int]:
    """Seed all permission definitions idempotently. Returns {name: id} map."""
    perm_map = {}
    for module, groups in ALL_PERMISSIONS.items():
        for group, perms in groups.items():
            for perm_name, perm_desc in perms:
                existing = db.query(Permission).filter(Permission.name == perm_name).first()
                if existing:
                    # Update description if changed
                    if existing.description != perm_desc:
                        existing.description = perm_desc
                        db.add(existing)
                    perm_map[perm_name] = existing.id
                else:
                    perm = Permission(
                        name=perm_name,
                        description=perm_desc,
                        module=module,
                        group=group,
                        is_active=True,
                    )
                    db.add(perm)
                    db.flush()
                    perm_map[perm_name] = perm.id
    db.commit()
    logger.info("Seeded %d permissions", len(perm_map))
    return perm_map


def seed_roles(db: Session, perm_map: Dict[str, int]) -> Dict[str, int]:
    """Seed all 26 roles idempotently. Returns {name: id} map."""
    all_roles = {}
    all_roles.update({f"PLATFORM:{k}": v for k, v in PLATFORM_ROLES.items()})
    all_roles.update({f"ORG:{k}": v for k, v in ORGANIZATION_ROLES.items()})
    all_roles.update({f"SYSTEM:{k}": v for k, v in SYSTEM_ROLES.items()})

    role_map = {}

    # Process roles in order: Platform → Organization → System
    for tier_name, roles_dict, tier_value in [
        ("Platform", PLATFORM_ROLES, "platform"),
        ("Organization", ORGANIZATION_ROLES, "organization"),
        ("System", SYSTEM_ROLES, "system"),
    ]:
        for role_name, role_def in roles_dict.items():
            existing = db.query(Role).filter(Role.name == role_name).first()
            if existing:
                # Update fields
                if existing.description != role_def["description"]:
                    existing.description = role_def["description"]
                if existing.tier != tier_value:
                    existing.tier = tier_value
                if existing.is_system != role_def["is_system"]:
                    existing.is_system = role_def["is_system"]
                db.add(existing)
                role_map[role_name] = existing.id
            else:
                role = Role(
                    name=role_name,
                    description=role_def["description"],
                    tier=tier_value,
                    is_system=role_def["is_system"],
                )
                db.add(role)
                db.flush()
                role_map[role_name] = role.id

    db.commit()
    logger.info("Seeded %d roles", len(role_map))
    return role_map


def seed_role_permissions(db: Session, role_map: Dict[str, int], perm_map: Dict[str, int]) -> int:
    """Map roles to permissions. Returns count of role-permission links created."""
    count = 0

    # Platform roles
    for role_name, role_def in PLATFORM_ROLES.items():
        role_id = role_map[role_name]
        target_perms = _resolve_role_permissions(role_name, role_def, perm_map)
        count += _assign_permissions_to_role(db, role_id, target_perms)

    # Organization roles
    for role_name, role_def in ORGANIZATION_ROLES.items():
        role_id = role_map[role_name]
        target_perms = _resolve_role_permissions(role_name, role_def, perm_map)
        count += _assign_permissions_to_role(db, role_id, target_perms)

    # System roles
    for role_name, role_def in SYSTEM_ROLES.items():
        role_id = role_map[role_name]
        target_perms = _resolve_role_permissions(role_name, role_def, perm_map)
        count += _assign_permissions_to_role(db, role_id, target_perms)

    db.commit()
    logger.info("Assigned %d role-permission links", count)
    return count


def _resolve_role_permissions(
    role_name: str,
    role_def: Dict,
    perm_map: Dict[str, int],
) -> List[int]:
    """Resolve a role's permission definition to a list of permission IDs."""
    perms = role_def["permissions"]
    if perms == "__all__":
        return list(perm_map.values())
    elif perms == "__org_admin__":
        return [perm_map[p] for p in ORG_ADMIN_PERMISSION_NAMES if p in perm_map]
    else:
        return [perm_map[p] for p in perms if p in perm_map]


def _assign_permissions_to_role(db: Session, role_id: int, perm_ids: List[int]) -> int:
    """Assign permissions to a role idempotently. Returns count of new assignments."""
    count = 0
    for perm_id in perm_ids:
        existing = db.query(RolePermission).filter(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == perm_id,
        ).first()
        if not existing:
            rp = RolePermission(role_id=role_id, permission_id=perm_id)
            db.add(rp)
            count += 1
    return count


def seed_all(db: Session) -> Dict[str, int]:
    """Run the full RBAC seeding pipeline. Returns stats."""
    logger.info("=== RBAC Seeding Started ===")

    # Step 1: Seed permissions
    perm_map = seed_permissions(db)
    logger.info("Permissions seeded: %d", len(perm_map))

    # Step 2: Seed roles
    role_map = seed_roles(db, perm_map)
    logger.info("Roles seeded: %d", len(role_map))

    # Step 3: Seed role-permission mappings
    link_count = seed_role_permissions(db, role_map, perm_map)
    logger.info("Role-permission links: %d", link_count)

    total = len(perm_map) + len(role_map) + link_count
    logger.info("=== RBAC Seeding Complete: %d total records ===", total)

    return {
        "permissions": len(perm_map),
        "roles": len(role_map),
        "links": link_count,
        "total": total,
    }


def validate_rbac_seed(db: Session) -> List[str]:
    """Validate the seeded RBAC data. Returns list of issues found."""
    issues = []

    # Check all roles exist
    for role_name in list(PLATFORM_ROLES.keys()) + list(ORGANIZATION_ROLES.keys()) + list(SYSTEM_ROLES.keys()):
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            issues.append(f"Missing role: {role_name}")

    # Check all permissions exist
    for perm_name in ALL_PERMISSION_NAMES:
        perm = db.query(Permission).filter(Permission.name == perm_name).first()
        if not perm:
            issues.append(f"Missing permission: {perm_name}")

    # Check SuperAdmin has all permissions
    sa = db.query(Role).filter(Role.name == "SuperAdmin").first()
    if sa:
        sa_count = db.query(RolePermission).filter(RolePermission.role_id == sa.id).count()
        expected = len(ALL_PERMISSION_NAMES)
        if sa_count != expected:
            issues.append(f"SuperAdmin has {sa_count}/{expected} permissions")

    if not issues:
        logger.info("RBAC validation passed — all %d roles and %d permissions correct",
                    len(list(PLATFORM_ROLES.keys()) + list(ORGANIZATION_ROLES.keys()) + list(SYSTEM_ROLES.keys())),
                    len(ALL_PERMISSION_NAMES))

    return issues
