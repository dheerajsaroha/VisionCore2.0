from pydantic import BaseModel, Field, ConfigDict, field_validator
from uuid import UUID
from typing import Optional, List
from datetime import datetime, time

class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    legal_id: str = Field(..., min_length=1, max_length=100)
    zkp_threshold: float = Field(0.98, ge=0.0, le=1.0)
    is_active: bool = True
    status: str = Field("ACTIVE", pattern=r"^(ACTIVE|SUSPENDED|ARCHIVED|PENDING_ONBOARDING)$")
    logo_url: Optional[str] = Field(None, max_length=512, pattern=r"^https?://")
    primary_color: str = Field("#4F46E5", pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("name", "legal_id", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value

    @field_validator("legal_id")
    @classmethod
    def normalize_legal_id(cls, value: str) -> str:
        return value.upper()

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    zkp_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    logo_url: Optional[str] = Field(None, max_length=512, pattern=r"^https?://")
    primary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    is_active: Optional[bool] = None
    status: Optional[str] = Field(None, pattern=r"^(ACTIVE|SUSPENDED|ARCHIVED|PENDING_ONBOARDING)$")

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

class OrganizationResponse(OrganizationBase):
    id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class DepartmentBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    is_deleted: int = 0

class DepartmentCreate(DepartmentBase):
    org_id: UUID

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_deleted: Optional[int] = None

class DepartmentResponse(DepartmentBase):
    id: int
    org_id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ShiftBase(BaseModel):
    shift_name: str = Field(..., max_length=100)
    start_time: time
    end_time: time
    grace_period_mins: int = 5
    buffer_mins: int = 15
    break_deduct_mins: int = 0
    is_deleted: int = 0

class ShiftCreate(ShiftBase):
    org_id: UUID

class ShiftUpdate(BaseModel):
    shift_name: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    grace_period_mins: Optional[int] = None
    buffer_mins: Optional[int] = None
    break_deduct_mins: Optional[int] = None
    is_deleted: Optional[int] = None

class ShiftResponse(ShiftBase):
    id: int
    org_id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ApiKeyCreate(BaseModel):
    scope: str = Field("camera_edge", min_length=1, max_length=50, pattern=r"^[a-z_]+$")
    rate_limit: int = Field(60, ge=1, le=10_000)

class ApiKeyResponse(BaseModel):
    id: int
    org_id: UUID
    scope: str
    rate_limit: int
    is_revoked: bool

    model_config = ConfigDict(from_attributes=True)
