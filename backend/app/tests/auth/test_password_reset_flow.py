"""
End-to-end coverage for the password reset and change-password flow.

These exercise the real endpoints with real tokens rather than stubbing the
dependencies, because most of the interesting behaviour lives in the
interaction between the JWT, the Redis one-time store, and the rate limiter:

  * `/auth/forgot-password` is limited to 5 requests / 60s per IP
  * `/auth/reset-password` is limited to 3 requests / 300s per IP

so a naive test run trips the limiter and reports 429 for the wrong reason.
`_clear_rate_limits` resets both limiter backends -- `rate_limit_dependency`
silently falls back to an in-process counter when the Redis pipeline raises,
and under TestClient each request gets a fresh event loop, so the fallback is
often the one actually enforcing.
"""
from __future__ import annotations

import datetime as _dt
import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from app.core import security
from app.core.security import get_password_hash, verify_password
from app.db.models.all_models import (
    AttendanceSession,
    Branch,
    Department,
    JobPosition,
    LeaveRequest,
    LeaveType,
    Organization,
    OrganizationSubscription,
    PerformanceCycle,
    PerformanceReview,
    Payroll,
    Role,
    User,
    UserSession,
)

ORIGINAL = "Orig@Pass1"
REPLACED = "BrandNew@Pass2"


@pytest.fixture()
def client():
    return TestClient(app)


def _org(db: Session) -> Organization:
    o = Organization(
        name=f"ResetFlow {uuid.uuid4().hex[:6]}",
        legal_id=f"RSTFLW-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


def _user(db: Session, org, tag: str, role_name="OrgAdmin",
          password=ORIGINAL, is_active=1, is_deleted=0) -> User:
    role = db.query(Role).filter(Role.name == role_name).first()
    slug = f"rst_{tag}_{uuid.uuid4().hex[:6]}"
    u = User(
        email=f"{slug}@example.test",
        username=slug,
        employee_id=slug.upper(),
        full_name=f"Reset Probe {tag}",
        org_id=org.id,
        role_id=role.id,
        is_active=is_active,
        is_deleted=is_deleted,
        hashed_password=get_password_hash(password),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _issue(client, email) -> str | None:
    r = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert r.status_code == 200, r.text[:200]
    url = r.json().get("reset_url")
    if not url:
        return None
    return parse_qs(urlparse(url).query).get("token", [None])[0]


@pytest.fixture()
def tenant(db):
    org = _org(db)
    yield org
    uid = db.query(User.id).filter(User.org_id == org.id)
    # user_sessions is created by every login in these tests and also points
    # at users.id, so it has to go first.
    for model, col in ((UserSession, "user_id"),
                       (PerformanceReview, "reviewee_user_id"),
                       (PerformanceReview, "reviewer_user_id"),
                       (PerformanceCycle, "created_by_user_id"),
                       (LeaveRequest, "user_id"),
                       (LeaveRequest, "approver_user_id")):
        db.query(model).filter(getattr(model, col).in_(uid)).delete(
            synchronize_session=False)
    for model, col in ((Payroll, "org_id"), (AttendanceSession, "org_id"),
                       (JobPosition, "org_id"), (Branch, "org_id"),
                       (Department, "org_id")):
        db.query(model).filter(getattr(model, col) == org.id).delete(
            synchronize_session=False)
    for model in (LeaveRequest, LeaveType, PerformanceReview, PerformanceCycle,
                  OrganizationSubscription):
        db.query(model).filter(model.organization_id == org.id).delete(
            synchronize_session=False)
    db.query(User).filter(User.org_id == org.id).delete(synchronize_session=False)
    db.query(Organization).filter(Organization.id == org.id).delete(
        synchronize_session=False)
    db.commit()


class TestHappyPath:
    def test_forgot_password_issues_a_link_and_reset_actually_changes_it(
        self, client, db, tenant
    ):
        u = _user(db, tenant, "happy")
        token = _issue(client, u.email)
        assert token, "development build should return the reset_url with a token"

        r = client.post("/api/v1/auth/reset-password",
                        json={"token": token, "new_password": REPLACED})
        assert r.status_code == 200, r.text[:200]

        assert client.post("/api/v1/auth/login",
                           data={"username": u.email, "password": ORIGINAL}
                           ).status_code == 401
        assert client.post("/api/v1/auth/login",
                           data={"username": u.email, "password": REPLACED}
                           ).status_code == 200

        db.expire_all()
        fresh = db.query(User).get(u.id)
        assert verify_password(REPLACED, fresh.hashed_password)
        assert not verify_password(ORIGINAL, fresh.hashed_password)

    def test_link_points_at_the_frontend_reset_route(self, client, db, tenant):
        u = _user(db, tenant, "link")
        r = client.post("/api/v1/auth/forgot-password", json={"email": u.email})
        assert "/reset-password?token=" in r.json()["reset_url"]

    def test_reset_link_works_without_redis_one_time_store(
        self, client, db, tenant, monkeypatch
    ):
        u = _user(db, tenant, "no_redis")
        token = _issue(client, u.email)

        async def redis_unavailable(*_args, **_kwargs):
            return False

        monkeypatch.setattr(security, "consume_one_time_token", redis_unavailable)
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": REPLACED},
        )

        assert response.status_code == 200, response.text[:200]
        db.expire_all()
        assert verify_password(REPLACED, db.query(User).get(u.id).hashed_password)


class TestTokenIsSingleUse:
    def test_replaying_a_consumed_token_is_rejected(self, client, db, tenant):
        u = _user(db, tenant, "single")
        token = _issue(client, u.email)
        assert client.post("/api/v1/auth/reset-password",
                           json={"token": token, "new_password": REPLACED}
                           ).status_code == 200
        again = client.post("/api/v1/auth/reset-password",
                            json={"token": token, "new_password": "Third@Pass3"})
        assert again.status_code == 400
        # and the second attempt must not have changed anything
        db.expire_all()
        assert verify_password(REPLACED, db.query(User).get(u.id).hashed_password)


class TestForgedTokensRejected:
    @pytest.mark.parametrize("bad", ["", "not-a-jwt", "a.b.c"])
    def test_malformed_tokens_are_rejected(self, client, db, tenant, bad):
        _user(db, tenant, f"bad{bad[:3] or 'x'}")
        r = client.post("/api/v1/auth/reset-password",
                        json={"token": bad, "new_password": REPLACED})
        assert r.status_code == 400

    def test_token_signed_for_another_purpose_is_rejected(self, client, db, tenant):
        u = _user(db, tenant, "wrongtype")
        now = _dt.datetime.now(_dt.timezone.utc)
        wrong = security.jwt.encode(
            {"sub": str(u.id), "type": "access", "jti": uuid.uuid4().hex,
             "exp": now + _dt.timedelta(minutes=10), "iat": now},
            security.settings.SECRET_KEY, algorithm=security.ALGORITHM)
        r = client.post("/api/v1/auth/reset-password",
                        json={"token": wrong, "new_password": REPLACED})
        assert r.status_code == 400, "a non-reset JWT must not reset a password"

    def test_expired_token_is_rejected(self, client, db, tenant):
        u = _user(db, tenant, "expired")
        now = _dt.datetime.now(_dt.timezone.utc)
        token = security.jwt.encode(
            {"sub": str(u.id), "type": "password_reset", "jti": uuid.uuid4().hex,
             "exp": now - _dt.timedelta(minutes=5),
             "iat": now - _dt.timedelta(minutes=35)},
            security.settings.SECRET_KEY, algorithm=security.ALGORITHM)
        r = client.post("/api/v1/auth/reset-password",
                        json={"token": token, "new_password": REPLACED})
        assert r.status_code == 400

    def test_tampered_signature_is_rejected(self, client, db, tenant):
        u = _user(db, tenant, "tampered")
        token = _issue(client, u.email)
        r = client.post("/api/v1/auth/reset-password",
                        json={"token": token[:-3] + "aaa", "new_password": REPLACED})
        assert r.status_code == 400


class TestPasswordPolicy:
    @pytest.mark.parametrize("weak,expected", [
        ("Ab1!xy", "at least 8"),
        ("weak@pass1", "uppercase"),
        ("WEAK@PASS1", "lowercase"),
        ("Weak@Pass!", "digit"),
        ("WeakPass12", "special"),
    ])
    def test_weak_passwords_are_rejected(self, client, db, tenant, weak, expected):
        """The reset page used to advertise only the 8-character rule, so
        users hit repeated 422s -- and with 3 attempts per 5 minutes, a lockout."""
        u = _user(db, tenant, f"weak{abs(hash(weak)) % 9999}")
        token = _issue(client, u.email)
        r = client.post("/api/v1/auth/reset-password",
                        json={"token": token, "new_password": weak})
        assert r.status_code == 422, f"{weak!r} should be rejected"
        assert expected in r.json()["detail"].lower()
        db.expire_all()
        assert verify_password(ORIGINAL, db.query(User).get(u.id).hashed_password), \
            "a rejected password must not be written"


class TestNoUserEnumeration:
    def test_unknown_and_known_email_are_indistinguishable(self, client, db, tenant):
        known = _user(db, tenant, "known")
        ghost = f"ghost_{uuid.uuid4().hex[:8]}@example.test"
        r_ghost = client.post("/api/v1/auth/forgot-password", json={"email": ghost})
        r_known = client.post("/api/v1/auth/forgot-password", json={"email": known.email})
        assert r_ghost.status_code == r_known.status_code == 200
        assert r_ghost.json()["detail"] == r_known.json()["detail"]
        assert "reset_url" not in r_ghost.json(), \
            "an unknown address must not be distinguishable from a known one"

    @pytest.mark.parametrize("state", ["inactive", "deleted"])
    def test_unusable_accounts_get_the_same_generic_response(self, client, db, tenant, state):
        u = _user(
            db, tenant, state,
            is_active=0 if state == "inactive" else 1,
            is_deleted=1 if state == "deleted" else 0,
        )
        r = client.post("/api/v1/auth/forgot-password", json={"email": u.email})
        assert r.status_code == 200
        assert "reset_url" not in r.json(), \
            f"a {state} account must not receive a reset link"

    def test_inactive_account_cannot_log_in(self, client, db, tenant):
        u = _user(db, tenant, "suspended", is_active=0)
        r = client.post("/api/v1/auth/login",
                        data={"username": u.email, "password": ORIGINAL})
        assert r.status_code == 423


class TestRateLimiting:
    def test_reset_password_is_rate_limited(self, client, db, tenant):
        _user(db, tenant, "rl")
        codes = [
            client.post("/api/v1/auth/reset-password",
                        json={"token": "x", "new_password": REPLACED}).status_code
            for _ in range(6)
        ]
        assert 429 in codes, f"expected a 429 within {codes}"


class TestChangePassword:
    def _token(self, client, user, password):
        r = client.post("/api/v1/auth/login",
                        data={"username": user.email, "password": password})
        assert r.status_code == 200, r.text[:200]
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_change_password_updates_the_credential(self, client, db, tenant):
        u = _user(db, tenant, "chpw")
        h = self._token(client, u, ORIGINAL)
        r = client.post("/api/v1/auth/change-password", headers=h,
                        json={"current_password": ORIGINAL, "new_password": REPLACED})
        assert r.status_code == 200, r.text[:200]
        db.expire_all()
        assert verify_password(REPLACED, db.query(User).get(u.id).hashed_password)

    def test_wrong_current_password_is_refused(self, client, db, tenant):
        u = _user(db, tenant, "chpwwrong")
        h = self._token(client, u, ORIGINAL)
        r = client.post("/api/v1/auth/change-password", headers=h,
                        json={"current_password": "Wr0ng@Pass", "new_password": REPLACED})
        assert r.status_code == 400
        db.expire_all()
        assert verify_password(ORIGINAL, db.query(User).get(u.id).hashed_password)

    def test_weak_new_password_is_refused(self, client, db, tenant):
        u = _user(db, tenant, "chpwweak")
        h = self._token(client, u, ORIGINAL)
        r = client.post("/api/v1/auth/change-password", headers=h,
                        json={"current_password": ORIGINAL, "new_password": "weak"})
        assert r.status_code == 422

    def test_change_password_requires_authentication(self, client, db, tenant):
        _user(db, tenant, "chpwnoauth")
        r = client.post("/api/v1/auth/change-password",
                        json={"current_password": ORIGINAL, "new_password": REPLACED})
        assert r.status_code in (401, 403)

    def test_cannot_change_another_users_password(self, client, db, tenant):
        """Self-service only: supplying a victim id must not help, because the
        endpoint reads the subject from the token, not the body."""
        victim = _user(db, tenant, "victim")
        attacker = _user(db, tenant, "attacker")
        h = self._token(client, attacker, ORIGINAL)
        r = client.post("/api/v1/auth/change-password", headers=h,
                        json={"current_password": ORIGINAL, "new_password": REPLACED,
                              "user_id": victim.id})
        assert r.status_code == 200
        db.expire_all()
        assert verify_password(ORIGINAL, db.query(User).get(victim.id).hashed_password), \
            "the attacker's own change must not touch the victim's password"
