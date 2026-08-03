"""
runtime_validation_performance.py — End-to-End Validation Script for Sprint 4 Entity 1
Validates all Performance Management system endpoints, engines, and integrations.
"""
import sys
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import SQLALCHEMY_DATABASE_URL
from app.db.models.all_models import (
    Organization, User, Role, PerformanceCycle, Competency, KPI,
    KPIAssignment, Goal, GoalProgress, PerformanceReview, Feedback,
    PerformanceRating, PerformanceImprovementPlan, PromotionRecommendation,
    CalibrationSession
)
from app.crud.crud_performance import (
    crud_perf_cycle, crud_competency, crud_kpi_engine, crud_goal_engine,
    crud_review_engine, crud_feedback, crud_rating_engine, crud_pip, crud_promotion
)
from app.db.seed_performance import seed_performance_defaults_for_org
from app.services.performance_analytics import performance_analytics
from app.services.rating_normalization import rating_normalization
from app.services.kpi_engine import kpi_engine
from app.services.goal_scoring_engine import goal_scoring_engine


def validate_step(test_name, condition, detail=""):
    if condition:
        print(f"   [PASS] {test_name}")
        return True
    else:
        print(f"   [FAIL] {test_name} — {detail}")
        return False


def main():
    passed = 0
    failed = 0
    total_tests = 0

    def record(condition, name):
        nonlocal passed, failed, total_tests
        total_tests += 1
        if validate_step(name, condition):
            passed += 1
        else:
            failed += 1

    print("=" * 70)
    print("SPRINT 4 ENTITY 1 — PERFORMANCE MANAGEMENT MODULE VALIDATION")
    print("=" * 70)

    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    try:
        # 1. Setup
        org = db.query(Organization).first()
        admin = db.query(User).filter(User.org_id == org.id).first() if org else None
        record(org is not None, "Organization found in database")
        record(admin is not None, "Admin user found in database")

        if not org or not admin:
            print("Cannot continue without test data.")
            sys.exit(1)

        print(f"Org: {org.name} ({org.id})")
        print(f"Admin: {admin.full_name} ({admin.email})")

        # 2. Seeder
        print("\n[Seeder] Default Competencies & Cycles")
        seed_performance_defaults_for_org(db, org.id, admin.id)
        comps = crud_competency.get_all_for_org(db, org.id)
        cycles = crud_perf_cycle.get_all_for_org(db, org.id)
        record(len(comps) >= 8, f"Seeded {len(comps)} competencies (expected >= 8)")
        record(len(cycles) >= 1, f"Seeded {len(cycles)} performance cycles (expected >= 1)")

        active_cycle = cycles[0] if cycles else None
        record(active_cycle is not None, "Active performance cycle exists")

        if not active_cycle:
            print("Cannot continue without a performance cycle.")
            sys.exit(1)

        # 3. Cycle Management
        print("\n[Cycle Management] CRUD & Status Transitions")
        new_cycle = crud_perf_cycle.create(db, org.id, admin.id, {
            "name": "FY2025 Q4 Performance Review",
            "cycle_type": "quarterly",
            "start_date": datetime.now(timezone.utc) - timedelta(days=30),
            "end_date": datetime.now(timezone.utc) + timedelta(days=60),
            "description": "Q4 team evaluation cycle"
        })
        record(new_cycle.id is not None, "Create performance cycle")
        record(new_cycle.cycle_type == "quarterly", f"Cycle type = '{new_cycle.cycle_type}'")

        updated_cycle = crud_perf_cycle.update(db, new_cycle, {"status": "active"})
        record(updated_cycle.status == "active", "Update cycle status to 'active'")

        fetched_cycle = crud_perf_cycle.get_by_id(db, new_cycle.id)
        record(fetched_cycle is not None, "Fetch cycle by ID")
        record(fetched_cycle.id == new_cycle.id, "Fetched cycle matches created")

        all_cycles = crud_perf_cycle.get_all_for_org(db, org.id)
        record(len(all_cycles) >= 2, f"List cycles for org ({len(all_cycles)} found)")

        # 4. Competency Framework
        print("\n[Competencies] Framework Management")
        custom_comp = crud_competency.create(db, org.id, {
            "name": "Agile Project Management",
            "category": "leadership",
            "description": "Ability to scrum master and agile delivery"
        })
        record(custom_comp.id is not None, "Create custom competency")
        record(custom_comp.category == "leadership", f"Category = '{custom_comp.category}'")

        all_comps = crud_competency.get_all_for_org(db, org.id)
        record(len(all_comps) >= 9, f"List competencies ({len(all_comps)} found)")

        # 5. KPI Management
        print("\n[KPI Engine] Templates & Assignments")
        dept_kpi = crud_kpi_engine.create_kpi(db, org.id, {
            "name": "Department Revenue Target",
            "description": "Revenue achievement vs quarterly target",
            "unit": "%",
            "kpi_type": "department"
        })
        record(dept_kpi.id is not None, "Create department-level KPI")

        kpi_assignment = crud_kpi_engine.assign_kpi(db, org.id, admin.id, {
            "kpi_id": dept_kpi.id,
            "user_id": admin.id,
            "cycle_id": active_cycle.id,
            "target_value": 95.0,
            "weight": 1.5
        })
        record(kpi_assignment.id is not None, "Assign KPI to user")
        record(kpi_assignment.weight == 1.5, f"Weight = {kpi_assignment.weight}x")

        updated_assignment = crud_kpi_engine.update_kpi_progress(db, kpi_assignment, 92.0)
        record(updated_assignment.actual_value == 92.0, "Update KPI actual value")
        record(updated_assignment.score is not None, "Auto-calculated score after update")
        record(updated_assignment.score >= 1.0 and updated_assignment.score <= 5.0,
               f"Score {updated_assignment.score} in valid range [1-5]")

        weighted_score = crud_kpi_engine.calculate_weighted_kpi_score(db, admin.id, active_cycle.id)
        record(weighted_score is not None, "Calculate weighted KPI score")
        record(weighted_score >= 1.0 and weighted_score <= 5.0,
               f"Weighted score {weighted_score} in valid range")

        # 6. Goal Management
        print("\n[Goal Engine] OKR & SMART Goals")
        goal_okr = crud_goal_engine.create(db, org.id, admin.id, {
            "cycle_id": active_cycle.id,
            "title": "Achieve 99.9% Platform Uptime",
            "description": "Enterprise reliability goal",
            "goal_framework": "okr",
            "target_value": 100.0,
            "current_value": 25.0,
            "unit": "%",
            "priority": "high"
        })
        record(goal_okr.id is not None, "Create OKR goal")
        record(goal_okr.completion_pct == 25.0, f"Initial completion = {goal_okr.completion_pct}%")

        goal_smart = crud_goal_engine.create(db, org.id, admin.id, {
            "cycle_id": active_cycle.id,
            "title": "Complete 5 microservice migrations",
            "goal_framework": "smart",
            "target_value": 5.0,
            "current_value": 2.0,
            "unit": "services"
        })
        record(goal_smart.id is not None, "Create SMART goal")
        record(goal_smart.completion_pct == 40.0, f"SMART completion = {goal_smart.completion_pct}%")

        # Progress logging
        prog = crud_goal_engine.log_progress(db, goal_okr, admin.id, 85.0, "Post-migration uptime achieved")
        record(prog.id is not None, "Log goal progress")
        record(goal_okr.completion_pct == 85.0, f"Updated completion = {goal_okr.completion_pct}%")

        # Cascading goal
        child_goal = crud_goal_engine.create(db, org.id, admin.id, {
            "cycle_id": active_cycle.id,
            "parent_goal_id": goal_okr.id,
            "title": "Reduce API error rate",
            "goal_framework": "smart",
            "target_value": 100.0,
            "current_value": 60.0,
            "unit": "%"
        })
        record(child_goal.parent_goal_id == goal_okr.id, "Create cascading goal with parent")

        all_goals = crud_goal_engine.get_user_goals(db, org.id, admin.id, active_cycle.id)
        record(len(all_goals) >= 3, f"List user goals ({len(all_goals)} found)")

        goal_score = crud_goal_engine.compute_user_goal_score(db, admin.id, active_cycle.id)
        record(goal_score is not None, "Compute user goal score")
        record(goal_score >= 1.0 and goal_score <= 5.0,
               f"Goal score {goal_score} in valid range [1-5]")

        # 7. Performance Reviews
        print("\n[Review Engine] 360 Multi-Stage Reviews")
        self_review = crud_review_engine.create_review(db, org.id, {
            "cycle_id": active_cycle.id,
            "reviewee_user_id": admin.id,
            "reviewer_user_id": admin.id,
            "review_type": "self"
        })
        record(self_review.id is not None, "Create self review")
        record(self_review.status == "pending", f"Status = '{self_review.status}'")

        submitted = crud_review_engine.submit_review(db, self_review, {
            "strengths": "Strong architecture and delivery",
            "areas_for_improvement": "Expand test coverage",
            "comments": "Self review for Sprint 4",
            "competency_ratings": [
                {"competency_id": comps[0].id, "rating": 4.5, "evidence": "Clean models"},
                {"competency_id": comps[1].id, "rating": 4.8, "evidence": "Scalable design"}
            ]
        })
        record(submitted.status == "submitted", "Submit review")
        record(submitted.overall_score is not None, "Overall score calculated")
        record(submitted.overall_score >= 1.0 and submitted.overall_score <= 5.0,
               f"Score {submitted.overall_score} in valid range [1-5]")

        # Manager review
        manager_review = crud_review_engine.create_review(db, org.id, {
            "cycle_id": active_cycle.id,
            "reviewee_user_id": admin.id,
            "review_type": "manager"
        })
        record(manager_review.id is not None, "Create manager review")

        # 360 review
        review_360 = crud_review_engine.create_review(db, org.id, {
            "cycle_id": active_cycle.id,
            "reviewee_user_id": admin.id,
            "review_type": "360"
        })
        record(review_360.id is not None, "Create 360 review")

        all_reviews = crud_review_engine.get_reviews(db, org.id, cycle_id=active_cycle.id, user_id=admin.id)
        record(len(all_reviews) >= 1, f"List reviews ({len(all_reviews)} found)")

        # 8. Feedback
        print("\n[Feedback] Peer, 360, Anonymous")
        peer_fb = crud_feedback.create(db, org.id, admin.id, {
            "receiver_user_id": admin.id,
            "feedback_type": "peer",
            "content": "Great teamwork and timely delivery",
            "rating": 4.5,
            "is_anonymous": False
        })
        record(peer_fb.id is not None, "Submit peer feedback")

        anon_fb = crud_feedback.create(db, org.id, admin.id, {
            "receiver_user_id": admin.id,
            "feedback_type": "anonymous",
            "content": "Keep up the good work",
            "rating": 4.0,
            "is_anonymous": True
        })
        record(anon_fb.id is not None, "Submit anonymous feedback")

        all_feedback = crud_feedback.get_feedback_for_user(db, org.id, admin.id)
        record(len(all_feedback) >= 1, f"List received feedback ({len(all_feedback)} found)")

        # 9. Final Performance Rating
        print("\n[Rating Engine] Aggregation & Normalization")
        rating = crud_rating_engine.get_or_calculate_final_rating(db, org.id, admin.id, active_cycle.id)
        record(rating.id is not None, "Calculate final performance rating")
        record(rating.final_rating is not None, f"Final rating = {rating.final_rating}")
        record(rating.final_rating >= 1.0 and rating.final_rating <= 5.0,
               f"Rating {rating.final_rating} in valid range")
        record(rating.rating_label is not None, f"Label = '{rating.rating_label}'")
        record(rating.kpi_score is not None, "KPI component scored")
        record(rating.goal_score is not None, "Goal component scored")

        # Rating normalization
        bell_curve = rating_normalization.compute_bell_curve(db, org.id, active_cycle.id)
        record(bell_curve is not None, "Compute bell curve distribution")

        top_performers = rating_normalization.get_top_performers(db, org.id, active_cycle.id, limit=5)
        record(top_performers is not None, "Get top performers")

        dept_comparison = rating_normalization.compute_department_averages(db, org.id)
        record(dept_comparison is not None, "Compute department comparison")

        # 10. Calibration
        print("\n[Calibration] HR Review Sessions")
        calibration = CalibrationSession(
            organization_id=org.id,
            cycle_id=active_cycle.id,
            facilitator_user_id=admin.id,
            status="open",
            notes="Q4 calibration session"
        )
        db.add(calibration)
        db.commit()
        db.refresh(calibration)
        record(calibration.id is not None, "Create calibration session")
        record(calibration.status == "open", f"Status = '{calibration.status}'")

        calibration.status = "completed"
        calibration.calibration_data = {str(admin.id): 4.5}
        db.commit()
        db.refresh(calibration)
        record(calibration.status == "completed", "Complete calibration session")

        # 11. PIP
        print("\n[PIP] Performance Improvement Plans")
        pip = crud_pip.create(db, org.id, admin.id, {
            "user_id": admin.id,
            "title": "Quality & Test Coverage PIP",
            "reason": "Improve unit test coverage",
            "objectives": "Achieve 95% coverage in 30 days",
            "milestones": [{"title": "Week 1: 70%", "due_date": datetime.now(timezone.utc).isoformat(), "status": "pending"}],
            "start_date": datetime.now(timezone.utc),
            "end_date": datetime.now(timezone.utc) + timedelta(days=30)
        })
        record(pip.id is not None, "Create PIP")
        record(pip.status == "active", f"Status = '{pip.status}'")

        updated_pip = crud_pip.update(db, pip, {"status": "completed", "outcome": "successful"})
        record(updated_pip.status == "completed", "Complete PIP")

        # 12. Promotion Recommendations
        print("\n[Promotion] Readiness & Decision Pipeline")
        promo = crud_promotion.create(db, org.id, admin.id, {
            "user_id": admin.id,
            "cycle_id": active_cycle.id,
            "proposed_role": "Principal Architect",
            "proposed_salary_increase_pct": 18.5,
            "readiness_score": 4.5,
            "justification": "Outstanding EAAC delivery"
        })
        record(promo.id is not None, "Create promotion recommendation")
        record(promo.status == "pending", f"Status = '{promo.status}'")

        approved_promo = crud_promotion.decide(db, promo, admin.id, "approved", "Approved by exec")
        record(approved_promo.status == "approved", "Approve promotion")
        record(approved_promo.decided_by_user_id == admin.id, "Decided by correct user")

        # 13. Analytics
        print("\n[Analytics] Performance Dashboards")
        dashboard = performance_analytics.get_dashboard(db, org.id, active_cycle.id)
        record(dashboard is not None, "Get dashboard analytics")
        record(dashboard.get("avg_performance_rating") is not None, "Avg rating in dashboard")

        dept_comp_result = performance_analytics.get_department_comparison(db, org.id, active_cycle.id)
        record(dept_comp_result is not None, "Get department comparison analytics")

        review_pipeline = performance_analytics.get_review_pipeline(db, org.id, active_cycle.id)
        record(review_pipeline is not None, "Get review pipeline")

        promo_pipeline = performance_analytics.get_promotion_pipeline(db, org.id)
        record(promo_pipeline is not None, "Get promotion pipeline")

        attrition = performance_analytics.get_attrition_risk_indicators(db, org.id, active_cycle.id)
        record(attrition is not None, "Get attrition risk indicators")

        # 14. HR Command Center Integration
        print("\n[HR Integration] Command Center Metrics")
        top_perf_count = db.query(PerformanceRating).filter(
            PerformanceRating.organization_id == org.id,
            PerformanceRating.final_rating >= 4.5
        ).count()
        record(top_perf_count >= 0, "Top performers count queryable")

        bottom_perf_count = db.query(PerformanceRating).filter(
            PerformanceRating.organization_id == org.id,
            PerformanceRating.final_rating < 2.0
        ).count()
        record(bottom_perf_count >= 0, "Bottom performers count queryable")

        # 15. EAAC Integration Verification
        print("\n[EAAC] Authorization Integration")
        from app.services.eaac_engine import EnterpriseAuthorizationEngine

        eaac_result = EnterpriseAuthorizationEngine.evaluate_access(
            db, admin.id, org.id, "performance.cycles.read"
        )
        record(eaac_result is not None, "EAAC evaluates for performance module")
        record(hasattr(eaac_result, "granted"), "EAAC decision has granted field")
        record(hasattr(eaac_result, "effective_permissions"), "EAAC has effective_permissions")
        record(hasattr(eaac_result, "effective_data_scopes"), "EAAC has data_scopes")

        # Final Summary
        print("\n" + "=" * 70)
        pct = round((passed / max(1, total_tests)) * 100, 1)
        print(f"RESULTS: {passed}/{total_tests} passed ({pct}%) | {failed} failed")
        if failed == 0:
            print("ALL SPRINT 4 ENTITY 1 VALIDATION CHECKS PASSED WITH 100% SUCCESS!")
        else:
            print(f"{failed} test(s) failed — review output above")
        print("=" * 70)

    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
