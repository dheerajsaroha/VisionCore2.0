"""
hcm_router.py — VisionCore 3.0 Sprint 5 Human Capital Management (HCM) Domain REST API

Unified domain router mounted at `/api/v1/hcm`.

Route groups (12):
  /profiles       — Employee master profiles, education, experience, awards, licenses, emergency contacts
  /skills         — Skill taxonomy & employee skill matrix
  /competencies   — Competency gap analysis & nine-box-aware reports
  /goals          — OKR / SMART goals & progress
  /performance    — Performance cycles, ratings dashboard & promotion pipeline
  /reviews        — Performance reviews (self / manager / 360)
  /courses        — Course catalog & modules
  /training       — Learning enrollments & progress
  /certifications — Certificate issuance & tracking
  /career         — Career paths, levels & individual development plans
  /succession     — Key positions, succession plans, nine-box grid & talent pools
  /documents      — Employee document vault

Integrates RBAC (`require_permission`), Correlation IDs, Audit Logging and the
enterprise Event Bus through the consolidated HCM domain service.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user, require_permission
from app.db.models.all_models import User
from app.services.hcm_domain_service import (
    assessment_service,
    career_service,
    certification_service,
    competency_service,
    course_service,
    document_service,
    employee_profile_service,
    goal_service,
    hcm_dashboard,
    learning_service,
    performance_service,
    review_service,
    skill_service,
    succession_service,
    talent_service,
)

router = APIRouter()


def _model_to_dict(obj: Any) -> Optional[Dict[str, Any]]:
    """Delegate to the domain service helper via a local serializer."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    try:
        d = {}
        for c in obj.__table__.columns:
            val = getattr(obj, c.name, None)
            if val is not None and hasattr(val, "isoformat"):
                try:
                    val = val.isoformat()
                except Exception:
                    pass
            elif isinstance(val, UUID):
                val = str(val)
            d[c.name] = val
        return d
    except Exception:
        return {"id": getattr(obj, "id", None)}


# =============================================================================
#  Request Schemas
# =============================================================================

class ProfileUpdateIn(BaseModel):
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    marital_status: Optional[str] = None
    nationality: Optional[str] = None
    blood_group: Optional[str] = None
    languages_spoken: Optional[dict] = None
    medical_allergies: Optional[str] = None
    disability_status: Optional[str] = None
    medical_fitness_status: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry: Optional[str] = None
    visa_type: Optional[str] = None
    visa_expiry: Optional[str] = None
    work_permit_number: Optional[str] = None
    bg_verification_status: Optional[str] = None
    bg_verification_date: Optional[str] = None
    bg_vendor_name: Optional[str] = None


class EducationCreate(BaseModel):
    degree: str
    field_of_study: str
    institution_name: str
    start_year: int
    end_year: Optional[int] = None
    grade_or_gpa: Optional[str] = None
    is_verified: bool = False


class ExperienceCreate(BaseModel):
    company_name: str
    job_title: str
    start_date: str
    end_date: Optional[str] = None
    is_current: bool = False
    description: Optional[str] = None
    is_verified: bool = False


class AwardCreate(BaseModel):
    title: str
    awarded_by: str
    award_date: str
    category: str = "spot_award"
    cash_prize: Optional[float] = None
    description: Optional[str] = None


class LicenseCreate(BaseModel):
    license_name: str
    license_number: str
    issuing_authority: str
    issue_date: str
    expiry_date: Optional[str] = None
    status: str = "active"


class EmergencyContactCreate(BaseModel):
    contact_name: str
    relationship_type: str
    phone_number: str
    alternate_phone: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool = True


class GoalCreate(BaseModel):
    user_id: Optional[int] = None
    cycle_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    goal_type: str = "individual"
    goal_framework: str = "smart"
    target_value: Optional[float] = None
    current_value: float = 0.0
    unit: Optional[str] = None
    due_date: Optional[str] = None
    status: str = "active"
    priority: str = "medium"


class GoalProgressIn(BaseModel):
    value: float
    note: Optional[str] = None


class ReviewCreate(BaseModel):
    cycle_id: int
    reviewee_user_id: int
    reviewer_user_id: Optional[int] = None
    review_type: str = "self"


class ReviewSubmit(BaseModel):
    overall_score: Optional[float] = None
    strengths: Optional[str] = None
    areas_for_improvement: Optional[str] = None
    comments: Optional[str] = None


class CourseCreate(BaseModel):
    category_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    instructor_name: Optional[str] = None
    course_type: str = "online"
    duration_hours: float = 1.0
    pass_percentage: float = 70.0
    is_mandatory: bool = False
    is_active: bool = True


class EnrollmentCreate(BaseModel):
    course_id: int
    user_id: Optional[int] = None


class EnrollmentComplete(BaseModel):
    score: Optional[float] = None


class AssessmentSubmit(BaseModel):
    quiz_id: int
    user_id: Optional[int] = None
    enrollment_id: Optional[int] = None
    score: float
    max_score: float = 100.0
    response_data: Optional[dict] = None


class SkillCreate(BaseModel):
    user_id: Optional[int] = None
    skill_id: int
    proficiency_level: str = "intermediate"
    source: str = "course_completion"
    verified_by: Optional[int] = None


class CertificationIssue(BaseModel):
    user_id: int
    course_id: int
    enrollment_id: Optional[int] = None
    expiry_date: Optional[str] = None
    certificate_url: Optional[str] = None


class CareerPathCreate(BaseModel):
    title: str
    department_id: Optional[int] = None
    description: Optional[str] = None
    total_levels: int = 5


class IDPCreate(BaseModel):
    user_id: int
    target_career_level_id: Optional[int] = None
    target_position_title: Optional[str] = None
    status: str = "in_progress"
    target_completion_date: Optional[str] = None


class KeyPositionCreate(BaseModel):
    title: str
    department_id: Optional[int] = None
    criticality_level: str = "critical"
    current_incumbent_user_id: Optional[int] = None
    vacancy_risk_level: str = "low"
    impact_rating: float = 4.0


class SuccessionPlanCreate(BaseModel):
    key_position_id: int
    target_fill_timeline_months: int = 6
    strategy_notes: Optional[str] = None
    status: str = "active"


class NominateIn(BaseModel):
    candidate_user_id: int
    readiness_rating: str = "ready_1_year"
    nomination_notes: Optional[str] = None


class NineBoxEvaluate(BaseModel):
    user_id: int
    performance_rating: int = 2
    potential_rating: int = 2
    cycle_id: Optional[int] = None


class DocumentUpload(BaseModel):
    user_id: Optional[int] = None
    file_id: Optional[str] = None
    title: str
    document_type: str
    version: int = 1
    file_url: Optional[str] = None
    access_level: str = "confidential"
    is_signed: bool = False


class TalentPoolCreate(BaseModel):
    name: str
    description: Optional[str] = None
    pool_type: str = "executive"
    status: str = "active"


class TalentMemberAdd(BaseModel):
    user_id: int
    readiness_level: str = "ready_1_year"
    nomination_reason: Optional[str] = None


_ADMIN_ROLES = ("Admin", "SuperAdmin", "OrgAdmin")


# =============================================================================
#  PROFILES /api/v1/hcm/profiles
# =============================================================================

@router.get("/profiles/dossier/{user_id}", tags=["profiles"])
def profile_dossier(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Full employee dossier: profile + education + experience + awards + licenses + emergency contacts."""
    if user_id != current_user.id and current_user.role.name not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Cannot view another employee's dossier")
    return employee_profile_service.profile_dossier(db, current_user.org_id, user_id)


@router.get("/profiles", tags=["profiles"])
def list_profiles(
    user_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    """List employee profiles with optional user filter."""
    from app.db.models.all_models import EmployeeProfile
    q = db.query(EmployeeProfile).filter(EmployeeProfile.org_id == current_user.org_id)
    if user_id:
        q = q.filter(EmployeeProfile.user_id == user_id)
    profiles = q.offset(skip).limit(limit).all()
    return [_model_to_dict(p) for p in profiles]


@router.put("/profiles/{user_id}", tags=["profiles"])
def upsert_profile(
    user_id: int,
    payload: ProfileUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("employee.profile.update", "employee.update")),
) -> Dict[str, Any]:
    """Create or update an employee's extended master profile."""
    profile = employee_profile_service.upsert_profile(
        db, current_user.org_id, user_id, payload.model_dump(exclude_none=True),
        actor_id=current_user.id,
    )
    return _model_to_dict(profile)


@router.post("/profiles/{user_id}/education", status_code=status.HTTP_201_CREATED, tags=["profiles"])
def add_education(
    user_id: int,
    payload: EducationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("employee.profile.update", "employee.update")),
) -> Dict[str, Any]:
    record = employee_profile_service.add_education(
        db, current_user.org_id, user_id, payload.model_dump(), actor_id=current_user.id)
    return _model_to_dict(record)


@router.get("/profiles/{user_id}/education", tags=["profiles"])
def list_education(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    if user_id != current_user.id and current_user.role.name not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Forbidden")
    return [_model_to_dict(e) for e in
            employee_profile_service.list_education(db, current_user.org_id, user_id)]


@router.post("/profiles/{user_id}/experience", status_code=status.HTTP_201_CREATED, tags=["profiles"])
def add_experience(
    user_id: int,
    payload: ExperienceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("employee.profile.update", "employee.update")),
) -> Dict[str, Any]:
    record = employee_profile_service.add_experience(
        db, current_user.org_id, user_id, payload.model_dump(), actor_id=current_user.id)
    return _model_to_dict(record)


@router.get("/profiles/{user_id}/experience", tags=["profiles"])
def list_experience(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    if user_id != current_user.id and current_user.role.name not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Forbidden")
    return [_model_to_dict(e) for e in
            employee_profile_service.list_experience(db, current_user.org_id, user_id)]


@router.post("/profiles/{user_id}/awards", status_code=status.HTTP_201_CREATED, tags=["profiles"])
def add_award(
    user_id: int,
    payload: AwardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("employee.profile.update", "employee.update")),
) -> Dict[str, Any]:
    record = employee_profile_service.add_award(
        db, current_user.org_id, user_id, payload.model_dump(), actor_id=current_user.id)
    return _model_to_dict(record)


@router.get("/profiles/{user_id}/awards", tags=["profiles"])
def list_awards(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    if user_id != current_user.id and current_user.role.name not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Forbidden")
    return [_model_to_dict(a) for a in
            employee_profile_service.list_awards(db, current_user.org_id, user_id)]


@router.post("/profiles/{user_id}/licenses", status_code=status.HTTP_201_CREATED, tags=["profiles"])
def add_license(
    user_id: int,
    payload: LicenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("employee.profile.update", "employee.update")),
) -> Dict[str, Any]:
    record = employee_profile_service.add_license(
        db, current_user.org_id, user_id, payload.model_dump(), actor_id=current_user.id)
    return _model_to_dict(record)


@router.get("/profiles/{user_id}/licenses", tags=["profiles"])
def list_licenses(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    if user_id != current_user.id and current_user.role.name not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Forbidden")
    return [_model_to_dict(l) for l in
            employee_profile_service.list_licenses(db, current_user.org_id, user_id)]


@router.post("/profiles/{user_id}/emergency-contacts", status_code=status.HTTP_201_CREATED, tags=["profiles"])
def add_emergency_contact(
    user_id: int,
    payload: EmergencyContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("employee.profile.update", "employee.update")),
) -> Dict[str, Any]:
    record = employee_profile_service.add_emergency_contact(
        db, current_user.org_id, user_id, payload.model_dump(), actor_id=current_user.id)
    return _model_to_dict(record)


@router.get("/profiles/{user_id}/emergency-contacts", tags=["profiles"])
def list_emergency_contacts(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    if user_id != current_user.id and current_user.role.name not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Forbidden")
    return [_model_to_dict(c) for c in
            employee_profile_service.list_emergency_contacts(db, current_user.org_id, user_id)]


# =============================================================================
#  SKILLS /api/v1/hcm/skills
# =============================================================================

@router.get("/skills", tags=["skills"])
def list_skill_taxonomy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    from app.db.models.all_models import SkillMaster
    skills = (db.query(SkillMaster)
              .filter(SkillMaster.organization_id == current_user.org_id,
                      SkillMaster.is_active.is_(True))
              .order_by(SkillMaster.name).all())
    return [_model_to_dict(s) for s in skills]


@router.get("/skills/matrix", tags=["skills"])
def skill_matrix(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Employee skill matrix (all org) or single employee skill list."""
    if user_id:
        records = skill_service.list_skills(db, current_user.org_id, user_id)
        return {"user_id": user_id, "skills": [_model_to_dict(r) for r in records]}
    return skill_service.skill_matrix(db, current_user.org_id)


@router.post("/skills/assign", status_code=status.HTTP_201_CREATED, tags=["skills"])
def assign_skill(
    payload: SkillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("skill.manage", "learning.skill.update")),
) -> Dict[str, Any]:
    target_user_id = payload.user_id or current_user.id
    record = skill_service.add_or_update_skill(
        db, current_user.org_id, target_user_id, payload.skill_id,
        payload.proficiency_level, source=payload.source,
        verified_by=payload.verified_by, actor_id=current_user.id,
    )
    return _model_to_dict(record)


# =============================================================================
#  COMPETENCIES /api/v1/hcm/competencies
# =============================================================================

@router.get("/competencies", tags=["competencies"])
def list_competencies(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    from app.db.models.all_models import Competency
    comps = (db.query(Competency)
             .filter(Competency.organization_id == current_user.org_id,
                     Competency.is_active.is_(True))
             .order_by(Competency.category, Competency.name)
             .offset(skip).limit(limit).all())
    return [_model_to_dict(c) for c in comps]


@router.get("/competencies/gap/{user_id}", tags=["competencies"])
def competency_gap(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Per-employee competency coverage and gap analysis."""
    return competency_service.competency_gap(db, current_user.org_id, user_id)


# =============================================================================
#  GOALS /api/v1/hcm/goals
# =============================================================================

@router.get("/goals", tags=["goals"])
def list_goals(
    user_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    target_user_id = user_id or current_user.id
    goals = goal_service.list_goals(db, current_user.org_id, target_user_id, status_filter)
    res = []
    for g in goals:
        d = _model_to_dict(g)
        if g.user:
            d["user_name"] = g.user.full_name
        res.append(d)
    return res


@router.post("/goals", status_code=status.HTTP_201_CREATED, tags=["goals"])
def create_goal(
    payload: GoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("performance.goal.create", "goal.manage")),
) -> Dict[str, Any]:
    target_user_id = payload.user_id or current_user.id
    g = goal_service.create_goal(
        db, current_user.org_id, target_user_id,
        payload.model_dump(exclude={"user_id"}),
        actor_id=current_user.id,
    )
    return _model_to_dict(g)


@router.post("/goals/{goal_id}/progress", tags=["goals"])
def log_goal_progress(
    goal_id: int,
    payload: GoalProgressIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("performance.goal.update", "goal.manage")),
) -> Dict[str, Any]:
    try:
        g = goal_service.log_progress(
            db, current_user.org_id, goal_id, current_user.id,
            payload.value, payload.note, actor_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _model_to_dict(g)


# =============================================================================
#  PERFORMANCE /api/v1/hcm/performance
# =============================================================================

@router.get("/performance/cycles", tags=["performance"])
def list_performance_cycles(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    cycles = performance_service.list_cycles(db, current_user.org_id, status_filter)
    return [_model_to_dict(c) for c in cycles]


@router.post("/performance/cycles", status_code=status.HTTP_201_CREATED, tags=["performance"])
def create_performance_cycle(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("performance.cycle.create", "performance.manage")),
) -> Dict[str, Any]:
    cycle = performance_service.create_cycle(
        db, current_user.org_id, payload, created_by=current_user.id)
    return _model_to_dict(cycle)


@router.get("/performance/ratings", tags=["performance"])
def performance_ratings(
    cycle_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Org-wide ratings distribution dashboard."""
    return performance_service.ratings_dashboard(db, current_user.org_id, cycle_id)


# =============================================================================
#  REVIEWS /api/v1/hcm/reviews
# =============================================================================

@router.get("/reviews", tags=["reviews"])
def list_reviews(
    user_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    reviews = review_service.list_reviews(db, current_user.org_id, user_id, status_filter)
    res = []
    for r in reviews:
        d = _model_to_dict(r)
        if r.reviewee:
            d["reviewee_name"] = r.reviewee.full_name
        if r.reviewer:
            d["reviewer_name"] = r.reviewer.full_name
        res.append(d)
    return res


@router.post("/reviews", status_code=status.HTTP_201_CREATED, tags=["reviews"])
def create_review(
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("performance.review.create", "performance.manage")),
) -> Dict[str, Any]:
    r = review_service.create_review(
        db, current_user.org_id, payload.model_dump(), actor_id=current_user.id)
    return _model_to_dict(r)


@router.post("/reviews/{review_id}/submit", tags=["reviews"])
def submit_review(
    review_id: int,
    payload: ReviewSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("performance.review.submit", "performance.manage")),
) -> Dict[str, Any]:
    try:
        r = review_service.submit_review(
            db, current_user.org_id, review_id, payload.model_dump(exclude_none=True),
            actor_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _model_to_dict(r)


# =============================================================================
#  COURSES /api/v1/hcm/courses
# =============================================================================

@router.get("/courses", tags=["courses"])
def list_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    courses = course_service.list_courses(db, current_user.org_id)
    res = []
    for c in courses:
        d = _model_to_dict(c)
        if c.category:
            d["category_name"] = c.category.name
        d["modules"] = [_model_to_dict(m) for m in c.modules]
        res.append(d)
    return res


@router.post("/courses", status_code=status.HTTP_201_CREATED, tags=["courses"])
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("learning.course.create", "learning.manage")),
) -> Dict[str, Any]:
    c = course_service.create_course(
        db, current_user.org_id, payload.model_dump(), actor_id=current_user.id)
    return _model_to_dict(c)


# =============================================================================
#  TRAINING /api/v1/hcm/training
# =============================================================================

@router.post("/training/enrollments", status_code=status.HTTP_201_CREATED, tags=["training"])
def enroll_in_course(
    payload: EnrollmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("learning.course.enroll", "learning.manage")),
) -> Dict[str, Any]:
    target_user_id = payload.user_id or current_user.id
    e = learning_service.enroll(
        db, current_user.org_id, payload.course_id, target_user_id,
        assigned_by=current_user.id if target_user_id != current_user.id else None,
        actor_id=current_user.id,
    )
    return _model_to_dict(e)


@router.get("/training/enrollments", tags=["training"])
def list_enrollments(
    user_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    enrollments = learning_service.list_enrollments(
        db, current_user.org_id, user_id, status_filter)
    res = []
    for e in enrollments:
        d = _model_to_dict(e)
        if e.course:
            d["course_title"] = e.course.title
        if e.user:
            d["user_name"] = e.user.full_name
        res.append(d)
    return res


@router.post("/training/enrollments/{enrollment_id}/complete", tags=["training"])
def complete_enrollment(
    enrollment_id: int,
    payload: EnrollmentComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("learning.course.update", "learning.manage")),
) -> Dict[str, Any]:
    try:
        e = learning_service.mark_completed(
            db, current_user.org_id, enrollment_id, payload.score, actor_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _model_to_dict(e)


@router.post("/training/assessments/submit", tags=["training"])
def submit_assessment(
    payload: AssessmentSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("learning.assessment.submit", "learning.manage")),
) -> Dict[str, Any]:
    target_user_id = payload.user_id or current_user.id
    attempt = assessment_service.submit_attempt(
        db, current_user.org_id, payload.quiz_id, target_user_id,
        payload.score, payload.max_score, payload.enrollment_id, payload.response_data,
    )
    return _model_to_dict(attempt)


# =============================================================================
#  CERTIFICATIONS /api/v1/hcm/certifications
# =============================================================================

@router.get("/certifications", tags=["certifications"])
def list_certifications(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    certs = certification_service.list_certificates(db, current_user.org_id, user_id)
    res = []
    for c in certs:
        d = _model_to_dict(c)
        if c.course:
            d["course_title"] = c.course.title
        if c.user:
            d["user_name"] = c.user.full_name
        res.append(d)
    return res


@router.post("/certifications/issue", status_code=status.HTTP_201_CREATED, tags=["certifications"])
def issue_certification(
    payload: CertificationIssue,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("learning.certificate.issue", "learning.manage")),
) -> Dict[str, Any]:
    cert = certification_service.issue_certificate(
        db, current_user.org_id, payload.user_id, payload.course_id,
        payload.enrollment_id, payload.expiry_date, payload.certificate_url,
        actor_id=current_user.id,
    )
    return _model_to_dict(cert)


# =============================================================================
#  CAREER /api/v1/hcm/career
# =============================================================================

@router.get("/career/paths", tags=["career"])
def list_career_paths(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    paths = career_service.list_career_paths(db, current_user.org_id)
    res = []
    for p in paths:
        d = _model_to_dict(p)
        if p.department:
            d["department_name"] = p.department.name
        d["levels"] = [_model_to_dict(l) for l in p.levels]
        res.append(d)
    return res


@router.post("/career/paths", status_code=status.HTTP_201_CREATED, tags=["career"])
def create_career_path(
    payload: CareerPathCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("career.manage", "succession.plan.create")),
) -> Dict[str, Any]:
    p = career_service.create_career_path(
        db, current_user.org_id, payload.model_dump(), actor_id=current_user.id)
    return _model_to_dict(p)


@router.get("/career/idp", tags=["career"])
def list_idps(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    idps = career_service.list_idps(db, current_user.org_id, user_id)
    res = []
    for i in idps:
        d = _model_to_dict(i)
        if i.user:
            d["user_name"] = i.user.full_name
        res.append(d)
    return res


@router.post("/career/idp", status_code=status.HTTP_201_CREATED, tags=["career"])
def create_idp(
    payload: IDPCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("career.manage", "succession.plan.create")),
) -> Dict[str, Any]:
    idp = career_service.create_idp(
        db, current_user.org_id, payload.user_id,
        payload.model_dump(exclude={"user_id"}), actor_id=current_user.id)
    return _model_to_dict(idp)


# =============================================================================
#  SUCCESSION /api/v1/hcm/succession
# =============================================================================

@router.get("/succession/key-positions", tags=["succession"])
def list_key_positions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    positions = succession_service.list_key_positions(db, current_user.org_id)
    res = []
    for p in positions:
        d = _model_to_dict(p)
        if p.department:
            d["department_name"] = p.department.name
        if p.incumbent:
            d["incumbent_name"] = p.incumbent.full_name
        res.append(d)
    return res


@router.post("/succession/key-positions", status_code=status.HTTP_201_CREATED, tags=["succession"])
def create_key_position(
    payload: KeyPositionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("succession.plan.create", "succession.manage")),
) -> Dict[str, Any]:
    kp = succession_service.create_key_position(
        db, current_user.org_id, payload.model_dump(), actor_id=current_user.id)
    return _model_to_dict(kp)


@router.get("/succession/plans", tags=["succession"])
def list_succession_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    plans = succession_service.list_plans(db, current_user.org_id)
    res = []
    for p in plans:
        d = _model_to_dict(p)
        if p.key_position:
            d["key_position_title"] = p.key_position.title
        d["candidates"] = [_model_to_dict(c) for c in p.candidates]
        res.append(d)
    return res


@router.post("/succession/plans", status_code=status.HTTP_201_CREATED, tags=["succession"])
def create_succession_plan(
    payload: SuccessionPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("succession.plan.create", "succession.manage")),
) -> Dict[str, Any]:
    plan = succession_service.create_plan(
        db, current_user.org_id, payload.model_dump(), actor_id=current_user.id)
    return _model_to_dict(plan)


@router.post("/succession/plans/{plan_id}/candidates", status_code=status.HTTP_201_CREATED, tags=["succession"])
def nominate_candidate(
    plan_id: int,
    payload: NominateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("succession.plan.update", "succession.manage")),
) -> Dict[str, Any]:
    candidate = succession_service.nominate_candidate(
        db, current_user.org_id, plan_id, payload.candidate_user_id,
        payload.readiness_rating, payload.nomination_notes, actor_id=current_user.id,
    )
    return _model_to_dict(candidate)


@router.get("/succession/nine-box", tags=["succession"])
def nine_box_grid(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    grid = succession_service.nine_box_grid(db, current_user.org_id)
    res = []
    for g in grid:
        d = _model_to_dict(g)
        if g.user:
            d["user_name"] = g.user.full_name
        res.append(d)
    return res


@router.post("/succession/nine-box", status_code=status.HTTP_201_CREATED, tags=["succession"])
def evaluate_nine_box(
    payload: NineBoxEvaluate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("succession.plan.update", "succession.manage")),
) -> Dict[str, Any]:
    g = succession_service.evaluate_nine_box(
        db, current_user.org_id, payload.user_id,
        payload.performance_rating, payload.potential_rating,
        evaluated_by=current_user.id, cycle_id=payload.cycle_id,
    )
    return _model_to_dict(g)


@router.get("/succession/talent-pools", tags=["succession"])
def list_talent_pools(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    pools = talent_service.list_pools(db, current_user.org_id)
    res = []
    for p in pools:
        d = _model_to_dict(p)
        d["members"] = [_model_to_dict(m) for m in p.members]
        res.append(d)
    return res


@router.post("/succession/talent-pools", status_code=status.HTTP_201_CREATED, tags=["succession"])
def create_talent_pool(
    payload: TalentPoolCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("succession.plan.create", "succession.manage")),
) -> Dict[str, Any]:
    pool = talent_service.create_pool(
        db, current_user.org_id, payload.model_dump(), actor_id=current_user.id)
    return _model_to_dict(pool)


@router.post("/succession/talent-pools/{pool_id}/members", status_code=status.HTTP_201_CREATED, tags=["succession"])
def add_talent_pool_member(
    pool_id: int,
    payload: TalentMemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("succession.plan.update", "succession.manage")),
) -> Dict[str, Any]:
    member = talent_service.add_member(
        db, current_user.org_id, pool_id, payload.user_id,
        payload.readiness_level, payload.nomination_reason, actor_id=current_user.id,
    )
    return _model_to_dict(member)


@router.get("/succession/talent-dashboard", tags=["succession"])
def talent_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Talent dashboard — pools, ready-now pipeline, high-potential counts."""
    return talent_service.talent_dashboard(db, current_user.org_id)


# =============================================================================
#  DOCUMENTS /api/v1/hcm/documents
# =============================================================================

@router.get("/documents", tags=["documents"])
def list_documents(
    user_id: Optional[int] = None,
    document_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    docs = document_service.list_documents(db, current_user.org_id, user_id, document_type)
    res = []
    for d in docs:
        item = _model_to_dict(d)
        if d.user:
            item["user_name"] = d.user.full_name
        res.append(item)
    return res


@router.post("/documents", status_code=status.HTTP_201_CREATED, tags=["documents"])
def upload_document(
    payload: DocumentUpload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("document.upload", "employee.document.manage")),
) -> Dict[str, Any]:
    target_user_id = payload.user_id or current_user.id
    doc = document_service.upload_document(
        db, current_user.org_id, target_user_id,
        payload.model_dump(exclude={"user_id"}), actor_id=current_user.id,
    )
    return _model_to_dict(doc)


@router.post("/documents/{document_id}/sign", tags=["documents"])
def sign_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_permission("document.sign", "employee.document.manage")),
) -> Dict[str, Any]:
    try:
        doc = document_service.sign_document(
            db, current_user.org_id, document_id, actor_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _model_to_dict(doc)


# =============================================================================
#  HCM EXECUTIVE DASHBOARD /api/v1/hcm/dashboard
# =============================================================================

@router.get("/dashboard", tags=["hcm-dashboard"])
def get_hcm_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Unified HCM executive dashboard across all domains."""
    return hcm_dashboard(db, current_user.org_id)


@router.get("/health", tags=["hcm-dashboard"])
def hcm_health():
    """Liveness check for the HCM domain router."""
    return {"status": "ok", "domain": "hcm", "route_groups": 12}

