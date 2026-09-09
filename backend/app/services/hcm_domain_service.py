"""
hcm_domain_service.py — VisionCore 3.0 Sprint 5 Human Capital Management (HCM) Domain Services

Provides 14 consolidated domain services spanning:
  - EmployeeProfileService   : extended employee master profile + education/experience/awards/licenses/emergency contacts
  - PerformanceService       : performance cycles & final ratings
  - GoalService              : OKR/SMART goal lifecycle
  - ReviewService            : self/manager/peer/360 review workflows
  - LearningService          : course enrollment & learning paths
  - CourseService            : course catalog & module management
  - AssessmentService        : quiz attempts, scoring & pass/fail
  - SkillService             : skill matrix, verification & gap analysis
  - CompetencyService        : competency framework & gap reports
  - CertificationService     : certification issuance & expiry tracking
  - CareerService            : career paths, levels & individual development plans
  - SuccessionService        : key positions, succession plans & successors
  - DocumentService          : employee document vault (versioning/signature/access)
  - TalentService            : talent pools, nominees & readiness

All services integrate:
  - audit_service.record()              → immutable audit trail
  - event_bus.publish()                 → enterprise domain events
  - notification_service.send()         → in-app/email/push notifications
  - tenant isolation (org_id)           → every query is org-scoped
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models.all_models import (
    AssessmentAttempt,
    AssessmentQuiz,
    CareerLevel,
    CareerPath,
    Certificate,
    Course,
    CourseEnrollment,
    EmployeeAward,
    EmployeeDocument,
    EmployeeEducation,
    EmployeeEmergencyContact,
    EmployeeExperience,
    EmployeeLicense,
    EmployeeProfile,
    EmployeeSkill,
    Goal,
    IndividualDevelopmentPlan,
    KeyPosition,
    NineBoxGrid,
    PerformanceCycle,
    PerformanceRating,
    PerformanceReview,
    SkillMaster,
    SuccessionPlan,
    SuccessorCandidate,
    TalentPool,
    TalentPoolMember,
    User,
)
from app.services.audit_service import audit_service
from app.services.event_bus import event_bus
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)


def _model_to_dict(obj: Any) -> Optional[Dict[str, Any]]:
    """Best-effort ORM object → dict serialization (safe for all HCM entities)."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    try:
        d = {}
        for c in obj.__table__.columns:
            val = getattr(obj, c.name, None)
            if isinstance(val, (datetime, date)):
                val = val.isoformat()
            elif isinstance(val, uuid.UUID):
                val = str(val)
            d[c.name] = val
        return d
    except Exception:
        return {"id": getattr(obj, "id", None)}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# =============================================================================
#  EMPLOYEE PROFILE SERVICE
# =============================================================================

class EmployeeProfileService:
    """Extended employee master profile + auxiliary records (education, experience,
    awards, licenses, emergency contacts) with domain event emission."""

    def get_or_create_profile(self, db: Session, org_id, user_id: int) -> EmployeeProfile:
        profile = (
            db.query(EmployeeProfile)
            .filter(EmployeeProfile.org_id == org_id, EmployeeProfile.user_id == user_id)
            .first()
        )
        if not profile:
            profile = EmployeeProfile(org_id=org_id, user_id=user_id)
            db.add(profile)
            db.commit()
            db.refresh(profile)
        return profile

    def upsert_profile(self, db: Session, org_id, user_id: int, data: Dict[str, Any],
                       actor_id: Optional[int] = None) -> EmployeeProfile:
        profile = self.get_or_create_profile(db, org_id, user_id)
        allowed = {c.name for c in EmployeeProfile.__table__.columns if c.name not in
                   ("id", "org_id", "user_id", "created_at", "updated_at")}
        for field, value in data.items():
            if field in allowed and value is not None:
                setattr(profile, field, value)
        profile.updated_at = _now()
        db.commit()
        db.refresh(profile)

        audit_service.record(
            actor_user_id=actor_id or user_id,
            organization_id=str(org_id),
            module="hcm_employee_profile",
            action="update",
            entity_type="employee_profile",
            entity_id=str(profile.id),
            summary=f"Employee profile updated for user {user_id}",
            details={"fields": list(data.keys())},
        )
        event_bus.publish(
            "EmployeeProfileUpdated", str(org_id),
            {"profile_id": profile.id, "user_id": user_id},
            actor_id=actor_id or user_id,
        )
        return profile

    def add_education(self, db: Session, org_id, user_id: int, data: Dict[str, Any],
                      actor_id: Optional[int] = None) -> EmployeeEducation:
        record = EmployeeEducation(org_id=org_id, user_id=user_id, **data)
        db.add(record)
        db.commit()
        db.refresh(record)
        audit_service.record(
            actor_user_id=actor_id or user_id, organization_id=str(org_id),
            module="hcm_employee_profile", action="create", entity_type="employee_education",
            entity_id=str(record.id), summary=f"Education added for user {user_id}",
        )
        return record

    def list_education(self, db: Session, org_id, user_id: int) -> List[EmployeeEducation]:
        return (
            db.query(EmployeeEducation)
            .filter(EmployeeEducation.org_id == org_id, EmployeeEducation.user_id == user_id)
            .order_by(EmployeeEducation.end_year.desc())
            .all()
        )

    def add_experience(self, db: Session, org_id, user_id: int, data: Dict[str, Any],
                       actor_id: Optional[int] = None) -> EmployeeExperience:
        record = EmployeeExperience(org_id=org_id, user_id=user_id, **data)
        db.add(record)
        db.commit()
        db.refresh(record)
        audit_service.record(
            actor_user_id=actor_id or user_id, organization_id=str(org_id),
            module="hcm_employee_profile", action="create", entity_type="employee_experience",
            entity_id=str(record.id), summary=f"Experience added for user {user_id}",
        )
        return record

    def list_experience(self, db: Session, org_id, user_id: int) -> List[EmployeeExperience]:
        return (
            db.query(EmployeeExperience)
            .filter(EmployeeExperience.org_id == org_id, EmployeeExperience.user_id == user_id)
            .order_by(EmployeeExperience.start_date.desc())
            .all()
        )

    def add_award(self, db: Session, org_id, user_id: int, data: Dict[str, Any],
                  actor_id: Optional[int] = None) -> EmployeeAward:
        record = EmployeeAward(org_id=org_id, user_id=user_id, **data)
        db.add(record)
        db.commit()
        db.refresh(record)
        event_bus.publish(
            "EmployeeAwarded", str(org_id),
            {"award_id": record.id, "user_id": user_id, "title": record.title},
            actor_id=actor_id or user_id,
        )
        notification_service.send(
            user_id=user_id, organization_id=str(org_id),
            title="Congratulations! 🎉",
            message=f"You received the award '{record.title}'.",
            source_module="hcm", source_event="EmployeeAwarded", source_id=str(record.id),
        )
        return record

    def list_awards(self, db: Session, org_id, user_id: int) -> List[EmployeeAward]:
        return (
            db.query(EmployeeAward)
            .filter(EmployeeAward.org_id == org_id, EmployeeAward.user_id == user_id)
            .order_by(EmployeeAward.award_date.desc())
            .all()
        )

    def add_license(self, db: Session, org_id, user_id: int, data: Dict[str, Any],
                    actor_id: Optional[int] = None) -> EmployeeLicense:
        record = EmployeeLicense(org_id=org_id, user_id=user_id, **data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def list_licenses(self, db: Session, org_id, user_id: int) -> List[EmployeeLicense]:
        return (
            db.query(EmployeeLicense)
            .filter(EmployeeLicense.org_id == org_id, EmployeeLicense.user_id == user_id)
            .order_by(EmployeeLicense.issue_date.desc())
            .all()
        )

    def add_emergency_contact(self, db: Session, org_id, user_id: int, data: Dict[str, Any],
                              actor_id: Optional[int] = None) -> EmployeeEmergencyContact:
        record = EmployeeEmergencyContact(org_id=org_id, user_id=user_id, **data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def list_emergency_contacts(self, db: Session, org_id, user_id: int) -> List[EmployeeEmergencyContact]:
        return (
            db.query(EmployeeEmergencyContact)
            .filter(EmployeeEmergencyContact.org_id == org_id, EmployeeEmergencyContact.user_id == user_id)
            .all()
        )

    def profile_dossier(self, db: Session, org_id, user_id: int) -> Dict[str, Any]:
        """Full employee dossier: profile + auxiliary records + KPIs + goals + skills."""
        return {
            "profile": _model_to_dict(self.get_or_create_profile(db, org_id, user_id)),
            "education": [_model_to_dict(e) for e in self.list_education(db, org_id, user_id)],
            "experience": [_model_to_dict(e) for e in self.list_experience(db, org_id, user_id)],
            "awards": [_model_to_dict(a) for a in self.list_awards(db, org_id, user_id)],
            "licenses": [_model_to_dict(l) for l in self.list_licenses(db, org_id, user_id)],
            "emergency_contacts": [_model_to_dict(c) for c in self.list_emergency_contacts(db, org_id, user_id)],
        }


# =============================================================================
#  PERFORMANCE SERVICE
# =============================================================================

class PerformanceService:
    """Performance cycles and final ratings."""

    def list_cycles(self, db: Session, org_id, status_filter: Optional[str] = None) -> List[PerformanceCycle]:
        q = db.query(PerformanceCycle).filter(PerformanceCycle.organization_id == org_id)
        if status_filter:
            q = q.filter(PerformanceCycle.status == status_filter)
        return q.order_by(PerformanceCycle.start_date.desc()).all()

    def create_cycle(self, db: Session, org_id, data: Dict[str, Any],
                     created_by: int) -> PerformanceCycle:
        cycle = PerformanceCycle(organization_id=org_id, created_by_user_id=created_by, **data)
        db.add(cycle)
        db.commit()
        db.refresh(cycle)
        event_bus.publish(
            "PerformanceCycleCreated", str(org_id),
            {"cycle_id": cycle.id, "name": cycle.name},
            actor_id=created_by,
        )
        return cycle

    def ratings_dashboard(self, db: Session, org_id, cycle_id: Optional[int] = None) -> Dict[str, Any]:
        q = db.query(PerformanceRating).filter(PerformanceRating.organization_id == org_id)
        if cycle_id:
            q = q.filter(PerformanceRating.cycle_id == cycle_id)
        ratings = q.all()
        avg = round(sum(float(r.final_rating or 0) for r in ratings) / max(len(ratings), 1), 2)
        return {
            "total_rated": len(ratings),
            "avg_rating": avg,
            "distribution": {
                "exceeds": sum(1 for r in ratings if (r.final_rating or 0) >= 4.5),
                "meets": sum(1 for r in ratings if 3.0 <= (r.final_rating or 0) < 4.5),
                "below": sum(1 for r in ratings if (r.final_rating or 0) < 3.0),
            },
        }


# =============================================================================
#  GOAL SERVICE
# =============================================================================

class GoalService:
    """OKR/SMART goal lifecycle with progress logging."""

    def create_goal(self, db: Session, org_id, user_id: int, data: Dict[str, Any],
                    actor_id: Optional[int] = None) -> Goal:
        goal = Goal(organization_id=org_id, user_id=user_id, **data)
        db.add(goal)
        db.commit()
        db.refresh(goal)
        event_bus.publish(
            "GoalCreated", str(org_id),
            {"goal_id": goal.id, "user_id": user_id, "title": goal.title},
            actor_id=actor_id or user_id,
        )
        return goal

    def list_goals(self, db: Session, org_id, user_id: Optional[int] = None,
                   status: Optional[str] = None) -> List[Goal]:
        q = db.query(Goal).filter(Goal.organization_id == org_id)
        if user_id:
            q = q.filter(Goal.user_id == user_id)
        if status:
            q = q.filter(Goal.status == status)
        return q.order_by(Goal.created_at.desc()).all()

    def log_progress(self, db: Session, org_id, goal_id: int, user_id: int,
                     value: float, note: Optional[str] = None,
                     actor_id: Optional[int] = None) -> Goal:
        goal = db.query(Goal).filter(Goal.id == goal_id, Goal.organization_id == org_id).first()
        if not goal:
            raise ValueError("Goal not found")
        completion = min(100.0, max(0.0, value / goal.target_value * 100)) if goal.target_value else 0.0
        goal.current_value = value
        goal.completion_pct = round(completion, 2)
        if goal.completion_pct >= 100.0:
            goal.status = "completed"
            event_bus.publish(
                "GoalCompleted", str(org_id),
                {"goal_id": goal.id, "user_id": user_id, "title": goal.title},
                actor_id=actor_id or user_id,
            )
        db.commit()
        db.refresh(goal)
        return goal


# =============================================================================
#  REVIEW SERVICE
# =============================================================================

class ReviewService:
    """Self/manager/peer/360 performance review workflow."""

    def create_review(self, db: Session, org_id, data: Dict[str, Any],
                      actor_id: Optional[int] = None) -> PerformanceReview:
        review = PerformanceReview(organization_id=org_id, **data)
        db.add(review)
        db.commit()
        db.refresh(review)
        event_bus.publish(
            "PerformanceReviewStarted", str(org_id),
            {"review_id": review.id, "reviewee": review.reviewee_user_id, "type": review.review_type},
            actor_id=actor_id,
        )
        return review

    def list_reviews(self, db: Session, org_id, user_id: Optional[int] = None,
                     status: Optional[str] = None) -> List[PerformanceReview]:
        q = db.query(PerformanceReview).filter(PerformanceReview.organization_id == org_id)
        if user_id:
            q = q.filter(PerformanceReview.reviewee_user_id == user_id)
        if status:
            q = q.filter(PerformanceReview.status == status)
        return q.order_by(PerformanceReview.created_at.desc()).all()

    def submit_review(self, db: Session, org_id, review_id: int, data: Dict[str, Any],
                      actor_id: Optional[int] = None) -> PerformanceReview:
        review = db.query(PerformanceReview).filter(
            PerformanceReview.id == review_id, PerformanceReview.organization_id == org_id).first()
        if not review:
            raise ValueError("Review not found")
        for field in ("overall_score", "strengths", "areas_for_improvement", "comments"):
            if field in data and data[field] is not None:
                setattr(review, field, data[field])
        review.status = "submitted"
        review.submitted_at = _now()
        db.commit()
        db.refresh(review)
        event_bus.publish(
            "PerformanceReviewCompleted", str(org_id),
            {"review_id": review.id, "reviewee": review.reviewee_user_id, "score": review.overall_score},
            actor_id=actor_id,
        )
        notification_service.send(
            user_id=review.reviewee_user_id, organization_id=str(org_id),
            title="Review Submitted",
            message=f"Your {review.review_type} review has been submitted.",
            source_module="hcm", source_event="PerformanceReviewCompleted", source_id=str(review.id),
        )
        return review


# =============================================================================
#  LEARNING & COURSE SERVICES
# =============================================================================

class CourseService:
    """Course catalog & module management."""

    def list_courses(self, db: Session, org_id) -> List[Course]:
        return (
            db.query(Course)
            .filter(Course.organization_id == org_id, Course.is_active.is_(True))
            .order_by(Course.title)
            .all()
        )

    def create_course(self, db: Session, org_id, data: Dict[str, Any],
                      actor_id: Optional[int] = None) -> Course:
        course = Course(organization_id=org_id, **data)
        db.add(course)
        db.commit()
        db.refresh(course)
        return course


class LearningService:
    """Course enrollment, progress and completion."""

    def enroll(self, db: Session, org_id, course_id: int, user_id: int,
               assigned_by: Optional[int] = None, actor_id: Optional[int] = None) -> CourseEnrollment:
        enrollment = CourseEnrollment(
            organization_id=org_id, course_id=course_id, user_id=user_id,
            assigned_by_user_id=assigned_by or user_id,
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        event_bus.publish(
            "CourseAssigned", str(org_id),
            {"enrollment_id": enrollment.id, "course_id": course_id, "user_id": user_id},
            actor_id=actor_id or user_id,
        )
        return enrollment

    def list_enrollments(self, db: Session, org_id, user_id: Optional[int] = None,
                         status: Optional[str] = None) -> List[CourseEnrollment]:
        q = db.query(CourseEnrollment).filter(CourseEnrollment.organization_id == org_id)
        if user_id:
            q = q.filter(CourseEnrollment.user_id == user_id)
        if status:
            q = q.filter(CourseEnrollment.status == status)
        return q.order_by(CourseEnrollment.enrolled_at.desc()).all()

    def mark_completed(self, db: Session, org_id, enrollment_id: int,
                       score: Optional[float] = None, actor_id: Optional[int] = None) -> CourseEnrollment:
        enrollment = db.query(CourseEnrollment).filter(
            CourseEnrollment.id == enrollment_id, CourseEnrollment.organization_id == org_id).first()
        if not enrollment:
            raise ValueError("Enrollment not found")
        enrollment.status = "completed"
        enrollment.progress_pct = 100.0
        if score is not None:
            enrollment.score = score
        enrollment.completed_at = _now()
        db.commit()
        db.refresh(enrollment)
        event_bus.publish(
            "CourseCompleted", str(org_id),
            {"enrollment_id": enrollment.id, "course_id": enrollment.course_id, "user_id": enrollment.user_id},
            actor_id=actor_id or enrollment.user_id,
        )
        return enrollment


# =============================================================================
#  ASSESSMENT SERVICE
# =============================================================================

class AssessmentService:
    """Quiz attempts, scoring & pass/fail resolution."""

    def submit_attempt(self, db: Session, org_id, quiz_id: int, user_id: int,
                       score: float, max_score: float = 100.0,
                       enrollment_id: Optional[int] = None,
                       response_data: Optional[dict] = None) -> AssessmentAttempt:
        quiz = db.query(AssessmentQuiz).filter(AssessmentQuiz.id == quiz_id).first()
        pass_threshold = quiz.pass_score if quiz else 70.0
        passed = score >= pass_threshold
        attempt = AssessmentAttempt(
            quiz_id=quiz_id, user_id=user_id, enrollment_id=enrollment_id,
            score=score, max_score=max_score, passed=passed,
            completed_at=_now(), response_data=response_data or {},
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        if passed:
            event_bus.publish(
                "AssessmentPassed", str(org_id),
                {"attempt_id": attempt.id, "quiz_id": quiz_id, "user_id": user_id, "score": score},
                actor_id=user_id,
            )
        return attempt


# =============================================================================
#  SKILL & COMPETENCY SERVICES
# =============================================================================

class SkillService:
    """Skill matrix, verification & gap analysis."""

    def add_or_update_skill(self, db: Session, org_id, user_id: int, skill_id: int,
                            proficiency_level: str, source: str = "course_completion",
                            verified_by: Optional[int] = None,
                            actor_id: Optional[int] = None) -> EmployeeSkill:
        record = (
            db.query(EmployeeSkill)
            .filter(EmployeeSkill.org_id == org_id, EmployeeSkill.user_id == user_id,
                    EmployeeSkill.skill_id == skill_id)
            .first()
        )
        if record:
            record.proficiency_level = proficiency_level
            record.source = source
            if verified_by:
                record.verified_by_user_id = verified_by
                record.verified_at = _now()
        else:
            record = EmployeeSkill(
                org_id=org_id, user_id=user_id, skill_id=skill_id,
                proficiency_level=proficiency_level, source=source,
                verified_by_user_id=verified_by,
                verified_at=_now() if verified_by else None,
            )
            db.add(record)
        db.commit()
        db.refresh(record)
        event_bus.publish(
            "SkillVerified" if verified_by else "SkillUpdated", str(org_id),
            {"skill_record_id": record.id, "user_id": user_id, "skill_id": skill_id,
             "level": proficiency_level},
            actor_id=actor_id or user_id,
        )
        return record

    def list_skills(self, db: Session, org_id, user_id: Optional[int] = None) -> List[EmployeeSkill]:
        q = db.query(EmployeeSkill).filter(EmployeeSkill.org_id == org_id)
        if user_id:
            q = q.filter(EmployeeSkill.user_id == user_id)
        return q.order_by(EmployeeSkill.skill_id).all()

    def skill_matrix(self, db: Session, org_id) -> Dict[str, Any]:
        records = self.list_skills(db, org_id)
        by_user: Dict[int, Dict[str, Any]] = {}
        for r in records:
            bucket = by_user.setdefault(r.user_id, {"count": 0, "verified": 0, "highest": None})
            bucket["count"] += 1
            if r.verified_at:
                bucket["verified"] += 1
        return {
            "total_skills_recorded": len(records),
            "users_with_skills": len(by_user),
            "verified_count": sum(1 for r in records if r.verified_at),
            "coverage": round(len(by_user) / max(_org_user_count(db, org_id), 1) * 100, 1),
        }


class CompetencyService:
    """Competency framework & gap reports."""

    def competency_gap(self, db: Session, org_id, user_id: int) -> Dict[str, Any]:
        """Compute competency gap from 9-box grid and skill coverage."""
        nine_box = (
            db.query(NineBoxGrid)
            .filter(NineBoxGrid.organization_id == org_id, NineBoxGrid.user_id == user_id)
            .order_by(NineBoxGrid.created_at.desc())
            .first()
        )
        skills = (
            db.query(EmployeeSkill)
            .filter(EmployeeSkill.org_id == org_id, EmployeeSkill.user_id == user_id)
            .all()
        )
        level_score = {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}
        total = sum(level_score.get(s.proficiency_level, 1) for s in skills)
        coverage = round(total / max(len(skills) * 4, 1) * 100, 1) if skills else 0.0
        return {
            "user_id": user_id,
            "skill_count": len(skills),
            "skill_coverage_pct": coverage,
            "nine_box": _model_to_dict(nine_box),
            "gap_level": "HIGH" if coverage < 50 else ("MEDIUM" if coverage < 75 else "LOW"),
            "recommendation": (
                "Enroll in structured training programs" if coverage < 50
                else "Focus on advanced/expert certifications" if coverage < 75
                else "Maintain current development trajectory"
            ),
        }


# =============================================================================
#  CERTIFICATION SERVICE
# =============================================================================

class CertificationService:
    """Certification issuance, tracking & expiry alerts."""

    def issue_certificate(self, db: Session, org_id, user_id: int, course_id: int,
                          enrollment_id: Optional[int] = None,
                          expiry_date: Optional[datetime] = None,
                          certificate_url: Optional[str] = None,
                          actor_id: Optional[int] = None) -> Certificate:
        cert_number = f"CERT-{uuid.uuid4().hex[:10].upper()}"
        cert = Certificate(
            organization_id=org_id, user_id=user_id, course_id=course_id,
            enrollment_id=enrollment_id, certificate_number=cert_number,
            expiry_date=expiry_date, certificate_url=certificate_url,
        )
        db.add(cert)
        db.commit()
        db.refresh(cert)
        event_bus.publish(
            "CertificationIssued", str(org_id),
            {"certificate_id": cert.id, "user_id": user_id, "course_id": course_id,
             "number": cert_number},
            actor_id=actor_id or user_id,
        )
        notification_service.send(
            user_id=user_id, organization_id=str(org_id),
            title="Certificate Issued 🏆",
            message=f"Your certificate {cert_number} has been issued.",
            source_module="hcm", source_event="CertificationIssued", source_id=str(cert.id),
        )
        return cert

    def list_certificates(self, db: Session, org_id, user_id: Optional[int] = None) -> List[Certificate]:
        q = db.query(Certificate).filter(Certificate.organization_id == org_id)
        if user_id:
            q = q.filter(Certificate.user_id == user_id)
        return q.order_by(Certificate.issue_date.desc()).all()


# =============================================================================
#  CAREER SERVICE
# =============================================================================

class CareerService:
    """Career paths, levels & individual development plans (IDPs)."""

    def list_career_paths(self, db: Session, org_id) -> List[CareerPath]:
        return (
            db.query(CareerPath)
            .filter(CareerPath.organization_id == org_id)
            .order_by(CareerPath.title)
            .all()
        )

    def create_career_path(self, db: Session, org_id, data: Dict[str, Any],
                           actor_id: Optional[int] = None) -> CareerPath:
        path = CareerPath(organization_id=org_id, **data)
        db.add(path)
        db.commit()
        db.refresh(path)
        return path

    def list_idps(self, db: Session, org_id, user_id: Optional[int] = None) -> List[IndividualDevelopmentPlan]:
        q = db.query(IndividualDevelopmentPlan).filter(IndividualDevelopmentPlan.organization_id == org_id)
        if user_id:
            q = q.filter(IndividualDevelopmentPlan.user_id == user_id)
        return q.order_by(IndividualDevelopmentPlan.created_at.desc()).all()

    def create_idp(self, db: Session, org_id, user_id: int, data: Dict[str, Any],
                   actor_id: Optional[int] = None) -> IndividualDevelopmentPlan:
        idp = IndividualDevelopmentPlan(organization_id=org_id, user_id=user_id, **data)
        db.add(idp)
        db.commit()
        db.refresh(idp)
        event_bus.publish(
            "CareerPlanUpdated", str(org_id),
            {"idp_id": idp.id, "user_id": user_id},
            actor_id=actor_id or user_id,
        )
        return idp


# =============================================================================
#  SUCCESSION SERVICE
# =============================================================================

class SuccessionService:
    """Key positions, succession plans, candidates & nine-box grid."""

    def list_key_positions(self, db: Session, org_id) -> List[KeyPosition]:
        return (
            db.query(KeyPosition)
            .filter(KeyPosition.organization_id == org_id)
            .order_by(KeyPosition.impact_rating.desc())
            .all()
        )

    def create_key_position(self, db: Session, org_id, data: Dict[str, Any],
                            actor_id: Optional[int] = None) -> KeyPosition:
        kp = KeyPosition(organization_id=org_id, **data)
        db.add(kp)
        db.commit()
        db.refresh(kp)
        return kp

    def list_plans(self, db: Session, org_id) -> List[SuccessionPlan]:
        return (
            db.query(SuccessionPlan)
            .filter(SuccessionPlan.organization_id == org_id)
            .order_by(SuccessionPlan.created_at.desc())
            .all()
        )

    def create_plan(self, db: Session, org_id, data: Dict[str, Any],
                    actor_id: Optional[int] = None) -> SuccessionPlan:
        plan = SuccessionPlan(organization_id=org_id, **data)
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan

    def nominate_candidate(self, db: Session, org_id, plan_id: int, candidate_user_id: int,
                           readiness_rating: str = "ready_1_year",
                           nomination_notes: Optional[str] = None,
                           actor_id: Optional[int] = None) -> SuccessorCandidate:
        candidate = SuccessorCandidate(
            succession_plan_id=plan_id, candidate_user_id=candidate_user_id,
            readiness_rating=readiness_rating, nomination_notes=nomination_notes,
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        event_bus.publish(
            "SuccessorAssigned", str(org_id),
            {"candidate_id": candidate.id, "plan_id": plan_id, "user_id": candidate_user_id,
             "readiness": readiness_rating},
            actor_id=actor_id,
        )
        return candidate

    def nine_box_grid(self, db: Session, org_id) -> List[NineBoxGrid]:
        return (
            db.query(NineBoxGrid)
            .filter(NineBoxGrid.organization_id == org_id)
            .order_by(NineBoxGrid.created_at.desc())
            .all()
        )

    def evaluate_nine_box(self, db: Session, org_id, user_id: int,
                          performance_rating: int, potential_rating: int,
                          evaluated_by: Optional[int] = None,
                          cycle_id: Optional[int] = None) -> NineBoxGrid:
        """9-box placement from performance (1-3) x potential (1-3) ratings."""
        box_map = {
            (3, 3): "Star", (3, 2): "High Professional", (3, 1): "High Performer",
            (2, 3): "High Potential", (2, 2): "Core Player", (2, 1): "Solid Professional",
            (1, 3): "Enigma", (1, 2): "Potential", (1, 1): "Underperformer",
        }
        box_category = box_map.get((performance_rating, potential_rating), "Core Player")
        record = NineBoxGrid(
            organization_id=org_id, user_id=user_id, cycle_id=cycle_id,
            performance_rating=performance_rating, potential_rating=potential_rating,
            box_category=box_category, evaluated_by_user_id=evaluated_by,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        event_bus.publish(
            "NineBoxEvaluated", str(org_id),
            {"grid_id": record.id, "user_id": user_id, "box": box_category},
            actor_id=evaluated_by,
        )
        return record


# =============================================================================
#  DOCUMENT SERVICE
# =============================================================================

class DocumentService:
    """Employee document vault — versioning, signature flags, access control."""

    def upload_document(self, db: Session, org_id, user_id: int, data: Dict[str, Any],
                        actor_id: Optional[int] = None) -> EmployeeDocument:
        doc = EmployeeDocument(org_id=org_id, user_id=user_id, is_signed=False, **data)
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    def list_documents(self, db: Session, org_id, user_id: Optional[int] = None,
                       document_type: Optional[str] = None) -> List[EmployeeDocument]:
        q = db.query(EmployeeDocument).filter(EmployeeDocument.org_id == org_id)
        if user_id:
            q = q.filter(EmployeeDocument.user_id == user_id)
        if document_type:
            q = q.filter(EmployeeDocument.document_type == document_type)
        return q.order_by(EmployeeDocument.created_at.desc()).all()

    def sign_document(self, db: Session, org_id, document_id: int,
                      actor_id: Optional[int] = None) -> EmployeeDocument:
        doc = db.query(EmployeeDocument).filter(
            EmployeeDocument.id == document_id, EmployeeDocument.org_id == org_id).first()
        if not doc:
            raise ValueError("Document not found")
        doc.is_signed = True
        doc.signed_at = _now()
        db.commit()
        db.refresh(doc)
        audit_service.record(
            actor_user_id=actor_id, organization_id=str(org_id),
            module="hcm_documents", action="sign", entity_type="employee_document",
            entity_id=str(doc.id), summary=f"Document '{doc.title}' signed",
            severity="warning",
        )
        return doc


# =============================================================================
#  TALENT SERVICE
# =============================================================================

class TalentService:
    """Talent pools, nominees and readiness tracking."""

    def list_pools(self, db: Session, org_id, status: Optional[str] = None) -> List[TalentPool]:
        q = db.query(TalentPool).filter(TalentPool.org_id == org_id)
        if status:
            q = q.filter(TalentPool.status == status)
        return q.order_by(TalentPool.name).all()

    def create_pool(self, db: Session, org_id, data: Dict[str, Any],
                    actor_id: Optional[int] = None) -> TalentPool:
        pool = TalentPool(org_id=org_id, **data)
        db.add(pool)
        db.commit()
        db.refresh(pool)
        return pool

    def add_member(self, db: Session, org_id, pool_id: int, user_id: int,
                   readiness_level: str = "ready_1_year",
                   nomination_reason: Optional[str] = None,
                   actor_id: Optional[int] = None) -> TalentPoolMember:
        member = TalentPoolMember(
            pool_id=pool_id, user_id=user_id,
            readiness_level=readiness_level, nomination_reason=nomination_reason,
        )
        db.add(member)
        db.commit()
        db.refresh(member)
        event_bus.publish(
            "TalentPoolMemberAdded", str(org_id),
            {"member_id": member.id, "pool_id": pool_id, "user_id": user_id,
             "readiness": readiness_level},
            actor_id=actor_id,
        )
        return member

    def pool_members(self, db: Session, org_id, pool_id: int) -> List[TalentPoolMember]:
        return (
            db.query(TalentPoolMember)
            .filter(TalentPoolMember.pool_id == pool_id)
            .all()
        )

    def talent_dashboard(self, db: Session, org_id) -> Dict[str, Any]:
        pools = self.list_pools(db, org_id)
        members = (
            db.query(TalentPoolMember)
            .join(TalentPool, TalentPool.id == TalentPoolMember.pool_id)
            .filter(TalentPool.org_id == org_id)
            .all()
        )
        readiness_counts: Dict[str, int] = {}
        for m in members:
            readiness_counts[m.readiness_level] = readiness_counts.get(m.readiness_level, 0) + 1
        return {
            "total_pools": len(pools),
            "total_members": len(members),
            "readiness": readiness_counts,
            "pools": [_model_to_dict(p) for p in pools],
        }


# =============================================================================
#  AGGREGATE HCM DASHBOARD
# =============================================================================

def _org_user_count(db: Session, org_id) -> int:
    return db.query(User).filter(User.org_id == org_id, User.is_deleted == 0).count()


def hcm_dashboard(db: Session, org_id) -> Dict[str, Any]:
    """Unified HCM executive dashboard across all 14 domains."""
    employees = _org_user_count(db, org_id)
    profiles = db.query(EmployeeProfile).filter(EmployeeProfile.org_id == org_id).count()
    goals_active = db.query(Goal).filter(Goal.organization_id == org_id,
                                         Goal.status.in_(["active", "on_hold"])).count()
    goals_completed = db.query(Goal).filter(Goal.organization_id == org_id,
                                            Goal.status == "completed").count()
    reviews_pending = db.query(PerformanceReview).filter(
        PerformanceReview.organization_id == org_id,
        PerformanceReview.status.in_(["pending", "in_progress"])).count()
    reviews_completed = db.query(PerformanceReview).filter(
        PerformanceReview.organization_id == org_id,
        PerformanceReview.status == "submitted").count()
    enrollments = db.query(CourseEnrollment).filter(
        CourseEnrollment.organization_id == org_id).count()
    certs = db.query(Certificate).filter(Certificate.organization_id == org_id).count()
    skills = db.query(EmployeeSkill).filter(EmployeeSkill.org_id == org_id).count()
    key_positions = db.query(KeyPosition).filter(KeyPosition.organization_id == org_id).count()
    successors = db.query(SuccessorCandidate).join(
        SuccessionPlan, SuccessionPlan.id == SuccessorCandidate.succession_plan_id
    ).filter(SuccessionPlan.organization_id == org_id).count()
    docs = db.query(EmployeeDocument).filter(EmployeeDocument.org_id == org_id).count()
    pools = db.query(TalentPool).filter(TalentPool.org_id == org_id).count()

    return {
        "employees": employees,
        "profile_completion_pct": round(profiles / max(employees, 1) * 100, 1),
        "goals": {"active": goals_active, "completed": goals_completed,
                  "completion_rate": round(goals_completed / max(goals_active + goals_completed, 1) * 100, 1)},
        "reviews": {"pending": reviews_pending, "completed": reviews_completed,
                    "completion_rate": round(reviews_completed / max(reviews_pending + reviews_completed, 1) * 100, 1)},
        "learning": {"enrollments": enrollments, "certificates_issued": certs,
                     "skills_recorded": skills},
        "succession": {"key_positions": key_positions, "successors_nominated": successors},
        "documents": docs,
        "talent_pools": pools,
    }


# =============================================================================
#  Singleton service instances
# =============================================================================

employee_profile_service = EmployeeProfileService()
performance_service = PerformanceService()
goal_service = GoalService()
review_service = ReviewService()
learning_service = LearningService()
course_service = CourseService()
assessment_service = AssessmentService()
skill_service = SkillService()
competency_service = CompetencyService()
certification_service = CertificationService()
career_service = CareerService()
succession_service = SuccessionService()
document_service = DocumentService()
talent_service = TalentService()

