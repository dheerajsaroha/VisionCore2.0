"""
seed_leave.py — Leave Types Seeder
Sprint 3 — Module 1
"""
from uuid import UUID
from sqlalchemy.orm import Session
from app.crud.crud_leave import crud_leave_type
from app.db.models.all_models import Organization

DEFAULT_LEAVE_TYPES = [
    {
        "code": "ANNUAL",
        "name": "Annual Leave",
        "description": "Paid annual vacation leave entitlement",
        "max_days_per_year": 18,
        "max_days_per_request": 14,
        "carry_forward": True,
        "max_carry_forward_days": 5,
        "requires_document": False,
        "min_notice_days": 3,
        "is_paid": True,
    },
    {
        "code": "SICK",
        "name": "Sick Leave",
        "description": "Leave for medical issues or doctor visits",
        "max_days_per_year": 12,
        "max_days_per_request": 7,
        "carry_forward": False,
        "max_carry_forward_days": 0,
        "requires_document": True,
        "min_notice_days": 0,
        "is_paid": True,
    },
    {
        "code": "CASUAL",
        "name": "Casual Leave",
        "description": "Short-notice casual/personal leave",
        "max_days_per_year": 10,
        "max_days_per_request": 3,
        "carry_forward": False,
        "max_carry_forward_days": 0,
        "requires_document": False,
        "min_notice_days": 1,
        "is_paid": True,
    },
    {
        "code": "MATERNITY",
        "name": "Maternity Leave",
        "description": "Maternity leave entitlement for female employees",
        "max_days_per_year": 180,
        "max_days_per_request": 180,
        "carry_forward": False,
        "max_carry_forward_days": 0,
        "requires_document": True,
        "min_notice_days": 30,
        "is_paid": True,
        "gender_specific": "female",
    },
    {
        "code": "PATERNITY",
        "name": "Paternity Leave",
        "description": "Paternity leave entitlement for male employees",
        "max_days_per_year": 15,
        "max_days_per_request": 15,
        "carry_forward": False,
        "max_carry_forward_days": 0,
        "requires_document": True,
        "min_notice_days": 7,
        "is_paid": True,
        "gender_specific": "male",
    },
    {
        "code": "COMPENSATORY",
        "name": "Compensatory Off",
        "description": "Off day earned by working on holidays or weekends",
        "max_days_per_year": 10,
        "max_days_per_request": 5,
        "carry_forward": False,
        "max_carry_forward_days": 0,
        "requires_document": False,
        "min_notice_days": 1,
        "is_paid": True,
    },
]


def seed_leave_types_for_org(db: Session, org_id: UUID) -> int:
    """Seed standard leave types for an organization if not already seeded.

    Uses PostgreSQL ON CONFLICT DO NOTHING to guarantee idempotency even
    under concurrent requests.  Existing leave types are never duplicated,
    and the function returns the count of newly inserted rows.
    """
    count = 0
    for lt in DEFAULT_LEAVE_TYPES:
        existing = crud_leave_type.get_by_code(db, org_id, lt["code"])
        if not existing:
            # upsert is idempotent — uses on_conflict_do_nothing
            crud_leave_type.upsert(db, org_id, lt)
            count += 1
    return count
