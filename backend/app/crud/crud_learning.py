"""
crud_learning.py — CRUD Operations & Engines for Learning & Development (L&D)
Sprint 4 — Entity 2
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models.all_models import (
    CourseCategory, Course, CourseModule, CourseEnrollment, ModuleProgress,
    TrainingSession, SessionAttendance, AssessmentQuiz, AssessmentQuestion,
    AssessmentAttempt, SkillMaster, EmployeeSkill, Certificate, TrainingBudget, User
)


class CRUDCourseEngine:
    def create_category(self, db: Session, org_id: UUID, name: str, description: Optional[str] = None) -> CourseCategory:
        cat = CourseCategory(organization_id=org_id, name=name, description=description)
        db.add(cat)
        db.commit()
        db.refresh(cat)
        return cat

    def get_categories(self, db: Session, org_id: UUID) -> List[CourseCategory]:
        return db.query(CourseCategory).filter(CourseCategory.organization_id == org_id).all()

    def create_course(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> Course:
        course = Course(
            organization_id=org_id,
            category_id=obj_in.get("category_id"),
            title=obj_in["title"],
            description=obj_in.get("description"),
            instructor_name=obj_in.get("instructor_name"),
            course_type=obj_in.get("course_type", "online"),
            duration_hours=obj_in.get("duration_hours", 1.0),
            pass_percentage=obj_in.get("pass_percentage", 70.0),
            is_mandatory=obj_in.get("is_mandatory", False),
            is_active=obj_in.get("is_active", True)
        )
        db.add(course)
        db.commit()
        db.refresh(course)
        return course

    def add_module(self, db: Session, course_id: int, obj_in: Dict[str, Any]) -> CourseModule:
        mod = CourseModule(
            course_id=course_id,
            title=obj_in["title"],
            description=obj_in.get("description"),
            sequence_order=obj_in.get("sequence_order", 1),
            duration_minutes=obj_in.get("duration_minutes", 30),
            content_type=obj_in.get("content_type", "document"),
            content_url=obj_in.get("content_url")
        )
        db.add(mod)
        db.commit()
        db.refresh(mod)
        return mod

    def get_courses(self, db: Session, org_id: UUID) -> List[Course]:
        return db.query(Course).filter(Course.organization_id == org_id, Course.is_active.is_(True)).all()

    def get_course_by_id(self, db: Session, course_id: int) -> Optional[Course]:
        return db.query(Course).filter(Course.id == course_id).first()

    def enroll_user(self, db: Session, org_id: UUID, course_id: int, user_id: int, assigned_by_id: Optional[int] = None) -> CourseEnrollment:
        existing = db.query(CourseEnrollment).filter(
            CourseEnrollment.organization_id == org_id,
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.user_id == user_id
        ).first()

        if existing:
            return existing

        enrollment = CourseEnrollment(
            organization_id=org_id,
            course_id=course_id,
            user_id=user_id,
            assigned_by_user_id=assigned_by_id,
            status="enrolled",
            progress_pct=0.0
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)

        # Initialize module progress records
        modules = db.query(CourseModule).filter(CourseModule.course_id == course_id).all()
        for m in modules:
            mp = ModuleProgress(
                enrollment_id=enrollment.id,
                module_id=m.id,
                user_id=user_id,
                status="not_started"
            )
            db.add(mp)
        db.commit()

        return enrollment

    def update_module_progress(self, db: Session, enrollment: CourseEnrollment, module_id: int, time_spent: int, completed: bool) -> CourseEnrollment:
        mp = db.query(ModuleProgress).filter(
            ModuleProgress.enrollment_id == enrollment.id,
            ModuleProgress.module_id == module_id
        ).first()

        if mp:
            mp.time_spent_seconds += time_spent
            if completed:
                mp.status = "completed"
                mp.completed_at = datetime.now(timezone.utc)
            else:
                mp.status = "in_progress"
            db.commit()

        # Recalculate enrollment completion percentage
        total_modules = db.query(CourseModule).filter(CourseModule.course_id == enrollment.course_id).count()
        completed_modules = db.query(ModuleProgress).filter(
            ModuleProgress.enrollment_id == enrollment.id,
            ModuleProgress.status == "completed"
        ).count()

        if total_modules > 0:
            enrollment.progress_pct = round((completed_modules / total_modules) * 100, 1)
            if enrollment.progress_pct >= 100.0:
                enrollment.status = "completed"
                enrollment.completed_at = datetime.now(timezone.utc)
                # Auto-issue certificate
                crud_certificate_engine.issue_certificate(db, enrollment)
                # Auto upgrade employee skill if course links to skill
                crud_skill_engine.auto_verify_skill_on_completion(db, enrollment)
            elif enrollment.progress_pct > 0.0:
                enrollment.status = "in_progress"

        db.commit()
        db.refresh(enrollment)
        return enrollment


class CRUDAssessmentEngine:
    def create_quiz(self, db: Session, course_id: int, obj_in: Dict[str, Any]) -> AssessmentQuiz:
        quiz = AssessmentQuiz(
            course_id=course_id,
            title=obj_in["title"],
            pass_score=obj_in.get("pass_score", 70.0),
            time_limit_minutes=obj_in.get("time_limit_minutes", 30),
            total_questions=len(obj_in.get("questions") or [])
        )
        db.add(quiz)
        db.commit()
        db.refresh(quiz)

        if obj_in.get("questions"):
            for q in obj_in["questions"]:
                question = AssessmentQuestion(
                    quiz_id=quiz.id,
                    question_text=q["question_text"],
                    question_type=q.get("question_type", "single_choice"),
                    options=q.get("options"),
                    correct_answer=str(q["correct_answer"]),
                    points=q.get("points", 1.0)
                )
                db.add(question)
            db.commit()

        return quiz

    def submit_quiz_attempt(self, db: Session, quiz: AssessmentQuiz, user_id: int, enrollment_id: Optional[int], submitted_answers: Dict[str, str]) -> AssessmentAttempt:
        questions = db.query(AssessmentQuestion).filter(AssessmentQuestion.quiz_id == quiz.id).all()
        total_points = sum(float(q.points) for q in questions)
        earned_points = 0.0

        for q in questions:
            user_ans = str(submitted_answers.get(str(q.id)) or "").strip().lower()
            correct_ans = str(q.correct_answer).strip().lower()
            if user_ans and user_ans == correct_ans:
                earned_points += float(q.points)

        pct_score = round((earned_points / max(1.0, total_points)) * 100, 1)
        passed = pct_score >= float(quiz.pass_score)

        attempt = AssessmentAttempt(
            quiz_id=quiz.id,
            user_id=user_id,
            enrollment_id=enrollment_id,
            score=pct_score,
            max_score=100.0,
            passed=passed,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            response_data=submitted_answers
        )
        db.add(attempt)

        if enrollment_id:
            enrollment = db.query(CourseEnrollment).filter(CourseEnrollment.id == enrollment_id).first()
            if enrollment:
                enrollment.score = pct_score
                if passed:
                    enrollment.status = "completed"
                    enrollment.progress_pct = 100.0
                    enrollment.completed_at = datetime.now(timezone.utc)
                    crud_certificate_engine.issue_certificate(db, enrollment)

        db.commit()
        db.refresh(attempt)
        return attempt


class CRUDSkillEngine:
    def create_skill(self, db: Session, org_id: UUID, name: str, category: str = "technical", description: Optional[str] = None) -> SkillMaster:
        skill = SkillMaster(
            organization_id=org_id,
            name=name,
            category=category,
            description=description,
            is_active=True
        )
        db.add(skill)
        db.commit()
        db.refresh(skill)
        return skill

    def get_skills(self, db: Session, org_id: UUID) -> List[SkillMaster]:
        return db.query(SkillMaster).filter(SkillMaster.organization_id == org_id, SkillMaster.is_active.is_(True)).all()

    def add_or_update_employee_skill(self, db: Session, org_id: UUID, user_id: int, skill_id: int, proficiency_level: str, source: str = "self_reported") -> EmployeeSkill:
        es = db.query(EmployeeSkill).filter(
            EmployeeSkill.organization_id == org_id,
            EmployeeSkill.user_id == user_id,
            EmployeeSkill.skill_id == skill_id
        ).first()

        if not es:
            es = EmployeeSkill(
                organization_id=org_id,
                user_id=user_id,
                skill_id=skill_id,
                proficiency_level=proficiency_level,
                source=source
            )
            db.add(es)
        else:
            es.proficiency_level = proficiency_level
            es.source = source

        db.commit()
        db.refresh(es)
        return es

    def auto_verify_skill_on_completion(self, db: Session, enrollment: CourseEnrollment):
        # Assign default intermediate skill matching course category/title
        first_skill = db.query(SkillMaster).filter(SkillMaster.organization_id == enrollment.organization_id).first()
        if first_skill:
            self.add_or_update_employee_skill(
                db,
                enrollment.organization_id,
                enrollment.user_id,
                first_skill.id,
                proficiency_level="intermediate",
                source="course_completion"
            )


class CRUDCertificateEngine:
    def issue_certificate(self, db: Session, enrollment: CourseEnrollment) -> Certificate:
        existing = db.query(Certificate).filter(Certificate.enrollment_id == enrollment.id).first()
        if existing:
            return existing

        cert_no = f"VC-CERT-{uuid.uuid4().hex[:8].upper()}"
        cert = Certificate(
            organization_id=enrollment.organization_id,
            enrollment_id=enrollment.id,
            user_id=enrollment.user_id,
            course_id=enrollment.course_id,
            certificate_number=cert_no,
            issue_date=datetime.now(timezone.utc),
            certificate_url=f"/certificates/{cert_no}.pdf"
        )
        db.add(cert)
        db.commit()
        db.refresh(cert)
        return cert


class CRUDTrainingBudget:
    def create_or_update_budget(self, db: Session, org_id: UUID, department_id: Optional[int], fiscal_year: int, allocated: float) -> TrainingBudget:
        budget = db.query(TrainingBudget).filter(
            TrainingBudget.organization_id == org_id,
            TrainingBudget.department_id == department_id,
            TrainingBudget.fiscal_year == fiscal_year
        ).first()

        if not budget:
            budget = TrainingBudget(
                organization_id=org_id,
                department_id=department_id,
                fiscal_year=fiscal_year,
                allocated_amount=allocated,
                spent_amount=0.0,
                remaining_amount=allocated
            )
            db.add(budget)
        else:
            budget.allocated_amount = allocated
            budget.remaining_amount = allocated - budget.spent_amount

        db.commit()
        db.refresh(budget)
        return budget


crud_course_engine = CRUDCourseEngine()
crud_assessment_engine = CRUDAssessmentEngine()
crud_skill_engine = CRUDSkillEngine()
crud_certificate_engine = CRUDCertificateEngine()
crud_training_budget = CRUDTrainingBudget()
