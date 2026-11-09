#  core/config.py
# =============================================================================
from __future__ import annotations
import json
import os
import secrets
import logging
import tempfile
from functools import lru_cache
from typing import List, Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# Remove blank complex env vars so .env defaults can be used instead.
if os.environ.get("ALLOWED_ORIGINS", None) == "":
    os.environ.pop("ALLOWED_ORIGINS", None)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8",
        case_sensitive=False, extra="ignore",
    )

    # App
    APP_NAME: str = "Face Detection Attendance System"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_flag(cls, value: object) -> object:
        """Accept common deployment labels without weakening production defaults.

        A few process managers use ``DEBUG=release`` as a build-mode label.  It
        is not a boolean, but treating it as an application-startup error makes
        every worker unavailable.  Map only unambiguous non-debug labels to
        ``False``; unknown values still go through Pydantic's strict boolean
        parsing and fail fast.
        """
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod", "staging"}:
                return False
            if normalized in {"development", "dev"}:
                return True
        return value

    # Security
    SECRET_KEY: str = Field(default="", min_length=0)

    @field_validator("SECRET_KEY", mode="after")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v or len(v) < 32:
            raise ValueError(
                "SECRET_KEY is required and must be at least 32 characters long. "
                "Set a strong SECRET_KEY in your .env file:\n"
                "  SECRET_KEY=your-64-char-random-string-here"
            )
        return v

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # Browser refresh credentials are deliberately separate from the short
    # lived bearer token. Keep the name configurable to support parallel
    # environments without falling back to an implicit cookie name.
    REFRESH_COOKIE_NAME: str = "visioncore_refresh"
    REFRESH_COOKIE_SECURE: bool | None = None
    REFRESH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    SESSION_IDLE_TIMEOUT_MINUTES: int = 60
    ALGORITHM: str = "HS256"
    BCRYPT_ROUNDS: int = 12

    @property
    def refresh_cookie_secure(self) -> bool:
        """Require HTTPS in deployed environments; allow localhost development."""
        if self.REFRESH_COOKIE_SECURE is not None:
            return self.REFRESH_COOKIE_SECURE
        return self.ENVIRONMENT in {"staging", "production"}

    # PostgreSQL — credentials MUST come from environment variables in production
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = Field(default="", min_length=0)
    POSTGRES_DB: str = "attendance_db"
    DB_ECHO: bool = False
    DATABASE_URL_OVERRIDE: Optional[str] = Field(default=None, alias="DATABASE_URL")

    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            url = self.DATABASE_URL_OVERRIDE
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg2://", 1)
            return url
        password = quote_plus(self.POSTGRES_PASSWORD)
        return (f"postgresql+psycopg2://{self.POSTGRES_USER}:{password}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}")

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            url = self.DATABASE_URL_OVERRIDE
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql+psycopg2://"):
                url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
            return url
        password = quote_plus(self.POSTGRES_PASSWORD)
        return (f"postgresql+asyncpg://{self.POSTGRES_USER}:{password}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}")

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            raw = v.strip()
            if raw == "":
                return []
            if raw.startswith("[") and raw.endswith("]"):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(origin).strip() for origin in parsed if str(origin).strip()]
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in raw.split(",") if origin.strip()]
        return v

    # Face recognition
    FACE_MODEL_NAME: str = "Facenet"
    FACE_DISTANCE_THRESHOLD: float = 0.40
    LIVENESS_CHECK_ENABLED: bool = True
    LIVENESS_STRICT_MODE: bool = True
    EMBEDDING_DIMENSIONS: int = 128
    # Upload ceiling for biometric enrollment/recognition payloads. A 1280x720
    # JPEG is ~150 KB, so 10 MB leaves ample headroom while still rejecting
    # unbounded uploads before they are decoded into memory.
    MAX_BIOMETRIC_IMAGE_BYTES: int = 10 * 1024 * 1024

    # Subscription enforcement
    # Gates business routers on the tenant's plan features and licensing limits.
    # Keep True in production so published plan limits are actually binding.
    # Set False only as an emergency rollback: with enforcement off every plan
    # grants every feature and unlimited capacity, so tiers stop being
    # distinguishable products.
    ENFORCE_SUBSCRIPTION_LIMITS: bool = True
    # Plan assigned to a newly provisioned tenant. Free tier keeps self-service
    # signup working while still producing enforceable seat/capacity limits.
    DEFAULT_PLAN_CODE: str = "starter"
    DEFAULT_TRIAL_DAYS: int = 14
    # Plans exposed on public pricing surfaces. An explicit allowlist rather than
    # an is_system filter: every seeded row is is_system=true (including
    # test_plan_* leftovers), so is_system does not identify the real catalog.
    PUBLIC_PLAN_CODES: str = "starter,professional,enterprise"

    # ZKP
    ZKP_DEFAULT_THRESHOLD: float = 0.98

    # Blockchain
    BLOCKCHAIN_URL: str = "http://127.0.0.1:8545"
    BLOCKCHAIN_ENABLED: bool = False
    BLOCKCHAIN_PRIVATE_KEY: str = Field(default="", description="Private key for anchoring transactions")
    BLOCKCHAIN_CONTRACT_ADDRESS: str = Field(default="", description="Deployed AttendanceAudit contract address")

    @field_validator("BLOCKCHAIN_PRIVATE_KEY", "BLOCKCHAIN_CONTRACT_ADDRESS", mode="after")
    @classmethod
    def validate_blockchain_credentials(cls, v: str, info) -> str:
        # Pydantic V2 passes ValidationInfo as second argument
        if info.data.get("BLOCKCHAIN_ENABLED") and not v:
            logger.warning(f"{info.field_name} is missing but BLOCKCHAIN_ENABLED is True.")
        return v

    # Geofencing
    GEOFENCE_ENABLED: bool = False
    GEOFENCE_RADIUS_METERS: int = 50

    # Attendance
    CHECKIN_COOLDOWN_MINUTES: int = 5

    # Email
    #
    # Delivery used to be SMTP-only and fail *silently* when unconfigured: the
    # reset endpoint reported success, nothing was sent, and nobody could tell
    # the difference. `EMAIL_TRANSPORT` now selects a provider and every send
    # returns a delivery result that is persisted, so a failure is visible
    # instead of inferred.
    #
    #   console - writes the message to the log and ./dev_mail/. No credentials,
    #              no cost, no network. Development only: nothing is delivered.
    #   smtp    - any SMTP server. Needs SMTP_HOST/USER/PASSWORD.
    #   brevo   - HTTP API, 300 messages/day free. Needs BREVO_API_KEY.
    #   resend  - HTTP API, 100 messages/day free. Needs RESEND_API_KEY.
    #
    # Free tiers need a verified sending domain (SPF/DKIM) before mail lands in
    # real inboxes rather than spam, so expect to add DNS records.
    EMAIL_TRANSPORT: str = "console"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_TIMEOUT_SECONDS: int = 10
    EMAIL_FROM: str = "noreply@attendance.local"
    EMAIL_FROM_NAME: str = "VisionCore"
    BREVO_API_KEY: str = ""
    RESEND_API_KEY: str = ""
    EMAIL_HTTP_TIMEOUT_SECONDS: int = 10
    DEV_MAIL_DIR: str = "./dev_mail"
    FRONTEND_URL: str = "http://localhost:5173"
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30
    # One-time code alternative to the link. Deliberately much shorter-lived
    # than the link and attempt-capped, because 6 digits is a small space.
    PASSWORD_RESET_OTP_EXPIRE_MINUTES: int = 10
    PASSWORD_RESET_OTP_MAX_ATTEMPTS: int = 5
    # Per-account ceilings, on top of the per-IP limiter. An attacker who knows
    # a victim's address could otherwise use the endpoint to flood their inbox
    # and to time-probe whether the account exists.
    PASSWORD_RESET_ACCOUNT_COOLDOWN_SECONDS: int = 60
    PASSWORD_RESET_ACCOUNT_HOURLY_LIMIT: int = 3

    # Audit
    AUDIT_ENABLED: bool = True

    # Cache & Rate Limiting
    CACHE_DIR: str = Field(default_factory=lambda: os.path.join(tempfile.gettempdir(), "visioncore_cache"))
    REDIS_URL: str = "redis://localhost:6379/0"



@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
