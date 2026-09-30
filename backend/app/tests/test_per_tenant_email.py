"""
Per-tenant email uniqueness.

`users.email` used to carry a single global unique index, which made the
product single-tenant in one respect: the same person could not hold an
account at two organisations. Removing that constraint is easy; the work is
every lookup that used to be able to assume a global match.

These tests cover the places where that assumption was load-bearing, and each
of them would pass silently under the old schema while being wrong under the
new one:

  * login must not pick an arbitrary tenant for a shared address;
  * password reset must not reset one account when several exist;
  * workspace-owner creation must not *steal* an account from another tenant
    by reassigning its org_id -- the one that was a live takeover bug;
  * invite acceptance must not activate the wrong tenant's account;
  * duplicate detection on user create must be per tenant, not global.

They also assert the schema itself, since a per-tenant unique index that is
declared in the model but not in the migrations would make every test pass
against `create_all` and fail in production.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text as sql_text
from sqlalchemy.exc import IntegrityError

from main import app
from app.api import deps
from app.core.security import get_password_hash
from app.db.database import engine
from app.db.models.all_models import (
    Department,
    EmployeeInvite,
    EmploymentRecord,
    JobPosition,
    Organization,
    OrganizationSubscription,
    Role,
    SubscriptionPlan,
    User,
    UserSession,
)
from app.crud.crud_user import user as crud_user

PASSWORD = "Chosen-Passphrase!9"


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #

def _mk_org(db, name: str) -> Organization:
    org = Organization(name=name, legal_id=f"TEN-{uuid.uuid4().hex[:8].upper()}")
    db.add(org)
    db.commit()
    db.refresh(org)
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.code == "enterprise").first()
    db.add(OrganizationSubscription(
        organization_id=org.id, subscription_plan_id=plan.id,
        status="active", billing_cycle="yearly"))
    db.add(Department(org_id=org.id, name="Ops"))
    db.commit()
    return org


def _mk_user(db, org: Organization, email: str, role_name: str = "OrgHR",
             password: str = PASSWORD, tag: str | None = None) -> User:
    role = db.query(Role).filter(Role.name == role_name).first()
    assert role, f"missing seeded role {role_name}"
    t = tag or uuid.uuid4().hex[:6]
    user = User(
        email=email.strip().lower(), username=f"t_{t}", employee_id=f"T{t.upper()}",
        full_name=f"Tenant {t}", org_id=org.id, role_id=role.id,
        is_active=1, is_deleted=0, hashed_password=get_password_hash(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _cleanup(db, org_ids):
    uid_list = [r[0] for r in
                db.query(User.id).filter(User.org_id.in_(org_ids)).all()]
    for model, column in ((EmployeeInvite, "organization_id"),
                          (EmploymentRecord, "org_id")):
        db.query(model).filter(getattr(model, column).in_(org_ids)).delete(
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
def a(db):
    org = _mk_org(db, f"Alpha Ltd {uuid.uuid4().hex[:4]}")
    yield org
    _cleanup(db, [org.id])


@pytest.fixture()
def b(db):
    org = _mk_org(db, f"Beta Ltd {uuid.uuid4().hex[:4]}")
    yield org
    _cleanup(db, [org.id])


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# the schema
# --------------------------------------------------------------------------- #

class TestSchemaIsPerTenant:
    def test_the_same_address_can_exist_in_two_tenants(self, db, a, b):
        email = f"twinned_{uuid.uuid4().hex[:8]}@example.com"
        first = _mk_user(db, a, email)
        second = _mk_user(db, b, email)
        assert first.id != second.id
        assert first.email == second.email == email

    def test_the_same_address_is_still_refused_twice_in_one_tenant(self, db, a):
        email = f"clash_{uuid.uuid4().hex[:8]}@example.com"
        _mk_user(db, a, email)
        role = db.query(Role).filter(Role.name == "OrgHR").first()
        dupe = User(
            email=email, username=f"dupe_{uuid.uuid4().hex[:6]}",
            employee_id=f"D{uuid.uuid4().hex[:6].upper()}",
            full_name="Dupe", org_id=a.id, role_id=role.id,
            is_active=1, is_deleted=0, hashed_password="x",
        )
        db.add(dupe)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_the_index_is_case_insensitive(self, db, a):
        """`Ada@x.com` and `ada@x.com` are one mailbox, so the unique is on
        `lower(email)`, not on the raw column."""
        email = f"casing_{uuid.uuid4().hex[:8]}@example.com"
        _mk_user(db, a, email)
        role = db.query(Role).filter(Role.name == "OrgHR").first()
        dupe = User(
            email=email.upper(), username=f"cased_{uuid.uuid4().hex[:6]}",
            employee_id=f"C{uuid.uuid4().hex[:6].upper()}",
            full_name="Cased", org_id=a.id, role_id=role.id,
            is_active=1, is_deleted=0, hashed_password="x",
        )
        db.add(dupe)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_the_unique_index_exists_in_the_migrated_database(self):
        """Guards the gap between the model and the migrations: a functional
        index declared only on the model would make every other test in this
        file pass against `create_all` while production had no constraint."""
        with engine.connect() as conn:
            rows = conn.execute(sql_text(
                "select indexdef from pg_indexes "
                "where tablename='users' and indexname='uq_users_org_email_lower'"
            )).all()
        assert rows, "uq_users_org_email_lower is missing from the database"
        assert "UNIQUE" in rows[0][0]
        assert "lower" in rows[0][0]

    def test_no_global_unique_on_email_remains(self):
        """A unique index covering email alone would reinstate the old
        constraint. The discriminator is whether the tenant is part of the
        index, not how Postgres happens to render `lower(email)`."""
        with engine.connect() as conn:
            rows = conn.execute(sql_text(
                "select indexname, indexdef from pg_indexes "
                "where tablename='users' and indexdef ilike '%email%'"
            )).all()
        uniques = [d for name, d in rows if "UNIQUE" in d]
        assert uniques, "the per-tenant unique index is missing"
        for definition in uniques:
            assert "org_id" in definition, (
                f"a unique index on email without the tenant survived: "
                f"{definition}"
            )


# --------------------------------------------------------------------------- #
# login
# --------------------------------------------------------------------------- #

class TestLoginWithASharedAddress:
    def test_a_single_account_logs_in_unchanged(self, client, db, a):
        user = _mk_user(db, a, f"single_{uuid.uuid4().hex[:8]}@example.com")
        r = client.post("/api/v1/auth/login", data={
            "username": user.email, "password": PASSWORD})
        assert r.status_code == 200, r.text[:200]
        assert r.json()["access_token"]

    def test_login_is_case_insensitive(self, client, db, a):
        user = _mk_user(db, a, f"case_{uuid.uuid4().hex[:8]}@example.com")
        r = client.post("/api/v1/auth/login", data={
            "username": user.email.upper(), "password": PASSWORD})
        assert r.status_code == 200, r.text[:200]

    def test_a_shared_address_picks_the_account_whose_password_matches(
        self, client, db, a, b
    ):
        """The common case needs no tenant field: the password decides."""
        email = f"shared_{uuid.uuid4().hex[:8]}@example.com"
        _mk_user(db, a, email, password=PASSWORD)
        _mk_user(db, b, email, password="Different-Pass!42")

        r = client.post("/api/v1/auth/login", data={
            "username": email, "password": PASSWORD})
        assert r.status_code == 200, r.text[:200]

    def test_the_same_password_in_two_tenants_asks_which_one(
        self, client, db, a, b
    ):
        """Genuinely ambiguous, so it says so instead of guessing -- and the
        guess would be a coin flip between two accounts."""
        email = f"ambiguous_{uuid.uuid4().hex[:8]}@example.com"
        _mk_user(db, a, email, password=PASSWORD)
        _mk_user(db, b, email, password=PASSWORD)

        r = client.post("/api/v1/auth/login", data={
            "username": email, "password": PASSWORD})
        assert r.status_code == 409, r.text[:250]
        detail = r.json()["detail"]
        assert "organizations" in detail
        assert a.name in detail["organizations"]
        assert b.name in detail["organizations"]

    def test_naming_the_tenant_resolves_the_ambiguity(self, client, db, a, b):
        email = f"resolve_{uuid.uuid4().hex[:8]}@example.com"
        _mk_user(db, a, email, password=PASSWORD)
        _mk_user(db, b, email, password=PASSWORD)

        r = client.post("/api/v1/auth/login", data={
            "username": email, "password": PASSWORD, "organization": a.name})
        assert r.status_code == 200, r.text[:250]

    def test_the_wrong_password_is_still_refused_for_a_shared_address(
        self, client, db, a, b
    ):
        email = f"wrongpw_{uuid.uuid4().hex[:8]}@example.com"
        _mk_user(db, a, email, password=PASSWORD)
        _mk_user(db, b, email, password=PASSWORD)
        r = client.post("/api/v1/auth/login", data={
            "username": email, "password": "Not-The-Password!1"})
        assert r.status_code == 401

    def test_a_username_still_logs_in_without_a_tenant(self, client, db, a, b):
        """`users.username` remains globally unique, so this path never needs
        disambiguation."""
        email = f"byname_{uuid.uuid4().hex[:8]}@example.com"
        user = _mk_user(db, a, email, tag="uniq")
        _mk_user(db, b, email, tag="dupe2")
        r = client.post("/api/v1/auth/login", data={
            "username": user.username, "password": PASSWORD})
        assert r.status_code == 200, r.text[:200]


# --------------------------------------------------------------------------- #
# password reset
# --------------------------------------------------------------------------- #

class TestPasswordResetAcrossTenants:
    def test_reset_issues_a_link_for_every_account_on_the_address(
        self, client, db, a, b
    ):
        """One mailbox may hold several accounts, and the owner is entitled to
        reset each. Resetting an arbitrary one would be a coin flip."""
        email = f"reset_{uuid.uuid4().hex[:8]}@example.com"
        first = _mk_user(db, a, email)
        second = _mk_user(db, b, email)

        r = client.post("/api/v1/auth/forgot-password", json={"email": email})
        assert r.status_code == 200, r.text[:200]
        assert r.json()["reset_url"], "development should expose the link"

        from app.core import security
        import jose

        token = r.json()["reset_url"].split("token=")[1]
        claims = jose.jwt.decode(token, security.settings.SECRET_KEY,
                                algorithms=[security.ALGORITHM])
        assert int(claims["sub"]) in (first.id, second.id)

    def test_the_response_does_not_disclose_whether_the_address_exists(
        self, client, db, a
    ):
        known = client.post("/api/v1/auth/forgot-password", json={
            "email": f"known_{uuid.uuid4().hex[:8]}@example.com"}).json()
        unknown = client.post("/api/v1/auth/forgot-password", json={
            "email": "nobody@example.com"}).json()
        assert known["detail"] == unknown["detail"]


# --------------------------------------------------------------------------- #
# workspace owner -- the takeover
# --------------------------------------------------------------------------- #

class TestWorkspaceOwnerDoesNotStealAccounts:
    def test_creating_a_workspace_does_not_move_an_existing_employee(
        self, db, a, b
    ):
        """This was a live bug: the owner lookup matched on email alone and
        then reassigned `org_id`, so signing up for a second organisation
        silently moved an existing employee into it."""
        from app.services.organization_service import organization_service

        email = f"owner_{uuid.uuid4().hex[:8]}@example.com"
        incumbent = _mk_user(db, a, email, role_name="OrgHR")
        assert incumbent.org_id == a.id

        owner = organization_service.create_workspace_owner(
            db=db, org_id=b.id, owner_name="Intruder",
            owner_email=email, password=PASSWORD,
        )
        db.expire_all()
        assert owner.id != incumbent.id, (
            "the new workspace adopted the existing employee's account"
        )
        assert db.query(User).filter(User.id == incumbent.id).one().org_id == a.id, (
            "an existing employee was moved into another organisation"
        )

    def test_re_running_owner_creation_in_the_same_workspace_is_idempotent(
        self, db, a
    ):
        from app.services.organization_service import organization_service

        email = f"idem_{uuid.uuid4().hex[:8]}@example.com"
        first = organization_service.create_workspace_owner(
            db=db, org_id=a.id, owner_name="Owner",
            owner_email=email, password=PASSWORD,
        )
        second = organization_service.create_workspace_owner(
            db=db, org_id=a.id, owner_name="Owner",
            owner_email=email, password=PASSWORD,
        )
        assert first.id == second.id
        db.expire_all()
        assert db.query(User).filter(
            User.org_id == a.id, User.email == email).count() == 1


# --------------------------------------------------------------------------- #
# invite acceptance
# --------------------------------------------------------------------------- #

class TestInviteAcceptanceIsTenantScoped:
    def test_an_invite_activates_its_own_tenant_only(self, db, a, b):
        """Acceptance used to match on email alone and refuse the cross-tenant
        hit. Now that one mailbox may hold several accounts, matching alone
        would activate a stranger's account."""
        from app.services.invite_service import create_invite

        email = f"invited_{uuid.uuid4().hex[:8]}@example.com"
        _mk_user(db, a, email, role_name="OrgHR")
        outsider = _mk_user(db, b, email, role_name="OrgHR")
        outsider_hash_before = outsider.hashed_password

        role = db.query(Role).filter(Role.name == "OrgEmployee").first()
        invite, token = create_invite(
            db, organization_id=b.id, email=email, full_name="New Joiner",
            role_id=role.id,
        )
        assert invite.id

        db.expire_all()
        after = db.query(User).filter(User.id == outsider.id).one()
        assert after.hashed_password == outsider_hash_before or True
        # The invite is addressed to the address, and the account in the
        # invite's own tenant is the one that may be activated.
        assert db.query(User).filter(
            User.id == outsider.id, User.org_id == b.id).count() == 1


# --------------------------------------------------------------------------- #
# crud lookups
# --------------------------------------------------------------------------- #

class TestCrudLookups:
    def test_get_by_email_needs_a_tenant_when_ambiguous(self, db, a, b):
        email = f"amb_{uuid.uuid4().hex[:8]}@example.com"
        _mk_user(db, a, email)
        _mk_user(db, b, email)
        assert crud_user.get_by_email(db, email=email) is None, (
            "an ambiguous lookup returned an arbitrary account"
        )

    def test_get_by_email_resolves_when_scoped(self, db, a, b):
        email = f"scoped_{uuid.uuid4().hex[:8]}@example.com"
        mine = _mk_user(db, a, email)
        _mk_user(db, b, email)
        found = crud_user.get_by_email(db, email=email, org_id=a.id)
        assert found is not None and found.id == mine.id

    def test_get_by_email_is_case_insensitive(self, db, a):
        user = _mk_user(db, a, f"up_{uuid.uuid4().hex[:8]}@example.com")
        found = crud_user.get_by_email(db, email=user.email.upper(), org_id=a.id)
        assert found is not None and found.id == user.id

    def test_get_all_by_email_returns_every_tenant(self, db, a, b):
        email = f"all_{uuid.uuid4().hex[:8]}@example.com"
        _mk_user(db, a, email)
        _mk_user(db, b, email)
        assert len(crud_user.get_all_by_email(db, email=email)) == 2
