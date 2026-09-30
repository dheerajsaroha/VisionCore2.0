"""
A finished workflow decision must resolve the entity it governs.

`WorkflowEngine` only ever moved the `approval_requests` row. The domain
entity kept a separate approval path of its own, so the two systems disagreed:

- approving a leave through the workflow engine left `leave_requests.status` at
  `pending`, its days stuck in `pending_days` and never moved to `used_days`;
- a request could read as fully approved in the workflow queue and still be
  un-actionable in the leave ledger, with the only way out a second action
  through the other path;
- the Command Center's fast action set `ApprovalRequest.status` directly,
  finalising a request in one step regardless of how many stages it declared,
  and bypassing the engine entirely.

These cover the bridge for leave, overtime and shift swap, and the single
approval path through the Command Center.
"""
import uuid
from datetime import date, timedelta

import pytest

from app.core.security import get_password_hash
from app.db.database import SessionLocal
from app.db.models.all_models import (
    ApprovalRequest,
    ApprovalStage,
    ApprovalWorkflow,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    OvertimeRecord,
    Organization,
    Role,
    User,
)
from app.services.workflow_engine import DomainOutcomeApplier, WorkflowEngine


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def org(db):
    o = Organization(
        name=f"Bridge {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-BRG-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


def _user(db, org, code, role_name="OrgManager"):
    role = db.query(Role).filter(Role.name == role_name).first()
    slug = f"{code}-{uuid.uuid4().hex[:6]}"
    u = User(
        email=f"{slug}@example.com",
        username=slug,
        employee_id=slug.upper(),
        full_name=code,
        org_id=org.id,
        role_id=role.id,
        is_active=1,
        hashed_password=get_password_hash("Test-Passw0rd!"),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _single_stage_wf(db, org, entity_type):
    wf = ApprovalWorkflow(
        organization_id=org.id,
        code=f"brg_{uuid.uuid4().hex[:6]}",
        name=f"{entity_type} approval",
        entity_type=entity_type,
        is_active=True,
    )
    db.add(wf)
    db.commit()
    db.refresh(wf)
    stg = ApprovalStage(
        workflow_id=wf.id, stage_order=1, name="Approver",
        approval_type="single", min_approvals=1, sla_hours=24,
    )
    db.add(stg)
    db.commit()
    db.refresh(wf)
    return wf


def _leave_type(db, org):
    lt = LeaveType(
        organization_id=org.id, code="EL", name="Earned Leave",
        max_days_per_year=18.0, max_days_per_request=10.0, is_active=1,
    )
    db.add(lt)
    db.commit()
    db.refresh(lt)
    return lt


def _pending_leave(db, org, user, leave_type, total_days=2.0):
    req = LeaveRequest(
        organization_id=org.id,
        user_id=user.id,
        leave_type_id=leave_type.id,
        start_date=date.today() + timedelta(days=7),
        end_date=date.today() + timedelta(days=8),
        total_days=total_days,
        status="pending",
        reason="bridge test",
    )
    db.add(req)
    balance = LeaveBalance(
        organization_id=org.id, user_id=user.id, leave_type_id=leave_type.id,
        year=date.today().year, entitled_days=18.0, used_days=0.0,
        pending_days=total_days,
    )
    db.add(balance)
    db.commit()
    db.refresh(req)
    db.refresh(balance)
    return req, balance


class TestLeaveBridge:
    def test_approving_the_workflow_approves_the_leave(self, db, org):
        """The defect: the leave stayed `pending` and its days stayed reserved."""
        wf = _single_stage_wf(db, org, "leave")
        leave_type = _leave_type(db, org)
        employee = _user(db, org, "employee")
        approver = _user(db, org, "approver", "OrgManager")
        leave, balance = _pending_leave(db, org, employee, leave_type, total_days=2.0)

        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=employee.id,
            entity_type="leave", entity_id=str(leave.id),
            payload={"leave_type": "EL", "total_days": 2.0},
        )
        leave.workflow_request_id = req.id
        db.commit()

        WorkflowEngine.process_action(db, req.id, approver.id, "approve", comments="ok")

        db.refresh(leave)
        db.refresh(balance)
        assert leave.status == "approved", (
            "approving the workflow must resolve the leave it governs"
        )
        assert leave.approver_user_id == approver.id
        assert balance.pending_days == 0.0, "reserved days must be released"
        assert balance.used_days == 2.0, "days must move to used"

    def test_rejecting_the_workflow_releases_the_reserved_days(self, db, org):
        wf = _single_stage_wf(db, org, "leave")
        leave_type = _leave_type(db, org)
        employee = _user(db, org, "employee2")
        approver = _user(db, org, "approver2", "OrgManager")
        leave, balance = _pending_leave(db, org, employee, leave_type, total_days=3.0)

        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=employee.id,
            entity_type="leave", entity_id=str(leave.id), payload={},
        )
        WorkflowEngine.process_action(db, req.id, approver.id, "reject", comments="no cover")

        db.refresh(leave)
        db.refresh(balance)
        assert leave.status == "rejected"
        assert balance.pending_days == 0.0, "a rejection must release the reservation"
        assert balance.used_days == 0.0

    def test_a_multi_stage_chain_only_resolves_on_the_last_stage(self, db, org):
        """The bridge must not fire when an intermediate stage is approved."""
        wf = _single_stage_wf(db, org, "leave")
        second = ApprovalStage(
            workflow_id=wf.id, stage_order=2, name="HR", approval_type="single",
            min_approvals=1, sla_hours=24,
        )
        db.add(second)
        db.commit()
        db.refresh(wf)

        leave_type = _leave_type(db, org)
        employee = _user(db, org, "employee3")
        manager = _user(db, org, "manager3", "OrgManager")
        leave, balance = _pending_leave(db, org, employee, leave_type, total_days=1.0)

        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=employee.id,
            entity_type="leave", entity_id=str(leave.id), payload={},
        )
        WorkflowEngine.process_action(db, req.id, manager.id, "approve")
        db.refresh(leave)
        assert leave.status == "pending", (
            "an intermediate approval must not resolve the leave"
        )
        assert balance.pending_days == 1.0

        hr = _user(db, org, "hr3", "OrgHR")
        WorkflowEngine.process_action(db, req.id, hr.id, "approve")
        db.refresh(leave)
        assert leave.status == "approved"


class TestOtherBridgedEntities:
    def test_overtime_approval_resolves_the_record(self, db, org):
        wf = _single_stage_wf(db, org, "overtime")
        employee = _user(db, org, "otemployee")
        approver = _user(db, org, "otapprover", "OrgManager")
        record = OvertimeRecord(
            org_id=org.id, user_id=employee.id, work_date=date.today(),
            overtime_minutes=120, overtime_hours=2.0, rate_multiplier=1.5,
            status="PENDING",
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=employee.id,
            entity_type="overtime", entity_id=str(record.id), payload={},
        )
        WorkflowEngine.process_action(db, req.id, approver.id, "approve")
        db.refresh(record)
        assert record.status != "PENDING", "the overtime record must leave the pending state"

    def test_shift_swap_resolution_is_wired(self, db, org):
        assert "shift_swap" in DomainOutcomeApplier._handlers

    def test_unregistered_entity_is_a_no_op_not_a_crash(self, db, org):
        """A workflow type with no domain entity must still complete."""
        wf = _single_stage_wf(db, org, "some_future_module")
        requester = _user(db, org, "requester")
        approver = _user(db, org, "approver3", "OrgManager")
        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=requester.id,
            entity_type="some_future_module", entity_id="X-1", payload={},
        )
        req = WorkflowEngine.process_action(db, req.id, approver.id, "approve")
        assert req.status == "approved"

    def test_a_failing_handler_does_not_lose_the_workflow_decision(self, db, org):
        """The approval is recorded even if the ledger cannot be updated."""
        wf = _single_stage_wf(db, org, "leave")
        requester = _user(db, org, "requester4")
        approver = _user(db, org, "approver4", "OrgManager")

        # entity_id points at a leave request that does not exist.
        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=requester.id,
            entity_type="leave", entity_id="999999", payload={},
        )
        req = WorkflowEngine.process_action(db, req.id, approver.id, "approve")
        assert req.status == "approved", (
            "a broken domain link must not strand the approval itself"
        )


class TestBothTracksStayInSync:
    """The Command Center surfaces both the leave and its workflow request.

    A leave approved through its own endpoint used to leave the workflow request
    `pending` forever — an item in the approval queue nobody could clear.
    """

    def test_direct_approval_also_resolves_the_workflow_request(self, db, org):
        from app.services.workforce_leave_service import LeaveService

        wf = _single_stage_wf(db, org, "leave")
        leave_type = _leave_type(db, org)
        employee = _user(db, org, "syncemployee")
        approver = _user(db, org, "syncapprover", "OrgManager")
        leave, balance = _pending_leave(db, org, employee, leave_type, total_days=1.5)

        wf_req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=employee.id,
            entity_type="leave", entity_id=str(leave.id), payload={},
        )
        leave.workflow_request_id = wf_req.id
        db.commit()

        LeaveService().approve_leave(db, org.id, leave.id, approver.id, "direct")

        db.refresh(wf_req)
        assert wf_req.status == "approved", (
            "a directly-approved leave must not leave a phantom pending queue item"
        )

    def test_direct_rejection_also_resolves_the_workflow_request(self, db, org):
        from app.services.workforce_leave_service import LeaveService

        wf = _single_stage_wf(db, org, "leave")
        leave_type = _leave_type(db, org)
        employee = _user(db, org, "syncemployee2")
        approver = _user(db, org, "syncapprover2", "OrgManager")
        leave, _ = _pending_leave(db, org, employee, leave_type, total_days=1.0)

        wf_req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=employee.id,
            entity_type="leave", entity_id=str(leave.id), payload={},
        )
        leave.workflow_request_id = wf_req.id
        db.commit()

        LeaveService().reject_leave(db, org.id, leave.id, approver.id, "direct")

        db.refresh(wf_req)
        assert wf_req.status == "rejected"

    def test_approving_via_the_engine_does_not_recurse(self, db, org):
        """The bridge calls approve_leave, which must not call the engine back."""
        wf = _single_stage_wf(db, org, "leave")
        leave_type = _leave_type(db, org)
        employee = _user(db, org, "syncemployee3")
        approver = _user(db, org, "syncapprover3", "OrgManager")
        leave, _ = _pending_leave(db, org, employee, leave_type, total_days=1.0)

        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=employee.id,
            entity_type="leave", entity_id=str(leave.id), payload={},
        )
        leave.workflow_request_id = req.id
        db.commit()

        req = WorkflowEngine.process_action(db, req.id, approver.id, "approve")
        db.refresh(leave)
        db.refresh(req)
        assert req.status == "approved"
        assert leave.status == "approved"
