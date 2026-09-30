"""
Public careers pages — the unauthenticated surface.

An organization posts a vacancy and it appears on its own public careers page,
reachable at `/careers/<career_slug>` (or the same API for an external site to
embed). Nothing here requires a session.

What this router deliberately does not expose:

  * drafts and closed roles — the query filters on `status == 'open'`, so a
    draft is indistinguishable from a job that was never created;
  * `posted_by_user_id`, internal ids of anything but the job being viewed, or
    any candidate data;
  * whether a referral code is real. `_consume_referral_code` ignores unknown
    codes rather than reporting them, because an "invalid code" message would
    turn this form into a code oracle;
  * an inactive organization. A suspended tenant's board returns 404.

Rate limiting is applied to application submission, since it is the one
write an anonymous caller can reach.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.rate_limit import rate_limit_dependency
from app.db.database import get_db
from app.db.models.all_models import Department, JobPosting, Organization
from app.schema.referral import (
    PublicApplyRequest,
    PublicJobDetail,
    PublicJobOut,
    PublicOrgProfile,
)
from app.services import referral_service as svc
from app.services.referral_service import CareersError

logger = logging.getLogger(__name__)

router = APIRouter()


def _org_or_404(db: Session, slug: str) -> Organization:
    try:
        return svc.resolve_org_by_slug(db, slug)
    except CareersError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Careers page not found"
        )


def _job_or_404(db: Session, org: Organization, job_id: int) -> Any:
    try:
        return svc.get_public_job(db, org, job_id)
    except CareersError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )


# --------------------------------------------------------------------------- #
# public reads
# --------------------------------------------------------------------------- #

@router.get(
    "/{slug}",
    response_model=PublicOrgProfile,
    summary="Public organization profile and open role count",
)
def public_org_profile(slug: str, db: Session = Depends(get_db)):
    org = _org_or_404(db, slug)
    open_roles = (
        db.query(JobPosting)
        .filter(
            JobPosting.organization_id == org.id,
            JobPosting.status == "open",
        )
        .count()
    )
    return {
        "name": org.name,
        "slug": org.career_slug,
        "logo_url": org.logo_url,
        "primary_color": org.primary_color,
        "open_roles": open_roles,
    }


@router.get(
    "/{slug}/jobs",
    response_model=List[PublicJobOut],
    summary="Open vacancies",
)
def public_job_list(
    slug: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    org = _org_or_404(db, slug)
    jobs, _total = svc.list_public_jobs(db, org, limit=limit, offset=offset)
    return jobs


@router.get(
    "/{slug}/jobs/{job_id}",
    response_model=PublicJobDetail,
    summary="Public job detail",
)
def public_job_detail(
    slug: str, job_id: int, db: Session = Depends(get_db)
):
    org = _org_or_404(db, slug)
    job = _job_or_404(db, org, job_id)
    dept = None
    if job.department_id is not None:
        dept = (
            db.query(Department.name)
            .filter(Department.id == job.department_id)
            .scalar()
        )
    return {
        "id": job.id,
        "title": job.title,
        "department": dept,
        "location": job.location,
        "employment_type": job.employment_type,
        "description": job.description,
        "requirements": job.requirements,
        "posted_at": job.created_at,
        "organization_name": org.name,
        "organization_logo_url": org.logo_url,
        "organization_color": org.primary_color,
    }


# --------------------------------------------------------------------------- #
# public write
# --------------------------------------------------------------------------- #

@router.post(
    "/{slug}/jobs/{job_id}/apply",
    status_code=status.HTTP_201_CREATED,
    summary="Apply for a vacancy",
    dependencies=[
        Depends(rate_limit_dependency(max_requests=5, window_seconds=300))
    ],
)
def public_apply(
    slug: str,
    job_id: int,
    payload: PublicApplyRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    org = _org_or_404(db, slug)
    job = _job_or_404(db, org, job_id)

    # Honeypot: a field hidden from humans. Accept and discard, so a bot does
    # not learn it was caught by returning an error.
    if payload.website:
        return {
            "reference": "APP-0",
            "job_title": job.title,
            "received": True,
            "referral_recorded": False,
        }

    try:
        return svc.apply_publicly(db, org, job, payload)
    except CareersError as exc:
        if str(exc) == "already applied":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An application for this role already exists for that email.",
            )
        logger.warning("Public application rejected: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
