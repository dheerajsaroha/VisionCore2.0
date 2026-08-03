"""
seed_workflow.py — Enterprise Approval Workflow Blueprints Seeder
Sprint 2 — Entity 4
"""
from __future__ import annotations
import logging
from sqlalchemy.orm import Session
from app.crud import crud_workflow
from app.db.models.all_models import (
    ApprovalWorkflow, ApprovalStage, ApprovalStageApprover,
    ApprovalTemplate, Role
)

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES = [
    {
        "code": "leave_approval_template",
        "name": "Standard Leave Approval Template",
        "entity_type": "leave",
        "description": "2-stage approval: Line Manager -> HR Admin",
        "template_json": {
            "stages": [
                {"stage_order": 1, "name": "Manager Approval", "approval_type": "single", "approver_type": "manager", "sla_hours": 24},
                {"stage_order": 2, "name": "HR Approval", "approval_type": "single", "approver_type": "role", "role_name": "OrgAdmin", "sla_hours": 48}
            ]
        }
    },
    {
        "code": "attendance_correction_template",
        "name": "Attendance Correction Blueprint",
        "entity_type": "attendance",
        "description": "1-stage Manager Approval with auto-approve < 15 min delta",
        "template_json": {
            "stages": [
                {
                    "stage_order": 1, "name": "Manager Approval", "approval_type": "single",
                    "approver_type": "manager", "sla_hours": 12,
                    "auto_approve_condition": {"field": "delta_minutes", "value": 10}
                }
            ]
        }
    },
    {
        "code": "expense_claim_template",
        "name": "Expense & Reimbursement Blueprint",
        "entity_type": "expense",
        "description": "Sequential 2-stage approval: Dept Head -> Finance Admin",
        "template_json": {
            "stages": [
                {"stage_order": 1, "name": "Department Head Approval", "approval_type": "single", "approver_type": "dept_head", "sla_hours": 24},
                {"stage_order": 2, "name": "Finance Approval", "approval_type": "single", "approver_type": "role", "role_name": "OrgAdmin", "sla_hours": 48}
            ]
        }
    },
    {
        "code": "payroll_approval_template",
        "name": "Payroll Execution Workflow",
        "entity_type": "payroll",
        "description": "Parallel 2-role approval: Finance Admin & SuperAdmin",
        "template_json": {
            "stages": [
                {"stage_order": 1, "name": "Executive Payroll Verification", "approval_type": "parallel", "min_approvals": 2, "approver_type": "role", "role_name": "SuperAdmin", "sla_hours": 72}
            ]
        }
    },
    {
        "code": "asset_request_template",
        "name": "IT Asset Allocation Blueprint",
        "entity_type": "asset",
        "description": "1-stage IT Admin approval",
        "template_json": {
            "stages": [
                {"stage_order": 1, "name": "IT Logistics Approval", "approval_type": "single", "approver_type": "role", "role_name": "OrgAdmin", "sla_hours": 24}
            ]
        }
    },
    {
        "code": "exit_clearance_template",
        "name": "Employee Exit Clearance Blueprint",
        "entity_type": "exit",
        "description": "Multi-stage department clearance",
        "template_json": {
            "stages": [
                {"stage_order": 1, "name": "Manager Handover", "approval_type": "single", "approver_type": "manager", "sla_hours": 48},
                {"stage_order": 2, "name": "HR Final Signoff", "approval_type": "single", "approver_type": "role", "role_name": "OrgAdmin", "sla_hours": 48}
            ]
        }
    }
]

def seed_templates(db: Session) -> int:
    seeded = 0
    for t_def in DEFAULT_TEMPLATES:
        existing = db.query(ApprovalTemplate).filter(ApprovalTemplate.code == t_def["code"]).first()
        if not existing:
            crud_workflow.create_template(db, t_def)
            seeded += 1
    return seeded

def seed_default_workflows(db: Session) -> int:
    seeded = 0
    roles = {r.name: r for r in db.query(Role).all()}
    sa_role = roles.get("SuperAdmin")
    oa_role = roles.get("OrgAdmin")

    for t_def in DEFAULT_TEMPLATES:
        wf_code = t_def["code"].replace("_template", "_default_wf")
        existing = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.code == wf_code).first()
        if existing:
            continue

        stages_in = []
        for s in t_def["template_json"]["stages"]:
            appr_role = sa_role if s.get("role_name") == "SuperAdmin" else oa_role
            stages_in.append({
                "stage_order": s["stage_order"],
                "name": s["name"],
                "approval_type": s.get("approval_type", "single"),
                "min_approvals": s.get("min_approvals", 1),
                "sla_hours": s.get("sla_hours", 24),
                "auto_approve_condition": s.get("auto_approve_condition", {}),
                "approvers": [
                    {
                        "approver_type": s["approver_type"],
                        "approver_role_id": appr_role.id if appr_role else None,
                        "sequence_order": 1
                    }
                ]
            })

        crud_workflow.create_workflow(db, {
            "code": wf_code,
            "name": t_def["name"],
            "entity_type": t_def["entity_type"],
            "description": t_def["description"],
            "organization_id": None,  # Global default
            "stages": stages_in
        })
        seeded += 1

    return seeded

def seed_all_workflows(db: Session) -> dict:
    t_count = seed_templates(db)
    wf_count = seed_default_workflows(db)
    logger.info(f"Seeded {t_count} templates and {wf_count} default workflows")
    return {"templates_seeded": t_count, "workflows_seeded": wf_count}
