"""
crud_workflow.py — Database Data Access Layer for Approval Workflows
Sprint 2 — Entity 4
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload
from app.db.models.all_models import (
    ApprovalWorkflow, ApprovalStage, ApprovalStageApprover,
    ApprovalTemplate, ApprovalRequest, ApprovalAction,
    ApprovalHistory, ApprovalEscalation, ApprovalDelegation,
    WorkflowCondition, WorkflowVariable, WorkflowAudit, ApprovalProxy, User, Role
)

# ── WORKFLOW CRUD ──
def get_workflow_by_id(db: Session, workflow_id: int) -> Optional[ApprovalWorkflow]:
    return db.query(ApprovalWorkflow).options(
        joinedload(ApprovalWorkflow.stages).joinedload(ApprovalStage.approvers)
    ).filter(ApprovalWorkflow.id == workflow_id).first()

def get_workflow_by_code(db: Session, code: str, organization_id: Optional[UUID] = None) -> Optional[ApprovalWorkflow]:
    q = db.query(ApprovalWorkflow).options(
        joinedload(ApprovalWorkflow.stages).joinedload(ApprovalStage.approvers)
    ).filter(ApprovalWorkflow.code == code)
    if organization_id:
        q = q.filter(or_(ApprovalWorkflow.organization_id == organization_id, ApprovalWorkflow.organization_id.is_(None)))
    return q.order_by(ApprovalWorkflow.organization_id.desc().nullslast()).first()

def get_workflows_for_org(db: Session, organization_id: Optional[UUID] = None, entity_type: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[ApprovalWorkflow]:
    q = db.query(ApprovalWorkflow).options(
        joinedload(ApprovalWorkflow.stages).joinedload(ApprovalStage.approvers)
    )
    if organization_id:
        q = q.filter(or_(ApprovalWorkflow.organization_id == organization_id, ApprovalWorkflow.organization_id.is_(None)))
    if entity_type:
        q = q.filter(ApprovalWorkflow.entity_type == entity_type)
    return q.offset(skip).limit(limit).all()

def create_workflow(db: Session, wf_data: Dict[str, Any]) -> ApprovalWorkflow:
    stages_data = wf_data.pop("stages", [])
    wf = ApprovalWorkflow(**wf_data)
    db.add(wf)
    db.commit()
    db.refresh(wf)

    for stg_idx, stg_in in enumerate(stages_data, start=1):
        approvers_data = stg_in.pop("approvers", [])
        stg_order = stg_in.pop("stage_order", stg_idx)
        stg = ApprovalStage(workflow_id=wf.id, stage_order=stg_order, **stg_in)
        db.add(stg)
        db.commit()
        db.refresh(stg)


        for appr_in in approvers_data:
            appr = ApprovalStageApprover(stage_id=stg.id, **appr_in)
            db.add(appr)
        db.commit()

    db.refresh(wf)
    return wf

def update_workflow(db: Session, workflow_id: int, updates: Dict[str, Any]) -> Optional[ApprovalWorkflow]:
    wf = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.id == workflow_id).first()
    if not wf:
        return None
    for k, v in updates.items():
        if v is not None and hasattr(wf, k):
            setattr(wf, k, v)
    wf.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(wf)
    return wf

def delete_workflow(db: Session, workflow_id: int) -> bool:
    wf = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.id == workflow_id).first()
    if not wf:
        return False
    db.delete(wf)
    db.commit()
    return True


# ── STAGE & APPROVER CRUD ──
def add_stage_to_workflow(db: Session, workflow_id: int, stage_in: Dict[str, Any]) -> ApprovalStage:
    approvers = stage_in.pop("approvers", [])
    stg = ApprovalStage(workflow_id=workflow_id, **stage_in)
    db.add(stg)
    db.commit()
    db.refresh(stg)

    for appr in approvers:
        db.add(ApprovalStageApprover(stage_id=stg.id, **appr))
    db.commit()
    db.refresh(stg)
    return stg

def delete_stage(db: Session, stage_id: int) -> bool:
    stg = db.query(ApprovalStage).filter(ApprovalStage.id == stage_id).first()
    if not stg:
        return False
    db.delete(stg)
    db.commit()
    return True


# ── REQUEST CRUD ──
def create_request(db: Session, req_data: Dict[str, Any]) -> ApprovalRequest:
    req = ApprovalRequest(**req_data)
    db.add(req)
    db.commit()
    db.refresh(req)

    # Log creation history
    hist = ApprovalHistory(
        request_id=req.id, from_status=None, to_status=req.status,
        from_stage_order=None, to_stage_order=req.current_stage_order,
        actor_user_id=req.requester_user_id, reason="Workflow request submitted"
    )
    db.add(hist)
    db.commit()
    return req

def get_request_by_id(db: Session, request_id: int) -> Optional[ApprovalRequest]:
    return db.query(ApprovalRequest).options(
        joinedload(ApprovalRequest.workflow),
        joinedload(ApprovalRequest.current_stage).joinedload(ApprovalStage.approvers),
        joinedload(ApprovalRequest.actions)
    ).filter(ApprovalRequest.id == request_id).first()

def get_requests(db: Session, organization_id: Optional[UUID] = None, requester_id: Optional[int] = None, status: Optional[str] = None, entity_type: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[ApprovalRequest]:
    q = db.query(ApprovalRequest).options(
        joinedload(ApprovalRequest.current_stage),
        joinedload(ApprovalRequest.actions)
    )
    if organization_id:
        q = q.filter(ApprovalRequest.organization_id == organization_id)
    if requester_id:
        q = q.filter(ApprovalRequest.requester_user_id == requester_id)
    if status:
        q = q.filter(ApprovalRequest.status == status)
    if entity_type:
        q = q.filter(ApprovalRequest.entity_type == entity_type)
    return q.order_by(ApprovalRequest.created_at.desc()).offset(skip).limit(limit).all()

def add_request_action(db: Session, action_data: Dict[str, Any]) -> ApprovalAction:
    act = ApprovalAction(**action_data)
    db.add(act)
    db.commit()
    db.refresh(act)
    return act

def update_request_status(db: Session, request_id: int, status: str, current_stage_id: Optional[int] = None, current_stage_order: Optional[int] = None, actor_id: Optional[int] = None, reason: Optional[str] = None) -> Optional[ApprovalRequest]:
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not req:
        return None
    from_status = req.status
    from_stage = req.current_stage_order

    req.status = status
    if current_stage_id is not None:
        req.current_stage_id = current_stage_id
    if current_stage_order is not None:
        req.current_stage_order = current_stage_order
    if status in ["approved", "rejected", "cancelled"]:
        req.completed_at = datetime.now(timezone.utc)
    req.updated_at = datetime.now(timezone.utc)

    hist = ApprovalHistory(
        request_id=req.id, from_status=from_status, to_status=status,
        from_stage_order=from_stage, to_stage_order=req.current_stage_order,
        actor_user_id=actor_id, reason=reason
    )
    db.add(hist)
    db.commit()
    db.refresh(req)
    return req


# ── DELEGATIONS & ESCALATIONS CRUD ──
def create_delegation(db: Session, del_data: Dict[str, Any]) -> ApprovalDelegation:
    deleg = ApprovalDelegation(**del_data)
    db.add(deleg)
    db.commit()
    db.refresh(deleg)
    return deleg

def get_active_delegations(db: Session, user_id: int, organization_id: Optional[UUID] = None) -> List[ApprovalDelegation]:
    now = datetime.now(timezone.utc)
    q = db.query(ApprovalDelegation).filter(
        ApprovalDelegation.delegatee_user_id == user_id,
        ApprovalDelegation.is_active.is_(True),
        ApprovalDelegation.start_date <= now,
        ApprovalDelegation.end_date >= now
    )
    if organization_id:
        q = q.filter(ApprovalDelegation.organization_id == organization_id)
    return q.all()

def create_template(db: Session, tmpl_data: Dict[str, Any]) -> ApprovalTemplate:
    tmpl = ApprovalTemplate(**tmpl_data)
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl

def get_templates(db: Session) -> List[ApprovalTemplate]:
    return db.query(ApprovalTemplate).filter(ApprovalTemplate.is_active.is_(True)).all()
