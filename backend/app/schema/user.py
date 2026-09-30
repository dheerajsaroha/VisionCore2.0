import uuid
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
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
    role: str = "Employee"
    organization: Optional[str] = "default"
    org_id: Optional[uuid.UUID] = None  # Injected server-side from JWT
    dept_id: Optional[int] = None
    shift_id: Optional[int] = None
    phone: Optional[str] = None
    employee_id: Optional[str] = None
    designation: Optional[str] = None
    employment_type: Optional[str] = "EMPLOYEE"
    reporting_manager_id: Optional[int] = None
    branch_id: Optional[int] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[int] = None
    role: Optional[str] = None
    dept_id: Optional[int] = None
    shift_id: Optional[int] = None
    phone: Optional[str] = None
    designation: Optional[str] = None
    employment_type: Optional[str] = None
    reporting_manager_id: Optional[int] = None
    branch_id: Optional[int] = None


class UserUpdateMe(BaseModel):
    """Fields an authenticated user may change on their own profile.

    Deliberately excludes role, organization, activation and employee identity;
    those remain administrator-managed fields.
    """
    full_name: Optional[str] = None
    email: Optional[str] = None

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_to_none(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


# ── Response ──────────────────────────────────────────────────────────────────
class RoleOut(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class DepartmentOut(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class ShiftOut(BaseModel):
    id: int
    shift_name: str

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
    phone: Optional[str] = None
    dept_id: Optional[int] = None
    shift_id: Optional[int] = None
    department: Optional[DepartmentOut] = None
    shift: Optional[ShiftOut] = None
    has_face_enrolled: Optional[bool] = None
    designation: Optional[str] = None
    employment_type: Optional[str] = None
    manager_name: Optional[str] = None
    manager_id: Optional[int] = None
    branch_id: Optional[int] = None
    location: Optional[str] = None
    last_activity: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    total: int
    users: List["UserResponse"]


# ── Biometric Enrollment ──────────────────────────────────────────────────────
class FaceEnroll(BaseModel):
    face_embedding: Optional[List[float]] = None
    image_base64: Optional[str] = None
