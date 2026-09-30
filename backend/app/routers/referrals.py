"""
Employee referral endpoints (authenticated, organization-scoped).

Gating:
  * `referral.create`  — an employee may nominate a candidate. This is the
    deliberately broad grant: referring someone is the point of the feature.
  * `referral.verify`  — only HR/admin may see the whole tenant's referrals,
    change their status, or see reward figures.

Every read and write is filtered by `current_user.org_id`, and a referral id
belonging to another tenant is reported as 404 rather than 403.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.db.models.all_models import JobPosting, Referral, User
from app.schema.referral import (
    ReferralCreate,
    ReferralOut,
    ReferralStats,
    ReferralUpdate,
)
from app.services import referral_service as svc
from app.services.referral_service import CareersError

router = APIRouter(dependencies=[Depends(deps.require_feature("recruitment"))])


def _serialize(referral: Referral, db: Session) -> Dict[str, Any]:
    job_title = None
    if referral.job_posting_id is not None:
        title = (
            db.query(JobPosting.title)
            .filter(JobPosting.id == referral.job_posting_id)
            .scalar()
        )
        job_title = title
    return {
        "id": referral.id,
        "organization_id": referral.organization_id,
        "job_posting_id": referral.job_posting_id,
        "job_title": job_title,
        "referrer_user_id": referral.referrer_user_id,
        "referrer_name": referral.referrer.full_name if referral.referrer else None,
        "candidate_id": referral.candidate_id,
        "referred_name": referral.referred_name,
        "referred_email": referral.referred_email,
        "referred_phone": referral.referred_phone,
        "notes": referral.notes,
        "referral_code": referral.referral_code,
        "status": referral.status,
        "reward_amount": float(referral.reward_amount)
        if referral.reward_amount is not None
        else None,
        "reward_status": referral.reward_status,
        "verified_by_user_id": referral.verified_by_user_id,
        "verified_at": referral.verified_at,
        "created_at": referral.created_at,
    }


# --------------------------------------------------------------------------- #
# creating a referral
# --------------------------------------------------------------------------- #

@router.post(
    "/referrals",
    response_model=ReferralOut,
    status_code=status.HTTP_201_CREATED,
    summary="Refer a candidate to a vacancy",
)
def create_referral(
    payload: ReferralCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        deps.require_permission("referral.create", "recruitment.create")
    ),
):
    """Nominate an external candidate.

    The referrer is always the caller, so nobody can raise a referral in a
    colleague's name and claim their referral bonus.
    """
    try:
        referral = svc.create_referral(
            db,
            org_id=current_user.org_id,
            referrer=current_user,
            referred_name=payload.referred_name,
            referred_email=str(payload.referred_email),
            referred_phone=payload.referred_phone,
            job_posting_id=payload.job_posting_id,
            notes=payload.notes,
        )
    except CareersError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _serialize(referral, db)


@router.get(
    "/referrals/mine",
    response_model=List[ReferralOut],
    summary="Referrals raised by the current user",
)
def list_my_referrals(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("referral.create")),
):
    """An employee sees only their own referrals — never a colleague's or the
    tenant's aggregate. Granted on `referral.create`, so a referral is
    trackable without granting any read access to the wider candidate pool."""
    rows, _ = svc.list_referrals(
        db,
        current_user.org_id,
        referrer_user_id=current_user.id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return [_serialize(r, db) for r in rows]


# --------------------------------------------------------------------------- #
# tenant-wide management (HR / admin)
# --------------------------------------------------------------------------- #

@router.get(
    "/referrals",
    response_model=List[ReferralOut],
    summary="All referrals in the organization",
)
def list_referrals(
    status_filter: Optional[str] = Query(None, alias="status"),
    job_posting_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("referral.verify")),
):
    rows, _ = svc.list_referrals(
        db,
        current_user.org_id,
        status=status_filter,
        job_posting_id=job_posting_id,
        limit=limit,
        offset=offset,
    )
    return [_serialize(r, db) for r in rows]


@router.get(
    "/referrals/stats",
    response_model=ReferralStats,
    summary="Referral programme statistics",
)
def referral_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("referral.verify")),
):
    return svc.referral_stats(db, current_user.org_id)


@router.get(
    "/referrals/{referral_id}",
    response_model=ReferralOut,
    summary="Fetch one referral",
)
def get_referral(
    referral_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("referral.verify")),
):
    referral = svc.get_referral_for_org(db, current_user.org_id, referral_id)
    if referral is None:
        # 404 rather than 403: a 403 would confirm the id exists in some tenant.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Referral not found"
        )
    return _serialize(referral, db)


@router.patch(
    "/referrals/{referral_id}",
    response_model=ReferralOut,
    summary="Update referral status, reward or notes",
)
def update_referral(
    referral_id: int,
    payload: ReferralUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("referral.verify")),
):
    referral = svc.get_referral_for_org(db, current_user.org_id, referral_id)
    if referral is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Referral not found"
        )
    try:
        referral = svc.update_referral(
            db,
            referral,
            status=payload.status,
            reward_amount=payload.reward_amount,
            reward_status=payload.reward_status,
            notes=payload.notes,
            verified_by=current_user,
        )
    except CareersError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return _serialize(referral, db)


# --------------------------------------------------------------------------- #
# public careers page address
# --------------------------------------------------------------------------- #

@router.get(
    "/career-page",
    summary="Public careers page URL for this organization",
)
def my_career_page(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """The address at which this organization's vacancies are published.

    The slug is generated on first call rather than at sign-up, so tenants that
    never publish a careers page cost nothing.
    """
    from app.core.config import settings

    org = current_user.organization
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    slug = svc.get_or_create_career_slug(db, org)
    jobs, total = svc.list_public_jobs(db, org, limit=100)
    return {
        "career_slug": slug,
        "career_path": f"/careers/{slug}",
        "api_path": f"{settings.API_V1_STR}/careers/{slug}",
        "open_roles": total,
    }
