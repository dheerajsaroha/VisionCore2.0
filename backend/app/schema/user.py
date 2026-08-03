import uuid
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime


# ── Registration ──────────────────────────────────────────────────────────────
class UserSignup(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str
    organization: str
    department: Optional[str] = None
    city: Optional[str] = None


# ── Admin User Creation ───────────────────────────────────────────────────────
class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str
    organization: str
    org_id: Optional[uuid.UUID] = None  # Injected server-side from JWT


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[int] = None
    role: Optional[str] = None
    dept_id: Optional[int] = None
    shift_id: Optional[int] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


# ── Response ──────────────────────────────────────────────────────────────────
class RoleOut(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: int
    full_name: str
    username: str
    email: str
    employee_id: str
    is_active: int
    org_id: uuid.UUID
    role: RoleOut
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    total: int
    users: List["UserResponse"]


# ── Biometric Enrollment ──────────────────────────────────────────────────────
class FaceEnroll(BaseModel):
    face_embedding: Optional[List[float]] = None
    image_base64: Optional[str] = None

