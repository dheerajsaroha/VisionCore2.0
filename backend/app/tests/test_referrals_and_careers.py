"""
Employee referral programme and the public careers page.

The two are tested together because they meet: an employee raises a referral
and hands the candidate a code, which the candidate then quotes on the public
careers page. Tested apart, they would miss exactly the bug that mattered most
-- a valid code that silently failed to attach on first use.

Covers, among other things:
  * drafts and closed vacancies are invisible publicly;
  * a job id from one tenant cannot be read through another tenant's slug;
  * referral codes are single-use and cannot cross tenants;
  * an unknown code is ignored rather than reported, so the public form is not
    a code oracle;
  * status transitions are constrained, so a referral cannot jump straight to
    `hired` and have a reward approved on the strength of one request.
"""
from __future__ import annotations

import uuid
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from app.api import deps
from app.core.security import get_password_hash
from app.db.models.all_models import (
    Candidate,
    Department,
    JobApplication,
    JobPosting,
    Organization,
    OrganizationSubscription,
    Referral,
    Role,
    SubscriptionPlan,
    User,
    UserSession,
)


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #

def _mk_org(db: Session, name: str) -> Organization:
    org = Organization(name=name, legal_id=f"CAR-{uuid.uuid4().hex[:8].upper()}")
    db.add(org)
    db.commit()
    db.refresh(org)
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "enterprise").first()
    db.add(OrganizationSubscription(
        organization_id=org.id, subscription_plan_id=plan.id,
        status="active", billing_cycle="yearly"))
    dept = Department(org_id=org.id, name="Engineering")
    db.add(dept)
    db.commit()
    db.refresh(dept)
    org.dept = dept
    return org


def _mk_user(db: Session, org: Organization, role_name: str, tag: str) -> User:
    role = db.query(Role).filter(Role.name == role_name).first()
    assert role, f"missing role {role_name}"
    slug = f"car_{tag}_{uuid.uuid4().hex[:6]}"
    user = User(
        email=f"{slug}@example.com", username=slug, employee_id=slug.upper(),
        full_name=f"Careers {tag}", org_id=org.id, role_id=role.id,
        is_active=1, is_deleted=0, hashed_password=get_password_hash("Password123!"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _mk_job(db: Session, org: Organization, title: str, status: str,
            poster: User, dept_id: Optional[int] = None) -> JobPosting:
    job = JobPosting(
        organization_id=org.id, title=title,
        department_id=dept_id if dept_id is not None else org.dept.id,
        description=f"{title} description.", requirements="Python, SQL",
        location="Remote", employment_type="Full-time", status=status,
        posted_by_user_id=poster.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@pytest.fixture()
def tenant_a(db):
    org = _mk_org(db, "Acme Careers Co")
    yield {
        "org": org,
        "hr": _mk_user(db, org, "OrgHR", "hra"),
        "emp": _mk_user(db, org, "OrgEmployee", "empa"),
    }
    _cleanup(db, [org.id])


@pytest.fixture()
def tenant_b(db):
    org = _mk_org(db, "Globex Careers Co")
    yield {
        "org": org,
        "hr": _mk_user(db, org, "OrgHR", "hrb"),
        "emp": _mk_user(db, org, "OrgEmployee", "empb"),
    }
    _cleanup(db, [org.id])


def _cleanup(db: Session, org_ids):
    uid_list = [row[0] for row in
                db.query(User.id).filter(User.org_id.in_(org_ids)).all()]
    for model in (JobApplication, Referral):
        db.query(model).filter(model.organization_id.in_(org_ids)).delete(
            synchronize_session=False)
    db.query(Candidate).filter(Candidate.organization_id.in_(org_ids)).delete(
        synchronize_session=False)
    if uid_list:
        db.query(UserSession).filter(UserSession.user_id.in_(uid_list)).delete(
            synchronize_session=False)
    db.query(JobPosting).filter(JobPosting.organization_id.in_(org_ids)).delete(
        synchronize_session=False)
    db.query(Department).filter(Department.org_id.in_(org_ids)).delete(
        synchronize_session=False)
    db.query(User).filter(User.org_id.in_(org_ids)).delete(synchronize_session=False)
    db.query(OrganizationSubscription).filter(
        OrganizationSubscription.organization_id.in_(org_ids)).delete(
            synchronize_session=False)
    db.query(Organization).filter(Organization.id.in_(org_ids)).delete(
        synchronize_session=False)
    db.commit()


def _as(user: User):
    """Authenticate as `user` and nothing more.

    Only `get_current_active_user` is overridden, so `require_permission` still
    runs for real against the seeded RolePermission grants. Overriding the
    permission dependency instead would let these tests pass for a role that
    has no business reaching the endpoint.
    """
    app.dependency_overrides[deps.get_current_active_user] = lambda: user


def _public():
    """Drop every override: the caller is anonymous."""
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _no_leftover_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
def slug(client, tenant_a, db):
    _as(tenant_a["hr"])
    r = client.get("/api/v1/recruitment/career-page")
    assert r.status_code == 200, r.text[:200]
    s = r.json()["career_slug"]
    _public()
    return s


# --------------------------------------------------------------------------- #
# public careers page
# --------------------------------------------------------------------------- #

class TestPublicCareersPage:
    def test_profile_is_reachable_without_a_session(self, client, db, tenant_a, slug):
        r = client.get(f"/api/v1/careers/{slug}")
        assert r.status_code == 200
        assert r.json()["name"] == "Acme Careers Co"

    def test_only_open_roles_are_listed(self, client, db, tenant_a, slug):
        _mk_job(db, tenant_a["org"], "Open Role", "open", tenant_a["hr"])
        _mk_job(db, tenant_a["org"], "Secret Draft", "draft", tenant_a["hr"])
        _mk_job(db, tenant_a["org"], "Closed Role", "closed", tenant_a["hr"])
        _public()
        r = client.get(f"/api/v1/careers/{slug}/jobs")
        assert r.status_code == 200
        titles = [j["title"] for j in r.json()]
        assert titles == ["Open Role"], (
            f"a draft or closed role leaked to the public board: {titles}"
        )

    def test_draft_and_closed_detail_are_404(self, client, db, tenant_a, slug):
        draft = _mk_job(db, tenant_a["org"], "Secret Draft", "draft", tenant_a["hr"])
        closed = _mk_job(db, tenant_a["org"], "Closed Role", "closed", tenant_a["hr"])
        _public()
        assert client.get(f"/api/v1/careers/{slug}/jobs/{draft.id}").status_code == 404
        assert client.get(f"/api/v1/careers/{slug}/jobs/{closed.id}").status_code == 404

    def test_public_payload_omits_internal_fields(self, client, db, tenant_a, slug):
        """`posted_by_user_id` would let a candidate enumerate staff accounts."""
        _mk_job(db, tenant_a["org"], "Open Role", "open", tenant_a["hr"])
        _public()
        jobs = client.get(f"/api/v1/careers/{slug}/jobs").json()
        assert jobs
        for job in jobs:
            assert "posted_by_user_id" not in job
            assert "status" not in job
            assert "organization_id" not in job

    def test_unknown_slug_is_404(self, client, db, tenant_a, slug):
        _public()
        assert client.get("/api/v1/careers/there-is-no-such-org").status_code == 404

    def test_inactive_tenant_disappears_from_the_public_web(self, client, db, tenant_a, slug):
        tenant_a["org"].is_active = False
        db.commit()
        _public()
        assert client.get(f"/api/v1/careers/{slug}").status_code == 404

    def test_job_id_from_another_tenant_is_404_via_this_tenants_slug(
        self, client, db, tenant_a, tenant_b
    ):
        """The slug and the job id must agree, or a caller could pair a valid
        job id from tenant B with tenant A's slug and apply to A's board."""
        job_b = _mk_job(db, tenant_b["org"], "Globex Role", "open", tenant_b["hr"])
        _as(tenant_a["hr"])
        slug_a = client.get("/api/v1/recruitment/career-page").json()["career_slug"]
        _public()
        assert client.get(f"/api/v1/careers/{slug_a}/jobs/{job_b.id}").status_code == 404

    def test_boards_are_isolated(self, client, db, tenant_a, tenant_b, slug):
        _mk_job(db, tenant_a["org"], "Acme Only", "open", tenant_a["hr"])
        _as(tenant_b["hr"])
        slug_b = client.get("/api/v1/recruitment/career-page").json()["career_slug"]
        _public()
        assert [j["title"] for j in client.get(f"/api/v1/careers/{slug_b}/jobs").json()] == []


# --------------------------------------------------------------------------- #
# internal referrals
# --------------------------------------------------------------------------- #

class TestCreateReferral:
    def test_employee_can_refer_a_candidate(self, client, db, tenant_a):
        job = _mk_job(db, tenant_a["org"], "Open Role", "open", tenant_a["hr"])
        _as(tenant_a["emp"])
        r = client.post("/api/v1/recruitment/referrals", json={
            "referred_name": "Rita Referral", "referred_email": "rita@example.com",
            "referred_phone": "+1 555 0100", "job_posting_id": job.id,
            "notes": "Met at a meetup.",
        })
        assert r.status_code == 201, r.text[:200]
        body = r.json()
        assert body["referral_code"].startswith("REF-")
        assert body["referrer_user_id"] == tenant_a["emp"].id
        assert body["status"] == "pending"

    def test_referrer_is_the_caller_not_the_payload(self, client, db, tenant_a):
        """A user must not be able to raise a referral in a colleague's name
        and claim their referral bonus."""
        job = _mk_job(db, tenant_a["org"], "Open Role", "open", tenant_a["hr"])
        _as(tenant_a["emp"])
        r = client.post("/api/v1/recruitment/referrals", json={
            "referred_name": "Rita", "referred_email": "rita@example.com",
            "job_posting_id": job.id,
            "referrer_user_id": tenant_a["hr"].id,
        })
        assert r.status_code == 201
        assert r.json()["referrer_user_id"] == tenant_a["emp"].id

    def test_duplicate_referral_refused(self, client, db, tenant_a):
        job = _mk_job(db, tenant_a["org"], "Open Role", "open", tenant_a["hr"])
        _as(tenant_a["emp"])
        payload = {"referred_name": "Rita", "referred_email": "rita@example.com",
                   "job_posting_id": job.id}
        assert client.post("/api/v1/recruitment/referrals", json=payload).status_code == 201
        assert client.post("/api/v1/recruitment/referrals", json=payload).status_code == 400

    def test_cannot_refer_against_another_tenants_job(self, client, db, tenant_a, tenant_b):
        job_b = _mk_job(db, tenant_b["org"], "Globex Role", "open", tenant_b["hr"])
        _as(tenant_a["emp"])
        r = client.post("/api/v1/recruitment/referrals", json={
            "referred_name": "Mallory", "referred_email": "m@example.com",
            "job_posting_id": job_b.id})
        assert r.status_code == 400, r.text[:200]

    def test_cannot_refer_against_a_closed_job(self, client, db, tenant_a):
        closed = _mk_job(db, tenant_a["org"], "Closed", "closed", tenant_a["hr"])
        _as(tenant_a["emp"])
        r = client.post("/api/v1/recruitment/referrals", json={
            "referred_name": "Late", "referred_email": "late@example.com",
            "job_posting_id": closed.id})
        assert r.status_code == 400, r.text[:200]

    def test_weak_input_is_rejected(self, client, db, tenant_a):
        _as(tenant_a["emp"])
        for payload in (
            {"referred_name": "R", "referred_email": "rita@example.com"},
            {"referred_name": "Rita", "referred_email": "not-an-email"},
            {"referred_name": "Rita", "referred_email": "rita@example.com",
             "referred_phone": "call me maybe<script>"},
        ):
            assert client.post("/api/v1/recruitment/referrals", json=payload).status_code == 422

    def test_requires_authentication(self, client, db, tenant_a):
        _public()
        r = client.post("/api/v1/recruitment/referrals", json={
            "referred_name": "Rita", "referred_email": "rita@example.com"})
        assert r.status_code in (401, 403)


class TestReferralVisibility:
    def test_employee_sees_only_their_own(self, client, db, tenant_a):
        job = _mk_job(db, tenant_a["org"], "Open Role", "open", tenant_a["hr"])
        _as(tenant_a["emp"])
        client.post("/api/v1/recruitment/referrals", json={
            "referred_name": "Rita", "referred_email": "rita@example.com",
            "job_posting_id": job.id})
        mine = client.get("/api/v1/recruitment/referrals/mine")
        assert mine.status_code == 200
        assert len(mine.json()) == 1
        assert all(r["referrer_user_id"] == tenant_a["emp"].id for r in mine.json())

    def test_employee_is_blocked_from_the_tenant_book(self, client, db, tenant_a):
        """`referral.create` is the broad grant and carries no read access to
        the candidate pool; `referral.verify` is the narrow one. An employee
        holds only the former, so the tenant-wide list must refuse them."""
        job = _mk_job(db, tenant_a["org"], "Open Role", "open", tenant_a["hr"])
        _as(tenant_a["emp"])
        client.post("/api/v1/recruitment/referrals", json={
            "referred_name": "Rita", "referred_email": "rita@example.com",
            "job_posting_id": job.id})
        r = client.get("/api/v1/recruitment/referrals")
        assert r.status_code == 403, (
            f"an employee reached the tenant-wide referral book ({r.status_code}); "
            "referral.create must not imply referral.verify"
        )
        assert client.get("/api/v1/recruitment/referrals/stats").status_code == 403
        assert client.get(f"/api/v1/recruitment/referrals/1").status_code == 403

    def test_hr_sees_the_whole_tenant(self, client, db, tenant_a):
        job = _mk_job(db, tenant_a["org"], "Open Role", "open", tenant_a["hr"])
        _as(tenant_a["emp"])
        client.post("/api/v1/recruitment/referrals", json={
            "referred_name": "Rita", "referred_email": "rita@example.com",
            "job_posting_id": job.id})
        _as(tenant_a["hr"])
        r = client.get("/api/v1/recruitment/referrals")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_stats_require_verify(self, client, db, tenant_a):
        _as(tenant_a["hr"])
        r = client.get("/api/v1/recruitment/referrals/stats")
        assert r.status_code == 200
        assert set(r.json()) >= {"total", "by_status", "conversion_rate",
                                 "reward_liability"}


# --------------------------------------------------------------------------- #
# referral + public application
# --------------------------------------------------------------------------- #

class TestPublicApplyLinksTheReferral:
    def test_valid_code_is_recorded(self, client, db, tenant_a, slug):
        """The end-to-end path: refer, share the code, candidate applies."""
        job = _mk_job(db, tenant_a["org"], "Open Role", "open", tenant_a["hr"])
        _as(tenant_a["emp"])
        code = client.post("/api/v1/recruitment/referrals", json={
            "referred_name": "Rita Referral", "referred_email": "rita@example.com",
            "job_posting_id": job.id}).json()["referral_code"]

        _public()
        r = client.post(f"/api/v1/careers/{slug}/jobs/{job.id}/apply", json={
            "full_name": "Rita Referral", "email": "rita@example.com",
            "cover_letter": "Hire me.", "referral_code": code,
        })
        assert r.status_code == 201, r.text[:200]
        assert r.json()["referral_recorded"] is True

        _as(tenant_a["hr"])
        book = client.get("/api/v1/recruitment/referrals").json()
        assert book[0]["status"] == "submitted", (
            "a code redeemed on the public form must move the referral to "
            f"'submitted', not leave it 'pending' (got {book[0]['status']!r})"
        )

    def test_unknown_code_is_ignored_not_reported(self, client, db, tenant_a, slug):
        """Reporting an invalid code would make the public form an oracle for
        testing which codes are real."""
        job = _mk_job(db, tenant_a["org"], "Open Role", "open", tenant_a["hr"])
        _public()
        r = client.post(f"/api/v1/careers/{slug}/jobs/{job.id}/apply", json={
            "full_name": "Fake Code", "email": "fake@example.com",
            "referral_code": "REF-BOGUS12"})
        assert r.status_code == 201, r.text[:200]
        assert r.json()["referral_recorded"] is False

    def test_cross_tenant_code_is_ignored(self, client, db, tenant_a, tenant_b, slug):
        job_a = _mk_job(db, tenant_a["org"], "Acme Role", "open", tenant_a["hr"])
        job_b = _mk_job(db, tenant_b["org"], "Globex Role", "open", tenant_b["hr"])
        _as(tenant_b["emp"])
        code_b = client.post("/api/v1/recruitment/referrals", json={
            "referred_name": "Other Tenant", "referred_email": "ot@example.com",
            "job_posting_id": job_b.id}).json()["referral_code"]

        _public()
        r = client.post(f"/api/v1/careers/{slug}/jobs/{job_a.id}/apply", json={
            "full_name": "Cross Tenant", "email": "ct@example.com",
            "referral_code": code_b})
        assert r.status_code == 201
        assert r.json()["referral_recorded"] is False, (
            "a referral code from another tenant was accepted"
        )

    def test_code_is_single_use(self, client, db, tenant_a, slug):
        job = _mk_job(db, tenant_a["org"], "Open Role", "open", tenant_a["hr"])
        _as(tenant_a["emp"])
        code = client.post("/api/v1/recruitment/referrals", json={
            "referred_name": "Rita", "referred_email": "rita@example.com",
            "job_posting_id": job.id}).json()["referral_code"]
        _public()
        first = client.post(f"/api/v1/careers/{slug}/jobs/{job.id}/apply", json={
            "full_name": "Rita", "email": "rita@example.com", "referral_code": code})
        assert first.json()["referral_recorded"] is True

        replay = client.post(f"/api/v1/careers/{slug}/jobs/{job.id}/apply", json={
            "full_name": "Someone Else", "email": "someone.else@example.com",
            "referral_code": code})
        assert replay.status_code == 201
        assert replay.json()["referral_recorded"] is False, (
            "a spent referral code was re-credited to a different applicant"
        )

    def test_duplicate_application_refused(self, client, db, tenant_a, slug):
        job = _mk_job(db, tenant_a["org"], "Open Role", "open", tenant_a["hr"])
        _public()
        body = {"full_name": "Rita", "email": "rita@example.com"}
        assert client.post(f"/api/v1/careers/{slug}/jobs/{job.id}/apply", json=body).status_code == 201
        assert client.post(f"/api/v1/careers/{slug}/jobs/{job.id}/apply", json=body).status_code == 409

    def test_applying_to_a_draft_job_is_404(self, client, db, tenant_a, slug):
        draft = _mk_job(db, tenant_a["org"], "Secret", "draft", tenant_a["hr"])
        _public()
        r = client.post(f"/api/v1/careers/{slug}/jobs/{draft.id}/apply", json={
            "full_name": "Rita", "email": "rita@example.com"})
        assert r.status_code == 404

    def test_honeypot_is_silently_absorbed(self, client, db, tenant_a, slug):
        job = _mk_job(db, tenant_a["org"], "Open Role", "open", tenant_a["hr"])
        _public()
        r = client.post(f"/api/v1/careers/{slug}/jobs/{job.id}/apply", json={
            "full_name": "Bot", "email": "bot@example.com",
            "website": "http://spam.example"})
        assert r.status_code == 201
        assert db.query(JobApplication).filter(
            JobApplication.organization_id == tenant_a["org"].id).count() == 0, (
            "a honeypot submission must not be stored"
        )

    def test_public_apply_needs_no_session(self, client, db, tenant_a, slug):
        job = _mk_job(db, tenant_a["org"], "Open Role", "open", tenant_a["hr"])
        _public()
        r = client.post(f"/api/v1/careers/{slug}/jobs/{job.id}/apply", json={
            "full_name": "Anon", "email": "anon@example.com"})
        assert r.status_code == 201, r.text[:200]


# --------------------------------------------------------------------------- #
# verification and rewards
# --------------------------------------------------------------------------- #

class TestReferralVerification:
    def _refer(self, client, db, tenant_a, email="rita@example.com"):
        job = _mk_job(db, tenant_a["org"], "Open Role", "open", tenant_a["hr"])
        _as(tenant_a["emp"])
        r = client.post("/api/v1/recruitment/referrals", json={
            "referred_name": "Rita", "referred_email": email, "job_posting_id": job.id})
        return r.json()["id"]

    def test_status_transitions_are_ordered(self, client, db, tenant_a):
        ref_id = self._refer(client, db, tenant_a)
        _as(tenant_a["hr"])
        jump = client.patch(f"/api/v1/recruitment/referrals/{ref_id}",
                            json={"status": "hired"})
        assert jump.status_code == 409, (
            "a referral must not jump from pending straight to hired"
        )
        for state in ("submitted", "screening", "qualified", "hired"):
            step = client.patch(f"/api/v1/recruitment/referrals/{ref_id}",
                                json={"status": state})
            assert step.status_code == 200, f"{state}: {step.text[:150]}"

    def test_reward_can_be_approved_and_counted(self, client, db, tenant_a):
        ref_id = self._refer(client, db, tenant_a)
        _as(tenant_a["hr"])
        for state in ("submitted", "screening", "qualified", "hired"):
            client.patch(f"/api/v1/recruitment/referrals/{ref_id}", json={"status": state})
        r = client.patch(f"/api/v1/recruitment/referrals/{ref_id}",
                         json={"reward_amount": 500.0, "reward_status": "approved"})
        assert r.status_code == 200
        stats = client.get("/api/v1/recruitment/referrals/stats").json()
        assert stats["hired"] == 1
        assert stats["reward_liability"] == 500.0

    def test_unknown_status_rejected(self, client, db, tenant_a):
        ref_id = self._refer(client, db, tenant_a)
        _as(tenant_a["hr"])
        r = client.patch(f"/api/v1/recruitment/referrals/{ref_id}",
                         json={"status": "money"})
        assert r.status_code == 422

    def test_cross_tenant_referral_is_404_not_403(self, client, db, tenant_a, tenant_b):
        ref_id = self._refer(client, db, tenant_a)
        _as(tenant_b["hr"])
        r = client.get(f"/api/v1/recruitment/referrals/{ref_id}")
        assert r.status_code == 404, (
            f"expected 404 for another tenant's referral, got {r.status_code}; "
            "403 would confirm the id exists somewhere"
        )
        book = client.get("/api/v1/recruitment/referrals")
        assert book.status_code == 200
        assert all(row["id"] != ref_id for row in book.json())
        assert all(row["organization_id"] == str(tenant_b["org"].id)
                   for row in book.json())

    def test_cross_tenant_patch_is_404(self, client, db, tenant_a, tenant_b):
        ref_id = self._refer(client, db, tenant_a)
        _as(tenant_b["hr"])
        r = client.patch(f"/api/v1/recruitment/referrals/{ref_id}",
                         json={"status": "hired", "reward_amount": 1.0})
        assert r.status_code == 404, f"got {r.status_code}"
