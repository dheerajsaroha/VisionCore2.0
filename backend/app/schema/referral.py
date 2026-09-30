"""
Schemas for the employee referral programme and the public careers page.

Kept apart from the recruitment schemas because the two halves have opposite
trust levels: `recruitment` payloads are trusted internal input, while the
`careers` payloads are unauthenticated public input and are validated far more
strictly.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

# --------------------------------------------------------------------------- #
# referral (internal, authenticated)
# --------------------------------------------------------------------------- #

REFERRAL_STATUSES = {"pending", "submitted", "screening", "qualified", "hired", "rejected"}
# Transitions a referral may be moved to. `pending` is the only starting state.
REFERRAL_STATUS_TRANSITIONS: Dict[str, set[str]] = {
    "pending": {"submitted", "screening", "qualified", "rejected"},
    "submitted": {"screening", "qualified", "rejected"},
    "screening": {"qualified", "hired", "rejected"},
    "qualified": {"hired", "rejected"},
    "hired": {"rejected"},
    "rejected": set(),
}


class ReferralCreate(BaseModel):
    """An employee nominating an external candidate."""

    referred_name: str = Field(min_length=2, max_length=100)
    referred_email: EmailStr
    referred_phone: Optional[str] = Field(default=None, max_length=30)
    job_posting_id: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("referred_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("referred_name cannot be blank")
        return v

    @field_validator("referred_phone")
    @classmethod
    def _clean_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        # Digits, spaces and the usual separators only.
        if not re.fullmatch(r"[0-9+()\-.\s]{6,30}", v):
            raise ValueError("referred_phone contains invalid characters")
        return v

    @field_validator("notes")
    @classmethod
    def _strip_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class ReferralUpdate(BaseModel):
    """HR/admin adjusting a referral's state, reward or notes."""

    status: Optional[str] = None
    reward_amount: Optional[float] = Field(default=None, ge=0, le=10_000_000)
    reward_status: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().lower()
        if v not in REFERRAL_STATUSES:
            raise ValueError(
                f"status must be one of: {sorted(REFERRAL_STATUSES)}"
            )
        return v

    @field_validator("reward_status")
    @classmethod
    def _valid_reward(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().lower()
        if v not in {"pending", "approved", "paid"}:
            raise ValueError("reward_status must be pending, approved or paid")
        return v


class ReferralOut(BaseModel):
    id: int
    organization_id: UUID
    job_posting_id: Optional[int] = None
    job_title: Optional[str] = None
    referrer_user_id: int
    referrer_name: Optional[str] = None
    candidate_id: Optional[int] = None
    referred_name: str
    referred_email: str
    referred_phone: Optional[str] = None
    notes: Optional[str] = None
    referral_code: str
    status: str
    reward_amount: Optional[float] = None
    reward_status: Optional[str] = None
    verified_by_user_id: Optional[int] = None
    verified_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReferralStats(BaseModel):
    total: int = 0
    by_status: Dict[str, int] = Field(default_factory=dict)
    hired: int = 0
    conversion_rate: float = 0.0
    reward_liability: float = 0.0
    top_referrers: List[Dict[str, Any]] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# public careers page (unauthenticated)
# --------------------------------------------------------------------------- #

class PublicJobOut(BaseModel):
    """Deliberately narrower than the internal job shape.

    Excludes `posted_by_user_id` and `status`, and adds only what a candidate
    needs. `status` is omitted rather than echoed because the public endpoint
    filters to `open` -- a closed or draft job must be indistinguishable from
    one that never existed.
    """

    id: int
    title: str
    department: Optional[str] = None
    location: str
    employment_type: str
    description: str
    requirements: Optional[str] = None
    posted_at: datetime


class PublicJobDetail(PublicJobOut):
    organization_name: str
    organization_logo_url: Optional[str] = None
    organization_color: str


class PublicOrgProfile(BaseModel):
    name: str
    slug: str
    logo_url: Optional[str] = None
    primary_color: str
    open_roles: int


class PublicApplyRequest(BaseModel):
    """Unauthenticated application submission. Every field is attacker
    controlled, so lengths are bounded and `referral_code` is treated as an
    untrusted hint rather than an instruction."""

    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=30)
    cover_letter: Optional[str] = Field(default=None, max_length=5000)
    resume_url: Optional[str] = Field(default=None, max_length=500)
    referral_code: Optional[str] = Field(default=None, max_length=32)
    # Standard honeypot: a hidden field real applicants never fill in.
    website: Optional[str] = Field(default=None, max_length=200)

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("full_name is required")
        return v

    @field_validator("cover_letter", "resume_url", "referral_code")
    @classmethod
    def _blank_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("resume_url")
    @classmethod
    def _check_url(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.fullmatch(r"https?://\S+", v):
            raise ValueError("resume_url must be an http(s) URL")
        return v
