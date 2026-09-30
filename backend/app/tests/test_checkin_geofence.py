"""
Tests for server-side geofence evaluation on check-in.

`geofence_pass` was previously read straight off the request body, so a caller
could assert "I was inside the geofence" from anywhere. It is now derived from
the submitted coordinates against the tenant's active zones, and left null when
no coordinates were supplied.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from app.api import deps
from app.db.database import SessionLocal, get_db
from app.db.models.all_models import (
    Organization,
    OrganizationSubscription,
    Payslip,
    Role,
    SubscriptionPlan,
    User,
)


VALID_PASSWORD = "Str0ng-Passphrase!42"


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def org(db):
    row = Organization(
        name=f"Geo Org {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-GEO-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "enterprise").first()
    db.add(OrganizationSubscription(
        organization_id=row.id,
        subscription_plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
    ))
    db.commit()
    return row


@pytest.fixture
def employee(db, org):
    role = db.query(Role).filter(Role.name == "OrgEmployee").first()
    user = User(
        org_id=org.id,
        role_id=role.id,
        full_name="Geo Employee",
        username=f"geo-{uuid.uuid4().hex[:8]}",
        email=f"geo-{uuid.uuid4().hex[:8]}@example.com",
        employee_id=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        hashed_password="x",
        is_active=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def client(db, employee):
    from app.core import rate_limit

    with TestClient(app) as c:
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_active_user] = lambda: employee
        try:
            yield c
        finally:
            app.dependency_overrides.clear()
            rate_limit._fallback_windows.clear()


def _post(client, **body):
    payload = {"image_base64": "aGVsbG8=", "source": "ai", **body}
    return client.post("/api/v1/attendance/check-in", json=payload)


def _log():
    """A minimal shape satisfying AttendanceLogResponse."""
    now = datetime.now(timezone.utc)
    return {
        "id": 1,
        "user_id": 1,
        "user_name": "Geo Employee",
        "user_email": None,
        "check_in": now,
        "check_out": None,
        "break_start": None,
        "break_end": None,
        "status": "present",
        "emotion": None,
        "is_live": 1,
        "recognition_distance": 0.1,
        "source": "ai",
        "created_at": now,
    }


def _patched_controller():
    """Stub the biometric controller so only geofence logic is exercised.

    The stub records the request it was handed so the tests can assert on the
    value the route actually persisted, rather than on a re-derivation.
    """
    controller = MagicMock()
    controller.handle_check_in.side_effect = (
        lambda db, req, current_user, background_tasks: _log()
    )
    return controller


class TestGeofenceIsServerComputed:
    def test_ignores_a_client_claimed_geofence_pass(self, client):
        ctrl = _patched_controller()
        with patch("app.routers.attendance.attendance_controller", ctrl), patch(
            "app.services.workforce_attendance_service.geo_attendance_service.validate_point",
            return_value={"valid": False, "zone_id": None},
        ):
            resp = _post(
                client,
                geofence_pass=1,  # the client lies
                gps_lat=19.0,
                gps_lng=72.0,
            )

        assert resp.status_code == 200, resp.text
        # A point outside every zone must not inherit the client's "I passed".
        assert ctrl.handle_check_in.call_args.kwargs["req"].geofence_pass == 0

    def test_accepts_a_client_claimed_failure(self, client):
        ctrl = _patched_controller()
        with patch("app.routers.attendance.attendance_controller", ctrl), patch(
            "app.services.workforce_attendance_service.geo_attendance_service.validate_point",
            return_value={"valid": True, "zone_id": 1},
        ):
            resp = _post(client, geofence_pass=0, gps_lat=19.0, gps_lng=72.0)

        assert resp.status_code == 200
        # A client cannot downgrade a legitimate on-site punch either.
        assert ctrl.handle_check_in.call_args.kwargs["req"].geofence_pass == 1

    def test_null_when_no_coordinates_supplied(self, client):
        ctrl = _patched_controller()
        with patch("app.routers.attendance.attendance_controller", ctrl), patch(
            "app.services.workforce_attendance_service.geo_attendance_service.validate_point"
        ) as validate:
            resp = _post(client, geofence_pass=1)

        assert resp.status_code == 200
        assert ctrl.handle_check_in.call_args.kwargs["req"].geofence_pass is None
        # No coordinates means there is nothing to validate against.
        validate.assert_not_called()

    def test_null_when_only_one_coordinate_supplied(self, client):
        ctrl = _patched_controller()
        with patch("app.routers.attendance.attendance_controller", ctrl), patch(
            "app.services.workforce_attendance_service.geo_attendance_service.validate_point"
        ) as validate:
            resp = _post(client, geofence_pass=1, gps_lat=19.0)

        assert resp.status_code == 200
        assert ctrl.handle_check_in.call_args.kwargs["req"].geofence_pass is None
        validate.assert_not_called()

    def test_coordinates_are_evaluated_against_the_callers_tenant(self, client, org):
        ctrl = _patched_controller()
        with patch("app.routers.attendance.attendance_controller", ctrl), patch(
            "app.services.workforce_attendance_service.geo_attendance_service.validate_point",
            return_value={"valid": True},
        ) as validate:
            _post(client, gps_lat=19.0, gps_lng=72.0)

        # Cross-tenant zone matching would let one company's zone judge another's punch.
        assert validate.call_args.args[1] == org.id
        assert validate.call_args.args[2:] == (19.0, 72.0)

    def test_records_the_punch_unchecked_when_evaluation_errors(self, client):
        ctrl = _patched_controller()
        with patch("app.routers.attendance.attendance_controller", ctrl), patch(
            "app.services.workforce_attendance_service.geo_attendance_service.validate_point",
            side_effect=RuntimeError("zone table unavailable"),
        ):
            resp = _post(client, geofence_pass=1, gps_lat=19.0, gps_lng=72.0)

        # A geofence outage must not cost the employee their punch.
        assert resp.status_code == 200
        assert ctrl.handle_check_in.call_args.kwargs["req"].geofence_pass is None
