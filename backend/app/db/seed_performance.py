"""
seed_performance.py — Seeder for Standard Competencies & Performance Cycle Templates
Sprint 4 — Entity 1
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.models.all_models import Competency, PerformanceCycle, User

STANDARD_COMPETENCIES = [
  {"name": "Domain Expertise & Code Quality", "category": "technical", "description": "Demonstrates deep understanding of software engineering patterns and clean code standards."},
  {"name": "System Architecture & Design", "category": "technical", "description": "Architects scalable, reliable, and maintainable systems."},
  {"name": "Collaboration & Teamwork", "category": "behavioral", "description": "Fosters open communication, mutual respect, and proactive team support."},
  {"name": "Ownership & Accountability", "category": "behavioral", "description": "Takes full responsibility for outcomes and delivers on commitments."},
  {"name": "Leadership & Mentorship", "category": "leadership", "description": "Guides and empowers junior team members while driving technical vision."},
  {"name": "Strategic Thinking", "category": "leadership", "description": "Aligns engineering decisions with enterprise business goals."},
  {"name": "Clear & Effective Communication", "category": "communication", "description": "Articulates complex ideas clearly across technical and non-technical stakeholders."},
  {"name": "Innovation & Problem Solving", "category": "innovation", "description": "Pioneers creative solutions to challenging platform requirements."}
]


def seed_performance_defaults_for_org(db: Session, org_id: UUID, admin_user_id: int):
    # 1. Seed Competencies if missing
    existing_comp_count = db.query(Competency).filter(Competency.organization_id == org_id).count()
    if existing_comp_count == 0:
        for c in STANDARD_COMPETENCIES:
            comp = Competency(
                organization_id=org_id,
                name=c["name"],
                category=c["category"],
                description=c["description"],
                is_active=True
            )
            db.add(comp)

    # 2. Seed active Annual Review Cycle if missing
    existing_cycle = db.query(PerformanceCycle).filter(PerformanceCycle.organization_id == org_id).first()
    if not existing_cycle:
        now = datetime.now(timezone.utc)
        cycle = PerformanceCycle(
            organization_id=org_id,
            created_by_user_id=admin_user_id,
            name="FY2025 Annual Performance Review",
            cycle_type="annual",
            start_date=now - timedelta(days=90),
            end_date=now + timedelta(days=275),
            review_deadline=now + timedelta(days=30),
            status="active",
            description="Organization-wide annual evaluation and goal assessment cycle."
        )
        db.add(cycle)

    db.commit()
