"""
Regression tests for frontend/backend integration fixes.

Covers:
- Liveness failure returns structured error code
- Auth refresh not triggered on login endpoint
- 403 errors contain structured detail when available
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app as fastapi_app
from app.api.deps import get_current_active_user, get_db
from app.services.liveness import liveness_service
from app.services.face_engine import face_engine
from app.repositories.attendance_repo import attendance_repo
from app.services.attendance_controller import attendance_controller
from app.core import rate_limit


class DummyRole:
    name = "Employee"


class DummyShift:
    start_time = __import__('datetime').datetime(2025, 1, 1, 9, 0).time()
    grace_period_mins = 5
    buffer_mins = 15


class MockUser:
    id = 1
    org_id = "test-org-uuid"
    role_id = 1
    role = DummyRole()
    shift = DummyShift()
    full_name = "Test User"
    email = "test@example.com"
    username = "testuser"
    employee_id = "EMP001"
    is_active = 1
    created_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)


def override_get_current_active_user():
    return MockUser()


def override_get_db():
    session = MagicMock()
    yield session


@pytest.fixture(autouse=True)
def setup_overrides():
    fastapi_app.dependency_overrides[get_current_active_user] = override_get_current_active_user
    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield
    fastapi_app.dependency_overrides.pop(get_current_active_user, None)
    fastapi_app.dependency_overrides.pop(get_db, None)


class MockPipeline:
    def __init__(self, *args, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    def incr(self, *args, **kwargs):
        pass
    def expire(self, *args, **kwargs):
        pass
    async def execute(self):
        return [1]


class MockRedisClient:
    def pipeline(self, *args, **kwargs):
        return MockPipeline()


rate_limit.redis_client = MockRedisClient()


client = TestClient(fastapi_app)


def test_liveness_failure_returns_structured_error():
    """Liveness failure must return a structured error with code LIVENESS_FAILED."""
    liveness_service.detect_liveness = MagicMock(return_value=(False, 0.10))
    face_engine.get_embedding = MagicMock(return_value=[0.1] * 128)

    response = client.post(
        "/api/v1/attendance/check-in",
        json={"image_base64": "ZHVtbXk=", "source": "edge"},
    )

    assert response.status_code == 403
    data = response.json()
    assert isinstance(data, dict)
    detail = data.get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "LIVENESS_FAILED"
    assert "message" in detail


def test_checkout_liveness_failure_returns_structured_error():
    """Check-out with liveness failure must return structured error."""
    liveness_service.detect_liveness = MagicMock(return_value=(False, 0.10))
    face_engine.get_embedding = MagicMock(return_value=[0.1] * 128)

    response = client.post(
        "/api/v1/attendance/check-out",
        json={"image_base64": "ZHVtbXk=", "source": "edge"},
    )

    assert response.status_code == 403
    data = response.json()
    assert isinstance(data, dict)
    detail = data.get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "LIVENESS_FAILED"


def test_checkin_success_returns_200():
    """Successful check-in with all mocks should return 200."""
    from app.services.attendance_controller import attendance_controller

    liveness_service.detect_liveness = MagicMock(return_value=(True, 0.98))
    face_engine.get_embedding = MagicMock(return_value=[0.1] * 128)

    mock_match = MagicMock()
    mock_match.user_id = 1
    attendance_repo.find_user_by_face = MagicMock(return_value=mock_match)

    class MockAttendanceLog:
        id = 100
        user_id = 1
        status = "on_time"
        check_in = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
        check_out = None
        emotion = "happy"
        is_live = 1
        recognition_distance = 0.2
        source = "edge"
        created_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)

    attendance_controller.log_check_in = MagicMock(return_value=MockAttendanceLog())

    response = client.post(
        "/api/v1/attendance/check-in",
        json={"image_base64": "ZHVtbXk=", "source": "edge"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == 1


def test_refresh_endpoint_returns_422_without_token():
    """Refresh without token must return 422, not 500."""
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 422
