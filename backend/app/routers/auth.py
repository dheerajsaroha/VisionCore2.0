"""
auth.py — Public authentication endpoints.
"""
from datetime import datetime, timedelta, timezone
import uuid

from typing import Any, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
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

    return {
        "access_token": security.create_access_token(
            user_obj.id, expires_delta=access_token_expires, session_jti=access_jti
        ),
        "refresh_token": security.create_refresh_token(
            user_obj.id, expires_delta=refresh_token_expires, session_jti=refresh_jti
        ),
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    request: Request,
    body: Optional[RefreshTokenRequest] = None,
    refresh_token: Optional[str] = Query(None),
    db: Session = Depends(deps.get_db),
) -> Any:
    """Refresh using refresh token with enterprise rotation + replay protection.

    Accepts ``refresh_token`` from (in priority order):
    1. Request body as JSON (``{"refresh_token": "..."}``)
    2. Query parameter (``?refresh_token=...``)

    At least one of the above must be supplied.
    """

    # Resolve refresh_token from body first, then query (backward compat).
    token = (body.refresh_token if body else None) or refresh_token
    if not token:
        raise HTTPException(status_code=422, detail="refresh_token is required (body or query)")

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

    old_session = user_session.get_for_user_by_refresh_jti(
        db, user_id=user_id, refresh_jti=refresh_jti)
    now = datetime.now(timezone.utc)

    # ── Fallback lookup when primary refresh_jti match fails ──────────────
    # The primary query may return None if:
    #   a) The session record has a NULL refresh_jti (created by an older
    #      code version before the refresh_jti column existed).
    #   b) The session record exists but has been marked inactive.
    #
    # Fallback strategy (two-tier):
    #   1. Look up by the access-token jti column using the same refresh_jti
    #      value — this covers legacy sessions where the refresh JTI was
    #      stored in the jti column by mistake.
    #   2. Return the latest *active* session for the user (broadest fallback).
    if not old_session or not old_session.is_active:
        old_session = user_session.get_for_user_by_jti(
            db, user_id=user_id, jti=refresh_jti)

    if not old_session or not old_session.is_active:
        old_session = user_session.get_latest_active_session_for_user(
            db, user_id=user_id)

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
    # Reuse Redis blacklist infrastructure.
    # Use a safe TTL derived from the refresh token exp; if exp parsing fails, fall back to default.
    try:
        exp = payload.get("exp")
        if exp is None:
            raise ValueError("Missing exp")
        now_ts = int(datetime.now(timezone.utc).timestamp())
        expires_in_seconds = max(0, int(exp - now_ts))
    except Exception:
        expires_in_seconds = int(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    await security.blacklist_token(token, expires_in=expires_in_seconds)
    user_session.revoke_by_session(
        db, user_id=user_id, jti=old_session.jti, reason="refresh_rotated")
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

    return {
        "access_token": security.create_access_token(
            user_obj.id, expires_delta=access_token_expires, session_jti=new_access_jti
        ),
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }



@router.post("/logout")
async def logout(
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
        # Keep logout idempotent; blacklist may still invalidate a syntactically
        # valid token when its database session was already removed.
        pass
    return {"detail": "Successfully logged out"}


@router.post("/change-password")
async def change_password(
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
    # Password strength validation
    is_valid, error_msg = security.validate_password_strength(user_in.password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_msg)

    existing = crud_user.get_by_email(db, email=user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered."
        )
    new_user = crud_user.create(db, obj_in=user_in.model_dump())
    return new_user
