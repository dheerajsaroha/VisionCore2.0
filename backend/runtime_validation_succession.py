"""
runtime_validation_succession.py — End-to-End Validation for Sprint 4 Entity 3
Succession Planning & Career Pathing Engine
"""
import sys
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import SQLALCHEMY_DATABASE_URL
from app.db.models.all_models import (
    Organization, User, KeyPosition, SuccessionPlan, SuccessorCandidate,
    NineBoxGrid, CareerPath, CareerLevel, IndividualDevelopmentPlan, IDPGoal,
    FlightRiskAssessment, MentorshipPair
)
from app.crud.crud_succession import (
    crud_succession_engine, crud_nine_box_engine, crud_career_engine,
    crud_idp_engine, crud_flight_risk_engine, crud_mentorship_engine
)
from app.db.seed_succession import seed_succession_defaults_for_org


def main():
    print("=" * 70)
    print("🚀 SPRINT 4 ENTITY 3 — SUCCESSION PLANNING & CAREER PATHING VALIDATION")
    print("=" * 70)

    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        org = db.query(Organization).first()
        admin = db.query(User).filter(User.org_id == org.id).first() if org else None
        if not org or not admin:
            print("❌ Missing Organization or User."); sys.exit(1)

        print(f"✅ Organization: {org.name}")
        print(f"✅ Admin User: {admin.full_name} ({admin.email})")

        # Step 1: Seeding
        print("\n🔹 Step 1: Seeding Default Key Positions & Career Paths...")
        seed_succession_defaults_for_org(db, org.id, admin.id)
        kps = crud_succession_engine.get_key_positions(db, org.id)
        paths = crud_career_engine.get_career_paths(db, org.id)
        print(f"   ✓ Key Positions Seeded: {len(kps)}")
        print(f"   ✓ Career Paths Seeded: {len(paths)}")
        assert len(kps) >= 2, "Expected ≥2 key positions"
        assert len(paths) >= 1, "Expected ≥1 career path"
        assert len(paths[0].levels) == 5, "Expected 5 career levels in Software Engineering track"

        # Step 2: Key Position Creation
        print("\n🔹 Step 2: Testing Key Position & Succession Plan Creation...")
        new_kp = crud_succession_engine.create_key_position(db, org.id, {
            "title": "VP of Engineering",
            "criticality_level": "critical",
            "current_incumbent_user_id": admin.id,
            "vacancy_risk_level": "medium",
            "impact_rating": 4.8
        })
        print(f"   ✓ Key Position Created: '{new_kp.title}' (ID={new_kp.id})")

        # Auto succession plan should be created
        plan = db.query(SuccessionPlan).filter(SuccessionPlan.key_position_id == new_kp.id).first()
        assert plan is not None, "Succession plan should be auto-created with key position"
        print(f"   ✓ Succession Plan Auto-Created: ID={plan.id}, Status='{plan.status}'")

        # Step 3: Succession Candidate Nomination
        print("\n🔹 Step 3: Testing Successor Candidate Nomination Engine...")
        cand = crud_succession_engine.nominate_successor(db, plan.id, {
            "candidate_user_id": admin.id,
            "readiness_rating": "ready_now",
            "emergency_backup": True,
            "nomination_notes": "Demonstrated full-stack technical leadership for 3+ years."
        })
        print(f"   ✓ Candidate Nominated: User={cand.candidate_user_id}, Readiness='{cand.readiness_rating}', Emergency={cand.emergency_backup}")
        assert cand.readiness_rating == "ready_now"
        assert cand.emergency_backup is True

        # Step 4: 9-Box Talent Matrix
        print("\n🔹 Step 4: Testing 9-Box Talent Matrix Engine...")
        org_users = db.query(User).filter(User.org_id == org.id, User.is_deleted == 0).limit(3).all()
        if len(org_users) < 3:
            org_users = org_users * 3  # pad if not enough users (different cycle_ids would be needed)
        test_cases = [
            (org_users[0].id, 3, 3, "Star (High Perf / High Pot)"),
            (org_users[1].id if len(org_users) > 1 else org_users[0].id, 2, 3, "High Potential"),
            (org_users[2].id if len(org_users) > 2 else org_users[0].id, 1, 1, "Underperformer / Risk"),
        ]
        for uid, perf, pot, expected_cat in test_cases:
            grid = crud_nine_box_engine.evaluate_employee(db, org.id, uid, perf, pot, evaluator_id=admin.id, cycle_id=None)
            print(f"   ✓ User={uid}, P{perf}/Pot{pot} → Category: '{grid.box_category}'")
            assert grid.box_category == expected_cat, f"Expected '{expected_cat}', got '{grid.box_category}'"

        # Step 5: Career Path & Ladder
        print("\n🔹 Step 5: Testing Career Path Architecture...")
        new_path = crud_career_engine.create_career_path(db, org.id, {
            "title": "Product Management Track",
            "description": "PM career ladder from Associate to VP",
            "levels": [
                {"level_number": 1, "level_title": "Associate PM", "min_experience_years": 0, "target_salary_min": 70000, "target_salary_max": 95000},
                {"level_number": 2, "level_title": "Product Manager", "min_experience_years": 2, "target_salary_min": 95000, "target_salary_max": 130000},
                {"level_number": 3, "level_title": "Senior PM", "min_experience_years": 5, "target_salary_min": 130000, "target_salary_max": 170000},
            ]
        })
        print(f"   ✓ Career Path Created: '{new_path.title}', Levels={len(new_path.levels)}")
        assert len(new_path.levels) == 3

        # Step 6: IDP Creation
        print("\n🔹 Step 6: Testing Individual Development Plan (IDP) Engine...")
        target_level = new_path.levels[2]  # Senior PM
        idp = crud_idp_engine.create_idp(db, org.id, admin.id, {
            "target_career_level_id": target_level.id,
            "target_position_title": "Senior Product Manager",
            "goals": [
                {"title": "Complete AWS Solutions Architect Certification", "goal_type": "training"},
                {"title": "Lead cross-functional product sprint", "goal_type": "project_assignment"},
            ]
        })
        print(f"   ✓ IDP Created: ID={idp.id}, Status='{idp.status}', Goals={len(idp.goals)}")
        assert len(idp.goals) == 2
        assert idp.status == "in_progress"

        # Update goal progress
        updated_goal = crud_idp_engine.update_idp_goal_progress(db, idp.goals[0].id, 75.0, "in_progress")
        print(f"   ✓ IDP Goal Progress Updated: '{updated_goal.title}' → {updated_goal.completion_pct}%")
        assert updated_goal.completion_pct == 75.0

        # Step 7: Flight Risk Assessment
        print("\n🔹 Step 7: Testing Flight Risk Assessment Engine...")
        risk = crud_flight_risk_engine.assess_flight_risk(
            db, org.id, admin.id, "high",
            risk_factors={"factors": ["limited_growth", "market_compensation"]},
            strategy="Schedule quarterly growth conversations; revise compensation band.",
            assessor_id=admin.id
        )
        print(f"   ✓ Flight Risk Assessed: User={risk.user_id}, Score='{risk.risk_score}'")
        assert risk.risk_score == "high"
        assert risk.retention_strategy is not None

        # Step 8: Mentorship Pairing
        print("\n🔹 Step 8: Testing Mentorship Network Engine...")
        # Get a second user if available, otherwise use same user
        second_user = db.query(User).filter(User.org_id == org.id, User.id != admin.id).first()
        mentor_id = admin.id
        mentee_id = second_user.id if second_user else admin.id

        pair = crud_mentorship_engine.create_pair(db, org.id, mentor_id, mentee_id, "Leadership, Architecture & Career Growth")
        print(f"   ✓ Mentorship Pair Created: Mentor={pair.mentor_user_id} → Mentee={pair.mentee_user_id}, Status='{pair.status}'")
        assert pair.status == "active"
        assert pair.focus_areas == "Leadership, Architecture & Career Growth"

        # Step 9: Analytics Aggregation
        print("\n🔹 Step 9: Verifying Analytics Aggregation...")
        all_kps = db.query(KeyPosition).filter(KeyPosition.organization_id == org.id).count()
        stars = db.query(NineBoxGrid).filter(
            NineBoxGrid.organization_id == org.id,
            NineBoxGrid.performance_rating == 3,
            NineBoxGrid.potential_rating == 3
        ).count()
        active_idps = db.query(IndividualDevelopmentPlan).filter(
            IndividualDevelopmentPlan.organization_id == org.id,
            IndividualDevelopmentPlan.status == "in_progress"
        ).count()
        high_risk = db.query(FlightRiskAssessment).filter(
            FlightRiskAssessment.organization_id == org.id,
            FlightRiskAssessment.risk_score.in_(["high", "critical"])
        ).count()
        mentorships = db.query(MentorshipPair).filter(
            MentorshipPair.organization_id == org.id,
            MentorshipPair.status == "active"
        ).count()

        print(f"   ✓ Critical Positions: {all_kps}")
        print(f"   ✓ 9-Box Stars: {stars}")
        print(f"   ✓ Active IDPs: {active_idps}")
        print(f"   ✓ High Flight Risk: {high_risk}")
        print(f"   ✓ Active Mentorships: {mentorships}")

        assert all_kps >= 2
        assert stars >= 1
        assert active_idps >= 1
        assert high_risk >= 1
        assert mentorships >= 1

        print("\n" + "=" * 70)
        print("🎉 ALL SPRINT 4 ENTITY 3 VALIDATION CHECKS PASSED WITH 100% SUCCESS!")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    main()
