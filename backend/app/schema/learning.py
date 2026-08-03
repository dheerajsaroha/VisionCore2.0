"""
learning.py — Pydantic Schemas for Enterprise Learning & Development System
Sprint 4 — Entity 2
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# ── COURSE CATEGORY SCHEMAS ──
class CourseCategoryBase(BaseModel):
    name: str = Field(..., description="Category name e.g. Technical Skills")
    description: Optional[str] = None


class CourseCategoryCreate(CourseCategoryBase):
    pass


class CourseCategoryResponse(CourseCategoryBase):
    id: int
    organization_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── COURSE SCHEMAS ──
class CourseBase(BaseModel):
    category_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    instructor_name: Optional[str] = None
    course_type: str = "online"  # online | classroom | workshop | hybrid
    duration_hours: float = 1.0
    pass_percentage: float = 70.0
    is_mandatory: bool = False
    is_active: bool = True


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    category_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    instructor_name: Optional[str] = None
    course_type: Optional[str] = None
    duration_hours: Optional[float] = None
    pass_percentage: Optional[float] = None
    is_mandatory: Optional[bool] = None
    is_active: Optional[bool] = None


class CourseModuleBase(BaseModel):
    title: str
    description: Optional[str] = None
    sequence_order: int = 1
    duration_minutes: int = 30
    content_type: str = "document"  # video | document | quiz | interactive
    content_url: Optional[str] = None


class CourseModuleCreate(CourseModuleBase):
    course_id: int


class CourseModuleResponse(CourseModuleBase):
    id: int
    course_id: int

    model_config = ConfigDict(from_attributes=True)


class CourseResponse(CourseBase):
    id: int
    organization_id: UUID
    category_name: Optional[str] = None
    created_at: datetime
    modules: List[CourseModuleResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ── ENROLLMENT SCHEMAS ──
class CourseEnrollmentCreate(BaseModel):
    course_id: int
    user_id: Optional[int] = None  # Self if omitted


class CourseProgressUpdate(BaseModel):
    module_id: int
    time_spent_seconds: int = 0
    completed: bool = True


class CourseEnrollmentResponse(BaseModel):
    id: int
    organization_id: UUID
    course_id: int
    course_title: Optional[str] = None
    user_id: int
    user_name: Optional[str] = None
    status: str
    progress_pct: float
    score: Optional[float] = None
    enrolled_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── TRAINING SESSION SCHEMAS ──
class TrainingSessionCreate(BaseModel):
    course_id: Optional[int] = None
    trainer_user_id: Optional[int] = None
    title: str
    location_or_link: Optional[str] = None
    start_time: datetime
    end_time: datetime
    max_participants: int = 30


class TrainingSessionResponse(BaseModel):
    id: int
    organization_id: UUID
    course_id: Optional[int] = None
    course_title: Optional[str] = None
    trainer_user_id: Optional[int] = None
    trainer_name: Optional[str] = None
    title: str
    location_or_link: Optional[str] = None
    start_time: datetime
    end_time: datetime
    max_participants: int
    current_participants: int
    status: str

    model_config = ConfigDict(from_attributes=True)


class SessionAttendanceResponse(BaseModel):
    id: int
    session_id: int
    user_id: int
    user_name: Optional[str] = None
    status: str
    check_in_time: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── ASSESSMENT & QUIZ SCHEMAS ──
class AssessmentQuestionCreate(BaseModel):
    question_text: str
    question_type: str = "single_choice"
    options: Optional[Dict[str, Any]] = None
    correct_answer: str
    points: float = 1.0


class AssessmentQuestionResponse(AssessmentQuestionCreate):
    id: int
    quiz_id: int

    model_config = ConfigDict(from_attributes=True)


class AssessmentQuizCreate(BaseModel):
    course_id: int
    title: str
    pass_score: float = 70.0
    time_limit_minutes: int = 30
    questions: Optional[List[AssessmentQuestionCreate]] = None


class AssessmentQuizResponse(BaseModel):
    id: int
    course_id: int
    title: str
    pass_score: float
    time_limit_minutes: int
    total_questions: int
    questions: List[AssessmentQuestionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class QuizSubmit(BaseModel):
    answers: Dict[str, str] = Field(..., description="Map of question_id to submitted_answer string")


class AssessmentAttemptResponse(BaseModel):
    id: int
    quiz_id: int
    user_id: int
    score: float
    max_score: float
    passed: bool
    started_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── SKILLS SCHEMAS ──
class SkillMasterCreate(BaseModel):
    name: str
    category: str = "technical"
    description: Optional[str] = None


class SkillMasterResponse(SkillMasterCreate):
    id: int
    organization_id: UUID
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class EmployeeSkillCreate(BaseModel):
    user_id: Optional[int] = None
    skill_id: int
    proficiency_level: str = "intermediate"  # beginner | intermediate | advanced | expert
    source: str = "self_reported"


class EmployeeSkillResponse(BaseModel):
    id: int
    organization_id: UUID
    user_id: int
    user_name: Optional[str] = None
    skill_id: int
    skill_name: Optional[str] = None
    proficiency_level: str
    verified_by_user_id: Optional[int] = None
    verified_at: Optional[datetime] = None
    source: str

    model_config = ConfigDict(from_attributes=True)


# ── CERTIFICATE SCHEMAS ──
class CertificateResponse(BaseModel):
    id: int
    organization_id: UUID
    enrollment_id: int
    user_id: int
    user_name: Optional[str] = None
    course_id: int
    course_title: Optional[str] = None
    certificate_number: str
    issue_date: datetime
    expiry_date: Optional[datetime] = None
    certificate_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ── BUDGET SCHEMAS ──
class TrainingBudgetCreate(BaseModel):
    department_id: Optional[int] = None
    fiscal_year: int = 2025
    allocated_amount: float


class TrainingBudgetResponse(BaseModel):
    id: int
    organization_id: UUID
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    fiscal_year: int
    allocated_amount: float
    spent_amount: float
    remaining_amount: float

    model_config = ConfigDict(from_attributes=True)


# ── ANALYTICS ──
class LearningAnalyticsResponse(BaseModel):
    total_active_courses: int
    enrolled_employees_count: int
    course_completion_rate: float
    certificates_issued_count: int
    active_training_sessions: int
    training_budget_spent: float
    top_skills: List[Dict[str, Any]]
