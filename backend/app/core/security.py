from datetime import datetime, timedelta, timezone
from typing import Any, Union
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings
import re
import uuid


# Exported for any module that needs it directly
ALGORITHM = settings.ALGORITHM

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Lazy Redis Client (optional) ───────────────────────────────────────────
# Redis is instantiated lazily with timeouts so that an unavailable Redis
# server does NOT block application startup or cause imports to hang.
_redis_client = None

def _get_redis():
    """Return a lazily-initialized async Redis client with connection timeouts."""
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as redis_async
        _redis_client = redis_async.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
        )
    return _redis_client


async def blacklist_token(token: str, expires_in: int | None = None) -> None:
    # Ensure expires_in is always an int; Redis TTL requires an integer.
    if expires_in is None:
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    else:
        expires_in = int(expires_in)
    try:
        client = _get_redis()
        await client.setex(f"blacklist:{token}", expires_in, "revoked")
    except Exception as exc:
        # Redis supplements database-backed session revocation; it must not make
        # logout or authentication unavailable.
        import logging
        logging.getLogger(__name__).warning("Redis unavailable for token blacklist write: %s", exc)


async def is_token_blacklisted(token: str) -> bool:
    try:
        client = _get_redis()
        return await client.exists(f"blacklist:{token}") > 0
    except Exception as exc:
        # Redis is optional. If it's down/unreachable, don't fail authentication.
        import logging
        logging.getLogger(__name__).warning(
            f"Redis unavailable for token blacklist check: {exc}")
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
