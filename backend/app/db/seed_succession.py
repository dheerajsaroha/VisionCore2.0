"""
seed_succession.py — Seeder for Standard Career Paths, Key Positions & 9-Box Matrix Defaults
Sprint 4 — Entity 3
"""
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.models.all_models import KeyPosition, SuccessionPlan, CareerPath, CareerLevel, User

def seed_succession_defaults_for_org(db: Session, org_id: UUID, admin_user_id: int):
    # 1. Seed Key Positions if empty
    kp_count = db.query(KeyPosition).filter(KeyPosition.organization_id == org_id).count()
    if kp_count == 0:
        kp1 = KeyPosition(
            organization_id=org_id,
            title="Chief Technology Officer (CTO)",
            criticality_level="critical",
            current_incumbent_user_id=admin_user_id,
            vacancy_risk_level="low",
            impact_rating=5.0
        )
        kp2 = KeyPosition(
            organization_id=org_id,
            title="Principal AI Systems Architect",
            criticality_level="high",
            current_incumbent_user_id=admin_user_id,
            vacancy_risk_level="medium",
            impact_rating=4.5
        )
        db.add_all([kp1, kp2])
        db.commit()

        # Create succession plans for key positions
        sp1 = SuccessionPlan(organization_id=org_id, key_position_id=kp1.id, target_fill_timeline_months=3, status="active")
        sp2 = SuccessionPlan(organization_id=org_id, key_position_id=kp2.id, target_fill_timeline_months=6, status="active")
        db.add_all([sp1, sp2])
        db.commit()

    # 2. Seed Career Paths if empty
    cp_count = db.query(CareerPath).filter(CareerPath.organization_id == org_id).count()
    if cp_count == 0:
        path = CareerPath(
            organization_id=org_id,
            title="Software Engineering Track",
            description="Technical leadership and individual contributor career progression ladder.",
            total_levels=5
        )
        db.add(path)
        db.commit()

        l1 = CareerLevel(career_path_id=path.id, level_number=1, level_title="Junior Software Engineer", min_experience_years=0.0, target_salary_min=60000, target_salary_max=85000)
        l2 = CareerLevel(career_path_id=path.id, level_number=2, level_title="Software Engineer", min_experience_years=2.0, target_salary_min=85000, target_salary_max=115000)
        l3 = CareerLevel(career_path_id=path.id, level_number=3, level_title="Senior Software Engineer", min_experience_years=4.0, target_salary_min=115000, target_salary_max=155000)
        l4 = CareerLevel(career_path_id=path.id, level_number=4, level_title="Staff Engineer", min_experience_years=7.0, target_salary_min=155000, target_salary_max=200000)
        l5 = CareerLevel(career_path_id=path.id, level_number=5, level_title="Principal Engineer", min_experience_years=10.0, target_salary_min=200000, target_salary_max=260000)
        db.add_all([l1, l2, l3, l4, l5])
        db.commit()
