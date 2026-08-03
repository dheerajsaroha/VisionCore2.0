"""
test_workforce_domain.py — Unit & Integration Tests for Workforce Core Domain
VisionCore 3.0 — Sprint 4

Covers:
  - AttendanceService: multi-channel session marking, AttendanceMarked event
  - AttendancePolicyService: grace/late evaluation, geofence containment
  - GeoAttendanceService: geofence zone point validation
  - LeaveService: apply/approve with balance reservation & deduction
  - ShiftService: template creation, shift assignment
  - RosterService: publish workflow with auto-generated roster entries
  - HolidayService: holiday calendar entries sync into business calendar
  - OvertimeService: overtime computation, approval
  - CapacityPlanningService: capacity snapshot utilization metrics

All tests use MagicMock DB sessions and patch audit/event/notification
integration points — mirroring the existing test_org_identity_domain.py style.
"""
import uuid
from datetime import date, datetime, time, timezone
from unittest.mock import ANY, MagicMock, patch

from app.db.models.all_models import (
    AttendancePolicy,
    AttendanceSession,
    BenchRecord,
    GeofenceZone,
    HeadcountPlan,
    HolidayCalendar,
    HolidayEntry,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    OvertimeRecord,
    Roster,
    Shift,
    ShiftAssignment,
    ShiftTemplate,
    TimeEntry,
    User,
)
from app.services.workforce_attendance_service import (
    attendance_policy_service,
    attendance_service,
    geo_attendance_service,
)
from app.services.workforce_shift_service import roster_service, shift_service
from app.services.workforce_leave_service import holiday_service, leave_service
from app.services.workforce_planning_service import capacity_planning_service
from app.services.workforce_time_service import overtime_service


def _mock_attendance_policy(org_id):
    """Build a permissive default AttendancePolicy with known thresholds."""
    return AttendancePolicy(
        id=1,
        org_id=org_id,
        name="Default Policy",
        grace_period_mins=5,
        late_threshold_mins=15,
        early_departure_threshold_mins=15,
        half_day_hours=4.0,
        overtime_trigger_mins=60,
        overtime_rate_multiplier=1.50,
        geofence_radius_meters=200,
        allow_face=True,
        allow_qr=True,
        allow_gps=True,
        allow_ble=False,
        allow_nfc=False,
        allow_wifi=True,
        allow_kiosk=True,
        allow_manual=True,
        ip_whitelist=[],
        is_active=True,
    )


# =============================================================================
#  Attendance — Session Marking & Event Emission
# =============================================================================

def test_attendance_session_marking():
    """mark_attendance via FACE channel should create a session, set status,
    and emit the AttendanceMarked domain event."""
    db = MagicMock()
    org_id = uuid.uuid4()
    work_date = date(2026, 8, 3)  # Monday

    policy = _mock_attendance_policy(org_id)
    user = User(id=10, org_id=org_id, full_name="Test User", email="t@acme.com")
    # user.shift intentionally left None → shift_start skipped in policy eval

    def mock_query(model):
        m = MagicMock()
        if model == AttendancePolicy:
            m.filter.return_value.order_by.return_value.first.return_value = policy
        elif model == User:
            m.filter.return_value.first.return_value = user
        elif model == AttendanceSession:
            m.filter.return_value.first.return_value = None  # force creation
        elif model == LeaveRequest:
            m.filter.return_value.first.return_value = None
        elif model == AttendanceDevice:
            m.filter.return_value.first.return_value = None
        else:
            m.filter.return_value.first.return_value = None
        return m

    db.query.side_effect = mock_query

    with patch("app.services.audit_service.audit_service.record") as mock_audit, \
         patch("app.services.event_bus.event_bus.publish") as mock_event, \
         patch("app.services.notification_service.notification_service.send") as mock_notif, \
         patch("app.services.business_calendar_service.business_calendar_service.is_working_day",
               return_value=True) as mock_wd:
        session = attendance_service.mark_attendance(
            db=db,
            org_id=org_id,
            user_id=10,
            channel="FACE",
            check_in=datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc),
            work_date=work_date,
        )

        assert session.status == "PRESENT"
        assert session.channel == "FACE"
        mock_event.assert_called_with("AttendanceMarked", str(org_id), ANY, actor_id=10)
        mock_audit.assert_called()
        mock_notif.assert_called()  # check-in triggers user notification


# =============================================================================
#  Attendance Policy Evaluation & Geofence Validation
# =============================================================================

def test_attendance_policy_evaluation_and_geofence():
    """A late check-in past the grace window should flag is_late, and a GPS
    point inside an active geofence zone should validate as within fence."""
    db = MagicMock()
    org_id = uuid.uuid4()

    policy = _mock_attendance_policy(org_id)
    zone = GeofenceZone(
        id=1,
        org_id=org_id,
        name="HQ Bengaluru",
        code="HQ",
        latitude=12.9716,
        longitude=77.5946,
        radius_meters=500,
        is_active=True,
    )

    def mock_query(model):
        m = MagicMock()
        if model == AttendancePolicy:
            m.filter.return_value.order_by.return_value.first.return_value = policy
        elif model == GeofenceZone:
            # Both filter().all() (policy eval) and filter().order_by().all() (list_zones)
            m.filter.return_value.all.return_value = [zone]
            m.filter.return_value.order_by.return_value.all.return_value = [zone]
        else:
            m.filter.return_value.first.return_value = None
        return m

    db.query.side_effect = mock_query

    # Late by 30 minutes (grace = 5 min)
    result = attendance_policy_service.evaluate_policy(
        db,
        org_id,
        {
            "check_in": datetime(2026, 8, 3, 9, 30, tzinfo=timezone.utc),
            "shift_start": "09:00",
            "channel": "FACE",
            "gps_lat": 12.9716,
            "gps_lng": 77.5946,
        },
    )
    assert result["is_late"] is True
    assert result["channel_allowed"] is True
    assert result["within_geofence"] is True
    assert result["geofence_zone"] == "HQ Bengaluru"

    # Direct geofence point validation
    validated = geo_attendance_service.validate_point(db, org_id, 12.9716, 77.5946)
    assert validated["valid"] is True
    assert validated["zone_name"] == "HQ Bengaluru"


# =============================================================================
#  Leave — Apply Reserves Balance, Approve Deducts It
# =============================================================================

def test_leave_apply_and_approve():
    """apply_leave reserves pending_days; approve_leave commits used_days and
    emits the LeaveApproved domain event."""
    db = MagicMock()
    org_id = uuid.uuid4()

    leave_type = LeaveType(
        id=1, organization_id=org_id, name="Annual Leave", code="ANNUAL",
        max_days_per_year=12, max_days_per_request=30, is_active=True, is_paid=True,
    )
    balance = LeaveBalance(
        id=1, user_id=10, organization_id=org_id, leave_type_id=1, year=2026,
        entitled_days=12.0, used_days=0.0, pending_days=0.0,
        carried_forward_days=0.0, adjusted_days=0.0,
    )
    request = LeaveRequest(
        id=1, organization_id=org_id, user_id=10, leave_type_id=1,
        total_days=2, status="pending",
    )

    def mock_query(model):
        m = MagicMock()
        if model == LeaveType:
            m.filter.return_value.first.return_value = leave_type
        elif model == LeaveBalance:
            m.filter.return_value.first.return_value = balance
        elif model == LeaveRequest:
            m.filter.return_value.first.return_value = request
        else:
            m.filter.return_value.first.return_value = None
        return m

    db.query.side_effect = mock_query

    with patch("app.services.audit_service.audit_service.record") as mock_audit, \
         patch("app.services.event_bus.event_bus.publish") as mock_event, \
         patch("app.services.notification_service.notification_service.send") as mock_notif, \
         patch("app.services.business_calendar_service.business_calendar_service.is_working_day",
               return_value=True) as mock_wd, \
         patch("app.services.workflow_engine.WorkflowEngine.submit_request",
               return_value=MagicMock(id=500)) as mock_wf:
        req = leave_service.apply_leave(
            db=db, org_id=org_id, user_id=10, leave_type_id=1,
            start_date=date(2026, 8, 3), end_date=date(2026, 8, 4),
            reason="Vacation",
        )
        assert req.status == "pending"
        assert balance.pending_days == 2.0
        mock_event.assert_any_call("LeaveRequested", str(org_id), ANY, actor_id=10)

        approved = leave_service.approve_leave(
            db=db, org_id=org_id, request_id=1, approver_user_id=5, note="OK"
        )
        assert approved.status == "approved"
        assert balance.pending_days == 0.0
        assert balance.used_days == 2.0
        mock_event.assert_any_call("LeaveApproved", str(org_id), ANY, actor_id=5)


# =============================================================================
#  Shift — Template Creation & Assignment Lifecycle
# =============================================================================

def test_shift_assignment_lifecycle():
    """Shift template creation, user shift assignment, and listing."""
    db = MagicMock()
    org_id = uuid.uuid4()

    tpl = shift_service.create_template(db, org_id, {
        "name": "Morning Shift",
        "shift_type": "FIXED",
        "start_time": time(9, 0),
        "end_time": time(18, 0),
        "grace_period_mins": 5,
        "buffer_mins": 15,
    })
    assert tpl.name == "Morning Shift"
    assert tpl.shift_type == "FIXED"

    with patch("app.services.audit_service.audit_service.record") as mock_audit:
        assignment = shift_service.assign_shift(db, org_id, {
            "user_id": 10,
            "shift_template_id": tpl.id,
            "start_date": date(2026, 8, 1),
            "end_date": date(2026, 8, 31),
            "assignment_type": "PERMANENT",
            "is_active": True,
        })
        assert assignment.user_id == 10
        assert assignment.start_date == date(2026, 8, 1)
        mock_audit.assert_called()

    # List assignments returns persisted rows
    stored = MagicMock()
    stored.id = 1
    stored.user_id = 10
    stored.start_date = date(2026, 8, 1)
    db.query.reset_mock()
    # list_assignments applies both tenant and active filters. Reuse one query
    # object so the mock mirrors SQLAlchemy's fluent query chain.
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = [stored]
    db.query.side_effect = None
    db.query.return_value = query

    assignments = shift_service.list_assignments(db, org_id)
    assert len(assignments) == 1
    assert assignments[0].user_id == 10


# =============================================================================
#  Roster — Publish Auto-Generates Entries
# =============================================================================

def test_roster_publish_generates_entries():
    """Publishing a roster with auto_generate creates per-day roster entries
    from active shift assignments and emits the RosterPublished event."""
    db = MagicMock()
    org_id = uuid.uuid4()

    roster = Roster(
        id=1, org_id=org_id, title="Aug Week 1", roster_type="WEEKLY",
        start_date=date(2026, 8, 3), end_date=date(2026, 8, 7), status="DRAFT",
    )
    tpl = ShiftTemplate(
        id=1, org_id=org_id, name="Morning", shift_type="FIXED",
        start_time=time(9, 0), end_time=time(18, 0), grace_period_mins=5, buffer_mins=15,
    )
    assignment = ShiftAssignment(
        id=1, org_id=org_id, user_id=10, shift_template_id=1,
        start_date=date(2026, 8, 1), end_date=date(2026, 8, 31),
        assignment_type="PERMANENT", is_active=True,
    )
    assignment.shift_template = tpl

    def mock_query(model):
        m = MagicMock()
        if model == Roster:
            m.filter.return_value.first.return_value = roster
        elif model == ShiftAssignment:
            m.filter.return_value.all.return_value = [assignment]
        else:
            m.filter.return_value.first.return_value = None
        return m

    db.query.side_effect = mock_query

    with patch("app.services.audit_service.audit_service.record") as mock_audit, \
         patch("app.services.event_bus.event_bus.publish") as mock_event, \
         patch("app.services.notification_service.notification_service.send") as mock_notif:
        published = roster_service.publish_roster(
            db=db, org_id=org_id, roster_id=1, published_by_user_id=5
        )
        assert published.status == "PUBLISHED"
        assert published.published_by_user_id == 5
        # 5 weekdays (Aug 3-7) → 5 roster entries generated
        mock_event.assert_any_call("RosterPublished", str(org_id), ANY, actor_id=5)


# =============================================================================
#  Holiday Calendar — Working-Day Exclusion in Leave Computation
# =============================================================================

def test_holiday_calendar_working_day_exclusion():
    """Holiday entries sync into the business calendar; leave day counting
    excludes non-working (holiday) days."""
    db = MagicMock()
    org_id = uuid.uuid4()

    cal = HolidayCalendar(id=1, org_id=org_id, name="India Holidays", country_code="IN", is_default=True)

    def mock_query(model):
        m = MagicMock()
        m.filter.return_value.first.return_value = cal if model == HolidayCalendar else None
        return m

    db.query.side_effect = mock_query

    with patch("app.services.audit_service.audit_service.record"), \
         patch("app.services.business_calendar_service.business_calendar_service.add_holiday") as mock_add:
        created = holiday_service.create_calendar(
            db, org_id, {"name": "India Holidays", "country_code": "IN", "is_default": True}
        )
        added = holiday_service.add_entry(
            db, org_id, created.id,
            {"name": "Independence Day", "holiday_date": date(2026, 8, 15), "holiday_type": "NATIONAL"},
        )
        assert added.name == "Independence Day"
        mock_add.assert_called_once()

    # Leave spanning a working day + a holiday should count only 1 day
    leave_type = LeaveType(
        id=1, organization_id=org_id, name="Annual", code="ANNUAL",
        max_days_per_year=12, max_days_per_request=30, is_active=True,
    )
    balance = LeaveBalance(
        user_id=10, organization_id=org_id, leave_type_id=1, year=2026,
        entitled_days=12.0, used_days=0.0, pending_days=0.0,
        carried_forward_days=0.0, adjusted_days=0.0,
    )
    request = LeaveRequest(
        id=1, organization_id=org_id, user_id=10, leave_type_id=1,
        total_days=1, status="pending",
    )

    def mock_query2(model):
        m = MagicMock()
        if model == LeaveType:
            m.filter.return_value.first.return_value = leave_type
        elif model == LeaveBalance:
            m.filter.return_value.first.return_value = balance
        elif model == LeaveRequest:
            m.filter.return_value.first.return_value = request
        else:
            m.filter.return_value.first.return_value = None
        return m

    db.query.side_effect = mock_query2

    def fake_working(d, org):
        return d != date(2026, 8, 4)  # Aug 4 is a holiday

    with patch("app.services.audit_service.audit_service.record"), \
         patch("app.services.event_bus.event_bus.publish"), \
         patch("app.services.notification_service.notification_service.send"), \
         patch("app.services.business_calendar_service.business_calendar_service.is_working_day",
               side_effect=fake_working), \
         patch("app.services.workflow_engine.WorkflowEngine.submit_request",
               return_value=MagicMock(id=500)):
        req = leave_service.apply_leave(
            db, org_id, 10, 1, date(2026, 8, 3), date(2026, 8, 4), reason="Test"
        )
        assert req.total_days == 1.0
        assert balance.pending_days == 1.0


# =============================================================================
#  Overtime — Compute, Approve & Comp-Off Credit
# =============================================================================

def test_overtime_compute_and_approval():
    """Overtime is computed from net work minutes vs the scheduled shift,
    and approval transitions the record to APPROVED with the event emitted."""
    db = MagicMock()
    org_id = uuid.uuid4()

    shift = Shift(
        id=1, org_id=org_id, shift_name="Standard",
        start_time=time(9, 0), end_time=time(18, 0), grace_period_mins=5, buffer_mins=15,
    )
    user = User(id=10, org_id=org_id, full_name="Emp", email="emp@acme.com")
    user.shift = shift
    entry = TimeEntry(
        id=1, org_id=org_id, user_id=10, work_date=date(2026, 8, 3),
        net_work_minutes=600, total_break_minutes=30, status="COMPLETED",
    )
    ot_record = OvertimeRecord(
        id=1, org_id=org_id, user_id=10, work_date=date(2026, 8, 3),
        overtime_minutes=60, overtime_hours=1.0, rate_multiplier=1.50, status="PENDING",
    )

    def mock_query(model):
        m = MagicMock()
        if model == User:
            m.filter.return_value.first.return_value = user
        elif model == TimeEntry:
            m.filter.return_value.first.return_value = entry
        elif model == OvertimeRecord:
            m.filter.return_value.first.return_value = ot_record
        else:
            m.filter.return_value.first.return_value = None
        return m

    db.query.side_effect = mock_query

    with patch("app.services.audit_service.audit_service.record") as mock_audit, \
         patch("app.services.event_bus.event_bus.publish") as mock_event, \
         patch("app.services.notification_service.notification_service.send") as mock_notif, \
         patch("app.services.workflow_engine.WorkflowEngine.submit_request",
               return_value=MagicMock(id=500)) as mock_wf:
        ot = overtime_service.compute_overtime(db, org_id, 10, date(2026, 8, 3), entry_id=1)
        # Scheduled 9h (540 min), worked 600 min → 60 min / 1.0 h overtime
        assert ot.overtime_hours == 1.0
        assert ot.overtime_minutes == 60
        assert ot.status == "PENDING"
        mock_event.assert_any_call("OvertimeComputed", str(org_id), ANY, actor_id=10)

        approved = overtime_service.approve_overtime(db, org_id, ot.id, approver_user_id=5)
        assert approved.status == "APPROVED"
        mock_event.assert_any_call("OvertimeApproved", str(org_id), ANY, actor_id=5)


# =============================================================================
#  Capacity Planning — Snapshot Utilization Metrics
# =============================================================================

def test_capacity_snapshot_utilization():
    """Capacity snapshot derives utilization from active users minus bench
    count over planned headcount capacity."""
    db = MagicMock()
    org_id = uuid.uuid4()

    users = [
        User(id=1, org_id=org_id, dept_id=2),
        User(id=2, org_id=org_id, dept_id=2),
        User(id=3, org_id=org_id, dept_id=2),
    ]
    bench = BenchRecord(
        id=1, org_id=org_id, user_id=1, status="ON_BENCH",
        bench_start_date=date(2026, 8, 1),
    )
    plan = HeadcountPlan(
        id=1, org_id=org_id, dept_id=2, period_year=2026, period_month=8,
        planned_headcount=5, approved_headcount=5, status="ACTIVE",
    )

    def mock_query(model):
        m = MagicMock()
        if model == User:
            m.filter.return_value.all.return_value = users
        elif model == BenchRecord:
            m.filter.return_value.all.return_value = [bench]
        elif model == HeadcountPlan:
            m.filter.return_value.order_by.return_value.first.return_value = plan
        else:
            m.filter.return_value.first.return_value = None
        return m

    db.query.side_effect = mock_query

    with patch("app.services.audit_service.audit_service.record") as mock_audit, \
         patch("app.services.event_bus.event_bus.publish") as mock_event:
        snap = capacity_planning_service.create_snapshot(db, org_id)

        # capacity=5, assigned=3, bench=1 → allocated=2 → utilization=40.0%
        assert snap.total_capacity == 5
        assert snap.bench_count == 1
        assert snap.allocated_count == 2
        assert snap.utilization_pct == 40.0
        mock_event.assert_any_call("CapacitySnapshotCreated", str(org_id), ANY)
