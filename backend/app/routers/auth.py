"""
auth.py — Public authentication endpoints.
"""
from datetime import datetime, timedelta, timezone
import logging
import smtplib
import uuid
from typing import Any, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from pydantic import BaseModel
from email.message import EmailMessage
from sqlalchemy.orm import Session

from app.api import deps
from app.core import security
from app.core.config import settings
from app.core.rate_limit import rate_limit_dependency
from app.crud.crud_user import user as crud_user
from app.schema.token import Token, RefreshTokenRequest
from app.schema.user import PasswordChange, UserSignup, UserResponse
from app.db.models.all_models import User
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


@router.post("/login", response_model=Token)
def login_access_token(
    request: Request,
    response: Response,
    db: Session = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
    _: bool = Depends(rate_limit_dependency(max_requests=5, window_seconds=60))
) -> Any:
    """
    Accepts username (email) + password, returns a JWT access token.
    Compatible with OAuth2PasswordBearer on the frontend.
    Rate limited: 5 attempts per IP per minute.
    """
    user_obj = db.query(User).filter(
        (User.email == form_data.username) | (User.username == form_data.username),
        User.is_deleted == 0
    ).first()

    if not user_obj or not security.verify_password(form_data.password, user_obj.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
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
    token: str
    new_password: str


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


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    _: bool = Depends(rate_limit_dependency(max_requests=5, window_seconds=60)),
) -> Any:
    """Issue a short-lived reset link without disclosing account existence."""
    user_obj = crud_user.get_by_email(db, email=payload.email.strip().lower())
    response: dict[str, str] = {"detail": RESET_SUCCESS_MESSAGE}
    if not user_obj or not user_obj.is_active or user_obj.is_deleted:
        return response

    token = security.create_password_reset_token(user_obj.id)
    reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?{urlencode({'token': token})}"
    _deliver_reset_email(user_obj.email, reset_url)
    if settings.ENVIRONMENT == "development":
        response["reset_url"] = reset_url
    return response


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    response: Response,
    db: Session = Depends(deps.get_db),
    _: bool = Depends(rate_limit_dependency(max_requests=3, window_seconds=300)),
) -> Any:
    """Consume a one-time reset token, update the password, and revoke sessions."""
    valid, message = security.validate_password_strength(payload.new_password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)
    try:
        claims = jwt.decode(payload.token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        if claims.get("type") != "password_reset" or not claims.get("jti"):
            raise ValueError("invalid token type")
        user_id = int(claims["sub"])
        expires_in = max(1, int(claims["exp"] - datetime.now(timezone.utc).timestamp()))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This reset link is invalid or has expired.")

    if not await security.consume_one_time_token(payload.token, expires_in):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This reset link is invalid, expired, or has already been used.")
    user_obj = db.query(User).filter(User.id == user_id, User.is_deleted == 0).first()
    if not user_obj or not user_obj.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This reset link is invalid or has expired.")
    user_obj.hashed_password = security.get_password_hash(payload.new_password)
    db.add(user_obj)
    db.commit()
    user_session.revoke_all_for_user(db, user_id=user_obj.id, reason="password_reset", logout=True)
    _clear_refresh_cookie(response)
    return {"detail": "Password reset successfully. Please sign in."}


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
        raise HTTPException(status_code=422, detail="refresh_token is required")

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
    response: Response,
    password_change: PasswordChange,
    db: Session = Depends(deps.get_db),
    token: str = Depends(deps.oauth2_scheme),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Change a password and invalidate every active device session."""
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

    existing = crud_user.get_by_email(db, email=user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered."
        )

    payload = user_in.model_dump()
    payload["role"] = "Employee"

    new_user = crud_user.create(db, obj_in=payload)
    return new_user
