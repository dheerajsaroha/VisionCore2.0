import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db as deps_get_db
from app.db.database import get_db as router_get_db
from app.db.models.all_models import Notification, User
from app.routers.notifications import push_notification, push_notification_to_org_managers
from main import app


@pytest.fixture(autouse=True)
def clean_overrides():
    yield
    app.dependency_overrides.clear()


def test_notification_db_persistence_and_lifecycle(client: TestClient, db: Session):
    """
    Verify notification insertion into DB, fetch via endpoint, mark as read, unread count, and deletion.
    """
    user = db.query(User).filter(User.is_active == 1, User.is_deleted == 0).first()
    assert user is not None

    app.dependency_overrides[router_get_db] = lambda: db
    app.dependency_overrides[deps_get_db] = lambda: db
    app.dependency_overrides[get_current_active_user] = lambda: user

    # 1. Push notification via DB helper
    notif = push_notification(
        user.org_id,
        user.id,
        title="Test Security Alert",
        message="Your security settings were updated.",
        notif_type="warning",
        db=db,
    )
    assert notif["id"] is not None

    # Verify notification row in PostgreSQL
    db_notif = db.query(Notification).filter(Notification.id == notif["id"]).first()
    assert db_notif is not None
    assert db_notif.is_read is False

    # 2. Get unread count
    uc_resp = client.get("/api/v1/notifications/unread-count")
    assert uc_resp.status_code == 200
    assert uc_resp.json()["unread_count"] >= 1

    # 3. List notifications
    list_resp = client.get("/api/v1/notifications")
    assert list_resp.status_code == 200
    notifs = list_resp.json()["notifications"]
    assert any(n["id"] == notif["id"] for n in notifs)

    # 4. Mark single read
    read_resp = client.patch(f"/api/v1/notifications/{notif['id']}/read")
    assert read_resp.status_code == 200

    # Verify state in DB
    db.refresh(db_notif)
    assert db_notif.is_read is True

    # 5. Delete notification
    del_resp = client.delete(f"/api/v1/notifications/{notif['id']}")
    assert del_resp.status_code == 200

    db_deleted = db.query(Notification).filter(Notification.id == notif["id"]).first()
    assert db_deleted is None


def test_push_notification_to_org_managers_db(client: TestClient, db: Session):
    """
    Verify push_notification_to_org_managers persists alerts for organization managers.
    """
    admin_user = (
        db.query(User)
        .filter(User.is_active == 1, User.is_deleted == 0)
        .join(User.role)
        .filter(User.role.has(name="Admin"))
        .first()
    )
    if not admin_user:
        admin_user = db.query(User).filter(User.is_active == 1, User.is_deleted == 0).first()

    assert admin_user is not None

    app.dependency_overrides[router_get_db] = lambda: db
    app.dependency_overrides[deps_get_db] = lambda: db
    app.dependency_overrides[get_current_active_user] = lambda: admin_user

    push_notification_to_org_managers(
        db,
        admin_user.org_id,
        title="Pending Leave Request",
        message="Employee John Doe submitted a leave request.",
        notif_type="info",
    )

    # Fetch admin notifications
    list_resp = client.get("/api/v1/notifications")
    assert list_resp.status_code == 200
    notifs = list_resp.json()["notifications"]
    assert any("Pending Leave Request" in n["title"] for n in notifs)
