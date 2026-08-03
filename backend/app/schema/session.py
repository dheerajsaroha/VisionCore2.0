from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UserSessionOut(BaseModel):
    id: UUID
    user_id: int
    jti: str
    created_at: datetime
    last_activity_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_name: Optional[str] = None
    browser: Optional[str] = None
    operating_system: Optional[str] = None
    is_active: bool
    revoked_at: Optional[datetime] = None
    logout_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserSessionListOut(BaseModel):
    sessions: list[UserSessionOut]



class DeleteResponse(BaseModel):
    detail: str

