"""
Referral programme and public careers page.

Tenancy rules that this module exists to enforce:

  * every referral is created and read inside `organization_id`. A referral id
    from another tenant is reported as not-found rather than forbidden, so the
    id space is not enumerable.
  * `career_slug` is the only public identifier for an organization. A job id
    is never sufficient on its own: the slug must resolve to the same
    organization that owns the job, or a caller could pair a valid job id with
    any slug and apply to someone else's board.
  * an unknown or already-used referral code is ignored rather than reported,
    so the public form cannot be used to test whether a code exists.
"""
from __future__ import annotations

import logging
import re
import secrets
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.all_models import (
    Candidate,
    Department,
    JobApplication,
    JobPosting,
    Organization,
    Referral,
    User,
)
from app.schema.referral import (
    REFERRAL_STATUS_TRANSITIONS,
    PublicApplyRequest,
)

logger = logging.getLogger(__name__)

_SLUG_MAX = 60
# Ambiguous characters are dropped so a spoken or re-typed slug still resolves.
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_RESERVED_SLUGS = {
    "api", "app", "admin", "auth", "careers", "career", "dashboard", "login",
    "logout", "signup", "public", "assets", "static", "www", "support",
    "help", "about", "contact", "pricing", "settings", "user", "users",
    "jobs", "job", "home", "www2", "null", "undefined", "none",
}


class CareersError(Exception):
    """Raised for public careers failures; the router maps these to status codes."""


def _slugify(name: str) -> str:
    """Best-effort slug from an organization name."""
    normalized = unicodedata.normalize("NFKD", name or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _SLUG_STRIP.sub("-", ascii_only).strip("-")
    return slug[:_SLUG_MAX].strip("-")


def _unique_slug(db: Session, name: str, exclude_org_id: Optional[UUID] = None) -> str:
    base = _slugify(name) or "company"
    if base in _RESERVED_SLUGS:
        base = f"{base}-company"
    candidate = base
    for _ in range(50):
        clash = (
            db.query(Organization)
            .filter(Organization.career_slug == candidate)
            .first()
        )
        if clash is None or (exclude_org_id and clash.id == exclude_org_id):
            return candidate
        candidate = f"{base}-{secrets.token_hex(3)}"
    raise CareersError("could not allocate a unique career slug")


def get_or_create_career_slug(db: Session, org: Organization) -> str:
    """Return the org's public slug, creating one on first use.

    Nullable column, generated lazily: backfilling every existing tenant in the
    migration would take a unique index over the whole table for no benefit.

    The row is re-read through `db` rather than mutating `org` in place. Callers
    reach this with `current_user.organization`, and when that user instance is
    bound to a different session, adding the foreign-session object to `db`
    produces an UPDATE that matches no rows and raises StaleDataError.
    """
    if org.career_slug:
        return org.career_slug

    owned = db.query(Organization).filter(Organization.id == org.id).first()
    if owned is None:
        raise CareersError("organization not found")
    if owned.career_slug:
        return owned.career_slug

    slug = _unique_slug(db, owned.name, exclude_org_id=owned.id)
    owned.career_slug = slug
    db.add(owned)
    db.commit()
    db.refresh(owned)
    return owned.career_slug


def resolve_org_by_slug(db: Session, slug: str) -> Organization:
    """Look up an organization for the public careers page.

    Inactive organizations are treated as absent so a suspended tenant's
    vacancies disappear from the public web.
    """
    if not slug:
        raise CareersError("not found")
    org = (
        db.query(Organization)
        .filter(Organization.career_slug == slug.strip().lower())
        .first()
    )
    if org is None or not org.is_active or (org.status or "").upper() != "ACTIVE":
        raise CareersError("not found")
    return org


def list_public_jobs(
    db: Session, org: Organization, *, limit: int = 100, offset: int = 0
) -> Tuple[List[Dict[str, Any]], int]:
    """Open jobs only. Drafts and closed roles must be invisible publicly."""
    base = db.query(JobPosting).filter(
        JobPosting.organization_id == org.id,
        JobPosting.status == "open",
    )
    total = base.count()
    rows = (
        base.order_by(JobPosting.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    dept_names = _department_names(db, [r.department_id for r in rows if r.department_id])
    return (
        [
            {
                "id": r.id,
                "title": r.title,
                "department": dept_names.get(r.department_id),
                "location": r.location,
                "employment_type": r.employment_type,
                "description": r.description,
                "requirements": r.requirements,
                "posted_at": r.created_at,
            }
            for r in rows
        ],
        total,
    )


def get_public_job(db: Session, org: Organization, job_id: int) -> JobPosting:
    """Fetch a job, scoped to the org that owns the slug.

    Both the slug and the job id must agree. Without the organization check a
    caller could request any tenant's job id against a slug they control.
    """
    job = (
        db.query(JobPosting)
        .filter(
            JobPosting.id == job_id,
            JobPosting.organization_id == org.id,
            JobPosting.status == "open",
        )
        .first()
    )
    if job is None:
        raise CareersError("not found")
    return job


def _department_names(db: Session, dept_ids: List[int]) -> Dict[int, str]:
    if not dept_ids:
        return {}
    rows = (
        db.query(Department.id, Department.name)
        .filter(Department.id.in_(set(dept_ids)))
        .all()
    )
    return {r[0]: r[1] for r in rows}


# --------------------------------------------------------------------------- #
# public application
# --------------------------------------------------------------------------- #

def apply_publicly(
    db: Session, org: Organization, job: JobPosting, payload: PublicApplyRequest
) -> Dict[str, Any]:
    """Create (or reuse) a Candidate and a JobApplication.

    Returns only non-sensitive fields: a public endpoint must not echo back
    internal ids that could be used to probe the ATS.
    """
    email = str(payload.email).strip().lower()

    candidate = (
        db.query(Candidate)
        .filter(
            Candidate.organization_id == org.id,
            func.lower(Candidate.email) == email,
        )
        .first()
    )
    if candidate is None:
        candidate = Candidate(
            organization_id=org.id,
            full_name=payload.full_name,
            email=email,
            phone=payload.phone,
            resume_url=payload.resume_url,
        )
        db.add(candidate)
        db.flush()

    existing = (
        db.query(JobApplication)
        .filter(
            JobApplication.organization_id == org.id,
            JobApplication.job_posting_id == job.id,
            JobApplication.candidate_id == candidate.id,
        )
        .first()
    )
    if existing is not None:
        raise CareersError("already applied")

    application = JobApplication(
        organization_id=org.id,
        job_posting_id=job.id,
        candidate_id=candidate.id,
        stage="applied",
        notes=payload.cover_letter,
    )
    db.add(application)
    db.flush()

    referral_linked = False
    if payload.referral_code:
        referral = _consume_referral_code(
            db, org, payload.referral_code, candidate.id, job.id
        )
        referral_linked = referral is not None

    db.commit()
    return {
        "reference": f"APP-{application.id}",
        "job_title": job.title,
        "received": True,
        "referral_recorded": referral_linked,
    }


def _consume_referral_code(
    db: Session, org: Organization, code: str, candidate_id: int, job_id: int
) -> Optional[Referral]:
    """Attach a public application to a referral, if the code is usable.

    An unknown, mismatched or already-spent code returns None rather than
    raising: the applicant is not told whether the code was real, which would
    otherwise let anyone enumerate valid codes through the public form.

    Replay is judged on `status`, not on `candidate_id`. `create_referral`
    already creates the Candidate row and links it, so `candidate_id` is
    populated from the moment the referral is raised; treating "already set" as
    "already spent" made every genuine first application look like a replay.
    """
    referral = (
        db.query(Referral)
        .filter(Referral.referral_code == code.strip())
        .first()
    )
    if referral is None:
        return None
    # Must belong to the same tenant as the job being applied to.
    if referral.organization_id != org.id:
        logger.warning(
            "Referral code from another organization presented to %s", org.name
        )
        return None
    # A referral tied to a different vacancy does not apply here.
    if referral.job_posting_id not in (None, job_id):
        return None
    # Anything past `pending` has already been applied against.
    if referral.status != "pending":
        return None
    # Someone other than the referred person is trying to claim it.
    if referral.candidate_id is not None and referral.candidate_id != candidate_id:
        return None

    referral.candidate_id = candidate_id
    referral.status = "submitted"
    referral.updated_at = datetime.now(timezone.utc)
    db.add(referral)
    return referral


# --------------------------------------------------------------------------- #
# internal referral management
# --------------------------------------------------------------------------- #

def new_referral_code(db: Session) -> str:
    """Short, unambiguous, globally unique code for a candidate to quote."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I/O/0/1
    for _ in range(20):
        code = "REF-" + "".join(secrets.choice(alphabet) for _ in range(8))
        if not db.query(Referral).filter(Referral.referral_code == code).first():
            return code
    raise CareersError("could not allocate a referral code")


def create_referral(
    db: Session,
    *,
    org_id: UUID,
    referrer: User,
    referred_name: str,
    referred_email: str,
    referred_phone: Optional[str] = None,
    job_posting_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> Referral:
    """Raise a referral. The referrer is always the authenticated caller.

    The referrer is taken from the session rather than the request body, so a
    user cannot nominate a referral in someone else's name.
    """
    email = (referred_email or "").strip().lower()

    job: Optional[JobPosting] = None
    if job_posting_id is not None:
        job = (
            db.query(JobPosting)
            .filter(
                JobPosting.id == job_posting_id,
                JobPosting.organization_id == org_id,
            )
            .first()
        )
        if job is None:
            # Cross-tenant or nonexistent job: do not confirm which.
            raise CareersError("job not found")
        if job.status != "open":
            raise CareersError("job is not accepting referrals")

    duplicate = (
        db.query(Referral)
        .filter(
            Referral.organization_id == org_id,
            Referral.referrer_user_id == referrer.id,
            func.lower(Referral.referred_email) == email,
            Referral.job_posting_id == job_posting_id,
        )
        .first()
    )
    if duplicate is not None:
        raise CareersError("already referred")

    candidate = (
        db.query(Candidate)
        .filter(
            Candidate.organization_id == org_id,
            func.lower(Candidate.email) == email,
        )
        .first()
    )
    if candidate is None:
        candidate = Candidate(
            organization_id=org_id,
            full_name=referred_name,
            email=email,
            phone=referred_phone,
        )
        db.add(candidate)
        db.flush()

    referral = Referral(
        organization_id=org_id,
        job_posting_id=job_posting_id,
        referrer_user_id=referrer.id,
        candidate_id=candidate.id,
        referred_name=referred_name,
        referred_email=email,
        referred_phone=referred_phone,
        notes=notes,
        referral_code=new_referral_code(db),
        status="pending",
    )
    db.add(referral)
    db.commit()
    db.refresh(referral)
    return referral


def get_referral_for_org(db: Session, org_id: UUID, referral_id: int) -> Optional[Referral]:
    return (
        db.query(Referral)
        .filter(Referral.id == referral_id, Referral.organization_id == org_id)
        .first()
    )


def list_referrals(
    db: Session,
    org_id: UUID,
    *,
    referrer_user_id: Optional[int] = None,
    status: Optional[str] = None,
    job_posting_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Referral], int]:
    q = db.query(Referral).filter(Referral.organization_id == org_id)
    if referrer_user_id is not None:
        q = q.filter(Referral.referrer_user_id == referrer_user_id)
    if status:
        q = q.filter(Referral.status == status)
    if job_posting_id is not None:
        q = q.filter(Referral.job_posting_id == job_posting_id)
    total = q.count()
    rows = q.order_by(Referral.created_at.desc()).offset(offset).limit(limit).all()
    return rows, total


def update_referral(
    db: Session,
    referral: Referral,
    *,
    status: Optional[str] = None,
    reward_amount: Optional[float] = None,
    reward_status: Optional[str] = None,
    notes: Optional[str] = None,
    verified_by: Optional[User] = None,
) -> Referral:
    """Apply a status transition, rejecting illegal jumps.

    Without this, a referral could be flipped straight from `pending` to
    `hired` and a reward approved on the strength of a single request.
    """
    if status is not None and status != referral.status:
        allowed = REFERRAL_STATUS_TRANSITIONS.get(referral.status, set())
        if status not in allowed:
            raise CareersError(
                f"cannot move a referral from '{referral.status}' to '{status}'"
            )
        referral.status = status

    if reward_amount is not None:
        referral.reward_amount = reward_amount
    if reward_status is not None:
        referral.reward_status = reward_status
    if notes is not None:
        referral.notes = notes
    if verified_by is not None:
        referral.verified_by_user_id = verified_by.id
        referral.verified_at = datetime.now(timezone.utc)

    referral.updated_at = datetime.now(timezone.utc)
    db.add(referral)
    db.commit()
    db.refresh(referral)
    return referral


def referral_stats(db: Session, org_id: UUID) -> Dict[str, Any]:
    rows = (
        db.query(Referral.status, func.count(Referral.id))
        .filter(Referral.organization_id == org_id)
        .group_by(Referral.status)
        .all()
    )
    by_status = {status: count for status, count in rows}
    total = sum(by_status.values())
    hired = by_status.get("hired", 0)
    liability = (
        db.query(func.coalesce(func.sum(Referral.reward_amount), 0))
        .filter(
            Referral.organization_id == org_id,
            Referral.reward_status.in_(["approved", "paid"]),
        )
        .scalar()
        or 0
    )
    top = (
        db.query(
            Referral.referrer_user_id,
            User.full_name,
            func.count(Referral.id),
        )
        .join(User, User.id == Referral.referrer_user_id)
        .filter(Referral.organization_id == org_id)
        .group_by(Referral.referrer_user_id, User.full_name)
        .order_by(func.count(Referral.id).desc())
        .limit(5)
        .all()
    )
    return {
        "total": total,
        "by_status": by_status,
        "hired": hired,
        "conversion_rate": round((hired / total) * 100, 1) if total else 0.0,
        "reward_liability": float(liability),
        "top_referrers": [
            {"user_id": uid, "full_name": name, "referrals": count}
            for uid, name, count in top
        ],
    }
