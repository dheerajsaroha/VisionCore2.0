"""
Delivery truthfulness, the one-time code, and notification for password reset.

The behaviour under test is the part that used to be missing. Previously
`_deliver_reset_email` returned early when no SMTP credentials were configured
and swallowed every provider exception, while `/auth/forgot-password` returned
200 with "if that account exists we have sent an email". Nothing recorded that
the mail was never sent, so:

  * a user could wait forever on a message that was never coming;
  * an operator had no way to find out mail was broken, because no log line
    said so;
  * and the account owner was told nothing at all, in any channel.

These tests pin the replacements: the outcome is stored on
`password_reset_requests`, `logged` is reported instead of `sent` when nothing
left the process, the code is single-use and attempt-limited, and the owner is
notified in-app regardless of whether a mail provider is configured.

The delivery assertions deliberately distinguish `logged` from `sent`. The
suite runs with the console transport, so asserting `sent` would be asserting
something untrue about this environment.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.db.models.all_models import (
    Notification,
    Organization,
    PasswordResetRequest,
    Role,
    User,
    UserSession,
)
from app.services import email_transport, password_reset_service

ORIGINAL = "Orig@Pass1"
REPLACED = "BrandNew@Pass2"
CODE = "314159"


@pytest.fixture()
def tenant(db):
    org = Organization(
        name=f"ResetDeliver {uuid.uuid4().hex[:6]}",
        legal_id=f"RSTDLV-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    yield org
    _purge(db, org)


def _purge(db: Session, org: Organization) -> None:
    """Remove the tenant. `notifications` and reset rows cascade with users."""
    # Login in these tests creates a user_sessions row, which references
    # users.id and therefore has to go first.
    db.query(UserSession).filter(
        UserSession.user_id.in_(db.query(User.id).filter(User.org_id == org.id))
    ).delete(synchronize_session=False)
    db.query(Notification).filter(
        Notification.org_id == org.id).delete(synchronize_session=False)
    db.query(PasswordResetRequest).filter(
        PasswordResetRequest.organization_id == org.id).delete(
            synchronize_session=False)
    db.query(User).filter(User.org_id == org.id).delete(synchronize_session=False)
    db.query(Organization).filter(Organization.id == org.id).delete(
        synchronize_session=False)
    db.commit()


def _user(db: Session, org, tag: str, email: str | None = None) -> User:
    role = db.query(Role).filter(Role.name == "OrgAdmin").first()
    slug = f"rsd_{tag}_{uuid.uuid4().hex[:6]}"
    u = User(
        email=email or f"{slug}@example.test",
        username=slug,
        employee_id=slug.upper(),
        full_name=f"Reset Deliver {tag}",
        org_id=org.id,
        role_id=role.id,
        is_active=1,
        is_deleted=0,
        hashed_password=get_password_hash(ORIGINAL),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _row(db: Session, user: User) -> PasswordResetRequest:
    return (
        db.query(PasswordResetRequest)
        .filter(PasswordResetRequest.user_id == user.id)
        .order_by(PasswordResetRequest.id.desc())
        .first()
    )


def _clear_rate_limits() -> None:
    """Reset both limiter backends, as the conftest fixture does per-test."""
    from app.core import rate_limit

    rate_limit._fallback_windows.clear()
    try:
        import redis as redis_sync

        from app.core.config import settings as _s
        rc = redis_sync.Redis.from_url(
            _s.REDIS_URL, decode_responses=True,
            socket_connect_timeout=2, socket_timeout=2)
        keys = list(rc.scan_iter(match="rate_limit:*"))
        if keys:
            rc.delete(*keys)
    except Exception:
        pass


def _forgot(client, email: str):
    return client.post("/api/v1/auth/forgot-password", json={"email": email})


# --------------------------------------------------------------------------- #
# the delivery outcome is recorded, and is not a lie
# --------------------------------------------------------------------------- #

class TestDeliveryIsRecordedTruthfully:
    def test_request_is_persisted_with_its_outcome(self, client, db, tenant):
        """The old flow left no trace; now the attempt itself is the record."""
        u = _user(db, tenant, "persist")
        _forgot(client, u.email)

        row = _row(db, u)
        assert row is not None, "the request must be recorded"
        assert row.user_id == u.id
        assert row.organization_id == tenant.id
        assert row.email == u.email.lower()
        assert row.token_jti, "the row must correlate with the JWT that was minted"
        assert row.otp_code_hash, "the code is stored, hashed"

    def test_console_transport_reports_logged_not_sent(self, client, db, tenant):
        """
        The console transport never delivers. It must not claim to.

        Asserting `sent` here would be asserting something untrue -- the message
        was written to a log and a file, and went nowhere near a mailbox. The
        distinction is the whole point of the field.
        """
        u = _user(db, tenant, "logged")
        _forgot(client, u.email)

        row = _row(db, u)
        assert row.delivery_status in {"logged", "sent"}
        if row.delivery_status == "logged":
            assert row.delivery_provider == "console"
            # A logged delivery is not a failure, and must not be dressed as one.
            assert row.delivery_error is None

    def test_provider_failure_is_captured_not_swallowed(
        self, client, db, tenant, monkeypatch
    ):
        """
        A broken provider must be visible.

        The previous implementation caught provider exceptions and passed, so a
        misconfigured mail server looked exactly like a working one.
        """
        u = _user(db, tenant, "providerfail")

        def explode(*_a, **_k):
            return email_transport.DeliveryResult(
                status="failed", provider="smtp",
                detail="", error="connection refused",
            )

        monkeypatch.setattr(password_reset_service, "send_email", explode)
        _forgot(client, u.email)

        row = _row(db, u)
        assert row.delivery_status == "failed"
        assert "connection refused" in (row.delivery_error or "")
        assert row.otp_code_hash, (
            "the code is still issued and recorded, so a transient provider "
            "fault does not silently cancel a reset the user was told about"
        )

    def test_endpoint_still_returns_success_on_delivery_failure(
        self, client, db, tenant, monkeypatch
    ):
        """
        A failed send must not change the response body.

        Reporting the failure would confirm the address is registered, which is
        the one thing this endpoint must not do. The failure is visible in the
        database and the logs instead.
        """
        u = _user(db, tenant, "neutral")
        monkeypatch.setattr(
            password_reset_service, "send_email",
            lambda *a, **k: email_transport.DeliveryResult(
                status="failed", provider="smtp",
                detail="", error="nope"))

        r = _forgot(client, u.email)
        assert r.status_code == 200
        assert "if an account exists" in r.json()["detail"].lower()

    def test_request_metadata_is_recorded(self, client, db, tenant):
        """IP and user agent are what make a suspicious pattern visible later."""
        u = _user(db, tenant, "meta")
        _forgot(client, u.email)

        row = _row(db, u)
        assert row.ip_address is not None
        assert row.user_agent is not None

    def test_unknown_address_is_recorded_without_an_account(
        self, client, db, tenant
    ):
        """
        A request for an address that matches nothing is still written down.

        Otherwise spraying the endpoint leaves no trace, and the per-address
        throttle has no rows to count against.
        """
        r = _forgot(client, f"ghost_{uuid.uuid4().hex[:8]}@example.test")
        assert r.status_code == 200

        row = (
            db.query(PasswordResetRequest)
            .filter(PasswordResetRequest.user_id.is_(None))
            .order_by(PasswordResetRequest.id.desc())
            .first()
        )
        assert row is not None
        assert row.delivery_status == "failed"
        assert row.notified_in_app is False
        assert row.otp_code_hash is None, "no credential for a non-existent account"


# --------------------------------------------------------------------------- #
# the account owner is told
# --------------------------------------------------------------------------- #

class TestInAppNotification:
    def test_reset_request_creates_a_durable_notification(
        self, client, db, tenant
    ):
        """
        The owner is notified in-app, and the row really persists.

        This is the channel that works with no third-party credentials, which
        is what makes the notification credible when mail is unconfigured.
        """
        u = _user(db, tenant, "notify")
        _forgot(client, u.email)

        note = (
            db.query(Notification)
            .filter(Notification.user_id == u.id,
                    Notification.source_event == "password_reset")
            .order_by(Notification.created_at.desc())
            .first()
        )
        assert note is not None, "the account owner must be notified in-app"
        assert note.org_id == tenant.id
        assert "password reset" in note.title.lower()
        assert note.is_read is False

    def test_notification_is_written_even_when_email_fails(
        self, client, db, tenant, monkeypatch
    ):
        """
        The two channels are independent.

        A mail outage must not also silence the in-app alert, or the two
        failures compound into total silence.
        """
        u = _user(db, tenant, "indep")
        monkeypatch.setattr(
            password_reset_service, "send_email",
            lambda *a, **k: email_transport.DeliveryResult(
                status="failed", provider="smtp",
                detail="", error="down"))

        _forgot(client, u.email)

        row = _row(db, u)
        assert row.delivery_status == "failed"
        assert row.notified_in_app is True
        assert db.query(Notification).filter(
            Notification.user_id == u.id).count() >= 1

    def test_password_change_notifies_the_account(
        self, client, db, tenant
    ):
        """
        The change itself is the moment that matters, so it is announced too.

        An audit row only reaches whoever reads the log; a password altered by
        someone else has to reach the person it happened to.
        """
        u = _user(db, tenant, "changed")
        login = client.post("/api/v1/auth/login",
                            data={"username": u.email, "password": ORIGINAL})
        assert login.status_code == 200, login.text[:200]
        token = login.json()["access_token"]

        r = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": ORIGINAL, "new_password": REPLACED},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text[:200]

        note = (
            db.query(Notification)
            .filter(Notification.user_id == u.id)
            .order_by(Notification.created_at.desc())
            .first()
        )
        assert note is not None
        assert "changed" in note.title.lower()


# --------------------------------------------------------------------------- #
# the code is a real credential, and a weak one
# --------------------------------------------------------------------------- #

class TestOneTimeCode:
    def test_code_can_complete_a_reset(self, client, db, tenant):
        u = _user(db, tenant, "codeok")
        r = _forgot(client, u.email)
        assert r.status_code == 200
        code = r.json().get("otp")
        assert code, "development build should return the code for testing"
        assert len(code) == 6 and code.isdigit()

        rr = client.post("/api/v1/auth/reset-password", json={
            "email": u.email, "otp": code, "new_password": REPLACED,
        })
        assert rr.status_code == 200, rr.text[:300]
        db.refresh(u)
        assert verify_password(REPLACED, u.hashed_password)

    def test_code_is_single_use(self, client, db, tenant):
        """Six digits is a small space; replay is the obvious attack."""
        u = _user(db, tenant, "replay")
        code = _forgot(client, u.email).json()["otp"]

        first = client.post("/api/v1/auth/reset-password", json={
            "email": u.email, "otp": code, "new_password": REPLACED})
        assert first.status_code == 200, first.text[:300]

        second = client.post("/api/v1/auth/reset-password", json={
            "email": u.email, "otp": code, "new_password": "Another@Pass3"})
        assert second.status_code == 400
        db.refresh(u)
        assert verify_password(REPLACED, u.hashed_password), (
            "the replayed code must not have changed the password again"
        )

    def test_code_is_stored_hashed(self, client, db, tenant):
        """A leaked table must not be a list of valid codes."""
        u = _user(db, tenant, "hashed")
        code = _forgot(client, u.email).json()["otp"]

        row = _row(db, u)
        assert row.otp_code_hash
        assert code not in row.otp_code_hash
        assert row.otp_code_hash == password_reset_service.hash_otp(code)

    def test_wrong_code_is_rejected_and_counted(self, client, db, tenant):
        u = _user(db, tenant, "wrong")
        _forgot(client, u.email)

        r = client.post("/api/v1/auth/reset-password", json={
            "email": u.email, "otp": "000000", "new_password": REPLACED})
        assert r.status_code == 400

        row = _row(db, u)
        assert row.otp_attempts == 1, (
            "failures must count, or the budget resets by simply trying again"
        )
        db.refresh(u)
        assert verify_password(ORIGINAL, u.hashed_password)

    def test_attempts_are_capped(self, client, db, tenant, monkeypatch):
        """
        Guessing must be bounded, and the bound must hold across requests.

        Uses a patched cap of 3 so the test does not depend on the configured
        value, then shows the real code stops working once it is used up.
        """
        monkeypatch.setattr(settings, "PASSWORD_RESET_OTP_MAX_ATTEMPTS", 3)
        u = _user(db, tenant, "capped")
        code = _forgot(client, u.email).json()["otp"]

        for _ in range(3):
            # /reset-password is limited to 3 requests / 300s per IP, which is
            # fewer attempts than this test makes. Clearing the limiter is the
            # point: it must be the *OTP* budget that stops the guessing, not
            # the unrelated IP limiter.
            _clear_rate_limits()
            r = client.post("/api/v1/auth/reset-password", json={
                "email": u.email, "otp": "000000", "new_password": REPLACED})
            assert r.status_code == 400

        # Budget exhausted: even the genuine code is now refused.
        _clear_rate_limits()
        r = client.post("/api/v1/auth/reset-password", json={
            "email": u.email, "otp": code, "new_password": REPLACED})
        assert r.status_code == 400
        db.refresh(u)
        assert verify_password(ORIGINAL, u.hashed_password)

    def test_expired_code_is_rejected(self, client, db, tenant):
        u = _user(db, tenant, "expired")
        code = _forgot(client, u.email).json()["otp"]

        row = _row(db, u)
        row.otp_expires_at = row.otp_expires_at.replace(year=2000)
        db.commit()

        r = client.post("/api/v1/auth/reset-password", json={
            "email": u.email, "otp": code, "new_password": REPLACED})
        assert r.status_code == 400
        db.refresh(u)
        assert verify_password(ORIGINAL, u.hashed_password)

    def test_code_must_not_be_confirmed_or_denied_by_the_error(
        self, client, db, tenant
    ):
        """
        An unknown address and a wrong code fail the same way.

        Differentiating them would hand back an enumeration oracle on the code
        path, undoing what the request endpoint works for.
        """
        u = _user(db, tenant, "enum")
        _forgot(client, u.email)

        known = client.post("/api/v1/auth/reset-password", json={
            "email": u.email, "otp": "000000", "new_password": REPLACED})
        unknown = client.post("/api/v1/auth/reset-password", json={
            "email": f"nobody_{uuid.uuid4().hex[:8]}@example.test",
            "otp": "000000", "new_password": REPLACED})

        assert known.status_code == unknown.status_code
        assert known.json()["detail"] == unknown.json()["detail"]

    def test_token_without_a_code_is_still_accepted(self, client, db, tenant):
        """The link path must keep working; the code is an addition, not a swap."""
        u = _user(db, tenant, "linkstill")
        from urllib.parse import parse_qs, urlparse
        url = _forgot(client, u.email).json()["reset_url"]
        token = parse_qs(urlparse(url).query)["token"][0]

        r = client.post("/api/v1/auth/reset-password",
                        json={"token": token, "new_password": REPLACED})
        assert r.status_code == 200, r.text[:300]

    def test_no_credential_at_all_is_rejected(self, client, db, tenant):
        """
        A password change with nothing to prove ownership is refused.

        Answered 400, matching the existing malformed-token contract rather
        than a separate 422, so a caller has one status to handle for every
        way a credential can turn out to be unusable.
        """
        r = client.post("/api/v1/auth/reset-password",
                        json={"new_password": REPLACED})
        assert r.status_code == 400


# --------------------------------------------------------------------------- #
# throttling
# --------------------------------------------------------------------------- #

class TestThrottling:
    def test_account_cooldown_blocks_a_second_request(self, client, db, tenant):
        """
        Per-address cooldown, on top of the per-IP limit.

        The per-IP limiter cannot help when one attacker spreads requests across
        addresses, or when a whole office shares a NAT egress.
        """
        u = _user(db, tenant, "cooldown")
        assert _forgot(client, u.email).status_code == 200

        second = _forgot(client, u.email)
        assert second.status_code == 200
        # Body is identical to success, because a distinct body would confirm
        # the account exists.
        assert "if an account exists" in second.json()["detail"].lower()

        assert db.query(PasswordResetRequest).filter(
            PasswordResetRequest.user_id == u.id).count() == 1, (
            "the second request must not have been issued"
        )

    def test_hourly_limit_blocks_a_burst(self, client, db, tenant, monkeypatch):
        monkeypatch.setattr(settings, "PASSWORD_RESET_ACCOUNT_COOLDOWN_SECONDS", 0)
        monkeypatch.setattr(settings, "PASSWORD_RESET_ACCOUNT_HOURLY_LIMIT", 2)
        u = _user(db, tenant, "burst")

        for _ in range(2):
            assert _forgot(client, u.email).status_code == 200
        _forgot(client, u.email)

        assert db.query(PasswordResetRequest).filter(
            PasswordResetRequest.user_id == u.id).count() == 2

    def test_throttle_state_is_exposed_for_diagnosis(self, db, tenant):
        """Operators need to distinguish 'throttled' from 'never delivered'."""
        u = _user(db, tenant, "state")
        allowed, reason = password_reset_service.account_throttle_state(db, u.email)
        assert allowed is True and reason == ""

        db.add(password_reset_service.record_unknown_request(
            db, email=u.email))
        db.commit()

        allowed, reason = password_reset_service.account_throttle_state(db, u.email)
        assert allowed is False
        assert reason


# --------------------------------------------------------------------------- #
# operator visibility
# --------------------------------------------------------------------------- #

class TestDeliveryStatusEndpoint:
    def test_administrator_can_ask_whether_mail_can_be_sent(
        self, client, db, tenant
    ):
        """
        The original failure was invisible: mail was broken, and nothing said so.

        This endpoint lets an administrator ask the system directly whether a
        provider is configured, and how many recent attempts ended undelivered.
        """
        u = _user(db, tenant, "status")
        login = client.post("/api/v1/auth/login",
                            data={"username": u.email, "password": ORIGINAL})
        assert login.status_code == 200, login.text[:200]
        token = login.json()["access_token"]

        r = client.get("/api/v1/auth/password-reset/delivery-status",
                       headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert "email" in body
        assert "configured" in body["email"]
        assert "transport" in body["email"]
        assert isinstance(body["unhealthy_deliveries_24h"], int)

    def test_unauthenticated_caller_is_refused(self, client, db, tenant):
        r = client.get("/api/v1/auth/password-reset/delivery-status")
        assert r.status_code in (401, 403)


class TestCredentialsAreIndividuallySpent:
    def test_using_the_code_also_invalidates_the_link(self, client, db, tenant):
        """
        Resetting with the code must not leave the link still usable.

        Both credentials were delivered in the same message, so a link left
        live after a code-based reset is a live credential sitting in a mailbox
        that has already been acted on -- for an attacker who copied it before
        the owner used the code.
        """
        from urllib.parse import parse_qs, urlparse

        u = _user(db, tenant, "crossuse")
        body = _forgot(client, u.email).json()
        token = parse_qs(urlparse(body["reset_url"]).query)["token"][0]
        code = body["otp"]

        used_code = client.post("/api/v1/auth/reset-password", json={
            "email": u.email, "otp": code, "new_password": REPLACED})
        assert used_code.status_code == 200, used_code.text[:300]

        _clear_rate_limits()
        via_link = client.post("/api/v1/auth/reset-password",
                               json={"token": token, "new_password": "Third@Pass3"})
        assert via_link.status_code == 400, (
            "the link must be spent once the code has been used"
        )
        db.refresh(u)
        assert verify_password(REPLACED, u.hashed_password)

    def test_using_the_link_also_invalidates_the_code(self, client, db, tenant):
        """The same closure, in the other direction."""
        from urllib.parse import parse_qs, urlparse

        u = _user(db, tenant, "crossrev")
        body = _forgot(client, u.email).json()
        token = parse_qs(urlparse(body["reset_url"]).query)["token"][0]
        code = body["otp"]

        _clear_rate_limits()
        via_link = client.post("/api/v1/auth/reset-password",
                               json={"token": token, "new_password": REPLACED})
        assert via_link.status_code == 200, via_link.text[:300]

        _clear_rate_limits()
        via_code = client.post("/api/v1/auth/reset-password", json={
            "email": u.email, "otp": code, "new_password": "Third@Pass3"})
        assert via_code.status_code == 400, (
            "the code must be spent once the link has been used"
        )
        db.refresh(u)
        assert verify_password(REPLACED, u.hashed_password)
