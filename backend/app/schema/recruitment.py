"""
Schemas for the recruitment module (job postings, candidates, applications,
interviews).

These exist mainly to stop the handlers taking a bare `dict`. With
`payload: dict`, a missing key raised `KeyError` and surfaced as a 500 instead
of a 422, and `stage` accepted any string at all -- so a typo could write
`"interveiw"` into a pipeline and leave a candidate stranded in `applied`
forever with no way to tell what went wrong.

Validated at the edge also means the pipeline states are a closed set defined
in one place rather than an implied union of whatever strings various handlers
happen to compare against.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

# The pipeline a `JobApplication` moves through. Kept in step with the
# `stage` column comment on the model and with the public careers form, which
# cannot set a stage at all.
APPLICATION_STAGES = {"applied", "screening", "interview", "offer", "hired", "rejected"}

# `hired` and `rejected` are terminal: nothing may follow them. A candidate
# who was rejected and later reopens should get a new application row.
TERMINAL_STAGES = {"hired", "rejected"}

JOB_STATUSES = {"draft", "open", "closed"}


# --------------------------------------------------------------------------- #
# job postings
# --------------------------------------------------------------------------- #

class JobPostingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str = Field(min_length=1)
    department_id: Optional[int] = None
    requirements: Optional[str] = None
    location: str = Field(default="Remote", max_length=100)
    employment_type: str = Field(default="Full-time", max_length=50)
    status: str = Field(default="open")
    # The internal slot this advert fills. Linking the two is what lets a hire
    # consume a slot and appear in the org structure.
    position_id: Optional[int] = None
    # How many openings this advert covers, so a multi-hire vacancy is
    # expressible and a capacity check can actually fail.
    headcount: int = Field(default=1, ge=1, le=1000)

    @field_validator("status")
    @classmethod
    def _known_status(cls, v: str) -> str:
        if v not in JOB_STATUSES:
            raise ValueError(f"status must be one of {sorted(JOB_STATUSES)}")
        return v


# --------------------------------------------------------------------------- #
# candidates
# --------------------------------------------------------------------------- #

class CandidateCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=30)
    resume_url: Optional[str] = Field(default=None, max_length=255)


# --------------------------------------------------------------------------- #
# applications
# --------------------------------------------------------------------------- #

class ApplicationCreate(BaseModel):
    job_posting_id: int
    candidate_id: int
    stage: str = "applied"
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    notes: Optional[str] = None

    @field_validator("stage")
    @classmethod
    def _known_stage(cls, v: str) -> str:
        if v not in APPLICATION_STAGES:
            raise ValueError(f"stage must be one of {sorted(APPLICATION_STAGES)}")
        return v


class ApplicationStageUpdate(BaseModel):
    stage: str
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    notes: Optional[str] = None

    @field_validator("stage")
    @classmethod
    def _known_stage(cls, v: str) -> str:
        if v not in APPLICATION_STAGES:
            raise ValueError(f"stage must be one of {sorted(APPLICATION_STAGES)}")
        return v


# --------------------------------------------------------------------------- #
# interviews
# --------------------------------------------------------------------------- #

class InterviewCreate(BaseModel):
    application_id: int
    interviewer_user_id: Optional[int] = None
    scheduled_at: datetime
    meeting_link: Optional[str] = Field(default=None, max_length=255)
