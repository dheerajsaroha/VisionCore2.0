"""
Password reset: issuing, delivering, and telling the account owner.

The old flow had two failures that compounded. Delivery returned early when no
SMTP credentials were configured and swallowed every provider error, while the
endpoint still reported success -- so a reset could be issued, never delivered
and never reported, and the account owner was told nothing in either case. The
second failure was that nothing ever notified the account holder at all, so
even a reset that *was* delivered gave an attacker who had taken over a mailbox
no visible signal, and gave the real owner none.

The design here has two independent channels on purpose:

* **In-app notification** is the primary one. It costs nothing, needs no
  third-party credentials, and cannot be taken down by a mail provider. It is
  what makes "the account person is notified" true even with mail
  unconfigured. It is weak on its own, since a user who has been locked out
  cannot read their notifications -- which is why it does not stand alone.

* **Email** carries the credential: the reset link and the one-time code. Both
  prove control of the mailbox, and neither can be satisfied from inside the
  app, so this channel cannot be replaced by the first.

Every request is recorded with the outcome, whatever it is. The point is that
"we emailed you" stops being an unfalsifiable claim.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.db.models.all_models import PasswordResetRequest, User
from app.services.email_transport import DeliveryResult, send_email

logger = logging.getLogger(__name__)

OTP_DIGITS = 6


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_otp(code: str) -> str:
    """
    Hash a one-time code for storage.

    Salted with the application's secret so a stolen table is not enough on its
    own: without `SECRET_KEY` an attacker cannot cheaply confirm a guessed code
    offline, which matters because six digits is only a million values.
    """
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_otp() -> str:
    """A uniform 6-digit code, drawn from `secrets` rather than `random`."""
    return f"{secrets.randbelow(10 ** OTP_DIGITS):0{OTP_DIGITS}d}"


# --------------------------------------------------------------------------- #
# throttling
# --------------------------------------------------------------------------- #

def account_throttle_state(db: Session, email: str) -> Tuple[bool, str]:
    """
    Per-address limits, on top of the per-IP limiter.

    Without these, an attacker who knows a victim's address can use the endpoint
    to flood their inbox, and can time responses to work out whether the
    account exists. Returns ``(allowed, reason)``.
    """
    normalized = (email or "").strip().lower()
    recent = (
        db.query(PasswordResetRequest)
        .filter(PasswordResetRequest.email == normalized)
        .order_by(PasswordResetRequest.created_at.desc())
        .first()
    )
    if recent is not None:
        age = (_now() - _aware(recent.created_at)).total_seconds()
        if age < settings.PASSWORD_RESET_ACCOUNT_COOLDOWN_SECONDS:
            wait = int(settings.PASSWORD_RESET_ACCOUNT_COOLDOWN_SECONDS - age)
            return False, f"Please wait {wait}s before requesting another reset."

    since = _now() - timedelta(hours=1)
    count = (
        db.query(func.count(PasswordResetRequest.id))
        .filter(
            PasswordResetRequest.email == normalized,
            PasswordResetRequest.created_at >= since,
        )
        .scalar()
        or 0
    )
    if count >= settings.PASSWORD_RESET_ACCOUNT_HOURLY_LIMIT:
        return False, "Too many reset requests for this account. Try again later."
    return True, ""


def _aware(value: Optional[datetime]) -> datetime:
    if value is None:
        return _now()
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# messages
# --------------------------------------------------------------------------- #

def _reset_link(token: str) -> str:
    return (f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?"
            f"{urlencode({'token': token})}")


def _body(link: str, otp: Optional[str], minutes: int) -> str:
    lines = [
        "We received a request to reset your password.",
        "",
        f"Open this one-time link to choose a new password:",
        f"{link}",
        "",
        f"The link expires in {minutes} minutes.",
    ]
    if otp:
        lines += [
            "",
            f"Or enter this {OTP_DIGITS}-digit code on the reset page: {otp}",
            f"The code expires in {settings.PASSWORD_RESET_OTP_EXPIRE_MINUTES} "
            "minutes and can be used at most "
            f"{settings.PASSWORD_RESET_OTP_MAX_ATTEMPTS} times.",
        ]
    lines += [
        "",
        "If you did not request this, no action is needed -- the link and code "
        "are useless to anyone else. Your current password still works.",
        "",
        "If this keeps happening, contact your administrator.",
    ]
    return "\n".join(lines)


SECURITY_SUBJECT = "Security alert: password reset requested for your account"
SECURITY_SUBJECT_CHANGED = "Security alert: your password was changed"


# --------------------------------------------------------------------------- #
# issuing
# --------------------------------------------------------------------------- #

def issue_reset(
    db: Session,
    user: User,
    *,
    request_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Mint a reset link and code for `user`, deliver them, and notify them in-app.

    Returns the token, code and delivery result so the caller can audit the
    outcome. Deliberately returns the secrets: the caller needs them to record
    the OTP hash, and the endpoint hands the code back only in development.
    """
    meta = request_meta or {}
    email = user.email.strip().lower()

    token = security.create_password_reset_token(user.id)
    jti = _jti_of(token)
    otp = generate_otp()
    link = _reset_link(token)

    delivery = send_email(
        to=user.email,
        subject=SECURITY_SUBJECT,
        body=_body(link, otp, settings.PASSWORD_RESET_EXPIRE_MINUTES),
    )
    if not delivery.delivered and delivery.status != "logged":
        logger.error(
            "Password reset delivery to user=%s ended as %s via %s: %s",
            user.id, delivery.status, delivery.provider, delivery.error,
        )

    row = PasswordResetRequest(
        user_id=user.id,
        organization_id=user.org_id,
        email=email,
        token_jti=jti,
        delivery_status=delivery.status,
        delivery_provider=delivery.provider,
        delivery_detail=(delivery.detail or None) if len(delivery.detail) < 500 else None,
        delivery_error=delivery.error or None,
        # The code is hashed; the plaintext is only ever in the sent message.
        otp_code_hash=hash_otp(otp),
        otp_expires_at=_now() + timedelta(
            minutes=settings.PASSWORD_RESET_OTP_EXPIRE_MINUTES),
        ip_address=meta.get("ip_address"),
        user_agent=(meta.get("user_agent") or "")[:255] or None,
    )
    db.add(row)
    db.flush()

    notified = _notify_in_app(
        db, user,
        title="Password reset requested",
        message=(
            "A password reset was requested for your account. If it was not "
            "you, no action is needed -- but if someone else has your password, "
            "change it now and contact your administrator."
        ),
        action_url=f"/forgot-password",
    )
    row.notified_in_app = notified
    db.commit()
    db.refresh(row)

    return {
        "request_row_id": row.id,
        "token": token,
        "otp": otp,
        "link": link,
        "delivery": delivery,
        "notified_in_app": notified,
    }


def record_unknown_request(
    db: Session,
    *,
    email: str,
    request_meta: Optional[Dict[str, Any]] = None,
) -> PasswordResetRequest:
    """
    Record a request against an address that matched no account.

    Written for two reasons. The per-address throttle needs rows to count, or
    the limit is unenforceable against addresses that do not exist. And an
    attacker spraying the endpoint should leave a trail, not a silent gap
    between "requests for unknown addresses" and "no requests at all".
    """
    meta = request_meta or {}
    row = PasswordResetRequest(
        user_id=None,
        organization_id=None,
        email=(email or "").strip().lower(),
        # No credential was issued, so nothing was delivered. `failed` rather
        # than `skipped_unconfigured`: no provider was ever asked.
        delivery_status="failed",
        delivery_provider=None,
        delivery_error="no active account for this address",
        ip_address=meta.get("ip_address"),
        user_agent=(meta.get("user_agent") or "")[:255] or None,
    )
    db.add(row)
    return row


def _jti_of(token: str) -> Optional[str]:
    try:
        from jose import jwt
        claims = jwt.get_unverified_claims(token)
        return claims.get("jti")
    except Exception:
        return None


def _notify_in_app(db: Session, user: User, *, title: str, message: str,
                   action_url: Optional[str] = None) -> bool:
    """
    Insert a durable in-app notification for the account owner.

    Uses the notifications router's `_push_notification` rather than
    `notification_service.send()`: that service's in-app branch only appends to
    an in-memory list and logs, so a reset alert built with it would evaporate
    on restart and would never appear in the user's notification feed. This path
    writes a real `notifications` row.

    Imported lazily because the notifications router imports the app, and a
    module-level import here would be circular.
    """
    try:
        from app.routers.notifications import _push_notification

        _push_notification(
            str(user.org_id), user.id,
            title=title, message=message,
            notif_type="security", action_url=action_url,
            source_event="password_reset", db=db,
        )
        return True
    except Exception:
        # Email may still be the channel that works, so a failure here is logged
        # and stepped over rather than failing the reset outright. The outcome
        # is recorded on the request row either way, so the gap is visible.
        logger.exception("Could not write in-app notification for user=%s", user.id)
        return False


def notify_password_changed(
    db: Session,
    user: User,
    *,
    source: str = "reset",
    request_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Tell the account owner their password has just changed.

    Separate from issuing the reset, because the moment that matters to the
    owner is the change itself. A password altered by anyone -- an attacker
    holding the mailbox, or an over-eager administrator -- has to be visible
    to the person it happened to.
    """
    reason = ("your password was reset"
              if source == "reset" else "your password was changed")
    notified = _notify_in_app(
        db, user,
        title="Your password was changed",
        message=(
            f"Success: {reason}. Every other signed-in session has been signed "
            "out. If this was not you, contact your administrator immediately."
        ),
        action_url="/settings/security",
    )
    delivery = send_email(
        to=user.email,
        subject=SECURITY_SUBJECT_CHANGED,
        body=(
            f"{reason.capitalize()} on your VisionCore account.\n\n"
            "If this was not you, contact your administrator immediately -- "
            "someone with access to your account may have changed it.\n"
        ),
    )
    db.commit()
    return {"notified_in_app": notified, "delivery": delivery}


# --------------------------------------------------------------------------- #
# consuming the code
# --------------------------------------------------------------------------- #

def verify_otp(db: Session, email: str, code: str) -> Tuple[Optional[PasswordResetRequest], Optional[str]]:
    """
    Check a one-time code against the newest usable request for `email`.

    Returns ``(row, error)``. The row's attempt counter is incremented on every
    check, including failures, so the budget cannot be reset by simply trying
    again.
    """
    normalized = (email or "").strip().lower()
    attempt = (code or "").strip()
    if not attempt.isdigit() or len(attempt) != OTP_DIGITS:
        return None, "Enter the 6-digit code from the email."

    row = (
        db.query(PasswordResetRequest)
        .filter(
            PasswordResetRequest.email == normalized,
            PasswordResetRequest.satisfied_at.is_(None),
            PasswordResetRequest.otp_expires_at.isnot(None),
        )
        .order_by(PasswordResetRequest.created_at.desc())
        .first()
    )
    if row is None:
        return None, "That code is no longer valid. Request a new one."

    if _aware(row.otp_expires_at) <= _now():
        return None, "That code has expired. Request a new one."

    if row.otp_attempts >= settings.PASSWORD_RESET_OTP_MAX_ATTEMPTS:
        return None, "Too many incorrect attempts. Request a new code."

    row.otp_attempts += 1
    db.commit()

    if not hmac.compare_digest(row.otp_code_hash or "", hash_otp(attempt)):
        remaining = max(
            0, settings.PASSWORD_RESET_OTP_MAX_ATTEMPTS - row.otp_attempts)
        return None, (f"That code is not correct. {remaining} attempt"
                      f"{'s' if remaining != 1 else ''} left.")

    return row, None


def consume_otp(row: PasswordResetRequest) -> None:
    """Close the request so the code cannot be replayed.

    This also retires the link issued in the same message: see
    `is_request_closed`.
    """
    row.satisfied_at = _now()


def is_request_closed(db: Session, jti: Optional[str]) -> bool:
    """
    Has this reset request already been completed by some credential?

    Consulted by the link path. Both the link and the code arrive in one
    message, so honouring the link after the owner has already reset with the
    code would leave a live credential behind -- usable by anyone who copied
    the link before the owner acted. The row ties the two together, so either
    one being used closes the request.
    """
    if not jti:
        return False
    return db.query(PasswordResetRequest).filter(
        PasswordResetRequest.token_jti == jti,
        PasswordResetRequest.satisfied_at.isnot(None),
    ).first() is not None


def consume_reset_link(db: Session, jti: str, user_id: int) -> bool:
    """Atomically claim an issued reset link in the database.

    Keeping the single-use state beside the reset request avoids making a
    valid link depend on Redis availability. The caller commits this update
    together with the password change.
    """
    result = db.execute(
        update(PasswordResetRequest)
        .where(
            PasswordResetRequest.token_jti == jti,
            PasswordResetRequest.user_id == user_id,
            PasswordResetRequest.satisfied_at.is_(None),
        )
        .values(satisfied_at=_now())
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1
