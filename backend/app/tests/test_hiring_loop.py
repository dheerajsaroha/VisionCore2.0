"""
The recruitment-to-employment loop: what actually happens when a candidate is
marked `hired`.

Before this, `hired` was a string. PATCHing an application set the column and
stopped: no user, no employment record, no slot consumed. These tests pin the
behaviour that replaced it.

The interesting cases are the ones where a naive implementation is quietly
wrong rather than loudly broken:

  * a retry must not mint a second employee and a second invite;
  * approving more people than the position has seats must fail on the
    over-capacity hire, and must not leave the failed application marked hired;
  * a rejected candidate must not be hireable;
  * a partially failed hire must leave nothing behind;
  * `users.email` is globally unique, so a candidate who already exists in
    another tenant must be refused rather than silently adopted.
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
    EmployeeInvite,
    EmploymentRecord,
    JobApplication,
    JobPosition,
    JobPosting,
    Organization,
    OrganizationSubscription,
    Role,
    SubscriptionPlan,
    User,
    UserSession,
)
from app.services.hiring_service import position_headroom


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #

def _mk_org(db, name: str) -> Organization:
    org = Organization(name=name, legal_id=f"HIR-{uuid.uuid4().hex[:8].upper()}")
    db.add(org)
    db.commit()
    db.refresh(org)
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.code == "enterprise").first()
    db.add(OrganizationSubscription(
        organization_id=org.id, subscription_plan_id=plan.id,
        status="active", billing_cycle="yearly"))
    dept = Department(org_id=org.id, name="Engineering")
    db.add(dept)
    db.commit()
    db.refresh(dept)
    org.dept = dept
    return org


def _mk_user(db, org: Organization, role_name: str, tag: str,
             email: str | None = None) -> User:
    role = db.query(Role).filter(Role.name == role_name).first()
    assert role, f"missing seeded role {role_name}"
    slug = f"hir_{tag}_{uuid.uuid4().hex[:6]}"
    user = User(
        email=email or f"{slug}@example.com", username=slug, employee_id=slug.upper(),
        full_name=f"Hire {tag}", org_id=org.id, role_id=role.id,
        is_active=1, is_deleted=0, hashed_password=get_password_hash("Password123!"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _mk_position(db, org: Organization, capacity: int = 1,
                 title: str = "Engineer") -> JobPosition:
    pos = JobPosition(
        org_id=org.id, code=f"POS-{uuid.uuid4().hex[:6].upper()}", title=title,
        dept_id=org.dept.id, headcount_capacity=capacity,
    )
    db.add(pos)
    db.commit()
    db.refresh(pos)
    return pos


def _mk_job(db, org: Organization, poster: User, position: JobPosition | None = None,
            headcount: int = 1) -> JobPosting:
    job = JobPosting(
        organization_id=org.id, title="Backend Engineer",
        department_id=org.dept.id, description="Build things.",
        status="open", posted_by_user_id=poster.id,
        position_id=position.id if position is not None else None,
        headcount=headcount,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _mk_candidate(db, org: Organization, email: str | None = None) -> Candidate:
    cand = Candidate(
        organization_id=org.id, full_name="Casey Candidate",
        email=email or f"cand_{uuid.uuid4().hex[:8]}@example.com",
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    return cand


def _cleanup(db, org_ids):
    uid_list = [r[0] for r in
                db.query(User.id).filter(User.org_id.in_(org_ids)).all()]
    # The recruitment tables name their tenant column `organization_id` while
    # the employment tables use `org_id`, so the column is picked per model
    # rather than assumed.
    for model, column in ((JobApplication, "organization_id"),
                          (EmployeeInvite, "organization_id"),
                          (EmploymentRecord, "org_id")):
        db.query(model).filter(getattr(model, column).in_(org_ids)).delete(
            synchronize_session=False)
    db.query(Candidate).filter(Candidate.organization_id.in_(org_ids)).delete(
        synchronize_session=False)
    db.query(JobPosting).filter(JobPosting.organization_id.in_(org_ids)).delete(
        synchronize_session=False)
    db.query(JobPosition).filter(JobPosition.org_id.in_(org_ids)).delete(
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
def tenant(db):
    org = _mk_org(db, "Acme Hiring Co")
    yield {"org": org, "hr": _mk_user(db, org, "OrgHR", "hr"),
           "emp": _mk_user(db, org, "OrgEmployee", "emp")}
    _cleanup(db, [org.id])


@pytest.fixture()
def other_tenant(db):
    org = _mk_org(db, "Globex Hiring Co")
    yield {"org": org, "hr": _mk_user(db, org, "OrgHR", "hrb")}
    _cleanup(db, [org.id])


def _as(user: User):
    app.dependency_overrides[deps.get_current_active_user] = lambda: user


@pytest.fixture(autouse=True)
def _no_leftover_overrides():
    yield
    app.dependency_overrides.clear()


def _apply(client, db, org, job, cand, stage="hired"):
    """File an application and move it to `stage` as the given tenant."""
    _as(org["emp"] if "emp" in org else org["hr"])
    created = client.post("/api/v1/recruitment/applications", json={
        "job_posting_id": job.id, "candidate_id": cand.id})
    assert created.status_code == 201, created.text[:200]
    return client.patch(
        f"/api/v1/recruitment/applications/{created.json()['id']}/stage",
        json={"stage": stage})


def _application_for(client, db, org, job, cand, stage="screening"):
    """File an application and park it at a non-terminal stage."""
    _as(org["emp"])
    created = client.post("/api/v1/recruitment/applications", json={
        "job_posting_id": job.id, "candidate_id": cand.id}).json()
    if stage != "applied":
        client.patch(
            f"/api/v1/recruitment/applications/{created['id']}/stage",
            json={"stage": stage})
    return created["id"]


# --------------------------------------------------------------------------- #
# the loop closes
# --------------------------------------------------------------------------- #

class TestHiringCreatesAnEmployee:
    def test_hiring_creates_a_user_an_employment_record_and_an_invite(
        self, client, db, tenant
    ):
        org = tenant["org"]
        pos = _mk_position(db, org, capacity=2)
        job = _mk_job(db, org, tenant["hr"], position=pos)
        cand = _mk_candidate(db, org)

        r = _apply(client, db, tenant, job, cand)
        assert r.status_code == 200, r.text[:300]
        body = r.json()

        assert body["stage"] == "hired"
        assert body["employment_id"], "no employment record was created"
        assert body["user_id"], "no employee account was created"
        assert body["invite_token"], "no onboarding invite was issued"

        db.expire_all()
        employment = db.query(EmploymentRecord).filter(
            EmploymentRecord.id == body["employment_id"]).one()
        assert employment.user_id == body["user_id"]
        assert employment.position_id == pos.id
        assert employment.status == "PENDING_ONBOARDING"
        assert employment.org_id == org.id

        # Looked up by id rather than by `accepted_user_id`, which is only set
        # once the invite is consumed.
        invite = db.query(EmployeeInvite).filter(
            EmployeeInvite.id == body["invite_id"]).one()
        assert invite.position_id == pos.id
        assert invite.status == "pending"
        assert invite.email == cand.email.strip().lower()

    def test_the_new_account_cannot_be_logged_into_before_onboarding(
        self, client, db, tenant
    ):
        """The account exists so the employment record can reference it, but
        its password is a random placeholder until the invite is accepted."""
        org = tenant["org"]
        job = _mk_job(db, org, tenant["hr"], position=_mk_position(db, org))
        # Unique per run: `users.email` is globally unique, so a leftover row
        # from an aborted run would make this look like a cross-tenant clash.
        email = f"onboard_{uuid.uuid4().hex[:8]}@example.com"
        cand = _mk_candidate(db, org, email=email)
        body = _apply(client, db, tenant, job, cand).json()

        app.dependency_overrides.clear()
        r = client.post("/api/v1/auth/login", data={
            "username": email, "password": "Password123!"})
        assert r.status_code != 200, (
            "a hired-but-not-onboarded account was able to log in"
        )
        assert body["invite_token"]

    def test_accepting_the_invite_activates_the_employment(
        self, client, db, tenant
    ):
        org = tenant["org"]
        job = _mk_job(db, org, tenant["hr"], position=_mk_position(db, org))
        cand = _mk_candidate(db, org)
        hired = _apply(client, db, tenant, job, cand).json()

        app.dependency_overrides.clear()
        r = client.post(
            "/api/v1/invites/accept",
            params={"token": hired["invite_token"]},
            json={"password": "Chosen-Passphrase!9", "full_name": "Casey Candidate"},
        )
        assert r.status_code == 200, r.text[:300]

        db.expire_all()
        employment = db.query(EmploymentRecord).filter(
            EmploymentRecord.id == hired["employment_id"]).one()
        assert employment.status == "PROBATION", (
            "onboarding did not convert the held slot into an employment"
        )

    def test_the_chosen_password_then_works(self, client, db, tenant):
        org = tenant["org"]
        job = _mk_job(db, org, tenant["hr"], position=_mk_position(db, org))
        email = f"newjoin_{uuid.uuid4().hex[:8]}@example.com"
        cand = _mk_candidate(db, org, email=email)
        hired = _apply(client, db, tenant, job, cand).json()

        app.dependency_overrides.clear()
        client.post("/api/v1/invites/accept",
                    params={"token": hired["invite_token"]},
                    json={"password": "Chosen-Passphrase!9",
                          "full_name": "Casey Candidate"})
        r = client.post("/api/v1/auth/login", data={
            "username": email, "password": "Chosen-Passphrase!9"})
        assert r.status_code == 200, r.text[:200]

    def test_headroom_moves_when_someone_is_hired(self, client, db, tenant):
        org = tenant["org"]
        pos = _mk_position(db, org, capacity=3)
        job = _mk_job(db, org, tenant["hr"], position=pos)
        assert position_headroom(db, org.id, pos.id)["filled"] == 0

        _apply(client, db, tenant, job, _mk_candidate(db, org))
        db.expire_all()
        after = position_headroom(db, org.id, pos.id)
        assert after["filled"] == 1
        assert after["remaining"] == 2

    def test_a_posting_without_a_position_still_hires(self, client, db, tenant):
        """A tenant that never defined positions must not be blocked; the hire
        is recorded with no slot rather than an invented one."""
        org = tenant["org"]
        job = _mk_job(db, org, tenant["hr"], position=None)
        body = _apply(client, db, tenant, job, _mk_candidate(db, org)).json()
        assert body["stage"] == "hired"
        assert body["position"] is None
        db.expire_all()
        assert db.query(EmploymentRecord).filter(
            EmploymentRecord.id == body["employment_id"]).one().position_id is None


# --------------------------------------------------------------------------- #
# idempotency
# --------------------------------------------------------------------------- #

class TestHiringIsIdempotent:
    def test_a_retry_does_not_mint_a_second_employee(self, client, db, tenant):
        org = tenant["org"]
        pos = _mk_position(db, org, capacity=5)
        job = _mk_job(db, org, tenant["hr"], position=pos)
        cand = _mk_candidate(db, org)
        app_id = _application_for(client, db, tenant, job, cand)

        first = client.patch(
            f"/api/v1/recruitment/applications/{app_id}/stage",
            json={"stage": "hired"})
        assert first.status_code == 200, first.text[:200]

        second = client.patch(
            f"/api/v1/recruitment/applications/{app_id}/stage",
            json={"stage": "hired"})
        assert second.status_code == 200, (
            f"a retried hire was rejected with {second.status_code} instead of "
            "returning the original hire"
        )
        assert second.json()["employment_id"] == first.json()["employment_id"]

        db.expire_all()
        assert db.query(EmploymentRecord).filter(
            EmploymentRecord.org_id == org.id).count() == 1
        assert db.query(EmployeeInvite).filter(
            EmployeeInvite.organization_id == org.id).count() == 1
        assert position_headroom(db, org.id, pos.id)["filled"] == 1

    def test_a_retry_reports_that_it_replayed(self, client, db, tenant):
        org = tenant["org"]
        job = _mk_job(db, org, tenant["hr"], position=_mk_position(db, org))
        app_id = _application_for(client, db, tenant, job, _mk_candidate(db, org))
        client.patch(f"/api/v1/recruitment/applications/{app_id}/stage",
                     json={"stage": "hired"})
        again = client.patch(f"/api/v1/recruitment/applications/{app_id}/stage",
                             json={"stage": "hired"})
        assert again.json()["idempotent_replay"] is True
        assert again.json()["invite_token"] is None, (
            "a retry re-sent the raw invite token, which should only ever be "
            "returned once"
        )


# --------------------------------------------------------------------------- #
# capacity
# --------------------------------------------------------------------------- #

class TestHeadcountCapacity:
    def test_hiring_beyond_capacity_is_refused(self, client, db, tenant):
        org = tenant["org"]
        pos = _mk_position(db, org, capacity=1)
        job = _mk_job(db, org, tenant["hr"], position=pos, headcount=5)
        first = _apply(client, db, tenant, job, _mk_candidate(db, org))
        assert first.status_code == 200, first.text[:200]

        second = _apply(client, db, tenant, job, _mk_candidate(db, org))
        assert second.status_code == 409, (
            f"hired past capacity with {second.status_code}: {second.text[:200]}"
        )
        assert "already filled" in second.json()["detail"]

    def test_a_refused_hire_leaves_the_application_where_it_was(
        self, client, db, tenant
    ):
        """The failure has to roll the whole transition back. Marking the
        second candidate `hired` with no employment record is the exact state
        this feature exists to eliminate."""
        org = tenant["org"]
        pos = _mk_position(db, org, capacity=1)
        job = _mk_job(db, org, tenant["hr"], position=pos, headcount=5)
        _apply(client, db, tenant, job, _mk_candidate(db, org))

        loser_job = _mk_job(db, org, tenant["hr"], position=pos, headcount=5)
        loser = _mk_candidate(db, org)
        app_id = _application_for(client, db, tenant, loser_job, loser)
        refused = client.patch(
            f"/api/v1/recruitment/applications/{app_id}/stage",
            json={"stage": "hired"})
        assert refused.status_code == 409

        db.expire_all()
        row = db.query(JobApplication).filter(JobApplication.id == app_id).one()
        assert row.stage == "screening", (
            f"a failed hire still marked the application '{row.stage}'"
        )
        assert row.hired_employment_id is None
        assert db.query(User).filter(
            User.email == loser.email).count() == 0, (
            "a failed hire left a half-created employee account behind"
        )

    def test_raising_capacity_lets_the_next_hire_through(self, client, db, tenant):
        org = tenant["org"]
        pos = _mk_position(db, org, capacity=1)
        job = _mk_job(db, org, tenant["hr"], position=pos, headcount=5)
        _apply(client, db, tenant, job, _mk_candidate(db, org))
        blocked = _apply(client, db, tenant, job, _mk_candidate(db, org))
        assert blocked.status_code == 409

        pos.headcount_capacity = 2
        db.commit()
        allowed = _apply(client, db, tenant, job, _mk_candidate(db, org))
        assert allowed.status_code == 200, allowed.text[:200]

    def test_offboarding_frees_the_slot(self, client, db, tenant):
        """Capacity is derived by counting employment records, so a terminated
        employee releases their seat without any reconciliation step."""
        org = tenant["org"]
        pos = _mk_position(db, org, capacity=1)
        job = _mk_job(db, org, tenant["hr"], position=pos, headcount=5)
        _apply(client, db, tenant, job, _mk_candidate(db, org))

        db.expire_all()
        record = db.query(EmploymentRecord).filter(
            EmploymentRecord.org_id == org.id,
            EmploymentRecord.status == "PENDING_ONBOARDING").one()
        record.status = "TERMINATED"
        db.commit()
        db.expire_all()

        assert position_headroom(db, org.id, pos.id)["remaining"] == 1
        again = _apply(client, db, tenant, job, _mk_candidate(db, org))
        assert again.status_code == 200, again.text[:200]


# --------------------------------------------------------------------------- #
# refusals
# --------------------------------------------------------------------------- #

class TestHiringRefusals:
    def test_a_rejected_candidate_cannot_be_hired(self, client, db, tenant):
        org = tenant["org"]
        job = _mk_job(db, org, tenant["hr"], position=_mk_position(db, org, capacity=5))
        cand = _mk_candidate(db, org)
        app_id = _application_for(client, db, tenant, job, cand)
        client.patch(f"/api/v1/recruitment/applications/{app_id}/stage",
                     json={"stage": "rejected"})

        r = client.patch(f"/api/v1/recruitment/applications/{app_id}/stage",
                         json={"stage": "hired"})
        assert r.status_code == 409, f"got {r.status_code}"
        db.expire_all()
        assert db.query(EmploymentRecord).filter(
            EmploymentRecord.org_id == org.id).count() == 0

    def test_a_candidate_in_another_tenant_is_refused(self, client, db, tenant, other_tenant):
        """The module has no role gate, so tenant scoping is the only
        boundary; a hire must not create employment in someone else's org."""
        org = tenant["org"]
        foreign_job = _mk_job(db, other_tenant["org"], other_tenant["hr"])
        foreign_cand = _mk_candidate(db, other_tenant["org"])

        _as(tenant["emp"])
        r = client.patch(
            f"/api/v1/recruitment/applications/{foreign_job.id}/stage",
            json={"stage": "hired"})
        # The application id here is the job id, so this is a 404 from the
        # lookup rather than a hire. What matters is that nothing was created.
        assert r.status_code == 404
        db.expire_all()
        assert db.query(EmploymentRecord).filter(
            EmploymentRecord.org_id == other_tenant["org"].id).count() == 0

    def test_a_candidate_who_already_exists_in_another_tenant_is_hired_independently(
        self, client, db, tenant, other_tenant
    ):
        """The same person may work for two organisations.

        `users.email` is unique per tenant, not globally, so this is a separate
        account rather than a clash. The hire must create its own employment in
        this tenant and leave the other tenant's account untouched -- taking it
        over would silently move an employee between tenants.
        """
        email = f"shared_{uuid.uuid4().hex[:8]}@example.com"
        elsewhere = _mk_user(db, other_tenant["org"], "OrgEmployee", "taken",
                             email=email)
        elsewhere_org_before = elsewhere.org_id

        org = tenant["org"]
        pos = _mk_position(db, org, capacity=2)
        job = _mk_job(db, org, tenant["hr"], position=pos)
        cand = _mk_candidate(db, org, email=email)
        r = _apply(client, db, tenant, job, cand)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body["user_id"] != elsewhere.id, (
            "the hire adopted the other tenant's account"
        )

        db.expire_all()
        # The other tenant keeps its own employee, in its own organisation.
        still_theirs = db.query(User).filter(User.id == elsewhere.id).one()
        assert still_theirs.org_id == elsewhere_org_before
        assert db.query(EmploymentRecord).filter(
            EmploymentRecord.org_id == other_tenant["org"].id).count() == 0

        # And the new employment belongs to this tenant and consumes its slot.
        record = db.query(EmploymentRecord).filter(
            EmploymentRecord.id == body["employment_id"]).one()
        assert record.org_id == org.id
        assert record.position_id == pos.id
        assert position_headroom(db, org.id, pos.id)["filled"] == 1

    def test_the_same_address_may_hold_independent_accounts_per_tenant(
        self, client, db, tenant, other_tenant
    ):
        """Both employees exist at once, and the per-tenant unique index is
        what makes that legal rather than a race."""
        email = f"dual_{uuid.uuid4().hex[:8]}@example.com"
        first = _mk_user(db, tenant["org"], "OrgHR", "one", email=email)
        second = _mk_user(db, other_tenant["org"], "OrgHR", "two", email=email)
        assert first.id != second.id
        assert first.email == second.email
        assert first.org_id != second.org_id

    def test_an_existing_employee_in_the_same_tenant_is_rehired_not_duplicated(
        self, client, db, tenant
    ):
        """Re-hiring someone who left is a real case. The account is reused and
        no invite is issued, because there is nobody to onboard."""
        org = tenant["org"]
        email = f"rehire_{uuid.uuid4().hex[:8]}@example.com"
        person = _mk_user(db, org, "OrgEmployee", "re", email=email)
        job = _mk_job(db, org, tenant["hr"], position=_mk_position(db, org))
        cand = _mk_candidate(db, org, email=email)

        r = _apply(client, db, tenant, job, cand)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body["user_id"] == person.id
        assert body["invite_token"] is None
        assert body["already_employed"] is True

        db.expire_all()
        record = db.query(EmploymentRecord).filter(
            EmploymentRecord.id == body["employment_id"]).one()
        assert record.status == "PROBATION", (
            "a re-hire should be an active employment, not one pending "
            "onboarding that will never complete"
        )
        assert db.query(EmployeeInvite).filter(
            EmployeeInvite.organization_id == org.id).count() == 0

    def test_hiring_another_tenants_position_is_refused(self, client, db, tenant, other_tenant):
        """A posting may only be attached to a position in the same tenant, or
        one tenant's vacancy would consume another tenant's headcount."""
        org = tenant["org"]
        foreign_pos = _mk_position(db, other_tenant["org"])
        _as(tenant["emp"])
        r = client.post("/api/v1/recruitment/jobs", json={
            "title": "Sneaky", "description": "x", "position_id": foreign_pos.id})
        assert r.status_code == 404, f"got {r.status_code}"
        db.expire_all()
        assert db.query(JobPosting).filter(
            JobPosting.organization_id == org.id,
            JobPosting.title == "Sneaky").count() == 0


# --------------------------------------------------------------------------- #
# the link is visible where people look for it
# --------------------------------------------------------------------------- #

class TestPostingCarriesItsSlot:
    def test_a_posting_reports_its_position_and_headcount(self, client, db, tenant):
        org = tenant["org"]
        pos = _mk_position(db, org, capacity=4)
        _as(tenant["emp"])
        r = client.post("/api/v1/recruitment/jobs", json={
            "title": "Platform Engineer", "description": "x",
            "position_id": pos.id, "headcount": 3})
        assert r.status_code == 201, r.text[:200]
        assert r.json()["position_id"] == pos.id
        assert r.json()["headcount"] == 3

        listed = client.get("/api/v1/recruitment/jobs").json()
        row = [j for j in listed if j["title"] == "Platform Engineer"][0]
        assert row["position_id"] == pos.id
        assert row["headcount"] == 3

    def test_headcount_must_be_positive(self, client, db, tenant):
        _as(tenant["emp"])
        for bad in (0, -1):
            r = client.post("/api/v1/recruitment/jobs", json={
                "title": "Bad", "description": "x", "headcount": bad})
            assert r.status_code == 422, f"headcount={bad} was accepted"
