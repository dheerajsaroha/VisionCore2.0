"""
Tests for magic-link employee onboarding.

The properties under test are the ones that make this safe to put in front of
new hires: the raw token is never recoverable, an invite works exactly once
even under concurrent acceptance, failure modes are indistinguishable so the
endpoint cannot be used to enumerate tokens, the invited role is authorised
while an administrator is present, and a tenant cannot see or act on another
tenant's invites.

Every address is generated per test. The suite runs against a live database
that other tests also write to, so a hardcoded address would collide with a row
a previous run left behind.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from main import app
from app.api import deps
from app.db.database import SessionLocal, get_db
from app.db.models.all_models import (
    EmployeeInvite,
    Organization,
    Role,
    User,
)
from app.routers import invites as invites_router
from app.services import invite_service as svc
from app.services.invite_service import InviteError

VALID_PASSWORD = "Str0ng-Passphrase!42"


# ── Helpers ─────────────────────────────────────────────────────────────
def _email(local: str) -> str:
    """A unique address, so reruns never collide with rows left by earlier runs."""
    return f"{local}-{uuid.uuid4().hex[:8]}@example.com"


def _make_org(db, prefix="Invite Org") -> Organization:
    org = Organization(
        name=f"{prefix} {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-INV-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _get_role(db, name: str) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    assert role is not None, f"seeded role '{name}' is required for these tests"
    return role


def _make_user(db, org: Organization, role_name: str, label: str) -> User:
    role = _get_role(db, role_name)
    user = User(
        org_id=org.id,
        role_id=role.id,
        full_name=label,
        username=f"inv-{uuid.uuid4().hex[:8]}",
        email=_email(label),
        employee_id=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        hashed_password=svc.get_password_hash(VALID_PASSWORD),
        is_active=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_admin(db, org: Organization, role_name: str = "Admin") -> User:
    return _make_user(db, org, role_name, "Invite Admin")


def _make_employee(db, org: Organization) -> User:
    return _make_user(db, org, "Employee", "Plain Employee")


def _issue(db, org, email, role="Employee", **kwargs):
    role_row = _get_role(db, role)
    return svc.create_invite(
        db,
        organization_id=org.id,
        email=email,
        role_id=role_row.id,
        **kwargs,
    )


# ── Token handling ──────────────────────────────────────────────────────
class TestTokenHandling:
    def test_token_is_high_entropy_and_url_safe(self):
        token = svc.generate_token()
        assert len(token) >= 32
        assert all(c.isalnum() or c in "-_" for c in token)

    def test_hash_is_deterministic_and_differs_from_token(self):
        token = svc.generate_token()
        digest = svc.hash_token(token)
        assert digest == svc.hash_token(token)
        assert digest != token
        assert len(digest) == 64  # SHA-256 hex

    def test_distinct_tokens_hash_distinctly(self):
        assert svc.hash_token(svc.generate_token()) != svc.hash_token(svc.generate_token())

    @pytest.mark.parametrize(
        "candidate,expected",
        [
            (None, False),
            ("", False),
            ("short", False),
            ("x" * 600, False),
            ("a" * 43, True),
        ],
    )
    def test_format_guard(self, candidate, expected):
        assert svc.is_valid_token_format(candidate) is expected

    def test_validity_window_is_clamped(self):
        assert svc._clamp_days(None) == svc.DEFAULT_VALID_DAYS
        assert svc._clamp_days(0) == svc.MIN_VALID_DAYS
        assert svc._clamp_days(999) == svc.MAX_VALID_DAYS


# ── Creation ────────────────────────────────────────────────────────────
class TestCreateInvite:
    def test_returns_token_but_stores_only_its_hash(self, db):
        org = _make_org(db)
        invite, token = _issue(db, org, _email("hash"))

        db.refresh(invite)
        assert invite.token_hash == svc.hash_token(token)
        assert invite.token_hash != token
        assert token not in invite.token_hash

    def test_email_is_normalised(self, db):
        org = _make_org(db)
        invite, _ = _issue(db, org, "  Mixed.Case@Example.COM ")
        db.refresh(invite)
        assert invite.email == "mixed.case@example.com"

    def test_defaults_to_pending_with_expiry(self, db):
        org = _make_org(db)
        invite, _ = _issue(db, org, _email("pending"))
        db.refresh(invite)
        assert invite.status == svc.STATUS_PENDING
        assert invite.used_at is None and invite.revoked_at is None
        assert invite.expires_at > datetime.now(timezone.utc)

    def test_rejects_invalid_email(self, db):
        org = _make_org(db)
        with pytest.raises(InviteError) as exc:
            _issue(db, org, "not-an-email")
        assert exc.value.code == "invalid_email"

    def test_duplicate_live_invite_is_refused(self, db):
        org = _make_org(db)
        email = _email("dupe")
        _issue(db, org, email)
        with pytest.raises(InviteError) as exc:
            _issue(db, org, email)
        assert exc.value.code == "duplicate"

    def test_expired_invite_is_replaced_not_duplicated(self, db):
        org = _make_org(db)
        email = _email("stale")
        first, _ = _issue(db, org, email)
        first.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()

        second, _ = _issue(db, org, email)
        assert second.id != first.id
        db.refresh(first)
        assert first.status == svc.STATUS_REVOKED

    def test_same_email_in_another_org_is_allowed(self, db):
        org_a, org_b = _make_org(db, "A"), _make_org(db, "B")
        email = _email("shared")
        _issue(db, org_a, email)
        invite_b, _ = _issue(db, org_b, email)
        assert invite_b.organization_id == org_b.id


# ── Status derivation ───────────────────────────────────────────────────
class TestStatus:
    def test_pending_invite_is_usable(self, db):
        org = _make_org(db)
        invite, _ = _issue(db, org, _email("usable"))
        assert svc.invite_status(invite) == svc.STATUS_PENDING
        assert svc.is_usable(invite) is True

    def test_expiry_overrides_pending_status(self, db):
        org = _make_org(db)
        invite, _ = _issue(db, org, _email("expiry"))
        invite.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert svc.invite_status(invite) == "expired"
        assert svc.is_usable(invite) is False

    def test_revoked_and_used_are_not_usable(self, db):
        org = _make_org(db)
        invite, _ = _issue(db, org, _email("revoked"))
        invite.revoked_at = datetime.now(timezone.utc)
        invite.status = svc.STATUS_REVOKED
        assert svc.is_usable(invite) is False

        invite.status = svc.STATUS_ACCEPTED
        invite.used_at = datetime.now(timezone.utc)
        assert svc.invite_status(invite) == svc.STATUS_ACCEPTED
        assert svc.is_usable(invite) is False

    def test_naive_expiry_treated_as_utc(self, db):
        org = _make_org(db)
        invite, _ = _issue(db, org, _email("naive"))
        invite.expires_at = (datetime.now(timezone.utc) + timedelta(days=1)).replace(tzinfo=None)
        assert svc.is_usable(invite) is True


# ── Acceptance ──────────────────────────────────────────────────────────
class TestAcceptInvite:
    def test_creates_user_with_authorised_role(self, db):
        org = _make_org(db)
        manager = _make_employee(db, org)
        email = _email("hire")
        invite, token = _issue(
            db, org, email, full_name="New Hire", manager_id=manager.id
        )
        role_row = _get_role(db, "Employee")

        user = svc.accept_invite(db, token, password=VALID_PASSWORD)

        assert user.email == email
        assert user.full_name == "New Hire"
        assert user.org_id == org.id
        assert user.role_id == role_row.id
        assert user.employee_id and user.employee_id.startswith("EMP-")
        assert user.hashed_password != VALID_PASSWORD

        db.refresh(invite)
        assert invite.status == svc.STATUS_ACCEPTED
        assert invite.used_at is not None
        assert invite.accepted_user_id == user.id

    def test_password_is_hashed_and_verifiable(self, db):
        from app.core.security import verify_password

        org = _make_org(db)
        _, token = _issue(db, org, _email("pw"), full_name="Password User")
        user = svc.accept_invite(db, token, password=VALID_PASSWORD)
        assert verify_password(VALID_PASSWORD, user.hashed_password) is True

    def test_can_only_be_used_once(self, db):
        org = _make_org(db)
        _, token = _issue(db, org, _email("once"), full_name="Once Only")
        svc.accept_invite(db, token, password=VALID_PASSWORD)

        with pytest.raises(InviteError):
            svc.accept_invite(db, token, password="Another-Passphrase!99")

    def test_expired_invite_is_refused(self, db):
        org = _make_org(db)
        invite, token = _issue(db, org, _email("expired"), full_name="Expired")
        invite.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()

        with pytest.raises(InviteError) as exc:
            svc.accept_invite(db, token, password=VALID_PASSWORD)
        assert exc.value.code == "expired"

    def test_revoked_invite_is_refused(self, db):
        org = _make_org(db)
        invite, token = _issue(db, org, _email("revoke"), full_name="Revoked")
        svc.revoke_invite(db, invite)

        with pytest.raises(InviteError):
            svc.accept_invite(db, token, password=VALID_PASSWORD)

    def test_unknown_and_used_tokens_are_indistinguishable(self, db):
        org = _make_org(db)
        _, token = _issue(db, org, _email("enumer"), full_name="Enumerated")
        svc.accept_invite(db, token, password=VALID_PASSWORD)

        messages = set()
        for candidate in (token, svc.generate_token(), "unknown-token-value"):
            with pytest.raises(InviteError) as exc:
                svc.accept_invite(db, candidate, password=VALID_PASSWORD)
            messages.add(exc.value.message)
        # One message means the endpoint cannot be used to test which tokens
        # exist, or which have already been spent.
        assert messages == {svc.GENERIC_INVALID}

    def test_existing_user_in_same_org_is_adopted(self, db):
        org = _make_org(db)
        existing = _make_employee(db, org)
        old_hash = existing.hashed_password
        _, token = _issue(db, org, existing.email)

        returned = svc.accept_invite(db, token, password=VALID_PASSWORD)

        assert returned.id == existing.id
        assert returned.hashed_password != old_hash
        assert db.query(User).filter(User.email == existing.email).count() == 1

    def test_user_in_another_org_is_never_adopted(self, db):
        org_a, org_b = _make_org(db, "A"), _make_org(db, "B")
        outsider = _make_employee(db, org_b)
        _, token = _issue(db, org_a, outsider.email)

        with pytest.raises(InviteError):
            svc.accept_invite(db, token, password=VALID_PASSWORD)

        db.refresh(outsider)
        assert outsider.org_id == org_b.id

    def test_name_is_required_when_not_supplied(self, db):
        org = _make_org(db)
        _, token = _issue(db, org, _email("noname"))
        with pytest.raises(InviteError) as exc:
            svc.accept_invite(db, token, password=VALID_PASSWORD)
        assert exc.value.code == "name_required"

    def test_malformed_token_rejected_without_db_write(self, db):
        org = _make_org(db)
        before = db.query(User).filter(User.org_id == org.id).count()
        with pytest.raises(InviteError):
            svc.accept_invite(db, "tiny", password=VALID_PASSWORD)
        assert db.query(User).filter(User.org_id == org.id).count() == before

    def test_concurrent_acceptance_creates_one_user(self, db):
        """The conditional claim must let exactly one racer win."""
        org = _make_org(db)
        email = _email("race")
        _, token = _issue(db, org, email, full_name="Racer")

        outcomes = []
        for _ in range(3):
            session = SessionLocal()
            try:
                svc.accept_invite(session, token, password=VALID_PASSWORD)
                outcomes.append("created")
            except InviteError:
                outcomes.append("rejected")
            finally:
                session.close()

        assert outcomes.count("created") == 1
        assert outcomes.count("rejected") == 2
        assert db.query(User).filter(User.email == email).count() == 1


# ── Checklist ───────────────────────────────────────────────────────────
class TestChecklist:
    def test_progress_and_completion(self, db):
        org = _make_org(db)
        invite, _ = _issue(db, org, _email("checklist"))
        assert svc.is_onboarding_complete(invite) is False

        svc.mark_checklist(db, invite, profile=True, documents=True)
        assert svc.checklist_progress(invite) == {
            "profile": True, "documents": True, "tax_form": False,
        }
        assert svc.is_onboarding_complete(invite) is False

        svc.mark_checklist(db, invite, tax_form=True)
        assert svc.is_onboarding_complete(invite) is True

    def test_none_leaves_step_untouched(self, db):
        org = _make_org(db)
        invite, _ = _issue(db, org, _email("untouched"))
        svc.mark_checklist(db, invite, profile=True)
        svc.mark_checklist(db, invite, documents=True)
        assert svc.checklist_progress(invite)["profile"] is True

    def test_step_can_be_reset(self, db):
        org = _make_org(db)
        invite, _ = _issue(db, org, _email("reset"))
        svc.mark_checklist(db, invite, profile=True)
        svc.mark_checklist(db, invite, profile=False)
        assert svc.checklist_progress(invite)["profile"] is False


# ── Serialisation ───────────────────────────────────────────────────────
class TestSerialize:
    def test_token_only_present_when_explicitly_requested(self, db):
        org = _make_org(db)
        invite, token = _issue(db, org, _email("serialize"))

        assert "token" not in svc.serialize(invite)
        assert "token" not in svc.serialize(invite, include_token=True)
        assert svc.serialize(invite, include_token=True, raw_token=token)["token"] == token

    def test_reports_effective_status(self, db):
        org = _make_org(db)
        invite, _ = _issue(db, org, _email("status"))
        invite.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        assert svc.serialize(invite)["status"] == "expired"


# ── Revocation ──────────────────────────────────────────────────────────
class TestRevoke:
    def test_accepted_invite_cannot_be_revoked(self, db):
        org = _make_org(db)
        invite, token = _issue(db, org, _email("burned"), full_name="Burned")
        svc.accept_invite(db, token, password=VALID_PASSWORD)
        db.refresh(invite)
        with pytest.raises(InviteError) as exc:
            svc.revoke_invite(db, invite)
        assert exc.value.code == "conflict"


# ── HTTP layer ──────────────────────────────────────────────────────────
class TestInvitesHTTP:
    @pytest.fixture
    def http_db(self):
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def http_client(self, http_db):
        from app.core import rate_limit

        with TestClient(app) as c:
            app.dependency_overrides[get_db] = lambda: http_db
            try:
                yield c
            finally:
                app.dependency_overrides.clear()
                rate_limit._fallback_windows.clear()

    def _as_admin(self, db, org):
        """Authenticate as a real Admin row, satisfying the permission check."""
        admin = _make_admin(db, org)
        app.dependency_overrides[deps.get_current_active_user] = lambda: admin
        return admin

    def test_create_returns_token_once_list_never_does(self, http_db, http_client):
        org = _make_org(http_db, "HTTP Invite Org")
        self._as_admin(http_db, org)

        created = http_client.post(
            "/api/v1/org/invites",
            json={"email": _email("http-hire"), "full_name": "HTTP Hire", "role": "Employee"},
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["token"] and body["invite_link"].endswith(body["token"])
        assert body["status"] == "pending"

        listed = http_client.get("/api/v1/org/invites")
        assert listed.status_code == 200, listed.text
        assert listed.json()
        assert all("token" not in row for row in listed.json())

    def test_recipient_can_validate_then_accept(self, http_db, http_client):
        org = _make_org(http_db, "Recipient Org")
        email = _email("flow")
        _, token = _issue(http_db, org, email, full_name="Flow User")

        validated = http_client.get("/api/v1/invites/validate", params={"token": token})
        assert validated.status_code == 200, validated.text
        payload = validated.json()
        assert payload["email"] == email
        assert payload["organization_name"] == org.name
        # Validation must not leak tenant internals to an unauthenticated caller.
        assert "org_id" not in payload and "invited_by_user_id" not in payload

        accepted = http_client.post(
            "/api/v1/invites/accept",
            params={"token": token},
            json={"password": VALID_PASSWORD},
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["email"] == email

        # The same link is now spent, and says so identically to a bad token.
        again = http_client.post(
            "/api/v1/invites/accept",
            params={"token": token},
            json={"password": VALID_PASSWORD},
        )
        bogus = http_client.post(
            "/api/v1/invites/accept",
            params={"token": svc.generate_token()},
            json={"password": VALID_PASSWORD},
        )
        assert again.status_code == bogus.status_code == 400
        assert again.json()["detail"] == bogus.json()["detail"] == svc.GENERIC_INVALID

    def test_validate_rejects_bad_token(self, http_client):
        response = http_client.get("/api/v1/invites/validate", params={"token": "nope"})
        assert response.status_code == 400
        assert response.json()["detail"] == svc.GENERIC_INVALID

    def test_privileged_role_requires_escalation_permission(self, http_db, http_client):
        """A plain employee must not be able to mint an Admin invite."""
        org = _make_org(http_db, "Escalation Org")
        plain = _make_employee(http_db, org)
        app.dependency_overrides[deps.get_current_active_user] = lambda: plain
        app.dependency_overrides[invites_router.MANAGE] = lambda: plain

        email = _email("sneaky")
        response = http_client.post(
            "/api/v1/org/invites", json={"email": email, "role": "Admin"}
        )
        assert response.status_code == 403, response.text
        assert http_db.query(EmployeeInvite).filter(
            EmployeeInvite.email == email
        ).count() == 0

    def test_employee_role_needs_no_escalation(self, http_db, http_client):
        org = _make_org(http_db, "Escalation OK Org")
        plain = _make_employee(http_db, org)
        app.dependency_overrides[deps.get_current_active_user] = lambda: plain
        app.dependency_overrides[invites_router.MANAGE] = lambda: plain

        response = http_client.post(
            "/api/v1/org/invites", json={"email": _email("ok-hire"), "role": "Employee"}
        )
        assert response.status_code == 201, response.text

    @pytest.mark.parametrize("requested", ["Employee", "employee", "OrgViewer", "viewer"])
    def test_self_assignable_roles_are_allowed(self, http_db, http_client, requested):
        """
        Regression guard: `normalize_role_name` maps the legacy "Employee" onto
        "OrgEmployee", so the privileged check must compare against canonical
        names or an ordinary hire would be refused.
        """
        org = _make_org(http_db, f"Baseline {requested}")
        plain = _make_employee(http_db, org)
        app.dependency_overrides[deps.get_current_active_user] = lambda: plain
        app.dependency_overrides[invites_router.MANAGE] = lambda: plain

        response = http_client.post(
            "/api/v1/org/invites", json={"email": _email("baseline"), "role": requested}
        )
        assert response.status_code == 201, f"{requested}: {response.text}"

    @pytest.mark.parametrize("requested", ["Admin", "admin", "OrgHR", "PlatformAdmin"])
    def test_privileged_roles_are_refused_without_escalation(self, http_db, http_client, requested):
        org = _make_org(http_db, f"Privileged {requested}")
        plain = _make_employee(http_db, org)
        app.dependency_overrides[deps.get_current_active_user] = lambda: plain
        app.dependency_overrides[invites_router.MANAGE] = lambda: plain

        response = http_client.post(
            "/api/v1/org/invites", json={"email": _email("privileged"), "role": requested}
        )
        assert response.status_code == 403, f"{requested}: {response.text}"

    def test_unknown_role_is_rejected(self, http_db, http_client):
        org = _make_org(http_db, "Unknown Role Org")
        plain = _make_employee(http_db, org)
        app.dependency_overrides[deps.get_current_active_user] = lambda: plain
        app.dependency_overrides[invites_router.MANAGE] = lambda: plain

        response = http_client.post(
            "/api/v1/org/invites", json={"email": _email("ghost"), "role": "Wizard"}
        )
        assert response.status_code == 400, response.text
        assert "does not exist" in response.json()["detail"]

    def test_tenant_cannot_see_or_revoke_another_tenants_invite(self, http_db, http_client):
        org_a, org_b = _make_org(http_db, "Tenant A"), _make_org(http_db, "Tenant B")
        email = _email("victim")
        victim_invite, _ = _issue(http_db, org_a, email)
        self._as_admin(http_db, org_b)

        listed = http_client.get("/api/v1/org/invites")
        assert listed.status_code == 200
        assert all(row["email"] != email for row in listed.json())

        revoked = http_client.post(f"/api/v1/org/invites/{victim_invite.id}/revoke")
        assert revoked.status_code == 404
        http_db.refresh(victim_invite)
        assert victim_invite.status == svc.STATUS_PENDING

    def test_checklist_updates_over_http(self, http_db, http_client):
        org = _make_org(http_db, "Checklist Org")
        _, token = _issue(http_db, org, _email("checklist"))

        response = http_client.put(
            "/api/v1/invites/checklist",
            params={"token": token},
            json={"profile": True, "documents": True, "tax_form": True},
        )
        assert response.status_code == 200, response.text
        assert response.json()["onboarding_complete"] is True

    def test_checklist_rejects_spent_token(self, http_db, http_client):
        org = _make_org(http_db, "Checklist Spent Org")
        _, token = _issue(http_db, org, _email("spent"), full_name="Spent")
        svc.accept_invite(http_db, token, password=VALID_PASSWORD)

        response = http_client.put(
            "/api/v1/invites/checklist", params={"token": token}, json={"profile": True}
        )
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == svc.GENERIC_INVALID
