"""
privacy_service.py — Privacy Request & Data Subject Rights (DSAR) Framework
Sprint 9 — Enterprise Intelligence & Analytics Layer

Handles GDPR/CCPA Right of Access (Data Export) and Right to be Forgotten (Anonymization).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.db.models.all_models import (
    PrivacyRequest,
    User,
    AttendanceLog,
    Payroll,
    AuditLog,
)

logger = logging.getLogger(__name__)


class PrivacyService:
    """Manages DSAR (Data Subject Access Request) lifecycle and processing."""

    def submit_privacy_request(
        self,
        db: Session,
        org_id: UUID,
        user_id: int,
        request_type: str,
        details: Optional[str] = None,
    ) -> PrivacyRequest:
        """Submits a new privacy request (ACCESS_EXPORT, RECTIFICATION, ANONYMIZATION, DELETION)."""
        request = PrivacyRequest(
            organization_id=org_id,
            user_id=user_id,
            request_type=request_type.upper(),
            status="REQUESTED",
            details=details,
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        return request

    def list_privacy_requests(
        self, db: Session, org_id: UUID, status_filter: Optional[str] = None
    ) -> List[PrivacyRequest]:
        """Lists privacy requests for an organization."""
        filters = [PrivacyRequest.organization_id == org_id]
        if status_filter:
            filters.append(PrivacyRequest.status == status_filter.upper())
        return list(
            db.scalars(
                select(PrivacyRequest).where(and_(*filters)).order_by(PrivacyRequest.created_at.desc())
            ).all()
        )

    def process_request(
        self, db: Session, request_id: int, processed_by_user_id: int, approve: bool = True, rejection_reason: Optional[str] = None, organization_id: Optional[UUID] = None
    ) -> PrivacyRequest:
        """Processes and fulfills a privacy request.

        `organization_id` is required. The lookup used to be by primary key
        alone, so any authenticated caller who guessed or enumerated an id could
        fulfil another tenant's request — and fulfilment for ACCESS_EXPORT reads
        that subject's payroll and attendance, making it a cross-tenant data
        exfiltration path rather than a mere authorization gap.
        """
        if organization_id is None:
            raise ValueError("organization_id is required to process a privacy request.")

        req = db.execute(
            select(PrivacyRequest).where(
                and_(
                    PrivacyRequest.id == request_id,
                    PrivacyRequest.organization_id == organization_id,
                )
            )
        ).scalar_one_or_none()

        if not req:
            # Deliberately "not found" rather than "forbidden": confirming that
            # an id exists in another tenant is itself a disclosure.
            raise ValueError("Privacy request not found.")

        req.processed_by_user_id = processed_by_user_id

        if not approve:
            req.status = "REJECTED"
            req.rejection_reason = rejection_reason or "Request denied by Compliance Administrator."
            db.commit()
            db.refresh(req)
            return req

        req.status = "IN_PROGRESS"
        db.commit()

        # Fulfill based on type
        if req.request_type in ("ACCESS_EXPORT", "EXPORT"):
            user = db.execute(select(User).where(User.id == req.user_id)).scalar_one_or_none()
            attendances = db.scalars(select(AttendanceLog).where(AttendanceLog.user_id == req.user_id)).all()
            payrolls = db.scalars(select(Payroll).where(Payroll.user_id == req.user_id)).all()

            export_data = {
                "profile": {
                    "id": user.id if user else None,
                    "email": user.email if user else "",
                    "full_name": user.full_name if user else "",
                },
                "attendance_records_count": len(attendances),
                "payroll_records_count": len(payrolls),
                "exported_at": datetime.now(timezone.utc).isoformat(),
            }
            req.export_file_url = f"/api/v1/compliance/privacy-requests/{req.id}/download"
            req.details = json.dumps(export_data)
            req.status = "COMPLETED"

        elif req.request_type in ("ANONYMIZATION", "DELETION"):
            user = db.execute(select(User).where(User.id == req.user_id)).scalar_one_or_none()
            if user:
                user.full_name = "ANONYMIZED_USER"
                user.email = f"anonymized_{user.id}@privacy.local"
                user.is_active = False
            req.status = "COMPLETED"

        else:
            req.status = "COMPLETED"

        req.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(req)
        return req


privacy_service = PrivacyService()
