from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime

from app.api import deps
from app.db.database import get_db
from app.db.models.all_models import User, JobPosting, Candidate, JobApplication, InterviewSchedule

router = APIRouter()


# ── JOB POSTINGS ──
@router.post("/jobs", status_code=201)
def create_job_posting(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """Create a new job posting."""
    if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "Manager"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    job = JobPosting(
        organization_id=current_user.org_id,
        title=payload["title"],
        department_id=payload.get("department_id"),
        description=payload["description"],
        requirements=payload.get("requirements"),
        location=payload.get("location", "Remote"),
        employment_type=payload.get("employment_type", "Full-time"),
        status=payload.get("status", "open"),
        posted_by_user_id=current_user.id
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"id": job.id, "title": job.title, "status": job.status, "created_at": job.created_at}


@router.get("/jobs")
def list_job_postings(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
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
        "created_at": j.created_at
    } for j in jobs]


# ── CANDIDATES & APPLICATIONS ──
@router.post("/candidates", status_code=201)
def register_candidate(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """Register a new candidate in the talent pool."""
    cand = Candidate(
        organization_id=current_user.org_id,
        full_name=payload["full_name"],
        email=payload["email"],
        phone=payload.get("phone"),
        resume_url=payload.get("resume_url")
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    return {"id": cand.id, "full_name": cand.full_name, "email": cand.email}


@router.get("/candidates")
def list_candidates(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """List all candidates in the organization's talent pool."""
    candidates = db.query(Candidate).filter(
        Candidate.organization_id == current_user.org_id
    ).order_by(Candidate.created_at.desc()).all()
    return [{
        "id": c.id,
        "name": c.full_name,
        "email": c.email,
        "phone": c.phone,
        "resume_url": c.resume_url,
        "created_at": c.created_at
    } for c in candidates]


@router.get("/positions")
def list_positions(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """List open positions (alias for job postings list)."""
    q = db.query(JobPosting).filter(JobPosting.organization_id == current_user.org_id)
    if status:
        q = q.filter(JobPosting.status == status)
    jobs = q.order_by(JobPosting.created_at.desc()).all()
    return [{
        "id": j.id,
        "title": j.title,
        "location": j.location,
        "type": j.employment_type,
        "status": j.status,
        "applicants_count": 0,
        "created_at": j.created_at
    } for j in jobs]


@router.post("/applications", status_code=201)
def submit_job_application(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """Submit candidate job application into pipeline."""
    app_obj = JobApplication(
        organization_id=current_user.org_id,
        job_posting_id=payload["job_posting_id"],
        candidate_id=payload["candidate_id"],
        stage=payload.get("stage", "applied"),
        notes=payload.get("notes")
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
    current_user: User = Depends(deps.get_current_active_user)
):
    """List applicant tracking pipeline applications."""
    q = db.query(JobApplication).filter(JobApplication.organization_id == current_user.org_id)
    if job_id:
        q = q.filter(JobApplication.job_posting_id == job_id)
    if stage:
        q = q.filter(JobApplication.stage == stage)
    apps = q.order_by(JobApplication.applied_at.desc()).all()
    return [{
        "id": a.id,
        "job_title": a.job_posting.title if a.job_posting else "Unknown Job",
        "candidate_name": a.candidate.full_name if a.candidate else "Unknown Candidate",
        "candidate_email": a.candidate.email if a.candidate else "",
        "stage": a.stage,
        "rating": a.rating,
        "applied_at": a.applied_at
    } for a in apps]


@router.patch("/applications/{app_id}/stage")
def update_application_stage(
    app_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """Advance or update candidate stage in recruitment pipeline."""
    if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "Manager"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    app_obj = db.query(JobApplication).filter(
        JobApplication.id == app_id,
        JobApplication.organization_id == current_user.org_id
    ).first()

    if not app_obj:
        raise HTTPException(status_code=404, detail="Application not found")

    app_obj.stage = payload["stage"]
    if "rating" in payload:
        app_obj.rating = payload["rating"]
    if "notes" in payload:
        app_obj.notes = payload["notes"]

    db.commit()
    db.refresh(app_obj)
    return {"id": app_obj.id, "stage": app_obj.stage, "rating": app_obj.rating}


# ── INTERVIEWS ──
@router.post("/interviews", status_code=201)
def schedule_interview(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """Schedule an interview for candidate application."""
    if current_user.role.name not in ["Admin", "SuperAdmin", "OrgAdmin", "Manager"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    sched = InterviewSchedule(
        organization_id=current_user.org_id,
        application_id=payload["application_id"],
        interviewer_user_id=payload.get("interviewer_user_id", current_user.id),
        scheduled_at=datetime.fromisoformat(payload["scheduled_at"]),
        meeting_link=payload.get("meeting_link"),
        status="scheduled"
    )
    db.add(sched)

    # Automatically advance application stage to 'interview'
    app_obj = db.query(JobApplication).filter(JobApplication.id == payload["application_id"]).first()
    if app_obj:
        app_obj.stage = "interview"
        db.add(app_obj)

    db.commit()
    db.refresh(sched)
    return {"id": sched.id, "scheduled_at": sched.scheduled_at, "status": sched.status}
