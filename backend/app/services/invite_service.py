"""
Employee onboarding invites.

A magic-link invite lets an administrator add a new hire without the new hire
needing a password, and without the administrator setting one on their behalf.

Security properties this module is responsible for:

* **No plaintext token at rest.** Only a SHA-256 hash is stored, so a database
  dump cannot be replayed into working onboarding links.
* **Single use, enforced atomically.** Accepting marks the invite used inside a
  conditional UPDATE, so two concurrent requests cannot both create a user.
* **No token enumeration.** Validation reports the same message whether the
  token is unknown, expired, revoked, or already used.
* **Role authorisation happens at creation time,** by an authenticated
  administrator who is already subject to the privilege-escalation rules.
  Accepting the link has no authenticated actor, so it applies the role that
  was already authorised.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.all_models import EmployeeInvite, EmploymentRecord, User
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)

# 32 bytes of entropy: the token is a bearer credential, so it must not be
# guessable even at a low attempt rate.
TOKEN_BYTES = 32
TOKEN_NIBBLES = TOKEN_BYTES * 2

DEFAULT_VALID_DAYS = 7
MIN_VALID_DAYS = 1
MAX_VALID_DAYS = 30

STATUS_PENDING = "pending"
STATUS_ACCEPTED = "accepted"
STATUS_REVOKED = "revoked"

# One message for every failure mode, so the endpoint cannot be used to test
# which tokens exist.
GENERIC_INVALID = "This invitation link is invalid, expired, or has already been used."


class InviteError(Exception):
    """Rejection of an invite operation, with a caller-facing message."""

    def __init__(self, message: str, *, code: str = "invalid"):
        super().__init__(message)
        self.message = message
        self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def generate_token() -> str:
    """A URL-safe bearer token."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(raw_token: str) -> str:
    """
    Hash a raw invite token for storage and lookup.

    The token already carries 256 bits of entropy, so a fast digest is
    appropriate here: this is not a low-entropy password being protected
    against dictionary attack.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def is_valid_token_format(raw_token: Optional[str]) -> bool:
    """Reject obviously malformed tokens before touching the database."""
    if not raw_token or not isinstance(raw_token, str):
        return False
    if len(raw_token) > 512:
        return False
    return len(raw_token) >= 16


def _clamp_days(days: Optional[int]) -> int:
    if days is None:
        return DEFAULT_VALID_DAYS
    return max(MIN_VALID_DAYS, min(MAX_VALID_DAYS, int(days)))


def create_invite(
    db: Session,
    *,
    organization_id,
    email: str,
    role_id: int,
    department_id: Optional[int] = None,
    manager_id: Optional[int] = None,
    position_id: Optional[int] = None,
    full_name: Optional[str] = None,
    invited_by_user_id: Optional[int] = None,
    valid_days: Optional[int] = None,
) -> Tuple[EmployeeInvite, str]:
    """
    Create an invite and return it together with the raw token.

    The raw token is returned exactly once. It is not recoverable afterwards,
    by design: only its hash is stored.
    """
    normalized_email = (email or "").strip().lower()
    if not normalized_email or "@" not in normalized_email:
        raise InviteError("A valid email address is required.", code="invalid_email")

    # A live invite for the same address would shadow this one, so refuse
    # rather than silently creating a second link.
    existing = (
        db.query(EmployeeInvite)
        .filter(
            EmployeeInvite.organization_id == organization_id,
            EmployeeInvite.email == normalized_email,
            EmployeeInvite.status == STATUS_PENDING,
            EmployeeInvite.used_at.is_(None),
            EmployeeInvite.revoked_at.is_(None),
        )
        .first()
    )
    if existing:
        if _aware(existing.expires_at) and _aware(existing.expires_at) <= _now():
            # Stale: mark it revoked so a fresh invite is allowed.
            existing.status = STATUS_REVOKED
            existing.revoked_at = _now()
            db.commit()
        else:
            raise InviteError(
                "An active invitation already exists for this address.",
                code="duplicate",
            )

    raw_token = generate_token()
    invite = EmployeeInvite(
        organization_id=organization_id,
        email=normalized_email,
        full_name=(full_name or "").strip() or None,
        token_hash=hash_token(raw_token),
        role_id=role_id,
        department_id=department_id,
        manager_id=manager_id,
        position_id=position_id,
        status=STATUS_PENDING,
        expires_at=_now() + timedelta(days=_clamp_days(valid_days)),
        invited_by_user_id=invited_by_user_id,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    logger.info("Employee invite created invite=%s org=%s", invite.id, organization_id)
    return invite, raw_token


def lookup_by_token(db: Session, raw_token: str) -> Optional[EmployeeInvite]:
    """Fetch an invite by its raw token, or None."""
    if not is_valid_token_format(raw_token):
        return None
    return (
        db.query(EmployeeInvite)
        .filter(EmployeeInvite.token_hash == hash_token(raw_token))
        .first()
    )


def invite_status(invite: EmployeeInvite, now: Optional[datetime] = None) -> str:
    """Effective status, treating a past expiry date as expired."""
    now = now or _now()
    if invite.status == STATUS_REVOKED:
        return STATUS_REVOKED
    if invite.status == STATUS_ACCEPTED or invite.used_at:
        return STATUS_ACCEPTED
    expires = _aware(invite.expires_at)
    if expires and expires <= now:
        return "expired"
    return STATUS_PENDING


def is_usable(invite: EmployeeInvite, now: Optional[datetime] = None) -> bool:
    return invite_status(invite, now) == STATUS_PENDING


def validate_invite(db: Session, raw_token: str) -> Dict[str, Any]:
    """
    Check an invite link without consuming it.

    Returns only what the recipient legitimately needs to see: the employer and
    the role they are being invited into. Everything else about the tenant
    stays private until the link is actually accepted.
    """
    invite = lookup_by_token(db, raw_token)
    if invite is None or not is_usable(invite):
        raise InviteError(GENERIC_INVALID, code="invalid")

    role_name = getattr(invite.role, "name", None) or ""
    org_name = getattr(invite.organization, "name", None) or ""

    return {
        "email": invite.email,
        "full_name": invite.full_name,
        "organization_name": org_name,
        "role_name": role_name,
        "expires_at": _aware(invite.expires_at).isoformat() if invite.expires_at else None,
    }


def accept_invite(
    db: Session,
    raw_token: str,
    *,
    password: str,
    full_name: Optional[str] = None,
    employee_id: Optional[str] = None,
) -> User:
    """
    Consume an invite and create the new hire's account.

    The invite is claimed with a conditional UPDATE so that only one of several
    concurrent requests can win; the loser sees the generic invalid message
    rather than a duplicate account.
    """
    if not is_valid_token_format(raw_token):
        raise InviteError(GENERIC_INVALID, code="invalid")

    now = _now()
    token_hash = hash_token(raw_token)

    invite = (
        db.query(EmployeeInvite)
        .filter(EmployeeInvite.token_hash == token_hash)
        .first()
    )
    if invite is None:
        raise InviteError(GENERIC_INVALID, code="invalid")

    expires = _aware(invite.expires_at)
    if invite.status == STATUS_REVOKED or invite.revoked_at:
        raise InviteError(GENERIC_INVALID, code="invalid")
    if invite.used_at or invite.status == STATUS_ACCEPTED:
        raise InviteError(GENERIC_INVALID, code="invalid")
    if expires and expires <= now:
        raise InviteError(GENERIC_INVALID, code="expired")

    # Claim the invite atomically. If another request already consumed it the
    # row count is zero and this call loses the race.
    claimed = db.query(EmployeeInvite).filter(
        EmployeeInvite.id == invite.id,
        EmployeeInvite.used_at.is_(None),
        EmployeeInvite.revoked_at.is_(None),
        EmployeeInvite.status == STATUS_PENDING,
    ).update(
        {"used_at": now, "status": STATUS_ACCEPTED},
        synchronize_session=False,
    )
    if not claimed:
        db.rollback()
        raise InviteError(GENERIC_INVALID, code="invalid")

    # A person may already exist (re-send for an account created manually, or
    # a hire the recruitment flow already created), in which case the invite
    # activates that account instead of duplicating it.
    #
    # Scoped to the invite's own tenant. This used to match on email alone and
    # then reject the cross-tenant hit, which was only safe while an address
    # could belong to one organisation globally; now the same mailbox may
    # legitimately have an account in several, and adopting the wrong one would
    # hand a stranger this invite's activation.
    existing_user = (
        db.query(User)
        .filter(
            func.lower(User.email) == invite.email,
            User.org_id == invite.organization_id,
        )
        .first()
    )
    if existing_user is not None:
        existing_user.hashed_password = get_password_hash(password)
        existing_user.is_active = 1
        if full_name:
            existing_user.full_name = full_name.strip()
        if employee_id:
            existing_user.employee_id = employee_id
        invite.accepted_user_id = existing_user.id
        # A hire created by the recruitment flow already has its account and a
        # slot held in PENDING_ONBOARDING. Onboarding is what converts that
        # reservation into a real employment.
        _activate_pending_employment(db, existing_user)
        db.commit()
        db.refresh(existing_user)
        logger.info("Invite accepted for existing user=%s", existing_user.id)
        return existing_user

    resolved_name = (full_name or invite.full_name or "").strip()
    if not resolved_name:
        db.rollback()
        raise InviteError(
            "Please provide your full name to complete onboarding.", code="name_required"
        )

    # Re-check the seat at acceptance time. Creating the invite only proved there
    # was room then; the organisation may have filled that seat in the meantime,
    # and this endpoint is unauthenticated so it gets no limit check for free.
    _require_employee_headroom(db, invite)

    new_user = User(
        org_id=invite.organization_id,
        role_id=invite.role_id,
        dept_id=invite.department_id,
        full_name=resolved_name,
        username=_unique_username(db, invite.email),
        email=invite.email,
        # employee_id is NOT NULL, so fall back to a generated one using the
        # same convention as crud_user.create.
        employee_id=(employee_id or "").strip() or f"EMP-{uuid.uuid4().hex[:6].upper()}",
        hashed_password=get_password_hash(password),
        is_active=1,
    )
    db.add(new_user)
    db.flush()
    invite.accepted_user_id = new_user.id
    _activate_pending_employment(db, new_user)
    db.commit()
    db.refresh(new_user)

    logger.info("Invite accepted invite=%s new user=%s", invite.id, new_user.id)
    return new_user


def _activate_pending_employment(db: Session, user: User) -> None:
    """Convert a held slot into a real employment once onboarding completes.

    A hire made through the recruitment pipeline gets its account and
    employment record at approval time so the slot is held immediately; the
    record sits in PENDING_ONBOARDING until the invite is accepted. Without
    this the person would occupy a slot forever while still reading as not
    employed.

    No-op for an ordinary invite, where no record was reserved.
    """
    pending = (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.org_id == user.org_id,
            EmploymentRecord.user_id == user.id,
            EmploymentRecord.status == "PENDING_ONBOARDING",
        )
        .order_by(EmploymentRecord.id.desc())
        .first()
    )
    if pending is not None:
        pending.status = "PROBATION"
        db.add(pending)


def _require_employee_headroom(db: Session, invite: EmployeeInvite) -> None:
    """
    Confirm the tenant may add one more employee before the account is created.

    Mirrors ``deps.require_limit("employees", increment_by=1)`` for a request
    that has no authenticated user to hang that dependency off.
    """
    from app.core.config import settings

    if not getattr(settings, "ENFORCE_SUBSCRIPTION_LIMITS", True):
        return

    from app.services.subscription_service import subscription_service

    current_usage = (
        db.query(User)
        .filter(
            User.org_id == invite.organization_id,
            User.is_deleted == 0,
        )
        .count()
    )
    result = subscription_service.check_licensing_limit(
        db, invite.organization_id, "employees", current_usage + 1
    )
    if not result["allowed"]:
        raise InviteError(
            "This organisation has reached its employee limit. Ask your administrator "
            "to upgrade the plan before completing onboarding.",
            code="limit",
        )


def _unique_username(db: Session, email: str) -> str:
    """Derive a unique username from the email local part, as crud_user does."""
    base = (email or "employee").split("@")[0] or "employee"
    username = base
    suffix = 1
    while db.query(User.id).filter(User.username == username).first():
        username = f"{base}{suffix}"
        suffix += 1
        if suffix > 1000:
            # Practically unreachable; guards against a pathological loop.
            username = f"{base}{uuid.uuid4().hex[:6]}"
            break
    return username


def revoke_invite(db: Session, invite: EmployeeInvite) -> EmployeeInvite:
    if invite.status == STATUS_ACCEPTED or invite.used_at:
        raise InviteError("An accepted invitation cannot be revoked.", code="conflict")
    invite.status = STATUS_REVOKED
    invite.revoked_at = _now()
    db.commit()
    db.refresh(invite)
    return invite


def checklist_progress(invite: EmployeeInvite) -> Dict[str, bool]:
    return {
        "profile": invite.profile_completed_at is not None,
        "documents": invite.documents_completed_at is not None,
        "tax_form": invite.tax_form_completed_at is not None,
    }


def is_onboarding_complete(invite: EmployeeInvite) -> bool:
    return all(checklist_progress(invite).values())


def mark_checklist(
    db: Session,
    invite: EmployeeInvite,
    *,
    profile: Optional[bool] = None,
    documents: Optional[bool] = None,
    tax_form: Optional[bool] = None,
) -> EmployeeInvite:
    """Update onboarding checklist steps. Only None values are left untouched."""
    now = _now()
    if profile is not None:
        invite.profile_completed_at = now if profile else None
    if documents is not None:
        invite.documents_completed_at = now if documents else None
    if tax_form is not None:
        invite.tax_form_completed_at = now if tax_form else None
    db.commit()
    db.refresh(invite)
    return invite


def serialize(invite: EmployeeInvite, *, include_token: bool = False,
              raw_token: Optional[str] = None) -> Dict[str, Any]:
    """Representation for the administration UI."""
    payload: Dict[str, Any] = {
        "id": invite.id,
        "email": invite.email,
        "full_name": invite.full_name,
        "status": invite_status(invite),
        "role_name": getattr(invite.role, "name", None),
        "department_id": invite.department_id,
        "manager_id": invite.manager_id,
        "expires_at": _aware(invite.expires_at).isoformat() if invite.expires_at else None,
        "used_at": _aware(invite.used_at).isoformat() if invite.used_at else None,
        "revoked_at": _aware(invite.revoked_at).isoformat() if invite.revoked_at else None,
        "accepted_user_id": invite.accepted_user_id,
        "created_at": _aware(invite.created_at).isoformat() if invite.created_at else None,
        "checklist": checklist_progress(invite),
        "onboarding_complete": is_onboarding_complete(invite),
    }
    # The raw token is available only in the response that created the invite.
    if include_token and raw_token:
        payload["token"] = raw_token
    return payload
