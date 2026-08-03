"""
seed_scope.py — Enterprise Data Scope & Resource Ownership Seeder

Seeds:
- 11 core enterprise data scopes (platform through custom)
- Default role data scope mappings for standard system roles
- Default resource ownership rules
- Default enterprise ownership policies

Idempotent — safe to execute repeatedly.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.db.models.all_models import (
    DataScope,
    RoleDataScope,
    Role,
    OwnershipRule,
    OwnershipPolicy,
)

logger = logging.getLogger(__name__)

# =============================================================================
#  DATA SCOPE DEFINITIONS
# =============================================================================

DATA_SCOPES: List[Dict] = [
    {
        "code": "platform",
        "name": "Platform Wide Scope",
        "description": "Full access across all tenant organizations, systems, and global data.",
        "scope_level": 100,
    },
    {
        "code": "multi_org",
        "name": "Multi Organization Scope",
        "description": "Access across multiple specified tenant organizations.",
        "scope_level": 90,
    },
    {
        "code": "organization",
        "name": "Organization Scope",
        "description": "Access across all entities within the user's tenant organization.",
        "scope_level": 80,
    },
    {
        "code": "business_unit",
        "name": "Business Unit Scope",
        "description": "Access across all departments within the user's business unit.",
        "scope_level": 70,
    },
    {
        "code": "department",
        "name": "Department Scope",
        "description": "Access restricted to entities within the user's department.",
        "scope_level": 60,
    },
    {
        "code": "team",
        "name": "Team Scope",
        "description": "Access restricted to entities within the user's direct team.",
        "scope_level": 50,
    },
    {
        "code": "project",
        "name": "Project Scope",
        "description": "Access restricted to assigned project teams and tasks.",
        "scope_level": 40,
    },
    {
        "code": "location",
        "name": "Location Scope",
        "description": "Access restricted to physical site or geographic office location.",
        "scope_level": 30,
    },
    {
        "code": "reporting_hierarchy",
        "name": "Reporting Hierarchy Scope",
        "description": "Access to self and all direct and indirect subordinates.",
        "scope_level": 20,
    },
    {
        "code": "self",
        "name": "Self / Individual Scope",
        "description": "Access restricted exclusively to resources created by or belonging to the user.",
        "scope_level": 10,
    },
    {
        "code": "custom",
        "name": "Custom Dynamic Scope",
        "description": "Custom parameter-driven filtering scope.",
        "scope_level": 0,
    },
]

DEFAULT_OWNERSHIP_RULES: List[Dict] = [
    {
        "entity_type": "employee",
        "name": "Employee Profile Default Rule",
        "default_owner_type": "subject",
        "auto_assign_creator": True,
        "auto_assign_manager": True,
        "rule_config": {"track_history": True},
    },
    {
        "entity_type": "attendance",
        "name": "Attendance Check-in Default Rule",
        "default_owner_type": "subject",
        "auto_assign_creator": True,
        "auto_assign_manager": True,
        "rule_config": {"auto_delegate_approvers": True},
    },
    {
        "entity_type": "leave",
        "name": "Leave Application Default Rule",
        "default_owner_type": "creator",
        "auto_assign_creator": True,
        "auto_assign_manager": True,
        "rule_config": {"require_manager_approval": True},
    },
    {
        "entity_type": "payroll",
        "name": "Payroll Record Rule",
        "default_owner_type": "organization",
        "auto_assign_creator": False,
        "auto_assign_manager": False,
        "rule_config": {"confidential": True},
    },
    {
        "entity_type": "document",
        "name": "Document Rule",
        "default_owner_type": "creator",
        "auto_assign_creator": True,
        "auto_assign_manager": False,
        "rule_config": {},
    },
]


def seed_data_scopes(db: Session) -> Dict[str, int]:
    """Seed data scope catalog. Returns map of code -> id."""
    scope_map = {}
    for scope_def in DATA_SCOPES:
        existing = db.query(DataScope).filter(DataScope.code == scope_def["code"]).first()
        if existing:
            existing.name = scope_def["name"]
            existing.description = scope_def["description"]
            existing.scope_level = scope_def["scope_level"]
            db.add(existing)
            scope_map[scope_def["code"]] = existing.id
        else:
            scope = DataScope(**scope_def)
            db.add(scope)
            db.flush()
            scope_map[scope_def["code"]] = scope.id
    db.commit()
    logger.info("Seeded %d data scopes", len(scope_map))
    return scope_map


def seed_default_role_data_scopes(db: Session, scope_map: Dict[str, int]) -> int:
    """Seed default role data scopes for standard system roles."""
    roles = db.query(Role).all()
    role_by_name = {r.name: r.id for r in roles}

    defaults = [
        ("SuperAdmin", "platform"),
        ("OrgAdmin", "organization"),
        ("DepartmentManager", "department"),
        ("OrgEmployee", "self"),
    ]

    count = 0
    for role_name, scope_code in defaults:
        role_id = role_by_name.get(role_name)
        scope_id = scope_map.get(scope_code)
        if role_id and scope_id:
            existing = db.query(RoleDataScope).filter(
                RoleDataScope.role_id == role_id,
                RoleDataScope.permission_id.is_(None),
                RoleDataScope.organization_id.is_(None),
            ).first()
            if not existing:
                rds = RoleDataScope(
                    role_id=role_id,
                    data_scope_id=scope_id,
                    permission_id=None,
                    organization_id=None,
                    scope_parameters={},
                )
                db.add(rds)
                count += 1
    db.commit()
    logger.info("Seeded %d default role-data-scope bindings", count)
    return count


def seed_ownership_rules(db: Session) -> int:
    """Seed standard ownership rules."""
    count = 0
    for rdef in DEFAULT_OWNERSHIP_RULES:
        existing = db.query(OwnershipRule).filter(OwnershipRule.entity_type == rdef["entity_type"]).first()
        if not existing:
            rule = OwnershipRule(**rdef)
            db.add(rule)
            count += 1
    db.commit()
    logger.info("Seeded %d ownership rules", count)
    return count


def seed_ownership_policies(db: Session) -> int:
    """Seed default system ownership policy."""
    existing = db.query(OwnershipPolicy).filter(OwnershipPolicy.organization_id.is_(None)).first()
    if not existing:
        policy = OwnershipPolicy(
            organization_id=None,
            name="Default Global Ownership Policy",
            max_delegation_days=30,
            allow_cross_dept_delegation=True,
            require_approval_for_transfer=False,
            policy_config={"notify_delegator": True},
        )
        db.add(policy)
        db.commit()
        logger.info("Seeded default global ownership policy")
        return 1
    return 0


def seed_all_scope_data(db: Session) -> Dict[str, int]:
    """Master seeder function for Scope & Ownership subsystem."""
    scope_map = seed_data_scopes(db)
    seed_default_role_data_scopes(db, scope_map)
    seed_ownership_rules(db)
    seed_ownership_policies(db)
    return scope_map
