"""
Recruitment: job postings, the candidate pool, the application pipeline and
interview scheduling.

ACCESS POLICY -- deliberately open to every authenticated user in the tenant.
This module is intentionally *not* role-scoped. It sits behind the `recruitment`
plan feature gate and behind tenant scoping, which are the two boundaries that
matter here; a third role layer on top only produced the bug the removed
`has_any_role` calls used to cause, where a legitimate hiring manager was
locked out of posting a job.

Consequence, stated plainly: any employee can read the whole candidate pool,
including names, emails, phone numbers and `resume_url`, and can move a
candidate through the pipeline. That is the accepted trade-off for a
self-serve ATS. The referrals module is *not* open on the same terms, because
it moves money (`reward_amount`) rather than just pipeline state.

What is still enforced, and is not negotiable:
  * `require_feature("recruitment")` -- the tenant's plan must include it.
  * tenant scoping on every read and every write, including on ids supplied by
    the caller. An id belonging to another organisation is a 404, not a 403,
    so a 403 cannot be used to confirm that an id exists elsewhere.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.db.models.all_models import (
    Candidate,
    InterviewSchedule,
    JobApplication,
    JobPosition,
    JobPosting,
    User,
)
from app.schema.recruitment import (
    APPLICATION_STAGES,
    TERMINAL_STAGES,
    ApplicationCreate,
    ApplicationStageUpdate,
    CandidateCreate,
    InterviewCreate,
    JobPostingCreate,
)
from app.services.hiring_service import HireError, hire_from_application

router = APIRouter(dependencies=[Depends(deps.require_feature("recruitment"))])


def _owned_job(db: Session, org_id, job_id: int) -> JobPosting:
    """Fetch a posting that belongs to `org_id`, or 404.

    Scoping the lookup by organization_id rather than fetching by id and
    comparing afterwards keeps this in one place, so a new caller cannot
    forget the tenant check.
    """
    job = (
        db.query(JobPosting)
        .filter(JobPosting.id == job_id, JobPosting.organization_id == org_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return job


def _owned_candidate(db: Session, org_id, candidate_id: int) -> Candidate:
    cand = (
        db.query(Candidate)
        .filter(Candidate.id == candidate_id, Candidate.organization_id == org_id)
        .first()
    )
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return cand


def _owned_position(db: Session, org_id, position_id: int):
    """Resolve a position within the tenant.

    A posting may only be attached to a position belonging to the same
    organisation, otherwise one tenant's vacancy could consume another
    tenant's headcount.
    """
    position = (
        db.query(JobPosition)
        .filter(JobPosition.id == position_id, JobPosition.org_id == org_id,
                JobPosition.is_deleted == 0)
        .first()
    )
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    return position


def _owned_application(db: Session, org_id, app_id: int) -> JobApplication:
    row = (
        db.query(JobApplication)
        .filter(JobApplication.id == app_id, JobApplication.organization_id == org_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    return row


# ── JOB POSTINGS ──
@router.post("/jobs", status_code=201)
def create_job_posting(
    payload: JobPostingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Create a new job posting."""
    if payload.position_id is not None:
        _owned_position(db, current_user.org_id, payload.position_id)

    job = JobPosting(
        organization_id=current_user.org_id,
        title=payload.title,
        department_id=payload.department_id,
        description=payload.description,
        requirements=payload.requirements,
        location=payload.location,
        employment_type=payload.employment_type,
        status=payload.status,
        posted_by_user_id=current_user.id,
        position_id=payload.position_id,
        headcount=payload.headcount,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"id": job.id, "title": job.title, "status": job.status,
            "position_id": job.position_id, "headcount": job.headcount,
            "created_at": job.created_at}


@router.get("/jobs")
def list_job_postings(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """List job postings for organization."""
    q = db.query(JobPosting).filter(JobPosting.organization_id == current_user.org_id)
    if status:
        q = q.filter(JobPosting.status == status)
    jobs = q.order_by(JobPosting.created_at.desc()).all()
    return [{
        "id": j.id,
        "title": j.title,
        "location": j.location,
        "employment_type": j.employment_type,
        "status": j.status,
        "position_id": j.position_id,
        "headcount": j.headcount,
        "created_at": j.created_at,
    } for j in jobs]


# ── CANDIDATES & APPLICATIONS ──
@router.post("/candidates", status_code=201)
def register_candidate(
    payload: CandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Register a new candidate in the talent pool."""
    cand = Candidate(
        organization_id=current_user.org_id,
        full_name=payload.full_name,
        email=str(payload.email),
        phone=payload.phone,
        resume_url=payload.resume_url,
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    return {"id": cand.id, "full_name": cand.full_name, "email": cand.email}


@router.get("/candidates")
def list_candidates(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """List all candidates in the organization's talent pool."""
    candidates = (
        db.query(Candidate)
        .filter(Candidate.organization_id == current_user.org_id)
        .order_by(Candidate.created_at.desc())
        .all()
    )
    return [{
        "id": c.id,
        "name": c.full_name,
        "email": c.email,
        "phone": c.phone,
        "resume_url": c.resume_url,
        "created_at": c.created_at,
    } for c in candidates]


@router.get("/positions")
def list_positions(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """List vacancies.

    Named `positions` because the recruiting UI calls them that, but these are
    `JobPosting` rows -- adverts -- and not `JobPosition` rows from
    Core & Identity, which are internal headcount slots with a grade, a band
    and a reporting line. The two are unrelated tables; see the module
    docstring of `app.routers.recruitment` for why that is still confusing.
    """
    q = db.query(JobPosting).filter(JobPosting.organization_id == current_user.org_id)
    if status:
        q = q.filter(JobPosting.status == status)
    jobs = q.order_by(JobPosting.created_at.desc()).all()
    if not jobs:
        return []

    # Counted in one grouped query rather than per posting, so the list cost
    # stays flat instead of issuing 1 + N queries.
    counts = dict(
        db.query(JobApplication.job_posting_id,
                 func.count(JobApplication.id))
        .filter(
            JobApplication.organization_id == current_user.org_id,
            JobApplication.job_posting_id.in_([j.id for j in jobs]),
        )
        .group_by(JobApplication.job_posting_id)
        .all()
    )
    return [{
        "id": j.id,
        "title": j.title,
        "location": j.location,
        "type": j.employment_type,
        "status": j.status,
        "applicants_count": counts.get(j.id, 0),
        "created_at": j.created_at,
    } for j in jobs]


@router.post("/applications", status_code=201)
def submit_job_application(
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Submit candidate job application into pipeline."""
    # Both ids arrive from the caller, so both are resolved within the tenant
    # before use. Without this check a caller could file an application against
    # another organisation's job posting using their own org id.
    _owned_job(db, current_user.org_id, payload.job_posting_id)
    _owned_candidate(db, current_user.org_id, payload.candidate_id)

    app_obj = JobApplication(
        organization_id=current_user.org_id,
        job_posting_id=payload.job_posting_id,
        candidate_id=payload.candidate_id,
        stage=payload.stage,
        rating=payload.rating,
        notes=payload.notes,
    )
    db.add(app_obj)
    db.commit()
    db.refresh(app_obj)
    return {"id": app_obj.id, "stage": app_obj.stage, "applied_at": app_obj.applied_at}


@router.get("/applications")
def list_job_applications(
    job_id: Optional[int] = Query(None),
    stage: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """List applicant tracking pipeline applications."""
    q = db.query(JobApplication).filter(
        JobApplication.organization_id == current_user.org_id)
    if job_id:
        q = q.filter(JobApplication.job_posting_id == job_id)
    if stage:
        q = q.filter(JobApplication.stage == stage)
    apps = q.order_by(JobApplication.applied_at.desc()).all()
    return [{
        "id": a.id,
        "candidate_id": a.candidate_id,
        "job_posting_id": a.job_posting_id,
        "job_title": a.job_posting.title if a.job_posting else "Unknown Job",
        "candidate_name": a.candidate.full_name if a.candidate else "Unknown Candidate",
        "candidate_email": a.candidate.email if a.candidate else "",
        "stage": a.stage,
        "rating": a.rating,
        "applied_at": a.applied_at,
    } for a in apps]


@router.patch("/applications/{app_id}/stage")
def update_application_stage(
    app_id: int,
    payload: ApplicationStageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Advance or update candidate stage in recruitment pipeline."""
    app_obj = _owned_application(db, current_user.org_id, app_id)

    # `hired` is not a label, it is a transition with consequences: it reserves
    # a slot, creates an employment record and issues an onboarding invite.
    #
    # It is handled first and separately because the generic terminal-state
    # rule below would otherwise reject a retried hire with a 409, and a retry
    # is exactly the case that has to stay safe. `hire_from_application` is
    # idempotent, and it refuses a rejected candidate itself.
    if payload.stage == "hired":
        try:
            report = hire_from_application(
                db,
                organization_id=current_user.org_id,
                application_id=app_obj.id,
                invited_by_user_id=current_user.id,
            )
        except HireError as exc:
            # Nothing was written, so the application is still where it was:
            # a capacity failure does not leave someone marked as hired.
            raise HTTPException(status_code=exc.status_code, detail=exc.message)

        # The service already committed the stage change together with the
        # employment record, so the two cannot disagree. Rating and notes are
        # advisory and applied afterwards.
        _apply_rating_and_notes(db, app_obj, payload)
        return {
            "id": app_obj.id,
            "stage": "hired",
            "rating": app_obj.rating,
            "employment_id": report["employment_id"],
            "user_id": report["user_id"],
            "invite_id": report["invite_id"],
            "invite_token": report["invite_token"],
            "already_employed": report["already_employed"],
            "idempotent_replay": report.get("idempotent_replay", False),
            "position": report["position"],
        }

    # Terminal states are final. Reopening a rejected candidate by patching the
    # stage back to `screening` would erase the record that they were ever
    # rejected.
    if app_obj.stage in TERMINAL_STAGES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"application is already '{app_obj.stage}' and cannot be moved "
                f"to '{payload.stage}'; record a new application instead"
            ),
        )
    if app_obj.stage == payload.stage:
        return {"id": app_obj.id, "stage": app_obj.stage, "rating": app_obj.rating}

    app_obj.stage = payload.stage
    _apply_rating_and_notes(db, app_obj, payload)
    db.commit()
    db.refresh(app_obj)
    return {"id": app_obj.id, "stage": app_obj.stage, "rating": app_obj.rating}


def _apply_rating_and_notes(db: Session, app_obj: JobApplication,
                            payload: ApplicationStageUpdate) -> None:
    """Rating and notes are advisory, so a failure here must not undo a hire.

    Kept in its own helper because the `hired` path has already committed by
    the time these are applied.
    """
    if payload.rating is not None:
        app_obj.rating = payload.rating
    if payload.notes is not None:
        app_obj.notes = payload.notes
    db.add(app_obj)


# ── INTERVIEWS ──
@router.post("/interviews", status_code=201)
def schedule_interview(
    payload: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Schedule an interview for a candidate application."""
    app_obj = _owned_application(db, current_user.org_id, payload.application_id)

    interviewer_id = payload.interviewer_user_id or current_user.id
    if not deps.has_any_role(current_user, "OrgAdmin", "Admin", "SuperAdmin",
                             "OrgManager", "OrgHR"):
        # Open access, with one floor: an ordinary employee may schedule an
        # interview for themselves, but cannot assign a panel interviewer on
        # someone else's behalf. Naming someone else to sit in on a hiring
        # decision is the one write here that acts on a third party.
        if interviewer_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="only HR or a manager may assign an interviewer",
            )

    sched = InterviewSchedule(
        organization_id=current_user.org_id,
        application_id=app_obj.id,
        interviewer_user_id=interviewer_id,
        scheduled_at=payload.scheduled_at,
        meeting_link=payload.meeting_link,
        status="scheduled",
    )
    db.add(sched)

    # Automatically advance the application to 'interview', unless it has
    # already reached a terminal state -- scheduling a catch-up interview
    # should not silently reopen a rejected candidate.
    if app_obj.stage not in TERMINAL_STAGES:
        app_obj.stage = "interview"
        db.add(app_obj)

    db.commit()
    db.refresh(sched)
    return {"id": sched.id, "scheduled_at": sched.scheduled_at,
            "status": sched.status}


__all__ = ["router", "APPLICATION_STAGES"]
