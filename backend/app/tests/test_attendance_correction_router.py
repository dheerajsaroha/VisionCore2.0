"""
Router-level tests for /attendance-corrections endpoints.

Strategy
--------
* `app.dependency_overrides[get_db]`               → MagicMock session
* `app.dependency_overrides[get_current_active_user]` → DummyUser fixture

Because `require_permission(_dependency)` internally calls
  `Depends(get_current_active_user)` and `Depends(get_db)`
overriding both propagates into every permission closure without touching
production code at all.

Permission gate: give the DummyUser a `role.permissions` list that contains
the required permission string — `_dependency` short-circuits on the JSON
list check and returns `current_user` immediately.

Service: patched via `unittest.mock.patch` on the module-level singleton.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import types

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_active_user
from app.api.deps import get_db as deps_get_db
from app.db.database import get_db as router_get_db
from main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Role:
    def __init__(self, name: str, permissions: list[str], role_id: int = 1):
        self.name = name
        self.permissions = permissions
        self.id = role_id


class _User:
    def __init__(self, user_id: int, org_id: uuid.UUID, role_name: str, perms: list[str]):
        self.id = user_id
        self.org_id = org_id
        self.role_id = 1
        self.role = _Role(role_name, perms)
        self.is_active = True


def _make_db(permissions_map=None) -> MagicMock:
    """Return a plain MagicMock whose query/filter/all/first chain safely.

    Must NOT use spec or spec_set — those cause SQLAlchemy to treat the mock
    as a real Session (binding Query to it), which triggers real DB connections.
    
    Args:
        permissions_map: Dict mapping permission names to bool indicating if the permission exists in RolePermission table
    """
    if permissions_map is None:
        permissions_map = {}
    
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.filter_by.return_value = q
    q.options.return_value = q
    q.join.return_value = q
    q.first.return_value = None
    q.all.return_value = []
    db.query.return_value = q
    
    # Override query to handle Permission and RolePermission models
    original_query = db.query
    def query_side_effect(model):
        name = getattr(model, '__name__', '')
        if name == 'Permission':
            # Return a mock query that returns a permission object for any name in permissions_map
            perm_q = MagicMock()
            perm_q.filter.return_value = perm_q
            perm_q.filter_by.return_value = perm_q
            perm_q.join.return_value = perm_q
            def perm_first():
                # Check if any permission in permissions_map is active
                # The query uses Permission.name.in_(perm_list) so we just need one match
                for perm_name in permissions_map:
                    if permissions_map[perm_name]:
                        return types.SimpleNamespace(id=1, is_active=True)
                return None
            perm_q.first = perm_first
            return perm_q
        elif name == 'RolePermission':
            # Return a mock query that returns a RolePermission for permissions in permissions_map
            rp_q = MagicMock()
            rp_q.filter.return_value = rp_q
            rp_q.filter_by.return_value = rp_q
            rp_q.join.return_value = rp_q
            def rp_first():
                for perm_name in permissions_map:
                    if permissions_map[perm_name]:
                        return types.SimpleNamespace(id=1)
                return None
            rp_q.first = rp_first
            return rp_q
        return original_query(model)
    db.query.side_effect = query_side_effect
    return db


BASE = "/api/v1/attendance-corrections"
_SVC = "app.routers.attendance_correction.attendance_correction_service"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_overrides():
    """Guarantee overrides are cleared after every test."""
    yield
    app.dependency_overrides.clear()


def _override(user: _User) -> MagicMock:
    """Install dependency overrides and return the mock DB.

    Must override BOTH get_db variants:
    - router_get_db  : used by Depends(get_db) in each route handler
    - deps_get_db    : used by Depends(get_db) inside require_permission._dependency
    """
    # Create permissions_map from user's role.permissions
    permissions_map = {p: True for p in (user.role.permissions if user.role and user.role.permissions else [])}
    db = _make_db(permissions_map)
    app.dependency_overrides[router_get_db] = lambda: db
    app.dependency_overrides[deps_get_db] = lambda: db
    app.dependency_overrides[get_current_active_user] = lambda: user
    return db


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


# Reusable org id
ORG = uuid.uuid4()

# Users with appropriate permissions
EMPLOYEE    = _User(42, ORG, "Employee", ["attendance_correction:create",
                                           "attendance_correction:view_own"])
MANAGER     = _User(99, ORG, "Manager",  ["attendance_correction:approve",
                                           "attendance_correction:reject",
                                           "attendance_correction:view_own"])
ADMIN_USER  = _User(7,  ORG, "Admin",    ["attendance_correction:override",
                                           "attendance_correction:approve",
                                           "attendance_correction:view_own"])
NO_PERMS    = _User(55, ORG, "Employee", [])


# ---------------------------------------------------------------------------
# Auth / permission guard tests (no service calls needed)
# ---------------------------------------------------------------------------

def test_unauthenticated_returns_401(client):
    """No override installed → real auth dependency rejects request."""
    r = client.post(BASE, json={})
    assert r.status_code == 401


def test_no_permission_returns_403(client):
    _override(NO_PERMS)
    r = client.post(BASE, json={}, headers={"Authorization": "Bearer x"})
    assert r.status_code == 403


def test_no_permission_approve_returns_403(client):
    _override(NO_PERMS)
    r = client.post(f"{BASE}/10/approve", json={}, headers={"Authorization": "Bearer x"})
    assert r.status_code == 403


def test_no_permission_reject_returns_403(client):
    _override(NO_PERMS)
    r = client.post(f"{BASE}/10/reject", json={}, headers={"Authorization": "Bearer x"})
    assert r.status_code == 403


def test_no_permission_override_returns_403(client):
    _override(NO_PERMS)
    r = client.post(f"{BASE}/10/override",
                    json={"override_reason": "x"},
                    headers={"Authorization": "Bearer x"})
    assert r.status_code == 403


def test_no_permission_pending_returns_403(client):
    _override(NO_PERMS)
    r = client.get(f"{BASE}/pending", headers={"Authorization": "Bearer x"})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /  — submit correction
# ---------------------------------------------------------------------------

@patch(_SVC)
def test_submit_happy_path(mock_svc, client):
    _override(EMPLOYEE)
    from app.db.models.all_models import AttendanceRequest
    stub = AttendanceRequest(
        id=100, org_id=ORG, employee_user_id=42,
        attendance_log_id=1, status="pending",
        submitted_at=datetime.now(timezone.utc),
    )
    mock_svc.submit_request.return_value = stub

    r = client.post(BASE, json={"attendance_log_id": 1, "request_payload": {"reason": "x"}})
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 100
    assert body["status"] == "pending"
    mock_svc.submit_request.assert_called_once()


@patch(_SVC)
def test_submit_duplicate_returns_409(mock_svc, client):
    _override(EMPLOYEE)
    from app.services.attendance_correction_service import DuplicatePendingRequestError
    mock_svc.submit_request.side_effect = DuplicatePendingRequestError("duplicate")
    r = client.post(BASE, json={})
    assert r.status_code == 409
    assert "duplicate" in r.json()["detail"]


# ---------------------------------------------------------------------------
# GET /my
# ---------------------------------------------------------------------------

@patch(_SVC)
def test_list_my_requests(mock_svc, client):
    _override(EMPLOYEE)
    from app.db.models.all_models import AttendanceRequest
    mock_svc.list_employee_requests.return_value = [
        AttendanceRequest(id=1, org_id=ORG, employee_user_id=42,
                          status="pending", submitted_at=datetime.now(timezone.utc))
    ]
    r = client.get(f"{BASE}/my")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["requests"][0]["id"] == 1
    mock_svc.list_employee_requests.assert_called_once()


# ---------------------------------------------------------------------------
# GET /pending  (STATIC path — must not be swallowed by /{request_id})
# ---------------------------------------------------------------------------

@patch(_SVC)
def test_list_pending_requests(mock_svc, client):
    _override(MANAGER)
    from app.db.models.all_models import AttendanceRequest
    mock_svc.list_pending_requests.return_value = [
        AttendanceRequest(id=5, org_id=ORG, employee_user_id=42,
                          status="pending", submitted_at=datetime.now(timezone.utc))
    ]
    r = client.get(f"{BASE}/pending")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["requests"][0]["id"] == 5
    mock_svc.list_pending_requests.assert_called_once()


# ---------------------------------------------------------------------------
# GET /{request_id}
# ---------------------------------------------------------------------------

@patch(_SVC)
def test_get_single_own_request(mock_svc, client):
    _override(EMPLOYEE)
    from app.db.models.all_models import AttendanceRequest
    stub = AttendanceRequest(
        id=200, org_id=ORG, employee_user_id=42,
        status="pending", submitted_at=datetime.now(timezone.utc),
    )
    mock_svc.get_request.return_value = stub
    r = client.get(f"{BASE}/200")
    assert r.status_code == 200
    assert r.json()["id"] == 200


@patch(_SVC)
def test_get_single_request_not_found_returns_404(mock_svc, client):
    _override(EMPLOYEE)
    from app.services.attendance_correction_service import RequestNotFoundError
    mock_svc.get_request.side_effect = RequestNotFoundError("not found")
    r = client.get(f"{BASE}/999")
    assert r.status_code == 404


@patch(_SVC)
def test_get_single_cross_tenant_returns_403(mock_svc, client):
    _override(EMPLOYEE)
    from app.services.attendance_correction_service import CrossTenantAccessError
    mock_svc.get_request.side_effect = CrossTenantAccessError("tenant mismatch")
    r = client.get(f"{BASE}/500")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /{request_id}  — cancel own request
# ---------------------------------------------------------------------------

@patch(_SVC)
def test_cancel_own_request(mock_svc, client):
    _override(EMPLOYEE)
    from app.db.models.all_models import AttendanceRequest
    pending = AttendanceRequest(id=100, org_id=ORG, employee_user_id=42, status="pending")
    cancelled = AttendanceRequest(
        id=100, org_id=ORG, employee_user_id=42,
        status="cancelled", submitted_at=datetime.now(timezone.utc),
        cancelled_at=datetime.now(timezone.utc),
    )
    mock_svc.get_request.return_value = pending
    mock_svc.cancel_request.return_value = cancelled
    r = client.delete(f"{BASE}/100")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    mock_svc.cancel_request.assert_called_once()


@patch(_SVC)
def test_cancel_other_employee_request_returns_403(mock_svc, client):
    _override(EMPLOYEE)
    from app.db.models.all_models import AttendanceRequest
    # Request belongs to employee 99, not 42
    other = AttendanceRequest(id=100, org_id=ORG, employee_user_id=99, status="pending")
    mock_svc.get_request.return_value = other
    r = client.delete(f"{BASE}/100")
    assert r.status_code == 403


@patch(_SVC)
def test_cancel_invalid_transition_returns_400(mock_svc, client):
    _override(EMPLOYEE)
    from app.db.models.all_models import AttendanceRequest
    from app.services.attendance_correction_service import InvalidWorkflowTransitionError
    approved = AttendanceRequest(id=100, org_id=ORG, employee_user_id=42, status="approved")
    mock_svc.get_request.return_value = approved
    mock_svc.cancel_request.side_effect = InvalidWorkflowTransitionError("bad transition")
    r = client.delete(f"{BASE}/100")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /{request_id}/approve
# ---------------------------------------------------------------------------

@patch(_SVC)
def test_approve_happy_path(mock_svc, client):
    _override(MANAGER)
    from app.db.models.all_models import AttendanceApproval
    stub = AttendanceApproval(
        id=7, attendance_request_id=100, org_id=ORG,
        approver_user_id=99, approval_status="approved",
        decided_at=datetime.now(timezone.utc),
    )
    mock_svc.approve_request.return_value = stub
    r = client.post(f"{BASE}/100/approve", json={"decision_notes": "ok"})
    assert r.status_code == 200
    assert r.json()["approval_status"] == "approved"
    mock_svc.approve_request.assert_called_once()


@patch(_SVC)
def test_approve_already_approved_returns_400(mock_svc, client):
    _override(MANAGER)
    from app.services.attendance_correction_service import InvalidWorkflowTransitionError
    mock_svc.approve_request.side_effect = InvalidWorkflowTransitionError("already approved")
    r = client.post(f"{BASE}/100/approve", json={})
    assert r.status_code == 400
    assert "already approved" in r.json()["detail"]


# ---------------------------------------------------------------------------
# POST /{request_id}/reject
# ---------------------------------------------------------------------------

@patch(_SVC)
def test_reject_happy_path(mock_svc, client):
    _override(MANAGER)
    from app.db.models.all_models import AttendanceApproval
    stub = AttendanceApproval(
        id=8, attendance_request_id=100, org_id=ORG,
        approver_user_id=99, approval_status="rejected",
        decided_at=datetime.now(timezone.utc),
    )
    mock_svc.reject_request.return_value = stub
    r = client.post(f"{BASE}/100/reject", json={"decision_notes": "no"})
    assert r.status_code == 200
    assert r.json()["approval_status"] == "rejected"
    mock_svc.reject_request.assert_called_once()


@patch(_SVC)
def test_reject_cancelled_request_returns_400(mock_svc, client):
    _override(MANAGER)
    from app.services.attendance_correction_service import InvalidWorkflowTransitionError
    mock_svc.reject_request.side_effect = InvalidWorkflowTransitionError("already cancelled")
    r = client.post(f"{BASE}/100/reject", json={})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /{request_id}/override
# ---------------------------------------------------------------------------

@patch(_SVC)
def test_override_happy_path(mock_svc, client):
    _override(ADMIN_USER)
    from app.db.models.all_models import AttendanceApproval
    stub = AttendanceApproval(
        id=9, attendance_request_id=100, org_id=ORG,
        approver_user_id=7, approval_status="overridden",
        override_reason="Policy", decided_at=datetime.now(timezone.utc),
    )
    mock_svc.override_request.return_value = stub
    r = client.post(f"{BASE}/100/override",
                    json={"override_reason": "Policy", "decision_notes": "n"})
    assert r.status_code == 200
    assert r.json()["approval_status"] == "overridden"
    mock_svc.override_request.assert_called_once()


@patch(_SVC)
def test_override_pending_returns_400(mock_svc, client):
    _override(ADMIN_USER)
    from app.services.attendance_correction_service import InvalidWorkflowTransitionError
    mock_svc.override_request.side_effect = InvalidWorkflowTransitionError("pending cannot be overridden")
    r = client.post(f"{BASE}/100/override",
                    json={"override_reason": "force", "decision_notes": ""})
    assert r.status_code == 400


def test_override_missing_reason_returns_422(client):
    _override(ADMIN_USER)
    r = client.post(f"{BASE}/100/override", json={"decision_notes": "x"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /{request_id}/timeline
# ---------------------------------------------------------------------------

@patch(_SVC)
def test_get_timeline_happy_path(mock_svc, client):
    _override(EMPLOYEE)
    from app.db.models.all_models import AttendanceRequest
    from app.repositories.attendance_correction_repo import RequestTimelineItem
    stub_req = AttendanceRequest(id=100, org_id=ORG, employee_user_id=42, status="approved")
    mock_svc.get_request.return_value = stub_req
    mock_svc.get_request_timeline.return_value = [
        RequestTimelineItem(kind="request",  status="pending",  occurred_at=datetime.now(timezone.utc)),
        RequestTimelineItem(kind="approval", status="approved", occurred_at=datetime.now(timezone.utc)),
    ]
    r = client.get(f"{BASE}/100/timeline")
    assert r.status_code == 200
    body = r.json()
    assert len(body["timeline"]) == 2
    assert body["timeline"][0]["kind"] == "request"
    assert body["timeline"][1]["kind"] == "approval"


@patch(_SVC)
def test_timeline_not_found_returns_404(mock_svc, client):
    _override(EMPLOYEE)
    from app.services.attendance_correction_service import RequestNotFoundError
    mock_svc.get_request.side_effect = RequestNotFoundError("not found")
    r = client.get(f"{BASE}/999/timeline")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

@patch(_SVC)
def test_cross_tenant_get_returns_403(mock_svc, client):
    _override(EMPLOYEE)
    from app.services.attendance_correction_service import CrossTenantAccessError
    mock_svc.get_request.side_effect = CrossTenantAccessError("forbidden tenant")
    r = client.get(f"{BASE}/777")
    assert r.status_code == 403
    assert "forbidden tenant" in r.json()["detail"]


@patch(_SVC)
def test_cross_tenant_approve_returns_403(mock_svc, client):
    _override(MANAGER)
    from app.services.attendance_correction_service import CrossTenantAccessError
    mock_svc.approve_request.side_effect = CrossTenantAccessError("wrong org")
    r = client.post(f"{BASE}/777/approve", json={})
    assert r.status_code == 403
