from datetime import datetime, timedelta, timezone
from typing import Any, Union
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings
import logging
import re
import uuid


logger = logging.getLogger(__name__)

# Exported for any module that needs it directly
ALGORITHM = settings.ALGORITHM

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")

_redis_clients: dict = {}


def _get_redis():
    """Return an async Redis client bound to the *current* event loop.

    A single module-level client is only safe while one event loop lives for
    the life of the process, which is true under uvicorn but not elsewhere:
    any code that runs the app on a fresh loop (the test client creates one per
    request) leaves the cached client attached to a dead loop. Every command
    then raises "Event loop is closed".

    Keying the client by the running loop keeps a long-lived server identical
    while making any other loop get a working client of its own.
    """
    import asyncio

    import redis.asyncio as redis_async

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # no running loop; fall back to an unbound client
        loop = None

    key = id(loop) if loop is not None else None
    cached = _redis_clients.get(key)
    if cached is not None:
        return cached

    client = redis_async.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        retry_on_timeout=False,
    )
    # Drop clients bound to loops that are gone, so the dict cannot grow
    # without bound when loops churn.
    for stale_key, stale in list(_redis_clients.items()):
        if stale_key != key:
            owner = getattr(stale, "_visioncore_loop", None)
            if owner is None or owner.is_closed():
                _redis_clients.pop(stale_key, None)
    try:
        client._visioncore_loop = loop
    except Exception:  # noqa: BLE001 - attribute is best effort
        pass
    _redis_clients[key] = client
    return client


async def blacklist_token(token: str, expires_in: int | None = None) -> None:
    """Add a token to the Redis blacklist. Best-effort — silently skips if Redis is down."""
    if expires_in is None:
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    else:
        expires_in = int(expires_in)
    try:
        client = _get_redis()
        await client.setex(f"blacklist:{token}", expires_in, "revoked")
    except Exception as exc:
        logger.warning("Redis unavailable — token blacklist write skipped: %s", exc)


async def is_token_blacklisted(token: str) -> bool:
    """Return True if the token has been revoked. Fails open when Redis is down."""
    try:
        client = _get_redis()
        return await client.exists(f"blacklist:{token}") > 0
    except Exception as exc:
        logger.warning("Redis unavailable for token blacklist check (fail-open): %s", exc)
        return False


async def consume_one_time_token(token: str, expires_in: int) -> bool:
    """Atomically consume a short-lived credential using Redis."""
    try:
        client = _get_redis()
        return bool(await client.set(f"one-time:{token}", "used", ex=expires_in, nx=True))
    except Exception as exc:
        logger.error("One-time token store unavailable: %s", exc)
        return False





def create_access_token(
    subject: Union[str, Any],
    expires_delta: timedelta | None = None,
    *,
    session_jti: str | None = None,
) -> str:


    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    if session_jti is None:
        session_jti = str(uuid.uuid4())

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "access",
        "jti": session_jti,
        "iat": int(now.timestamp()),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: timedelta | None = None,
    *,
    session_jti: str | None = None,
) -> str:

    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    if session_jti is None:
        session_jti = str(uuid.uuid4())

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
        "jti": session_jti,
        "iat": int(now.timestamp()),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_password_reset_token(subject: Union[str, Any]) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "exp": now + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
        "sub": str(subject),
        "type": "password_reset",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
    }, settings.SECRET_KEY, algorithm=ALGORITHM)



def verify_token_type(token: str, expected_type: str) -> bool:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("type") == expected_type
    except (JWTError, Exception):
        return False


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validates password strength.
    Returns (is_valid, error_message).
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+\[\]\\;/`~]", password):
        return False, "Password must contain at least one special character."
    return True, ""
