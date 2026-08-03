from __future__ import annotations

from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps

from app.db.database import get_db
from app.db.models.all_models import UserSession
from app.schema.session import DeleteResponse, UserSessionListOut, UserSessionOut
from app.services.session_service import session_service

router = APIRouter(tags=["sessions"])


@router.get("/sessions", response_model=UserSessionListOut)
def list_sessions(
    *,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_active_user),
) -> Any:
    sessions: List[UserSession] = session_service.list_my_sessions(db, user_id=current_user.id)
    return {"sessions": sessions}


@router.delete("/sessions/{session_id}", response_model=DeleteResponse)
def delete_session(
    session_id: UUID,
    *,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_active_user),
) -> Any:
    obj = session_service.delete_session(db, user_id=current_user.id, session_id=session_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return {"detail": "Session deleted"}


@router.get("/sessions/{session_id}", response_model=UserSessionOut)
def get_session(
    session_id: UUID,
    *,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_active_user),
) -> Any:
    obj = session_service.get_session(db, user_id=current_user.id, session_id=session_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return obj


@router.delete("/sessions", response_model=DeleteResponse)
def delete_all_sessions(
    *,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_active_user),
    token: str = Depends(deps.oauth2_scheme),
) -> Any:
    try:
        from jose import jwt
        from app.core.config import settings
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        current_jti = payload.get("jti")
    except Exception:
        current_jti = None

    session_service.revoke_all_my_sessions(db, user_id=current_user.id, except_jti=current_jti)
    return {"detail": "All sessions deleted"}


@router.post("/sessions/revoke/{session_id}", response_model=DeleteResponse)
def revoke_session(
    session_id: UUID,
    *,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_active_user),
) -> Any:
    obj = session_service.delete_session(db, user_id=current_user.id, session_id=session_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return {"detail": "Session revoked"}


@router.post("/sessions/revoke", response_model=DeleteResponse)
def revoke_session_by_id(
    session_id: UUID,
    *,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_active_user),
) -> Any:
    """Compatibility endpoint for clients that submit the session id as a parameter."""
    obj = session_service.delete_session(db, user_id=current_user.id, session_id=session_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return {"detail": "Session revoked"}


@router.post("/sessions/revoke-all", response_model=DeleteResponse)
def revoke_all_sessions(
    *,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_active_user),
) -> Any:
    session_service.revoke_all_my_sessions(db, user_id=current_user.id)
    return {"detail": "All sessions revoked"}

