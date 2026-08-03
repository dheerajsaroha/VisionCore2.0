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
    ApprovalDelegation, ApprovalEscalation, WorkflowCondition, User
)

logger = logging.getLogger(__name__)


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

        first_stage = wf.stages[0] if wf.stages else None
        first_stage_id = first_stage.id if first_stage else None
        first_stage_order = first_stage.stage_order if first_stage else 1

        # Check auto-approval rules
        is_auto_approved = wf.auto_approval_enabled
        if first_stage and first_stage.auto_approve_condition:
            cond = first_stage.auto_approve_condition
            field = cond.get("field")
            val = cond.get("value")
            if field and val and payload.get(field) == val:
                is_auto_approved = True

        status = "approved" if is_auto_approved else "pending"
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
            crud_workflow.update_request_status(db, req.id, "approved", actor_id=requester_user_id, reason="Auto-approved")
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
                next_stage = WorkflowEngine._get_next_stage(wf, req.current_stage_order)
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
                    WorkflowEngine._dispatch_workflow_event("workflow.approved", req)

        elif action == "reject":
            req = crud_workflow.update_request_status(
                db, req.id, "rejected", actor_id=actor_user_id,
                reason=f"Rejected at stage {req.current_stage_order}: {comments or 'No reason provided'}"
            )
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
        """Determines if the current stage requirements (sequential or parallel quorum) are satisfied."""
        if not stg:
            return True
        # Default single approval completes stage
        if not hasattr(stg, "requires_unanimous") or not stg.requires_unanimous:
            return True
        # If unanimous parallel approval is required, check all approvers
        actions = db.query(ApprovalAction).filter(
            ApprovalAction.request_id == req.id,
            ApprovalAction.stage_id == stg.id,
            ApprovalAction.action == "approve"
        ).all()
        approved_user_ids = {a.actor_user_id for a in actions} | {current_actor_id}
        total_approvers = len(stg.approvers) if stg.approvers else 1
        return len(approved_user_ids) >= total_approvers

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
    def _get_next_stage(wf: ApprovalWorkflow, current_order: int) -> Optional[ApprovalStage]:
        stages = sorted(wf.stages, key=lambda s: s.stage_order)
        for s in stages:
            if s.stage_order > current_order and s.is_active:
                return s
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
