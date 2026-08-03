from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.api import deps
from app.db.database import get_db
from app.db.models.all_models import (
    User, LeaveRequest, AttendanceLog, Payroll, JobPosting, PayrollAdvance, AttendanceCorrection,
    PerformanceReview, PerformanceCycle, Goal, PerformanceRating, PerformanceImprovementPlan, PromotionRecommendation,
    Course, CourseEnrollment, Certificate, TrainingSession, TrainingBudget,
    KeyPosition, SuccessionPlan, SuccessorCandidate, NineBoxGrid,
    IndividualDevelopmentPlan, FlightRiskAssessment, MentorshipPair,
    PolicyDocument, PolicyAcknowledgement, PolicyVersion, Department
)

router = APIRouter()


@router.get("/command-center")
def get_hr_command_center_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """Aggregated HR metrics for HR Command Center Dashboard."""
    org_id = current_user.org_id

    # 1. Total active employees
    total_employees = db.query(User).filter(
        User.org_id == org_id,
        User.is_deleted == 0
    ).count()

    # 2. Pending leave requests
    pending_leaves = db.query(LeaveRequest).filter(
        LeaveRequest.organization_id == org_id,
        LeaveRequest.status == "pending"
    ).count()

    # 3. Today's attendance rate
    today = datetime.now().date()
    today_logs = db.query(AttendanceLog).join(User).filter(
        User.org_id == org_id,
        AttendanceLog.is_deleted == 0
    ).all()
    today_present = len([l for l in today_logs if l.check_in and l.check_in.date() == today])
    att_rate = round((today_present / max(1, total_employees)) * 100, 1)

    # 4. Monthly payroll total (latest month)
    curr_month, curr_year = datetime.now().month, datetime.now().year
    payrolls = db.query(Payroll).filter(
        Payroll.org_id == org_id,
        Payroll.month == curr_month,
        Payroll.year == curr_year
    ).all()
    monthly_payroll_spend = sum(float(p.total_salary) for p in payrolls)

    # 5. Open job postings
    open_jobs = db.query(JobPosting).filter(
        JobPosting.organization_id == org_id,
        JobPosting.status == "open"
    ).count()

    # 6. Pending salary advances
    pending_advances = db.query(PayrollAdvance).filter(
        PayrollAdvance.organization_id == org_id,
        PayrollAdvance.status == "pending"
    ).count()

    # 7. Pending attendance corrections
    pending_corrections = db.query(AttendanceCorrection).filter(
        AttendanceCorrection.organization_id == org_id,
        AttendanceCorrection.status == "pending"
    ).count()

    # 8. Performance metrics
    pending_reviews = db.query(PerformanceReview).filter(
        PerformanceReview.organization_id == org_id,
        PerformanceReview.status == "pending"
    ).count()

    completed_reviews = db.query(PerformanceReview).filter(
        PerformanceReview.organization_id == org_id,
        PerformanceReview.status == "submitted"
    ).count()
    total_reviews = pending_reviews + completed_reviews
    review_completion_pct = round((completed_reviews / max(1, total_reviews)) * 100, 1)

    active_cycles = db.query(PerformanceCycle).filter(
        PerformanceCycle.organization_id == org_id,
        PerformanceCycle.status == "active"
    ).count()

    goals = db.query(Goal).filter(Goal.organization_id == org_id).all()
    goal_completion_pct = round(sum(float(g.completion_pct) for g in goals) / max(1, len(goals)), 1) if goals else 0.0

    ratings = db.query(PerformanceRating).filter(PerformanceRating.organization_id == org_id).all()
    avg_rating = round(sum(float(r.final_rating or 3.0) for r in ratings) / max(1, len(ratings)), 2) if ratings else 3.5

    open_pips = db.query(PerformanceImprovementPlan).filter(
        PerformanceImprovementPlan.organization_id == org_id,
        PerformanceImprovementPlan.status == "active"
    ).count()

    promotion_candidates = db.query(PromotionRecommendation).filter(
        PromotionRecommendation.organization_id == org_id,
        PromotionRecommendation.status == "pending"
    ).count()

    # 9. Learning & Development metrics
    total_courses = db.query(Course).filter(Course.organization_id == org_id, Course.is_active.is_(True)).count()
    enrolled_count = db.query(CourseEnrollment).filter(CourseEnrollment.organization_id == org_id).count()
    completed_enrollments = db.query(CourseEnrollment).filter(CourseEnrollment.organization_id == org_id, CourseEnrollment.status == "completed").count()
    course_completion_rate = round((completed_enrollments / max(1, enrolled_count)) * 100, 1)

    certs_issued = db.query(Certificate).filter(Certificate.organization_id == org_id).count()
    active_sessions = db.query(TrainingSession).filter(TrainingSession.organization_id == org_id, TrainingSession.status == "scheduled").count()

    budgets = db.query(TrainingBudget).filter(TrainingBudget.organization_id == org_id).all()
    budget_spent = sum(float(b.spent_amount) for b in budgets)

    # 10. Succession Planning & Career Pathing metrics
    critical_positions = db.query(KeyPosition).filter(KeyPosition.organization_id == org_id).count()

    plans_with_ready = db.query(SuccessionPlan).join(SuccessorCandidate).filter(
        SuccessionPlan.organization_id == org_id,
        SuccessorCandidate.readiness_rating == "ready_now"
    ).distinct().count()
    succession_readiness_pct = round((plans_with_ready / max(1, critical_positions)) * 100, 1)

    nine_box_stars = db.query(NineBoxGrid).filter(
        NineBoxGrid.organization_id == org_id,
        NineBoxGrid.performance_rating == 3,
        NineBoxGrid.potential_rating == 3
    ).count()

    active_idps = db.query(IndividualDevelopmentPlan).filter(
        IndividualDevelopmentPlan.organization_id == org_id,
        IndividualDevelopmentPlan.status == "in_progress"
    ).count()

    high_flight_risk = db.query(FlightRiskAssessment).filter(
        FlightRiskAssessment.organization_id == org_id,
        FlightRiskAssessment.risk_score.in_(["high", "critical"])
    ).count()

    active_mentorships = db.query(MentorshipPair).filter(
        MentorshipPair.organization_id == org_id,
        MentorshipPair.status == "active"
    ).count()

    # Performance-specific additional metrics
    top_performers_count = db.query(PerformanceRating).filter(
        PerformanceRating.organization_id == org_id,
        PerformanceRating.final_rating >= 4.5
    ).count()

    bottom_performers_count = db.query(PerformanceRating).filter(
        PerformanceRating.organization_id == org_id,
        PerformanceRating.final_rating < 2.0
    ).count()

    avg_goal_completion = goal_completion_pct

    total_review_target = total_employees
    review_completion_rate = review_completion_pct

    # Top performing department by average rating
    from app.services.rating_normalization import rating_normalization as rn
    dept_stats = rn.compute_department_averages(db, org_id)
    top_performing_dept = dept_stats[0]["department_name"] if dept_stats else "N/A"
    top_dept_rating = dept_stats[0]["avg_rating"] if dept_stats else 0.0

    # ── POLICY CENTER METRICS ──
    active_policies = db.query(PolicyDocument).filter(
        PolicyDocument.organization_id == org_id,
        PolicyDocument.status == "published"
    ).count()

    pending_acknowledgements = db.query(PolicyAcknowledgement).join(
        PolicyDocument, PolicyAcknowledgement.document_id == PolicyDocument.id
    ).filter(
        PolicyDocument.organization_id == org_id,
        PolicyAcknowledgement.is_acknowledged == False
    ).count()

    # Compliance across all employees
    total_acks = db.query(PolicyAcknowledgement).join(
        PolicyDocument, PolicyAcknowledgement.document_id == PolicyDocument.id
    ).filter(
        PolicyDocument.organization_id == org_id
    ).count()
    accepted_acks = db.query(PolicyAcknowledgement).join(
        PolicyDocument, PolicyAcknowledgement.document_id == PolicyDocument.id
    ).filter(
        PolicyDocument.organization_id == org_id,
        PolicyAcknowledgement.is_acknowledged == True
    ).count()
    compliance_percentage = round((accepted_acks / max(1, total_acks)) * 100, 1) if total_acks > 0 else 100.0

    now_utc = datetime.now(timezone.utc)
    expiring_policies = db.query(PolicyDocument).filter(
        PolicyDocument.organization_id == org_id,
        PolicyDocument.status == "published",
        PolicyDocument.expiry_date.isnot(None),
        PolicyDocument.expiry_date <= now_utc + timedelta(days=30),
        PolicyDocument.expiry_date > now_utc
    ).count()

    # Policy acknowledgements with no acknowledgement (is_acknowledged=False) and old created_at
    overdue_acknowledgements = db.query(PolicyAcknowledgement).join(
        PolicyDocument, PolicyAcknowledgement.document_id == PolicyDocument.id
    ).filter(
        PolicyDocument.organization_id == org_id,
        PolicyAcknowledgement.is_acknowledged == False,
        PolicyAcknowledgement.created_at < now_utc - timedelta(days=7)
    ).count()

    recently_published = db.query(PolicyDocument).filter(
        PolicyDocument.organization_id == org_id,
        PolicyDocument.status == "published",
        PolicyDocument.published_at.isnot(None),
        PolicyDocument.published_at >= now_utc - timedelta(days=7)
    ).count()

    total_versions = db.query(PolicyVersion).join(
        PolicyDocument, PolicyVersion.document_id == PolicyDocument.id
    ).filter(
        PolicyDocument.organization_id == org_id
    ).count()
    policy_versions = total_versions

    # Department-level compliance
    departments_list = db.query(Department).filter(
        Department.org_id == org_id, Department.is_deleted == 0
    ).all()
    dept_compliance = []
    for dept in departments_list:
        dept_users = db.query(User).filter(
            User.org_id == org_id, User.dept_id == dept.id, User.is_deleted == 0
        ).count()
        if dept_users > 0:
            dept_acks = db.query(PolicyAcknowledgement).join(
                PolicyDocument, PolicyAcknowledgement.document_id == PolicyDocument.id
            ).filter(
                PolicyDocument.organization_id == org_id,
                PolicyAcknowledgement.user_id.in_(
                    db.query(User.id).filter(User.dept_id == dept.id)
                )
            ).count()
            dept_accepted = db.query(PolicyAcknowledgement).join(
                PolicyDocument, PolicyAcknowledgement.document_id == PolicyDocument.id
            ).filter(
                PolicyDocument.organization_id == org_id,
                PolicyAcknowledgement.user_id.in_(
                    db.query(User.id).filter(User.dept_id == dept.id)
                ),
                PolicyAcknowledgement.is_acknowledged == True
            ).count()
            dept_compliance.append({
                "department_id": dept.id,
                "department_name": dept.name,
                "compliance_pct": round((dept_accepted / max(1, dept_acks)) * 100, 1) if dept_acks > 0 else 100.0
            })

    return {
        "organization_id": str(org_id),
        "total_employees": total_employees,
        "pending_leaves": pending_leaves,
        "today_attendance_rate": att_rate,
        "today_present_count": today_present,
        "monthly_payroll_spend": monthly_payroll_spend,
        "open_job_postings": open_jobs,
        "pending_salary_advances": pending_advances,
        "pending_attendance_corrections": pending_corrections,
        "pending_reviews": pending_reviews,
        "active_performance_cycles": active_cycles,
        "goal_completion_pct": goal_completion_pct,
        "avg_performance_rating": avg_rating,
        "open_pips": open_pips,
        "promotion_candidates": promotion_candidates,
        "review_completion_pct": review_completion_pct,
        # Performance-specific widgets
        "top_performers_count": top_performers_count,
        "bottom_performers_count": bottom_performers_count,
        "avg_goal_completion": avg_goal_completion,
        "review_completion_rate": review_completion_rate,
        "top_performing_department": top_performing_dept,
        "top_department_avg_rating": top_dept_rating,
        # Learning & Development
        "total_active_courses": total_courses,
        "enrolled_employees_count": enrolled_count,
        "course_completion_rate": course_completion_rate,
        "certificates_issued_count": certs_issued,
        "active_training_sessions": active_sessions,
        "training_budget_spent": budget_spent,
# Succession Planning
        "critical_positions_count": critical_positions,
        "succession_readiness_pct": succession_readiness_pct,
        "nine_box_stars_count": nine_box_stars,
        "active_idps_count": active_idps,
        "high_flight_risk_count": high_flight_risk,
        "active_mentorships_count": active_mentorships,
        # Policy Center
        "active_policies": active_policies,
        "pending_acknowledgements": pending_acknowledgements,
        "compliance_percentage": compliance_percentage,
        "expiring_policies": expiring_policies,
        "overdue_acknowledgements": overdue_acknowledgements,
        "recently_published": recently_published,
        "policy_versions": policy_versions,
        "department_compliance": dept_compliance
    }

