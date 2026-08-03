"""
seed_learning.py — Seeder for Standard Course Categories, Skills & Compliance Courses
Sprint 4 — Entity 2
"""
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.models.all_models import CourseCategory, SkillMaster, Course, CourseModule, TrainingBudget

STANDARD_CATEGORIES = [
    {"name": "Technical & Engineering", "description": "Software architecture, coding standards, and DevOps best practices."},
    {"name": "Compliance & Security", "description": "Mandatory workplace safety, data privacy, and ISO compliance."},
    {"name": "Leadership & Management", "description": "People management, strategic planning, and executive leadership."},
    {"name": "Soft Skills & Communication", "description": "Effective communication, negotiation, and time management."}
]

STANDARD_SKILLS = [
    {"name": "Python & FastApi Microservices", "category": "technical", "description": "Backend microservice development with Python and FastAPI."},
    {"name": "React & Modern UI Architecture", "category": "technical", "description": "Frontend component design and state management."},
    {"name": "PostgreSQL & Database Optimization", "category": "technical", "description": "Database query tuning and schema indexing."},
    {"name": "Information Security & ISO 27001", "category": "compliance", "description": "Enterprise data protection and threat prevention."},
    {"name": "Executive Leadership & Team Management", "category": "leadership", "description": "Strategic leadership and organizational growth."}
]


def seed_learning_defaults_for_org(db: Session, org_id: UUID):
    # 1. Seed Categories if empty
    cat_count = db.query(CourseCategory).filter(CourseCategory.organization_id == org_id).count()
    if cat_count == 0:
        for c in STANDARD_CATEGORIES:
            cat = CourseCategory(organization_id=org_id, name=c["name"], description=c["description"])
            db.add(cat)
        db.commit()

    # 2. Seed Skills if empty
    skill_count = db.query(SkillMaster).filter(SkillMaster.organization_id == org_id).count()
    if skill_count == 0:
        for s in STANDARD_SKILLS:
            skill = SkillMaster(organization_id=org_id, name=s["name"], category=s["category"], description=s["description"], is_active=True)
            db.add(skill)
        db.commit()

    # 3. Seed Default Mandatory Compliance Course if empty
    course_count = db.query(Course).filter(Course.organization_id == org_id).count()
    if course_count == 0:
        cat = db.query(CourseCategory).filter(CourseCategory.organization_id == org_id).first()
        course = Course(
            organization_id=org_id,
            category_id=cat.id if cat else None,
            title="ISO 27001 Data Security & Compliance 2025",
            description="Mandatory annual information security training for all enterprise employees.",
            instructor_name="VisionCore Security Team",
            course_type="online",
            duration_hours=2.0,
            pass_percentage=80.0,
            is_mandatory=True,
            is_active=True
        )
        db.add(course)
        db.commit()

        # Add modules
        m1 = CourseModule(course_id=course.id, title="Module 1: Password Hygiene & MFA", sequence_order=1, duration_minutes=30, content_type="document")
        m2 = CourseModule(course_id=course.id, title="Module 2: Phishing & Threat Mitigation", sequence_order=2, duration_minutes=45, content_type="video")
        m3 = CourseModule(course_id=course.id, title="Module 3: GDPR & Data Classification", sequence_order=3, duration_minutes=45, content_type="quiz")
        db.add_all([m1, m2, m3])
        db.commit()

    # 4. Seed Training Budget if empty
    budget_count = db.query(TrainingBudget).filter(TrainingBudget.organization_id == org_id).count()
    if budget_count == 0:
        budget = TrainingBudget(
            organization_id=org_id,
            department_id=None,
            fiscal_year=2025,
            allocated_amount=500000.0,
            spent_amount=45000.0,
            remaining_amount=455000.0
        )
        db.add(budget)
        db.commit()
