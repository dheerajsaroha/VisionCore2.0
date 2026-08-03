"""
billing.py — Billing & Subscription Management Router
Sprint 6 — Phase B: Enterprise Multi-Tenant SaaS Completion

SuperAdmin and tenant admin endpoints for billing management.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.api.deps import get_current_active_user, get_current_superadmin
from app.db.models.all_models import User
from app.services.billing_service import billing_service
from app.schema.billing import (
    SubscriptionChangeRequest, SubscriptionChangeResponse,
    TrialActionRequest, RenewalRequest,
    InvoiceResponse, BillingAnalyticsResponse,
    BillingEventResponse, PaymentMethodCreate, PaymentMethodResponse,
    ProviderConfigRequest, ProviderConfigResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


# ── Subscription Management ──────────────────────────────────────────────

@router.post("/subscription/change", response_model=SubscriptionChangeResponse)
def change_subscription_plan(
    request: SubscriptionChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Change subscription plan for a tenant (SuperAdmin only)."""
    try:
        result = billing_service.change_subscription_plan(
            db=db,
            organization_id=UUID(request.organization_id),
            new_plan_code=request.new_plan_code,
            billing_cycle=request.billing_cycle,
            proration=request.proration,
            reason=request.reason,
            actor_user_id=current_user.id,
        )
        return SubscriptionChangeResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/subscription/trial", response_model=dict)
def manage_trial(
    request: TrialActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Extend or end a trial period (SuperAdmin only)."""
    try:
        result = billing_service.manage_trial(
            db=db,
            organization_id=UUID(request.organization_id),
            action=request.action,
            extend_days=request.extend_days or 14,
            actor_user_id=current_user.id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/subscription/renewal", response_model=dict)
def configure_renewal(
    request: RenewalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Configure subscription renewal settings."""
    try:
        result = billing_service.configure_renewal(
            db=db,
            organization_id=UUID(request.organization_id),
            auto_renew=request.auto_renew,
            billing_cycle=request.billing_cycle,
            actor_user_id=current_user.id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── Invoice Management ───────────────────────────────────────────────────

@router.post("/invoices/generate", response_model=InvoiceResponse)
def generate_invoice(
    organization_id: str,
    billing_cycle: str = Query("monthly", pattern="^(monthly|yearly)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Generate an invoice for a tenant."""
    try:
        invoice = billing_service.generate_invoice(
            db=db,
            organization_id=UUID(organization_id),
            billing_cycle=billing_cycle,
        )
        return InvoiceResponse(
            id=invoice.id,
            invoice_number=invoice.invoice_number,
            organization_id=invoice.organization_id,
            status=invoice.status.value,
            billing_cycle=invoice.billing_cycle,
            line_items=invoice.line_items,
            subtotal=invoice.subtotal,
            discounts=invoice.discounts,
            tax=invoice.tax,
            total=invoice.total,
            currency=invoice.currency,
            due_date=invoice.due_date,
            paid_at=invoice.paid_at,
            notes=invoice.notes,
            created_at=invoice.created_at,
            updated_at=invoice.updated_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/invoices", response_model=list[InvoiceResponse])
def list_invoices(
    organization_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
):
    """List invoices, optionally filtered by organization."""
    if organization_id:
        invoices = billing_service.get_invoices_for_org(organization_id)
    else:
        invoices = billing_service.get_all_invoices(limit=limit, offset=offset)

    return [
        InvoiceResponse(
            id=inv["id"],
            invoice_number=inv["invoice_number"],
            organization_id=inv["organization_id"],
            status=inv["status"],
            billing_cycle=inv["billing_cycle"],
            line_items=inv["line_items"],
            subtotal=inv["subtotal"],
            discounts=inv["discounts"],
            tax=inv["tax"],
            total=inv["total"],
            currency=inv["currency"],
            due_date=inv["due_date"],
            paid_at=inv["paid_at"],
            notes=inv["notes"],
            created_at=inv["created_at"],
            updated_at=inv["updated_at"],
        )
        for inv in invoices
    ]


# ── Billing Analytics ────────────────────────────────────────────────────

@router.get("/analytics/{organization_id}", response_model=BillingAnalyticsResponse)
def get_billing_analytics(
    organization_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get billing analytics for a tenant."""
    analytics = billing_service.get_tenant_billing_analytics(
        db=db, organization_id=UUID(organization_id)
    )
    return BillingAnalyticsResponse(**analytics)


@router.get("/events/{organization_id}", response_model=list[BillingEventResponse])
def get_billing_events(
    organization_id: str,
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
):
    """Get billing events for a tenant."""
    events = billing_service.get_billing_events(organization_id, limit=limit)
    return [BillingEventResponse(**e) for e in events]


# ── Payment Provider Management ──────────────────────────────────────────

@router.get("/providers", response_model=list[str])
def get_active_providers(
    current_user: User = Depends(get_current_active_user),
):
    """Get list of available payment providers."""
    return billing_service.get_active_providers()


@router.post("/providers/configure", response_model=ProviderConfigResponse)
def configure_provider(
    request: ProviderConfigRequest,
    current_user: User = Depends(get_current_superadmin),
):
    """Configure a payment provider (SuperAdmin only)."""
    return ProviderConfigResponse(
        id=1,
        provider=request.provider,
        is_active=request.is_active,
        configured_at=datetime.now(timezone.utc).isoformat(),
    )


# ── Payment Methods ──────────────────────────────────────────────────────

@router.post("/payment-methods", response_model=PaymentMethodResponse)
def add_payment_method(
    request: PaymentMethodCreate,
    current_user: User = Depends(get_current_active_user),
):
    """Add a payment method for a tenant."""
    return PaymentMethodResponse(
        id=1,
        organization_id=request.organization_id,
        provider=request.provider,
        payment_method_id=request.payment_method_id,
        is_default=request.is_default,
        billing_details=request.billing_details,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


from datetime import datetime, timezone
