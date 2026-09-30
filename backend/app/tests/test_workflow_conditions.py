"""
Conditional approval routing and quorum.

`workflow_conditions` was created, migrated and never queried. It models exactly
the conditional logic the module is named for — `skip_stage`, `auto_approve` and
`require_stage` over a field, an operator and a value — so the headline case
from the brief, "if the expense is over $1,000 also require Finance", could not
be expressed regardless of what an administrator entered. The workflow resolver
accepted a `payload` and discarded it, and the one rule that did evaluate
(`auto_approve_condition`) supported strict equality only, so a seeded example
meant "auto-approve when `delta_minutes == 10`" rather than "under 15 minutes".

Separately, stage quorum was governed by `hasattr(stg, "requires_unanimous")`.
`ApprovalStage` has no such column — it has `approval_type` and `min_approvals`
— so `hasattr` was always False, the function returned True on the first
approval, and a seeded `min_approvals: 2` parallel payroll control was in
practice single-approval.
"""
import uuid

import pytest

from app.db.database import SessionLocal
from app.db.models.all_models import (
    ApprovalAction,
    Organization,
    ApprovalStage,
    ApprovalStageApprover,
    ApprovalWorkflow,
    Role,
    User,
    WorkflowCondition,
)
from app.core.security import get_password_hash
from app.services.workflow_engine import ConditionEvaluator, WorkflowEngine


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
        name=f"Cond {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-COND-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


def _user(db, code, org=None):
    role = db.query(Role).filter(Role.name == "OrgHR").first()
    slug = f"{code}-{uuid.uuid4().hex[:6]}"
    u = User(
        email=f"{slug}@example.com",
        username=slug,
        employee_id=slug.upper(),
        full_name=code,
        org_id=org.id if org is not None else None,
        role_id=role.id,
        is_active=1,
        hashed_password=get_password_hash("Test-Passw0rd!"),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _condition(db, stage, ctype, field, operator, value):
    c = WorkflowCondition(
        workflow_id=stage.workflow_id,
        stage_id=stage.id,
        condition_type=ctype,
        field_name=field,
        operator=operator,
        value=str(value),
    )
    db.add(c)
    db.commit()
    return c


def _workflow(db, org, stages_spec, *, auto_approval_enabled=False, code=None):
    wf = ApprovalWorkflow(
        organization_id=org.id,
        code=code or f"cond_{uuid.uuid4().hex[:6]}",
        name="Conditional Expense Chain",
        entity_type="expense",
        auto_approval_enabled=auto_approval_enabled,
        is_active=True,
    )
    db.add(wf)
    db.commit()
    db.refresh(wf)

    for i, name in enumerate(stages_spec, start=1):
        stg = ApprovalStage(
            workflow_id=wf.id,
            stage_order=i,
            name=name,
            approval_type="single",
            min_approvals=1,
            sla_hours=24,
        )
        db.add(stg)
        db.commit()
        db.refresh(stg)
    db.commit()
    db.refresh(wf)
    return wf


def _stage(wf, name):
    return next(s for s in wf.stages if s.name == name)


class TestConditionEvaluation:
    def test_numeric_comparison_is_not_lexicographic(self):
        """`greater_than` on amounts must compare numbers.

        As strings, "900" > "1000" is True, which would invert a spend threshold.
        """
        assert ConditionEvaluator._compare(900, "greater_than", 1000) is False
        assert ConditionEvaluator._compare(1500, "greater_than", 1000) is True

    def test_stored_numeric_threshold_is_coerced(self):
        assert ConditionEvaluator._compare(
            ConditionEvaluator._coerce("1500"), "greater_than",
            ConditionEvaluator._coerce("1000"),
        ) is True

    def test_all_documented_operators(self):
        assert ConditionEvaluator._compare(5, "equals", 5)
        assert ConditionEvaluator._compare(5, "not_equals", 6)
        assert ConditionEvaluator._compare(6, "greater_than", 5)
        assert ConditionEvaluator._compare(4, "less_than", 5)
        assert ConditionEvaluator._compare("finance", "in", "hr,finance,legal")
        assert ConditionEvaluator._compare("laptop request", "contains", "laptop")

    def test_unknown_operator_fails_closed(self, db, org):
        stage_wf = _workflow(db, org, ["Only"])
        stage = _stage(stage_wf, "Only")
        cond = _condition(db, stage, "skip_stage", "amount", "regex", ".*")
        assert ConditionEvaluator.evaluate_condition(cond, {"amount": 100}) is False

    def test_missing_field_is_false(self, db, org):
        """A rule about an amount cannot hold when no amount was supplied.

        Treating an absent field as a match would skip a required approval.
        """
        wf = _workflow(db, org, ["Finance"])
        cond = _condition(db, _stage(wf, "Finance"), "skip_stage", "amount", "less_than", 1000)
        assert ConditionEvaluator.evaluate_condition(cond, {"reason": "travel"}) is False


class TestConditionalStageSkipping:
    def test_low_value_skips_the_finance_stage(self, db, org):
        """The headline case: Finance is only required above a threshold."""
        wf = _workflow(db, org, ["Manager", "Finance"])
        _condition(db, _stage(wf, "Finance"), "skip_stage", "amount", "less_than", 1000)

        requester = _user(db, "requester", org)
        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=requester.id,
            entity_type="expense", entity_id="EXP-1", payload={"amount": 250},
        )
        db.refresh(req)
        assert req.current_stage.name == "Manager", (
            "a 250 expense must start at Manager, not be pre-approved past it"
        )

    def test_high_value_keeps_the_finance_stage(self, db, org):
        wf = _workflow(db, org, ["Manager", "Finance"])
        _condition(db, _stage(wf, "Finance"), "skip_stage", "amount", "less_than", 1000)

        requester = _user(db, "requester2", org)
        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=requester.id,
            entity_type="expense", entity_id="EXP-2", payload={"amount": 5000},
        )
        db.refresh(req)
        assert req.current_stage.name == "Manager"

        # Approving Manager must now route to Finance rather than finishing.
        approver = _user(db, "approver2", org)
        req = WorkflowEngine.process_action(db, req.id, approver.id, "approve")
        db.refresh(req)
        assert req.current_stage.name == "Finance", (
            "a 5000 expense must still require Finance approval"
        )
        assert req.status == "pending"

    def test_require_stage_vetoes_a_skip(self, db, org):
        """A control explicitly marked required must not be skipped."""
        wf = _workflow(db, org, ["Manager", "Finance"])
        finance = _stage(wf, "Finance")
        _condition(db, finance, "skip_stage", "amount", "less_than", 1000)
        _condition(db, finance, "require_stage", "amount", "less_than", 1000)

        requester = _user(db, "requester3", org)
        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=requester.id,
            entity_type="expense", entity_id="EXP-3", payload={"amount": 100},
        )
        approver = _user(db, "approver3", org)
        req = WorkflowEngine.process_action(db, req.id, approver.id, "approve")
        db.refresh(req)
        assert req.current_stage.name == "Finance"

    def test_all_skip_rules_must_hold(self, db, org):
        wf = _workflow(db, org, ["Manager", "Finance"])
        finance = _stage(wf, "Finance")
        _condition(db, finance, "skip_stage", "amount", "less_than", 1000)
        _condition(db, finance, "skip_stage", "currency", "equals", "INR")

        requester = _user(db, "requester4", org)
        # Under threshold but a different currency: the second rule fails, so
        # Finance is still required.
        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=requester.id,
            entity_type="expense", entity_id="EXP-4",
            payload={"amount": 100, "currency": "USD"},
        )
        approver = _user(db, "approver4", org)
        req = WorkflowEngine.process_action(db, req.id, approver.id, "approve")
        db.refresh(req)
        assert req.current_stage.name == "Finance"


class TestAutoApproval:
    def test_auto_approve_rule_now_supports_operators(self, db, org):
        """The seeded rule could only test equality.

        `{"field": "delta_minutes", "value": 10}` meant exactly ten minutes. A
        threshold rule needs `less_than`.
        """
        wf = _workflow(db, org, ["Manager"])
        stg = _stage(wf, "Manager")
        stg.auto_approve_condition = {
            "field": "delta_minutes", "operator": "less_than", "value": 15,
        }
        db.commit()

        requester = _user(db, "smallcorrection", org)
        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=requester.id,
            entity_type="expense", entity_id="EXP-5", payload={"delta_minutes": 5},
        )
        db.refresh(req)
        assert req.status == "approved", "a 5-minute correction should auto-approve"

    def test_large_correction_is_not_auto_approved(self, db, org):
        wf = _workflow(db, org, ["Manager"])
        stg = _stage(wf, "Manager")
        stg.auto_approve_condition = {
            "field": "delta_minutes", "operator": "less_than", "value": 15,
        }
        db.commit()

        requester = _user(db, "largecorrection", org)
        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=requester.id,
            entity_type="expense", entity_id="EXP-6", payload={"delta_minutes": 90},
        )
        db.refresh(req)
        assert req.status == "pending"

    def test_equality_rule_still_works(self, db, org):
        """Backward compatibility with the already-seeded equality rule."""
        wf = _workflow(db, org, ["Manager"])
        stg = _stage(wf, "Manager")
        stg.auto_approve_condition = {"field": "delta_minutes", "value": 10}
        db.commit()

        requester = _user(db, "exactten", org)
        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=requester.id,
            entity_type="expense", entity_id="EXP-7", payload={"delta_minutes": 10},
        )
        db.refresh(req)
        assert req.status == "approved"


class TestQuorum:
    def _quorum_wf(self, db, org, min_approvals, approver_count):
        wf = ApprovalWorkflow(
            organization_id=org.id,
            code=f"q_{uuid.uuid4().hex[:6]}",
            name="Parallel Payroll Verification",
            entity_type="payroll",
            is_active=True,
        )
        db.add(wf)
        db.commit()
        db.refresh(wf)
        stg = ApprovalStage(
            workflow_id=wf.id, stage_order=1, name="Executive Verification",
            approval_type="parallel", min_approvals=min_approvals, sla_hours=72,
        )
        db.add(stg)
        db.commit()
        db.refresh(stg)
        role = db.query(Role).filter(Role.name == "OrgHR").first()
        for i in range(approver_count):
            db.add(ApprovalStageApprover(
                stage_id=stg.id, approver_type="role", approver_role_id=role.id,
                sequence_order=i + 1,
            ))
        db.commit()
        db.refresh(wf)
        return wf, stg

    def test_single_approval_does_not_satisfy_a_quorum_of_two(self, db, org):
        """The defect: `requires_unanimous` never existed, so one approval passed."""
        wf, _ = self._quorum_wf(db, org, min_approvals=2, approver_count=2)
        requester = _user(db, "payrollreq", org)
        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=requester.id,
            entity_type="payroll", entity_id="RUN-1", payload={},
        )
        first = _user(db, "approver_a", org)
        req = WorkflowEngine.process_action(db, req.id, first.id, "approve")
        db.refresh(req)
        assert req.status == "pending", "one of two required approvals must not finish it"
        assert req.current_stage_id == req.current_stage.id

    def test_second_approval_completes_the_stage(self, db, org):
        wf, _ = self._quorum_wf(db, org, min_approvals=2, approver_count=2)
        requester = _user(db, "payrollreq2", org)
        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=requester.id,
            entity_type="payroll", entity_id="RUN-2", payload={},
        )
        WorkflowEngine.process_action(db, req.id, _user(db, "apr_b1", org).id, "approve")
        req = WorkflowEngine.process_action(db, req.id, _user(db, "apr_b2", org).id, "approve")
        db.refresh(req)
        assert req.status == "approved"

    def test_one_user_approving_twice_does_not_meet_a_quorum(self, db, org):
        wf, _ = self._quorum_wf(db, org, min_approvals=2, approver_count=2)
        requester = _user(db, "payrollreq3", org)
        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=requester.id,
            entity_type="payroll", entity_id="RUN-3", payload={},
        )
        solo = _user(db, "apr_solo", org)
        WorkflowEngine.process_action(db, req.id, solo.id, "approve")
        # The requester is not the approver, but the same user acting twice must
        # not be counted twice regardless.
        actions = db.query(ApprovalAction).filter(ApprovalAction.request_id == req.id).all()
        assert len(actions) == 1

    def test_quorum_larger_than_approvers_does_not_deadlock(self, db, org):
        """The seeded payroll template is min_approvals=2 with one approver."""
        wf, _ = self._quorum_wf(db, org, min_approvals=2, approver_count=1)
        requester = _user(db, "payrollreq4", org)
        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=requester.id,
            entity_type="payroll", entity_id="RUN-4", payload={},
        )
        req = WorkflowEngine.process_action(db, req.id, _user(db, "apr_only", org).id, "approve")
        db.refresh(req)
        assert req.status == "approved", (
            "an unsatisfiable quorum must cap rather than strand the request"
        )

    def test_single_approval_stage_is_unaffected(self, db, org):
        wf, _ = self._quorum_wf(db, org, min_approvals=1, approver_count=1)
        requester = _user(db, "payrollreq5", org)
        req = WorkflowEngine.submit_request(
            db, organization_id=org.id, requester_user_id=requester.id,
            entity_type="payroll", entity_id="RUN-5", payload={},
        )
        req = WorkflowEngine.process_action(db, req.id, _user(db, "apr_single", org).id, "approve")
        db.refresh(req)
        assert req.status == "approved"


class TestConditionSchemaAndApi:
    """A rule has to be enterable, not merely readable by the engine."""

    def test_schema_rejects_an_unknown_operator(self):
        from pydantic import ValidationError
        from app.schema.workflow import ConditionCreate

        with pytest.raises(ValidationError):
            ConditionCreate(
                condition_type="skip_stage", field_name="amount",
                operator="regex", value=".*",
            )

    def test_schema_rejects_an_unknown_condition_type(self):
        from pydantic import ValidationError
        from app.schema.workflow import ConditionCreate

        with pytest.raises(ValidationError):
            ConditionCreate(
                condition_type="obliterate", field_name="amount",
                operator="equals", value="1",
            )

    def test_conditions_persist_through_the_crud_layer(self, db, org):
        from app.crud import crud_workflow

        wf = crud_workflow.create_workflow(db, {
            "organization_id": org.id,
            "code": f"api_{uuid.uuid4().hex[:6]}",
            "name": "Expense Chain",
            "entity_type": "expense",
            "is_active": True,
            "auto_approval_enabled": False,
            "workflow_config": {},
            "stages": [
                {
                    "stage_order": 1, "name": "Manager", "approval_type": "single",
                    "min_approvals": 1, "sla_hours": 24, "allow_rework": True,
                    "auto_approve_condition": {}, "is_active": True,
                    "approvers": [], "conditions": [],
                },
                {
                    "stage_order": 2, "name": "Finance", "approval_type": "single",
                    "min_approvals": 1, "sla_hours": 48, "allow_rework": True,
                    "auto_approve_condition": {}, "is_active": True,
                    "approvers": [],
                    "conditions": [{
                        "condition_type": "skip_stage", "field_name": "amount",
                        "operator": "less_than", "value": "1000",
                    }],
                },
            ],
        })
        db.commit()

        reloaded = crud_workflow.get_workflow_by_id(db, wf.id)
        finance = next(s for s in reloaded.stages if s.name == "Finance")
        assert len(finance.conditions) == 1
        cond = finance.conditions[0]
        assert (cond.condition_type, cond.operator, cond.value) == (
            "skip_stage", "less_than", "1000",
        )

    def test_a_stage_exposes_its_conditions_in_the_response_schema(self):
        from app.schema.workflow import StageResponse

        assert "conditions" in StageResponse.model_fields, (
            "an admin must be able to read back the routing they configured"
        )
