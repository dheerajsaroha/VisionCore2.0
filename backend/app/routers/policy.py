"""
policy.py — FastAPI Router for Enterprise Policy Center & Compliance Management System
Sprint 4 — Entity 5
All endpoints enforce EAAC authorization pipeline (Subscription → Feature → Permission → Scope → Ownership)
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_db, get_current_active_user
from app.api.eaac_deps import require_eaac_authorization
from app.db.models.all_models import (
    User, PolicyCategory, PolicyTag, PolicyDocument, PolicyVersion, PolicyAttachment,
    PolicyDistribution, PolicyAcknowledgement, PolicySignature, PolicyTemplate,
    PolicyReminder, PolicyNotification, ComplianceRule, ComplianceRecord, ComplianceAudit
)
from app.crud.crud_policy import (
    crud_policy_category, crud_policy_tag, crud_policy_document, crud_policy_version,
    crud_policy_attachment, crud_policy_distribution, crud_policy_acknowledgement,
    crud_policy_signature, crud_policy_template, crud_policy_reminder,
    crud_policy_notification, crud_compliance_rule, crud_compliance_record
)
from app.schema.policy import (
    PolicyCategoryCreate, PolicyCategoryUpdate, PolicyCategoryResponse,
    PolicyTagCreate, PolicyTagResponse,
    PolicyDocumentCreate, PolicyDocumentUpdate, PolicyDocumentResponse,
    PolicyVersionCreate, PolicyVersionResponse, PolicyAttachmentCreate, PolicyAttachmentResponse,
    PolicyDistributionCreate, PolicyDistributionResponse,
    PolicyAcknowledgeRequest, PolicyAcknowledgementResponse,
    PolicySignatureCreate, PolicySignatureResponse,
    PolicyTemplateCreate, PolicyTemplateResponse,
    PolicyReminderCreate, PolicyReminderResponse,
    PolicyNotificationResponse,
    ComplianceRuleCreate, ComplianceRuleResponse,
    ComplianceRecordResponse,
    PolicyCenterAnalytics
)
from app.db.seed_policy import seed_policy_defaults_for_org
from app.services.policy_engine import policy_engine
from app.services.distribution_engine import distribution_engine
from app.services.compliance_engine import compliance_engine
from app.services.signature_engine import signature_engine
from app.services.reminder_engine import reminder_engine
from app.services.policy_search_service import policy_search_service

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY CATEGORIES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/categories", response_model=List[PolicyCategoryResponse])
def list_policy_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List policy categories for current organization."""
    seed_policy_defaults_for_org(db, current_user.org_id, current_user.id)
    return crud_policy_category.get_all_for_org(db, current_user.org_id)


@router.post("/categories", response_model=PolicyCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_policy_category(
    payload: PolicyCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.category.create"))
):
    return crud_policy_category.create(db, current_user.org_id, payload.model_dump())


@router.patch("/categories/{category_id}", response_model=PolicyCategoryResponse)
def update_policy_category(
    category_id: int,
    payload: PolicyCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.category.update"))
):
    cat = crud_policy_category.get_by_id(db, category_id)
    if not cat or cat.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Category not found")
    return crud_policy_category.update(db, cat, payload.model_dump(exclude_unset=True))


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY TAGS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/tags", response_model=List[PolicyTagResponse])
def list_policy_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List policy tags for current organization."""
    return crud_policy_tag.get_all_for_org(db, current_user.org_id)


@router.post("/tags", response_model=PolicyTagResponse, status_code=status.HTTP_201_CREATED)
def create_policy_tag(
    payload: PolicyTagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.tag.create"))
):
    return crud_policy_tag.create(db, current_user.org_id, payload.model_dump())


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY DOCUMENTS (Master CRUD + Workflow)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/documents", response_model=Dict[str, Any])
def search_policy_documents(
    query: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    policy_type: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    sort_by: str = Query("updated_at"),
    sort_desc: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Search policy documents with full-text and faceted filtering."""
    return policy_search_service.search_policies(
        db, current_user.org_id, query=query, status=status,
        policy_type=policy_type, category_id=category_id,
        sort_by=sort_by, sort_desc=sort_desc, skip=skip, limit=limit
    )


@router.get("/documents/{doc_id}", response_model=PolicyDocumentResponse)
def get_policy_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a policy document with versions and attachments."""
    doc = crud_policy_document.get_by_id(db, doc_id)
    if not doc or doc.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Policy document not found")

    versions = crud_policy_version.get_versions_for_doc(db, doc_id)
    attachments = crud_policy_attachment.get_for_doc(db, doc_id)
    return {
        **doc.__dict__,
        "versions": [v.__dict__ for v in versions],
        "attachments": [a.__dict__ for a in attachments]
    }


@router.post("/documents", response_model=PolicyDocumentResponse, status_code=status.HTTP_201_CREATED)
def create_policy_document(
    payload: PolicyDocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.document.create"))
):
    """Create a new policy document."""
    doc = crud_policy_document.create(db, current_user.org_id, current_user.id, payload.model_dump())
    return {**doc.__dict__, "versions": [], "attachments": []}


@router.patch("/documents/{doc_id}", response_model=PolicyDocumentResponse)
def update_policy_document(
    doc_id: int,
    payload: PolicyDocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.document.update"))
):
    doc = crud_policy_document.get_by_id(db, doc_id)
    if not doc or doc.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Policy document not found")
    updated = crud_policy_document.update(db, doc, payload.model_dump(exclude_unset=True))
    return {**updated.__dict__, "versions": [], "attachments": []}


@router.post("/documents/{doc_id}/publish", response_model=PolicyDocumentResponse)
def publish_policy_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.document.publish"))
):
    doc = crud_policy_document.get_by_id(db, doc_id)
    if not doc or doc.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Policy document not found")
    pub = crud_policy_document.publish(db, doc, current_user.id)
    return {**pub.__dict__, "versions": [], "attachments": []}


@router.post("/documents/{doc_id}/archive", response_model=PolicyDocumentResponse)
def archive_policy_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.document.archive"))
):
    doc = crud_policy_document.get_by_id(db, doc_id)
    if not doc or doc.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Policy document not found")
    arch = crud_policy_document.archive(db, doc, current_user.id)
    return {**arch.__dict__, "versions": [], "attachments": []}


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY VERSIONS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/documents/{doc_id}/versions", response_model=List[PolicyVersionResponse])
def list_policy_versions(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all versions of a policy document."""
    return crud_policy_version.get_versions_for_doc(db, doc_id)


@router.post("/documents/{doc_id}/versions", response_model=PolicyVersionResponse, status_code=status.HTTP_201_CREATED)
def create_policy_version(
    doc_id: int,
    payload: PolicyVersionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.version.create"))
):
    """Create a new version of a policy document."""
    return crud_policy_version.create(db, doc_id, current_user.id, payload.model_dump())


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY ATTACHMENTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/documents/{doc_id}/attachments", response_model=List[PolicyAttachmentResponse])
def list_policy_attachments(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List attachments for a policy document."""
    return crud_policy_attachment.get_for_doc(db, doc_id)


@router.post("/documents/{doc_id}/attachments", response_model=PolicyAttachmentResponse, status_code=status.HTTP_201_CREATED)
def attach_file_to_policy(
    doc_id: int,
    payload: PolicyAttachmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.attachment.create"))
):
    return crud_policy_attachment.create(db, doc_id, current_user.id, payload.model_dump())


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY DISTRIBUTION
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/documents/{doc_id}/distributions", response_model=List[PolicyDistributionResponse])
def list_policy_distributions(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List distributions for a policy document."""
    return crud_policy_distribution.get_for_doc(db, doc_id)


@router.post("/documents/{doc_id}/distributions", response_model=PolicyDistributionResponse, status_code=status.HTTP_201_CREATED)
def create_policy_distribution(
    doc_id: int,
    payload: PolicyDistributionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.distribution.create"))
):
    return crud_policy_distribution.create(db, doc_id, payload.model_dump())


@router.post("/documents/{doc_id}/distribute/org", response_model=PolicyDistributionResponse)
def distribute_to_org(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.distribution.create"))
):
    """Distribute a policy organization-wide."""
    return distribution_engine.distribute_policy_to_org(db, doc_id, current_user.org_id)


@router.post("/documents/{doc_id}/distribute/department/{dept_id}", response_model=PolicyDistributionResponse)
def distribute_to_department(
    doc_id: int,
    dept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.distribution.create"))
):
    return distribution_engine.distribute_policy_to_department(db, doc_id, dept_id)


@router.post("/documents/{doc_id}/distribute/user/{user_id}", response_model=PolicyDistributionResponse)
def distribute_to_user(
    doc_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.distribution.create"))
):
    return distribution_engine.distribute_policy_to_user(db, doc_id, user_id)


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY ACKNOWLEDGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/documents/{doc_id}/acknowledgements", response_model=List[PolicyAcknowledgementResponse])
def list_acknowledgements(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.acknowledgement.read"))
):
    """List all acknowledgements for a policy document."""
    acks = crud_policy_acknowledgement.get_for_doc(db, doc_id)
    result = []
    for a in acks:
        user = db.query(User).filter(User.id == a.user_id).first()
        result.append({**a.__dict__, "user_name": user.full_name if user else None})
    return result


@router.post("/documents/{doc_id}/acknowledge", response_model=PolicyAcknowledgementResponse)
def acknowledge_policy(
    doc_id: int,
    payload: Optional[PolicyAcknowledgeRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Acknowledge a policy document (employee self-service)."""
    ack_data = payload.model_dump() if payload else {}
    ack = crud_policy_acknowledgement.acknowledge(db, doc_id, current_user.id, ack_data)
    return {**ack.__dict__, "user_name": current_user.full_name}


@router.get("/pending-acknowledgements", response_model=List[Dict[str, Any]])
def get_pending_acknowledgements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get policies pending acknowledgement for the current user."""
    return policy_engine.get_user_pending_acknowledgements(db, current_user.org_id, current_user.id)


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY SIGNATURES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/documents/{doc_id}/signatures", response_model=List[PolicySignatureResponse])
def list_signatures(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.signature.read"))
):
    """List digital signatures for a policy document."""
    return signature_engine.get_document_signatures(db, doc_id)


@router.post("/documents/{doc_id}/sign", response_model=PolicySignatureResponse, status_code=status.HTTP_201_CREATED)
def sign_policy_document(
    doc_id: int,
    payload: PolicySignatureCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Sign a policy document (employee self-service)."""
    try:
        sig = signature_engine.sign_document(db, current_user.id, doc_id, payload.model_dump())
        return {**sig.__dict__, "user_name": current_user.full_name}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/signatures/{sig_id}/verify", response_model=Dict[str, Any])
def verify_signature(
    sig_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.signature.verify"))
):
    """Verify a digital signature's integrity."""
    return signature_engine.verify_signature(db, sig_id)


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/templates", response_model=List[PolicyTemplateResponse])
def list_policy_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List policy templates for quick document creation."""
    return crud_policy_template.get_all_for_org(db, current_user.org_id)


@router.post("/templates", response_model=PolicyTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_policy_template(
    payload: PolicyTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.template.create"))
):
    return crud_policy_template.create(db, current_user.org_id, current_user.id, payload.model_dump())


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY REMINDERS & NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/documents/{doc_id}/reminders", response_model=PolicyReminderResponse, status_code=status.HTTP_201_CREATED)
def create_policy_reminder(
    doc_id: int,
    payload: PolicyReminderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.reminder.create"))
):
    return crud_policy_reminder.create(db, current_user.org_id, payload.model_dump())


@router.get("/documents/{doc_id}/reminders", response_model=List[PolicyReminderResponse])
def list_policy_reminders(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    return crud_policy_reminder.get_for_doc(db, doc_id)


@router.post("/reminders/process", response_model=Dict[str, Any])
def process_reminders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.reminder.process"))
):
    """Process all pending reminders — sends notifications for unacknowledged policies."""
    return reminder_engine.process_pending_reminders(db, current_user.org_id)


@router.get("/notifications", response_model=List[PolicyNotificationResponse])
def get_my_notifications(
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get policy notifications for current user."""
    return crud_policy_notification.get_for_user(db, current_user.org_id, current_user.id, unread_only=unread_only)


@router.post("/notifications/{notif_id}/read", response_model=PolicyNotificationResponse)
def mark_notification_read(
    notif_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    n = crud_policy_notification.mark_read(db, notif_id)
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    return n


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLIANCE RULES & RECORDS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/compliance-rules", response_model=List[ComplianceRuleResponse])
def list_compliance_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List compliance rules for current organization."""
    return crud_compliance_rule.get_all_for_org(db, current_user.org_id)


@router.post("/compliance-rules", response_model=ComplianceRuleResponse, status_code=status.HTTP_201_CREATED)
def create_compliance_rule(
    payload: ComplianceRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("compliance.rule.create"))
):
    return crud_compliance_rule.create(db, current_user.org_id, current_user.id, payload.model_dump())


@router.get("/compliance/summary", response_model=Dict[str, Any])
def get_compliance_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("compliance.summary.read"))
):
    """Get organization-wide compliance summary."""
    return compliance_engine.get_org_compliance_summary(db, current_user.org_id)


@router.post("/compliance/check", response_model=Dict[str, Any])
def run_compliance_check(
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("compliance.check.run"))
):
    """Run compliance checks for a user (defaults to current user)."""
    target_id = user_id or current_user.id
    if target_id != current_user.id:
        _ = require_eaac_authorization("compliance.check.run", action="execute")
    return policy_engine.run_compliance_check(db, current_user.org_id, target_id)


@router.get("/compliance/breaches", response_model=List[Dict[str, Any]])
def get_compliance_breaches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("compliance.breaches.read"))
):
    """Detect users who are non-compliant and past their due dates."""
    return compliance_engine.detect_compliance_breaches(db, current_user.org_id)


@router.get("/compliance/trend", response_model=List[Dict[str, Any]])
def get_compliance_trend(
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    return compliance_engine.get_compliance_trend(db, current_user.org_id, days)


# ═══════════════════════════════════════════════════════════════════════════════
# DISTRIBUTION & REMINDER STATS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/distribution-stats", response_model=Dict[str, Any])
def get_distribution_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.distribution.read"))
):
    return distribution_engine.get_distribution_stats(db, current_user.org_id)


@router.get("/reminder-stats", response_model=Dict[str, Any])
def get_reminder_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    return reminder_engine.get_reminder_stats(db, current_user.org_id)


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY ANALYTICS DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/analytics/dashboard", response_model=PolicyCenterAnalytics)
def get_policy_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Executive analytics dashboard for Policy Center."""
    return policy_engine.get_dashboard_analytics(db, current_user.org_id)


@router.get("/analytics/report", response_model=Dict[str, Any])
def get_policy_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.report.generate"))
):
    """Generate comprehensive policy center report."""
    analytics = policy_engine.get_dashboard_analytics(db, current_user.org_id)
    dist_stats = distribution_engine.get_distribution_stats(db, current_user.org_id)
    rem_stats = reminder_engine.get_reminder_stats(db, current_user.org_id)
    comp_summary = compliance_engine.get_org_compliance_summary(db, current_user.org_id)
    stats = policy_search_service.get_policy_statistics(db, current_user.org_id)
    expiring = policy_engine.get_expiring_policies(db, current_user.org_id)
    return {
        **analytics,
        "distribution_stats": dist_stats,
        "reminder_stats": rem_stats,
        "compliance_summary": comp_summary,
        "statistics": stats,
        "expiring_policies_count": len(expiring),
        "expiring_policies": [
            {"id": p.id, "title": p.title, "expiry_date": p.expiry_date}
            for p in expiring
        ]
    }


@router.get("/users-for-policy/{doc_id}", response_model=List[Dict[str, Any]])
def get_users_for_policy(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: Any = Depends(require_eaac_authorization("policy.distribution.users"))
):
    """Get users who should receive/acknowledge a specific policy."""
    return distribution_engine.get_users_for_policy(db, doc_id)

