"""
auth.py — Public authentication endpoints.
"""
from datetime import datetime, timedelta, timezone
import logging
import smtplib
import uuid
from typing import Any, List, Optional
from urllib.parse import urlencode

from fastapi import (APIRouter, Body, Depends, Form, HTTPException, Query,
                     Request, Response, status)
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from pydantic import BaseModel
from email.message import EmailMessage
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api import deps
from app.core import security
from app.core.config import settings
from app.core.rate_limit import rate_limit_dependency
from app.crud.crud_user import user as crud_user
from app.schema.token import Token, RefreshTokenRequest
from app.schema.user import PasswordChange, UserSignup, UserResponse
from app.db.models.all_models import Organization, PasswordResetRequest, User
from app.services import email_transport, password_reset_service
from app.crud.crud_session import user_session

router = APIRouter()


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Set the long-lived browser credential outside JavaScript reach."""
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=f"{settings.API_V1_STR}/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=f"{settings.API_V1_STR}/auth",
        secure=settings.refresh_cookie_secure,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


def _request_meta(request: Request) -> dict[str, str | None]:
    """IP and user-agent for the reset record, from the shared helper."""
    meta = _session_metadata(request)
    return {"ip_address": meta.get("ip_address"),
            "user_agent": meta.get("user_agent")}


def _session_metadata(request: Request) -> dict[str, str | None]:
    """Capture bounded request metadata without adding a UA-parser dependency."""
    user_agent = request.headers.get("user-agent")
    lowered = (user_agent or "").lower()
    browser = next((name for name in ("Edge", "Chrome", "Firefox", "Safari")
                    if name.lower() in lowered), None)
    operating_system = next((name for name in ("Windows", "Android", "iOS", "macOS", "Linux")
                              if name.lower() in lowered), None)
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": user_agent,
        "device_name": request.headers.get("sec-ch-ua-platform"),
        "device_type": "mobile" if "mobile" in lowered else "desktop",
        "browser": browser,
        "operating_system": operating_system,
    }


def _resolve_login_candidates(
    db: Session, identifier: str, organization: Optional[str]
) -> List[User]:
    """
    Find the accounts an identifier could refer to.

    `username` is still globally unique, so a username match is always a single
    account. `email` is unique per tenant and therefore may match several, which
    is the case this exists to handle.
    """
    identifier = (identifier or "").strip()
    lowered = identifier.lower()
    q = db.query(User).filter(
        User.is_deleted == 0,
        (func.lower(User.email) == lowered) | (func.lower(User.username) == lowered),
    )

    if organization and organization.strip():
        wanted = organization.strip().lower()
        q = q.join(Organization, User.org_id == Organization.id).filter(
            (func.lower(Organization.name) == wanted)
            | (func.lower(Organization.legal_id) == wanted)
            | (func.lower(Organization.career_slug) == wanted)
        )
    return q.all()


@router.post("/login", response_model=Token)
def login_access_token(
    request: Request,
    response: Response,
    db: Session = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
    organization: Optional[str] = Form(
        None,
        description=(
            "Organisation name, legal id or career slug. Only needed when the "
            "same address holds accounts in more than one organisation."
        ),
    ),
    _: bool = Depends(rate_limit_dependency(max_requests=5, window_seconds=60))
) -> Any:
    """
    Accepts username (email) + password, returns a JWT access token.
    Compatible with OAuth2PasswordBearer on the frontend.
    Rate limited: 5 attempts per IP per minute.
    """
    # The password is checked against every account the identifier could mean
    # before any of them is chosen. That keeps the common case -- one address,
    # one account -- completely unchanged, and means a tenant prompt appears
    # only when the same person genuinely holds two accounts *and* reused the
    # same password for both, which no amount of guessing could resolve.
    candidates = _resolve_login_candidates(
        db, form_data.username, organization
    )
    matches = [
        u for u in candidates
        if security.verify_password(form_data.password, u.hashed_password)
    ]

    if len(matches) > 1:
        orgs = sorted({
            (db.query(Organization.name).filter(Organization.id == u.org_id).scalar()
             or str(u.org_id))
            for u in matches
        })
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "This email has accounts in more than one organisation. "
                    "Add the organisation name to sign in."
                ),
                "organizations": orgs,
            },
        )

    if not matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    user_obj = matches[0]
    if not user_obj.is_active:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Account is suspended")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    access_jti = uuid.uuid4().hex
    refresh_jti = uuid.uuid4().hex
    now = datetime.now(timezone.utc)

    user_session.create_for_user(
        db,
        user_id=user_obj.id,
        jti=access_jti,
        refresh_jti=refresh_jti,
        expires_at=now + refresh_token_expires,
        **_session_metadata(request),
    )

    refresh_token = security.create_refresh_token(
        user_obj.id, expires_delta=refresh_token_expires, session_jti=refresh_jti
    )
    _set_refresh_cookie(response, refresh_token)
    return {
        "access_token": security.create_access_token(
            user_obj.id, expires_delta=access_token_expires, session_jti=access_jti
        ),
        "token_type": "bearer",
    }


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    """
    Either credential is sufficient to prove control of the mailbox:

    * `token` -- the signed link, and
    * `email` + `otp` -- the six-digit code, for people who cannot follow a
      link (a phone-only mailbox, a stripped HTML message, a corporate client
      that rewrites links).

    Both resolve to the same account and both are single-use, so offering the
    code does not weaken the link.
    """
    new_password: str
    token: Optional[str] = None
    # Plain str, not EmailStr, to match ForgotPasswordRequest. EmailStr rejects
    # reserved TLDs such as `.test` and `.localhost`, which the address must
    # match by value, not by RFC validity -- a request that fails validation
    # here would be indistinguishable from a reset attempt that found nothing.
    # Normalization happens in the service.
    email: Optional[str] = None
    otp: Optional[str] = None

    @property
    def has_token(self) -> bool:
        return bool((self.token or "").strip())

    @property
    def has_otp(self) -> bool:
        return bool((self.otp or "").strip()) and bool(self.email)


RESET_SUCCESS_MESSAGE = "If an account exists for that email, password reset instructions have been sent."
logger = logging.getLogger(__name__)


def _deliver_reset_email(recipient: str, reset_url: str) -> None:
    """Best-effort SMTP delivery; caller always returns the generic response."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("Password reset mail is not configured")
        return
    message = EmailMessage()
    message["Subject"] = "Reset your VisionCore password"
    message["From"] = settings.EMAIL_FROM
    message["To"] = recipient
    message.set_content(
        f"Use this one-time link to reset your password. It expires in "
        f"{settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes:\n\n{reset_url}"
    )
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
    except Exception:
        logger.exception("Unable to deliver password reset email")


def _audit_password_event(
    db: Session,
    user: "User",
    *,
    action: str,
    summary: str,
    request: Optional[Request] = None,
    details: Optional[dict] = None,
) -> None:
    """Record a credential change in the audit log.

    Password resets were previously invisible to the audit trail: nothing in
    this module called the audit service, so a takeover performed via the
    reset flow left no record that the credential had changed. The reset token
    is never included in `details` -- only the fact that one was issued or used.
    """
    try:
        from app.services.audit_service import audit_service

        audit_service.record(
            actor_user_id=user.id,
            actor_email=user.email,
            organization_id=str(user.org_id) if user.org_id else "",
            tenant_id=str(user.org_id) if user.org_id else "",
            module="auth",
            source_service="auth_router",
            action=action,
            entity_type="user",
            entity_id=str(user.id),
            summary=summary,
            details=details or {},
        )
    except Exception:  # noqa: BLE001 - auditing must not break the auth flow
        logger.exception("Failed to audit %s for user %s", action, getattr(user, "id", "?"))


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    _: bool = Depends(rate_limit_dependency(max_requests=5, window_seconds=60))
) -> Any:
    """
    Issue a reset link and one-time code, without disclosing account existence.

    The response is deliberately identical whether or not the address is known,
    so this endpoint cannot be used to enumerate staff. The *record* of what
    happened is not identical: every attempt lands in
    `password_reset_requests`, which is what makes a failed delivery
    diagnosable instead of merely suspected.
    """
    response: dict[str, Any] = {"detail": RESET_SUCCESS_MESSAGE}
    wanted = (payload.email or "").strip().lower()
    meta = _request_meta(request)

    allowed, reason = password_reset_service.account_throttle_state(db, wanted)
    if not allowed:
        # Same neutral body as success. Telling the caller they are being
        # throttled would confirm the address is known, which is the one thing
        # this endpoint must not do.
        logger.info("Password reset throttled for %s: %s", wanted, reason)
        return response

    # Every account holding this address gets a link, not just the first. Email
    # is unique per tenant now, so one mailbox may have several accounts and
    # choosing one arbitrarily would make the reset a coin flip; the same person
    # owns them all, and the links all arrive at the same mailbox.
    accounts = crud_user.get_all_by_email(db, email=wanted)
    issued = 0
    for user_obj in accounts:
        if not user_obj.is_active or user_obj.is_deleted:
            continue
        result = password_reset_service.issue_reset(db, user_obj, request_meta=meta)
        issued += 1
        _audit_password_event(
            db, user_obj,
            action="password_reset_requested",
            summary="Password reset link and code issued",
            request=request,
            details={
                "delivery_status": result["delivery"].status,
                "delivery_provider": result["delivery"].provider,
            },
        )
        if settings.ENVIRONMENT == "development":
            # Development convenience only: with the console transport the mail
            # goes to ./dev_mail/, but handing it back makes the flow testable
            # without reading files. Never done outside development.
            response["reset_url"] = result["link"]
            response["otp"] = result["otp"]
            response["delivery_status"] = result["delivery"].status

    if issued == 0:
        # Record the attempt even for an unknown address. Otherwise a flood
        # against non-existent accounts leaves no trace at all, and the
        # per-account throttle has nothing to count.
        db.add(password_reset_service.record_unknown_request(
            db, email=wanted, request_meta=meta))
        db.commit()
    return response


@router.get("/password-reset/delivery-status")
async def password_reset_delivery_status(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission("users.read")),
) -> Any:
    """
    Report whether email can actually leave this deployment.

    Added because the previous failure was invisible: no SMTP credentials meant
    nothing was sent, nothing was logged as an error an operator would look
    for, and the endpoint kept reporting success. An administrator can now ask
    the system this question directly, and see how many recent attempts ended
    undelivered.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    unhealthy = (
        db.query(func.count(PasswordResetRequest.id))
        .filter(
            PasswordResetRequest.delivery_status.in_(
                ["failed", "skipped_unconfigured"]
            ),
            PasswordResetRequest.created_at >= since,
        )
        .scalar()
    ) or 0
    return {
        "email": email_transport.transport_status(),
        "unhealthy_deliveries_24h": int(unhealthy),
    }


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    response: Response,
    db: Session = Depends(deps.get_db),
    _: bool = Depends(rate_limit_dependency(max_requests=3, window_seconds=300)),
) -> Any:
    """
    Complete a reset using the link token or the one-time code.

    Whichever is used, the outcome is the same and the other is burned: a
    successful reset revokes every session and invalidates the code, so a
    link intercepted in a mailbox is not still good after the owner acts.
    """
    valid, message = security.validate_password_strength(payload.new_password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)

    used_code = False
    if payload.has_token:
        user_obj, jti = _resolve_reset_token(db, payload.token)
    elif payload.has_otp:
        user_obj = _resolve_reset_otp(db, payload.email, payload.otp)
        used_code = True
    else:
        # Neither credential is usable. Answered here rather than by a schema
        # validator so that a missing, blank and malformed credential all give
        # the same 400 -- one contract for "that credential is not valid",
        # instead of splitting callers across 400 and 422.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either the reset link token, or your email and "
                   "the 6-digit code.")

    # The single-use check happens BEFORE the password changes.
    #
    # Order matters: a consumed token must not be able to set a password again.
    # Checking after the write means a replayed link -- a token still sitting
    # in an old mailbox or a proxy log -- succeeds a second time, which is the
    # one thing a one-time token exists to prevent.
    if not used_code:
        if not password_reset_service.consume_reset_link(db, jti, user_obj.id):
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This reset link is invalid, expired, or has already "
                       "been used.")

    user_obj.hashed_password = security.get_password_hash(payload.new_password)
    db.add(user_obj)
    db.commit()

    # Both credentials for this request are spent, whichever one was presented.
    if used_code:
        # _resolve_reset_otp already committed the attempt count; the row is
        # re-read to burn the code without clobbering the counter.
        row = (
            db.query(PasswordResetRequest)
            .filter(
                PasswordResetRequest.user_id == user_obj.id,
                PasswordResetRequest.satisfied_at.is_(None),
                PasswordResetRequest.otp_code_hash.isnot(None),
            )
            .order_by(PasswordResetRequest.created_at.desc())
            .first()
        )
        if row is not None:
            password_reset_service.consume_otp(row)
            db.commit()
    user_session.revoke_all_for_user(db, user_id=user_obj.id, reason="password_reset", logout=True)
    _audit_password_event(
        db, user_obj,
        action="password_reset_completed",
        summary=("Password reset completed via emailed code"
                 if used_code else
                 "Password reset completed via emailed token"),
    )
    # The owner hears about the change from two directions, because an
    # unexpected change is the signal that matters most.
    password_reset_service.notify_password_changed(
        db, user_obj, source="reset",
        request_meta=_request_meta(request))
    _clear_refresh_cookie(response)
    return {"detail": "Password reset successfully. Please sign in."}


def _resolve_reset_token(db: Session, token: str):
    """Validate a reset link and return the account it points at."""
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        if claims.get("type") != "password_reset" or not claims.get("jti"):
            raise ValueError("invalid token type")
        user_id = int(claims["sub"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired.")

    user_obj = db.query(User).filter(
        User.id == user_id, User.is_deleted == 0).first()
    if not user_obj or not user_obj.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired.")
    # Redis is the token's own single-use store; this is the cross-credential
    # check. The link and the code ship in the same message, so a link used
    # after the code already completed the reset is a live credential.
    if password_reset_service.is_request_closed(db, claims.get("jti")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid, expired, or has already been used.")
    return user_obj, claims["jti"]


def _resolve_reset_otp(db: Session, email: str | None, otp: str | None):
    """
    Validate a one-time code and return the account it belongs to.

    Errors are deliberately vague about *which* part was wrong, so the code
    cannot be turned into a confirmation oracle for the address. A guessable
    failure ("that address has no code") would undo the enumeration resistance
    the request endpoint works for.
    """
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="That reset code is not correct, has expired, or has already been used.",
    )
    row, error = password_reset_service.verify_otp(db, email or "", otp or "")
    if row is None:
        logger.info("OTP reset rejected for %s: %s", (email or "").lower(), error)
        raise invalid
    user_obj = db.query(User).filter(
        User.id == row.user_id, User.is_deleted == 0).first()
    if not user_obj or not user_obj.is_active:
        raise invalid
    return user_obj


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    request: Request,
    response: Response,
    body: Optional[RefreshTokenRequest] = None,
    refresh_token: Optional[str] = Query(None),
    db: Session = Depends(deps.get_db),
) -> Any:
    """Refresh using refresh token with enterprise rotation + replay protection.

    Browser clients use the HttpOnly refresh cookie. Request body and query
    parameter support are temporary compatibility paths for non-browser
    clients; neither is returned by login or refresh responses.
    """

    # Browser clients obtain this only from the HttpOnly cookie. Body/query
    # input remains a temporary non-browser compatibility path and is never
    # emitted by login/refresh responses.
    token = request.cookies.get(settings.REFRESH_COOKIE_NAME) or (body.refresh_token if body else None) or refresh_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh session is unavailable",
        )

    # 1) Validate token type
    if not security.verify_token_type(token, "refresh"):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # 2) Verify token is not revoked (replay protection)
    if await security.is_token_blacklisted(token):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    # 3) Verify JWT + expiration
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[security.ALGORITHM],
        )
        user_id = int(payload.get("sub"))
        refresh_jti = payload.get("jti")
        if not refresh_jti:
            raise ValueError("Missing refresh token identifier")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_obj = db.query(User).filter(User.id == user_id, User.is_deleted == 0).first()
    if not user_obj or not user_obj.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    old_session = user_session.get_active_for_user_by_refresh_jti(
        db, user_id=user_id, refresh_jti=refresh_jti)
    now = datetime.now(timezone.utc)

    if not old_session or not old_session.is_active:
        raise HTTPException(status_code=401, detail="Refresh session has been revoked")
    if old_session.expires_at and old_session.expires_at <= now:
        user_session.revoke_by_session(
            db, user_id=user_id, jti=old_session.jti, reason="session_expired")
        raise HTTPException(status_code=401, detail="Refresh session has expired")

    # 4) Issue new tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    new_access_jti = uuid.uuid4().hex
    new_refresh_jti = uuid.uuid4().hex
    new_refresh_token = security.create_refresh_token(
        user_obj.id, expires_delta=refresh_token_expires, session_jti=new_refresh_jti)

    # 5) Revoke previous refresh token immediately (enterprise rotation)
    try:
        exp = payload.get("exp")
        if exp is None:
            raise ValueError("Missing exp")
        now_ts = int(datetime.now(timezone.utc).timestamp())
        expires_in_seconds = max(0, int(exp - now_ts))
    except Exception:
        expires_in_seconds = int(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    # Consume this exact refresh JTI atomically. This closes the concurrent
    # refresh race: only one request can rotate a given refresh credential.
    if not user_session.consume_refresh_session(
        db, user_id=user_id, refresh_jti=refresh_jti, reason="refresh_rotated"
    ):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")
    await security.blacklist_token(token, expires_in=expires_in_seconds)
    user_session.create_for_user(
        db,
        user_id=user_id,
        jti=new_access_jti,
        refresh_jti=new_refresh_jti,
        expires_at=now + refresh_token_expires,
        ip_address=old_session.ip_address,
        user_agent=old_session.user_agent,
        device_name=old_session.device_name,
        device_type=old_session.device_type,
        browser=old_session.browser,
        browser_version=old_session.browser_version,
        operating_system=old_session.operating_system,
        operating_system_version=old_session.operating_system_version,
    )

    _set_refresh_cookie(response, new_refresh_token)
    return {
        "access_token": security.create_access_token(
            user_obj.id, expires_delta=access_token_expires, session_jti=new_access_jti
        ),
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(
    response: Response,
    token: str = Depends(deps.oauth2_scheme),
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Logout the current user by blacklisting the token.
    """
    await security.blacklist_token(token)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        if payload.get("type") == "access" and payload.get("jti"):
            user_session.revoke_by_session(
                db, user_id=int(payload["sub"]), jti=payload["jti"],
                reason="logout", logout=True)
    except Exception:
        pass
    _clear_refresh_cookie(response)
    return {"detail": "Successfully logged out"}


@router.post("/change-password")
async def change_password(
    request: Request,
    response: Response,
    password_change: PasswordChange,
    db: Session = Depends(deps.get_db),
    token: str = Depends(deps.oauth2_scheme),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Change a password and invalidate every active device session.

    The owner is notified as well as audited, because a password changed while
    they were not at the keyboard is the case they need to know about, and it
    reaches them on a channel -- the in-app feed and their mailbox -- rather
    than only in a log an administrator might read later.
    """
    if not security.verify_password(password_change.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    valid, message = security.validate_password_strength(password_change.new_password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)

    current_user.hashed_password = security.get_password_hash(password_change.new_password)
    db.add(current_user)
    db.commit()
    user_session.revoke_all_for_user(
        db, user_id=current_user.id, reason="password_changed", logout=True)
    _audit_password_event(
        db,
        current_user,
        action="password_changed",
        summary="Password changed by the account holder",
    )
    password_reset_service.notify_password_changed(
        db, current_user, source="change", request_meta=_request_meta(request))
    await security.blacklist_token(token)
    _clear_refresh_cookie(response)
    return {"detail": "Password changed. Please sign in again on all devices."}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    request: Request,
    *,
    db: Session = Depends(deps.get_db),
    user_in: UserSignup,
    _: bool = Depends(rate_limit_dependency(max_requests=3, window_seconds=300))
) -> Any:
    """
    Self-service registration. Creates a new org or joins an existing one.
    Rate limited: 3 registrations per IP per 5 minutes.
    """
    is_valid, error_msg = security.validate_password_strength(user_in.password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_msg)

    # Deliberately still global, unlike the per-tenant uniqueness. This endpoint
    # can join the caller to a named organisation, so allowing a second account
    # for an address that already holds one would be a way to acquire a
    # duplicate identity. The database no longer prevents it; this does.
    if crud_user.get_all_by_email(db, email=user_in.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered."
        )

    payload = user_in.model_dump()
    payload["role"] = "Employee"

    new_user = crud_user.create(db, obj_in=payload)
    return new_user
