"""
learning.py — FastAPI Router for Enterprise Learning & Development System
Sprint 4 — Entity 2
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api import deps
from app.api.deps import (
    get_db,
    get_current_active_user,
    normalize_role_name,
    require_permission,
)
from app.db.models.all_models import (
    User, CourseCategory, Course, CourseModule, CourseEnrollment, ModuleProgress,
    TrainingSession, SessionAttendance, AssessmentQuiz, AssessmentQuestion,
    AssessmentAttempt, SkillMaster, EmployeeSkill, Certificate, TrainingBudget
)
from app.crud.crud_learning import (
    crud_course_engine, crud_assessment_engine, crud_skill_engine,
    crud_certificate_engine, crud_training_budget
)
from app.schema.learning import (
    CourseCategoryCreate, CourseCategoryResponse, CourseCreate, CourseUpdate,
    CourseModuleCreate, CourseModuleResponse, CourseResponse, CourseEnrollmentCreate,
    CourseProgressUpdate, CourseEnrollmentResponse, TrainingSessionCreate,
    TrainingSessionResponse, SessionAttendanceResponse, AssessmentQuizCreate,
    AssessmentQuizResponse, QuizSubmit, AssessmentAttemptResponse, SkillMasterCreate,
    SkillMasterResponse, EmployeeSkillCreate, EmployeeSkillResponse, CertificateResponse,
    TrainingBudgetCreate, TrainingBudgetResponse, LearningAnalyticsResponse
)
from app.db.seed_learning import seed_learning_defaults_for_org
from app.services.permission_service import PermissionService


def _has(db: Session, user: User, *permission_names: str) -> bool:
    """Whether `user` holds any of `permission_names`.

    These checks used to call `current_user.has_permission(...)`, but `User` has
    no such method, so every one of them raised `AttributeError` and returned
    500 — including the plain `GET /enrollments`, `GET /employee-skills` and
    `GET /certificates` reads. An employee opening Learning & Development hit
    three server errors on load.

    Only SuperAdmin is treated as holding everything, matching `require_permission`.
    """
    if user.role and normalize_role_name(user.role.name) == "SuperAdmin":
        return True
    return PermissionService.has_any_permission(db, user, list(permission_names))

router = APIRouter(dependencies=[Depends(deps.require_feature("training"))])


# ── CATEGORIES ──
@router.post("/categories", response_model=CourseCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_course_category(
    payload: CourseCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("learning.create")),
):
    return crud_course_engine.create_category(db, current_user.org_id, payload.name, payload.description)


@router.get("/categories", response_model=List[CourseCategoryResponse])
def list_course_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    seed_learning_defaults_for_org(db, current_user.org_id)
    return crud_course_engine.get_categories(db, current_user.org_id)


# ── COURSES & MODULES ──
@router.post("/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("learning.create")),
):
    c = crud_course_engine.create_course(db, current_user.org_id, payload.model_dump())
    return {**c.__dict__, "category_name": c.category.name if c.category else None, "modules": []}


@router.get("/courses", response_model=List[CourseResponse])
def list_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    seed_learning_defaults_for_org(db, current_user.org_id)
    courses = crud_course_engine.get_courses(db, current_user.org_id)
    res = []
    for c in courses:
        res.append({
            **c.__dict__,
            "category_name": c.category.name if c.category else None,
            "modules": [m.__dict__ for m in c.modules]
        })
    return res


@router.post("/courses/{course_id}/modules", response_model=CourseModuleResponse, status_code=status.HTTP_201_CREATED)
def add_course_module(
    course_id: int,
    payload: CourseModuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("learning.create")),
):
    course = crud_course_engine.get_course_by_id(db, course_id)
    if not course or course.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Course not found")
    return crud_course_engine.add_module(db, course_id, payload.model_dump())


# ── ENROLLMENTS & PROGRESS ──
@router.post("/enrollments", response_model=CourseEnrollmentResponse, status_code=status.HTTP_201_CREATED)
def enroll_in_course(
    payload: CourseEnrollmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("learning.view")),
):
    target_user_id = payload.user_id or current_user.id
    if target_user_id != current_user.id and not _has(db, current_user, "learning.manage"):
        raise HTTPException(status_code=403, detail="Unauthorized")

    course = crud_course_engine.get_course_by_id(db, payload.course_id)
    if not course or course.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Course not found")

    enrollment = crud_course_engine.enroll_user(db, current_user.org_id, payload.course_id, target_user_id, assigned_by_id=current_user.id if target_user_id != current_user.id else None)
    return {
        **enrollment.__dict__,
        "course_title": course.title,
        "user_name": enrollment.user.full_name if enrollment.user else None
    }


@router.get("/enrollments", response_model=List[CourseEnrollmentResponse])
def list_enrollments(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    target_user_id = user_id
    if target_user_id is None and not _has(db, current_user, "learning.view_org"):
        target_user_id = current_user.id

    q = db.query(CourseEnrollment).filter(CourseEnrollment.organization_id == current_user.org_id)
    if target_user_id:
        q = q.filter(CourseEnrollment.user_id == target_user_id)

    enrollments = q.all()
    res = []
    for e in enrollments:
        res.append({
            **e.__dict__,
            "course_title": e.course.title if e.course else None,
            "user_name": e.user.full_name if e.user else None
        })
    return res


@router.post("/enrollments/{enrollment_id}/progress", response_model=CourseEnrollmentResponse)
def update_enrollment_progress(
    enrollment_id: int,
    payload: CourseProgressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    enrollment = db.query(CourseEnrollment).filter(CourseEnrollment.id == enrollment_id).first()
    if not enrollment or enrollment.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    if enrollment.user_id != current_user.id and not _has(db, current_user, "learning.manage"):
        raise HTTPException(status_code=403, detail="Unauthorized")

    updated = crud_course_engine.update_module_progress(db, enrollment, payload.module_id, payload.time_spent_seconds, payload.completed)
    return {
        **updated.__dict__,
        "course_title": updated.course.title if updated.course else None,
        "user_name": updated.user.full_name if updated.user else None
    }


# ── TRAINING SESSIONS ──
@router.post("/sessions", response_model=TrainingSessionResponse, status_code=status.HTTP_201_CREATED)
def create_training_session(
    payload: TrainingSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("learning.create")),
):

    session = TrainingSession(
        organization_id=current_user.org_id,
        course_id=payload.course_id,
        trainer_user_id=payload.trainer_user_id or current_user.id,
        title=payload.title,
        location_or_link=payload.location_or_link,
        start_time=payload.start_time,
        end_time=payload.end_time,
        max_participants=payload.max_participants,
        status="scheduled"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        **session.__dict__,
        "course_title": session.course.title if session.course else None,
        "trainer_name": session.trainer.full_name if session.trainer else None
    }


@router.get("/sessions", response_model=List[TrainingSessionResponse])
def list_training_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    sessions = db.query(TrainingSession).filter(TrainingSession.organization_id == current_user.org_id).all()
    res = []
    for s in sessions:
        res.append({
            **s.__dict__,
            "course_title": s.course.title if s.course else None,
            "trainer_name": s.trainer.full_name if s.trainer else None
        })
    return res


# ── ASSESSMENTS & QUIZZES ──
@router.post("/quizzes", response_model=AssessmentQuizResponse, status_code=status.HTTP_201_CREATED)
def create_quiz(
    payload: AssessmentQuizCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("learning.create")),
):
    quiz = crud_assessment_engine.create_quiz(db, payload.course_id, payload.model_dump())
    return {
        **quiz.__dict__,
        "questions": [q.__dict__ for q in quiz.questions]
    }


@router.get("/quizzes", response_model=List[AssessmentQuizResponse])
def list_quizzes(
    course_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    q = db.query(AssessmentQuiz).join(Course).filter(Course.organization_id == current_user.org_id)
    if course_id:
        q = q.filter(AssessmentQuiz.course_id == course_id)
    quizzes = q.all()
    res = []
    for quiz in quizzes:
        res.append({
            **quiz.__dict__,
            "questions": [quest.__dict__ for quest in quiz.questions]
        })
    return res


@router.post("/quizzes/{quiz_id}/submit", response_model=AssessmentAttemptResponse)
def submit_quiz(
    quiz_id: int,
    payload: QuizSubmit,
    enrollment_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    quiz = db.query(AssessmentQuiz).filter(AssessmentQuiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    attempt = crud_assessment_engine.submit_quiz_attempt(db, quiz, current_user.id, enrollment_id, payload.answers)
    return attempt


# ── SKILLS MATRIX ──
@router.post("/skills", response_model=SkillMasterResponse, status_code=status.HTTP_201_CREATED)
def create_skill(
    payload: SkillMasterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("learning.manage")),
):
    return crud_skill_engine.create_skill(db, current_user.org_id, payload.name, payload.category, payload.description)


@router.get("/skills", response_model=List[SkillMasterResponse])
def list_skills(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    seed_learning_defaults_for_org(db, current_user.org_id)
    return crud_skill_engine.get_skills(db, current_user.org_id)


@router.post("/employee-skills", response_model=EmployeeSkillResponse, status_code=status.HTTP_201_CREATED)
def add_employee_skill(
    payload: EmployeeSkillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("learning.update")),
):
    target_user_id = payload.user_id or current_user.id
    if target_user_id != current_user.id and not _has(db, current_user, "learning.manage"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    es = crud_skill_engine.add_or_update_employee_skill(db, current_user.org_id, target_user_id, payload.skill_id, payload.proficiency_level, payload.source)
    return {
        **es.__dict__,
        "user_name": es.user.full_name if es.user else None,
        "skill_name": es.skill.name if es.skill else None
    }


@router.get("/employee-skills", response_model=List[EmployeeSkillResponse])
def list_employee_skills(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    target_user_id = user_id
    if target_user_id is None and not _has(db, current_user, "learning.view_org"):
        target_user_id = current_user.id

    q = db.query(EmployeeSkill).filter(EmployeeSkill.organization_id == current_user.org_id)
    if target_user_id:
        q = q.filter(EmployeeSkill.user_id == target_user_id)
    skills = q.all()
    res = []
    for s in skills:
        res.append({
            **s.__dict__,
            "user_name": s.user.full_name if s.user else None,
            "skill_name": s.skill.name if s.skill else None
        })
    return res


# ── CERTIFICATES ──
@router.get("/certificates", response_model=List[CertificateResponse])
def list_certificates(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    target_user_id = user_id
    if target_user_id is None and not _has(db, current_user, "learning.view_org"):
        target_user_id = current_user.id

    q = db.query(Certificate).filter(Certificate.organization_id == current_user.org_id)
    if target_user_id:
        q = q.filter(Certificate.user_id == target_user_id)

    certs = q.all()
    res = []
    for c in certs:
        res.append({
            **c.__dict__,
            "user_name": c.user.full_name if c.user else None,
            "course_title": c.course.title if c.course else None
        })
    return res


# ── BUDGET ──
@router.get("/budget", response_model=List[TrainingBudgetResponse])
def get_training_budgets(
    fiscal_year: int = 2025,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("learning.view_org")),
):
    seed_learning_defaults_for_org(db, current_user.org_id)
    budgets = db.query(TrainingBudget).filter(
        TrainingBudget.organization_id == current_user.org_id,
        TrainingBudget.fiscal_year == fiscal_year
    ).all()
    res = []
    for b in budgets:
        res.append({
            **b.__dict__,
            "department_name": b.department.name if b.department else "Organization-Wide"
        })
    return res


# ── ANALYTICS ──
@router.get("/analytics/dashboard", response_model=LearningAnalyticsResponse)
def get_learning_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("learning.view_org")),
):
    org_id = current_user.org_id
    total_courses = db.query(Course).filter(Course.organization_id == org_id, Course.is_active.is_(True)).count()
    enrolled_count = db.query(CourseEnrollment).filter(CourseEnrollment.organization_id == org_id).count()

    completed_count = db.query(CourseEnrollment).filter(CourseEnrollment.organization_id == org_id, CourseEnrollment.status == "completed").count()
    completion_rate = round((completed_count / max(1, enrolled_count)) * 100, 1)

    certs_count = db.query(Certificate).filter(Certificate.organization_id == org_id).count()
    active_sessions = db.query(TrainingSession).filter(TrainingSession.organization_id == org_id, TrainingSession.status == "scheduled").count()

    budgets = db.query(TrainingBudget).filter(TrainingBudget.organization_id == org_id).all()
    spent_budget = sum(float(b.spent_amount) for b in budgets)

    skills = db.query(SkillMaster).filter(SkillMaster.organization_id == org_id).limit(5).all()
    top_skills = [{"name": s.name, "category": s.category, "count": db.query(EmployeeSkill).filter(EmployeeSkill.skill_id == s.id).count()} for s in skills]

    return LearningAnalyticsResponse(
        total_active_courses=total_courses,
        enrolled_employees_count=enrolled_count,
        course_completion_rate=completion_rate,
        certificates_issued_count=certs_count,
        active_training_sessions=active_sessions,
        training_budget_spent=spent_budget,
        top_skills=top_skills
    )
