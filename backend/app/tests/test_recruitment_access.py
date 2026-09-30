"""
Recruitment module: access policy and tenant isolation.

Two things are asserted here, and they pull in opposite directions on purpose.

1. The module is open to every authenticated user in the tenant. That is a
   deliberate decision, not an oversight, so these tests fail if someone
   re-introduces a role gate and locks out an ordinary employee.

2. Tenant isolation is absolute, including for ids the caller supplies. The
   module has no role layer, so the org check is the only boundary there is.
   Two endpoints previously missed it:
     * `POST /applications` accepted a foreign `job_posting_id`/`candidate_id`;
     * `POST /interviews` looked the application up by id alone, so scheduling
       an interview mutated *another tenant's* application stage.
   Both are covered by tests that would have caught the original code.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from main import app
from app.api import deps
from app.core.security import get_password_hash
from app.db.models.all_models import (
    Candidate,
    Department,
    InterviewSchedule,
    JobApplication,
    JobPosting,
    Organization,
    OrganizationSubscription,
    Role,
    SubscriptionPlan,
    User,
    UserSession,
)


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #

def _mk_org(db, name: str) -> Organization:
    org = Organization(name=name, legal_id=f"REC-{uuid.uuid4().hex[:8].upper()}")
    db.add(org)
    db.commit()
    db.refresh(org)
    plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.code == "enterprise")
        .first()
    )
    assert plan, "the enterprise plan must be seeded"
    db.add(OrganizationSubscription(
        organization_id=org.id, subscription_plan_id=plan.id,
        status="active", billing_cycle="yearly"))
    dept = Department(org_id=org.id, name="Recruiting")
    db.add(dept)
    db.commit()
    db.refresh(dept)
    org.dept = dept
    return org


def _mk_user(db, org: Organization, role_name: str, tag: str) -> User:
    role = db.query(Role).filter(Role.name == role_name).first()
    assert role, f"missing seeded role {role_name}"
    slug = f"rec_{tag}_{uuid.uuid4().hex[:6]}"
    user = User(
        email=f"{slug}@example.com", username=slug, employee_id=slug.upper(),
        full_name=f"Recruit {tag}", org_id=org.id, role_id=role.id,
        is_active=1, is_deleted=0,
        hashed_password=get_password_hash("Password123!"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _mk_job(db, org: Organization, poster: User, title="Open Role") -> JobPosting:
    job = JobPosting(
        organization_id=org.id, title=title, department_id=org.dept.id,
        description="Work here.", location="Remote", employment_type="Full-time",
        status="open", posted_by_user_id=poster.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _mk_candidate(db, org: Organization, email="cand@example.com") -> Candidate:
    cand = Candidate(
        organization_id=org.id, full_name="Casey Candidate", email=email,
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    return cand


def _cleanup(db, org_ids):
    uid_list = [r[0] for r in
                db.query(User.id).filter(User.org_id.in_(org_ids)).all()]
    for model in (InterviewSchedule, JobApplication):
        db.query(model).filter(model.organization_id.in_(org_ids)).delete(
            synchronize_session=False)
    db.query(Candidate).filter(Candidate.organization_id.in_(org_ids)).delete(
        synchronize_session=False)
    db.query(JobPosting).filter(JobPosting.organization_id.in_(org_ids)).delete(
        synchronize_session=False)
    if uid_list:
        db.query(UserSession).filter(UserSession.user_id.in_(uid_list)).delete(
            synchronize_session=False)
    db.query(Department).filter(Department.org_id.in_(org_ids)).delete(
        synchronize_session=False)
    db.query(User).filter(User.org_id.in_(org_ids)).delete(
        synchronize_session=False)
    db.query(OrganizationSubscription).filter(
        OrganizationSubscription.organization_id.in_(org_ids)).delete(
            synchronize_session=False)
    db.query(Organization).filter(Organization.id.in_(org_ids)).delete(
        synchronize_session=False)
    db.commit()


@pytest.fixture()
def tenant_a(db):
    org = _mk_org(db, "Acme Recruiting Co")
    yield {"org": org,
           "hr": _mk_user(db, org, "OrgHR", "hra"),
           "emp": _mk_user(db, org, "OrgEmployee", "empa")}
    _cleanup(db, [org.id])


@pytest.fixture()
def tenant_b(db):
    org = _mk_org(db, "Globex Recruiting Co")
    yield {"org": org,
           "hr": _mk_user(db, org, "OrgHR", "hrb"),
           "emp": _mk_user(db, org, "OrgEmployee", "empb")}
    _cleanup(db, [org.id])


def _as(user: User):
    app.dependency_overrides[deps.get_current_active_user] = lambda: user


@pytest.fixture(autouse=True)
def _no_leftover_overrides():
    yield
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# 1. open access -- deliberate
# --------------------------------------------------------------------------- #

class TestRecruitmentIsOpenToEveryUser:
    """No role gate. If one of these starts returning 403, the module has been
    re-scoped and the decision recorded in the router docstring was undone."""

    def test_an_employee_can_post_a_vacancy(self, client, db, tenant_a):
        _as(tenant_a["emp"])
        r = client.post("/api/v1/recruitment/jobs", json={
            "title": "Backend Engineer", "description": "Build things.",
        })
        assert r.status_code == 201, r.text[:200]
        assert r.json()["status"] == "open"

    def test_an_employee_can_register_and_read_candidates(self, client, db, tenant_a):
        _as(tenant_a["emp"])
        created = client.post("/api/v1/recruitment/candidates", json={
            "full_name": "Robin Applicant", "email": "robin@example.com",
        })
        assert created.status_code == 201
        rows = client.get("/api/v1/recruitment/candidates").json()
        assert [c["email"] for c in rows] == ["robin@example.com"]

    def test_an_employee_can_move_a_candidate_through_the_pipeline(
        self, client, db, tenant_a
    ):
        job = _mk_job(db, tenant_a["org"], tenant_a["hr"])
        cand = _mk_candidate(db, tenant_a["org"])
        _as(tenant_a["emp"])
        app_row = client.post("/api/v1/recruitment/applications", json={
            "job_posting_id": job.id, "candidate_id": cand.id}).json()
        moved = client.patch(
            f"/api/v1/recruitment/applications/{app_row['id']}/stage",
            json={"stage": "screening", "rating": 4})
        assert moved.status_code == 200, moved.text[:200]
        assert moved.json()["stage"] == "screening"

    def test_an_employee_can_schedule_an_interview_for_themselves(
        self, client, db, tenant_a
    ):
        job = _mk_job(db, tenant_a["org"], tenant_a["hr"])
        cand = _mk_candidate(db, tenant_a["org"])
        _as(tenant_a["emp"])
        app_row = client.post("/api/v1/recruitment/applications", json={
            "job_posting_id": job.id, "candidate_id": cand.id}).json()
        when = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        r = client.post("/api/v1/recruitment/interviews", json={
            "application_id": app_row["id"], "scheduled_at": when,
        })
        assert r.status_code == 201, r.text[:200]
        assert r.json()["status"] == "scheduled"

    def test_anonymous_is_still_refused(self, client, db, tenant_a):
        app.dependency_overrides.clear()
        assert client.get("/api/v1/recruitment/candidates").status_code in (401, 403)
        assert client.get("/api/v1/recruitment/jobs").status_code in (401, 403)

    def test_a_tenant_without_the_feature_is_refused(self, client, db, tenant_a):
        """Open to all users, but still only for a tenant that bought it."""
        plan = (db.query(SubscriptionPlan)
                .filter(SubscriptionPlan.code == "starter").first())
        sub = db.query(OrganizationSubscription).filter(
            OrganizationSubscription.organization_id == tenant_a["org"].id).first()
        sub.subscription_plan_id = plan.id
        db.commit()
        _as(tenant_a["emp"])
        r = client.get("/api/v1/recruitment/jobs")
        assert r.status_code in (402, 403), r.status_code


# --------------------------------------------------------------------------- #
# 2. tenant isolation -- non-negotiable
# --------------------------------------------------------------------------- #

class TestRecruitmentTenantIsolation:
    def test_lists_never_include_another_tenants_rows(self, client, db, tenant_a, tenant_b):
        job_b = _mk_job(db, tenant_b["org"], tenant_b["hr"], "Globex Only")
        cand_b = _mk_candidate(db, tenant_b["org"], "theirs@example.com")
        db.add(JobApplication(organization_id=tenant_b["org"].id,
                              job_posting_id=job_b.id, candidate_id=cand_b.id))
        db.commit()

        _as(tenant_a["emp"])
        assert client.get("/api/v1/recruitment/jobs").json() == []
        assert client.get("/api/v1/recruitment/candidates").json() == []
        assert client.get("/api/v1/recruitment/applications").json() == []
        assert client.get("/api/v1/recruitment/positions").json() == []

    def test_cannot_file_an_application_against_another_tenants_job(
        self, client, db, tenant_a, tenant_b
    ):
        """`job_posting_id` comes from the caller and used to be trusted.

        The row would have carried the caller's own org id while pointing at
        another tenant's posting, so it would have shown up in that tenant's
        pipeline while belonging to neither.
        """
        job_b = _mk_job(db, tenant_b["org"], tenant_b["hr"])
        cand_a = _mk_candidate(db, tenant_a["org"], "mine@example.com")
        _as(tenant_a["emp"])
        r = client.post("/api/v1/recruitment/applications", json={
            "job_posting_id": job_b.id, "candidate_id": cand_a.id})
        assert r.status_code == 404, f"got {r.status_code}, expected 404"
        assert db.query(JobApplication).filter(
            JobApplication.organization_id == tenant_a["org"].id).count() == 0

    def test_cannot_file_an_application_with_another_tenants_candidate(
        self, client, db, tenant_a, tenant_b
    ):
        job_a = _mk_job(db, tenant_a["org"], tenant_a["hr"])
        cand_b = _mk_candidate(db, tenant_b["org"], "theirs@example.com")
        _as(tenant_a["emp"])
        r = client.post("/api/v1/recruitment/applications", json={
            "job_posting_id": job_a.id, "candidate_id": cand_b.id})
        assert r.status_code == 404, f"got {r.status_code}, expected 404"

    def test_scheduling_an_interview_cannot_reach_into_another_tenant(
        self, client, db, tenant_a, tenant_b
    ):
        """The worst of the two: the lookup ignored org entirely, so this
        silently rewrote the other tenant's pipeline."""
        job_b = _mk_job(db, tenant_b["org"], tenant_b["hr"])
        cand_b = _mk_candidate(db, tenant_b["org"], "theirs@example.com")
        foreign = JobApplication(
            organization_id=tenant_b["org"].id, job_posting_id=job_b.id,
            candidate_id=cand_b.id, stage="screening")
        db.add(foreign)
        db.commit()
        db.refresh(foreign)

        _as(tenant_a["emp"])
        when = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        r = client.post("/api/v1/recruitment/interviews", json={
            "application_id": foreign.id, "scheduled_at": when})
        assert r.status_code == 404, f"got {r.status_code}, expected 404"

        db.expire_all()
        assert db.query(JobApplication).get(foreign.id).stage == "screening", (
            "another tenant's application stage was overwritten"
        )
        assert db.query(InterviewSchedule).filter(
            InterviewSchedule.organization_id == tenant_b["org"].id).count() == 0

    def test_cannot_advance_another_tenants_application(self, client, db, tenant_a, tenant_b):
        job_b = _mk_job(db, tenant_b["org"], tenant_b["hr"])
        cand_b = _mk_candidate(db, tenant_b["org"], "theirs@example.com")
        foreign = JobApplication(
            organization_id=tenant_b["org"].id, job_posting_id=job_b.id,
            candidate_id=cand_b.id, stage="screening")
        db.add(foreign)
        db.commit()
        db.refresh(foreign)

        _as(tenant_a["emp"])
        r = client.patch(
            f"/api/v1/recruitment/applications/{foreign.id}/stage",
            json={"stage": "hired"})
        assert r.status_code == 404, f"got {r.status_code}, expected 404"
        db.expire_all()
        assert db.query(JobApplication).get(foreign.id).stage == "screening"

    def test_an_employee_may_not_appoint_someone_else_as_interviewer(
        self, client, db, tenant_a
    ):
        """The one floor kept on an otherwise open module: naming a third party
        to sit in on a hiring decision acts on someone other than the caller."""
        job = _mk_job(db, tenant_a["org"], tenant_a["hr"])
        cand = _mk_candidate(db, tenant_a["org"])
        _as(tenant_a["emp"])
        app_row = client.post("/api/v1/recruitment/applications", json={
            "job_posting_id": job.id, "candidate_id": cand.id}).json()
        when = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        r = client.post("/api/v1/recruitment/interviews", json={
            "application_id": app_row["id"], "scheduled_at": when,
            "interviewer_user_id": tenant_a["hr"].id})
        assert r.status_code == 403, f"got {r.status_code}, expected 403"

        _as(tenant_a["hr"])
        ok = client.post("/api/v1/recruitment/interviews", json={
            "application_id": app_row["id"], "scheduled_at": when,
            "interviewer_user_id": tenant_a["hr"].id})
        assert ok.status_code == 201, ok.text[:200]


# --------------------------------------------------------------------------- #
# 3. pipeline integrity
# --------------------------------------------------------------------------- #

class TestPipelineIntegrity:
    def _application(self, client, db, tenant):
        job = _mk_job(db, tenant["org"], tenant["hr"])
        cand = _mk_candidate(db, tenant["org"])
        _as(tenant["emp"])
        return client.post("/api/v1/recruitment/applications", json={
            "job_posting_id": job.id, "candidate_id": cand.id}).json()

    def test_a_terminal_stage_cannot_be_reopened(self, client, db, tenant_a):
        row = self._application(client, db, tenant_a)
        client.patch(f"/api/v1/recruitment/applications/{row['id']}/stage",
                     json={"stage": "hired"})
        reopen = client.patch(f"/api/v1/recruitment/applications/{row['id']}/stage",
                              json={"stage": "screening"})
        assert reopen.status_code == 409, f"got {reopen.status_code}"
        db.expire_all()
        assert db.query(JobApplication).get(row["id"]).stage == "hired"

    def test_a_rejected_candidate_stays_rejected_when_interviewed(
        self, client, db, tenant_a
    ):
        row = self._application(client, db, tenant_a)
        client.patch(f"/api/v1/recruitment/applications/{row['id']}/stage",
                     json={"stage": "rejected"})
        when = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
        r = client.post("/api/v1/recruitment/interviews", json={
            "application_id": row["id"], "scheduled_at": when})
        assert r.status_code == 201
        db.expire_all()
        assert db.query(JobApplication).get(row["id"]).stage == "rejected", (
            "scheduling an interview reopened a rejected candidate"
        )

    def test_scheduling_advances_an_open_candidate_to_interview(
        self, client, db, tenant_a
    ):
        row = self._application(client, db, tenant_a)
        when = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        client.post("/api/v1/recruitment/interviews", json={
            "application_id": row["id"], "scheduled_at": when})
        db.expire_all()
        assert db.query(JobApplication).get(row["id"]).stage == "interview"

    def test_an_unknown_stage_is_refused(self, client, db, tenant_a):
        row = self._application(client, db, tenant_a)
        r = client.patch(f"/api/v1/recruitment/applications/{row['id']}/stage",
                         json={"stage": "interveiw"})
        assert r.status_code == 422

    def test_a_missing_field_is_422_not_500(self, client, db, tenant_a):
        """The handlers used to take a bare `dict`, so a missing key raised
        KeyError and surfaced as a 500."""
        _as(tenant_a["emp"])
        assert client.post("/api/v1/recruitment/jobs",
                           json={"description": "no title"}).status_code == 422
        assert client.post("/api/v1/recruitment/candidates",
                           json={"full_name": "No Email"}).status_code == 422
        assert client.post("/api/v1/recruitment/candidates", json={
            "full_name": "Bad", "email": "not-an-email"}).status_code == 422

    def test_rating_is_range_checked(self, client, db, tenant_a):
        row = self._application(client, db, tenant_a)
        r = client.patch(f"/api/v1/recruitment/applications/{row['id']}/stage",
                         json={"stage": "screening", "rating": 99})
        assert r.status_code == 422


# --------------------------------------------------------------------------- #
# 4. truthful reporting
# --------------------------------------------------------------------------- #

class TestPositionsListing:
    def test_applicant_counts_are_real(self, client, db, tenant_a):
        """Was hardcoded to 0, so the board always looked unstaffed."""
        busy = _mk_job(db, tenant_a["org"], tenant_a["hr"], "Busy Role")
        quiet = _mk_job(db, tenant_a["org"], tenant_a["hr"], "Quiet Role")
        for _ in range(3):
            db.add(JobApplication(
                organization_id=tenant_a["org"].id,
                job_posting_id=busy.id, candidate_id=_mk_candidate(
                    db, tenant_a["org"], f"c{uuid.uuid4().hex[:8]}@example.com").id))
        db.commit()

        _as(tenant_a["emp"])
        rows = {r["title"]: r for r in client.get(
            "/api/v1/recruitment/positions").json()}
        assert rows["Busy Role"]["applicants_count"] == 3
        assert rows["Quiet Role"]["applicants_count"] == 0

    def test_another_tenants_applicants_are_not_counted(
        self, client, db, tenant_a, tenant_b
    ):
        job_a = _mk_job(db, tenant_a["org"], tenant_a["hr"], "Acme Role")
        job_b = _mk_job(db, tenant_b["org"], tenant_b["hr"], "Globex Role")
        db.add(JobApplication(
            organization_id=tenant_b["org"].id, job_posting_id=job_b.id,
            candidate_id=_mk_candidate(db, tenant_b["org"],
                                       "theirs@example.com").id))
        db.commit()

        _as(tenant_a["emp"])
        rows = {r["title"]: r for r in client.get(
            "/api/v1/recruitment/positions").json()}
        assert rows["Acme Role"]["applicants_count"] == 0

    def test_status_filter_works(self, client, db, tenant_a):
        _mk_job(db, tenant_a["org"], tenant_a["hr"], "Open Role")
        closed = _mk_job(db, tenant_a["org"], tenant_a["hr"], "Closed Role")
        closed.status = "closed"
        db.commit()
        _as(tenant_a["emp"])
        rows = client.get("/api/v1/recruitment/positions?status=open").json()
        assert [r["title"] for r in rows] == ["Open Role"]
