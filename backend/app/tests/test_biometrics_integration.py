import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from main import app as fastapi_app
from app.api.deps import get_current_active_user, get_db
from app.services.face_engine import face_engine
from app.services.liveness import liveness_service


# =====================================================
# TEST CLIENT
# =====================================================

client = TestClient(fastapi_app)


# =====================================================
# MOCK USERS
# =====================================================

class DummyRole:
    name = "Employee"


class DummyShift:
    start_time = datetime(2025, 1, 1, 9, 0).time()
    grace_period_mins = 5
    buffer_mins = 15


class MockUser:
    id = 1
    org_id = "test-org-uuid"
    role_id = 1
    role = DummyRole()
    shift = DummyShift()


def override_get_current_active_user():
    return MockUser()


def override_get_db():
    session = MagicMock()
    yield session


@pytest.fixture(autouse=True)
def setup_biometrics_overrides():
    fastapi_app.dependency_overrides[get_current_active_user] = override_get_current_active_user
    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield
    fastapi_app.dependency_overrides.pop(get_current_active_user, None)
    fastapi_app.dependency_overrides.pop(get_db, None)


# =====================================================
# REDIS MOCK
# =====================================================

from app.core import rate_limit
_ORIGINAL_GET_REDIS = rate_limit._get_redis


class MockPipeline:
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


# =====================================================
# ATTENDANCE CONTROLLER MOCK
# =====================================================

from app.services.attendance_controller import attendance_controller
from app.repositories.attendance_repo import attendance_repo


class MockAttendanceLog:
    id = 100
    user_id = 1
    status = "on_time"
    check_in = datetime.now(timezone.utc)
    check_out = None
    emotion = "happy"
    is_live = 1
    recognition_distance = 0.2
    source = "edge"
    created_at = datetime.now(timezone.utc)


_ORIGINAL_CONTROLLER_LOG_CHECK_IN = attendance_controller.log_check_in
_MODULE_CONTROLLER_LOG_CHECK_IN = MagicMock(
    return_value=MockAttendanceLog()
)

_BASELINE_BIOMETRIC_STATE = {
    "liveness_detect": liveness_service.detect_liveness,
    "face_embedding": face_engine.get_embedding,
    "face_emotion": face_engine.get_emotion,
    "repo_find_user": attendance_repo.find_user_by_face,
    "controller_log_check_in": _ORIGINAL_CONTROLLER_LOG_CHECK_IN,
}


@pytest.fixture(autouse=True)
def restore_biometric_state():
    # The client is now resolved per event loop, so patch the
    # resolver rather than a cached client object.
    rate_limit._get_redis = lambda: MockRedisClient()
    attendance_controller.log_check_in = _MODULE_CONTROLLER_LOG_CHECK_IN
    yield
    rate_limit._get_redis = _ORIGINAL_GET_REDIS
    liveness_service.detect_liveness = _BASELINE_BIOMETRIC_STATE["liveness_detect"]
    face_engine.get_embedding = _BASELINE_BIOMETRIC_STATE["face_embedding"]
    face_engine.get_emotion = _BASELINE_BIOMETRIC_STATE["face_emotion"]
    attendance_repo.find_user_by_face = _BASELINE_BIOMETRIC_STATE["repo_find_user"]
    attendance_controller.log_check_in = _BASELINE_BIOMETRIC_STATE["controller_log_check_in"]


# =====================================================
# SUCCESSFUL CHECK-IN
# =====================================================

def test_checkin_success():

    from app.services.face_engine import face_engine
    from app.services.liveness import liveness_service
    from app.repositories.attendance_repo import attendance_repo

    liveness_service.detect_liveness = MagicMock(
        return_value=(True, 0.98)
    )

    face_engine.get_embedding = MagicMock(
        return_value=[0.1] * 128
    )

    face_engine.get_emotion = MagicMock(
        return_value="happy"
    )

    attendance_repo.find_user_by_face = MagicMock()

    mock_match = MagicMock()
    mock_match.user_id = 1

    attendance_repo.find_user_by_face.return_value = mock_match

    response = client.post(
        "/api/v1/attendance/check-in",
        json={
            "image_base64": "ZHVtbXk=",
            "source": "edge"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["user_id"] == 1
    assert data["status"] == "on_time"


# =====================================================
# SPOOF ATTACK
# =====================================================

def test_checkin_spoof_rejected():

    from app.services.face_engine import face_engine
    from app.services.liveness import liveness_service

    liveness_service.detect_liveness = MagicMock(
        return_value=(False, 0.10)
    )

    face_engine.get_embedding = MagicMock(
        return_value=[0.1] * 128
    )

    response = client.post(
        "/api/v1/attendance/check-in",
        json={
            "image_base64": "ZHVtbXk=",
            "source": "edge"
        }
    )

    assert response.status_code in [401, 403]


# =====================================================
# NO FACE DETECTED
# =====================================================

def test_checkin_no_face_detected():

    from app.services.face_engine import face_engine
    from app.services.liveness import liveness_service

    liveness_service.detect_liveness = MagicMock(
        return_value=(True, 0.98)
    )

    face_engine.get_embedding = MagicMock(
        return_value=None
    )

    response = client.post(
        "/api/v1/attendance/check-in",
        json={
            "image_base64": "ZHVtbXk=",
            "source": "edge"
        }
    )

    assert response.status_code in [400, 404]


# =====================================================
# UNKNOWN FACE
# =====================================================

def test_checkin_unknown_face():

    from app.services.face_engine import face_engine
    from app.services.liveness import liveness_service
    from app.repositories.attendance_repo import attendance_repo

    liveness_service.detect_liveness = MagicMock(
        return_value=(True, 0.98)
    )

    face_engine.get_embedding = MagicMock(
        return_value=[0.1] * 128
    )

    attendance_repo.find_user_by_face = MagicMock(
        return_value=None
    )

    response = client.post(
        "/api/v1/attendance/check-in",
        json={
            "image_base64": "ZHVtbXk=",
            "source": "edge"
        }
    )

    assert response.status_code in [400, 404]
