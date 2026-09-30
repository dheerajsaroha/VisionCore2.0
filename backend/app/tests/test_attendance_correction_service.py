from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.db.models.all_models import AttendanceApproval, AttendanceLog, AttendanceRequest, User
from app.repositories.attendance_correction_repo import RequestTimelineItem
from app.services.attendance_correction_service import (
    AttendanceCorrectionService,
    CrossTenantAccessError,
    DuplicatePendingRequestError,
    InvalidWorkflowTransitionError,
    RequestNotFoundError,
    ValidationError,
)


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return AttendanceCorrectionService(repository=mock_repo)


@pytest.fixture
def mock_db():
    db = MagicMock(spec=Session)
    db.in_transaction.return_value = False
    return db


# ---------------------------------------------------------------------------
# submit_request() tests
# ---------------------------------------------------------------------------

def test_submit_request_success(service, mock_repo, mock_db):
    org_id = uuid.uuid4()
    employee_id = 42

    # Mock employee User
    employee = User(id=employee_id, org_id=org_id, is_deleted=0)

    # Mock attendance log
    log_id = 101
    attendance_user = User(id=employee_id, org_id=org_id, is_deleted=0)
    attendance_log = AttendanceLog(id=log_id, user_id=employee_id, is_deleted=0)
    attendance_log.user = attendance_user

    # Setup database query mock
    def mock_query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        if model == User:
            q.first.return_value = employee
        elif model == AttendanceLog:
            q.first.return_value = attendance_log
        elif model == AttendanceRequest:
            # No duplicate pending request exists
            q.first.return_value = None
        return q

    mock_db.query.side_effect = mock_query_fn

    # Mock repository create
    expected_request = AttendanceRequest(
        id=500,
        org_id=org_id,
        employee_user_id=employee_id,
        attendance_log_id=log_id,
        status="pending",
    )
    mock_repo.create_request.return_value = expected_request

    # Call service and assert
    with patch("app.services.attendance_correction_service.AuditService") as mock_audit_cls:
        audit_service_instance = MagicMock()
        mock_audit_cls.return_value = audit_service_instance

        res = service.submit_request(
            mock_db,
            org_id=org_id,
            employee_user_id=employee_id,
            attendance_log_id=log_id,
            request_payload={"reason": "Forgot to check-in"},
        )

        assert res == expected_request
        mock_repo.create_request.assert_called_once_with(
            mock_db,
            org_id=org_id,
            employee_user_id=employee_id,
            attendance_log_id=log_id,
            request_payload={"reason": "Forgot to check-in"},
        )
        audit_service_instance.log_create.assert_called_once()


def test_submit_request_employee_not_found(service, mock_db):
    org_id = uuid.uuid4()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(ValidationError, match="User with ID 42 not found"):
        service.submit_request(mock_db, org_id=org_id, employee_user_id=42, attendance_log_id=None, request_payload=None)


def test_submit_request_employee_tenant_mismatch(service, mock_db):
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    employee = User(id=42, org_id=other_org_id, is_deleted=0)

    mock_db.query.return_value.filter.return_value.first.return_value = employee

    with pytest.raises(CrossTenantAccessError, match="User does not belong to the specified tenant"):
        service.submit_request(mock_db, org_id=org_id, employee_user_id=42, attendance_log_id=None, request_payload=None)


def test_submit_request_attendance_log_not_found(service, mock_db):
    org_id = uuid.uuid4()
    employee = User(id=42, org_id=org_id, is_deleted=0)

    def mock_query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        if model == User:
            q.first.return_value = employee
        elif model == AttendanceLog:
            q.first.return_value = None
        return q

    mock_db.query.side_effect = mock_query_fn

    with pytest.raises(ValidationError, match="Attendance log with ID 999 not found"):
        service.submit_request(mock_db, org_id=org_id, employee_user_id=42, attendance_log_id=999, request_payload=None)


def test_submit_request_attendance_log_belongs_to_other_employee(service, mock_db):
    org_id = uuid.uuid4()
    employee = User(id=42, org_id=org_id, is_deleted=0)
    attendance_log = AttendanceLog(id=101, user_id=99, is_deleted=0) # belongs to employee 99

    def mock_query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        if model == User:
            q.first.return_value = employee
        elif model == AttendanceLog:
            q.first.return_value = attendance_log
        return q

    mock_db.query.side_effect = mock_query_fn

    with pytest.raises(ValidationError, match="Attendance record does not belong to the specified employee"):
        service.submit_request(mock_db, org_id=org_id, employee_user_id=42, attendance_log_id=101, request_payload=None)


def test_submit_request_attendance_log_tenant_mismatch(service, mock_db):
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    employee = User(id=42, org_id=org_id, is_deleted=0)
    
    # User associated with log belongs to other tenant
    log_user = User(id=42, org_id=other_org_id, is_deleted=0)
    attendance_log = AttendanceLog(id=101, user_id=42, is_deleted=0)
    attendance_log.user = log_user

    def mock_query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        if model == User:
            q.first.return_value = employee
        elif model == AttendanceLog:
            q.first.return_value = attendance_log
        return q

    mock_db.query.side_effect = mock_query_fn

    with pytest.raises(CrossTenantAccessError, match="Attendance record does not belong to this tenant"):
        service.submit_request(mock_db, org_id=org_id, employee_user_id=42, attendance_log_id=101, request_payload=None)


def test_submit_request_duplicate_pending(service, mock_db):
    org_id = uuid.uuid4()
    employee = User(id=42, org_id=org_id, is_deleted=0)
    existing_request = AttendanceRequest(id=5, org_id=org_id, employee_user_id=42, status="pending")

    def mock_query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        if model == User:
            q.first.return_value = employee
        elif model == AttendanceRequest:
            q.first.return_value = existing_request
        return q

    mock_db.query.side_effect = mock_query_fn

    with pytest.raises(DuplicatePendingRequestError, match="A pending correction request already exists"):
        service.submit_request(mock_db, org_id=org_id, employee_user_id=42, attendance_log_id=None, request_payload=None)


# ---------------------------------------------------------------------------
# approve_request() tests
# ---------------------------------------------------------------------------

def test_approve_request_success(service, mock_repo, mock_db):
    org_id = uuid.uuid4()
    request_id = 500
    approver_id = 99

    approver = User(id=approver_id, org_id=org_id, is_deleted=0)
    request = AttendanceRequest(id=request_id, org_id=org_id, status="pending")

    def mock_query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        if model == User:
            q.first.return_value = approver
        elif model == AttendanceRequest:
            q.first.return_value = request
        return q

    mock_db.query.side_effect = mock_query_fn

    # Mock repository approval
    expected_approval = AttendanceApproval(
        id=77,
        attendance_request_id=request_id,
        org_id=org_id,
        approver_user_id=approver_id,
        approval_status="approved",
    )
    mock_repo.approve_request.return_value = expected_approval

    with patch("app.services.attendance_correction_service.AuditService") as mock_audit_cls:
        audit_service_instance = MagicMock()
        mock_audit_cls.return_value = audit_service_instance

        res = service.approve_request(
            mock_db,
            org_id=org_id,
            request_id=request_id,
            approver_user_id=approver_id,
            notes="Approved workflow",
            ip_address="127.0.0.1",
            user_agent="Firefox",
            correlation_id="corr-abc",
        )

        assert res == expected_approval
        assert expected_approval.created_by_ip == "127.0.0.1"
        assert expected_approval.created_by_user_agent == "Firefox"
        assert expected_approval.created_by_correlation_id == "corr-abc"
        mock_repo.approve_request.assert_called_once_with(
            mock_db,
            org_id=org_id,
            request_id=request_id,
            approver_user_id=approver_id,
            decision_notes="Approved workflow",
        )
        audit_service_instance.log_update.assert_called_once()


def test_approve_request_applies_requested_times_to_attendance_log(service, mock_repo, mock_db):
    org_id = uuid.uuid4()
    approver_id = 99
    employee_id = 42
    approver = User(id=approver_id, org_id=org_id, is_deleted=0)
    employee = User(id=employee_id, org_id=org_id, is_deleted=0)
    request = AttendanceRequest(
        id=500,
        org_id=org_id,
        employee_user_id=employee_id,
        attendance_log_id=101,
        request_payload={
            "requested_clock_in": "2026-09-26T09:15:00+00:00",
            "requested_clock_out": "2026-09-26T17:30:00+00:00",
            "reason": "Forgot to clock in",
        },
        status="pending",
    )
    attendance_log = AttendanceLog(
        id=101,
        user_id=employee_id,
        is_deleted=0,
        check_in=datetime(2026, 9, 26, 9, 0, tzinfo=timezone.utc),
        status="late",
    )
    attendance_log.user = employee

    def mock_query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        if model == User:
            q.first.return_value = approver
        elif model == AttendanceRequest:
            q.first.return_value = request
        elif model == AttendanceLog:
            q.first.return_value = attendance_log
        return q

    mock_db.query.side_effect = mock_query_fn
    mock_repo.approve_request.return_value = AttendanceApproval(
        id=77,
        attendance_request_id=500,
        org_id=org_id,
        approver_user_id=approver_id,
        approval_status="approved",
    )

    with patch("app.services.attendance_correction_service.AuditService"):
        service.approve_request(
            mock_db,
            org_id=org_id,
            request_id=500,
            approver_user_id=approver_id,
        )

    assert attendance_log.check_in == datetime(2026, 9, 26, 9, 15, tzinfo=timezone.utc)
    assert attendance_log.check_out == datetime(2026, 9, 26, 17, 30, tzinfo=timezone.utc)
    assert attendance_log.status == "manual_override"


def test_approve_request_not_found(service, mock_db):
    org_id = uuid.uuid4()
    approver = User(id=99, org_id=org_id, is_deleted=0)

    def mock_query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        if model == User:
            q.first.return_value = approver
        elif model == AttendanceRequest:
            q.first.return_value = None
        return q

    mock_db.query.side_effect = mock_query_fn

    with pytest.raises(RequestNotFoundError, match="Attendance request with ID 500 not found"):
        service.approve_request(mock_db, org_id=org_id, request_id=500, approver_user_id=99)


def test_approve_request_tenant_mismatch(service, mock_db):
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    approver = User(id=99, org_id=org_id, is_deleted=0)
    request = AttendanceRequest(id=500, org_id=other_org_id, status="pending")

    def mock_query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        if model == User:
            q.first.return_value = approver
        elif model == AttendanceRequest:
            q.first.return_value = request
        return q

    mock_db.query.side_effect = mock_query_fn

    with pytest.raises(CrossTenantAccessError, match="Access to this attendance request is forbidden"):
        service.approve_request(mock_db, org_id=org_id, request_id=500, approver_user_id=99)


def test_approve_request_invalid_transition(service, mock_db):
    org_id = uuid.uuid4()
    approver = User(id=99, org_id=org_id, is_deleted=0)
    request = AttendanceRequest(id=500, org_id=org_id, status="approved") # already approved

    def mock_query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        if model == User:
            q.first.return_value = approver
        elif model == AttendanceRequest:
            q.first.return_value = request
        return q

    mock_db.query.side_effect = mock_query_fn

    with pytest.raises(InvalidWorkflowTransitionError, match="Invalid workflow transition"):
        service.approve_request(mock_db, org_id=org_id, request_id=500, approver_user_id=99)


# ---------------------------------------------------------------------------
# reject_request() tests
# ---------------------------------------------------------------------------

def test_reject_request_success(service, mock_repo, mock_db):
    org_id = uuid.uuid4()
    request_id = 500
    approver_id = 99

    approver = User(id=approver_id, org_id=org_id, is_deleted=0)
    request = AttendanceRequest(id=request_id, org_id=org_id, status="pending")

    def mock_query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        if model == User:
            q.first.return_value = approver
        elif model == AttendanceRequest:
            q.first.return_value = request
        return q

    mock_db.query.side_effect = mock_query_fn

    expected_rejection = AttendanceApproval(
        id=78,
        attendance_request_id=request_id,
        org_id=org_id,
        approver_user_id=approver_id,
        approval_status="rejected",
    )
    mock_repo.reject_request.return_value = expected_rejection

    with patch("app.services.attendance_correction_service.AuditService") as mock_audit_cls:
        audit_service_instance = MagicMock()
        mock_audit_cls.return_value = audit_service_instance

        res = service.reject_request(
            mock_db,
            org_id=org_id,
            request_id=request_id,
            approver_user_id=approver_id,
            notes="Rejected workflow",
        )

        assert res == expected_rejection
        mock_repo.reject_request.assert_called_once_with(
            mock_db,
            org_id=org_id,
            request_id=request_id,
            approver_user_id=approver_id,
            decision_notes="Rejected workflow",
        )
        audit_service_instance.log_update.assert_called_once()


# ---------------------------------------------------------------------------
# override_request() tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("initial_status", ["approved", "rejected"])
def test_override_request_success(service, mock_repo, mock_db, initial_status):
    org_id = uuid.uuid4()
    request_id = 500
    approver_id = 99

    approver = User(id=approver_id, org_id=org_id, is_deleted=0)
    request = AttendanceRequest(id=request_id, org_id=org_id, status=initial_status)

    def mock_query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        if model == User:
            q.first.return_value = approver
        elif model == AttendanceRequest:
            q.first.return_value = request
        return q

    mock_db.query.side_effect = mock_query_fn

    expected_override = AttendanceApproval(
        id=79,
        attendance_request_id=request_id,
        org_id=org_id,
        approver_user_id=approver_id,
        approval_status="overridden",
        override_reason="Admin override",
    )
    mock_repo.override_request.return_value = expected_override

    with patch("app.services.attendance_correction_service.AuditService") as mock_audit_cls:
        audit_service_instance = MagicMock()
        mock_audit_cls.return_value = audit_service_instance

        res = service.override_request(
            mock_db,
            org_id=org_id,
            request_id=request_id,
            approver_user_id=approver_id,
            override_reason="Admin override",
            notes="Notes on override",
        )

        assert res == expected_override
        mock_repo.override_request.assert_called_once_with(
            mock_db,
            org_id=org_id,
            request_id=request_id,
            approver_user_id=approver_id,
            decision_notes="Notes on override",
            override_reason="Admin override",
        )
        audit_service_instance.log_update.assert_called_once()


def test_override_request_requires_reason(service, mock_db):
    with pytest.raises(ValidationError, match="Override reason is required"):
        service.override_request(mock_db, org_id=uuid.uuid4(), request_id=500, approver_user_id=99, override_reason="")


def test_override_request_invalid_transition(service, mock_db):
    org_id = uuid.uuid4()
    approver = User(id=99, org_id=org_id, is_deleted=0)
    request = AttendanceRequest(id=500, org_id=org_id, status="pending") # cannot override pending request

    def mock_query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        if model == User:
            q.first.return_value = approver
        elif model == AttendanceRequest:
            q.first.return_value = request
        return q

    mock_db.query.side_effect = mock_query_fn

    with pytest.raises(InvalidWorkflowTransitionError, match="Invalid workflow transition"):
        service.override_request(mock_db, org_id=org_id, request_id=500, approver_user_id=99, override_reason="Override")


# ---------------------------------------------------------------------------
# cancel_request() tests
# ---------------------------------------------------------------------------

def test_cancel_request_success(service, mock_repo, mock_db):
    org_id = uuid.uuid4()
    request_id = 500
    employee = User(id=42, org_id=org_id, is_deleted=0)
    request = AttendanceRequest(id=request_id, org_id=org_id, status="pending", employee=employee)

    def mock_query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        if model == AttendanceRequest:
            q.first.return_value = request
        elif model == User:
            q.first.return_value = employee
        return q

    mock_db.query.side_effect = mock_query_fn

    expected_cancelled = AttendanceRequest(
        id=request_id,
        org_id=org_id,
        status="cancelled",
        cancelled_at=datetime.now(timezone.utc),
    )
    mock_repo.cancel_request.return_value = expected_cancelled

    with patch("app.services.attendance_correction_service.AuditService") as mock_audit_cls:
        audit_service_instance = MagicMock()
        mock_audit_cls.return_value = audit_service_instance

        res = service.cancel_request(mock_db, org_id=org_id, request_id=request_id)

        assert res == expected_cancelled
        mock_repo.cancel_request.assert_called_once()
        audit_service_instance.log_update.assert_called_once()


def test_cancel_request_invalid_transition(service, mock_db):
    org_id = uuid.uuid4()
    request = AttendanceRequest(id=500, org_id=org_id, status="approved")

    mock_db.query.return_value.filter.return_value.first.return_value = request

    with pytest.raises(InvalidWorkflowTransitionError, match="Invalid workflow transition"):
        service.cancel_request(mock_db, org_id=org_id, request_id=500)


# ---------------------------------------------------------------------------
# Query & Read methods tests
# ---------------------------------------------------------------------------

def test_get_request_success(service, mock_db):
    org_id = uuid.uuid4()
    request = AttendanceRequest(id=500, org_id=org_id, status="pending")

    mock_db.query.return_value.filter.return_value.first.return_value = request

    res = service.get_request(mock_db, org_id=org_id, request_id=500)
    assert res == request


def test_get_request_timeline(service, mock_repo, mock_db):
    org_id = uuid.uuid4()
    request = AttendanceRequest(id=500, org_id=org_id, status="approved")

    mock_db.query.return_value.filter.return_value.first.return_value = request

    expected_timeline = [
        RequestTimelineItem(kind="request", status="pending", occurred_at=datetime.now(timezone.utc)),
        RequestTimelineItem(kind="approval", status="approved", occurred_at=datetime.now(timezone.utc)),
    ]
    mock_repo.get_request_timeline.return_value = expected_timeline

    res = service.get_request_timeline(mock_db, org_id=org_id, request_id=500)
    assert res == expected_timeline
    mock_repo.get_request_timeline.assert_called_once_with(mock_db, org_id=org_id, request_id=500)


def test_list_pending_requests(service, mock_repo, mock_db):
    org_id = uuid.uuid4()
    expected_list = [AttendanceRequest(id=1, org_id=org_id, status="pending")]
    mock_repo.list_pending_requests.return_value = expected_list

    res = service.list_pending_requests(mock_db, org_id=org_id, limit=10, offset=0)
    assert res == expected_list
    mock_repo.list_pending_requests.assert_called_once_with(mock_db, org_id=org_id, limit=10, offset=0)


def test_list_employee_requests(service, mock_repo, mock_db):
    org_id = uuid.uuid4()
    employee = User(id=42, org_id=org_id, is_deleted=0)
    expected_list = [AttendanceRequest(id=1, org_id=org_id, employee_user_id=42)]

    def mock_query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        if model == User:
            q.first.return_value = employee
        return q

    mock_db.query.side_effect = mock_query_fn
    mock_repo.list_employee_requests.return_value = expected_list

    res = service.list_employee_requests(mock_db, org_id=org_id, employee_user_id=42, limit=5, offset=1)
    assert res == expected_list
    mock_repo.list_employee_requests.assert_called_once_with(
        mock_db, org_id=org_id, employee_user_id=42, limit=5, offset=1
    )
