import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db as deps_get_db
from app.db.database import get_db as router_get_db
from app.db.models.all_models import AttendanceLog, User, Organization, Role
from main import app


@pytest.fixture(autouse=True)
def clean_overrides():
    yield
    app.dependency_overrides.clear()


def test_checkout_without_checkin_returns_400(client: TestClient, db: Session):
    """Attempting to check out without an active check-in record must return 400."""
    user = db.query(User).filter(User.is_active == 1, User.is_deleted == 0).first()
    assert user is not None, "Test requires at least one active user in DB"

    app.dependency_overrides[router_get_db] = lambda: db
    app.dependency_overrides[deps_get_db] = lambda: db
    app.dependency_overrides[get_current_active_user] = lambda: user

    # Ensure no open sessions exist for this user
    open_logs = db.query(AttendanceLog).filter(
        AttendanceLog.user_id == user.id,
        AttendanceLog.check_out.is_(None),
        AttendanceLog.is_deleted == 0
    ).all()
    now_utc = datetime.now(timezone.utc)
    for l in open_logs:
        l.check_out = now_utc
    db.commit()

    response = client.post("/api/v1/attendance/check-out")
    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "No active check-in found" in detail


def test_successful_checkout_flow(client: TestClient, db: Session):
    """
    1. Create active check-in record.
    2. Post to check-out.
    3. Verify check_out timestamp is populated.
    4. Attempt second check-out (duplicate) and verify 400.
    """
    user = db.query(User).filter(User.is_active == 1, User.is_deleted == 0).first()
    assert user is not None, "Test requires at least one active user in DB"

    app.dependency_overrides[router_get_db] = lambda: db
    app.dependency_overrides[deps_get_db] = lambda: db
    app.dependency_overrides[get_current_active_user] = lambda: user

    # Clean up open sessions
    open_logs = db.query(AttendanceLog).filter(
        AttendanceLog.user_id == user.id,
        AttendanceLog.check_out.is_(None),
        AttendanceLog.is_deleted == 0
    ).all()
    now_utc = datetime.now(timezone.utc)
    for l in open_logs:
        l.check_out = now_utc
    db.commit()

    # Insert open attendance log
    log = AttendanceLog(
        user_id=user.id,
        check_in=now_utc,
        status="on_time",
        is_live=1,
        source="ai",
        is_deleted=0,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    assert log.check_out is None

    # Perform check-out
    co_resp = client.post("/api/v1/attendance/check-out")
    assert co_resp.status_code == 200, co_resp.text
    data = co_resp.json()
    assert data["id"] == log.id
    assert data["check_out"] is not None

    # Verify second check-out fails with 400
    dup_resp = client.post("/api/v1/attendance/check-out")
    assert dup_resp.status_code == 400
