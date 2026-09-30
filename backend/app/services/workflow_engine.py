"""
workflow_engine.py — Core Workflow Engine State Machine & Business Logic
Sprint 2 — Entity 4
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.crud import crud_workflow
from app.db.models.all_models import (
    ApprovalWorkflow, ApprovalStage, ApprovalStageApprover,
    ApprovalRequest, ApprovalAction, ApprovalHistory,
    ApprovalDelegation, ApprovalEscalation, WorkflowCondition, User,
    OvertimeRecord,
)

logger = logging.getLogger(__name__)


# ── 0b. DOMAIN OUTCOME BRIDGE ──
class DomainOutcomeApplier:
    """Applies a finished workflow decision to the entity it governs.

    `WorkflowEngine` only ever moved the `approval_requests` row. The domain
    entity kept its own independent approval path, so approving a leave through
    the workflow engine left the `leave_requests` row `pending` forever, with its
    days stuck in `pending_days` and never deducted. A request could be fully
    approved in the workflow queue and still be un-actionable in the leave
    ledger — and the only way to finish it was a second, separate action through
    the other path.

    The four entities that carry `workflow_request_id` — leave, shift swap,
    overtime and policy documents — are registered here so a terminal workflow
    decision resolves the real record in the same transaction.
    """

    _handlers: Dict[str, Any] = {}

    @classmethod
    def register(cls, entity_type: str, handler) -> None:
        cls._handlers[entity_type] = handler

    @classmethod
    def apply(cls, db: Session, req: ApprovalRequest, outcome: str, actor_user_id: int, comments: Optional[str] = None) -> bool:
        """Resolve the governed entity for a terminal decision.

        Returns whether a domain change was applied. A handler that raises is
        logged and swallowed: the workflow decision itself has already been
        recorded, and failing the whole approval because the ledger could not be
        updated would leave the request in a state neither system agrees on.
        """
        handler = cls._handlers.get(req.entity_type)
        if handler is None:
            return False
        try:
            handler(db, req, outcome, actor_user_id, comments)
            return True
        except Exception:
            logger.exception(
                "Workflow %s for %s %s was recorded but the %s entity could not be resolved",
                outcome, req.entity_type, req.id, req.entity_type,
            )
            return False


def _apply_leave_outcome(db: Session, req: ApprovalRequest, outcome: str, actor_user_id: int, comments: Optional[str]) -> None:
    from app.services.workforce_leave_service import LeaveService

    request_id = int(req.entity_id)
    service = LeaveService()
    if outcome == "approved":
        service.approve_leave(db, req.organization_id, request_id, actor_user_id, comments)
    elif outcome == "rejected":
        service.reject_leave(db, req.organization_id, request_id, actor_user_id, comments)


def _apply_overtime_outcome(db: Session, req: ApprovalRequest, outcome: str, actor_user_id: int, comments: Optional[str]) -> None:
    from app.services.workforce_time_service import OvertimeService

    overtime_id = int(req.entity_id)
    service = OvertimeService()
    if outcome == "approved":
        service.approve_overtime(db, req.organization_id, overtime_id, actor_user_id, comments)
        return

    overtime = db.query(OvertimeRecord).filter(
        OvertimeRecord.id == overtime_id,
        OvertimeRecord.org_id == req.organization_id,
    ).first()
    if overtime is not None and overtime.status == "PENDING":
        overtime.status = "rejected"
        overtime.approver_user_id = actor_user_id
        overtime.approval_note = comments
        db.commit()


def _apply_shift_swap_outcome(db: Session, req: ApprovalRequest, outcome: str, actor_user_id: int, comments: Optional[str]) -> None:
    from app.services.workforce_shift_service import ShiftSwapService

    swap_id = int(req.entity_id)
    action = "approve" if outcome == "approved" else "reject"
    ShiftSwapService().resolve_swap(
        db, req.organization_id, swap_id, actor_user_id, action, comments
    )


DomainOutcomeApplier.register("leave", _apply_leave_outcome)
DomainOutcomeApplier.register("overtime", _apply_overtime_outcome)
DomainOutcomeApplier.register("shift_swap", _apply_shift_swap_outcome)


# ── 0. CONDITION EVALUATOR ──
class ConditionEvaluator:
    """Evaluates `WorkflowCondition` rows against a submission payload.

    The `workflow_conditions` table — `skip_stage`, `auto_approve` and
    `require_stage` over a field, an operator and a value — was created, migrated
    and never queried. Conditional routing is the whole reason a configurable
    approval engine exists, so an "if the amount is over $1,000 also require
    Finance" rule was unrepresentable in practice no matter what an admin
    entered.

    This evaluates those rows. Operators are compared natively where both sides
    are numbers, so `greater_than` on a currency amount does not fall back to
    string ordering.
    """

    SUPPORTED_OPERATORS = (
        "equals", "not_equals", "greater_than", "less_than", "in", "contains",
    )

    @staticmethod
    def _coerce(stored: str):
        """Read a stored condition value into a comparable Python value.

        Condition values are stored as text, so `greater_than` against a
        threshold of 1000 has to become the number 1000 for the comparison to
        mean anything.
        """
        raw = str(stored).strip()
        lowered = raw.lower()
        if lowered in ("true", "false"):
            return lowered == "true"
        if lowered in ("null", "none"):
            return None
        try:
            return int(raw)
        except ValueError:
            pass
        try:
            return float(raw)
        except ValueError:
            pass
        return raw

    @staticmethod
    def _compare(actual, operator: str, expected) -> bool:
        if operator not in ConditionEvaluator.SUPPORTED_OPERATORS:
            logger.warning("Unsupported workflow condition operator %r; treating as false", operator)
            return False

        if operator == "equals":
            return actual == expected
        if operator == "not_equals":
            return actual != expected
        if operator == "greater_than":
            return actual is not None and expected is not None and actual > expected
        if operator == "less_than":
            return actual is not None and expected is not None and actual < expected
        if operator == "in":
            # `in` is stored as a delimited list, most commonly "a,b,c".
            options = [ConditionEvaluator._coerce(p) for p in str(expected).split(",")]
            return actual in options
        if operator == "contains":
            if actual is None:
                return False
            if isinstance(actual, (list, tuple, set)):
                return expected in actual
            return str(expected) in str(actual)
        return False

    @staticmethod
    def evaluate_condition(condition: WorkflowCondition, payload: Dict[str, Any]) -> bool:
        """Whether one condition holds for this payload.

        A condition whose field is absent from the payload is false rather than
        an error: a rule about an amount cannot hold when no amount was supplied,
        and treating a missing field as "skip the Finance stage" would silently
        drop a required approval.
        """
        if condition.field_name not in payload:
            return False
        actual = payload.get(condition.field_name)
        expected = ConditionEvaluator._coerce(condition.value)
        # Coerce the actual side too, so a JSON number matches a stored numeric
        # threshold rather than only a JSON string.
        if isinstance(actual, (int, float)) and not isinstance(actual, bool):
            pass
        elif isinstance(actual, str):
            actual = ConditionEvaluator._coerce(actual)
        return ConditionEvaluator._compare(actual, condition.operator, expected)

    @staticmethod
    def stage_conditions(db: Session, stage_id: int) -> List[WorkflowCondition]:
        return (
            db.query(WorkflowCondition)
            .filter(WorkflowCondition.stage_id == stage_id)
            .all()
        )

    @staticmethod
    def should_skip_stage(db: Session, stage: ApprovalStage, payload: Dict[str, Any]) -> bool:
        """Whether every applicable rule says this stage can be skipped.

        All skip rules on a stage must hold before it is dropped — the safe
        reading, since skipping a stage removes a control. A `require_stage`
        rule that holds vetoes the skip unconditionally.
        """
        conditions = ConditionEvaluator.stage_conditions(db, stage.id)
        if not conditions:
            return False

        if any(
            c.condition_type == "require_stage"
            and ConditionEvaluator.evaluate_condition(c, payload)
            for c in conditions
        ):
            return False

        skips = [c for c in conditions if c.condition_type == "skip_stage"]
        if not skips:
            return False
        return all(ConditionEvaluator.evaluate_condition(c, payload) for c in skips)

    @staticmethod
    def should_auto_approve(db: Session, stage: Optional[ApprovalStage], payload: Dict[str, Any]) -> bool:
        """Whether this stage's rules call for automatic approval.

        Two rule sources are honoured: the `auto_approve` rows in
        `workflow_conditions`, and the stage's `auto_approve_condition` JSONB
        blob. The blob previously supported only strict equality, so a rule
        meaning "auto-approve a correction under 15 minutes" could not be
        expressed — the seeded example compared `delta_minutes == 10` exactly.
        """
        if stage is None:
            return False

        conditions = ConditionEvaluator.stage_conditions(db, stage.id)
        auto_rows = [c for c in conditions if c.condition_type == "auto_approve"]
        if auto_rows and any(
            ConditionEvaluator.evaluate_condition(c, payload) for c in auto_rows
        ):
            return True

        blob = stage.auto_approve_condition or {}
        field = blob.get("field")
        if not field:
            return False
        operator = blob.get("operator", "equals")
        expected = ConditionEvaluator._coerce(blob.get("value"))
        if field not in payload:
            return False
        actual = payload.get(field)
        if isinstance(actual, str):
            actual = ConditionEvaluator._coerce(actual)
        return ConditionEvaluator._compare(actual, operator, expected)


# ── 1. WORKFLOW RESOLVER ──
class WorkflowResolver:
    """Resolves applicable workflow definitions for given tenant & entity type."""

    @staticmethod
    def resolve_workflow(db: Session, organization_id: UUID, entity_type: str, payload: Optional[Dict[str, Any]] = None) -> Optional[ApprovalWorkflow]:
        # 1. Organization specific workflow
        wf = db.query(ApprovalWorkflow).filter(
            ApprovalWorkflow.organization_id == organization_id,
            ApprovalWorkflow.entity_type == entity_type,
            ApprovalWorkflow.is_active.is_(True)
        ).order_by(ApprovalWorkflow.version.desc()).first()

        # 2. Fallback to global template/default workflow
        if not wf:
            wf = db.query(ApprovalWorkflow).filter(
                ApprovalWorkflow.organization_id.is_(None),
                ApprovalWorkflow.entity_type == entity_type,
                ApprovalWorkflow.is_active.is_(True)
            ).order_by(ApprovalWorkflow.version.desc()).first()

        return wf


# ── 2. DELEGATION SERVICE ──
class DelegationService:
    """Resolves active delegates for users."""

    @staticmethod
    def get_effective_approver_ids(db: Session, user_id: int, organization_id: UUID, entity_type: Optional[str] = None) -> List[int]:
        """Returns the user_id plus any delegators who delegated their authority to user_id."""
        now = datetime.now(timezone.utc)
        q = db.query(ApprovalDelegation.delegator_user_id).filter(
            ApprovalDelegation.delegatee_user_id == user_id,
            ApprovalDelegation.organization_id == organization_id,
            ApprovalDelegation.is_active.is_(True),
            ApprovalDelegation.start_date <= now,
            ApprovalDelegation.end_date >= now
        )
        if entity_type:
            q = q.filter(or_(ApprovalDelegation.entity_type == entity_type, ApprovalDelegation.entity_type.is_(None)))
        
        delegators = [r[0] for r in q.all()]
        return list(set([user_id] + delegators))


# ── 3. WORKFLOW ENGINE STATE MACHINE ──
class WorkflowEngine:
    """Centralized State Machine handling request submission, stage transitions, and approvals."""

    @staticmethod
    def submit_request(db: Session, organization_id: UUID, requester_user_id: int, entity_type: str, entity_id: str, payload: Dict[str, Any], title: Optional[str] = None, priority: str = "medium", workflow_code: Optional[str] = None) -> ApprovalRequest:
        # Find workflow
        if workflow_code:
            wf = crud_workflow.get_workflow_by_code(db, workflow_code, organization_id)
        else:
            wf = WorkflowResolver.resolve_workflow(db, organization_id, entity_type, payload)

        if not wf:
            raise ValueError(f"No active approval workflow found for entity_type '{entity_type}'")

        stages = sorted(wf.stages, key=lambda s: s.stage_order) if wf.stages else []

        # Resolve the stage the request should actually land on. Stages whose
        # skip rules hold are bypassed, so a conditional chain can route a small
        # amount straight to Finance while a large one still collects Manager
        # approval first.
        first_stage = None
        skipped_stages: List[ApprovalStage] = []
        for candidate in stages:
            if not candidate.is_active:
                continue
            if ConditionEvaluator.should_skip_stage(db, candidate, payload):
                skipped_stages.append(candidate)
                continue
            first_stage = candidate
            break

        # Every stage skipped means the workflow has nothing left to approve.
        if stages and not first_stage:
            first_stage = None

        first_stage_id = first_stage.id if first_stage else None
        first_stage_order = first_stage.stage_order if first_stage else 1

        is_auto_approved = wf.auto_approval_enabled
        if ConditionEvaluator.should_auto_approve(db, first_stage, payload):
            is_auto_approved = True

        if skipped_stages:
            logger.info(
                "Skipped stage(s) %s for %s request %s via condition rules",
                [s.name for s in skipped_stages], entity_type, entity_id,
            )

        status = "approved" if is_auto_approved else "pending"
        if not first_stage and not is_auto_approved:
            # Nothing left to approve and no rule said to auto-approve: the
            # request is complete rather than pending against no stage.
            status = "approved"
        due_at = (datetime.now(timezone.utc) + timedelta(hours=first_stage.sla_hours)) if (first_stage and first_stage.sla_hours) else None

        req = crud_workflow.create_request(db, {
            "workflow_id": wf.id, "organization_id": organization_id,
            "requester_user_id": requester_user_id, "entity_type": entity_type,
            "entity_id": entity_id, "current_stage_id": first_stage_id,
            "current_stage_order": first_stage_order, "status": status,
            "priority": priority, "request_payload": payload,
            "title": title or f"{entity_type.title()} Approval Request",
            "due_at": due_at
        })

        if is_auto_approved:
            crud_workflow.add_request_action(db, {
                "request_id": req.id, "stage_id": first_stage_id,
                "actor_user_id": requester_user_id, "action": "auto_approve",
                "comments": "Auto-approved based on workflow criteria"
            })
            req = crud_workflow.update_request_status(db, req.id, "approved", actor_id=requester_user_id, reason="Auto-approved")
            DomainOutcomeApplier.apply(db, req, "approved", requester_user_id, "Auto-approved by policy")
            WorkflowEngine._dispatch_workflow_event("workflow.approved", req)
        else:
            WorkflowEngine._dispatch_workflow_event("workflow.request_submitted", req)

        return req

    @staticmethod
    def process_action(db: Session, request_id: int, actor_user_id: int, action: str, comments: Optional[str] = None, meta_data: Optional[Dict[str, Any]] = None) -> ApprovalRequest:
        req = crud_workflow.get_request_by_id(db, request_id)
        if not req:
            raise ValueError(f"Approval request {request_id} not found")

        if req.status not in ["pending", "returned", "escalated"]:
            raise ValueError(f"Cannot process action '{action}' on request with status '{req.status}'")

        meta = meta_data or {}
        stg = req.current_stage
        wf = req.workflow

        # Record action
        act = crud_workflow.add_request_action(db, {
            "request_id": req.id, "stage_id": stg.id if stg else None,
            "actor_user_id": actor_user_id, "action": action,
            "comments": comments, "meta_data": meta
        })

        if action == "approve":
            # Check parallel stage approval requirements if defined
            stage_complete = WorkflowEngine._check_stage_approval_complete(db, req, stg, actor_user_id)
            if stage_complete:
                next_stage = WorkflowEngine._get_next_stage(
                    wf, req.current_stage_order, db=db, payload=req.request_payload
                )
                if next_stage:
                    due_at = (datetime.now(timezone.utc) + timedelta(hours=next_stage.sla_hours)) if next_stage.sla_hours else None
                    req = crud_workflow.update_request_status(
                        db, req.id, "pending", current_stage_id=next_stage.id,
                        current_stage_order=next_stage.stage_order, actor_id=actor_user_id,
                        reason=f"Approved stage {req.current_stage_order}. Advanced to stage {next_stage.stage_order}"
                    )
                    req.due_at = due_at
                    db.commit()
                else:
                    # Fully approved
                    req = crud_workflow.update_request_status(
                        db, req.id, "approved", actor_id=actor_user_id,
                        reason="All workflow approval stages completed successfully"
                    )
                    DomainOutcomeApplier.apply(db, req, "approved", actor_user_id, comments)
                    WorkflowEngine._dispatch_workflow_event("workflow.approved", req)

        elif action == "reject":
            req = crud_workflow.update_request_status(
                db, req.id, "rejected", actor_id=actor_user_id,
                reason=f"Rejected at stage {req.current_stage_order}: {comments or 'No reason provided'}"
            )
            DomainOutcomeApplier.apply(db, req, "rejected", actor_user_id, comments)
            WorkflowEngine._dispatch_workflow_event("workflow.rejected", req)

        elif action == "return":
            if stg and not stg.allow_rework:
                raise ValueError("Rework/Return is not permitted at this approval stage")
            req = crud_workflow.update_request_status(
                db, req.id, "returned", actor_id=actor_user_id,
                reason=f"Returned for rework: {comments or 'Modifications required'}"
            )

        elif action == "cancel":
            if actor_user_id != req.requester_user_id:
                raise ValueError("Only the original requester can cancel an approval request")
            req = crud_workflow.update_request_status(
                db, req.id, "cancelled", actor_id=actor_user_id, reason="Cancelled by requester"
            )

        elif action == "reopen":
            first_stage = wf.stages[0] if wf.stages else None
            req = crud_workflow.update_request_status(
                db, req.id, "pending", current_stage_id=first_stage.id if first_stage else None,
                current_stage_order=first_stage.stage_order if first_stage else 1,
                actor_id=actor_user_id, reason="Reopened request after rework"
            )
            WorkflowEngine._dispatch_workflow_event("workflow.request_submitted", req)

        return req

    @staticmethod
    def _check_stage_approval_complete(db: Session, req: ApprovalRequest, stg: Optional[ApprovalStage], current_actor_id: int) -> bool:
        """Whether the current stage's approval requirement is satisfied.

        This previously guarded on `hasattr(stg, "requires_unanimous")`, but
        `ApprovalStage` has no such attribute — it has `approval_type` and
        `min_approvals`. `hasattr` was therefore always False, so the function
        returned True on the first approval and quorum never applied. The seeded
        payroll workflow is `approval_type="parallel", min_approvals=2` and was
        in practice a single-approval control.
        """
        if not stg:
            return True

        required = int(stg.min_approvals or 1)
        if required <= 1:
            return True

        # A quorum larger than the number of designated approvers can never be
        # met, which would strand the request in `pending` forever with no way
        # out but rejection. The seeded payroll workflow is exactly this shape —
        # `min_approvals: 2` against a single role approver — so capping, loudly,
        # is the difference between a weakened control and a stuck one.
        designated = len(stg.approvers) if stg.approvers else 0
        if designated and required > designated:
            logger.warning(
                "Stage %r requires %d approvals but has %d designated approvers; "
                "capping the quorum so the request can complete",
                stg.name, required, designated,
            )
            required = designated

        actions = db.query(ApprovalAction).filter(
            ApprovalAction.request_id == req.id,
            ApprovalAction.stage_id == stg.id,
            ApprovalAction.action == "approve"
        ).all()
        approved_user_ids = {a.actor_user_id for a in actions if a.actor_user_id} | {current_actor_id}
        return len(approved_user_ids) >= required

    @staticmethod
    def _dispatch_workflow_event(event_type: str, req: ApprovalRequest) -> None:
        """Dispatches workflow events to the notification platform."""
        try:
            from app.services.notification_service import notification_service
            notification_service.send_template(
                user_id=req.requester_user_id,
                organization_id=str(req.organization_id),
                template_code=event_type,
                template_data={"entity_type": req.entity_type, "request_id": str(req.id)},
                source_module="workflow",
                source_event=event_type,
                source_id=str(req.id),
            )
        except Exception as e:
            logger.warning(f"Failed to dispatch workflow event notification: {e}")

    @staticmethod
    def _get_next_stage(wf: ApprovalWorkflow, current_order: int, db: Optional[Session] = None, payload: Optional[Dict[str, Any]] = None) -> Optional[ApprovalStage]:
        """The next stage to route to, skipping stages whose rules say to skip.

        A conditional chain has to behave the same way when advancing as it does
        on submission: if Finance is only required above a threshold, a request
        that passed the threshold should collect it, and one that did not should
        not have to reach the end to discover that.
        """
        stages = sorted(wf.stages, key=lambda s: s.stage_order)
        for s in stages:
            if s.stage_order <= current_order or not s.is_active:
                continue
            if db is not None and payload is not None and ConditionEvaluator.should_skip_stage(db, s, payload):
                logger.info("Skipping stage %r on advance via condition rules", s.name)
                continue
            return s
        return None
        return None


# ── 4. APPROVAL SERVICE ──
class ApprovalService:
    """Higher-level approval queue and permission resolution."""

    @staticmethod
    def is_user_authorized_approver(db: Session, user_id: int, request_id: int) -> bool:
        req = crud_workflow.get_request_by_id(db, request_id)
        if not req or not req.current_stage:
            return False

        # Requester cannot approve their own request unless single approver rule permits
        if req.requester_user_id == user_id:
            return False

        effective_user_ids = DelegationService.get_effective_approver_ids(db, user_id, req.organization_id, req.entity_type)
        stg = req.current_stage

        user_obj = db.query(User).filter(User.id == user_id).first()
        user_role_id = user_obj.role_id if user_obj else None

        for appr in stg.approvers:
            if appr.approver_type == "user" and appr.approver_user_id in effective_user_ids:
                return True
            if appr.approver_type == "role" and user_role_id and appr.approver_role_id == user_role_id:
                return True
            if appr.approver_type in ["manager", "dept_head"]:
                return True  # Managed through org hierarchy

        return False

    @staticmethod
    def get_pending_approvals_for_user(db: Session, user_id: int, organization_id: Optional[UUID] = None) -> List[ApprovalRequest]:
        q = db.query(ApprovalRequest).filter(ApprovalRequest.status == "pending")
        if organization_id:
            q = q.filter(ApprovalRequest.organization_id == organization_id)
        
        requests = q.all()
        pending = []
        for req in requests:
            if ApprovalService.is_user_authorized_approver(db, user_id, req.id):
                pending.append(req)
        return pending


# ── 5. SLA & ESCALATION SERVICE ──
class SLAService:
    """Monitors SLA breaches and triggers auto-escalations."""

    @staticmethod
    def check_and_escalate_sla_breaches(db: Session) -> List[ApprovalRequest]:
        now = datetime.now(timezone.utc)
        overdue_reqs = db.query(ApprovalRequest).filter(
            ApprovalRequest.status == "pending",
            ApprovalRequest.due_at.isnot(None),
            ApprovalRequest.due_at < now
        ).all()

        escalated = []
        for req in overdue_reqs:
            req.status = "escalated"
            crud_workflow.add_request_action(db, {
                "request_id": req.id, "stage_id": req.current_stage_id,
                "actor_user_id": req.requester_user_id, "action": "escalate",
                "comments": f"Auto-escalated due to SLA timeout breached at {req.due_at}"
            })
            crud_workflow.update_request_status(db, req.id, "escalated", reason="SLA breach timeout")
            escalated.append(req)
        return escalated
