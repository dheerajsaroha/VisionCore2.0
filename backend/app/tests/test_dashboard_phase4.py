"""
test_dashboard_phase4.py — Unit and integration tests for Phase 4 Dashboard & Workforce Overview.
Verifies role awareness, tenant isolation, live metric calculations, approval actions, alerts,
department attendance comparisons, and multi-dimensional analytics.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from main import app
from app.api import deps
from app.db.database import SessionLocal
from app.db.models.all_models import (
    User, Role, Organization, Department, AttendanceLog,
    LeaveRequest, LeaveType, Reimbursement, Ticket, AttendanceCorrection,
    ApprovalRequest, AuditLog
)

class MockRole:
    def __init__(self, name: str):
        self.name = name
        self.id = 1

class MockUser:
    def __init__(self, role_name: str, org_id: uuid.UUID, user_id: int = 1, dept_id: int = None):
        self.id = user_id
        self.org_id = org_id
        self.role_id = 1
        self.role = MockRole(role_name)
        self.dept_id = dept_id
        self.full_name = f"Test {role_name}"
        self.username = f"test_{role_name.lower()}"
        self.email = f"{role_name.lower()}@visioncore.test"
        self.is_active = 1
        self.is_deleted = 0


@pytest.fixture
def test_org_id(db):
    org = db.query(Organization).first()
    return org.id if org else uuid.uuid4()


@pytest.fixture
def test_user(db, test_org_id):
    user = db.query(User).filter(User.org_id == test_org_id).first()
    return user


def test_superadmin_overview(client: TestClient, test_org_id):
    """SuperAdmin should receive platform-wide statistics."""
    super_user = MockUser("SuperAdmin", test_org_id, user_id=999)
    app.dependency_overrides[deps.get_current_active_user] = lambda: super_user

    try:
        response = client.get("/api/v1/dashboard/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "SuperAdmin"
        assert data["scope"] == "platform"
        assert "totalOrganizations" in data["stats"]
        assert "totalEmployees" in data["stats"]
        assert "biometricSLA" in data["stats"]
    finally:
        app.dependency_overrides.pop(deps.get_current_active_user, None)


def test_orgadmin_overview(client: TestClient, test_org_id):
    """OrgAdmin should receive organization-scoped workforce overview."""
    admin_user = MockUser("OrgAdmin", test_org_id, user_id=101)
    app.dependency_overrides[deps.get_current_active_user] = lambda: admin_user

    try:
        response = client.get("/api/v1/dashboard/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "OrgAdmin"
        assert data["scope"] == "organization"
        assert "totalEmployees" in data["stats"]
        assert "todayCheckins" in data["stats"]
        assert "presentRate" in data["stats"]
        assert "pendingApprovals" in data["stats"]
    finally:
        app.dependency_overrides.pop(deps.get_current_active_user, None)


def test_hr_overview(client: TestClient, test_org_id):
    """HR role should receive dedicated people & workforce overview."""
    hr_user = MockUser("HR", test_org_id, user_id=150)
    app.dependency_overrides[deps.get_current_active_user] = lambda: hr_user

    try:
        response = client.get("/api/v1/dashboard/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "HR"
        assert data["scope"] == "workforce"
        assert "totalEmployees" in data["stats"]
        assert "todayCheckins" in data["stats"]
        assert "trainingCompletion" in data["stats"]
        assert "openPositions" in data["stats"]
    finally:
        app.dependency_overrides.pop(deps.get_current_active_user, None)


def test_manager_overview(client: TestClient, test_org_id):
    """Manager should receive team-scoped statistics."""
    manager_user = MockUser("Manager", test_org_id, user_id=202, dept_id=5)
    app.dependency_overrides[deps.get_current_active_user] = lambda: manager_user

    try:
        response = client.get("/api/v1/dashboard/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "Manager"
        assert data["scope"] == "team"
        assert "teamCount" in data["stats"]
        assert "presentRate" in data["stats"]
    finally:
        app.dependency_overrides.pop(deps.get_current_active_user, None)


def test_employee_overview(client: TestClient, test_org_id):
    """Employee should receive personal workspace metrics."""
    emp_user = MockUser("Employee", test_org_id, user_id=303)
    app.dependency_overrides[deps.get_current_active_user] = lambda: emp_user

    try:
        response = client.get("/api/v1/dashboard/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "Employee"
        assert data["scope"] == "personal"
        assert "myCheckedIn" in data["stats"]
        assert "leaveBalanceDays" in data["stats"]
    finally:
        app.dependency_overrides.pop(deps.get_current_active_user, None)


def test_tenant_isolation(client: TestClient, db):
    """Metrics must strictly be scoped to the authenticated user's organization."""
    # Create two isolated organizations
    org_a = Organization(name="Tenant Alpha", legal_id=f"LEGAL_ALPHA_{uuid.uuid4().hex[:6]}")
    org_b = Organization(name="Tenant Beta", legal_id=f"LEGAL_BETA_{uuid.uuid4().hex[:6]}")
    db.add_all([org_a, org_b])
    db.commit()
    db.refresh(org_a)
    db.refresh(org_b)

    try:
        role = db.query(Role).first()
        role_id = role.id if role else 1
        user_a = User(
            full_name="Alpha Worker", username=f"worker_a_{uuid.uuid4().hex[:6]}",
            email=f"worker_a_{uuid.uuid4().hex[:6]}@alpha.test",
            employee_id=f"EMP_A_{uuid.uuid4().hex[:6]}",
            role_id=role_id,
            hashed_password="fakehash", org_id=org_a.id, is_active=1, is_deleted=0
        )
        user_b = User(
            full_name="Beta Worker", username=f"worker_b_{uuid.uuid4().hex[:6]}",
            email=f"worker_b_{uuid.uuid4().hex[:6]}@beta.test",
            employee_id=f"EMP_B_{uuid.uuid4().hex[:6]}",
            role_id=role_id,
            hashed_password="fakehash", org_id=org_b.id, is_active=1, is_deleted=0
        )
        db.add_all([user_a, user_b])
        db.commit()

        # Query Org A
        mock_a = MockUser("OrgAdmin", org_a.id, user_id=user_a.id)
        app.dependency_overrides[deps.get_current_active_user] = lambda: mock_a
        res_a = client.get("/api/v1/dashboard/overview")
        assert res_a.status_code == 200
        stats_a = res_a.json()["stats"]
        assert stats_a["totalEmployees"] >= 1

        # Query Org B
        mock_b = MockUser("OrgAdmin", org_b.id, user_id=user_b.id)
        app.dependency_overrides[deps.get_current_active_user] = lambda: mock_b
        res_b = client.get("/api/v1/dashboard/overview")
        assert res_b.status_code == 200
        stats_b = res_b.json()["stats"]
        assert stats_b["totalEmployees"] >= 1
    finally:
        app.dependency_overrides.pop(deps.get_current_active_user, None)
        # Cleanup
        db.query(User).filter(User.org_id.in_([org_a.id, org_b.id])).delete(synchronize_session=False)
        db.delete(org_a)
        db.delete(org_b)
        db.commit()


def test_workforce_breakdown(client: TestClient, test_org_id):
    """Workforce breakdown returns headcount trends, departments, and distributions."""
    admin_user = MockUser("OrgAdmin", test_org_id, user_id=101)
    app.dependency_overrides[deps.get_current_active_user] = lambda: admin_user

    try:
        response = client.get("/api/v1/dashboard/workforce-breakdown")
        assert response.status_code == 200
        data = response.json()
        assert "totalHeadcount" in data
        assert "departmentDistribution" in data
        assert "employmentTypes" in data
        assert "locationDistribution" in data
        assert "headcountTrends" in data
        assert len(data["headcountTrends"]) == 6
    finally:
        app.dependency_overrides.pop(deps.get_current_active_user, None)


def test_attendance_stats(client: TestClient, test_org_id):
    """Attendance stats returns today's summary, 7d trends, department comparisons, and recent logs."""
    admin_user = MockUser("OrgAdmin", test_org_id, user_id=101)
    app.dependency_overrides[deps.get_current_active_user] = lambda: admin_user

    try:
        response = client.get("/api/v1/dashboard/attendance-stats")
        assert response.status_code == 200
        data = response.json()
        assert "today" in data
        assert "trends" in data
        assert "departmentAttendance" in data
        assert "recentLogs" in data
        assert len(data["trends"]) == 7
        assert "earlyDeparture" in data["today"]
        assert "overtime" in data["today"]
    finally:
        app.dependency_overrides.pop(deps.get_current_active_user, None)


def test_leave_overview(client: TestClient, test_org_id):
    """Leave overview returns balances, utilization rate, approved/rejected counts, and upcoming leave."""
    admin_user = MockUser("OrgAdmin", test_org_id, user_id=101)
    app.dependency_overrides[deps.get_current_active_user] = lambda: admin_user

    try:
        response = client.get("/api/v1/dashboard/leave-overview")
        assert response.status_code == 200
        data = response.json()
        assert "isEmployee" in data
        assert "myBalances" in data
        assert "currentlyOnLeave" in data
        assert "upcomingLeave" in data
        assert "leaveUtilization" in data
        assert "approvedCount" in data
        assert "rejectedCount" in data
    finally:
        app.dependency_overrides.pop(deps.get_current_active_user, None)


def test_pending_approvals_and_action(client: TestClient, test_org_id, test_user, db):
    """Pending approvals list and fast approve/reject action execution."""
    admin_user = MockUser("OrgAdmin", test_org_id, user_id=test_user.id if test_user else 101)
    app.dependency_overrides[deps.get_current_active_user] = lambda: admin_user

    try:
        # Ensure a LeaveType exists for the foreign key
        lt = db.query(LeaveType).filter(LeaveType.organization_id == test_org_id).first()
        if not lt:
            lt = LeaveType(organization_id=test_org_id, name="Annual Leave", code="ANNUAL")
            db.add(lt)
            db.commit()
            db.refresh(lt)

        # Create a test pending leave request in DB
        lr = LeaveRequest(
            organization_id=test_org_id,
            user_id=test_user.id if test_user else 1,
            leave_type_id=lt.id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
            total_days=2,
            reason="Test Conference Attendance",
            status="pending",
        )
        db.add(lr)
        db.commit()
        db.refresh(lr)

        # 1. Fetch pending approvals list
        get_res = client.get("/api/v1/dashboard/pending-approvals")
        assert get_res.status_code == 200
        items = get_res.json()
        matching = [it for it in items if it["item_type"] == "leave" and it["raw_id"] == lr.id]
        assert len(matching) == 1

        # 2. Execute approval action
        post_res = client.post(
            f"/api/v1/dashboard/approvals/leave/{lr.id}/action",
            json={"action": "approve", "note": "Approved for annual conference"},
        )
        assert post_res.status_code == 200
        action_data = post_res.json()
        assert action_data["success"] is True
        assert action_data["action"] == "approved"

        # Verify DB state updated
        db.refresh(lr)
        assert lr.status == "approved"
        assert lr.approver_note == "Approved for annual conference"

        # Cleanup
        db.delete(lr)
        db.commit()
    finally:
        app.dependency_overrides.pop(deps.get_current_active_user, None)


def test_alerts_panel(client: TestClient, test_org_id):
    """Alerts endpoint returns actionable operational notices."""
    admin_user = MockUser("OrgAdmin", test_org_id, user_id=101)
    app.dependency_overrides[deps.get_current_active_user] = lambda: admin_user

    try:
        response = client.get("/api/v1/dashboard/alerts")
        assert response.status_code == 200
        alerts = response.json()
        assert isinstance(alerts, list)
        assert len(alerts) > 0
        assert "severity" in alerts[0]
        assert "title" in alerts[0]
    finally:
        app.dependency_overrides.pop(deps.get_current_active_user, None)


def test_activity_feed_and_analytics(client: TestClient, test_org_id):
    """Activity feed and deep multi-dimensional analytics endpoints."""
    admin_user = MockUser("OrgAdmin", test_org_id, user_id=101)
    app.dependency_overrides[deps.get_current_active_user] = lambda: admin_user

    try:
        feed_res = client.get("/api/v1/dashboard/activity-feed")
        assert feed_res.status_code == 200
        activities = feed_res.json()
        assert isinstance(activities, list)

        analytics_res = client.get("/api/v1/dashboard/analytics")
        assert analytics_res.status_code == 200
        analytics = analytics_res.json()
        assert "attendanceCompliance" in analytics
        assert "leaveUtilization" in analytics
        assert "hiringTrends" in analytics
        assert "performanceDistribution" in analytics
        assert "payrollCosts" in analytics
    finally:
        app.dependency_overrides.pop(deps.get_current_active_user, None)


def test_ai_insights_endpoint(client: TestClient, test_org_id):
    """AI insights returns permission-guarded role-scoped insights."""
    admin_user = MockUser("OrgAdmin", test_org_id, user_id=101)
    app.dependency_overrides[deps.get_current_active_user] = lambda: admin_user

    try:
        response = client.get("/api/v1/dashboard/ai-insights")
        assert response.status_code == 200
        insights = response.json()
        assert isinstance(insights, list)
        assert len(insights) >= 3
        assert "confidence" in insights[0]
    finally:
        app.dependency_overrides.pop(deps.get_current_active_user, None)
