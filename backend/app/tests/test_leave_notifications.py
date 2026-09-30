"""
Tests for durable leave-approver notifications.

The blueprint promises that a submitted leave request reaches the manager for
one-click approval. That path did not exist: the only DB-backed notifier was
dead code called solely from tests, and the notification service it would have
used keeps history in process memory, so nothing survived a restart and nothing
appeared in the in-app feed.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.database import SessionLocal
from app.db.models.all_models import (
    EmploymentRecord,
    LeaveRequest,
    LeaveType,
    Notification,
    Organization,
    Permission,
    Role,
    RolePermission,
    User,
)
from app.services.notification_service import (
    _db_recipients_for_permission,
    notify_leave_approvers,
)


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
        name=f"Notify Org {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-NOTIF-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _user(db, org, role_name, label):
    role = db.query(Role).filter(Role.name == role_name).first()
    assert role is not None, f"seeded role {role_name} required"
    user = User(
        org_id=org.id,
        role_id=role.id,
        full_name=label,
        username=f"nf-{uuid.uuid4().hex[:8]}",
        email=f"nf-{uuid.uuid4().hex[:8]}@example.com",
        employee_id=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        hashed_password="x",
        is_active=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _leave_type(db, org, code="CASUAL"):
    row = LeaveType(
        organization_id=org.id,
        name="Casual Leave",
        code=f"{code}{uuid.uuid4().hex[:4].upper()}",
        is_paid=True,
        max_days_per_year=12,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _request(db, org, user, leave_type):
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    row = LeaveRequest(
        organization_id=org.id,
        user_id=user.id,
        leave_type_id=leave_type.id,
        start_date=start + timedelta(days=1),
        end_date=start + timedelta(days=2),
        total_days=2.0,
        status="pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _notifications_for(db, user_id):
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .all()
    )


class TestPermissionRecipients:
    def test_finds_users_holding_a_permission(self, db, org):
        hr = _user(db, org, "OrgHR", "HR Person")
        _user(db, org, "OrgViewer", "Viewer Person")
        granted = db.query(Permission.id).filter(Permission.name == "leave.approve").first()
        assert granted is not None, "leave.approve must be seeded"

        existing = (
            db.query(RolePermission)
            .filter(RolePermission.permission_id == granted[0])
            .first()
        )
        assert existing is not None

        assert hr.id in _db_recipients_for_permission(db, org.id, "leave.approve")

    def test_no_permission_yields_nobody(self, db, org):
        _user(db, org, "OrgViewer", "Viewer")
        assert _db_recipients_for_permission(db, org.id, "leave.no.such.permission") == []


class TestNotifyLeaveApprovers:
    def test_notifies_users_with_approval_authority(self, db, org):
        requester = _user(db, org, "OrgEmployee", "Requester")
        approver = _user(db, org, "OrgManager", "Approver")
        request = _request(db, org, requester, _leave_type(db, org))

        count = notify_leave_approvers(db, request, actor_id=requester.id)
        db.expire_all()

        assert count >= 1
        assert approver.id in _db_recipients_for_permission(db, org.id, "leave.approve")
        titles = [n.title for n in _notifications_for(db, approver.id)]
        assert any("Requester" in t for t in titles), titles

    def test_never_notifies_the_requester(self, db, org):
        """A requester must not be the approver of their own request."""
        requester = _user(db, org, "OrgHR", "HR Requester")
        request = _request(db, org, requester, _leave_type(db, org))

        notify_leave_approvers(db, request, actor_id=requester.id)
        db.expire_all()

        assert _notifications_for(db, requester.id) == []

    def test_reporting_manager_is_notified(self, db, org):
        requester = _user(db, org, "OrgEmployee", "Report Requester")
        manager = _user(db, org, "OrgEmployee", "The Manager")
        db.add(EmploymentRecord(
            org_id=org.id,
            user_id=requester.id,
            status="ACTIVE",
            reporting_manager_id=manager.id,
        ))
        db.commit()

        request = _request(db, org, requester, _leave_type(db, org))
        notify_leave_approvers(db, request, actor_id=requester.id)
        db.expire_all()

        messages = [n.message for n in _notifications_for(db, manager.id)]
        assert messages, "reporting manager should be notified"
        assert any("Casual Leave" in (m or "") for m in messages)

    def test_notification_links_to_the_request(self, db, org):
        requester = _user(db, org, "OrgEmployee", "Linker")
        manager = _user(db, org, "OrgManager", "Link Manager")
        request = _request(db, org, requester, _leave_type(db, org))

        notify_leave_approvers(db, request, actor_id=requester.id)
        db.expire_all()

        rows = _notifications_for(db, manager.id)
        assert any(r.action_url == f"/leave/requests/{request.id}" for r in rows)
        assert all(r.source_event == "leave.requested" for r in rows)
        assert all(r.is_read is False for r in rows)

    def test_recipient_is_not_notified_twice(self, db, org):
        """A manager who is both the reporting manager and a permission holder
        should receive one notification, not two."""
        requester = _user(db, org, "OrgEmployee", "Dup Requester")
        manager = _user(db, org, "OrgManager", "Dup Manager")
        db.add(EmploymentRecord(
            org_id=org.id,
            user_id=requester.id,
            status="ACTIVE",
            reporting_manager_id=manager.id,
        ))
        db.commit()

        request = _request(db, org, requester, _leave_type(db, org))
        notify_leave_approvers(db, request, actor_id=requester.id)
        db.expire_all()

        rows = [
            r for r in _notifications_for(db, manager.id)
            if r.source_event == "leave.requested"
        ]
        assert len(rows) == 1, f"expected exactly one notification, got {len(rows)}"

    def test_other_tenants_are_never_notified(self, db, org):
        other_org = Organization(
            name=f"Other {uuid.uuid4().hex[:6]}",
            legal_id=f"TEST-NOTIF-{uuid.uuid4().hex[:8].upper()}",
        )
        db.add(other_org)
        db.commit()
        db.refresh(other_org)

        outsider = _user(db, other_org, "OrgManager", "Outsider Manager")
        requester = _user(db, org, "OrgEmployee", "Scoped Requester")
        request = _request(db, org, requester, _leave_type(db, org))

        notify_leave_approvers(db, request, actor_id=requester.id)
        db.expire_all()

        assert _notifications_for(db, outsider.id) == []

    def test_requester_in_another_org_gets_nothing(self, db, org):
        """No approvers in a fresh org means no rows, and no exception."""
        requester = _user(db, org, "OrgEmployee", "Lonely Requester")
        request = _request(db, org, requester, _leave_type(db, org))

        # Strip authority so the recipient set is empty for this org only.
        original = _db_recipients_for_permission
        try:
            import app.services.notification_service as ns

            ns._db_recipients_for_permission = lambda *a, **k: []
            assert notify_leave_approvers(db, request, actor_id=requester.id) == 0
        finally:
            import app.services.notification_service as ns

            ns._db_recipients_for_permission = original
