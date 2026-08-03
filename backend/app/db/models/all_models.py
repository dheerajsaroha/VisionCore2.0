# =============================================================================
#  db/models/all_models.py
#  All SQLAlchemy models in one file — zero circular import risk.
#  Individual model files import from here via __init__.py
# =============================================================================
from __future__ import annotations

import uuid
from datetime import datetime, time, timezone
from typing import List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, DateTime,
                         Float, ForeignKey, Index, Integer, Numeric, String, Text, Time,
                         UniqueConstraint, text)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, NVARCHAR


def _utc_now() -> datetime:
    """Return timezone-aware UTC datetime for model defaults."""
    return datetime.now(timezone.utc)


# ── Role ──────────────────────────────────────────────────────────────────────
class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, unique=True, index=True,
                                       comment="Unique role name across all tiers")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True,
                                                        comment="Human-readable role description")
    tier: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                       server_default=text("'organization'"),
                                       comment="platform | organization | system")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                             server_default=text("FALSE"),
                                             comment="System roles cannot be deleted")
    permissions: Mapped[dict] = mapped_column(JSONB, nullable=False,
                                               server_default=text("'[]'::jsonb"),
                                               comment="Legacy flat permission list — use RolePermission instead")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    users: Mapped[List["User"]] = relationship("User", back_populates="role")
    role_permissions: Mapped[List["RolePermission"]] = relationship(
        "RolePermission", back_populates="role", cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint("name", name="uq_roles_name"),
        Index("ix_roles_tier", "tier"),
    )
    def __repr__(self): return f"<Role {self.id} {self.name!r} tier={self.tier}>"


# ── Permission ────────────────────────────────────────────────────────────────
class Permission(Base):
    """Granular permission definitions — the atomic unit of authorization."""
    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, unique=True, index=True,
                                       comment="Dot-notation: e.g. 'users.read', 'attendance.checkin'")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True,
                                                        comment="Human-readable description")
    module: Mapped[Optional[str]] = mapped_column(NVARCHAR(50), nullable=True, index=True,
                                                   comment="Grouping: auth | users | attendance | payroll | etc")
    group: Mapped[Optional[str]] = mapped_column(NVARCHAR(50), nullable=True,
                                                  comment="Sub-group within module: read | write | admin")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                             server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    role_permissions: Mapped[List["RolePermission"]] = relationship(
        "RolePermission", back_populates="permission", cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint("name", name="uq_permissions_name"),
        Index("ix_permissions_module", "module"),
    )
    def __repr__(self): return f"<Permission {self.id} {self.name!r}>"


# ── RolePermission (Many-to-Many Join) ────────────────────────────────────────
class RolePermission(Base):
    """Maps roles to permissions (many-to-many)."""
    __tablename__ = "role_permissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id", ondelete="CASCADE"),
                                          nullable=False, index=True)
    permission_id: Mapped[int] = mapped_column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"),
                                                nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    role: Mapped["Role"] = relationship("Role", back_populates="role_permissions")
    permission: Mapped["Permission"] = relationship("Permission", back_populates="role_permissions")
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
        Index("ix_role_permissions_role", "role_id"),
        Index("ix_role_permissions_permission", "permission_id"),
    )
    def __repr__(self): return f"<RolePermission role={self.role_id} perm={self.permission_id}>"


# ── SystemSetting ─────────────────────────────────────────────────────────────
class SystemSetting(Base):
    """Global key-value settings that control runtime behavior."""
    __tablename__ = "system_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    setting_key: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, unique=True, index=True)
    setting_value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))
    def __repr__(self): return f"<SystemSetting {self.setting_key}={self.setting_value!r}>"


# ── Organization ──────────────────────────────────────────────────────────────
class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           server_default=text("uuid_generate_v4()"))
    name: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False, index=True)
    legal_id: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, unique=True)
    blockchain_root_key: Mapped[Optional[str]] = mapped_column(NVARCHAR(255), nullable=True)
    zkp_threshold: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False,
                                                  server_default=text("0.98"))
    logo_url: Mapped[Optional[str]] = mapped_column(NVARCHAR(512), nullable=True)
    primary_color: Mapped[str] = mapped_column(NVARCHAR(7), nullable=False,
                                                server_default=text("'#4F46E5'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                            default=True,
                                            server_default=text("TRUE"))
    status: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False,
                                         default="ACTIVE",
                                         server_default=text("'ACTIVE'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    api_keys:    Mapped[List["OrgApiKey"]]  = relationship("OrgApiKey",  back_populates="organization",
                                                            cascade="all, delete-orphan")
    departments: Mapped[List["Department"]] = relationship("Department", back_populates="organization")
    shifts:      Mapped[List["Shift"]]      = relationship("Shift",      back_populates="organization")
    users:       Mapped[List["User"]]       = relationship("User",       back_populates="organization")
    tickets:     Mapped[List["Ticket"]]     = relationship("Ticket",     back_populates="organization")
    reimbursements: Mapped[List["Reimbursement"]] = relationship("Reimbursement", back_populates="organization")
    payrolls:    Mapped[List["Payroll"]]    = relationship("Payroll",    back_populates="organization")
    def __repr__(self): return f"<Organization {self.id} {self.name!r}>"


# ── OrgApiKey ─────────────────────────────────────────────────────────────────
class OrgApiKey(Base):
    __tablename__ = "org_api_keys"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False, unique=True,
                                           comment="SHA-256 of raw key — pgcrypto digest()")
    scope: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False,
                                        server_default=text("'write_checkin'"))
    rate_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("100"))
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                             server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    organization: Mapped["Organization"] = relationship("Organization", back_populates="api_keys")
    offline_sync_queue: Mapped[List["OfflineSyncQueue"]] = relationship(
        "OfflineSyncQueue", back_populates="api_key")
    __table_args__ = (
        Index("ix_org_api_keys_active", "key_hash", postgresql_where=text("is_revoked = false")),
    )
    def __repr__(self): return f"<OrgApiKey {self.id} scope={self.scope!r}>"


# ── Department ────────────────────────────────────────────────────────────────
class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                             server_default=text("0"),
                                             comment="0=active, 1=soft-deleted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    organization: Mapped["Organization"] = relationship("Organization", back_populates="departments")
    users: Mapped[List["User"]] = relationship("User", back_populates="department")
    __table_args__ = (
        CheckConstraint("is_deleted IN (0, 1)", name="ck_dept_is_deleted"),
        Index("ix_departments_active", "org_id", postgresql_where=text("is_deleted = 0")),
    )
    def __repr__(self): return f"<Department {self.id} {self.name!r}>"


# ── Shift ─────────────────────────────────────────────────────────────────────
class Shift(Base):
    __tablename__ = "shifts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    shift_name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    start_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    end_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    grace_period_mins: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"),
                                                    comment="Minutes after start before 'Late'")
    buffer_mins: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("15"),
                                              comment="Minutes before start for early clock-in")
    break_deduct_mins: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                             server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    organization: Mapped["Organization"] = relationship("Organization", back_populates="shifts")
    users: Mapped[List["User"]] = relationship("User", back_populates="shift")
    __table_args__ = (
        CheckConstraint("is_deleted IN (0, 1)", name="ck_shifts_is_deleted"),
        CheckConstraint("grace_period_mins >= 0", name="ck_shifts_grace"),
    )
    def __repr__(self): return f"<Shift {self.id} {self.shift_name!r}>"


# ── User ──────────────────────────────────────────────────────────────────────
class User(Base):
    """
    Central identity table.
    hashed_password : bcrypt via passlib (never raw SQL)
    enrollment_token: pgcrypto server_default encode(gen_random_bytes(32),'hex')
    is_deleted      : 0=active 1=soft-deleted — NEVER hard DELETE
    """
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="RESTRICT"),
                                               nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id", ondelete="RESTRICT"),
                                          nullable=False, index=True)
    dept_id: Mapped[Optional[int]] = mapped_column(Integer,
                                                    ForeignKey("departments.id", ondelete="SET NULL"),
                                                    nullable=True, index=True)
    shift_id: Mapped[Optional[int]] = mapped_column(Integer,
                                                     ForeignKey("shifts.id", ondelete="SET NULL"),
                                                     nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    username: Mapped[str] = mapped_column(NVARCHAR(80), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(NVARCHAR(150), nullable=False, unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(NVARCHAR(20), nullable=True)
    employee_id: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False,
                                              unique=True, index=True,
                                              comment="HR / payroll reference code")
    enrollment_token: Mapped[Optional[str]] = mapped_column(
        NVARCHAR(255), nullable=True, unique=True, index=True,
        server_default=text("encode(gen_random_bytes(32), 'hex')"),
        comment="pgcrypto gen_random_bytes — one-time ZKP onboarding link")
    token_expires: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    hashed_password: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False,
                                                  comment="bcrypt passlib — mirrors pgcrypto crypt()")
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                             server_default=text("0"),
                                             comment="0=active 1=soft-deleted")
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1,
                                            server_default=text("1"),
                                            comment="1=active 0=suspended")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    organization: Mapped["Organization"] = relationship("Organization", back_populates="users",
                                                         foreign_keys=[org_id])
    role: Mapped["Role"] = relationship("Role", back_populates="users", foreign_keys=[role_id])
    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="users",
                                                               foreign_keys=[dept_id])
    shift: Mapped[Optional["Shift"]] = relationship("Shift", back_populates="users",
                                                     foreign_keys=[shift_id])
    face_embedding: Mapped[Optional["FaceEmbedding"]] = relationship(
        "FaceEmbedding", back_populates="user", uselist=False)
    attendance_logs: Mapped[List["AttendanceLog"]] = relationship(
        "AttendanceLog", back_populates="user", foreign_keys="AttendanceLog.user_id")
    manual_overrides_as_target: Mapped[List["ManualOverride"]] = relationship(
        "ManualOverride", back_populates="target_user", foreign_keys="ManualOverride.target_user_id")
    manual_overrides_as_admin: Mapped[List["ManualOverride"]] = relationship(
        "ManualOverride", back_populates="admin_user", foreign_keys="ManualOverride.admin_user_id")
    monthly_summaries: Mapped[List["MonthlyGrowthSummary"]] = relationship(
        "MonthlyGrowthSummary", back_populates="user")
    tickets: Mapped[List["Ticket"]] = relationship("Ticket", back_populates="user")
    reimbursements: Mapped[List["Reimbursement"]] = relationship("Reimbursement", back_populates="user", foreign_keys="Reimbursement.user_id")
    payrolls: Mapped[List["Payroll"]] = relationship("Payroll", back_populates="user")
    sessions: Mapped[List["UserSession"]] = relationship("UserSession", back_populates="user")
    __table_args__ = (
        CheckConstraint("is_deleted IN (0, 1)", name="ck_users_is_deleted"),
        CheckConstraint("is_active IN (0, 1)", name="ck_users_is_active"),
        Index("ix_users_active_org", "org_id", postgresql_where=text("is_deleted = 0")),
        Index("ix_users_org_email", "org_id", "email"),
    )
    def __repr__(self): return f"<User {self.id} {self.username!r} active={self.is_active}>"


# ── UserSession ──────────────────────────────────────────────────────────────
class UserSession(Base):
    """Persisted authentication session for a user and device."""
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("uuid_generate_v4()"))
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    jti: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    refresh_jti: Mapped[Optional[str]] = mapped_column(NVARCHAR(255), nullable=True)
    session_name: Mapped[Optional[str]] = mapped_column(NVARCHAR(255), nullable=True)
    device_name: Mapped[Optional[str]] = mapped_column(NVARCHAR(255), nullable=True)
    device_type: Mapped[Optional[str]] = mapped_column(NVARCHAR(50), nullable=True)
    browser: Mapped[Optional[str]] = mapped_column(NVARCHAR(128), nullable=True)
    browser_version: Mapped[Optional[str]] = mapped_column(NVARCHAR(64), nullable=True)
    operating_system: Mapped[Optional[str]] = mapped_column(NVARCHAR(128), nullable=True)
    operating_system_version: Mapped[Optional[str]] = mapped_column(NVARCHAR(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(NVARCHAR(45), nullable=True)
    login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    logout_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[Optional[str]] = mapped_column(NVARCHAR(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now,
        server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", back_populates="sessions")

    __table_args__ = (
        UniqueConstraint("jti", name="uq_user_sessions_jti"),
        Index("ix_user_sessions_user_id", "user_id"),
        Index("ix_user_sessions_jti", "jti"),
        Index("ix_user_sessions_is_active", "is_active"),
        Index("ix_user_sessions_expires_at", "expires_at"),
        Index("ix_user_sessions_last_activity_at", "last_activity_at"),
    )

    def __repr__(self): return f"<UserSession {self.id} user={self.user_id} active={self.is_active}>"


# ── FaceEmbedding ─────────────────────────────────────────────────────────────
class FaceEmbedding(Base):
    """pgvector VECTOR(128). HNSW index created via Alembic raw SQL."""
    __tablename__ = "face_embeddings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                                          nullable=False, index=True)
    embedding: Mapped[List[float]] = mapped_column(Vector(128), nullable=False,
                                                    comment="FaceNet 128-d — pgvector VECTOR(128)")
    zkp_public_commitment: Mapped[Optional[str]] = mapped_column(
        NVARCHAR(512), nullable=True, comment="Schnorr P=x·G — no raw biometric stored")
    model_name: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False,
                                             server_default=text("'Facenet'"))
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1,
                                            server_default=text("1"),
                                            comment="1=current 0=superseded by re-enrollment")
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                   default=_utc_now, server_default=text("NOW()"))
    user: Mapped["User"] = relationship("User", back_populates="face_embedding")
    __table_args__ = (
        CheckConstraint("is_active IN (0, 1)", name="ck_face_embed_is_active"),
        Index("ix_face_embeddings_active_user", "user_id",
              postgresql_where=text("is_active = 1")),
    )
    def __repr__(self): return f"<FaceEmbedding {self.id} user={self.user_id} active={self.is_active}>"


# ── AttendanceLog ─────────────────────────────────────────────────────────────
class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"),
                                          nullable=False, index=True)
    check_in: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                default=_utc_now, server_default=text("NOW()"),
                                                index=True)
    check_out: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True,
                                                           comment="NULL until clock-out")
    status: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False,
                                         comment="on_time|late|early|absent|excused|manual_override")
    emotion: Mapped[Optional[str]] = mapped_column(NVARCHAR(30), nullable=True)
    emotion_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    is_live: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                          server_default=text("0"),
                                          comment="1=liveness passed")
    recognition_distance: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True,
                                                                    comment="pgvector cosine distance at match")
    source: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                         server_default=text("'ai'"),
                                         comment="ai|manual|edge|bulk_import")
    geofence_pass: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gps_lat: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    gps_lng: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                             server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    user: Mapped["User"] = relationship("User", back_populates="attendance_logs",
                                         foreign_keys=[user_id])
    manual_override: Mapped[Optional["ManualOverride"]] = relationship(
        "ManualOverride", back_populates="attendance_log", uselist=False)
    __table_args__ = (
        Index("ix_attendance_user_checkin", "user_id", "check_in",
              postgresql_where=text("is_deleted = 0")),
        Index("ix_attendance_checkin_brin", "check_in", postgresql_using="brin"),
        CheckConstraint("is_deleted IN (0,1)", name="ck_attendance_is_deleted"),
        CheckConstraint("is_live IN (0,1)", name="ck_attendance_is_live"),
        CheckConstraint(
            "status IN ('on_time','late','early','absent','excused','manual_override')",
            name="ck_attendance_status"),
        CheckConstraint("source IN ('ai','manual','edge','bulk_import')",
                        name="ck_attendance_source"),
    )
    def __repr__(self): return f"<AttendanceLog {self.id} user={self.user_id} {self.status!r}>"


# ── ManualOverride ────────────────────────────────────────────────────────────
class ManualOverride(Base):
    __tablename__ = "manual_overrides"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    target_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"),
                                                 nullable=False, index=True)
    admin_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"),
                                                nullable=False, index=True)
    attendance_log_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("attendance_logs.id", ondelete="SET NULL"), nullable=True, index=True)
    reason_category: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    override_status: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False)
    override_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    employee_approved: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                    server_default=text("0"),
                                                    comment="0=pending ZKP approval 1=approved")
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    target_user: Mapped["User"] = relationship("User", back_populates="manual_overrides_as_target",
                                                foreign_keys=[target_user_id])
    admin_user: Mapped["User"] = relationship("User", back_populates="manual_overrides_as_admin",
                                               foreign_keys=[admin_user_id])
    attendance_log: Mapped[Optional["AttendanceLog"]] = relationship(
        "AttendanceLog", back_populates="manual_override", foreign_keys=[attendance_log_id])
    __table_args__ = (
        CheckConstraint("employee_approved IN (0,1)", name="ck_override_approved"),
        CheckConstraint(
            "reason_category IN ('device_malfunction','forgot_phone','network_outage',"
            "'camera_failure','admin_correction','other')", name="ck_override_reason"),
        Index("ix_override_pending", "target_user_id",
              postgresql_where=text("employee_approved = 0")),
    )
    def __repr__(self): return f"<ManualOverride {self.id} approved={self.employee_approved}>"


# ── BlockchainAuditLog ────────────────────────────────────────────────────────
class BlockchainAuditLog(Base):
    """APPEND-ONLY — no UPDATE, no DELETE, no is_deleted column."""
    __tablename__ = "blockchain_audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    ref_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    ref_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True,
                                           comment="attendance|manual_override|org_onboard|user_enroll|key_revoke")
    record_hash: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False,
                                              comment="SHA-256 hex — pgcrypto encode(digest(),'hex')")
    tx_hash: Mapped[Optional[str]] = mapped_column(NVARCHAR(128), nullable=True)
    block_number: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    anchored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                   default=_utc_now, server_default=text("NOW()"),
                                                   index=True)
    __table_args__ = (
        Index("ix_blockchain_ref", "ref_type", "ref_id"),
        CheckConstraint(
            "ref_type IN ('attendance','manual_override','org_onboard','user_enroll','key_revoke','ticket','payroll','reimbursement')",
            name="ck_blockchain_ref_type"),
    )
    def __repr__(self): return f"<BlockchainAuditLog {self.id} {self.ref_type!r} ref={self.ref_id}>"


# ── MonthlyGrowthSummary ──────────────────────────────────────────────────────
class MonthlyGrowthSummary(Base):
    __tablename__ = "monthly_growth_summary"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                                          nullable=False, index=True)
    month_year: Mapped[str] = mapped_column(NVARCHAR(7), nullable=False, comment="'2026-03'")
    total_present: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_late: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_absent: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_manual: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    avg_emotion_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    stress_event_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    burnout_risk_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True,
                                                                 comment=">40 triggers AI Nudge")
    productivity_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    growth_index: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                   default=_utc_now, server_default=text("NOW()"))
    user: Mapped["User"] = relationship("User", back_populates="monthly_summaries")
    __table_args__ = (
        UniqueConstraint("user_id", "month_year", name="uq_monthly_user_month"),
        Index("ix_monthly_burnout_risk", "burnout_risk_score",
              postgresql_where=text("burnout_risk_score > 40")),
    )
    def __repr__(self): return f"<MonthlyGrowthSummary {self.user_id} {self.month_year!r}>"


# ── OfflineSyncQueue ──────────────────────────────────────────────────────────
class OfflineSyncQueue(Base):
    __tablename__ = "offline_sync_queue"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    device_key_id: Mapped[int] = mapped_column(Integer,
                                                ForeignKey("org_api_keys.id", ondelete="RESTRICT"),
                                                nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    synced: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"),
                                         comment="0=pending 1=synced")
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_key: Mapped["OrgApiKey"] = relationship("OrgApiKey", back_populates="offline_sync_queue",
                                                 foreign_keys=[device_key_id])
    __table_args__ = (
        CheckConstraint("synced IN (0,1)", name="ck_sync_synced"),
        Index("ix_sync_queue_pending", "captured_at", postgresql_where=text("synced = 0")),
    )
    def __repr__(self): return f"<OfflineSyncQueue {self.id} synced={self.synced}>"


# ── Ticket ────────────────────────────────────────────────────────────────────
class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                                          nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    title: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, default="open",
                                         server_default=text("'open'"),
                                         comment="open|resolved|escalated|closed")
    priority: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, default="medium",
                                           server_default=text("'medium'"),
                                           comment="low|medium|high|critical")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", back_populates="tickets")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="tickets")

    __table_args__ = (
        CheckConstraint("status IN ('open','resolved','escalated','closed')", name="ck_ticket_status"),
        CheckConstraint("priority IN ('low','medium','high','critical')", name="ck_ticket_priority"),
    )

# ── Reimbursement ─────────────────────────────────────────────────────────────
class Reimbursement(Base):
    __tablename__ = "reimbursements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                                          nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, default="pending",
                                         server_default=text("'pending'"),
                                         comment="pending|approved|rejected|paid")
    receipt_url: Mapped[Optional[str]] = mapped_column(NVARCHAR(512), nullable=True)
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                    default=_utc_now, server_default=text("NOW()"))
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="reimbursements", foreign_keys=[user_id])
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by])
    organization: Mapped["Organization"] = relationship("Organization", back_populates="reimbursements")

    __table_args__ = (
        CheckConstraint("status IN ('pending','approved','rejected','paid')", name="ck_reimb_status"),
    )

# ── Payroll ───────────────────────────────────────────────────────────────────
class Payroll(Base):
    __tablename__ = "payrolls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                                          nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    base_salary: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    deductions: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0.0)
    reimbursements_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0.0)
    total_salary: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, default="draft",
                                         server_default=text("'draft'"),
                                         comment="draft|pending|paid")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                    default=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", back_populates="payrolls")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="payrolls")

    __table_args__ = (
        CheckConstraint("status IN ('draft','pending','paid')", name="ck_payroll_status"),
        UniqueConstraint("user_id", "month", "year", name="uq_user_monthly_payroll"),
    )


# =============================================================================
#  SUBSCRIPTION & FEATURE MANAGEMENT — Sprint 2, Entity 2
# =============================================================================

# ── SubscriptionPlan ─────────────────────────────────────────────────────────
class SubscriptionPlan(Base):
    """Defines subscription plan tiers (Starter, Professional, Enterprise, etc.)."""
    __tablename__ = "subscription_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    code: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, unique=True, index=True,
                                       comment="Unique plan code: starter|professional|enterprise")
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False,
                                       comment="Display name: Starter|Professional|Enterprise")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True,
                                                        comment="Human-readable plan description")
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"),
                                       comment="Numeric tier: 0=Starter, 1=Professional, 2=Enterprise, etc.")
    monthly_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0,
                                                  server_default=text("0"),
                                                  comment="Monthly price in currency units")
    yearly_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0,
                                                 server_default=text("0"),
                                                 comment="Yearly price (annual discount)")
    currency: Mapped[str] = mapped_column(NVARCHAR(3), nullable=False, server_default=text("'USD'"),
                                           comment="ISO 4217 currency code")
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14,
                                             server_default=text("14"),
                                             comment="Number of free trial days")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                             server_default=text("TRUE"),
                                             comment="Plan is available for assignment")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                             server_default=text("TRUE"),
                                             comment="System plans cannot be deleted")
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                server_default=text("0"),
                                                comment="Sort order for plan listing")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    organization_subscriptions: Mapped[List["OrganizationSubscription"]] = relationship(
        "OrganizationSubscription", back_populates="plan")
    plan_features: Mapped[List["PlanFeature"]] = relationship(
        "PlanFeature", back_populates="plan", cascade="all, delete-orphan")
    licensing_limits: Mapped[List["LicensingLimit"]] = relationship(
        "LicensingLimit", back_populates="plan", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("code", name="uq_subscription_plans_code"),
        Index("ix_subscription_plans_active", "is_active"),
        Index("ix_subscription_plans_tier", "tier"),
    )
    def __repr__(self): return f"<SubscriptionPlan {self.code!r} tier={self.tier}>"


# ── OrganizationSubscription ─────────────────────────────────────────────────
class OrganizationSubscription(Base):
    """Links an organization to a subscription plan with lifecycle management."""
    __tablename__ = "organization_subscriptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False, index=True)
    subscription_plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        NVARCHAR(30), nullable=False, server_default=text("'active'"),
        comment="active|trialing|canceled|expired|past_due|paused")
    billing_cycle: Mapped[str] = mapped_column(
        NVARCHAR(10), nullable=False, server_default=text("'monthly'"),
        comment="monthly|yearly")
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"),
                                                  comment="When subscription became active")
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True,
                                                          comment="When subscription ends/ended")
    next_renewal: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True,
                                                              comment="Next scheduled renewal date")
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                              server_default=text("TRUE"),
                                              comment="Auto-renew at end of billing period")
    trial_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True,
                                                           comment="Trial period end date")
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True,
                                                             comment="When cancellation was requested")
    cancellation_reason: Mapped[Optional[str]] = mapped_column(NVARCHAR(500), nullable=True,
                                                                comment="Reason for cancellation")
    renewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True,
                                                            comment="When subscription was last renewed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan",
                                                     back_populates="organization_subscriptions")

    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_org_subscription_one_per_org"),
        Index("ix_org_subscriptions_status", "status"),
        Index("ix_org_subscriptions_plan", "subscription_plan_id"),
        Index("ix_org_subscriptions_next_renewal", "next_renewal"),
        CheckConstraint(
            "status IN ('active','trialing','canceled','expired','past_due','paused')",
            name="ck_org_subscription_status"),
        CheckConstraint("billing_cycle IN ('monthly','yearly')",
                        name="ck_org_subscription_billing_cycle"),
    )
    def __repr__(self): return f"<OrganizationSubscription org={self.organization_id} plan={self.subscription_plan_id} status={self.status}>"


# ── Feature ──────────────────────────────────────────────────────────────────
class Feature(Base):
    """Feature catalog — defines all features that can be enabled per subscription."""
    __tablename__ = "features"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    code: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, unique=True, index=True,
                                       comment="Unique feature key: attendance|payroll|recruitment|etc")
    module: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True,
                                         comment="Module grouping: attendance|hr|finance|platform|etc")
    name: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False,
                                       comment="Display name: 'Attendance Tracking'")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True,
                                                        comment="Human-readable description")
    category: Mapped[str] = mapped_column(
        NVARCHAR(30), nullable=False, server_default=text("'core'"),
        comment="core|hr|finance|operations|governance|communication|analytics|ai|platform|security")
    dependencies: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True,
                                                          comment="JSON list of feature codes this depends on")
    beta: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                        server_default=text("FALSE"),
                                        comment="Feature is in beta")
    deprecated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                              server_default=text("FALSE"),
                                              comment="Feature is deprecated")
    visibility: Mapped[str] = mapped_column(
        NVARCHAR(20), nullable=False, server_default=text("'public'"),
        comment="public|hidden|internal|admin")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))

    plan_features: Mapped[List["PlanFeature"]] = relationship(
        "PlanFeature", back_populates="feature", cascade="all, delete-orphan")
    feature_flags: Mapped[List["FeatureFlag"]] = relationship(
        "FeatureFlag", back_populates="feature", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("code", name="uq_features_code"),
        Index("ix_features_module", "module"),
        Index("ix_features_category", "category"),
        Index("ix_features_active", "deprecated"),
        CheckConstraint("visibility IN ('public','hidden','internal','admin')",
                        name="ck_features_visibility"),
        CheckConstraint("category IN ('core','hr','finance','operations','governance',"
                        "'communication','analytics','ai','platform','security')",
                        name="ck_features_category"),
    )
    def __repr__(self): return f"<Feature {self.code!r} module={self.module}>"


# ── PlanFeature (Maps SubscriptionPlan → Feature) ───────────────────────────
class PlanFeature(Base):
    """Maps a subscription plan to features it enables."""
    __tablename__ = "plan_features"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subscription_plans.id", ondelete="CASCADE"),
        nullable=False, index=True)
    feature_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                           server_default=text("TRUE"),
                                           comment="Feature is enabled by this plan")
    default_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                              server_default=text("TRUE"),
                                              comment="Feature is ON by default")
    configurable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                                server_default=text("TRUE"),
                                                comment="Organization can override via feature flags")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))

    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan", back_populates="plan_features")
    feature: Mapped["Feature"] = relationship("Feature", back_populates="plan_features")

    __table_args__ = (
        UniqueConstraint("plan_id", "feature_id", name="uq_plan_feature"),
        Index("ix_plan_features_plan", "plan_id"),
        Index("ix_plan_features_feature", "feature_id"),
    )
    def __repr__(self): return f"<PlanFeature plan={self.plan_id} feature={self.feature_id} enabled={self.enabled}>"


# ── FeatureFlag (Organization-specific override) ────────────────────────────
class FeatureFlag(Base):
    """Organization-specific feature override — allows enabling/disabling features per org."""
    __tablename__ = "feature_flags"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True)
    feature_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                           comment="Override value: True=enable, False=disable")
    reason: Mapped[Optional[str]] = mapped_column(NVARCHAR(500), nullable=True,
                                                   comment="Why this override was applied")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True,
                                                            comment="Override expiration (NULL=permanent)")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    feature: Mapped["Feature"] = relationship("Feature", back_populates="feature_flags")

    __table_args__ = (
        UniqueConstraint("organization_id", "feature_id", name="uq_org_feature_flag"),
        Index("ix_feature_flags_org", "organization_id"),
        Index("ix_feature_flags_feature", "feature_id"),
        Index("ix_feature_flags_expires", "expires_at"),
    )
    def __repr__(self): return f"<FeatureFlag org={self.organization_id} feature={self.feature_id} enabled={self.enabled}>"


# ── LicensingLimit (Per-plan resource limits) ────────────────────────────────
class LicensingLimit(Base):
    """Defines resource limits for a subscription plan."""
    __tablename__ = "licensing_limits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subscription_plans.id", ondelete="CASCADE"),
        nullable=False, index=True)
    limit_type: Mapped[str] = mapped_column(
        NVARCHAR(50), nullable=False, index=True,
        comment="employees|departments|teams|projects|storage_gb|api_calls_per_min|"
                "api_keys|camera_devices|biometric_devices|reports_per_day|"
                "exports_per_day|concurrent_sessions|notification_templates|"
                "training_courses|workflow_definitions|automation_rules|"
                "marketplace_apps|integrations|custom_roles|custom_dashboards")
    soft_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True,
                                                       comment="Soft limit (warning threshold)")
    hard_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True,
                                                       comment="Hard limit (enforcement threshold)")
    is_unlimited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                                server_default=text("FALSE"),
                                                comment="No limit on this resource")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True,
                                                        comment="Human-readable description of the limit")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))

    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan", back_populates="licensing_limits")

    __table_args__ = (
        UniqueConstraint("plan_id", "limit_type", name="uq_plan_limit_type"),
        Index("ix_licensing_limits_plan", "plan_id"),
        Index("ix_licensing_limits_type", "limit_type"),
        CheckConstraint(
            "NOT (is_unlimited = TRUE AND hard_limit IS NOT NULL)",
            name="ck_limit_unlimited_no_hard"),
    )
    def __repr__(self): return f"<LicensingLimit plan={self.plan_id} type={self.limit_type}>"


# =============================================================================
#  ENTERPRISE DATA SCOPE & RESOURCE OWNERSHIP MODELS (Sprint 2, Entity 3)
# =============================================================================

# ── DataScope (Catalog of available data scopes) ──────────────────────────────
class DataScope(Base):
    """Catalog of available enterprise data scopes."""
    __tablename__ = "data_scopes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    code: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, unique=True, index=True,
                                      comment="platform|multi_org|organization|business_unit|department|team|project|location|reporting_hierarchy|self|custom")
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scope_level: Mapped[int] = mapped_column(Integer, nullable=False, default=10, index=True,
                                              comment="Hierarchy level: 100=platform, 80=org, 60=dept, 50=team, 20=hierarchy, 10=self, 0=custom")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    role_data_scopes: Mapped[List["RoleDataScope"]] = relationship("RoleDataScope", back_populates="data_scope", cascade="all, delete-orphan")

    def __repr__(self): return f"<DataScope {self.code!r} level={self.scope_level}>"


# ── RoleDataScope (Mapping Roles/Permissions to Data Scopes) ─────────────────
class RoleDataScope(Base):
    """Maps a role (and optionally specific permission) to a Data Scope in an org."""
    __tablename__ = "role_data_scopes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    data_scope_id: Mapped[int] = mapped_column(Integer, ForeignKey("data_scopes.id", ondelete="RESTRICT"), nullable=False, index=True)
    permission_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=True, index=True, comment="NULL = applies to all permissions of the role")
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True, comment="NULL = global default rule")
    scope_parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), comment="Dynamic criteria (e.g. dept_ids, team_ids)")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    role: Mapped["Role"] = relationship("Role")
    data_scope: Mapped["DataScope"] = relationship("DataScope", back_populates="role_data_scopes")
    permission: Mapped[Optional["Permission"]] = relationship("Permission")
    organization: Mapped[Optional["Organization"]] = relationship("Organization")

    __table_args__ = (
        Index("ix_role_data_scopes_lookup", "role_id", "permission_id", "organization_id"),
    )
    def __repr__(self): return f"<RoleDataScope role={self.role_id} scope={self.data_scope_id}>"


# ── ResourceOwnership (Resource-level Ownership Mapping) ─────────────────────
class ResourceOwnership(Base):
    """Maps specific domain entities to their users/org owners and ownership types."""
    __tablename__ = "resource_ownerships"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    entity_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True, comment="employee|attendance|leave|payroll|referral|document|asset|etc")
    entity_id: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, index=True, comment="String/UUID string of target entity PK")
    owner_type: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, index=True, comment="creator|assignee|subject|reviewer|approver|manager|organization|delegate")
    owner_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    owner_org_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    meta_data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    owner_user: Mapped[Optional["User"]] = relationship("User")
    owner_org: Mapped[Optional["Organization"]] = relationship("Organization")

    __table_args__ = (
        Index("ix_resource_ownership_lookup", "entity_type", "entity_id", "owner_user_id"),
        Index("ix_resource_ownership_user", "owner_user_id", "is_active"),
    )
    def __repr__(self): return f"<ResourceOwnership entity={self.entity_type}:{self.entity_id} owner={self.owner_user_id} type={self.owner_type}>"


# ── OwnershipHistory (Audit Trail for Ownership Changes) ────────────────────
class OwnershipHistory(Base):
    """Audit log tracking ownership creation, transfers, delegations, and revocations."""
    __tablename__ = "ownership_histories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    resource_ownership_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("resource_ownerships.id", ondelete="SET NULL"), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, index=True, comment="created|assigned|transferred|delegated|revoked|expired|recovered")
    previous_owner_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    new_owner_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    previous_owner_type: Mapped[Optional[str]] = mapped_column(NVARCHAR(30), nullable=True)
    new_owner_type: Mapped[Optional[str]] = mapped_column(NVARCHAR(30), nullable=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    actor_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_user_id])
    previous_owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[previous_owner_user_id])
    new_owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[new_owner_user_id])

    def __repr__(self): return f"<OwnershipHistory entity={self.entity_type}:{self.entity_id} action={self.action}>"


# ── OwnershipDelegation (Temporary Delegation of Rights) ─────────────────────
class OwnershipDelegation(Base):
    """Temporary delegation of resource ownership or permission scope between users."""
    __tablename__ = "ownership_delegations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    delegator_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    delegatee_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[Optional[str]] = mapped_column(NVARCHAR(50), nullable=True, comment="NULL = all entity types")
    permission_code: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True, comment="NULL = all delegator permissions")
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    delegator: Mapped["User"] = relationship("User", foreign_keys=[delegator_user_id])
    delegatee: Mapped["User"] = relationship("User", foreign_keys=[delegatee_user_id])
    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        Index("ix_ownership_delegation_active", "delegatee_user_id", "is_active", "start_date", "end_date"),
    )
    def __repr__(self): return f"<OwnershipDelegation delegator={self.delegator_user_id} delegatee={self.delegatee_user_id}>"


# ── OwnershipRule (Declarative Automatic Ownership Rules) ────────────────────
class OwnershipRule(Base):
    """Rules defining automatic ownership assignment on entity lifecycle events."""
    __tablename__ = "ownership_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    entity_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    default_owner_type: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, default="creator")
    auto_assign_creator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    auto_assign_manager: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    rule_config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    def __repr__(self): return f"<OwnershipRule entity={self.entity_type} name={self.name!r}>"


# ── OwnershipPolicy (Enterprise Policies for Ownership & Delegation) ─────────
class OwnershipPolicy(Base):
    """Enterprise governance policies for ownership transfers, delegation limits, etc."""
    __tablename__ = "ownership_policies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    max_delegation_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    allow_cross_dept_delegation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    require_approval_for_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    policy_config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped[Optional["Organization"]] = relationship("Organization")

    def __repr__(self): return f"<OwnershipPolicy org={self.organization_id} name={self.name!r}>"


# ── OwnershipException (Explicit Granular Access Overrides) ───────────────────
class OwnershipException(Base):
    """Specific user access overrides for individual resources outside standard scope."""
    __tablename__ = "ownership_exceptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, index=True)
    permission_code: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, index=True)
    granted_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    granted_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[granted_by_user_id])

    __table_args__ = (
        Index("ix_ownership_exception_lookup", "user_id", "entity_type", "entity_id", "permission_code", "is_active"),
    )
    def __repr__(self): return f"<OwnershipException user={self.user_id} entity={self.entity_type}:{self.entity_id}>"


# ── ApprovalWorkflow (Master Approval Workflow Definition) ───────────────────
class ApprovalWorkflow(Base):
    """Master definition for configurable enterprise approval workflows."""
    __tablename__ = "approval_workflows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True, comment="leave|attendance|payroll|expense|asset|travel|exit|recruitment|policy|etc")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_event: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, default="on_create")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    auto_approval_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    workflow_config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped[Optional["Organization"]] = relationship("Organization")
    stages: Mapped[list["ApprovalStage"]] = relationship("ApprovalStage", back_populates="workflow", cascade="all, delete-orphan", order_by="ApprovalStage.stage_order")

    __table_args__ = (
        Index("ix_approval_workflow_org_entity", "organization_id", "entity_type", "is_active"),
    )
    def __repr__(self): return f"<ApprovalWorkflow code={self.code!r} entity={self.entity_type} org={self.organization_id}>"


# ── ApprovalStage (Workflow Approval Stages / Steps) ─────────────────────────
class ApprovalStage(Base):
    """Stages / steps belonging to an ApprovalWorkflow."""
    __tablename__ = "approval_stages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("approval_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    approval_type: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, default="single", comment="single|parallel|sequential")
    min_approvals: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sla_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    allow_rework: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    auto_approve_condition: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    workflow: Mapped["ApprovalWorkflow"] = relationship("ApprovalWorkflow", back_populates="stages")
    approvers: Mapped[list["ApprovalStageApprover"]] = relationship("ApprovalStageApprover", back_populates="stage", cascade="all, delete-orphan", order_by="ApprovalStageApprover.sequence_order")

    __table_args__ = (
        Index("ix_approval_stage_wf_order", "workflow_id", "stage_order"),
    )
    def __repr__(self): return f"<ApprovalStage wf={self.workflow_id} order={self.stage_order} name={self.name!r}>"


# ── ApprovalStageApprover (Stage Approver Definitions) ───────────────────────
class ApprovalStageApprover(Base):
    """Designated approver entities (users, roles, managers) assigned to a stage."""
    __tablename__ = "approval_stage_approvers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    stage_id: Mapped[int] = mapped_column(Integer, ForeignKey("approval_stages.id", ondelete="CASCADE"), nullable=False, index=True)
    approver_type: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, comment="role|user|manager|dept_head")
    approver_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    approver_role_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True, index=True)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    stage: Mapped["ApprovalStage"] = relationship("ApprovalStage", back_populates="approvers")
    user: Mapped[Optional["User"]] = relationship("User")
    role: Mapped[Optional["Role"]] = relationship("Role")

    def __repr__(self): return f"<ApprovalStageApprover stage={self.stage_id} type={self.approver_type}>"


# ── ApprovalTemplate (Pre-configured Workflow Blueprints) ───────────────────
class ApprovalTemplate(Base):
    """Blueprint templates for rapidly instantiating standard workflows."""
    __tablename__ = "approval_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    code: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    template_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    def __repr__(self): return f"<ApprovalTemplate code={self.code!r} entity={self.entity_type}>"


# ── ApprovalRequest (Active Workflow Instances) ──────────────────────────────
class ApprovalRequest(Base):
    """Active instance of an approval request submitted for a resource."""
    __tablename__ = "approval_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("approval_workflows.id", ondelete="RESTRICT"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    requester_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, index=True)
    current_stage_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("approval_stages.id", ondelete="SET NULL"), nullable=True, index=True)
    current_stage_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, default="pending", index=True, comment="pending|approved|rejected|returned|cancelled|escalated")
    priority: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, default="medium", comment="low|medium|high|urgent")
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    title: Mapped[Optional[str]] = mapped_column(NVARCHAR(200), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    workflow: Mapped["ApprovalWorkflow"] = relationship("ApprovalWorkflow")
    organization: Mapped["Organization"] = relationship("Organization")
    requester: Mapped["User"] = relationship("User", foreign_keys=[requester_user_id])
    current_stage: Mapped[Optional["ApprovalStage"]] = relationship("ApprovalStage")
    actions: Mapped[list["ApprovalAction"]] = relationship("ApprovalAction", back_populates="request", cascade="all, delete-orphan", order_by="ApprovalAction.created_at")

    __table_args__ = (
        Index("ix_approval_req_lookup", "organization_id", "entity_type", "entity_id"),
        Index("ix_approval_req_status", "requester_user_id", "status"),
    )
    def __repr__(self): return f"<ApprovalRequest id={self.id} entity={self.entity_type}:{self.entity_id} status={self.status}>"


# ── ApprovalAction (Approval Decision Records) ───────────────────────────────
class ApprovalAction(Base):
    """Decision action record (approve, reject, return, reassign, delegate)."""
    __tablename__ = "approval_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("approval_stages.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, index=True, comment="approve|reject|return|reassign|delegate|escalate|auto_approve")
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta_data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    request: Mapped["ApprovalRequest"] = relationship("ApprovalRequest", back_populates="actions")
    actor: Mapped["User"] = relationship("User")
    stage: Mapped[Optional["ApprovalStage"]] = relationship("ApprovalStage")

    def __repr__(self): return f"<ApprovalAction req={self.request_id} action={self.action} actor={self.actor_user_id}>"


# ── ApprovalHistory (Immutable Request Transition Log) ───────────────────────
class ApprovalHistory(Base):
    """Immutable log of request state and stage transitions."""
    __tablename__ = "approval_wf_histories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status: Mapped[Optional[str]] = mapped_column(NVARCHAR(30), nullable=True)
    to_status: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False)
    from_stage_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    to_stage_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    request: Mapped["ApprovalRequest"] = relationship("ApprovalRequest")
    actor: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self): return f"<ApprovalHistory req={self.request_id} {self.from_status}->{self.to_status}>"


# ── ApprovalEscalation (Auto-Escalation Rules) ───────────────────────────────
class ApprovalEscalation(Base):
    """Auto-escalation rules for overdue approval requests."""
    __tablename__ = "approval_escalations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("approval_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("approval_stages.id", ondelete="CASCADE"), nullable=True, index=True)
    timeout_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    target_type: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, default="role", comment="role|user|manager")
    target_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    target_role_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    workflow: Mapped["ApprovalWorkflow"] = relationship("ApprovalWorkflow")
    target_user: Mapped[Optional["User"]] = relationship("User")
    target_role: Mapped[Optional["Role"]] = relationship("Role")

    def __repr__(self): return f"<ApprovalEscalation wf={self.workflow_id} hours={self.timeout_hours}>"


# ── ApprovalDelegation (Time-bound Approval Delegation) ──────────────────────
class ApprovalDelegation(Base):
    """Temporary delegation of approval authority between users."""
    __tablename__ = "approval_wf_delegations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    delegator_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    delegatee_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[Optional[str]] = mapped_column(NVARCHAR(50), nullable=True, comment="NULL = all entity types")
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    delegator: Mapped["User"] = relationship("User", foreign_keys=[delegator_user_id])
    delegatee: Mapped["User"] = relationship("User", foreign_keys=[delegatee_user_id])
    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        Index("ix_approval_wf_del_active", "delegatee_user_id", "is_active", "start_date", "end_date"),
    )
    def __repr__(self): return f"<ApprovalDelegation delegator={self.delegator_user_id} delegatee={self.delegatee_user_id}>"


# ── WorkflowCondition (Stage Routing / Skipping Rules) ───────────────────────
class WorkflowCondition(Base):
    """Dynamic condition rules for routing requests or skipping stages."""
    __tablename__ = "workflow_conditions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("approval_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("approval_stages.id", ondelete="CASCADE"), nullable=True, index=True)
    condition_type: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, default="skip_stage", comment="skip_stage|auto_approve|require_stage")
    field_name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    operator: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, default="equals", comment="equals|not_equals|greater_than|less_than|in|contains")
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    workflow: Mapped["ApprovalWorkflow"] = relationship("ApprovalWorkflow")
    stage: Mapped[Optional["ApprovalStage"]] = relationship("ApprovalStage")

    def __repr__(self): return f"<WorkflowCondition wf={self.workflow_id} field={self.field_name} op={self.operator}>"


# ── WorkflowVariable (Workflow Instance Metadata) ─────────────────────────────
class WorkflowVariable(Base):
    """Key-value runtime variables attached to active workflow requests."""
    __tablename__ = "workflow_variables"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, default="string")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    request: Mapped["ApprovalRequest"] = relationship("ApprovalRequest")

    def __repr__(self): return f"<WorkflowVariable req={self.request_id} key={self.key!r}>"


# ── WorkflowAudit (Governance & Engine Audit Log) ────────────────────────────
class WorkflowAudit(Base):
    """System-level audit log of workflow definitions, rule modifications, and engine events."""
    __tablename__ = "workflow_audits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped[Optional["Organization"]] = relationship("Organization")
    actor: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self): return f"<WorkflowAudit event={self.event_type} actor={self.actor_user_id}>"


# ── ApprovalProxy (Proxy Approver Mapping) ───────────────────────────────────
class ApprovalProxy(Base):
    """Mapping of primary approvers to backup proxy approvers."""
    __tablename__ = "approval_proxies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    primary_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    proxy_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    primary_user: Mapped["User"] = relationship("User", foreign_keys=[primary_user_id])
    proxy_user: Mapped["User"] = relationship("User", foreign_keys=[proxy_user_id])
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<ApprovalProxy primary={self.primary_user_id} proxy={self.proxy_user_id}>"


# =============================================================================
# ENTITY 5: ENTERPRISE DYNAMIC ROLES & ROLE TEMPLATE ENGINE
# =============================================================================

# ── DynamicRole (Master Configurable Role Model) ──────────────────────────────
class DynamicRole(Base):
    """Dynamic, organization-configurable role definition."""
    __tablename__ = "dynamic_roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    code: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tier: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, default="organization", server_default=text("'organization'")) # platform, organization, system, custom
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    parent_role_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("dynamic_roles.id", ondelete="SET NULL"), nullable=True, index=True)
    template_code: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    status: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, default="active", server_default=text("'active'")) # active, disabled, archived, draft
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    permissions_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    data_scopes_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    approval_rights_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    features_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped[Optional["Organization"]] = relationship("Organization")
    parent_role: Mapped[Optional["DynamicRole"]] = relationship("DynamicRole", remote_side=[id])

    def __repr__(self): return f"<DynamicRole id={self.id} code={self.code!r} tier={self.tier!r}>"


# ── RoleTemplate (Built-in Blueprint Templates) ──────────────────────────────
class RoleTemplate(Base):
    """Pre-configured blueprint template for rapid organization role creation."""
    __tablename__ = "role_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    code: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(150), nullable=False)
    category: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, default="hr") # hr, finance, admin, security, employee
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    template_config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    def __repr__(self): return f"<RoleTemplate code={self.code!r} category={self.category!r}>"


# ── RoleInheritance (DAG Multi-Level Role Hierarchy) ─────────────────────────
class RoleInheritance(Base):
    """Explicit Directed Acyclic Graph (DAG) parent-child role inheritance mapping."""
    __tablename__ = "role_inheritances"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    parent_role_id: Mapped[int] = mapped_column(Integer, ForeignKey("dynamic_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    child_role_id: Mapped[int] = mapped_column(Integer, ForeignKey("dynamic_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    inherit_permissions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    inherit_scopes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    inherit_workflows: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    override_rules_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    parent_role: Mapped["DynamicRole"] = relationship("DynamicRole", foreign_keys=[parent_role_id])
    child_role: Mapped["DynamicRole"] = relationship("DynamicRole", foreign_keys=[child_role_id])

    def __repr__(self): return f"<RoleInheritance parent={self.parent_role_id} -> child={self.child_role_id}>"


# ── RoleVersion (Role Change History & Snapshot Rollback) ─────────────────────
class RoleVersion(Base):
    """Complete snapshot versioning history for dynamic roles."""
    __tablename__ = "role_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("dynamic_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    role: Mapped["DynamicRole"] = relationship("DynamicRole")
    created_by_user: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self): return f"<RoleVersion role={self.role_id} v={self.version}>"


# ── UserRoleAssignment (User Multi-Role & Expiry Mapping) ────────────────────
class UserRoleAssignment(Base):
    """Multi-role assignments for users with primary flag and expiry dates."""
    __tablename__ = "user_role_assignments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("dynamic_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    role: Mapped["DynamicRole"] = relationship("DynamicRole")
    organization: Mapped["Organization"] = relationship("Organization")
    assigned_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_by_user_id])

    def __repr__(self): return f"<UserRoleAssignment user={self.user_id} role={self.role_id} primary={self.is_primary}>"


# ── RoleAssignmentHistory (Audit Log of Role Assignments) ─────────────────────
class RoleAssignmentHistory(Base):
    """Historical record of role assignment and revocation events."""
    __tablename__ = "role_assignment_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("dynamic_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False) # assigned, revoked, expired, primary_changed
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    role: Mapped["DynamicRole"] = relationship("DynamicRole")
    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_user_id])

    def __repr__(self): return f"<RoleAssignmentHistory user={self.user_id} action={self.action}>"


# ── RoleApproval (Governance Approval for Role Changes) ───────────────────────
class RoleApproval(Base):
    """Governance approval requests for sensitive role policy modifications."""
    __tablename__ = "role_approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("dynamic_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, default="pending", server_default=text("'pending'")) # pending, approved, rejected
    proposed_changes_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    role: Mapped["DynamicRole"] = relationship("DynamicRole")
    requested_by: Mapped["User"] = relationship("User", foreign_keys=[requested_by_user_id])
    approved_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by_user_id])

    def __repr__(self): return f"<RoleApproval role={self.role_id} status={self.status}>"


# ── RoleClone (Role Clone Audit Log) ─────────────────────────────────────────
class RoleClone(Base):
    """Audit log tracking role cloning operations."""
    __tablename__ = "role_clones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    source_role_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("dynamic_roles.id", ondelete="SET NULL"), nullable=True)
    source_template_code: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    new_role_id: Mapped[int] = mapped_column(Integer, ForeignKey("dynamic_roles.id", ondelete="CASCADE"), nullable=False)
    cloned_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    new_role: Mapped["DynamicRole"] = relationship("DynamicRole", foreign_keys=[new_role_id])
    cloned_by: Mapped["User"] = relationship("User", foreign_keys=[cloned_by_user_id])

    def __repr__(self): return f"<RoleClone new_role={self.new_role_id}>"


# ── RoleImportExport (Role Data Import/Export Payload Store) ─────────────────
class RoleImportExport(Base):
    """Storage for role export payloads and import tracking."""
    __tablename__ = "role_import_exports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    operation_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False) # export, import
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    created_by: Mapped["User"] = relationship("User")

    def __repr__(self): return f"<RoleImportExport op={self.operation_type} org={self.organization_id}>"


# ── RoleAudit (Immutable Role Event Log) ─────────────────────────────────────
class RoleAudit(Base):
    """Immutable audit trail for all dynamic role and template lifecycle events."""
    __tablename__ = "role_audits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped[Optional["Organization"]] = relationship("Organization")
    actor: Mapped[Optional["User"]] = relationship("User")


    def __repr__(self): return f"<RoleAudit event={self.event_type} actor={self.actor_user_id}>"


# =============================================================================
# SPRINT 3 — MODULE 1: LEAVE MANAGEMENT
# =============================================================================

class LeaveType(Base):
    """Leave type configuration per organization (Annual, Sick, Casual, etc.)"""
    __tablename__ = "leave_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_days_per_year: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_days_per_request: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    carry_forward: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_carry_forward_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requires_document: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    min_notice_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    gender_specific: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    balances: Mapped[List["LeaveBalance"]] = relationship("LeaveBalance", back_populates="leave_type")
    requests: Mapped[List["LeaveRequest"]] = relationship("LeaveRequest", back_populates="leave_type")

    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_leave_types_org_code"),)

    def __repr__(self): return f"<LeaveType {self.code} org={self.organization_id}>"


class LeavePolicy(Base):
    """Org-level leave policy configuration."""
    __tablename__ = "leave_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    policy_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2025)
    accrual_type: Mapped[str] = mapped_column(String(50), nullable=False, default="yearly")
    allow_negative_balance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_approve_after_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    policy_config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<LeavePolicy {self.name} org={self.organization_id}>"


class LeaveBalance(Base):
    """Per-user leave balance ledger."""
    __tablename__ = "leave_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type_id: Mapped[int] = mapped_column(ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False, default=2025)
    entitled_days: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    used_days: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    pending_days: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    carried_forward_days: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    adjusted_days: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User")
    leave_type: Mapped["LeaveType"] = relationship("LeaveType", back_populates="balances")
    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (UniqueConstraint("user_id", "leave_type_id", "year", name="uq_leave_balance_user_type_year"),)

    @property
    def available_days(self) -> float:
        return max(0.0, self.entitled_days + self.carried_forward_days + self.adjusted_days - self.used_days - self.pending_days)

    def __repr__(self): return f"<LeaveBalance user={self.user_id} type={self.leave_type_id}>"


class LeaveRequest(Base):
    """Individual leave application with approval state machine."""
    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type_id: Mapped[int] = mapped_column(ForeignKey("leave_types.id"), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_days: Mapped[float] = mapped_column(Float, nullable=False)
    is_half_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    half_day_period: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    approver_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approver_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    workflow_request_id: Mapped[Optional[int]] = mapped_column(ForeignKey("approval_requests.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approver_user_id])
    leave_type: Mapped["LeaveType"] = relationship("LeaveType", back_populates="requests")
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<LeaveRequest user={self.user_id} status={self.status}>"


class LeaveAdjustment(Base):
    """Manual leave balance adjustments by HR/Admin."""
    __tablename__ = "leave_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type_id: Mapped[int] = mapped_column(ForeignKey("leave_types.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    adjustment_days: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    adjusted_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    adjusted_by: Mapped["User"] = relationship("User", foreign_keys=[adjusted_by_user_id])
    leave_type: Mapped["LeaveType"] = relationship("LeaveType")
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<LeaveAdjustment user={self.user_id} days={self.adjustment_days}>"


# ── AttendanceCorrection ──────────────────────────────────────────────────────
class AttendanceCorrection(Base):
    """Attendance correction request for regularizing missed or faulty punch-ins/outs."""
    __tablename__ = "attendance_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    attendance_log_id: Mapped[Optional[int]] = mapped_column(ForeignKey("attendance_logs.id", ondelete="SET NULL"), nullable=True)
    requested_clock_in: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_clock_out: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", server_default=text("'pending'"))
    reviewer_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewer_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    reviewer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewer_user_id])
    attendance_log: Mapped[Optional["AttendanceLog"]] = relationship("AttendanceLog")
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<AttendanceCorrection user={self.user_id} status={self.status}>"


# =============================================================================
# SPRINT 3 — MODULE 3: PAYROLL ENHANCEMENT
# =============================================================================

class PayGrade(Base):
    """Pay Grades and Salary Ranges."""
    __tablename__ = "pay_grades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    grade_name: Mapped[str] = mapped_column(String(50), nullable=False)
    min_salary: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    max_salary: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<PayGrade {self.grade_name}>"


class SalaryStructure(Base):
    """Detailed employee salary breakdown structure."""
    __tablename__ = "salary_structures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    pay_grade_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pay_grades.id", ondelete="SET NULL"), nullable=True)
    base_pay: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    hra: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0.0)
    special_allowance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0.0)
    pf_deduction: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0.0)
    tds_deduction: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0.0)
    gross_salary: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    net_salary: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User")
    pay_grade: Mapped[Optional["PayGrade"]] = relationship("PayGrade")
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<SalaryStructure user={self.user_id} net={self.net_salary}>"


class PayrollAdvance(Base):
    """Employee salary advance / loan request."""
    __tablename__ = "payroll_advances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", server_default=text("'pending'"))
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    approved_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by_user_id])
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<PayrollAdvance user={self.user_id} amount={self.amount}>"


# =============================================================================
# SPRINT 3 — MODULE 4: RECRUITMENT & ATS
# =============================================================================

class JobPosting(Base):
    """Job vacancy posting."""
    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[str] = mapped_column(String(100), nullable=False, default="Remote")
    employment_type: Mapped[str] = mapped_column(String(50), nullable=False, default="Full-time") # Full-time, Part-time, Contract
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open", server_default=text("'open'")) # open, closed, draft
    posted_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    posted_by: Mapped["User"] = relationship("User")
    department: Mapped[Optional["Department"]] = relationship("Department")

    def __repr__(self): return f"<JobPosting {self.title}>"


class Candidate(Base):
    """Job applicant pool profile."""
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    resume_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<Candidate {self.full_name}>"


class JobApplication(Base):
    """Applicant tracking pipeline submission."""
    __tablename__ = "job_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False, default="applied", server_default=text("'applied'")) # applied, screening, interview, offer, hired, rejected
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) # 1-5 scale
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    job_posting: Mapped["JobPosting"] = relationship("JobPosting")
    candidate: Mapped["Candidate"] = relationship("Candidate")
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<JobApplication candidate={self.candidate_id} job={self.job_posting_id} stage={self.stage}>"


class InterviewSchedule(Base):
    """Candidate interview scheduling."""
    __tablename__ = "interview_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    interviewer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meeting_link: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="scheduled", server_default=text("'scheduled'")) # scheduled, completed, cancelled

    application: Mapped["JobApplication"] = relationship("JobApplication")
    interviewer: Mapped["User"] = relationship("User")
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<InterviewSchedule app={self.application_id} status={self.status}>"


# =============================================================================
# SPRINT 4 — ENTITY 1: PERFORMANCE MANAGEMENT SYSTEM
# =============================================================================

class PerformanceCycle(Base):
    """Performance review cycle definition (Annual, Quarterly, Probation, etc.)."""
    __tablename__ = "performance_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    cycle_type: Mapped[str] = mapped_column(String(50), nullable=False)  # annual|half_year|quarterly|monthly|probation|promotion|exit|custom
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    review_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft", server_default=text("'draft'"))  # draft|active|closed|archived
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    created_by: Mapped["User"] = relationship("User")

    def __repr__(self): return f"<PerformanceCycle {self.name} {self.status}>"


class Competency(Base):
    """Competency/skill framework definitions per organization."""
    __tablename__ = "competencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # technical|behavioral|leadership|communication|innovation|custom
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<Competency {self.name} [{self.category}]>"


class KPI(Base):
    """Key Performance Indicator template per organization."""
    __tablename__ = "kpis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # %, count, revenue, score
    kpi_type: Mapped[str] = mapped_column(String(50), nullable=False, default="individual")  # individual|department|organization
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    department: Mapped[Optional["Department"]] = relationship("Department")

    def __repr__(self): return f"<KPI {self.name}>"


class KPIAssignment(Base):
    """KPI assigned to a user for a specific performance cycle with target & weight."""
    __tablename__ = "kpi_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("performance_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    target_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    actual_value: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=1.0)  # weight in weighted avg
    score: Mapped[Optional[float]] = mapped_column(Numeric(4, 2), nullable=True)  # 1-5 computed
    assigned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    kpi: Mapped["KPI"] = relationship("KPI")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    cycle: Mapped["PerformanceCycle"] = relationship("PerformanceCycle")
    assigned_by: Mapped["User"] = relationship("User", foreign_keys=[assigned_by_user_id])
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<KPIAssignment user={self.user_id} kpi={self.kpi_id} score={self.score}>"


class Goal(Base):
    """Individual / Team / Org goal (OKR, SMART, Cascading, Stretch)."""
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("performance_cycles.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_goal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("goals.id", ondelete="SET NULL"), nullable=True)  # cascading
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    goal_type: Mapped[str] = mapped_column(String(50), nullable=False, default="individual")  # individual|team|organization
    goal_framework: Mapped[str] = mapped_column(String(50), nullable=False, default="smart")  # okr|smart|personal|stretch
    target_value: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    current_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active", server_default=text("'active'"))  # active|completed|abandoned|on_hold
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")  # low|medium|high|critical
    completion_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User")
    cycle: Mapped[Optional["PerformanceCycle"]] = relationship("PerformanceCycle")
    organization: Mapped["Organization"] = relationship("Organization")
    progress_logs: Mapped[List["GoalProgress"]] = relationship("GoalProgress", back_populates="goal")

    def __repr__(self): return f"<Goal {self.title[:40]} {self.completion_pct}%>"


class GoalProgress(Base):
    """Time-series progress check-ins for a goal."""
    __tablename__ = "goal_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    completion_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    goal: Mapped["Goal"] = relationship("Goal", back_populates="progress_logs")
    user: Mapped["User"] = relationship("User")

    def __repr__(self): return f"<GoalProgress goal={self.goal_id} pct={self.completion_pct}>"


class PerformanceReview(Base):
    """Review instance — self, manager, skip-level, HR, or 360."""
    __tablename__ = "performance_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("performance_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewee_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_type: Mapped[str] = mapped_column(String(50), nullable=False)  # self|manager|skip_level|hr|peer|360
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", server_default=text("'pending'"))  # pending|in_progress|submitted|acknowledged
    overall_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 2), nullable=True)  # 1.0-5.0
    strengths: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    areas_for_improvement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    cycle: Mapped["PerformanceCycle"] = relationship("PerformanceCycle")
    reviewee: Mapped["User"] = relationship("User", foreign_keys=[reviewee_user_id])
    reviewer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewer_user_id])
    competency_ratings: Mapped[List["CompetencyRating"]] = relationship("CompetencyRating", back_populates="review")

    def __repr__(self): return f"<PerformanceReview reviewee={self.reviewee_user_id} type={self.review_type} status={self.status}>"


class CompetencyRating(Base):
    """Per-review competency score (1-5 scale)."""
    __tablename__ = "competency_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("performance_reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    competency_id: Mapped[int] = mapped_column(ForeignKey("competencies.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[float] = mapped_column(Numeric(3, 1), nullable=False)  # 1.0-5.0
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    review: Mapped["PerformanceReview"] = relationship("PerformanceReview", back_populates="competency_ratings")
    competency: Mapped["Competency"] = relationship("Competency")

    def __repr__(self): return f"<CompetencyRating review={self.review_id} competency={self.competency_id} rating={self.rating}>"


class Feedback(Base):
    """Peer / 360° / anonymous / manager / self feedback."""
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("performance_cycles.id", ondelete="SET NULL"), nullable=True)
    receiver_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    giver_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)  # NULL = anonymous
    feedback_type: Mapped[str] = mapped_column(String(50), nullable=False)  # peer|manager|self|360|anonymous|scheduled
    is_anonymous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[Optional[float]] = mapped_column(Numeric(3, 1), nullable=True)  # optional 1-5
    is_visible_to_receiver: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    receiver: Mapped["User"] = relationship("User", foreign_keys=[receiver_user_id])
    giver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[giver_user_id])

    def __repr__(self): return f"<Feedback type={self.feedback_type} receiver={self.receiver_user_id}>"


class PerformanceRating(Base):
    """Final aggregated performance rating per user per cycle."""
    __tablename__ = "performance_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("performance_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kpi_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 2), nullable=True)  # weighted KPI avg
    goal_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 2), nullable=True)  # goal completion score
    competency_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 2), nullable=True)
    final_rating: Mapped[Optional[float]] = mapped_column(Numeric(4, 2), nullable=True)  # 1.0-5.0
    rating_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Exceptional|Exceeds|Meets|Below|Unsatisfactory
    is_calibrated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    calibrated_rating: Mapped[Optional[float]] = mapped_column(Numeric(4, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    cycle: Mapped["PerformanceCycle"] = relationship("PerformanceCycle")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        UniqueConstraint("cycle_id", "user_id", name="uq_perf_rating_cycle_user"),
    )

    def __repr__(self): return f"<PerformanceRating user={self.user_id} cycle={self.cycle_id} final={self.final_rating}>"


class CalibrationSession(Base):
    """HR-level cross-team rating normalization session."""
    __tablename__ = "calibration_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("performance_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    facilitator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open", server_default=text("'open'"))  # open|completed
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    calibration_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # {user_id: calibrated_rating}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    cycle: Mapped["PerformanceCycle"] = relationship("PerformanceCycle")
    facilitator: Mapped["User"] = relationship("User")

    def __repr__(self): return f"<CalibrationSession cycle={self.cycle_id} status={self.status}>"


class PerformanceImprovementPlan(Base):
    """Performance Improvement Plan (PIP) lifecycle."""
    __tablename__ = "pips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    manager_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    objectives: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    milestones: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # [{title, due_date, status}]
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active", server_default=text("'active'"))  # active|completed|extended|terminated
    outcome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # successful|unsuccessful|extended
    closure_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    manager: Mapped["User"] = relationship("User", foreign_keys=[manager_user_id])
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<PIP user={self.user_id} status={self.status}>"


class PromotionRecommendation(Base):
    """Manager → HR → Approval promotion pipeline."""
    __tablename__ = "promotion_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("performance_cycles.id", ondelete="SET NULL"), nullable=True)
    recommended_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    proposed_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    proposed_salary_increase_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    readiness_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 2), nullable=True)  # 1-5
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", server_default=text("'pending'"))  # pending|approved|rejected|deferred
    decision_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    recommended_by: Mapped["User"] = relationship("User", foreign_keys=[recommended_by_user_id])
    decided_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[decided_by_user_id])
    cycle: Mapped[Optional["PerformanceCycle"]] = relationship("PerformanceCycle")
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<PromotionRecommendation user={self.user_id} status={self.status}>"


# ============================================================================
# SPRINT 4 — ENTITY 2: LEARNING & DEVELOPMENT (L&D) / TRAINING MANAGEMENT SYSTEM
# ============================================================================

class CourseCategory(Base):
    __tablename__ = "course_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<CourseCategory {self.name}>"


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("course_categories.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    instructor_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    course_type: Mapped[str] = mapped_column(String(30), nullable=False, default="online")  # online | classroom | workshop | hybrid
    duration_hours: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    pass_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=70.0)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    category: Mapped[Optional["CourseCategory"]] = relationship("CourseCategory")
    modules: Mapped[List["CourseModule"]] = relationship("CourseModule", back_populates="course", cascade="all, delete-orphan")

    def __repr__(self): return f"<Course {self.title}>"


class CourseModule(Base):
    __tablename__ = "course_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False, default="document")  # video | document | quiz | interactive
    content_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    course: Mapped["Course"] = relationship("Course", back_populates="modules")

    def __repr__(self): return f"<CourseModule {self.title}>"


class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="enrolled")  # enrolled | in_progress | completed | failed | expired
    progress_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    course: Mapped["Course"] = relationship("Course")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    assigned_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_by_user_id])

    def __repr__(self): return f"<CourseEnrollment user={self.user_id} course={self.course_id} status={self.status}>"


class ModuleProgress(Base):
    __tablename__ = "module_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("course_enrollments.id", ondelete="CASCADE"), nullable=False, index=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("course_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_started")  # not_started | in_progress | completed
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    enrollment: Mapped["CourseEnrollment"] = relationship("CourseEnrollment")
    module: Mapped["CourseModule"] = relationship("CourseModule")
    user: Mapped["User"] = relationship("User")

    def __repr__(self): return f"<ModuleProgress module={self.module_id} status={self.status}>"


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[Optional[int]] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    trainer_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    location_or_link: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_participants: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    current_participants: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="scheduled")  # scheduled | ongoing | completed | cancelled

    course: Mapped[Optional["Course"]] = relationship("Course")
    trainer: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self): return f"<TrainingSession {self.title}>"


class SessionAttendance(Base):
    __tablename__ = "session_attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="registered")  # registered | attended | absent | excused
    check_in_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["TrainingSession"] = relationship("TrainingSession")
    user: Mapped["User"] = relationship("User")

    def __repr__(self): return f"<SessionAttendance session={self.session_id} user={self.user_id}>"


class AssessmentQuiz(Base):
    __tablename__ = "assessment_quizzes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    pass_score: Mapped[float] = mapped_column(Float, nullable=False, default=70.0)
    time_limit_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    course: Mapped["Course"] = relationship("Course")
    questions: Mapped[List["AssessmentQuestion"]] = relationship("AssessmentQuestion", back_populates="quiz", cascade="all, delete-orphan")

    def __repr__(self): return f"<AssessmentQuiz {self.title}>"


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("assessment_quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(30), nullable=False, default="single_choice")  # single_choice | multiple_choice | true_false
    options: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    points: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    quiz: Mapped["AssessmentQuiz"] = relationship("AssessmentQuiz", back_populates="questions")

    def __repr__(self): return f"<AssessmentQuestion quiz={self.quiz_id}>"


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("assessment_quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    enrollment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("course_enrollments.id", ondelete="SET NULL"), nullable=True)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_score: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    response_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    quiz: Mapped["AssessmentQuiz"] = relationship("AssessmentQuiz")
    user: Mapped["User"] = relationship("User")
    enrollment: Mapped[Optional["CourseEnrollment"]] = relationship("CourseEnrollment")

    def __repr__(self): return f"<AssessmentAttempt quiz={self.quiz_id} user={self.user_id} passed={self.passed}>"


class SkillMaster(Base):
    __tablename__ = "skill_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="technical")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<SkillMaster {self.name}>"


class EmployeeSkill(Base):
    __tablename__ = "employee_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skill_master.id", ondelete="CASCADE"), nullable=False, index=True)
    proficiency_level: Mapped[str] = mapped_column(String(30), nullable=False, default="intermediate")  # beginner | intermediate | advanced | expert
    verified_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="course_completion")

    skill: Mapped["SkillMaster"] = relationship("SkillMaster")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    verified_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[verified_by_user_id])

    def __repr__(self): return f"<EmployeeSkill user={self.user_id} skill={self.skill_id} level={self.proficiency_level}>"


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("course_enrollments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    certificate_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    issue_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    certificate_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    enrollment: Mapped["CourseEnrollment"] = relationship("CourseEnrollment")
    user: Mapped["User"] = relationship("User")
    course: Mapped["Course"] = relationship("Course")

    def __repr__(self): return f"<Certificate {self.certificate_number}>"


class TrainingBudget(Base):
    __tablename__ = "training_budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2025)
    allocated_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    spent_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    remaining_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    department: Mapped[Optional["Department"]] = relationship("Department")

    def __repr__(self): return f"<TrainingBudget year={self.fiscal_year} remaining={self.remaining_amount}>"


# ============================================================================
# SPRINT 4 — ENTITY 3: EMPLOYEE SUCCESSION PLANNING & CAREER PATHING ENGINE
# ============================================================================

class KeyPosition(Base):
    __tablename__ = "key_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    criticality_level: Mapped[str] = mapped_column(String(30), nullable=False, default="critical")  # critical | high | medium
    current_incumbent_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    vacancy_risk_level: Mapped[str] = mapped_column(String(30), nullable=False, default="low")  # low | medium | high
    impact_rating: Mapped[float] = mapped_column(Float, nullable=False, default=4.0)  # 1.0 - 5.0
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    department: Mapped[Optional["Department"]] = relationship("Department")
    incumbent: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self): return f"<KeyPosition {self.title} criticality={self.criticality_level}>"


class SuccessionPlan(Base):
    __tablename__ = "succession_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    key_position_id: Mapped[int] = mapped_column(ForeignKey("key_positions.id", ondelete="CASCADE"), nullable=False, index=True)
    target_fill_timeline_months: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    strategy_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")  # active | draft | archived
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    key_position: Mapped["KeyPosition"] = relationship("KeyPosition")
    candidates: Mapped[List["SuccessorCandidate"]] = relationship("SuccessorCandidate", back_populates="plan", cascade="all, delete-orphan")

    def __repr__(self): return f"<SuccessionPlan key_position={self.key_position_id}>"


class SuccessorCandidate(Base):
    __tablename__ = "successor_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    succession_plan_id: Mapped[int] = mapped_column(ForeignKey("succession_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    readiness_rating: Mapped[str] = mapped_column(String(30), nullable=False, default="ready_1_year")  # ready_now | ready_1_year | ready_2_years | ready_3_plus_years
    emergency_backup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    nomination_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="nominated")  # nominated | approved | rejected

    plan: Mapped["SuccessionPlan"] = relationship("SuccessionPlan", back_populates="candidates")
    candidate_user: Mapped["User"] = relationship("User")

    def __repr__(self): return f"<SuccessorCandidate user={self.candidate_user_id} readiness={self.readiness_rating}>"


class NineBoxGrid(Base):
    __tablename__ = "nine_box_grids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("performance_cycles.id", ondelete="SET NULL"), nullable=True)
    performance_rating: Mapped[int] = mapped_column(Integer, nullable=False, default=2)  # 1=Low, 2=Medium, 3=High
    potential_rating: Mapped[int] = mapped_column(Integer, nullable=False, default=2)    # 1=Low, 2=Medium, 3=High
    box_category: Mapped[str] = mapped_column(String(50), nullable=False, default="Core Player")  # Star | High Potential | High Professional | Core Player | Risk etc
    evaluated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    evaluated_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[evaluated_by_user_id])
    cycle: Mapped[Optional["PerformanceCycle"]] = relationship("PerformanceCycle")

    def __repr__(self): return f"<NineBoxGrid user={self.user_id} cat='{self.box_category}'>"


class CareerPath(Base):
    __tablename__ = "career_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_levels: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    organization: Mapped["Organization"] = relationship("Organization")
    department: Mapped[Optional["Department"]] = relationship("Department")
    levels: Mapped[List["CareerLevel"]] = relationship("CareerLevel", back_populates="career_path", cascade="all, delete-orphan")

    def __repr__(self): return f"<CareerPath {self.title}>"


class CareerLevel(Base):
    __tablename__ = "career_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    career_path_id: Mapped[int] = mapped_column(ForeignKey("career_paths.id", ondelete="CASCADE"), nullable=False, index=True)
    level_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    level_title: Mapped[str] = mapped_column(String(150), nullable=False)
    min_experience_years: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    required_skills: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # [{skill_id, proficiency}]
    target_salary_min: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    target_salary_max: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    career_path: Mapped["CareerPath"] = relationship("CareerPath", back_populates="levels")

    def __repr__(self): return f"<CareerLevel {self.level_title} L{self.level_number}>"


class IndividualDevelopmentPlan(Base):
    __tablename__ = "individual_development_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_career_level_id: Mapped[Optional[int]] = mapped_column(ForeignKey("career_levels.id", ondelete="SET NULL"), nullable=True)
    target_position_title: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="in_progress")  # draft | in_progress | completed | cancelled
    target_completion_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User")
    target_career_level: Mapped[Optional["CareerLevel"]] = relationship("CareerLevel")
    goals: Mapped[List["IDPGoal"]] = relationship("IDPGoal", back_populates="idp", cascade="all, delete-orphan")

    def __repr__(self): return f"<IndividualDevelopmentPlan user={self.user_id} status={self.status}>"


class IDPGoal(Base):
    __tablename__ = "idp_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    idp_id: Mapped[int] = mapped_column(ForeignKey("individual_development_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    goal_type: Mapped[str] = mapped_column(String(40), nullable=False, default="skill_acquisition")  # skill_acquisition | training | mentorship | project_assignment
    target_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")  # pending | in_progress | completed
    completion_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    idp: Mapped["IndividualDevelopmentPlan"] = relationship("IndividualDevelopmentPlan", back_populates="goals")

    def __repr__(self): return f"<IDPGoal {self.title} pct={self.completion_pct}>"


class FlightRiskAssessment(Base):
    __tablename__ = "flight_risk_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    risk_score: Mapped[str] = mapped_column(String(30), nullable=False, default="low")  # low | medium | high | critical
    risk_factors: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # ["market_compensation", "limited_growth", "commute"]
    retention_strategy: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assessed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    assessed_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assessed_by_user_id])

    def __repr__(self): return f"<FlightRiskAssessment user={self.user_id} risk={self.risk_score}>"


class MentorshipPair(Base):
    __tablename__ = "mentorship_pairs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    mentor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mentee_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")  # active | completed | paused
    focus_areas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    mentor: Mapped["User"] = relationship("User", foreign_keys=[mentor_user_id])
    mentee: Mapped["User"] = relationship("User", foreign_keys=[mentee_user_id])

    def __repr__(self): return f"<MentorshipPair mentor={self.mentor_user_id} mentee={self.mentee_user_id}>"


# ============================================================================
# SPRINT 4 — ENTITY 4: EMPLOYEE COMPENSATION & BENEFITS MANAGEMENT SYSTEM
# ============================================================================

class CompensationGrade(Base):
    __tablename__ = "compensation_grades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    grade_code: Mapped[str] = mapped_column(String(20), nullable=False)        # IC1, IC2 … IC7, M1 … M5
    grade_name: Mapped[str] = mapped_column(String(100), nullable=False)       # Junior Engineer, Software Engineer …
    salary_min: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    salary_mid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    salary_max: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization: Mapped["Organization"] = relationship("Organization")
    bands: Mapped[List["CompensationBand"]] = relationship("CompensationBand", back_populates="grade", cascade="all, delete-orphan")

    def __repr__(self): return f"<CompensationGrade {self.grade_code} {self.salary_min}–{self.salary_max}>"


class CompensationBand(Base):
    __tablename__ = "compensation_bands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("compensation_grades.id", ondelete="CASCADE"), nullable=False, index=True)
    band_label: Mapped[str] = mapped_column(String(50), nullable=False)        # Low, Mid, High / P1, P2, P3
    band_min: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    band_max: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    target_pct_of_midpoint: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)

    grade: Mapped["CompensationGrade"] = relationship("CompensationGrade", back_populates="bands")

    def __repr__(self): return f"<CompensationBand {self.band_label} {self.band_min}–{self.band_max}>"


class SalaryRevision(Base):
    __tablename__ = "salary_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    revision_type: Mapped[str] = mapped_column(String(40), nullable=False, default="merit")  # merit | promotion | adjustment | off_cycle
    previous_salary: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    proposed_salary: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    increase_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="proposed")  # proposed | approved | rejected | implemented
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    performance_review_id: Mapped[Optional[int]] = mapped_column(ForeignKey("performance_reviews.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    approved_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by_user_id])

    def __repr__(self): return f"<SalaryRevision user={self.user_id} type={self.revision_type} pct={self.increase_pct}%>"


class BenefitsPlan(Base):
    __tablename__ = "benefits_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_name: Mapped[str] = mapped_column(String(100), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(40), nullable=False, default="health")  # health | dental | vision | pf | nps | esop | life | other
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    employer_contribution_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    employee_contribution_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_coverage_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<BenefitsPlan {self.plan_name} type={self.plan_type}>"


class BenefitsEnrollment(Base):
    __tablename__ = "benefits_enrollments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("benefits_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    coverage_tier: Mapped[str] = mapped_column(String(30), nullable=False, default="individual")  # individual | individual+spouse | family
    elected_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")  # active | waived | terminated

    user: Mapped["User"] = relationship("User")
    plan: Mapped["BenefitsPlan"] = relationship("BenefitsPlan")

    def __repr__(self): return f"<BenefitsEnrollment user={self.user_id} plan={self.plan_id} tier={self.coverage_tier}>"


class EquityGrant(Base):
    __tablename__ = "equity_grants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    grant_type: Mapped[str] = mapped_column(String(30), nullable=False, default="rsu")  # rsu | eso | phantom
    total_shares: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vested_shares: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    strike_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    grant_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    cliff_months: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    vesting_months: Mapped[int] = mapped_column(Integer, nullable=False, default=48)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")  # active | fully_vested | forfeited | exercised

    user: Mapped["User"] = relationship("User")
    vesting_events: Mapped[List["EquityVestingEvent"]] = relationship("EquityVestingEvent", back_populates="grant", cascade="all, delete-orphan")

    def __repr__(self): return f"<EquityGrant user={self.user_id} type={self.grant_type} shares={self.total_shares}>"


class EquityVestingEvent(Base):
    __tablename__ = "equity_vesting_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    grant_id: Mapped[int] = mapped_column(ForeignKey("equity_grants.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    shares_vesting: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    grant: Mapped["EquityGrant"] = relationship("EquityGrant", back_populates="vesting_events")

    def __repr__(self): return f"<EquityVestingEvent grant={self.grant_id} shares={self.shares_vesting} vested={self.vested}>"


class TotalRewardsStatement(Base):
    __tablename__ = "total_rewards_statements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2025)
    base_salary: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_benefits_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    equity_fmv: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bonus_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_comp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    compa_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    grade_id: Mapped[Optional[int]] = mapped_column(ForeignKey("compensation_grades.id", ondelete="SET NULL"), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User")
    grade: Mapped[Optional["CompensationGrade"]] = relationship("CompensationGrade")

    def __repr__(self): return f"<TotalRewardsStatement user={self.user_id} total={self.total_comp}>"


class CompensationReview(Base):
    __tablename__ = "compensation_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    review_name: Mapped[str] = mapped_column(String(150), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2025)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")  # open | in_review | approved | closed
    total_budget: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    used_budget: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<CompensationReview {self.review_name} FY{self.fiscal_year}>"


# ============================================================================
# SPRINT 4 — ENTITY 5: ENTERPRISE POLICY CENTER & COMPLIANCE MANAGEMENT SYSTEM
# ============================================================================

class PolicyCategory(Base):
    """Policy category/folder taxonomy for organizing policy documents."""
    __tablename__ = "policy_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("policy_categories.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    parent: Mapped[Optional["PolicyCategory"]] = relationship("PolicyCategory", remote_side=[id])
    policies: Mapped[List["PolicyDocument"]] = relationship("PolicyDocument", back_populates="category")

    def __repr__(self): return f"<PolicyCategory {self.name}>"


class PolicyTag(Base):
    """Tag for labeling and filtering policy documents."""
    __tablename__ = "policy_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<PolicyTag {self.name}>"


class PolicyDocument(Base):
    """Master policy document record — core entity of the Policy Center."""
    __tablename__ = "policy_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("policy_categories.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    document_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    owner_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approver_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", server_default=text("'draft'"))
    # draft -> review -> pending_approval -> approved -> published -> effective -> expired -> archived -> superseded
    policy_type: Mapped[str] = mapped_column(String(50), nullable=False, default="hr_policy")
    # hr_policy|it_policy|security_policy|attendance_policy|leave_policy|payroll_policy|
    # recruitment_policy|performance_policy|workplace_conduct|travel_policy|expense_policy|
    # asset_policy|privacy_policy|legal_policy|compliance_document|custom
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    requires_acknowledgement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    requires_signature: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    workflow_request_id: Mapped[Optional[int]] = mapped_column(ForeignKey("approval_requests.id", ondelete="SET NULL"), nullable=True)
    tags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, server_default=text("'[]'::jsonb"))
    meta_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    category: Mapped[Optional["PolicyCategory"]] = relationship("PolicyCategory", back_populates="policies")
    owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[owner_user_id])
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approver_user_id])
    created_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_user_id])
    versions: Mapped[List["PolicyVersion"]] = relationship("PolicyVersion", back_populates="document", cascade="all, delete-orphan")
    attachments: Mapped[List["PolicyAttachment"]] = relationship("PolicyAttachment", back_populates="document", cascade="all, delete-orphan")
    distributions: Mapped[List["PolicyDistribution"]] = relationship("PolicyDistribution", back_populates="document", cascade="all, delete-orphan")
    acknowledgements: Mapped[List["PolicyAcknowledgement"]] = relationship("PolicyAcknowledgement", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_policy_docs_org_status", "organization_id", "status"),
        Index("ix_policy_docs_effective", "effective_date"),
        Index("ix_policy_docs_expiry", "expiry_date"),
    )

    def __repr__(self): return f"<PolicyDocument {self.document_number or self.title[:50]} status={self.status}>"


class PolicyVersion(Base):
    """Versioned snapshot of policy document content."""
    __tablename__ = "policy_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("policy_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    version_type: Mapped[str] = mapped_column(String(20), nullable=False, default="major")  # major|minor|draft
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")  # draft|current|superseded
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    document: Mapped["PolicyDocument"] = relationship("PolicyDocument", back_populates="versions")
    created_by: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_policy_version_doc_ver"),
        Index("ix_policy_versions_doc", "document_id"),
    )

    def __repr__(self): return f"<PolicyVersion doc={self.document_id} v{self.version} ({self.version_type})>"


class PolicyAttachment(Base):
    """File attachment linked to a policy document."""
    __tablename__ = "policy_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("policy_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("policy_versions.id", ondelete="SET NULL"), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False, default="pdf")  # pdf|docx|pptx|xlsx|image|other
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    document: Mapped["PolicyDocument"] = relationship("PolicyDocument", back_populates="attachments")
    uploaded_by: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self): return f"<PolicyAttachment {self.file_name}>"


class PolicyDistribution(Base):
    """Target scope for policy distribution (org-wide, department, role, individual)."""
    __tablename__ = "policy_distributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("policy_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    distribution_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # organization|department|team|role|individual|dynamic_group
    target_org_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    target_dept_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), nullable=True)
    target_role_id: Mapped[Optional[int]] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), nullable=True)
    target_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    document: Mapped["PolicyDocument"] = relationship("PolicyDocument", back_populates="distributions")
    target_org: Mapped[Optional["Organization"]] = relationship("Organization", foreign_keys=[target_org_id])
    target_dept: Mapped[Optional["Department"]] = relationship("Department", foreign_keys=[target_dept_id])
    target_role: Mapped[Optional["Role"]] = relationship("Role", foreign_keys=[target_role_id])
    target_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[target_user_id])

    def __repr__(self): return f"<PolicyDistribution doc={self.document_id} type={self.distribution_type}>"


class PolicyAcknowledgement(Base):
    """Employee acknowledgement record with read confirmation & optional digital signature."""
    __tablename__ = "policy_acknowledgements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("policy_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("policy_versions.id", ondelete="SET NULL"), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    device_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    read_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    signature_id: Mapped[Optional[int]] = mapped_column(ForeignKey("policy_signatures.id", ondelete="SET NULL", use_alter=True, name="fk_policy_acknowledgement_signature"), nullable=True)
    reminder_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    last_reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    document: Mapped["PolicyDocument"] = relationship("PolicyDocument", back_populates="acknowledgements")
    user: Mapped["User"] = relationship("User")
    signature: Mapped[Optional["PolicySignature"]] = relationship("PolicySignature", foreign_keys="PolicyAcknowledgement.signature_id", uselist=False)

    __table_args__ = (
        UniqueConstraint("document_id", "user_id", name="uq_policy_ack_user_doc"),
        Index("ix_policy_ack_pending", "document_id", "is_acknowledged"),
    )

    def __repr__(self): return f"<PolicyAcknowledgement doc={self.document_id} user={self.user_id} ack={self.is_acknowledged}>"


class PolicySignature(Base):
    """Digital signature record with hash verification and audit trail."""
    __tablename__ = "policy_signatures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    acknowledgement_id: Mapped[Optional[int]] = mapped_column(ForeignKey("policy_acknowledgements.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("policy_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    signature_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    signature_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    device_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verification_method: Mapped[str] = mapped_column(String(30), nullable=False, default="click")  # click|otp|biometric|dsc
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User")
    document: Mapped["PolicyDocument"] = relationship("PolicyDocument")
    # acknowledgement back-reference removed — bidirectional FK creates ambiguity.
    # Use PolicyAcknowledgement.signature relationship instead.

    __table_args__ = (
        Index("ix_policy_signatures_doc", "document_id"),
    )

    def __repr__(self): return f"<PolicySignature doc={self.document_id} user={self.user_id}>"


class PolicyTemplate(Base):
    """Reusable policy document template with placeholders."""
    __tablename__ = "policy_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("policy_categories.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    category: Mapped[Optional["PolicyCategory"]] = relationship("PolicyCategory")

    def __repr__(self): return f"<PolicyTemplate {self.name}>"


class PolicyReminder(Base):
    """Reminder configuration for pending policy acknowledgements."""
    __tablename__ = "policy_reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("policy_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    reminder_type: Mapped[str] = mapped_column(String(30), nullable=False, default="automated")  # automated|manual|escalation
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    max_reminders: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    escalation_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    document: Mapped["PolicyDocument"] = relationship("PolicyDocument")
    escalation_user: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self): return f"<PolicyReminder doc={self.document_id} interval={self.interval_days}d>"


class PolicyNotification(Base):
    """Notification log for policy events (created, published, expiring, etc.)."""
    __tablename__ = "policy_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("policy_documents.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    notification_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # new_policy|policy_updated|policy_expiring|ack_reminder|escalation|policy_published
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    document: Mapped[Optional["PolicyDocument"]] = relationship("PolicyDocument")
    user: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        Index("ix_policy_notif_user", "user_id", "is_read"),
    )

    def __repr__(self): return f"<PolicyNotification type={self.notification_type} user={self.user_id}>"


class ComplianceRule(Base):
    """Configurable compliance rules for policy adherence scoring."""
    __tablename__ = "compliance_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # mandatory_read|acknowledgement_required|signed_required|within_days|training_required
    policy_type_filter: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    grace_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    created_by: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self): return f"<ComplianceRule {self.name} type={self.rule_type}>"


class ComplianceRecord(Base):
    """Per-user per-policy compliance tracking record."""
    __tablename__ = "compliance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("policy_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id: Mapped[Optional[int]] = mapped_column(ForeignKey("compliance_rules.id", ondelete="SET NULL"), nullable=True)
    is_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    compliant_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    # pending|compliant|overdue|waived|exempted
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    document: Mapped["PolicyDocument"] = relationship("PolicyDocument")
    user: Mapped["User"] = relationship("User")
    rule: Mapped[Optional["ComplianceRule"]] = relationship("ComplianceRule")

    __table_args__ = (
        Index("ix_compliance_record_user_org", "user_id", "organization_id"),
    )

    def __repr__(self): return f"<ComplianceRecord doc={self.document_id} user={self.user_id} compliant={self.is_compliant}>"


class ComplianceAudit(Base):
    """Audit trail for compliance events and policy enforcement actions."""
    __tablename__ = "compliance_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("policy_documents.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    audit_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # compliance_check|reminder_sent|escalation|exemption_granted|waiver_granted
    description: Mapped[str] = mapped_column(Text, nullable=False)
    meta_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    organization: Mapped["Organization"] = relationship("Organization")
    document: Mapped[Optional["PolicyDocument"]] = relationship("PolicyDocument")
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    created_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_user_id])

    def __repr__(self): return f"<ComplianceAudit type={self.audit_type} doc={self.document_id}>"


# ============================================================================
# SPRINT 4 — ENTITY 3: ASSET & DEVICE MANAGEMENT SYSTEM
# ============================================================================

class AssetCategory(Base):
    """Classification taxonomy for asset types (IT Equipment, Furniture, Vehicle, Software, etc.)."""
    __tablename__ = "asset_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("asset_categories.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    parent: Mapped[Optional["AssetCategory"]] = relationship("AssetCategory", remote_side=[id])

    def __repr__(self): return f"<AssetCategory {self.name}>"


class Asset(Base):
    """Master asset record — core entity tracking all organizational assets."""
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("asset_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    asset_tag: Mapped[str] = mapped_column(String(50), nullable=False, comment="Internal asset tag/barcode")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    serial_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False, default="it_equipment")
    # it_equipment | furniture | vehicle | software | building | office_equipment | consumable | other
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="available", server_default=text("'available'"))
    # available | assigned | under_maintenance | lost | stolen | disposed | retired
    condition: Mapped[str] = mapped_column(String(30), nullable=False, default="new", server_default=text("'new'"))
    # new | excellent | good | fair | poor | damaged
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    room_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    purchase_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    purchase_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    warranty_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    warranty_provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    warranty_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)
    purchase_order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True)
    depreciation_method: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # slm | wdv | none
    useful_life_months: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    salvage_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    qr_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meta_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    category: Mapped[Optional["AssetCategory"]] = relationship("AssetCategory")
    assigned_to: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_to_user_id])
    department: Mapped[Optional["Department"]] = relationship("Department")
    vendor: Mapped[Optional["Vendor"]] = relationship("Vendor", foreign_keys=[vendor_id])
    purchase_order: Mapped[Optional["PurchaseOrder"]] = relationship("PurchaseOrder", foreign_keys=[purchase_order_id])
    assignments: Mapped[List["AssetAssignment"]] = relationship("AssetAssignment", back_populates="asset")
    maintenance_records: Mapped[List["AssetMaintenance"]] = relationship("AssetMaintenance", back_populates="asset")
    depreciation_entries: Mapped[List["AssetDepreciation"]] = relationship("AssetDepreciation", back_populates="asset")
    insurance_policies: Mapped[List["AssetInsurance"]] = relationship("AssetInsurance", back_populates="asset")
    license_records: Mapped[List["AssetLicense"]] = relationship("AssetLicense", back_populates="asset")

    __table_args__ = (
        UniqueConstraint("organization_id", "asset_tag", name="uq_asset_org_tag"),
        Index("ix_assets_status", "status"),
        Index("ix_assets_type", "asset_type"),
    )

    def __repr__(self): return f"<Asset {self.asset_tag} {self.name} status={self.status}>"


class AssetAssignment(Base):
    """Asset-to-employee assignment and return tracking."""
    __tablename__ = "asset_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assignment_type: Mapped[str] = mapped_column(String(30), nullable=False, default="permanent")  # permanent | temporary | loan
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    expected_return_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    returned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    returned_condition: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    return_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", server_default=text("'active'"))  # active | returned | overdue
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    asset: Mapped["Asset"] = relationship("Asset", back_populates="assignments")
    assigned_to: Mapped["User"] = relationship("User", foreign_keys=[assigned_to_user_id])
    assigned_by: Mapped["User"] = relationship("User", foreign_keys=[assigned_by_user_id])
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<AssetAssignment asset={self.asset_id} user={self.assigned_to_user_id} status={self.status}>"


class AssetMaintenance(Base):
    """Maintenance and repair records for assets."""
    __tablename__ = "asset_maintenance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    maintenance_type: Mapped[str] = mapped_column(String(30), nullable=False)  # preventive | corrective | emergency | inspection
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    scheduled_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="scheduled", server_default=text("'scheduled'"))
    # scheduled | in_progress | completed | cancelled | deferred
    performed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_maintenance_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    asset: Mapped["Asset"] = relationship("Asset", back_populates="maintenance_records")
    vendor: Mapped[Optional["Vendor"]] = relationship("Vendor")
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<AssetMaintenance asset={self.asset_id} type={self.maintenance_type} status={self.status}>"


class AssetDepreciation(Base):
    """Depreciation schedule entries for assets (SLM or WDV method)."""
    __tablename__ = "asset_depreciation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opening_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    depreciation_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    closing_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    accumulated_depreciation: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    depreciation_method: Mapped[str] = mapped_column(String(10), nullable=False)  # slm | wdv
    is_posted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    asset: Mapped["Asset"] = relationship("Asset", back_populates="depreciation_entries")
    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        Index("ix_asset_depreciation_period", "asset_id", "period_start", "period_end"),
    )

    def __repr__(self): return f"<AssetDepreciation asset={self.asset_id} period={self.period_start.date()} amount={self.depreciation_amount}>"


class AssetDisposal(Base):
    """Asset disposal, scrap, auction, or write-off records."""
    __tablename__ = "asset_disposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    disposal_type: Mapped[str] = mapped_column(String(30), nullable=False)  # sold | scrapped | donated | auctioned | written_off | lost | stolen
    disposal_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    disposal_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    book_value_at_disposal: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gain_loss: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    asset: Mapped["Asset"] = relationship("Asset")
    approved_by: Mapped[Optional["User"]] = relationship("User")
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<AssetDisposal asset={self.asset_id} type={self.disposal_type}>"


class AssetAudit(Base):
    """Physical verification audit records for asset tracking."""
    __tablename__ = "asset_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    audit_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    audit_type: Mapped[str] = mapped_column(String(30), nullable=False, default="physical")  # physical | spot_check | annual | random
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned")  # planned | in_progress | completed | cancelled
    scheduled_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    conducted_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    total_assets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verified_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    damaged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discrepancies: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    conducted_by: Mapped[Optional["User"]] = relationship("User")
    results: Mapped[List["AssetAuditResult"]] = relationship("AssetAuditResult", back_populates="audit", cascade="all, delete-orphan")

    def __repr__(self): return f"<AssetAudit {self.audit_code} status={self.status}>"


class AssetAuditResult(Base):
    """Individual asset verification result within an audit."""
    __tablename__ = "asset_audit_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    audit_id: Mapped[int] = mapped_column(ForeignKey("asset_audits.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    verified_location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    verified_condition: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    qr_scanned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    discrepancy_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verified_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    audit: Mapped["AssetAudit"] = relationship("AssetAudit", back_populates="results")
    asset: Mapped["Asset"] = relationship("Asset")
    verified_by: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self): return f"<AssetAuditResult audit={self.audit_id} asset={self.asset_id} present={self.is_present}>"


class AssetInsurance(Base):
    """Insurance policies covering organizational assets."""
    __tablename__ = "asset_insurance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_no: Mapped[str] = mapped_column(String(100), nullable=False)
    insurance_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    coverage_type: Mapped[str] = mapped_column(String(30), nullable=False, default="comprehensive")  # comprehensive | third_party | theft | fire
    sum_insured: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    premium_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    premium_frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="annual")  # annual | half_yearly | quarterly | monthly
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expiry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")  # active | expired | cancelled | renewed
    documents_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    asset: Mapped["Asset"] = relationship("Asset", back_populates="insurance_policies")
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<AssetInsurance asset={self.asset_id} policy={self.policy_no}>"


class AssetLicense(Base):
    """Software license tracking (perpetual, subscription, OEM, volume licensing)."""
    __tablename__ = "asset_licenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    license_key: Mapped[str] = mapped_column(String(255), nullable=False)
    license_type: Mapped[str] = mapped_column(String(30), nullable=False, default="perpetual")  # perpetual | subscription | oem | volume | freeware
    total_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    used_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    renewal_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")  # active | expiring | expired | revoked
    is_subscription: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    asset: Mapped["Asset"] = relationship("Asset", back_populates="license_records")
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self): return f"<AssetLicense asset={self.asset_id} type={self.license_type}>"


class Vendor(Base):
    """Vendor/supplier master for asset procurement."""
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_person: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gst_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    payment_terms: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")  # active | inactive | blacklisted
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    purchase_orders: Mapped[List["PurchaseOrder"]] = relationship("PurchaseOrder", back_populates="vendor")

    def __repr__(self): return f"<Vendor {self.vendor_name}>"


class PurchaseOrder(Base):
    """Asset purchase order records."""
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    po_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=False, index=True)
    order_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    expected_delivery_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", server_default=text("'draft'"))
    # draft | ordered | partially_received | received | cancelled | closed
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tax_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    grand_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="purchase_orders")
    approved_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by_user_id])
    created_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_user_id])
    items: Mapped[List["PurchaseOrderItem"]] = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")

    def __repr__(self): return f"<PurchaseOrder {self.po_number} status={self.status}>"


class PurchaseOrderItem(Base):
    """Line items within a purchase order."""
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("asset_categories.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    purchase_order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder", back_populates="items")
    category: Mapped[Optional["AssetCategory"]] = relationship("AssetCategory")

    def __repr__(self): return f"<PurchaseOrderItem po={self.purchase_order_id} item={self.item_name}>"


class AssetConsumable(Base):
    """Consumable inventory tracking (toner, cartridges, stationery, etc.)."""
    __tablename__ = "asset_consumables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    consumable_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # stationery | toner | cartridge | cleaning | lab | kitchen | safety | other
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit_of_measure: Mapped[str] = mapped_column(String(30), nullable=False, default="pieces")  # pieces | liters | packs | boxes | rolls
    quantity_in_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minimum_stock_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

















class ConsumableIssuance(Base):
    """Consumable issuance/release tracking to employees."""
    __tablename__ = "consumable_issuances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    consumable_id: Mapped[int] = mapped_column(ForeignKey("asset_consumables.id", ondelete="CASCADE"), nullable=False, index=True)
    issued_to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    issued_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    consumable: Mapped["AssetConsumable"] = relationship("AssetConsumable")
    issued_to: Mapped["User"] = relationship("User", foreign_keys=[issued_to_user_id])
    issued_by: Mapped["User"] = relationship("User", foreign_keys=[issued_by_user_id])

    def __repr__(self): return f"<ConsumableIssuance consumable={self.consumable_id} qty={self.quantity}>"


# ── Organization & Identity Domain Extensions ────────────────────────────────

class LegalEntity(Base):
    """Legal corporate entity under an Organization (tax entity, registered entity)."""
    __tablename__ = "legal_entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("uuid_generate_v4()"))
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False, index=True)
    legal_name: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    registration_number: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, unique=True)
    tax_id: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    country: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, default="India", server_default=text("'India'"))
    state: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(NVARCHAR(10), nullable=False, default="INR", server_default=text("'INR'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        Index("ix_legal_entities_org", "org_id", postgresql_where=text("is_deleted = 0")),
    )


class BusinessUnit(Base):
    """Strategic division or business unit within an Organization."""
    __tablename__ = "business_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    legal_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_entities.id", ondelete="SET NULL"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(150), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    head_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    legal_entity: Mapped[Optional["LegalEntity"]] = relationship("LegalEntity")
    head: Mapped[Optional["User"]] = relationship("User", foreign_keys=[head_user_id])


class Branch(Base):
    """Physical location/branch/office of an organization."""
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(150), nullable=False, index=True)
    branch_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, default="HQ", server_default=text("'HQ'"))
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    country: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, default="India", server_default=text("'India'"))
    timezone: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, default="Asia/Kolkata", server_default=text("'Asia/Kolkata'"))
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    geofence_radius_meters: Mapped[int] = mapped_column(Integer, nullable=False, default=200, server_default=text("200"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")


class Team(Base):
    """Sub-unit team within a department."""
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    dept_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(150), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lead_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    department: Mapped["Department"] = relationship("Department")
    lead: Mapped[Optional["User"]] = relationship("User", foreign_keys=[lead_user_id])


class CostCenter(Base):
    """Financial cost center for budget allocation."""
    __tablename__ = "cost_centers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manager_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    annual_budget: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0, server_default=text("0.0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    manager: Mapped[Optional["User"]] = relationship("User", foreign_keys=[manager_user_id])


class JobPosition(Base):
    """Enterprise position model and position hierarchy."""
    __tablename__ = "job_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(NVARCHAR(150), nullable=False, index=True)
    dept_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    reporting_position_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("job_positions.id", ondelete="SET NULL"), nullable=True, index=True)
    grade: Mapped[Optional[str]] = mapped_column(NVARCHAR(50), nullable=True)
    band: Mapped[Optional[str]] = mapped_column(NVARCHAR(50), nullable=True)
    min_salary: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    max_salary: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    headcount_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    department: Mapped[Optional["Department"]] = relationship("Department")
    reporting_position: Mapped[Optional["JobPosition"]] = relationship("JobPosition", remote_side=[id])


class EmploymentRecord(Base):
    """Detailed employment record, status, and reporting structure."""
    __tablename__ = "employment_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    position_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("job_positions.id", ondelete="SET NULL"), nullable=True, index=True)
    business_unit_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True)
    branch_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    cost_center_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("cost_centers.id", ondelete="SET NULL"), nullable=True)

    employment_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, default="EMPLOYEE", server_default=text("'EMPLOYEE'"))
    status: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, default="ACTIVE", server_default=text("'ACTIVE'"))

    joining_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    confirmation_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    reporting_manager_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    skip_level_manager_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    functional_manager_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    designation: Mapped[Optional[str]] = mapped_column(NVARCHAR(150), nullable=True)
    work_email: Mapped[Optional[str]] = mapped_column(NVARCHAR(150), nullable=True)
    notice_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default=text("30"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    position: Mapped[Optional["JobPosition"]] = relationship("JobPosition")
    reporting_manager: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reporting_manager_id])
    skip_level_manager: Mapped[Optional["User"]] = relationship("User", foreign_keys=[skip_level_manager_id])
    functional_manager: Mapped[Optional["User"]] = relationship("User", foreign_keys=[functional_manager_id])


class IdentityHistory(Base):
    """Audit timeline of identity lifecycle events."""
    __tablename__ = "identity_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, index=True)
    previous_state: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_state: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    performed_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    performed_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[performed_by_id])


class OrganizationProvisioning(Base):
    """Stateful organization provisioning workflow record."""
    __tablename__ = "organization_provisionings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("uuid_generate_v4()"))
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    state: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, default="PENDING", server_default=text("'PENDING'"))
    steps_completed: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    error_log: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    initiated_by_email: Mapped[Optional[str]] = mapped_column(NVARCHAR(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")


# =============================================================================
#  SPRINT 4 — WORKFORCE CORE DOMAIN
#  Canonical Workforce models covering Attendance, Shifts & Rosters,
#  Time Tracking & Breaks, Holidays, and Workforce Planning.
#  APPENDED SECTION — zero modifications to any existing model above.
# =============================================================================
from sqlalchemy import Date  # noqa: E402  (Date column type appended here)


# ── 1.1 ATTENDANCE DOMAIN EXTENSIONS ──────────────────────────────────────────

class AttendanceDevice(Base):
    """Device registry for all attendance capture channels."""
    __tablename__ = "attendance_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    device_name: Mapped[str] = mapped_column(NVARCHAR(150), nullable=False)
    device_type: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False,
                                              server_default=text("'FACE'"),
                                              comment="FACE|QR|GPS|BLE|NFC|WiFi|KIOSK|MANUAL")
    serial_number: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(NVARCHAR(255), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(NVARCHAR(45), nullable=True)
    is_trusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                             server_default=text("TRUE"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                            server_default=text("TRUE"))
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        UniqueConstraint("org_id", "serial_number", name="uq_attendance_device_org_serial"),
        CheckConstraint(
            "device_type IN ('FACE','QR','GPS','BLE','NFC','WiFi','KIOSK','MANUAL')",
            name="ck_attendance_device_type"),
        Index("ix_attendance_devices_org_active", "org_id", "is_active"),
    )
    def __repr__(self): return f"<AttendanceDevice {self.id} {self.device_type!r} {self.device_name!r}>"


class GeofenceZone(Base):
    """Named geographic zones with lat/lng center + radius for GPS attendance."""
    __tablename__ = "geofence_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(150), nullable=False)
    code: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    radius_meters: Mapped[int] = mapped_column(Integer, nullable=False, default=200,
                                                server_default=text("200"))
    address: Mapped[Optional[str]] = mapped_column(NVARCHAR(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                            server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        UniqueConstraint("org_id", "code", name="uq_geofence_zone_org_code"),
        CheckConstraint("radius_meters > 0", name="ck_geofence_radius_positive"),
    )
    def __repr__(self): return f"<GeofenceZone {self.id} {self.code!r}>"


class AttendancePolicy(Base):
    """Org-level attendance rules: grace period, late threshold, overtime triggers, geofence."""
    __tablename__ = "attendance_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(150), nullable=False)
    grace_period_mins: Mapped[int] = mapped_column(Integer, nullable=False, default=5,
                                                    server_default=text("5"))
    late_threshold_mins: Mapped[int] = mapped_column(Integer, nullable=False, default=15,
                                                      server_default=text("15"))
    early_departure_threshold_mins: Mapped[int] = mapped_column(Integer, nullable=False, default=15,
                                                                 server_default=text("15"))
    half_day_hours: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False, default=4.0,
                                                   server_default=text("4.0"))
    overtime_trigger_mins: Mapped[int] = mapped_column(Integer, nullable=False, default=60,
                                                        server_default=text("60"))
    overtime_rate_multiplier: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False, default=1.50,
                                                            server_default=text("1.50"))
    geofence_radius_meters: Mapped[int] = mapped_column(Integer, nullable=False, default=200,
                                                         server_default=text("200"))
    allow_gps: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                            server_default=text("TRUE"))
    allow_face: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                             server_default=text("TRUE"))
    allow_qr: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                           server_default=text("TRUE"))
    allow_ble: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                            server_default=text("FALSE"))
    allow_nfc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                            server_default=text("FALSE"))
    allow_wifi: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                             server_default=text("TRUE"))
    allow_kiosk: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                              server_default=text("TRUE"))
    allow_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                               server_default=text("TRUE"))
    ip_whitelist: Mapped[dict] = mapped_column(JSONB, nullable=False,
                                                server_default=text("'[]'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                            server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_attendance_policy_org_name"),
        CheckConstraint("grace_period_mins >= 0", name="ck_attendance_policy_grace"),
        CheckConstraint("late_threshold_mins >= 0", name="ck_attendance_policy_late"),
        CheckConstraint("geofence_radius_meters > 0", name="ck_attendance_policy_radius"),
    )
    def __repr__(self): return f"<AttendancePolicy {self.id} {self.name!r}>"


class AttendanceSession(Base):
    """Per-day attendance session with check-in/out, status, channel, device ref."""
    __tablename__ = "attendance_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"),
                                          nullable=False, index=True)
    attendance_log_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("attendance_logs.id", ondelete="SET NULL"), nullable=True, index=True)
    work_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    check_in: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False,
                                         server_default=text("'PRESENT'"),
                                         comment="PRESENT|LATE|ABSENT|HALF_DAY|HOLIDAY|WEEKEND|WFH|BUSINESS_TRAVEL|ON_LEAVE|MISSED_PUNCH")
    channel: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False,
                                          server_default=text("'FACE'"),
                                          comment="FACE|QR|GPS|BLE|NFC|WiFi|KIOSK|MANUAL")
    device_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("attendance_devices.id", ondelete="SET NULL"), nullable=True, index=True)
    device_ref: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    work_hours: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    overtime_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                   server_default=text("0"))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    attendance_log: Mapped[Optional["AttendanceLog"]] = relationship(
        "AttendanceLog", foreign_keys=[attendance_log_id])
    device: Mapped[Optional["AttendanceDevice"]] = relationship(
        "AttendanceDevice", foreign_keys=[device_id])
    events: Mapped[List["AttendanceEvent"]] = relationship(
        "AttendanceEvent", back_populates="session", cascade="all, delete-orphan",
        foreign_keys="AttendanceEvent.session_id")

    __table_args__ = (
        UniqueConstraint("user_id", "work_date", name="uq_attendance_session_user_date"),
        CheckConstraint(
            "status IN ('PRESENT','LATE','ABSENT','HALF_DAY','HOLIDAY','WEEKEND','WFH',"
            "'BUSINESS_TRAVEL','ON_LEAVE','MISSED_PUNCH')", name="ck_attendance_session_status"),
        Index("ix_attendance_sessions_org_date", "org_id", "work_date"),
    )
    def __repr__(self): return f"<AttendanceSession {self.id} user={self.user_id} {self.status!r}>"


class AttendanceEvent(Base):
    """Individual punch events within an attendance session (IN, OUT, BREAK_START, BREAK_END)."""
    __tablename__ = "attendance_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"),
                                          nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                             comment="IN|OUT|BREAK_START|BREAK_END")
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False,
                                          server_default=text("'FACE'"))
    device_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("attendance_devices.id", ondelete="SET NULL"), nullable=True, index=True)
    geofence_zone_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("geofence_zones.id", ondelete="SET NULL"), nullable=True, index=True)
    gps_lat: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    gps_lng: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    is_synced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                            server_default=text("TRUE"))
    source: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                         server_default=text("'device'"),
                                         comment="device|api|bulk_import|manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))

    session: Mapped["AttendanceSession"] = relationship(
        "AttendanceSession", back_populates="events", foreign_keys=[session_id])
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    device: Mapped[Optional["AttendanceDevice"]] = relationship(
        "AttendanceDevice", foreign_keys=[device_id])
    geofence_zone: Mapped[Optional["GeofenceZone"]] = relationship(
        "GeofenceZone", foreign_keys=[geofence_zone_id])

    __table_args__ = (
        CheckConstraint("event_type IN ('IN','OUT','BREAK_START','BREAK_END')",
                        name="ck_attendance_event_type"),
        Index("ix_attendance_events_user_time", "user_id", "event_time"),
        Index("ix_attendance_events_session", "session_id"),
    )
    def __repr__(self): return f"<AttendanceEvent {self.id} {self.event_type!r} user={self.user_id}>"


# ── 1.2 SHIFT & ROSTER EXTENSIONS ─────────────────────────────────────────────

class ShiftTemplate(Base):
    """Reusable shift configuration templates (FIXED, FLEXIBLE, ROTATIONAL, NIGHT, SPLIT)."""
    __tablename__ = "shift_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(150), nullable=False)
    shift_type: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                             server_default=text("'FIXED'"),
                                             comment="FIXED|FLEXIBLE|ROTATIONAL|NIGHT|SPLIT")
    start_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    end_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    break_start_time: Mapped[Optional[time]] = mapped_column(Time(timezone=False), nullable=True)
    break_end_time: Mapped[Optional[time]] = mapped_column(Time(timezone=False), nullable=True)
    total_hours: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    grace_period_mins: Mapped[int] = mapped_column(Integer, nullable=False, default=5,
                                                    server_default=text("5"))
    buffer_mins: Mapped[int] = mapped_column(Integer, nullable=False, default=15,
                                             server_default=text("15"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                            server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_shift_template_org_name"),
        CheckConstraint("shift_type IN ('FIXED','FLEXIBLE','ROTATIONAL','NIGHT','SPLIT')",
                        name="ck_shift_template_type"),
    )
    def __repr__(self): return f"<ShiftTemplate {self.id} {self.name!r} type={self.shift_type!r}>"


class ShiftAssignment(Base):
    """Maps a user to a shift for a date range (permanent, temporary, rotational, swap)."""
    __tablename__ = "shift_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                                          nullable=False, index=True)
    shift_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("shifts.id", ondelete="SET NULL"),
                                                     nullable=True, index=True)
    shift_template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("shift_templates.id", ondelete="SET NULL"), nullable=True, index=True)
    assignment_type: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                                  server_default=text("'PERMANENT'"),
                                                  comment="PERMANENT|TEMPORARY|ROTATIONAL|SWAP")
    start_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                            server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    shift: Mapped[Optional["Shift"]] = relationship("Shift", foreign_keys=[shift_id])
    shift_template: Mapped[Optional["ShiftTemplate"]] = relationship(
        "ShiftTemplate", foreign_keys=[shift_template_id])
    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        CheckConstraint("assignment_type IN ('PERMANENT','TEMPORARY','ROTATIONAL','SWAP')",
                        name="ck_shift_assignment_type"),
        CheckConstraint("end_date >= start_date", name="ck_shift_assignment_dates"),
        Index("ix_shift_assignments_user_dates", "user_id", "start_date", "end_date"),
    )
    def __repr__(self): return f"<ShiftAssignment {self.id} user={self.user_id}>"


class Roster(Base):
    """Published weekly/monthly roster record per department."""
    __tablename__ = "rosters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    dept_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    roster_type: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                              server_default=text("'WEEKLY'"),
                                              comment="WEEKLY|MONTHLY|CUSTOM")
    start_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                         server_default=text("'DRAFT'"),
                                         comment="DRAFT|PUBLISHED|ARCHIVED")
    published_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    department: Mapped[Optional["Department"]] = relationship("Department", foreign_keys=[dept_id])
    published_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[published_by_user_id])
    entries: Mapped[List["RosterEntry"]] = relationship(
        "RosterEntry", back_populates="roster", cascade="all, delete-orphan",
        foreign_keys="RosterEntry.roster_id")

    __table_args__ = (
        CheckConstraint("roster_type IN ('WEEKLY','MONTHLY','CUSTOM')", name="ck_roster_type"),
        CheckConstraint("status IN ('DRAFT','PUBLISHED','ARCHIVED')", name="ck_roster_status"),
        CheckConstraint("end_date >= start_date", name="ck_roster_dates"),
    )
    def __repr__(self): return f"<Roster {self.id} {self.title!r} status={self.status!r}>"


class RosterEntry(Base):
    """Individual employee day within a roster."""
    __tablename__ = "roster_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    roster_id: Mapped[int] = mapped_column(Integer, ForeignKey("rosters.id", ondelete="CASCADE"),
                                            nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                                          nullable=False, index=True)
    work_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    shift_template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("shift_templates.id", ondelete="SET NULL"), nullable=True, index=True)
    shift_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("shifts.id", ondelete="SET NULL"),
                                                     nullable=True, index=True)
    start_time: Mapped[Optional[time]] = mapped_column(Time(timezone=False), nullable=True)
    end_time: Mapped[Optional[time]] = mapped_column(Time(timezone=False), nullable=True)
    status: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                         server_default=text("'SCHEDULED'"),
                                         comment="SCHEDULED|DRAFT|SWAPPED|ON_LEAVE|HOLIDAY|WEEKEND")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))

    roster: Mapped["Roster"] = relationship("Roster", back_populates="entries",
                                            foreign_keys=[roster_id])
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    shift_template: Mapped[Optional["ShiftTemplate"]] = relationship(
        "ShiftTemplate", foreign_keys=[shift_template_id])
    shift: Mapped[Optional["Shift"]] = relationship("Shift", foreign_keys=[shift_id])
    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        UniqueConstraint("roster_id", "user_id", "work_date", name="uq_roster_entry_user_date"),
        CheckConstraint("status IN ('SCHEDULED','DRAFT','SWAPPED','ON_LEAVE','HOLIDAY','WEEKEND')",
                        name="ck_roster_entry_status"),
    )
    def __repr__(self): return f"<RosterEntry {self.id} user={self.user_id} date={self.work_date}>"


class ShiftSwapRequest(Base):
    """Employee-initiated shift swap workflow."""
    __tablename__ = "shift_swap_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    requester_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    shift_assignment_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("shift_assignments.id", ondelete="SET NULL"), nullable=True, index=True)
    swap_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    requested_shift_template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("shift_templates.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                         server_default=text("'PENDING'"),
                                         comment="PENDING|APPROVED|REJECTED|CANCELLED")
    approver_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    workflow_request_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("approval_requests.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    requester: Mapped["User"] = relationship("User", foreign_keys=[requester_user_id])
    target_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[target_user_id])
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approver_user_id])
    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','CANCELLED')",
                        name="ck_shift_swap_status"),
        Index("ix_shift_swap_pending", "org_id", "status"),
    )
    def __repr__(self): return f"<ShiftSwapRequest {self.id} user={self.requester_user_id} status={self.status!r}>"


# ── 1.3 TIME TRACKING & BREAK MANAGEMENT ──────────────────────────────────────

class TimeEntry(Base):
    """Clock-in/clock-out/break tracking per user per day."""
    __tablename__ = "time_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"),
                                          nullable=False, index=True)
    work_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    clock_in: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    clock_out: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                      server_default=text("0"))
    net_work_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                   server_default=text("0"))
    status: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                         server_default=text("'ACTIVE'"),
                                         comment="ACTIVE|COMPLETED|MISSING_OUT")
    source: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                         server_default=text("'device'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    organization: Mapped["Organization"] = relationship("Organization")
    break_logs: Mapped[List["BreakLog"]] = relationship(
        "BreakLog", back_populates="time_entry", cascade="all, delete-orphan",
        foreign_keys="BreakLog.time_entry_id")

    __table_args__ = (
        UniqueConstraint("user_id", "work_date", name="uq_time_entry_user_date"),
        CheckConstraint("status IN ('ACTIVE','COMPLETED','MISSING_OUT')", name="ck_time_entry_status"),
    )
    def __repr__(self): return f"<TimeEntry {self.id} user={self.user_id} date={self.work_date}>"


class BreakLog(Base):
    """Break start/end events with type (LUNCH, SHORT, PRAYER, OTHER)."""
    __tablename__ = "break_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"),
                                          nullable=False, index=True)
    time_entry_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("time_entries.id", ondelete="SET NULL"), nullable=True, index=True)
    break_type: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                             server_default=text("'SHORT'"),
                                             comment="LUNCH|SHORT|PRAYER|OTHER")
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                   server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    time_entry: Mapped[Optional["TimeEntry"]] = relationship(
        "TimeEntry", back_populates="break_logs", foreign_keys=[time_entry_id])
    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        CheckConstraint("break_type IN ('LUNCH','SHORT','PRAYER','OTHER')", name="ck_break_log_type"),
        Index("ix_break_logs_user_time", "user_id", "start_time"),
    )
    def __repr__(self): return f"<BreakLog {self.id} user={self.user_id} type={self.break_type!r}>"


class OvertimeRecord(Base):
    """Computed overtime with approval workflow state."""
    __tablename__ = "overtime_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"),
                                          nullable=False, index=True)
    work_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    overtime_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                   server_default=text("0"))
    overtime_hours: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0,
                                                   server_default=text("0.0"))
    rate_multiplier: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False, default=1.50,
                                                    server_default=text("1.50"))
    status: Mapped[str] = mapped_column(NVARCHAR(25), nullable=False,
                                         server_default=text("'PENDING'"),
                                         comment="PENDING|APPROVED|REJECTED|COMP_OFF_CREDITED|PAID")
    approver_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approval_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workflow_request_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("approval_requests.id", ondelete="SET NULL"), nullable=True)
    comp_off_balance_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("comp_off_balances.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approver_user_id])
    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        UniqueConstraint("user_id", "work_date", name="uq_overtime_user_date"),
        CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','COMP_OFF_CREDITED','PAID')",
            name="ck_overtime_status"),
        CheckConstraint("overtime_minutes >= 0", name="ck_overtime_minutes_non_negative"),
    )
    def __repr__(self): return f"<OvertimeRecord {self.id} user={self.user_id} mins={self.overtime_minutes}>"


class CompOffBalance(Base):
    """Compensatory off ledger per user per year."""
    __tablename__ = "comp_off_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                                          nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, default=2026,
                                       server_default=text("2026"))
    entitled_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                   server_default=text("0"))
    used_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                               server_default=text("0"))
    pending_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                  server_default=text("0"))
    adjusted_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                   server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        UniqueConstraint("user_id", "year", name="uq_comp_off_user_year"),
    )

    @property
    def available_minutes(self) -> int:
        return max(0, self.entitled_minutes + self.adjusted_minutes - self.used_minutes - self.pending_minutes)

    def __repr__(self): return f"<CompOffBalance user={self.user_id} year={self.year} avail={self.available_minutes}>"


# ── 1.4 HOLIDAY & CALENDAR ────────────────────────────────────────────────────

class HolidayCalendar(Base):
    """Named holiday calendar per organization."""
    __tablename__ = "holiday_calendars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(150), nullable=False)
    country_code: Mapped[Optional[str]] = mapped_column(NVARCHAR(3), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                             server_default=text("FALSE"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                            server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    entries: Mapped[List["HolidayEntry"]] = relationship(
        "HolidayEntry", back_populates="calendar", cascade="all, delete-orphan",
        foreign_keys="HolidayEntry.calendar_id")

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_holiday_calendar_org_name"),
    )
    def __repr__(self): return f"<HolidayCalendar {self.id} {self.name!r}>"


class HolidayEntry(Base):
    """Individual holiday with type (NATIONAL, OPTIONAL, RESTRICTED, ORG_SPECIFIC)."""
    __tablename__ = "holiday_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    calendar_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("holiday_calendars.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    holiday_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    holiday_type: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                               server_default=text("'NATIONAL'"),
                                               comment="NATIONAL|OPTIONAL|RESTRICTED|ORG_SPECIFIC")
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                               server_default=text("FALSE"))
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))

    calendar: Mapped["HolidayCalendar"] = relationship(
        "HolidayCalendar", back_populates="entries", foreign_keys=[calendar_id])
    organization: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        UniqueConstraint("calendar_id", "holiday_date", name="uq_holiday_entry_calendar_date"),
        CheckConstraint(
            "holiday_type IN ('NATIONAL','OPTIONAL','RESTRICTED','ORG_SPECIFIC')",
            name="ck_holiday_entry_type"),
    )
    def __repr__(self): return f"<HolidayEntry {self.id} {self.name!r} date={self.holiday_date}>"


# ── 1.5 WORKFORCE PLANNING ────────────────────────────────────────────────────

class HeadcountPlan(Base):
    """Planned headcount per department per period."""
    __tablename__ = "headcount_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    dept_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2026,
                                              server_default=text("2026"))
    period_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    planned_headcount: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                    server_default=text("0"))
    approved_headcount: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                     server_default=text("0"))
    vacant_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                   server_default=text("0"))
    budgeted_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0,
                                                  server_default=text("0.0"))
    status: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                         server_default=text("'DRAFT'"),
                                         comment="DRAFT|APPROVED|ACTIVE|CLOSED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    department: Mapped[Optional["Department"]] = relationship("Department", foreign_keys=[dept_id])

    __table_args__ = (
        CheckConstraint("status IN ('DRAFT','APPROVED','ACTIVE','CLOSED')", name="ck_headcount_status"),
        Index("ix_headcount_plans_org_period", "org_id", "period_year", "period_month"),
    )
    def __repr__(self): return f"<HeadcountPlan {self.id} dept={self.dept_id} planned={self.planned_headcount}>"


class CapacitySnapshot(Base):
    """Point-in-time capacity/utilization snapshot."""
    __tablename__ = "capacity_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    dept_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    snapshot_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    total_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                 server_default=text("0"))
    allocated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                  server_default=text("0"))
    available_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                  server_default=text("0"))
    bench_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                              server_default=text("0"))
    utilization_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0,
                                                    server_default=text("0.0"))
    snapshot_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False,
                                                     server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    department: Mapped[Optional["Department"]] = relationship("Department", foreign_keys=[dept_id])

    __table_args__ = (
        CheckConstraint("utilization_pct >= 0 AND utilization_pct <= 100",
                        name="ck_capacity_utilization_range"),
        Index("ix_capacity_snapshots_org_date", "org_id", "snapshot_date"),
    )
    def __repr__(self): return f"<CapacitySnapshot {self.id} date={self.snapshot_date} util={self.utilization_pct}>"


class BenchRecord(Base):
    """Bench tracking per employee (unallocated capacity)."""
    __tablename__ = "bench_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                                          nullable=False, index=True)
    dept_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    bench_start_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    bench_end_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False,
                                         server_default=text("'ON_BENCH'"),
                                         comment="ON_BENCH|ALLOCATED|RELEASED")
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    days_on_bench: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    organization: Mapped["Organization"] = relationship("Organization")
    department: Mapped[Optional["Department"]] = relationship("Department", foreign_keys=[dept_id])

    __table_args__ = (
        CheckConstraint("status IN ('ON_BENCH','ALLOCATED','RELEASED')", name="ck_bench_status"),
        Index("ix_bench_records_active", "org_id", "status"),
    )
    def __repr__(self): return f"<BenchRecord {self.id} user={self.user_id} status={self.status!r}>"


class WorkforceForcast(Base):
    """Future hiring requirement projections."""
    __tablename__ = "workforce_forcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("organizations.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    dept_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    forecast_period: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    current_headcount: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                    server_default=text("0"))
    projected_headcount: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                      server_default=text("0"))
    hiring_requirement: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                     server_default=text("0"))
    attrition_estimate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0,
                                                       server_default=text("0.0"))
    growth_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0,
                                                server_default=text("0.0"))
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0,
                                                     server_default=text("0.0"))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_utc_now, onupdate=_utc_now,
                                                  server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    department: Mapped[Optional["Department"]] = relationship("Department", foreign_keys=[dept_id])

    __table_args__ = (
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 100",
                        name="ck_forcast_confidence_range"),
        Index("ix_workforce_forcasts_org_period", "org_id", "forecast_period"),
    )
    def __repr__(self): return f"<WorkforceForcast {self.id} period={self.forecast_period} hire={self.hiring_requirement}>"


# =============================================================================
# SPRINT 5 — HUMAN CAPITAL MANAGEMENT (HCM) DOMAIN ENTITIES
# =============================================================================

class EmployeeProfile(Base):
    """Extended Employee Master Profile (Personal, Medical, Passport, Background Verification)."""
    __tablename__ = "hcm_employee_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # Personal Info
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    marital_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    blood_group: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    languages_spoken: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # ["English", "Spanish"]
    
    # Medical Info
    medical_allergies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    disability_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    medical_fitness_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="fit")
    
    # Visa & Passport
    passport_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    passport_expiry: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    visa_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    visa_expiry: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    work_permit_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Background Verification
    bg_verification_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")  # pending|verified|failed|waived
    bg_verification_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    bg_vendor_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Audit & Status
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    user: Mapped["User"] = relationship("User")

    def __repr__(self): return f"<EmployeeProfile user={self.user_id} bg={self.bg_verification_status}>"


class EmployeeEducation(Base):
    """Employee educational qualification history."""
    __tablename__ = "hcm_employee_educations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    degree: Mapped[str] = mapped_column(String(100), nullable=False)  # Bachelor's, Master's, Doctorate, Diploma
    field_of_study: Mapped[str] = mapped_column(String(150), nullable=False)
    institution_name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    end_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    grade_or_gpa: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    user: Mapped["User"] = relationship("User")

    def __repr__(self): return f"<EmployeeEducation user={self.user_id} degree='{self.degree}'>"


class EmployeeExperience(Base):
    """Prior professional employment experience."""
    __tablename__ = "hcm_employee_experiences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(150), nullable=False)
    job_title: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[Date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    user: Mapped["User"] = relationship("User")

    def __repr__(self): return f"<EmployeeExperience user={self.user_id} company='{self.company_name}'>"


class EmployeeAward(Base):
    """Awards and corporate recognitions."""
    __tablename__ = "hcm_employee_awards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    awarded_by: Mapped[str] = mapped_column(String(150), nullable=False)
    award_date: Mapped[Date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="spot_award")  # spot_award|annual|leadership|innovation
    cash_prize: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    user: Mapped["User"] = relationship("User")

    def __repr__(self): return f"<EmployeeAward user={self.user_id} title='{self.title}'>"


class EmployeeLicense(Base):
    """Professional licenses & regulatory certifications."""
    __tablename__ = "hcm_employee_licenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    license_name: Mapped[str] = mapped_column(String(150), nullable=False)
    license_number: Mapped[str] = mapped_column(String(100), nullable=False)
    issuing_authority: Mapped[str] = mapped_column(String(150), nullable=False)
    issue_date: Mapped[Date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")  # active|expired|revoked
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    user: Mapped["User"] = relationship("User")

    def __repr__(self): return f"<EmployeeLicense user={self.user_id} name='{self.license_name}'>"


class EmployeeEmergencyContact(Base):
    """Emergency contact details for employees."""
    __tablename__ = "hcm_employee_emergency_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_name: Mapped[str] = mapped_column(String(100), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)  # Spouse|Parent|Sibling|Friend|Other
    phone_number: Mapped[str] = mapped_column(String(30), nullable=False)
    alternate_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    user: Mapped["User"] = relationship("User")

    def __repr__(self): return f"<EmployeeEmergencyContact user={self.user_id} contact='{self.contact_name}'>"


class TalentPool(Base):
    """Talent pool definition for succession & high-potential tracking."""
    __tablename__ = "hcm_talent_pools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pool_type: Mapped[str] = mapped_column(String(50), nullable=False, default="executive")  # executive|technical|future_leaders|critical_roles
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")  # active|archived
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    members: Mapped[List["TalentPoolMember"]] = relationship("TalentPoolMember", back_populates="pool", cascade="all, delete-orphan")

    def __repr__(self): return f"<TalentPool name='{self.name}' type='{self.pool_type}'>"


class TalentPoolMember(Base):
    """Member mapping in a Talent Pool."""
    __tablename__ = "hcm_talent_pool_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    pool_id: Mapped[int] = mapped_column(Integer, ForeignKey("hcm_talent_pools.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    readiness_level: Mapped[str] = mapped_column(String(30), nullable=False, default="ready_1_year")  # ready_now|ready_1_year|ready_2_years
    nomination_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    pool: Mapped["TalentPool"] = relationship("TalentPool", back_populates="members")
    user: Mapped["User"] = relationship("User")

    def __repr__(self): return f"<TalentPoolMember pool={self.pool_id} user={self.user_id}>"


class EmployeeDocument(Base):
    """Integrated Employee Document Vault linking with Enterprise File Service."""
    __tablename__ = "hcm_employee_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # UUID from enterprise file service
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)  # identity|education|offer_letter|contract|payslip|performance|medical|policy
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_signed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    access_level: Mapped[str] = mapped_column(String(30), nullable=False, default="confidential")  # public|internal|confidential|restricted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, server_default=text("NOW()"))

    organization: Mapped["Organization"] = relationship("Organization")
    user: Mapped["User"] = relationship("User")

    def __repr__(self): return f"<EmployeeDocument title='{self.title}' type='{self.document_type}'>"


