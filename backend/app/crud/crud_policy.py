"""
crud_policy.py — CRUD Operations for Policy Center & Compliance Management
Sprint 4 — Entity 5
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models.all_models import (
    PolicyCategory, PolicyTag, PolicyDocument, PolicyVersion, PolicyAttachment,
    PolicyDistribution, PolicyAcknowledgement, PolicySignature, PolicyTemplate,
    PolicyReminder, PolicyNotification, ComplianceRule, ComplianceRecord, ComplianceAudit, User
)


class CRUDPolicyCategory:
    def get_by_id(self, db: Session, cat_id: int) -> Optional[PolicyCategory]:
        return db.query(PolicyCategory).filter(PolicyCategory.id == cat_id).first()

    def get_all_for_org(self, db: Session, org_id: UUID) -> List[PolicyCategory]:
        return db.query(PolicyCategory).filter(
            PolicyCategory.organization_id == org_id,
            PolicyCategory.is_active.is_(True)
        ).order_by(PolicyCategory.name).all()

    def create(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> PolicyCategory:
        db_obj = PolicyCategory(
            organization_id=org_id,
            name=obj_in["name"],
            code=obj_in.get("code"),
            description=obj_in.get("description"),
            parent_category_id=obj_in.get("parent_category_id"),
            is_active=obj_in.get("is_active", True)
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: PolicyCategory, updates: Dict[str, Any]) -> PolicyCategory:
        for field, val in updates.items():
            if val is not None and hasattr(db_obj, field):
                setattr(db_obj, field, val)
        db.commit()
        db.refresh(db_obj)
        return db_obj


class CRUDPolicyTag:
    def get_all_for_org(self, db: Session, org_id: UUID) -> List[PolicyTag]:
        return db.query(PolicyTag).filter(PolicyTag.organization_id == org_id).all()

    def create(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> PolicyTag:
        db_obj = PolicyTag(
            organization_id=org_id,
            name=obj_in["name"],
            color=obj_in.get("color")
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


class CRUDPolicyDocument:
    def get_by_id(self, db: Session, doc_id: int) -> Optional[PolicyDocument]:
        return db.query(PolicyDocument).filter(PolicyDocument.id == doc_id).first()

    def get_all_for_org(
        self, db: Session, org_id: UUID,
        status: Optional[str] = None,
        policy_type: Optional[str] = None,
        category_id: Optional[int] = None
    ) -> List[PolicyDocument]:
        q = db.query(PolicyDocument).filter(PolicyDocument.organization_id == org_id)
        if status:
            q = q.filter(PolicyDocument.status == status)
        if policy_type:
            q = q.filter(PolicyDocument.policy_type == policy_type)
        if category_id:
            q = q.filter(PolicyDocument.category_id == category_id)
        return q.order_by(PolicyDocument.updated_at.desc()).all()

    def create(self, db: Session, org_id: UUID, user_id: int, obj_in: Dict[str, Any]) -> PolicyDocument:
        db_obj = PolicyDocument(
            organization_id=org_id,
            created_by_user_id=user_id,
            title=obj_in["title"],
            category_id=obj_in.get("category_id"),
            document_number=obj_in.get("document_number"),
            owner_user_id=obj_in.get("owner_user_id"),
            approver_user_id=obj_in.get("approver_user_id"),
            author=obj_in.get("author"),
            content=obj_in.get("content"),
            summary=obj_in.get("summary"),
            policy_type=obj_in.get("policy_type", "hr_policy"),
            is_mandatory=obj_in.get("is_mandatory", False),
            requires_acknowledgement=obj_in.get("requires_acknowledgement", True),
            requires_signature=obj_in.get("requires_signature", False),
            effective_date=obj_in.get("effective_date"),
            expiry_date=obj_in.get("expiry_date"),
            tags=obj_in.get("tags"),
            meta_data=obj_in.get("meta_data"),
            status="draft",
            current_version=1
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)

        # Auto-create version 1
        version = PolicyVersion(
            document_id=db_obj.id,
            version=1,
            version_type="major",
            title=db_obj.title,
            content=db_obj.content,
            change_summary="Initial version",
            status="draft",
            created_by_user_id=user_id
        )
        db.add(version)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: PolicyDocument, updates: Dict[str, Any]) -> PolicyDocument:
        for field, val in updates.items():
            if val is not None and hasattr(db_obj, field):
                setattr(db_obj, field, val)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def publish(self, db: Session, db_obj: PolicyDocument, user_id: int) -> PolicyDocument:
        db_obj.status = "published"
        db_obj.published_at = datetime.now(timezone.utc)
        if not db_obj.effective_date:
            db_obj.effective_date = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_obj)

        # Create notification
        notif = PolicyNotification(
            organization_id=db_obj.organization_id,
            document_id=db_obj.id,
            user_id=None,
            notification_type="policy_published",
            title=f"Policy Published: {db_obj.title}",
            message=f"Policy '{db_obj.title}' has been published and is effective from {db_obj.effective_date}."
        )
        db.add(notif)
        db.commit()
        return db_obj

    def archive(self, db: Session, db_obj: PolicyDocument, user_id: int) -> PolicyDocument:
        db_obj.status = "archived"
        db_obj.archived_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def expire(self, db: Session, db_obj: PolicyDocument) -> PolicyDocument:
        db_obj.status = "expired"
        db.commit()
        db.refresh(db_obj)
        return db_obj


class CRUDPolicyVersion:
    def get_by_id(self, db: Session, ver_id: int) -> Optional[PolicyVersion]:
        return db.query(PolicyVersion).filter(PolicyVersion.id == ver_id).first()

    def get_versions_for_doc(self, db: Session, doc_id: int) -> List[PolicyVersion]:
        return db.query(PolicyVersion).filter(
            PolicyVersion.document_id == doc_id
        ).order_by(PolicyVersion.version.desc()).all()

    def create(self, db: Session, doc_id: int, user_id: int, obj_in: Dict[str, Any]) -> PolicyVersion:
        doc = db.query(PolicyDocument).filter(PolicyDocument.id == doc_id).first()
        if not doc:
            raise ValueError("Document not found")
        new_version = doc.current_version + 1

        version = PolicyVersion(
            document_id=doc_id,
            version=new_version,
            version_type=obj_in.get("version_type", "major"),
            title=obj_in.get("title", doc.title),
            content=obj_in.get("content", doc.content),
            change_summary=obj_in.get("change_summary"),
            status="draft",
            created_by_user_id=user_id
        )
        doc.current_version = new_version
        if obj_in.get("title"):
            doc.title = obj_in["title"]
        if obj_in.get("content"):
            doc.content = obj_in["content"]

        db.add(version)
        db.commit()
        db.refresh(version)
        return version


class CRUDPolicyAttachment:
    def create(self, db: Session, doc_id: int, user_id: int, obj_in: Dict[str, Any]) -> PolicyAttachment:
        att = PolicyAttachment(
            document_id=doc_id,
            version_id=obj_in.get("version_id"),
            file_name=obj_in["file_name"],
            file_url=obj_in["file_url"],
            file_type=obj_in.get("file_type", "pdf"),
            file_size_bytes=obj_in.get("file_size_bytes", 0),
            uploaded_by_user_id=user_id
        )
        db.add(att)
        db.commit()
        db.refresh(att)
        return att

    def get_for_doc(self, db: Session, doc_id: int) -> List[PolicyAttachment]:
        return db.query(PolicyAttachment).filter(
            PolicyAttachment.document_id == doc_id
        ).all()


class CRUDPolicyDistribution:
    def create(self, db: Session, doc_id: int, obj_in: Dict[str, Any]) -> PolicyDistribution:
        dist = PolicyDistribution(
            document_id=doc_id,
            distribution_type=obj_in.get("distribution_type", "organization"),
            target_org_id=obj_in.get("target_org_id"),
            target_dept_id=obj_in.get("target_dept_id"),
            target_role_id=obj_in.get("target_role_id"),
            target_user_id=obj_in.get("target_user_id")
        )
        db.add(dist)
        db.commit()
        db.refresh(dist)
        return dist

    def get_for_doc(self, db: Session, doc_id: int) -> List[PolicyDistribution]:
        return db.query(PolicyDistribution).filter(
            PolicyDistribution.document_id == doc_id,
            PolicyDistribution.is_active.is_(True)
        ).all()


class CRUDPolicyAcknowledgement:
    def get_for_doc(self, db: Session, doc_id: int) -> List[PolicyAcknowledgement]:
        return db.query(PolicyAcknowledgement).filter(
            PolicyAcknowledgement.document_id == doc_id
        ).order_by(PolicyAcknowledgement.created_at.desc()).all()

    def get_for_user(self, db: Session, doc_id: int, user_id: int) -> Optional[PolicyAcknowledgement]:
        return db.query(PolicyAcknowledgement).filter(
            PolicyAcknowledgement.document_id == doc_id,
            PolicyAcknowledgement.user_id == user_id
        ).first()

    def acknowledge(self, db: Session, doc_id: int, user_id: int, obj_in: Dict[str, Any]) -> PolicyAcknowledgement:
        existing = self.get_for_user(db, doc_id, user_id)
        if existing:
            existing.is_acknowledged = True
            existing.acknowledged_at = datetime.now(timezone.utc)
            existing.ip_address = obj_in.get("ip_address")
            existing.device_info = obj_in.get("device_info")
            existing.user_agent = obj_in.get("user_agent")
            existing.read_duration_seconds = obj_in.get("read_duration_seconds")
            existing.version_id = obj_in.get("version_id")
            db.commit()
            db.refresh(existing)
            return existing

        ack = PolicyAcknowledgement(
            document_id=doc_id,
            user_id=user_id,
            version_id=obj_in.get("version_id"),
            is_acknowledged=True,
            acknowledged_at=datetime.now(timezone.utc),
            ip_address=obj_in.get("ip_address"),
            device_info=obj_in.get("device_info"),
            user_agent=obj_in.get("user_agent"),
            read_duration_seconds=obj_in.get("read_duration_seconds")
        )
        db.add(ack)
        db.commit()
        db.refresh(ack)
        return ack

    def get_pending_count(self, db: Session, org_id: UUID, user_id: Optional[int] = None) -> int:
        q = db.query(PolicyAcknowledgement).join(
            PolicyDocument, PolicyAcknowledgement.document_id == PolicyDocument.id
        ).filter(
            PolicyDocument.organization_id == org_id,
            PolicyAcknowledgement.is_acknowledged == False
        )
        if user_id:
            q = q.filter(PolicyAcknowledgement.user_id == user_id)
        return q.count()


class CRUDPolicySignature:
    def create(self, db: Session, user_id: int, obj_in: Dict[str, Any]) -> PolicySignature:
        sig = PolicySignature(
            acknowledgement_id=obj_in.get("acknowledgement_id"),
            user_id=user_id,
            document_id=obj_in["document_id"],
            signature_hash=obj_in["signature_hash"],
            signature_metadata=obj_in.get("signature_metadata"),
            ip_address=obj_in.get("ip_address"),
            device_info=obj_in.get("device_info"),
            verification_method=obj_in.get("verification_method", "click")
        )
        db.add(sig)
        db.commit()
        db.refresh(sig)
        return sig

    def get_for_doc(self, db: Session, doc_id: int) -> List[PolicySignature]:
        return db.query(PolicySignature).filter(
            PolicySignature.document_id == doc_id
        ).order_by(PolicySignature.signed_at.desc()).all()


class CRUDPolicyTemplate:
    def get_all_for_org(self, db: Session, org_id: UUID) -> List[PolicyTemplate]:
        return db.query(PolicyTemplate).filter(
            PolicyTemplate.organization_id == org_id,
            PolicyTemplate.is_active.is_(True)
        ).all()

    def create(self, db: Session, org_id: UUID, user_id: int, obj_in: Dict[str, Any]) -> PolicyTemplate:
        tmpl = PolicyTemplate(
            organization_id=org_id,
            category_id=obj_in.get("category_id"),
            name=obj_in["name"],
            content=obj_in["content"],
            variables=obj_in.get("variables"),
            created_by_user_id=user_id
        )
        db.add(tmpl)
        db.commit()
        db.refresh(tmpl)
        return tmpl


class CRUDPolicyReminder:
    def create(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> PolicyReminder:
        rem = PolicyReminder(
            organization_id=org_id,
            document_id=obj_in["document_id"],
            reminder_type=obj_in.get("reminder_type", "automated"),
            interval_days=obj_in.get("interval_days", 7),
            max_reminders=obj_in.get("max_reminders", 3),
            escalation_user_id=obj_in.get("escalation_user_id")
        )
        db.add(rem)
        db.commit()
        db.refresh(rem)
        return rem

    def get_for_doc(self, db: Session, doc_id: int) -> List[PolicyReminder]:
        return db.query(PolicyReminder).filter(
            PolicyReminder.document_id == doc_id,
            PolicyReminder.is_active.is_(True)
        ).all()


class CRUDPolicyNotification:
    def get_for_user(self, db: Session, org_id: UUID, user_id: int, unread_only: bool = False) -> List[PolicyNotification]:
        q = db.query(PolicyNotification).filter(
            PolicyNotification.organization_id == org_id,
            PolicyNotification.user_id == user_id
        )
        if unread_only:
            q = q.filter(PolicyNotification.is_read == False)
        return q.order_by(PolicyNotification.created_at.desc()).all()

    def mark_read(self, db: Session, notif_id: int) -> Optional[PolicyNotification]:
        n = db.query(PolicyNotification).filter(PolicyNotification.id == notif_id).first()
        if n:
            n.is_read = True
            db.commit()
            db.refresh(n)
        return n


class CRUDComplianceRule:
    def get_all_for_org(self, db: Session, org_id: UUID) -> List[ComplianceRule]:
        return db.query(ComplianceRule).filter(
            ComplianceRule.organization_id == org_id,
            ComplianceRule.is_active.is_(True)
        ).all()

    def create(self, db: Session, org_id: UUID, user_id: int, obj_in: Dict[str, Any]) -> ComplianceRule:
        rule = ComplianceRule(
            organization_id=org_id,
            name=obj_in["name"],
            rule_type=obj_in["rule_type"],
            policy_type_filter=obj_in.get("policy_type_filter"),
            description=obj_in.get("description"),
            grace_period_days=obj_in.get("grace_period_days", 14),
            weight=obj_in.get("weight", 1.0),
            created_by_user_id=user_id
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return rule


class CRUDComplianceRecord:
    def get_for_user(self, db: Session, org_id: UUID, user_id: int) -> List[ComplianceRecord]:
        return db.query(ComplianceRecord).filter(
            ComplianceRecord.organization_id == org_id,
            ComplianceRecord.user_id == user_id
        ).order_by(ComplianceRecord.updated_at.desc()).all()

    def get_for_doc(self, db: Session, org_id: UUID, doc_id: int) -> List[ComplianceRecord]:
        return db.query(ComplianceRecord).filter(
            ComplianceRecord.organization_id == org_id,
            ComplianceRecord.document_id == doc_id
        ).all()

    def create_or_update(self, db: Session, org_id: UUID, doc_id: int, user_id: int,
                         rule_id: Optional[int], is_compliant: bool,
                         due_date: Optional[datetime] = None) -> ComplianceRecord:
        existing = db.query(ComplianceRecord).filter(
            ComplianceRecord.organization_id == org_id,
            ComplianceRecord.document_id == doc_id,
            ComplianceRecord.user_id == user_id,
            ComplianceRecord.rule_id == rule_id
        ).first()

        if existing:
            existing.is_compliant = is_compliant
            existing.status = "compliant" if is_compliant else "pending"
            if is_compliant:
                existing.compliant_at = datetime.now(timezone.utc)
                existing.due_date = due_date
            db.commit()
            db.refresh(existing)
            return existing

        rec = ComplianceRecord(
            organization_id=org_id,
            document_id=doc_id,
            user_id=user_id,
            rule_id=rule_id,
            is_compliant=is_compliant,
            status="compliant" if is_compliant else "pending",
            compliant_at=datetime.now(timezone.utc) if is_compliant else None,
            due_date=due_date
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec


crud_policy_category = CRUDPolicyCategory()
crud_policy_tag = CRUDPolicyTag()
crud_policy_document = CRUDPolicyDocument()
crud_policy_version = CRUDPolicyVersion()
crud_policy_attachment = CRUDPolicyAttachment()
crud_policy_distribution = CRUDPolicyDistribution()
crud_policy_acknowledgement = CRUDPolicyAcknowledgement()
crud_policy_signature = CRUDPolicySignature()
crud_policy_template = CRUDPolicyTemplate()
crud_policy_reminder = CRUDPolicyReminder()
crud_policy_notification = CRUDPolicyNotification()
crud_compliance_rule = CRUDComplianceRule()
crud_compliance_record = CRUDComplianceRecord()
