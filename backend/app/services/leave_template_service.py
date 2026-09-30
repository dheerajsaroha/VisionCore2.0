"""
Leave templates — the organization chooses its starting set of leave types.

Leave types used to be a hardcoded list pushed into every tenant on first
access, so every organization received the same six types, including 180 days
of maternity leave. The set an organization offers depends on its sector and
region, so it is now the organization's decision.

The catalogue below is a starting point, not a legal opinion. Day counts must be
checked against the jurisdiction an organization actually operates in, which is
why they are data an admin can edit rather than constants in code.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.all_models import LeaveTemplate, LeaveTemplateItem, LeaveType

# Each entry: code, name, description, and the LeaveType configuration it creates.
LEAVE_TEMPLATES: List[Dict[str, Any]] = [
    {
        "code": "IN_STATUTORY",
        "name": "India — Statutory & Earned",
        "region": "IN",
        "description": (
            "Earned leave with maternity and paternity as statutory entitlements, "
            "suitable for an Indian establishment. Confirm maternity benefit "
            "eligibility separately; this sets the leave ledger only."
        ),
        "is_default": True,
        "items": [
            {
                "code": "EL", "name": "Earned Leave",
                "description": "Accrued annual leave as per the Shops and Establishments rules",
                "max_days_per_year": 18.0, "max_days_per_request": 6.0,
                "carry_forward": True, "max_carry_forward_days": 30.0,
                "requires_document": False, "min_notice_days": 7, "is_paid": True,
            },
            {
                "code": "SL", "name": "Sick Leave",
                "description": "Leave on account of illness or injury",
                "max_days_per_year": 12.0, "max_days_per_request": 12.0,
                "carry_forward": False, "max_carry_forward_days": 0.0,
                "requires_document": True, "min_notice_days": 0, "is_paid": True,
            },
            {
                "code": "CL", "name": "Casual Leave",
                "description": "Short-term absence for personal reasons",
                "max_days_per_year": 10.0, "max_days_per_request": 3.0,
                "carry_forward": False, "max_carry_forward_days": 0.0,
                "requires_document": False, "min_notice_days": 1, "is_paid": True,
            },
            {
                "code": "MATERNITY", "name": "Maternity Leave",
                "description": "Statutory maternity leave for female employees",
                "max_days_per_year": 180.0, "max_days_per_request": 180.0,
                "carry_forward": False, "max_carry_forward_days": 0.0,
                "requires_document": True, "min_notice_days": 30, "is_paid": True,
                "gender_specific": "female",
            },
            {
                "code": "PATERNITY", "name": "Paternity Leave",
                "description": "Paternity leave for male employees",
                "max_days_per_year": 15.0, "max_days_per_request": 15.0,
                "carry_forward": False, "max_carry_forward_days": 0.0,
                "requires_document": False, "min_notice_days": 7, "is_paid": True,
                "gender_specific": "male",
            },
        ],
    },
    {
        "code": "UK_STANDARD",
        "name": "United Kingdom — Standard",
        "region": "UK",
        "description": (
            "Statutory minimum plus a typical employer enhancement: 5.6 weeks of "
            "holiday, sick pay, and family leave."
        ),
        "is_default": False,
        "items": [
            {
                "code": "HOLIDAY", "name": "Holiday Leave",
                "description": "Annual holiday including the statutory 5.6 weeks",
                "max_days_per_year": 28.0, "max_days_per_request": 14.0,
                "carry_forward": False, "max_carry_forward_days": 0.0,
                "requires_document": False, "min_notice_days": 7, "is_paid": True,
            },
            {
                "code": "SICK", "name": "Sick Leave",
                "description": "Statutory Sick Pay",
                "max_days_per_year": 28.0, "max_days_per_request": 28.0,
                "carry_forward": False, "max_carry_forward_days": 0.0,
                "requires_document": True, "min_notice_days": 0, "is_paid": True,
            },
            {
                "code": "FAMILY", "name": "Family Leave",
                "description": "Shared parental leave, parental bereavement, and dependants' leave",
                "max_days_per_year": 37.0, "max_days_per_request": 37.0,
                "carry_forward": False, "max_carry_forward_days": 0.0,
                "requires_document": True, "min_notice_days": 14, "is_paid": True,
            },
        ],
    },
    {
        "code": "US_STANDARD",
        "name": "United States — Standard",
        "region": "US",
        "description": (
            "Paid time off, sick time, and family medical leave. Note that FMLA is "
            "an entitlement rather than an accrued balance and is administered "
            "separately."
        ),
        "is_default": False,
        "items": [
            {
                "code": "PTO", "name": "Paid Time Off",
                "description": "Accrued vacation and personal time",
                "max_days_per_year": 15.0, "max_days_per_request": 10.0,
                "carry_forward": True, "max_carry_forward_days": 10.0,
                "requires_document": False, "min_notice_days": 3, "is_paid": True,
            },
            {
                "code": "SICK", "name": "Sick Leave",
                "description": "Accrued sick time",
                "max_days_per_year": 8.0, "max_days_per_request": 8.0,
                "carry_forward": False, "max_carry_forward_days": 0.0,
                "requires_document": True, "min_notice_days": 0, "is_paid": True,
            },
            {
                "code": "FAMILY", "name": "Family Medical Leave",
                "description": "Leave for a serious family health condition",
                "max_days_per_year": 60.0, "max_days_per_request": 60.0,
                "carry_forward": False, "max_carry_forward_days": 0.0,
                "requires_document": True, "min_notice_days": 30, "is_paid": True,
            },
        ],
    },
    {
        "code": "TECH_EXEMPT",
        "name": "Knowledge Worker / Exempt",
        "region": None,
        "description": (
            "Flexible time off for a professional workforce: unlimited paid time off, "
            "plus explicit sick and parental leave. Unlimited types are recorded as 0 "
            "entitlement with policy set to allow a negative balance."
        ),
        "is_default": False,
        "items": [
            {
                "code": "PTO", "name": "Paid Time Off",
                "description": "Discretionary paid time off",
                "max_days_per_year": 0.0, "max_days_per_request": None,
                "carry_forward": False, "max_carry_forward_days": 0.0,
                "requires_document": False, "min_notice_days": 0, "is_paid": True,
            },
            {
                "code": "SICK", "name": "Sick Leave",
                "description": "Paid sick leave, separate from discretionary time off",
                "max_days_per_year": 10.0, "max_days_per_request": 10.0,
                "carry_forward": False, "max_carry_forward_days": 0.0,
                "requires_document": False, "min_notice_days": 0, "is_paid": True,
            },
            {
                "code": "PARENTAL", "name": "Parental Leave",
                "description": "Equal, available to any parent",
                "max_days_per_year": 60.0, "max_days_per_request": 60.0,
                "carry_forward": False, "max_carry_forward_days": 0.0,
                "requires_document": False, "min_notice_days": 14, "is_paid": True,
            },
        ],
    },
    {
        "code": "MINIMAL",
        "name": "Minimal — No Paid Leave",
        "region": None,
        "description": (
            "Unpaid leave only, for an organization that offers no paid entitlement. "
            "Use for organizations that record time off as unpaid."
        ),
        "is_default": False,
        "items": [
            {
                "code": "UNPAID", "name": "Unpaid Leave",
                "description": "Approved absence recorded as unpaid",
                "max_days_per_year": 0.0, "max_days_per_request": None,
                "carry_forward": False, "max_carry_forward_days": 0.0,
                "requires_document": False, "min_notice_days": 7, "is_paid": False,
            },
        ],
    },
]


def seed_leave_templates(db: Session) -> int:
    """Insert any missing catalogue templates. Idempotent, keyed on code.

    Existing templates are never overwritten: an organization may have been
    built on a template whose contents were later adjusted in code, and a deploy
    must not silently rewrite the rules its leave ledger is being run against.
    """
    created = 0
    for spec in LEAVE_TEMPLATES:
        existing = db.query(LeaveTemplate).filter(LeaveTemplate.code == spec["code"]).first()
        if existing:
            continue
        template = LeaveTemplate(
            code=spec["code"],
            name=spec["name"],
            description=spec.get("description"),
            region=spec.get("region"),
            is_default=bool(spec.get("is_default")),
            is_system=True,
            is_active=True,
        )
        for order, item in enumerate(spec.get("items", [])):
            template.items.append(LeaveTemplateItem(display_order=order, **{
                k: v for k, v in item.items()
            }))
        db.add(template)
        created += 1
    db.commit()
    return created


def list_templates(db: Session) -> List[LeaveTemplate]:
    return (
        db.query(LeaveTemplate)
        .filter(LeaveTemplate.is_active.is_(True))
        .order_by(LeaveTemplate.is_default.desc(), LeaveTemplate.name)
        .all()
    )


def get_template(db: Session, code: str) -> Optional[LeaveTemplate]:
    return db.query(LeaveTemplate).filter(LeaveTemplate.code == code).first()


def apply_template(
    db: Session, org_id: UUID, code: str, replace: bool = False
) -> Dict[str, Any]:
    """Materialize a template's leave types into an organization.

    Additive by default: types the organization already has (matched on code)
    are left alone, and no type is ever deleted. `replace=True` additionally
    deactivates the organization's types that the template does not contain,
    which is offered for a tenant being moved onto a different region's rules.

    Gender-scoped types are materialized like any other type, but the balance
    seeder still refuses to pre-grant them as an annual entitlement (see
    `crud_leave.leave_type_applies_to_user`); they become usable when requested
    against a qualifying event.
    """
    template = get_template(db, code)
    if template is None or not template.is_active:
        raise ValueError(f"Unknown leave template: {code}")

    existing = {lt.code: lt for lt in db.query(LeaveType).filter(LeaveType.organization_id == org_id).all()}

    created, updated, deactivated = [], [], []
    for item in template.items:
        current = existing.get(item.code)
        if current is None:
            db.add(LeaveType(
                organization_id=org_id,
                code=item.code,
                name=item.name,
                description=item.description,
                max_days_per_year=item.max_days_per_year,
                max_days_per_request=item.max_days_per_request,
                carry_forward=item.carry_forward,
                max_carry_forward_days=item.max_carry_forward_days,
                requires_document=item.requires_document,
                min_notice_days=item.min_notice_days,
                is_paid=item.is_paid,
                is_active=1,
                gender_specific=item.gender_specific,
            ))
            created.append(item.code)
        elif replace:
            # Explicitly re-aligning a tenant to a template's current rules.
            current.name = item.name
            current.description = item.description
            current.max_days_per_year = item.max_days_per_year
            current.max_days_per_request = item.max_days_per_request
            current.carry_forward = item.carry_forward
            current.max_carry_forward_days = item.max_carry_forward_days
            current.requires_document = item.requires_document
            current.min_notice_days = item.min_notice_days
            current.is_paid = item.is_paid
            current.gender_specific = item.gender_specific
            current.is_active = 1
            updated.append(item.code)

    if replace:
        wanted = {i.code for i in template.items}
        for lt_code, lt in existing.items():
            if lt_code not in wanted and lt.is_active:
                lt.is_active = 0
                deactivated.append(lt_code)

    db.commit()
    return {
        "template": template.code,
        "created": created,
        "updated": updated,
        "deactivated": deactivated,
    }
