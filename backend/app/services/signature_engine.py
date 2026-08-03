"""
signature_engine.py — Digital Signature Verification & Management Engine
Sprint 4 — Entity 5
"""
from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.db.models.all_models import (
    PolicySignature, PolicyAcknowledgement, PolicyDocument, User
)
from app.crud.crud_policy import crud_policy_signature


class SignatureEngine:
    """Digital signature creation, verification, and audit trail."""

    @staticmethod
    def generate_signature_hash(
        user_id: int,
        document_id: int,
        document_version: int,
        timestamp: Optional[datetime] = None
    ) -> str:
        """Generate a deterministic signature hash for a document sign event."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        raw = f"{user_id}:{document_id}:{document_version}:{timestamp.isoformat()}:policy-center-v1"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def sign_document(
        db: Session,
        user_id: int,
        document_id: int,
        obj_in: Dict[str, Any]
    ) -> PolicySignature:
        """Sign a policy document with digital signature."""
        doc = db.query(PolicyDocument).filter(PolicyDocument.id == document_id).first()
        if not doc:
            raise ValueError("Document not found")

        # Generate signature hash if not provided
        sig_hash = obj_in.get("signature_hash") or SignatureEngine.generate_signature_hash(
            user_id, document_id, doc.current_version
        )

        sig = crud_policy_signature.create(db, user_id, {
            "acknowledgement_id": obj_in.get("acknowledgement_id"),
            "document_id": document_id,
            "signature_hash": sig_hash,
            "signature_metadata": obj_in.get("signature_metadata"),
            "ip_address": obj_in.get("ip_address"),
            "device_info": obj_in.get("device_info"),
            "verification_method": obj_in.get("verification_method", "click")
        })

        # Auto-mark acknowledgement as acknowledged if not already
        ack = db.query(PolicyAcknowledgement).filter(
            PolicyAcknowledgement.document_id == document_id,
            PolicyAcknowledgement.user_id == user_id
        ).first()

        if ack and not ack.is_acknowledged:
            ack.is_acknowledged = True
            ack.acknowledged_at = datetime.now(timezone.utc)
            db.commit()

        return sig

    @staticmethod
    def verify_signature(
        db: Session,
        signature_id: int
    ) -> Dict[str, Any]:
        """Verify a digital signature's integrity."""
        sig = db.query(PolicySignature).filter(PolicySignature.id == signature_id).first()
        if not sig:
            return {"verified": False, "reason": "Signature not found"}

        doc = db.query(PolicyDocument).filter(PolicyDocument.id == sig.document_id).first()
        if not doc:
            return {"verified": False, "reason": "Document not found"}

        # Recompute hash and compare
        expected_hash = SignatureEngine.generate_signature_hash(
            sig.user_id, sig.document_id, doc.current_version, sig.signed_at
        )

        is_valid = sig.signature_hash == expected_hash

        # Update verification status
        sig.is_verified = is_valid
        db.commit()

        user = db.query(User).filter(User.id == sig.user_id).first()
        return {
            "verified": is_valid,
            "signature_id": sig.id,
            "user_id": sig.user_id,
            "user_name": user.full_name if user else "Unknown",
            "document_id": sig.document_id,
            "document_title": doc.title if doc else "Unknown",
            "signed_at": sig.signed_at,
            "verification_method": sig.verification_method,
            "reason": None if is_valid else "Hash mismatch — document may have been altered"
        }

    @staticmethod
    def get_document_signatures(db: Session, document_id: int) -> List[Dict[str, Any]]:
        """Get all signatures for a document with user info."""
        sigs = crud_policy_signature.get_for_doc(db, document_id)
        result = []
        for s in sigs:
            user = db.query(User).filter(User.id == s.user_id).first()
            result.append({
                "id": s.id,
                "user_id": s.user_id,
                "user_name": user.full_name if user else "Unknown",
                "signed_at": s.signed_at,
                "is_verified": s.is_verified,
                "verification_method": s.verification_method,
                "signature_hash": s.signature_hash[:16] + "..." if s.signature_hash else None
            })
        return result


signature_engine = SignatureEngine()

