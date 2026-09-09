"""
notifications.py — Database-backed in-app notification REST API.
Provides per-user notification listing, mark-as-read, and mark-all-read.
Notifications are persisted in PostgreSQL ('notifications' table) with strict
tenant isolation and user scoping.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import SessionLocal
from app.db.models.all_models import User, Notification

router = APIRouter()


def _push_notification(
    org_id: Any,
    user_id: int,
    *,
    title: str,
    message: str,
    notif_type: str = "info",
    action_url: Optional[str] = None,
    source_event: Optional[str] = None,
    db: Optional[Session] = None,
) -> dict:
    """Push a notification into PostgreSQL DB. Called by service layer or endpoints."""
    parsed_org_id = uuid.UUID(str(org_id)) if isinstance(org_id, str) else org_id
    notif_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    def _insert(session: Session) -> Notification:
        obj = Notification(
            id=notif_id,
            user_id=user_id,
            org_id=parsed_org_id,
            title=title,
            message=message,
            type=notif_type,
            action_url=action_url,
            source_event=source_event,
            is_read=False,
            created_at=now,
        )
        session.add(obj)
        return obj

    if db is not None:
        obj = _insert(db)
        db.flush()
    else:
        with SessionLocal() as session:
            obj = _insert(session)
            session.commit()

    return {
        "id": notif_id,
        "user_id": user_id,
        "org_id": str(parsed_org_id),
        "title": title,
        "message": message,
        "type": notif_type,
        "action_url": action_url,
        "source_event": source_event,
        "is_read": False,
        "read_at": None,
        "created_at": now.isoformat(),
    }


def push_notification_to_org_managers(
    db: Session,
    org_id: Any,
    title: str,
    message: str,
    *,
    notif_type: str = "info",
    action_url: Optional[str] = None,
    source_event: Optional[str] = None,
    exclude_user_id: Optional[int] = None,
) -> None:
    """Find all Admins/Managers in the organization and push a notification to each."""
    from app.db.models.all_models import User, Role
    try:
        parsed_org_id = uuid.UUID(str(org_id)) if isinstance(org_id, str) else org_id
        managers = (
            db.query(User)
            .filter(
                User.org_id == parsed_org_id,
                User.is_active == 1,
                User.is_deleted == 0
            )
            .join(User.role)
            .filter(Role.name.in_(["Admin", "SuperAdmin", "OrgAdmin", "Manager", "OrgManager"]))
            .all()
        )
        for m in managers:
            if exclude_user_id and m.id == exclude_user_id:
                continue
            _push_notification(
                parsed_org_id,
                m.id,
                title=title,
                message=message,
                notif_type=notif_type,
                action_url=action_url,
                source_event=source_event,
                db=db,
            )
        db.flush()
    except Exception as err:
        pass


# Expose push functions so other services can import them
push_notification = _push_notification


# ── Pydantic schemas ────────────────────────────────────────────────
class NotificationOut(BaseModel):
    id: str
    user_id: int
    org_id: str
    title: str
    message: str
    type: str
    action_url: Optional[str] = None
    source_event: Optional[str] = None
    is_read: bool
    read_at: Optional[str] = None
    created_at: str


class NotificationList(BaseModel):
    notifications: List[NotificationOut]
    unread_count: int
    total: int


# ── Endpoints ───────────────────────────────────────────────────────
@router.get("", response_model=NotificationList, summary="Get my notifications")
def get_my_notifications(
    skip: int = 0,
    limit: int = 50,
    unread_only: bool = False,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
) -> Any:
    """Return the authenticated user's in-app notifications (newest first)."""
    base_query = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.org_id == current_user.org_id,
    )
    if unread_only:
        base_query = base_query.filter(Notification.is_read == False)

    total = base_query.count()
    unread_count = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.org_id == current_user.org_id,
            Notification.is_read == False,
        )
        .count()
    )

    rows = (
        base_query.order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    items = [
        NotificationOut(
            id=r.id,
            user_id=r.user_id,
            org_id=str(r.org_id),
            title=r.title,
            message=r.message,
            type=r.type,
            action_url=r.action_url,
            source_event=r.source_event,
            is_read=r.is_read,
            read_at=r.read_at.isoformat() if r.read_at else None,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]

    return NotificationList(
        notifications=items,
        unread_count=unread_count,
        total=total,
    )


@router.patch("/{notification_id}/read", summary="Mark a notification as read")
def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
) -> Any:
    notif = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
            Notification.org_id == current_user.org_id,
        )
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    if not notif.is_read:
        notif.is_read = True
        notif.read_at = datetime.now(timezone.utc)
        db.commit()

    return {"ok": True}


@router.patch("/read-all", summary="Mark all notifications as read")
def mark_all_read(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
) -> Any:
    now = datetime.now(timezone.utc)
    updated_count = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.org_id == current_user.org_id,
            Notification.is_read == False,
        )
        .update({"is_read": True, "read_at": now}, synchronize_session=False)
    )
    db.commit()
    return {"ok": True, "marked_read": updated_count}


@router.get("/unread-count", summary="Get unread notification count")
def get_unread_count(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
) -> Any:
    count = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.org_id == current_user.org_id,
            Notification.is_read == False,
        )
        .count()
    )
    return {"unread_count": count}


@router.delete("/{notification_id}", summary="Dismiss a notification")
def delete_notification(
    notification_id: str,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
) -> Any:
    notif = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
            Notification.org_id == current_user.org_id,
        )
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    db.delete(notif)
    db.commit()
    return {"ok": True}
