"""
Turning a candidate marked `hired` into an actual employee.

Before this, `stage` was the whole story: PATCHing an application to `hired`
wrote the string 'hired' and stopped. No user, no employment record, no slot
consumed. Approving a hire left the org structure untouched, so the recruitment
board and the employee directory could disagree completely.

This service owns that transition. It is deliberately separate from the
router, because the same transition needs to be reachable from more than one
place (the pipeline PATCH today, a bulk import or an offer-acceptance webhook
tomorrow) and none of them should re-implement the headcount arithmetic.

The three things it guarantees, in order of how badly they bite if skipped:

1. **A slot is reserved at hire time, not at acceptance.** The employment
   record is created immediately with status PENDING_ONBOARDING, so approving
   three people against a two-slot position fails on the third. If the slot
   were only counted once the invite was accepted, HR could approve ten hires
   against one slot and discover the problem weeks later.

2. **The transition is idempotent.** `JobApplication.hired_employment_id` is
   written in the same commit as the employment record, so a retried request
   returns the original hire instead of minting a second employee and a second
   invite. Nothing here is safe to run twice otherwise.

3. **A rejected candidate cannot be hired**, and a terminal application is
   never reopened to make room for one.

Headroom is derived by counting employment records rather than kept as a
counter column, so it cannot drift out of step with the rows it summarises.
"""
from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.models.all_models import (
    Candidate,
    EmploymentRecord,
    JobApplication,
    JobPosition,
    JobPosting,
    Role,
    User,
)

# Employment states that hold a slot. Anything not listed has released it:
# TERMINATED and ALUMNI have left, so their headroom is available again.
SLOT_HOLDING_STATUSES = {"PENDING_ONBOARDING", "PROBATION", "ACTIVE",
                         "NOTICE_PERIOD", "SUSPENDED"}

# The state a hire sits in between approval and completing onboarding.
PENDING_ONBOARDING = "PENDING_ONBOARDING"

DEFAULT_HIRE_ROLE = "OrgEmployee"


class HireError(Exception):
    """A hire that cannot proceed. `code` maps to an HTTP status in the router."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.message = message
        self.code = code

    @property
    def status_code(self) -> int:
        return {
            "not_found": 404,
            "capacity": 409,
            "conflict": 409,
            "eligibility": 409,
        }.get(self.code, 400)


# --------------------------------------------------------------------------- #
# headroom
# --------------------------------------------------------------------------- #

def position_fill(db: Session, org_id, position_id: int) -> int:
    """How many slots of `position_id` are currently spoken for.

    Counted from the employment records rather than a stored counter, so
    offboarding automatically frees the slot with no reconciliation step.
    """
    return int(
        db.query(func.count(EmploymentRecord.id))
        .filter(
            EmploymentRecord.org_id == org_id,
            EmploymentRecord.position_id == position_id,
            EmploymentRecord.status.in_(SLOT_HOLDING_STATUSES),
        )
        .scalar()
        or 0
    )


def position_headroom(db: Session, org_id, position_id: int) -> Dict[str, Any]:
    position = (
        db.query(JobPosition)
        .filter(JobPosition.id == position_id, JobPosition.org_id == org_id,
                JobPosition.is_deleted == 0)
        .first()
    )
    if not position:
        return {"position_id": position_id, "title": None,
                "capacity": None, "filled": None, "remaining": None}
    filled = position_fill(db, org_id, position_id)
    return {
        "position_id": position.id,
        "title": position.title,
        "capacity": position.headcount_capacity,
        "filled": filled,
        "remaining": max(0, position.headcount_capacity - filled),
    }


# --------------------------------------------------------------------------- #
# the transition
# --------------------------------------------------------------------------- #

def _owned(db: Session, model, org_id, row_id: int, label: str):
    row = db.query(model).filter(model.id == row_id, model.organization_id == org_id).first()
    if not row:
        raise HireError(f"{label} not found", code="not_found")
    return row


def hire_from_application(
    db: Session,
    *,
    organization_id,
    application_id: int,
    invited_by_user_id: Optional[int] = None,
    role_name: str = DEFAULT_HIRE_ROLE,
) -> Dict[str, Any]:
    """
    Promote a `hired` application into a real employee.

    Returns a report of what happened -- including the invite's raw token,
    which is returned exactly once and is not recoverable afterwards. When the
    candidate already has an account in this tenant the hire is recorded
    without a new invite and ``invite_token`` is None.
    """
    application = _owned(db, JobApplication, organization_id, application_id,
                         "Application")
    job = _owned(db, JobPosting, organization_id, application.job_posting_id,
                 "Job posting")
    candidate = _owned(db, Candidate, organization_id, application.candidate_id,
                       "Candidate")

    # Idempotency. This check is what makes a retried PATCH safe, and it has
    # to come before every write below.
    if application.hired_employment_id is not None:
        return _existing_report(db, organization_id, application)

    if application.stage == "rejected":
        raise HireError(
            "This candidate was rejected and cannot be hired.", code="eligibility"
        )

    position_id = job.position_id
    headroom: Optional[Dict[str, Any]] = None
    if position_id is not None:
        headroom = position_headroom(db, organization_id, position_id)
        if headroom["capacity"] is not None and headroom["remaining"] <= 0:
            raise HireError(
                f"Position '{headroom['title']}' is already filled "
                f"({headroom['filled']}/{headroom['capacity']}). "
                "Raise the position's headcount capacity or link the vacancy "
                "to a different position.",
                code="capacity",
            )

    # Scoped to this tenant. A candidate whose address already has an account
    # elsewhere is a separate person as far as this hire is concerned -- the
    # same mailbox may legitimately be an employee at another organisation --
    # so they get their own account here rather than being refused.
    existing_user = (
        db.query(User)
        .filter(
            func.lower(User.email) == candidate.email.strip().lower(),
            User.org_id == organization_id,
            User.is_deleted == 0,
        )
        .first()
    )
    invite_token: Optional[str] = None
    invite_id: Optional[int] = None

    # The User row is created now rather than at invite acceptance, because
    # `employment_records.user_id` is NOT NULL -- a slot cannot be held by a
    # person who has no account.
    #
    # The account is real but not usable: it gets a random unguessable
    # password, so logging in before onboarding is impossible, and
    # `accept_invite` replaces it with the password the new hire chooses. That
    # also means the hire shows up in the employee directory straight away,
    # which is what HR expects after approving someone.
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HireError(
            f"Role '{role_name}' is not configured in this deployment.",
            code="conflict",
        )

    created_here = existing_user is None
    if existing_user is not None:
        # Re-hire: the account already exists, so there is nobody to invite
        # and nothing to wait for.
        existing_user.is_active = 1
        db.add(existing_user)
    else:
        existing_user = User(
            org_id=organization_id,
            role_id=role.id,
            dept_id=job.department_id,
            full_name=candidate.full_name,
            username=_unique_username(db, candidate.email),
            email=candidate.email.strip().lower(),
            employee_id=_unique_employee_id(db),
            # Placeholder only. `secrets.token_urlsafe` is not a password
            # anybody could guess, and it is overwritten on acceptance.
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            is_active=1,
        )
        db.add(existing_user)
        db.flush()

    employment = EmploymentRecord(
        org_id=organization_id,
        user_id=existing_user.id,
        position_id=position_id,
        business_unit_id=None,
        branch_id=None,
        cost_center_id=None,
        employment_type=_employment_type(job.employment_type),
        # PROBATION when the person is already known to us, otherwise held
        # until they finish onboarding.
        status="PENDING_ONBOARDING" if created_here else "PROBATION",
        joining_date=datetime.now(timezone.utc),
    )
    db.add(employment)
    db.flush()

    application.hired_employment_id = employment.id
    application.stage = "hired"
    db.add(application)

    if created_here:
        # Imported lazily: invite_service imports models too, and a
        # module-level import here would make the two modules circular.
        from app.services.invite_service import InviteError, create_invite

        try:
            invite, invite_token = create_invite(
                db,
                organization_id=organization_id,
                email=existing_user.email,
                full_name=existing_user.full_name,
                role_id=role.id,
                department_id=job.department_id,
                position_id=position_id,
                invited_by_user_id=invited_by_user_id,
            )
        except InviteError as exc:
            # Nothing should be half-recorded. Rolling back discards the
            # account, the employment record and the stage change together: a
            # reserved slot that nobody can onboard would be worse than no
            # hire at all.
            db.rollback()
            raise HireError(exc.message, code="conflict") from exc
        invite_id = invite.id

    db.commit()
    db.refresh(application)
    db.refresh(employment)

    if position_id is not None:
        headroom = position_headroom(db, organization_id, position_id)

    return {
        "application_id": application.id,
        "employment_id": employment.id,
        "user_id": existing_user.id if existing_user is not None else None,
        "invite_id": invite_id,
        "invite_token": invite_token,
        "already_employed": not created_here,
        "position": headroom,
        "posting_filled": _posting_filled(db, job),
    }


def _existing_report(db: Session, org_id, application: JobApplication) -> Dict[str, Any]:
    """The report for a hire that already happened, so a retry is a no-op
    that still answers the caller's question."""
    employment = (
        db.query(EmploymentRecord)
        .filter(EmploymentRecord.id == application.hired_employment_id)
        .first()
    )
    position_id = employment.position_id if employment is not None else None
    return {
        "application_id": application.id,
        "employment_id": application.hired_employment_id,
        "user_id": employment.user_id if employment is not None else None,
        "invite_id": None,
        "invite_token": None,
        "already_employed": True,
        "idempotent_replay": True,
        "position": (position_headroom(db, org_id, position_id)
                     if position_id is not None else None),
        "posting_filled": False,
    }


def _unique_username(db: Session, email: str) -> str:
    """A login name derived from the email, made unique within the tenant.

    `users.username` is unique, and an address can only yield one candidate, so
    the clash case is narrow -- but it is real, because `create_invite` refuses
    a second live invite to the same address while a manually created account
    for that address may already exist.
    """
    base = re.sub(r"[^a-z0-9._-]+", ".", (email or "").strip().lower())[:120] or "hire"
    candidate = base
    suffix = 1
    while db.query(User.id).filter(User.username == candidate).first():
        suffix += 1
        candidate = f"{base}.{suffix}"
    return candidate


def _unique_employee_id(db: Session) -> str:
    """An employee number in the same shape `crud_user.create` generates."""
    while True:
        candidate = f"EMP-{uuid.uuid4().hex[:6].upper()}"
        if not db.query(User.id).filter(User.employee_id == candidate).first():
            return candidate


def _employment_type(job_type: Optional[str]) -> str:
    """Map a posting's employment type onto the employment-record vocabulary.

    The two features spell the same three concepts differently, and this is the
    vocabulary the employee directory validates against.
    """
    return {
        "Full-time": "FULL_TIME",
        "Part-time": "PART_TIME",
        "Contract": "CONTRACT",
        "Intern": "INTERN",
    }.get((job_type or "").strip(), "EMPLOYEE")


def _posting_filled(db: Session, job: JobPosting) -> bool:
    """True when this posting has consumed every opening it advertised.

    Counted from the application rows rather than read off the position, so a
    posting that covers several seats for one position still closes on the
    right hire.
    """
    hired = int(
        db.query(func.count(JobApplication.id))
        .filter(
            JobApplication.job_posting_id == job.id,
            JobApplication.stage == "hired",
        )
        .scalar()
        or 0
    )
    return hired >= job.headcount
