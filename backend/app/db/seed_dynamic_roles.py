"""
seed_dynamic_roles.py — Enterprise Built-in Role Blueprint Templates Seeder
Sprint 2 — Entity 5
"""
from __future__ import annotations
import logging
from sqlalchemy.orm import Session
from app.crud import crud_dynamic_role
from app.db.models.all_models import RoleTemplate

logger = logging.getLogger(__name__)

DEFAULT_ROLE_TEMPLATES = [
    {
        "code": "org_admin_template",
        "name": "Organization Administrator Blueprint",
        "category": "admin",
        "description": "Full administrative control over organization settings, employees, and roles",
        "template_config": {
            "permissions": ["*"],
            "data_scopes": {"scope_level": "organization"},
            "approval_rights": ["*"],
            "features": ["*"]
        }
    },
    {
        "code": "hr_manager_template",
        "name": "HR Manager Blueprint",
        "category": "hr",
        "description": "Full HR operations, attendance overrides, leave approvals, and recruitment",
        "template_config": {
            "permissions": ["employee.read", "employee.write", "attendance.read", "attendance.override", "leave.approve", "recruitment.manage"],
            "data_scopes": {"scope_level": "organization"},
            "approval_rights": ["leave", "attendance_correction", "exit_clearance"],
            "features": ["advanced_analytics", "biometric_sync"]
        }
    },
    {
        "code": "hr_executive_template",
        "name": "HR Executive Blueprint",
        "category": "hr",
        "description": "Day-to-day employee record updates and leave processing",
        "template_config": {
            "permissions": ["employee.read", "attendance.read", "leave.process"],
            "data_scopes": {"scope_level": "department"},
            "approval_rights": ["leave"],
            "features": ["biometric_sync"]
        }
    },
    {
        "code": "recruiter_template",
        "name": "Recruiter & Talent Blueprint",
        "category": "hr",
        "description": "Candidate onboarding and referral verification",
        "template_config": {
            "permissions": ["recruitment.read", "recruitment.write", "referral.verify"],
            "data_scopes": {"scope_level": "department"},
            "approval_rights": ["referral"],
            "features": ["advanced_analytics"]
        }
    },
    {
        "code": "finance_manager_template",
        "name": "Finance Manager Blueprint",
        "category": "finance",
        "description": "Payroll execution, reimbursement sign-off, and expense auditing",
        "template_config": {
            "permissions": ["payroll.read", "payroll.execute", "reimbursement.approve", "expense.audit"],
            "data_scopes": {"scope_level": "organization"},
            "approval_rights": ["expense", "payroll"],
            "features": ["payroll_export"]
        }
    },
    {
        "code": "payroll_officer_template",
        "name": "Payroll Officer Blueprint",
        "category": "finance",
        "description": "Payslip generation and reimbursement claim review",
        "template_config": {
            "permissions": ["payroll.read", "reimbursement.read"],
            "data_scopes": {"scope_level": "organization"},
            "approval_rights": ["expense"],
            "features": ["payroll_export"]
        }
    },
    {
        "code": "dept_manager_template",
        "name": "Department Manager Blueprint",
        "category": "admin",
        "description": "Managerial sign-off for department team members",
        "template_config": {
            "permissions": ["employee.read", "attendance.read", "leave.approve"],
            "data_scopes": {"scope_level": "department"},
            "approval_rights": ["leave", "attendance_correction"],
            "features": ["biometric_sync"]
        }
    },
    {
        "code": "it_admin_template",
        "name": "IT Administrator Blueprint",
        "category": "admin",
        "description": "Hardware asset allocation, device sync, and IT support",
        "template_config": {
            "permissions": ["asset.manage", "device.sync", "support.ticket.manage"],
            "data_scopes": {"scope_level": "organization"},
            "approval_rights": ["asset"],
            "features": ["biometric_sync"]
        }
    },
    {
        "code": "security_officer_template",
        "name": "Security & Audit Officer Blueprint",
        "category": "security",
        "description": "Immutable audit log review and ZKP verification monitoring",
        "template_config": {
            "permissions": ["audit.read", "security.inspect", "report.generate"],
            "data_scopes": {"scope_level": "organization"},
            "approval_rights": [],
            "features": ["audit_trail"]
        }
    },
    {
        "code": "employee_template",
        "name": "Standard Employee Blueprint",
        "category": "employee",
        "description": "Self-service attendance clocking, leave submission, and payslip viewing",
        "template_config": {
            "permissions": ["attendance.history", "leave.submit", "expense.submit", "payroll.view_own"],
            "data_scopes": {"scope_level": "self"},
            "approval_rights": [],
            "features": []
        }
    },
    {
        "code": "intern_template",
        "name": "Intern & Trainee Blueprint",
        "category": "employee",
        "description": "Restricted self-service for interns and trainees",
        "template_config": {
            "permissions": ["attendance.history", "leave.submit"],
            "data_scopes": {"scope_level": "self"},
            "approval_rights": [],
            "features": []
        }
    },
    {
        "code": "contractor_template",
        "name": "Contractor & External Consultant Blueprint",
        "category": "employee",
        "description": "External consultant portal access",
        "template_config": {
            "permissions": ["attendance.history"],
            "data_scopes": {"scope_level": "self"},
            "approval_rights": [],
            "features": []
        }
    }
]

def seed_role_templates(db: Session) -> int:
    seeded = 0
    for t_def in DEFAULT_ROLE_TEMPLATES:
        existing = db.query(RoleTemplate).filter(RoleTemplate.code == t_def["code"]).first()
        if not existing:
            crud_dynamic_role.create_template(db, t_def)
            seeded += 1
    logger.info(f"Seeded {seeded} role templates")
    return seeded
