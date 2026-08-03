"""
test_hcm_domain.py — Unit & Integration Tests for Sprint 5 Human Capital Management (HCM) Domain
VisionCore 3.0 Enterprise Platform

Covers all 14 consolidated domain services:
  - EmployeeProfileService : profile upsert + education/experience/awards/licenses/emergency contacts
  - PerformanceService     : cycles & ratings dashboard
  - GoalService            : create goal → GoalCreated; complete → GoalCompleted
  - ReviewService          : create review → PerformanceReviewStarted; submit → PerformanceReviewCompleted
  - CourseService          : course catalog & creation
  - LearningService        : enroll → CourseAssigned; complete → CourseCompleted
  - AssessmentService      : quiz attempt pass/fail → AssessmentPassed
  - SkillService           : skill matrix & verification → SkillVerified / SkillUpdated
  - CompetencyService      : nine-box + skill coverage gap analysis
  - CertificationService   : issue → CertificationIssued (+ notification)
  - CareerService          : career paths & IDPs → CareerPlanUpdated
  - SuccessionService      : key positions, plans, nominees → SuccessorAssigned; nine-box evaluation
  - DocumentService        : document vault upload & digital signing (audit)
  - TalentService          : talent pools, members & readiness dashboard → TalentPoolMemberAdded

All tests use MagicMock DB sessions and patch audit/event/notification integration
points — mirroring the established test_workforce_domain.py and test_org_identity_domain.py style.
"""
import uuid
from datetime import date, datetime, timezone
from unittest.mock import ANY, MagicMock, patch

from app.db.models.all_models import (
    AssessmentQuiz,
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
    PerformanceRating,
    PerformanceReview,
    SkillMaster,
    SuccessionPlan,
    SuccessorCandidate,
    TalentPool,
    TalentPoolMember,
    User,
)
from app.services.hcm_domain_service import (
    assessment_service,
    career_service,
    certification_service,
    competency_service,
    course_service,
    document_service,
    employee_profile_service,
    goal_service,
    hcm_dashboard,
    learning_service,
    performance_service,
    review_service,
    skill_service,
    succession_service,
    talent_service,
)


def _org_id():
    return uuid.uuid4()


def _make_db(model_map):
    """Build a MagicMock DB whose query(model) chains resolve to mapped rows.
    Handles both plain filter() chains and filter().order_by() chains for the
    configurable 'first' and 'all' endpoints.
    model_map: {ModelClass: {"first": obj | None, "all": [objs] | None}}
    """
    db = MagicMock()

    def mock_query(model):
        m = MagicMock()
        spec = model_map.get(model, {})
        first_val = spec.get("first", None)
        all_val = spec.get("all", None)
        if "first" in spec:
            m.filter.return_value.first.return_value = first_val
            m.filter.return_value.order_by.return_value.first.return_value = first_val
        if "all" in spec:
            m.filter.return_value.all.return_value = all_val
            m.filter.return_value.order_by.return_value.all.return_value = all_val
        return m

    db.query.side_effect = mock_query
    return db


# =============================================================================
#  EMPLOYEE PROFILE SERVICE
# =============================================================================

def test_employee_profile_upsert_publishes_event():
    """Upserting an employee profile persists allowed fields and emits the
    EmployeeProfileUpdated domain event."""
    org = _org_id()
    profile = EmployeeProfile(id=1, org_id=org, user_id=10)
    db = _make_db({EmployeeProfile: {"first": profile}})

    with patch("app.services.audit_service.audit_service.record") as mock_audit, \
         patch("app.services.event_bus.event_bus.publish") as mock_event:
        updated = employee_profile_service.upsert_profile(
            db, org, 10,
            {"gender": "Female", "nationality": "Indian", "blood_group": "O+"},
            actor_id=5,
        )
        assert updated.gender == "Female"
        assert updated.nationality == "Indian"
        assert updated.blood_group == "O+"
        mock_audit.assert_called_once()
        mock_event.assert_called_with(
            "EmployeeProfileUpdated", str(org), ANY, actor_id=5
        )


def test_employee_profile_education_experience_awards_licenses_contacts():
    """Auxiliary employee profile records (education, experience, award, license,
    emergency contact) are created org-scoped and audit-logged."""
    org = _org_id()

    with patch("app.services.audit_service.audit_service.record") as mock_audit, \
         patch("app.services.event_bus.event_bus.publish") as mock_event, \
         patch("app.services.notification_service.notification_service.send") as mock_notif:
        education = employee_profile_service.add_education(
            db=MagicMock(), org_id=org, user_id=10,
            data={"degree": "B.Tech", "field_of_study": "CS", "institution_name": "IIT",
                  "start_year": 2016, "end_year": 2020, "grade_or_gpa": "8.5"},
        )
        assert education.user_id == 10
        assert education.field_of_study == "CS"

        experience = employee_profile_service.add_experience(
            db=MagicMock(), org_id=org, user_id=10,
            data={"company_name": "Acme", "job_title": "SWE",
                  "start_date": date(2020, 7, 1), "end_date": date(2024, 1, 1)},
        )
        assert experience.job_title == "SWE"

        award = employee_profile_service.add_award(
            db=MagicMock(), org_id=org, user_id=10,
            data={"title": "Star Performer", "awarded_by": "CEO",
                  "award_date": date(2024, 5, 1), "category": "annual"},
        )
        assert award.title == "Star Performer"
        mock_event.assert_called_with("EmployeeAwarded", str(org), ANY, actor_id=10)
        mock_notif.assert_called_once()

        license_ = employee_profile_service.add_license(
            db=MagicMock(), org_id=org, user_id=10,
            data={"license_name": "PMP", "license_number": "PMP-123",
                  "issuing_authority": "PMI", "issue_date": date(2023, 1, 1)},
        )
        assert license_.license_name == "PMP"

        contact = employee_profile_service.add_emergency_contact(
            db=MagicMock(), org_id=org, user_id=10,
            data={"contact_name": "Jane Doe", "relationship_type": "Spouse",
                  "phone_number": "+91-9000000000", "is_primary": True},
        )
        assert contact.contact_name == "Jane Doe"
        assert contact.is_primary is True
        mock_audit.assert_any_call(
            actor_user_id=10, organization_id=str(org),
            module="hcm_employee_profile", action="create",
            entity_type="employee_education", entity_id=str(education.id),
            summary=ANY,
        )


def test_employee_profile_dossier_aggregates():
    """profile_dossier returns a consolidated employee record bundle."""
    org = _org_id()
    profile = EmployeeProfile(id=1, org_id=org, user_id=10, nationality="Indian")
    education = EmployeeEducation(id=1, org_id=org, user_id=10, degree="B.Tech")
    experience = EmployeeExperience(id=1, org_id=org, user_id=10, company_name="Acme")
    award = EmployeeAward(id=1, org_id=org, user_id=10, title="Award")
    license_ = EmployeeLicense(id=1, org_id=org, user_id=10, license_name="PMP")
    contact = EmployeeEmergencyContact(id=1, org_id=org, user_id=10, contact_name="Jane")

    db = _make_db({
        EmployeeProfile: {"first": profile},
        EmployeeEducation: {"all": [education]},
        EmployeeExperience: {"all": [experience]},
        EmployeeAward: {"all": [award]},
        EmployeeLicense: {"all": [license_]},
        EmployeeEmergencyContact: {"all": [contact]},
    })

    with patch("app.services.audit_service.audit_service.record"):
        dossier = employee_profile_service.profile_dossier(db, org, 10)
        assert dossier["profile"]["nationality"] == "Indian"
        assert len(dossier["education"]) == 1
        assert len(dossier["experience"]) == 1
        assert len(dossier["awards"]) == 1
        assert len(dossier["licenses"]) == 1
        assert len(dossier["emergency_contacts"]) == 1


# =============================================================================
#  PERFORMANCE & GOAL SERVICES
# =============================================================================

def test_performance_cycle_creation_and_ratings_dashboard():
    """Cycle creation emits PerformanceCycleCreated; ratings dashboard aggregates
    final ratings distribution."""
    org = _org_id()
    cycle = MagicMock(id=1, organization_id=org, name="H1 2026", created_by_user_id=5)
    ratings = [
        PerformanceRating(id=1, organization_id=org, user_id=10, final_rating=4.8),
        PerformanceRating(id=2, organization_id=org, user_id=11, final_rating=3.2),
        PerformanceRating(id=3, organization_id=org, user_id=12, final_rating=2.4),
    ]

    with patch("app.services.event_bus.event_bus.publish") as mock_event:
        created = performance_service.create_cycle(
            db=MagicMock(), org_id=org,
            data={"name": "H1 2026", "cycle_type": "half_year",
                  "start_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
                  "end_date": datetime(2026, 6, 30, tzinfo=timezone.utc)},
            created_by=5,
        )
        assert created.name == "H1 2026"
        mock_event.assert_called_with("PerformanceCycleCreated", str(org), ANY, actor_id=5)

    # ratings dashboard
    db = MagicMock()
    db.query.side_effect = lambda model: (_ for _ in ()).throw(
        AssertionError("unexpected query")) if False else MagicMock()
    # Configure via direct mock chain: db.query(PerformanceRating).filter().all()
    q_mock = MagicMock()
    q_mock.filter.return_value.all.return_value = ratings
    db.query.return_value = q_mock
    dash = performance_service.ratings_dashboard(db, org)
    assert dash["total_rated"] == 3
    assert dash["avg_rating"] == round((4.8 + 3.2 + 2.4) / 3, 2)
    assert dash["distribution"]["exceeds"] == 1
    assert dash["distribution"]["meets"] == 1
    assert dash["distribution"]["below"] == 1


def test_goal_creation_logprogress_and_completion():
    """Goal creation emits GoalCreated; reaching 100% emits GoalCompleted."""
    org = _org_id()
    goal = Goal(id=1, organization_id=org, user_id=10, title="Ship OKR",
                target_value=100.0, current_value=0.0, completion_pct=0.0,
                status="active")

    with patch("app.services.event_bus.event_bus.publish") as mock_event:
        created = goal_service.create_goal(
            db=MagicMock(), org_id=org, user_id=10,
            data={"title": "Ship OKR", "goal_type": "individual",
                  "goal_framework": "okr", "target_value": 100.0},
        )
        assert created.title == "Ship OKR"
        mock_event.assert_called_with("GoalCreated", str(org), ANY, actor_id=10)

    db = _make_db({Goal: {"first": goal}})
    with patch("app.services.event_bus.event_bus.publish") as mock_event:
        completed = goal_service.log_progress(
            db, org, goal.id, 10, value=100.0, note="Done", actor_id=5)
        assert completed.completion_pct == 100.0
        assert completed.status == "completed"
        mock_event.assert_any_call("GoalCompleted", str(org), ANY, actor_id=5)


# =============================================================================
#  REVIEW SERVICE
# =============================================================================

def test_review_creation_submission_events_and_notification():
    """Creating a review emits PerformanceReviewStarted; submitting emits
    PerformanceReviewCompleted and notifies the reviewee."""
    org = _org_id()
    review = PerformanceReview(
        id=1, organization_id=org, cycle_id=1, reviewee_user_id=10,
        reviewer_user_id=5, review_type="manager", status="pending",
    )

    with patch("app.services.event_bus.event_bus.publish") as mock_event:
        created = review_service.create_review(
            db=MagicMock(), org_id=org,
            data={"cycle_id": 1, "reviewee_user_id": 10, "reviewer_user_id": 5,
                  "review_type": "manager"},
            actor_id=5,
        )
        assert created.review_type == "manager"
        mock_event.assert_called_with("PerformanceReviewStarted", str(org), ANY, actor_id=5)

    db = _make_db({PerformanceReview: {"first": review}})
    with patch("app.services.event_bus.event_bus.publish") as mock_event, \
         patch("app.services.notification_service.notification_service.send") as mock_notif:
        submitted = review_service.submit_review(
            db, org, review.id,
            {"overall_score": 4.5, "strengths": "Strong delivery", "comments": "Great"},
            actor_id=5,
        )
        assert submitted.status == "submitted"
        assert submitted.overall_score == 4.5
        mock_event.assert_called_with("PerformanceReviewCompleted", str(org), ANY, actor_id=5)
        mock_notif.assert_called_with(
            user_id=10, organization_id=str(org), title=ANY, message=ANY,
            source_module="hcm", source_event="PerformanceReviewCompleted",
            source_id=str(review.id),
        )


# =============================================================================
#  LEARNING, COURSE & ASSESSMENT SERVICES
# =============================================================================

def test_course_and_learning_enrollment_completion():
    """Course creation persists to the catalog; enrollment emits CourseAssigned
    and completion emits CourseCompleted with score."""
    org = _org_id()

    with patch("app.services.audit_service.audit_service.record"):
        course = course_service.create_course(
            db=MagicMock(), org_id=org,
            data={"title": "AI Fundamentals", "course_type": "online",
                  "duration_hours": 4.0, "pass_percentage": 70.0},
        )
        assert course.title == "AI Fundamentals"

    with patch("app.services.event_bus.event_bus.publish") as mock_event:
        enrollment = learning_service.enroll(
            db=MagicMock(), org_id=org, course_id=1, user_id=10,
            assigned_by=5, actor_id=5,
        )
        assert enrollment.course_id == 1
        assert enrollment.user_id == 10
        mock_event.assert_called_with("CourseAssigned", str(org), ANY, actor_id=5)

    enrollment_row = CourseEnrollment(id=1, organization_id=org, course_id=1,
                                      user_id=10, status="enrolled", progress_pct=10.0)
    db = _make_db({CourseEnrollment: {"first": enrollment_row}})
    with patch("app.services.event_bus.event_bus.publish") as mock_event:
        completed = learning_service.mark_completed(
            db, org, enrollment_row.id, score=92.0, actor_id=10)
        assert completed.status == "completed"
        assert completed.progress_pct == 100.0
        assert completed.score == 92.0
        mock_event.assert_called_with("CourseCompleted", str(org), ANY, actor_id=10)


def test_assessment_attempt_pass_emits_event():
    """A quiz attempt scoring above the pass threshold is marked passed and
    emits AssessmentPassed."""
    org = _org_id()
    quiz = AssessmentQuiz(id=1, course_id=1, title="Quiz", pass_score=70.0)

    db = _make_db({AssessmentQuiz: {"first": quiz}})
    with patch("app.services.event_bus.event_bus.publish") as mock_event:
        attempt = assessment_service.submit_attempt(
            db, org, quiz.id, 10, score=82.0, max_score=100.0, enrollment_id=1,
            response_data={"q1": "A"},
        )
        assert attempt.passed is True
        assert attempt.score == 82.0
        mock_event.assert_called_with("AssessmentPassed", str(org), ANY, actor_id=10)


# =============================================================================
#  SKILL & COMPETENCY SERVICES
# =============================================================================

def test_skill_verification_and_matrix():
    """Adding a skill with a verifier emits SkillVerified; the org skill matrix
    computes coverage per user."""
    org = _org_id()
    org_users = [User(id=10, org_id=org), User(id=11, org_id=org),
                 User(id=12, org_id=org), User(id=13, org_id=org)]

    # New skill record (no existing row) → db.query(EmployeeSkill).filter().first() returns None
    db = _make_db({EmployeeSkill: {"first": None}})
    with patch("app.services.event_bus.event_bus.publish") as mock_event:
        record = skill_service.add_or_update_skill(
            db, org, 10, skill_id=1, proficiency_level="advanced",
            source="course_completion", verified_by=5, actor_id=5,
        )
        assert record.user_id == 10
        assert record.verified_by_user_id == 5
        assert record.verified_at is not None
        mock_event.assert_called_with("SkillVerified", str(org), ANY, actor_id=5)

    # Skill matrix: two records for one user, both verified; org has 4 users
    records = [
        EmployeeSkill(id=1, org_id=org, user_id=10, skill_id=1,
                      proficiency_level="expert", verified_at=datetime.now(timezone.utc)),
        EmployeeSkill(id=2, org_id=org, user_id=10, skill_id=2,
                      proficiency_level="intermediate", verified_at=datetime.now(timezone.utc)),
    ]
    db = MagicMock()

    def query_side(model):
        m = MagicMock()
        if model == EmployeeSkill:
            m.filter.return_value.order_by.return_value.all.return_value = records
        elif model == User:
            m.filter.return_value.count.return_value = 4
        return m

    db.query.side_effect = query_side
    matrix = skill_service.skill_matrix(db, org)
    assert matrix["total_skills_recorded"] == 2
    assert matrix["users_with_skills"] == 1
    assert matrix["verified_count"] == 2
    assert matrix["coverage"] == 25.0  # 1/4


def test_competency_gap_analysis():
    """Competency gap combines nine-box placement and skill coverage."""
    org = _org_id()
    nine_box = NineBoxGrid(id=1, organization_id=org, user_id=10,
                           performance_rating=2, potential_rating=3,
                           box_category="High Potential")
    skills = [
        EmployeeSkill(id=1, org_id=org, user_id=10, skill_id=1, proficiency_level="beginner"),
        EmployeeSkill(id=2, org_id=org, user_id=10, skill_id=2, proficiency_level="intermediate"),
    ]
    db = _make_db({NineBoxGrid: {"first": nine_box}, EmployeeSkill: {"all": skills}})
    gap = competency_service.competency_gap(db, org, 10)
    assert gap["user_id"] == 10
    assert gap["nine_box"]["box_category"] == "High Potential"
    # coverage = (1 + 2) / (2 * 4) = 37.5 → HIGH gap
    assert gap["gap_level"] == "HIGH"
    assert "training" in gap["recommendation"].lower()


# =============================================================================
#  CERTIFICATION SERVICE
# =============================================================================

def test_certificate_issuance_event_and_notification():
    """Issuing a certificate generates a unique number and emits
    CertificationIssued with a user notification."""
    org = _org_id()
    with patch("app.services.event_bus.event_bus.publish") as mock_event, \
         patch("app.services.notification_service.notification_service.send") as mock_notif:
        cert = certification_service.issue_certificate(
            db=MagicMock(), org_id=org, user_id=10, course_id=1,
            enrollment_id=1, certificate_url="https://files/", actor_id=5,
        )
        assert cert.certificate_number.startswith("CERT-")
        assert cert.user_id == 10
        mock_event.assert_called_with("CertificationIssued", str(org), ANY, actor_id=5)
        mock_notif.assert_called_once()


# =============================================================================
#  CAREER SERVICE
# =============================================================================

def test_career_idp_publishes_plan_event():
    """Creating an Individual Development Plan emits CareerPlanUpdated."""
    org = _org_id()
    idp = MagicMock(id=1, organization_id=org, user_id=10)
    db = _make_db({IndividualDevelopmentPlan: {"first": idp}})
    with patch("app.services.event_bus.event_bus.publish") as mock_event:
        created = career_service.create_idp(
            db=MagicMock(), org_id=org, user_id=10,
            data={"target_position_title": "Principal Engineer", "status": "in_progress"},
            actor_id=5,
        )
        assert created.target_position_title == "Principal Engineer"
        mock_event.assert_called_with("CareerPlanUpdated", str(org), ANY, actor_id=5)


# =============================================================================
#  SUCCESSION SERVICE
# =============================================================================

def test_succession_nomination_and_nine_box():
    """Nominating a successor emits SuccessorAssigned; nine-box evaluation maps
    performance x potential to a box category."""
    org = _org_id()

    with patch("app.services.event_bus.event_bus.publish") as mock_event:
        candidate = succession_service.nominate_candidate(
            db=MagicMock(), org_id=org, plan_id=1, candidate_user_id=10,
            readiness_rating="ready_now", nomination_notes="Executive material",
            actor_id=5,
        )
        assert candidate.succession_plan_id == 1
        assert candidate.readiness_rating == "ready_now"
        mock_event.assert_called_with("SuccessorAssigned", str(org), ANY, actor_id=5)

    with patch("app.services.event_bus.event_bus.publish") as mock_event:
        grid = succession_service.evaluate_nine_box(
            db=MagicMock(), org_id=org, user_id=10,
            performance_rating=3, potential_rating=3,
            evaluated_by=5,
        )
        assert grid.box_category == "Star"
        mock_event.assert_any_call("NineBoxEvaluated", str(org), ANY, actor_id=5)


# =============================================================================
#  DOCUMENT SERVICE
# =============================================================================

def test_document_vault_upload_and_signing():
    """Employee documents upload into the vault; signing flips the flag and
    writes an audit (warning severity)."""
    org = _org_id()

    doc = document_service.upload_document(
        db=MagicMock(), org_id=org, user_id=10,
        data={"title": "Offer Letter", "document_type": "offer_letter",
              "file_id": str(uuid.uuid4()), "access_level": "confidential"},
    )
    assert doc.title == "Offer Letter"
    assert doc.is_signed is False

    stored = EmployeeDocument(id=1, org_id=org, user_id=10, title="Offer Letter",
                              document_type="offer_letter")
    db = _make_db({EmployeeDocument: {"first": stored}})
    with patch("app.services.audit_service.audit_service.record") as mock_audit:
        signed = document_service.sign_document(db, org, stored.id, actor_id=10)
        assert signed.is_signed is True
        assert signed.signed_at is not None
        mock_audit.assert_called_with(
            actor_user_id=10, organization_id=str(org),
            module="hcm_documents", action="sign",
            entity_type="employee_document", entity_id="1",
            summary=ANY, severity="warning",
        )


# =============================================================================
#  TALENT SERVICE
# =============================================================================

def test_talent_pool_member_and_dashboard():
    """Creating a talent pool, adding members, and computing readiness counts
    for the talent dashboard."""
    org = _org_id()
    pool_row = TalentPool(id=1, org_id=org, name="Future Leaders", pool_type="future_leaders",
                          status="active")

    with patch("app.services.event_bus.event_bus.publish") as mock_event:
        pool = talent_service.create_pool(
            db=MagicMock(), org_id=org,
            data={"name": "Future Leaders", "pool_type": "future_leaders"},
        )
        assert pool.name == "Future Leaders"
        member = talent_service.add_member(
            db=MagicMock(), org_id=org, pool_id=1, user_id=10,
            readiness_level="ready_now", nomination_reason="High performer",
            actor_id=5,
        )
        assert member.pool_id == 1
        mock_event.assert_called_with("TalentPoolMemberAdded", str(org), ANY, actor_id=5)

    members = [
        TalentPoolMember(id=1, pool_id=1, user_id=10, readiness_level="ready_now"),
        TalentPoolMember(id=2, pool_id=1, user_id=11, readiness_level="ready_1_year"),
        TalentPoolMember(id=3, pool_id=1, user_id=12, readiness_level="ready_now"),
    ]
    db = MagicMock()

    def query_side(model):
        m = MagicMock()
        if model == TalentPool:
            m.filter.return_value.order_by.return_value.all.return_value = [pool_row]
        elif model == TalentPoolMember:
            m.join.return_value.filter.return_value.all.return_value = members
        return m

    db.query.side_effect = query_side
    dash = talent_service.talent_dashboard(db, org)
    assert dash["total_pools"] == 1
    assert dash["total_members"] == 3
    assert dash["readiness"]["ready_now"] == 2
    assert dash["readiness"]["ready_1_year"] == 1


# =============================================================================
#  HCM EXECUTIVE DASHBOARD
# =============================================================================

def test_hcm_executive_dashboard_aggregates_domains():
    """The unified HCM dashboard aggregates KPIs across all HCM domains."""
    org = _org_id()
    db = MagicMock()
    counts = {}

    def cfg(model, value):
        m = MagicMock()
        m.filter.return_value.count.return_value = value
        m.join.return_value.filter.return_value.count.return_value = value
        counts[model] = m
        return m

    # Every model queried by hcm_dashboard
    cfg(User, 10)
    cfg(EmployeeProfile, 8)
    cfg(Goal, 5)          # active goals
    cfg(Goal, 7)          # completed goals (second query returns same mock → 5)
    cfg(PerformanceReview, 3)
    cfg(PerformanceReview, 4)
    cfg(CourseEnrollment, 12)
    cfg(Certificate, 4)
    cfg(EmployeeSkill, 20)
    cfg(KeyPosition, 6)
    cfg(SuccessorCandidate, 4)
    cfg(EmployeeDocument, 9)
    cfg(TalentPool, 2)

    def side(model):
        return counts[model]

    db.query.side_effect = side

    with patch("app.services.audit_service.audit_service.record"):
        dash = hcm_dashboard(db, org)
        assert dash["employees"] == 10
        assert dash["profile_completion_pct"] == 80.0
        assert dash["goals"]["active"] == 5
        assert dash["reviews"]["pending"] == 3
        assert dash["learning"]["enrollments"] == 12
        assert dash["succession"]["key_positions"] == 6
        assert dash["documents"] == 9
        assert dash["talent_pools"] == 2

