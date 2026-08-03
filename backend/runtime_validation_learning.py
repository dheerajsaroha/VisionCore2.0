"""
runtime_validation_learning.py — End-to-End Validation Script for Sprint 4 Entity 2
"""
import sys
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import SQLALCHEMY_DATABASE_URL
from app.db.models.all_models import (
    Organization, User, CourseCategory, Course, CourseModule, CourseEnrollment,
    ModuleProgress, TrainingSession, SessionAttendance, AssessmentQuiz,
    AssessmentQuestion, AssessmentAttempt, SkillMaster, EmployeeSkill,
    Certificate, TrainingBudget
)
from app.crud.crud_learning import (
    crud_course_engine, crud_assessment_engine, crud_skill_engine,
    crud_certificate_engine, crud_training_budget
)
from app.db.seed_learning import seed_learning_defaults_for_org

def main():
    print("=" * 70)
    print("🚀 SPRINT 4 ENTITY 2 — LEARNING & DEVELOPMENT MODULE VALIDATION")
    print("=" * 70)

    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    try:
        # 1. Fetch Organization & Admin User
        org = db.query(Organization).first()
        admin = db.query(User).filter(User.org_id == org.id).first() if org else None

        if not org or not admin:
            print("❌ Database missing Organization or User.")
            sys.exit(1)

        print(f"✅ Organization: {org.name} ({org.id})")
        print(f"✅ Admin User: {admin.full_name} ({admin.email})")

        # 2. Test Seeding
        print("\n🔹 Step 1: Seeding L&D Default Categories, Skills, Courses & Budgets...")
        seed_learning_defaults_for_org(db, org.id)

        cats = crud_course_engine.get_categories(db, org.id)
        skills = crud_skill_engine.get_skills(db, org.id)
        courses = crud_course_engine.get_courses(db, org.id)
        print(f"   ✓ Categories Count: {len(cats)}")
        print(f"   ✓ Skills Count: {len(skills)}")
        print(f"   ✓ Courses Count: {len(courses)}")
        assert len(cats) >= 4, "Expected at least 4 course categories"
        assert len(skills) >= 5, "Expected at least 5 skills"
        assert len(courses) >= 1, "Expected at least 1 course"

        # 3. Test Course Creation & Module Addition
        print("\n🔹 Step 2: Testing Course & Module Architecture...")
        new_course = crud_course_engine.create_course(db, org.id, {
            "category_id": cats[0].id,
            "title": "VisionCore Microservices Architecture 2025",
            "description": "Advanced FastAPI and PostgreSQL engineering",
            "instructor_name": "Senior Systems Architect",
            "course_type": "online",
            "duration_hours": 3.5,
            "pass_percentage": 75.0,
            "is_mandatory": False
        })
        print(f"   ✓ Course Created: ID={new_course.id}, Title='{new_course.title}'")

        m1 = crud_course_engine.add_module(db, new_course.id, {
            "title": "Lesson 1: EAAC Authorization & RBAC Pipeline",
            "sequence_order": 1,
            "duration_minutes": 45,
            "content_type": "video",
            "content_url": "https://learning.visioncore.com/m1"
        })
        m2 = crud_course_engine.add_module(db, new_course.id, {
            "title": "Lesson 2: Performance & Indexing Optimization",
            "sequence_order": 2,
            "duration_minutes": 60,
            "content_type": "document"
        })
        print(f"   ✓ Modules Added: 2 modules created (ID={m1.id}, ID={m2.id})")

        # 4. Test Enrollment & Progress Tracking
        print("\n🔹 Step 3: Testing Enrollment & Module Progress Engine...")
        enrollment = crud_course_engine.enroll_user(db, org.id, new_course.id, admin.id)
        print(f"   ✓ User Enrolled: Enrollment ID={enrollment.id}, Status='{enrollment.status}'")
        assert enrollment.status == "enrolled", f"Expected enrolled, got {enrollment.status}"

        # Complete Module 1
        crud_course_engine.update_module_progress(db, enrollment, m1.id, time_spent=2700, completed=True)
        print(f"   ✓ Progress Updated (Mod 1 Completed): Progress Pct={enrollment.progress_pct}%")
        assert enrollment.progress_pct == 50.0, f"Expected 50.0%, got {enrollment.progress_pct}"

        # Complete Module 2
        crud_course_engine.update_module_progress(db, enrollment, m2.id, time_spent=3600, completed=True)
        print(f"   ✓ Progress Updated (Mod 2 Completed): Status='{enrollment.status}', Pct={enrollment.progress_pct}%")
        assert enrollment.progress_pct == 100.0, f"Expected 100.0%, got {enrollment.progress_pct}"
        assert enrollment.status == "completed", f"Expected completed, got {enrollment.status}"

        # 5. Test Certificate Auto-Issuance
        print("\n🔹 Step 4: Testing Certificate Auto-Issuance Engine...")
        cert = db.query(Certificate).filter(Certificate.enrollment_id == enrollment.id).first()
        assert cert is not None, "Certificate should be automatically generated on course completion"
        print(f"   ✓ Certificate Auto-Issued: Serial='{cert.certificate_number}', URL='{cert.certificate_url}'")

        # 6. Test Quiz Engine & Automated Grading
        print("\n🔹 Step 5: Testing Assessment Quiz Engine & Automated Grading...")
        quiz = crud_assessment_engine.create_quiz(db, new_course.id, {
            "title": "Microservices Final Assessment",
            "pass_score": 75.0,
            "time_limit_minutes": 20,
            "questions": [
                {
                    "question_text": "What does EAAC stand for?",
                    "question_type": "single_choice",
                    "options": {"a": "Enterprise Architecture", "b": "Enterprise Authorization & Access Control"},
                    "correct_answer": "b",
                    "points": 50.0
                },
                {
                    "question_text": "Is PostgreSQL JSONB indexed?",
                    "question_type": "true_false",
                    "options": {"true": "True", "false": "False"},
                    "correct_answer": "true",
                    "points": 50.0
                }
            ]
        })
        print(f"   ✓ Quiz Created: ID={quiz.id}, Title='{quiz.title}'")

        # Submit attempt
        attempt = crud_assessment_engine.submit_quiz_attempt(db, quiz, admin.id, enrollment.id, {
            str(quiz.questions[0].id): "b",
            str(quiz.questions[1].id): "true"
        })
        print(f"   ✓ Quiz Submitted & Auto-Graded: Score={attempt.score}%, Passed={attempt.passed}")
        assert attempt.score == 100.0, f"Expected 100.0%, got {attempt.score}"
        assert attempt.passed is True, "Expected attempt to pass"

        # 7. Test Skill Matrix Verification
        print("\n🔹 Step 6: Testing Employee Skill Matrix Engine...")
        emp_skill = crud_skill_engine.add_or_update_employee_skill(db, org.id, admin.id, skills[0].id, "advanced", "assessment")
        print(f"   ✓ Skill Verified: User={admin.id}, Skill='{skills[0].name}', Level='{emp_skill.proficiency_level}'")

        # 8. Test Training Budget Tracking
        print("\n🔹 Step 7: Testing Departmental Training Budget Engine...")
        budget = crud_training_budget.create_or_update_budget(db, org.id, None, 2025, 250000.0)
        print(f"   ✓ Budget Updated: Allocated=${budget.allocated_amount}, Remaining=${budget.remaining_amount}")

        print("\n" + "=" * 70)
        print("🎉 ALL SPRINT 4 ENTITY 2 VALIDATION CHECKS PASSED WITH 100% SUCCESS!")
        print("=" * 70)

    finally:
        db.close()

if __name__ == "__main__":
    main()
