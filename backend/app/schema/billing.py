"""
billing.py — Pydantic Schemas for Billing & Subscription Management
Sprint 6 — Phase B: Enterprise Multi-Tenant SaaS Completion
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ── Invoice Models ──────────────────────────────────────────────────────

class InvoiceLineItem(BaseModel):
    """A single line item on an invoice."""
    description: str
    quantity: int = 1
    unit_price: float
    total_price: float
    metadata: dict = {}


class InvoiceCreate(BaseModel):
    """Create a new invoice."""
    organization_id: str
    subscription_plan_id: int
    billing_cycle: str = "monthly"
    line_items: list[InvoiceLineItem] = []
    discounts: float = 0.0
    tax_rate: float = 0.0
    currency: str = "USD"
    notes: str = ""


class InvoiceResponse(BaseModel):
    """Invoice response."""
    id: int
    invoice_number: str
    organization_id: str
    organization_name: str = ""
    subscription_plan: str = ""
    status: str
    billing_cycle: str
    line_items: list[dict] = []
    subtotal: float
    discounts: float
    tax: float
    total: float
    currency: str
    due_date: Optional[str] = None
    paid_at: Optional[str] = None
    notes: str = ""
    created_at: str
    updated_at: str


# ── Subscription Management ──────────────────────────────────────────────

class SubscriptionChangeRequest(BaseModel):
    """Change subscription plan."""
    organization_id: str
    new_plan_code: str = Field(..., min_length=1)
    billing_cycle: str = "monthly"
    proration: bool = True
    reason: str = ""


class SubscriptionChangeResponse(BaseModel):
    """Response after subscription change."""
    success: bool
    organization_id: str
    previous_plan: str
    new_plan: str
    change_type: str  # upgrade, downgrade
    effective_date: str
    proration_amount: float = 0.0
    next_billing_date: str
    message: str = ""


class TrialActionRequest(BaseModel):
    """Extend or end trial."""
    organization_id: str
    action: str = Field(..., pattern="^(extend|end)$")
    extend_days: Optional[int] = Field(None, ge=1, le=90)


class RenewalRequest(BaseModel):
    """Configure renewal settings."""
    organization_id: str
    auto_renew: bool = True
    billing_cycle: Optional[str] = Field(None, pattern="^(monthly|yearly)$")


# ── Payment Provider Abstraction ─────────────────────────────────────────

class PaymentProviderType(str):
    STRIPE = "stripe"
    RAZORPAY = "razorpay"
    PADDLE = "paddle"


class PaymentMethodCreate(BaseModel):
    """Add a payment method."""
    organization_id: str
    provider: str = Field(..., pattern="^(stripe|razorpay|paddle)$")
    payment_method_id: str
    is_default: bool = True
    billing_details: dict = {}


class PaymentMethodResponse(BaseModel):
    """Payment method response."""
    id: int
    organization_id: str
    provider: str
    payment_method_id: str
    is_default: bool
    last_four: str = ""
    expiry_date: Optional[str] = None
    card_brand: str = ""
    billing_details: dict = {}
    created_at: str


# ── Billing Analytics ────────────────────────────────────────────────────

class BillingAnalyticsResponse(BaseModel):
    """Billing analytics for a tenant."""
    organization_id: str
    organization_name: str = ""
    current_plan: str = ""
    plan_tier: int = 0
    status: str = ""
    billing_cycle: str = ""
    monthly_cost: float = 0.0
    total_invoiced: float = 0.0
    total_paid: float = 0.0
    total_outstanding: float = 0.0
    invoices_count: int = 0
    trial_end_date: Optional[str] = None
    next_billing_date: Optional[str] = None
    subscription_start: Optional[str] = None
    days_until_renewal: Optional[int] = None
    payment_method_count: int = 0
    currency: str = "USD"


class BillingEventResponse(BaseModel):
    """Billing event/transaction record."""
    id: int
    organization_id: str
    event_type: str
    description: str
    amount: float = 0.0
    currency: str = "USD"
    metadata: dict = {}
    created_at: str


# ── Provider Configuration ───────────────────────────────────────────────

class ProviderConfigRequest(BaseModel):
    """Configure a payment provider."""
    provider: str = Field(..., pattern="^(stripe|razorpay|paddle)$")
    api_key: str = Field(..., min_length=1)
    webhook_secret: str = ""
    is_active: bool = True
    config: dict = {}


class ProviderConfigResponse(BaseModel):
    """Payment provider configuration response."""
    id: int
    provider: str
    is_active: bool
    configured_at: str
    last_used_at: Optional[str] = None
