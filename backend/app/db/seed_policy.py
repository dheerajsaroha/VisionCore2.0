"""
seed_policy.py — Seeder for Policy Center Categories, Default Templates & Compliance Rules
Sprint 4 — Entity 5
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.models.all_models import (
    PolicyCategory, PolicyDocument, PolicyVersion, PolicyDistribution,
    PolicyTemplate, ComplianceRule, PolicyTag, User
)


DEFAULT_POLICY_CATEGORIES = [
    {"name": "HR Policies", "code": "hr", "description": "Human resources policies covering employment, benefits, conduct, and relations."},
    {"name": "IT & Security Policies", "code": "it_security", "description": "Information technology, data security, and acceptable use policies."},
    {"name": "Attendance & Leave Policies", "code": "attendance_leave", "description": "Policies governing attendance, time-off, and leave management."},
    {"name": "Payroll & Compensation Policies", "code": "payroll_comp", "description": "Salary, bonuses, reimbursements, and compensation policies."},
    {"name": "Recruitment & Onboarding Policies", "code": "recruitment", "description": "Hiring, interviewing, and employee onboarding policies."},
    {"name": "Performance Management Policies", "code": "performance", "description": "Performance review, OKR, and PIP policy frameworks."},
    {"name": "Workplace Conduct & Ethics", "code": "conduct", "description": "Code of conduct, anti-harassment, and workplace ethics policies."},
    {"name": "Travel & Expense Policies", "code": "travel_expense", "description": "Business travel, accommodation, and expense reimbursement policies."},
    {"name": "Legal & Compliance Documents", "code": "legal", "description": "Regulatory compliance, legal agreements, and statutory documents."},
    {"name": "Asset & Device Management", "code": "asset", "description": "Company asset allocation, device usage, and return policies."},
]


DEFAULT_COMPLIANCE_RULES = [
    {"name": "Mandatory HR Policy Acknowledgement", "rule_type": "acknowledgement_required",
     "policy_type_filter": "hr_policy", "description": "All employees must acknowledge HR policies upon hire and on updates.", "grace_period_days": 14, "weight": 2.0},
    {"name": "IT Security Policy Acknowledgement", "rule_type": "acknowledgement_required",
     "policy_type_filter": "it_policy", "description": "All employees must acknowledge IT security policies.", "grace_period_days": 7, "weight": 3.0},
    {"name": "Code of Conduct Acknowledgement", "rule_type": "acknowledgement_required",
     "policy_type_filter": "security_policy", "description": "Annual acknowledgement of code of conduct.", "grace_period_days": 30, "weight": 2.5},
    {"name": "Mandatory Attendance Policy Read", "rule_type": "mandatory_read",
     "policy_type_filter": "attendance_policy", "description": "All employees must read attendance policies.", "grace_period_days": 14, "weight": 1.0},
    {"name": "Payroll Policy Acknowledgement", "rule_type": "acknowledgement_required",
     "policy_type_filter": "payroll_policy", "description": "Employees must acknowledge payroll policies.", "grace_period_days": 14, "weight": 1.5},
]


DEFAULT_TEMPLATES = [
    {
        "name": "Employee Code of Conduct",
        "content": "# {company_name} Employee Code of Conduct\n\n## 1. Purpose\nThis Code of Conduct outlines the expected behavior and ethical standards for all employees.\n\n## 2. Scope\nThis policy applies to all employees, contractors, and temporary staff.\n\n## 3. Core Principles\n- Integrity and Honesty\n- Respect and Dignity\n- Compliance with Laws\n- Confidentiality\n- Professional Excellence\n\n## 4. Reporting Violations\nEmployees should report any violations to their manager or HR.\n\n## 5. Disciplinary Action\nViolation of this Code may result in disciplinary action, up to and including termination.\n\n---\n*Document Version: 1.0*\n*Effective Date: {effective_date}*",
        "variables": {"company_name": "Organization Name", "effective_date": "Effective Date"}
    },
    {
        "name": "IT Acceptable Use Policy",
        "content": "# {company_name} IT Acceptable Use Policy\n\n## 1. Purpose\nThis policy defines acceptable use of company technology resources.\n\n## 2. Scope\nApplies to all users of company IT systems.\n\n## 3. Policy\n- Company resources are for business purposes\n- Personal use should be limited\n- No unauthorized access or sharing of credentials\n- All activity may be monitored\n- Report security incidents immediately\n\n## 4. Enforcement\nViolations will result in disciplinary action.\n\n---\n*Effective Date: {effective_date}*",
        "variables": {"company_name": "Organization Name", "effective_date": "Effective Date"}
    },
    {
        "name": "Anti-Harassment Policy",
        "content": "# {company_name} Anti-Harassment Policy\n\n## 1. Policy Statement\n{company_name} is committed to a workplace free from harassment.\n\n## 2. Prohibited Conduct\n- Sexual harassment\n- Discrimination based on protected characteristics\n- Retaliation for reporting\n- Bullying or intimidation\n\n## 3. Reporting Procedure\nContact HR or use the anonymous reporting hotline.\n\n## 4. Investigation\nAll complaints will be investigated promptly and confidentially.\n\n---\n*Effective Date: {effective_date}*",
        "variables": {"company_name": "Organization Name", "effective_date": "Effective Date"}
    }
]


def seed_policy_defaults_for_org(db: Session, org_id: UUID, admin_user_id: int):
    """Seed default policy categories, templates, and compliance rules for an organization."""
    now = datetime.now(timezone.utc)

    # 1. Seed Policy Categories
    existing_cats = db.query(PolicyCategory).filter(PolicyCategory.organization_id == org_id).count()
    if existing_cats == 0:
        for cat_data in DEFAULT_POLICY_CATEGORIES:
            cat = PolicyCategory(
                organization_id=org_id,
                name=cat_data["name"],
                code=cat_data["code"],
                description=cat_data.get("description"),
                is_active=True
            )
            db.add(cat)

    # 2. Seed Policy Templates
    existing_templates = db.query(PolicyTemplate).filter(PolicyTemplate.organization_id == org_id).count()
    if existing_templates == 0:
        for tpl_data in DEFAULT_TEMPLATES:
            template = PolicyTemplate(
                organization_id=org_id,
                name=tpl_data["name"],
                content=tpl_data["content"],
                variables=tpl_data.get("variables"),
                is_active=True,
                created_by_user_id=admin_user_id
            )
            db.add(template)

    # 3. Seed Compliance Rules
    existing_rules = db.query(ComplianceRule).filter(ComplianceRule.organization_id == org_id).count()
    if existing_rules == 0:
        for rule_data in DEFAULT_COMPLIANCE_RULES:
            rule = ComplianceRule(
                organization_id=org_id,
                name=rule_data["name"],
                rule_type=rule_data["rule_type"],
                policy_type_filter=rule_data.get("policy_type_filter"),
                description=rule_data.get("description"),
                grace_period_days=rule_data.get("grace_period_days", 14),
                weight=rule_data.get("weight", 1.0),
                is_active=True,
                created_by_user_id=admin_user_id
            )
            db.add(rule)

    db.commit()
