from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.db.models.all_models import UserSession


class CRUDUserSession:
    def get_for_user_by_jti(self, db: Session, *, user_id: int, jti: str) -> Optional[UserSession]:
        return (
            db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.jti == jti,
            )
            .order_by(UserSession.created_at.desc())
            .first()
        )

    def list_for_user(self, db: Session, *, user_id: int, include_inactive: bool = False) -> List[UserSession]:
        q = db.query(UserSession).filter(UserSession.user_id == user_id)
        if not include_inactive:
            q = q.filter(UserSession.is_active == True)
        return q.order_by(UserSession.created_at.desc()).all()

    def create_for_user(self, db: Session, *, user_id: int, jti: str,
                         refresh_jti: Optional[str] = None, expires_at: Optional[datetime] = None,
                         ip_address: Optional[str] = None, user_agent: Optional[str] = None,
                         device_name: Optional[str] = None, device_type: Optional[str] = None,
                         browser: Optional[str] = None, browser_version: Optional[str] = None,
                         operating_system: Optional[str] = None,
                         operating_system_version: Optional[str] = None) -> UserSession:
        obj = UserSession(
            user_id=user_id,
            jti=jti,
            refresh_jti=refresh_jti,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            device_name=device_name,
            device_type=device_type,
            browser=browser,
            browser_version=browser_version,
            operating_system=operating_system,
            operating_system_version=operating_system_version,
            is_active=True,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update_last_activity(self, db: Session, *, session_obj: UserSession, now: datetime | None = None) -> UserSession:
        if now is None:
            now = datetime.now(timezone.utc)
        session_obj.last_activity_at = now
        db.add(session_obj)
        db.commit()
        db.refresh(session_obj)
        return session_obj

    def get_for_user_by_id(self, db: Session, *, user_id: int, session_id: UUID) -> Optional[UserSession]:
        return db.query(UserSession).filter(
            UserSession.user_id == user_id, UserSession.id == session_id
        ).first()

    def get_for_user_by_refresh_jti(self, db: Session, *, user_id: int, refresh_jti: str) -> Optional[UserSession]:
        return db.query(UserSession).filter(
            UserSession.user_id == user_id, UserSession.refresh_jti == refresh_jti
        ).order_by(UserSession.created_at.desc()).first()

    def get_active_for_user_by_refresh_jti(self, db: Session, *, user_id: int, refresh_jti: str) -> Optional[UserSession]:
        """Strict lookup of an active session matching refresh_jti."""
        return (
            db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.refresh_jti == refresh_jti,
                UserSession.is_active == True,
            )
            .order_by(UserSession.created_at.desc())
            .first()
        )

    def get_latest_active_session_for_user(self, db: Session, *, user_id: int) -> Optional[UserSession]:
        """Return the most recent active session for a user.
        Used as a fallback when refresh_jti lookup does not match any session."""
        return (
            db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
            )
            .order_by(UserSession.created_at.desc())
            .first()
        )

    def revoke_by_session(self, db: Session, *, user_id: int, jti: str,
                          reason: Optional[str] = None, logout: bool = False) -> Optional[UserSession]:
        obj = (
            db.query(UserSession)
            .filter(UserSession.user_id == user_id, UserSession.jti == jti)
            .order_by(UserSession.created_at.desc())
            .first()
        )
        if not obj:
            return None
        now = datetime.now(timezone.utc)
        obj.is_active = False
        obj.revoked_at = now
        obj.revoke_reason = reason
        if logout:
            obj.logout_at = now
        obj.last_activity_at = now
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def revoke_all_for_user(self, db: Session, *, user_id: int, except_jti: str | None = None,
                            reason: Optional[str] = None, logout: bool = False) -> List[UserSession]:
        q = db.query(UserSession).filter(UserSession.user_id == user_id)
        if except_jti is not None:
            q = q.filter(UserSession.jti != except_jti)
        q = q.filter(UserSession.is_active == True)
        objs = q.all()
        now = datetime.now(timezone.utc)
        for obj in objs:
            obj.is_active = False
            obj.revoked_at = now
            obj.revoke_reason = reason
            obj.last_activity_at = now
            if logout:
                obj.logout_at = now
            db.add(obj)
        db.commit()
        for obj in objs:
            db.refresh(obj)
        return objs


user_session = CRUDUserSession()

