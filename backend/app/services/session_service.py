from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.crud.crud_session import user_session
from app.db.models.all_models import UserSession


class SessionService:
    def list_my_sessions(self, db: Session, *, user_id: int) -> List[UserSession]:
        return user_session.list_for_user(db, user_id=user_id)

    def get_session(self, db: Session, *, user_id: int, session_id: UUID) -> Optional[UserSession]:
        return user_session.get_for_user_by_id(db, user_id=user_id, session_id=session_id)

    def delete_session(self, db: Session, *, user_id: int, session_id: UUID) -> Optional[UserSession]:
        obj = self.get_session(db, user_id=user_id, session_id=session_id)
        if not obj:
            return None
        now = datetime.now(timezone.utc)
        obj.is_active = False
        obj.revoked_at = now
        obj.logout_at = now
        obj.last_activity_at = now
        obj.revoke_reason = "session_deleted"
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def revoke_all_my_sessions(self, db: Session, *, user_id: int, except_jti: str | None = None,
                               reason: str = "all_sessions_revoked") -> int:
        revoked = user_session.revoke_all_for_user(
            db, user_id=user_id, except_jti=except_jti, reason=reason, logout=True)
        return len(revoked)

    def touch_session_last_activity(
        self,
        db: Session,
        *,
        user_id: int,
        jti: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_name: Optional[str] = None,
        browser: Optional[str] = None,
        operating_system: Optional[str] = None,
    ) -> Optional[UserSession]:
        session_obj = user_session.get_for_user_by_jti(db, user_id=user_id, jti=jti)
        if not session_obj or not session_obj.is_active:
            return None

        session_obj.last_activity_at = datetime.now(timezone.utc)
        # Update metadata opportunistically.
        if ip_address:
            session_obj.ip_address = ip_address
        if user_agent:
            session_obj.user_agent = user_agent
        if device_name is not None:
            session_obj.device_name = device_name
        if browser is not None:
            session_obj.browser = browser
        if operating_system is not None:
            session_obj.operating_system = operating_system

        db.add(session_obj)
        db.commit()
        db.refresh(session_obj)
        return session_obj


session_service = SessionService()
