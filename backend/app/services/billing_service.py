"""
billing_service.py — Enterprise Billing & Subscription Lifecycle Service
Sprint 6 — Phase B: Enterprise Multi-Tenant SaaS Completion

Complete billing infrastructure:
- Subscription lifecycle (upgrade, downgrade, trial, renewal)
- Invoice models and generation
- Payment provider abstraction (Stripe, Razorpay, Paddle)
- Billing events and webhooks
- Trial expiration and renewal scheduling

No payment gateway integration yet (provider-ready abstraction).
No frozen modules are modified.
"""
from __future__ import annotations

import logging
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.all_models import Organization, SubscriptionPlan, OrganizationSubscription
from app.services.notification_service import NotificationChannel, NotificationPriority
from app.services.audit_service import audit_service
from app.services.scheduler_service import scheduler_service, JobPriority
from app.services.config_center import config_center
from app.events.event_bus import event_bus
from app.events.event_types import (
    SubscriptionChangedEvent, EventPriority
)

logger = logging.getLogger(__name__)


class SubscriptionChangeType(Enum):
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    TRIAL_EXTEND = "trial_extend"
    TRIAL_END = "trial_end"
    RENEWAL = "renewal"
    CANCELLATION = "cancellation"


class InvoiceStatus(Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


@dataclass
class Invoice:
    """Represents a billing invoice."""
    id: int = 0
    invoice_number: str = ""
    organization_id: str = ""
    subscription_plan_id: int = 0
    status: InvoiceStatus = InvoiceStatus.DRAFT
    billing_cycle: str = "monthly"
    line_items: list[dict] = field(default_factory=list)
    subtotal: float = 0.0
    discounts: float = 0.0
    tax_rate: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    currency: str = "USD"
    due_date: Optional[str] = None
    paid_at: Optional[str] = None
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class BillingEvent:
    """Billing event/transaction record."""
    id: int = 0
    organization_id: str = ""
    event_type: str = ""
    description: str = ""
    amount: float = 0.0
    currency: str = "USD"
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# =============================================================================
#  Payment Provider Abstraction
# =============================================================================

class PaymentProvider(ABC):
    """Abstract base class for payment providers."""

    @abstractmethod
    def create_customer(self, organization_id: str, email: str, name: str) -> str:
        """Create a customer in the payment provider. Returns customer ID."""
        ...

    @abstractmethod
    def create_subscription(self, customer_id: str, plan_id: str, billing_cycle: str) -> str:
        """Create a subscription. Returns subscription ID."""
        ...

    @abstractmethod
    def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel a subscription."""
        ...

    @abstractmethod
    def update_subscription(self, subscription_id: str, new_plan_id: str) -> str:
        """Update a subscription plan."""
        ...

    @abstractmethod
    def create_invoice(self, customer_id: str, amount: float, currency: str, description: str) -> str:
        """Create an invoice. Returns invoice ID."""
        ...

    @abstractmethod
    def charge(self, customer_id: str, amount: float, currency: str, description: str) -> dict:
        """Charge a customer. Returns charge result."""
        ...

    @abstractmethod
    def refund(self, charge_id: str, amount: float) -> dict:
        """Process a refund."""
        ...

    @abstractmethod
    def get_payment_methods(self, customer_id: str) -> list[dict]:
        """Get saved payment methods for a customer."""
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the provider name."""
        ...


class StripeProvider(PaymentProvider):
    """Stripe payment provider implementation (placeholder)."""

    def get_provider_name(self) -> str:
        return "stripe"

    def create_customer(self, organization_id: str, email: str, name: str) -> str:
        logger.info(f"[Stripe] Creating customer: {email} ({name})")
        return f"cus_{secrets.token_hex(12)}"

    def create_subscription(self, customer_id: str, plan_id: str, billing_cycle: str) -> str:
        logger.info(f"[Stripe] Creating subscription: customer={customer_id}, plan={plan_id}")
        return f"sub_{secrets.token_hex(12)}"

    def cancel_subscription(self, subscription_id: str) -> bool:
        logger.info(f"[Stripe] Cancelling subscription: {subscription_id}")
        return True

    def update_subscription(self, subscription_id: str, new_plan_id: str) -> str:
        logger.info(f"[Stripe] Updating subscription: {subscription_id} → {new_plan_id}")
        return subscription_id

    def create_invoice(self, customer_id: str, amount: float, currency: str, description: str) -> str:
        logger.info(f"[Stripe] Creating invoice: {customer_id}, ${amount}")
        return f"in_{secrets.token_hex(12)}"

    def charge(self, customer_id: str, amount: float, currency: str, description: str) -> dict:
        logger.info(f"[Stripe] Charging {customer_id}: ${amount} for {description}")
        return {
            "charge_id": f"ch_{secrets.token_hex(12)}",
            "status": "succeeded",
            "amount": amount,
            "currency": currency,
        }

    def refund(self, charge_id: str, amount: float) -> dict:
        logger.info(f"[Stripe] Refunding charge {charge_id}: ${amount}")
        return {"refund_id": f"rf_{secrets.token_hex(12)}", "status": "succeeded"}

    def get_payment_methods(self, customer_id: str) -> list[dict]:
        logger.info(f"[Stripe] Getting payment methods for {customer_id}")
        return []


class RazorpayProvider(PaymentProvider):
    """Razorpay payment provider implementation (placeholder)."""

    def get_provider_name(self) -> str:
        return "razorpay"

    def create_customer(self, organization_id: str, email: str, name: str) -> str:
        return f"cust_{secrets.token_hex(12)}"

    def create_subscription(self, customer_id: str, plan_id: str, billing_cycle: str) -> str:
        return f"sub_{secrets.token_hex(12)}"

    def cancel_subscription(self, subscription_id: str) -> bool:
        return True

    def update_subscription(self, subscription_id: str, new_plan_id: str) -> str:
        return subscription_id

    def create_invoice(self, customer_id: str, amount: float, currency: str, description: str) -> str:
        return f"inv_{secrets.token_hex(12)}"

    def charge(self, customer_id: str, amount: float, currency: str, description: str) -> dict:
        return {"charge_id": f"ch_{secrets.token_hex(12)}", "status": "succeeded"}

    def refund(self, charge_id: str, amount: float) -> dict:
        return {"refund_id": f"rf_{secrets.token_hex(12)}", "status": "succeeded"}

    def get_payment_methods(self, customer_id: str) -> list[dict]:
        return []


class PaddleProvider(PaymentProvider):
    """Paddle payment provider implementation (placeholder)."""

    def get_provider_name(self) -> str:
        return "paddle"

    def create_customer(self, organization_id: str, email: str, name: str) -> str:
        return f"ctm_{secrets.token_hex(12)}"

    def create_subscription(self, customer_id: str, plan_id: str, billing_cycle: str) -> str:
        return f"sub_{secrets.token_hex(12)}"

    def cancel_subscription(self, subscription_id: str) -> bool:
        return True

    def update_subscription(self, subscription_id: str, new_plan_id: str) -> str:
        return subscription_id

    def create_invoice(self, customer_id: str, amount: float, currency: str, description: str) -> str:
        return f"inv_{secrets.token_hex(12)}"

    def charge(self, customer_id: str, amount: float, currency: str, description: str) -> dict:
        return {"charge_id": f"ch_{secrets.token_hex(12)}", "status": "succeeded"}

    def refund(self, charge_id: str, amount: float) -> dict:
        return {"refund_id": f"rf_{secrets.token_hex(12)}", "status": "succeeded"}

    def get_payment_methods(self, customer_id: str) -> list[dict]:
        return []


# =============================================================================
#  Billing Service
# =============================================================================

# Invoice counter config key
INVOICE_COUNTER_KEY = "billing.invoice_counter"


class BillingService:
    """
    Enterprise billing & subscription lifecycle service.

    Features:
    - Subscription upgrade/downgrade with proration
    - Trial management (extend, end)
    - Renewal scheduling
    - Invoice generation
    - Payment provider abstraction (Stripe, Razorpay, Paddle)
    - Billing events and audit trail
    - Payment method management
    """

    def __init__(self):
        self._providers: dict[str, PaymentProvider] = {
            "stripe": StripeProvider(),
            "razorpay": RazorpayProvider(),
            "paddle": PaddleProvider(),
        }
        self._invoices: list[Invoice] = []
        self._events: list[BillingEvent] = []
        self._max_history: int = 10000
        self._invoice_counter: int = 0

    # ──────────────────────────────────────────────────────────────────────
    #  Provider Management
    # ──────────────────────────────────────────────────────────────────────

    def get_provider(self, provider_name: str) -> Optional[PaymentProvider]:
        """Get a payment provider by name."""
        return self._providers.get(provider_name.lower())

    def get_active_providers(self) -> list[str]:
        """Get list of available payment providers."""
        return list(self._providers.keys())

    # ──────────────────────────────────────────────────────────────────────
    #  Subscription Lifecycle
    # ──────────────────────────────────────────────────────────────────────

    def change_subscription_plan(
        self,
        db: Session,
        organization_id: UUID,
        new_plan_code: str,
        billing_cycle: str = "monthly",
        proration: bool = True,
        reason: str = "",
        actor_user_id: Optional[int] = None,
    ) -> dict:
        """
        Change a tenant's subscription plan.

        Handles upgrade, downgrade, and cross-grade scenarios.
        """
        org_id_str = str(organization_id)
        org = db.query(Organization).filter(Organization.id == organization_id).first()
        if not org:
            raise ValueError(f"Organization not found: {organization_id}")

        # Get current subscription
        current_sub = db.query(OrganizationSubscription).filter(
            OrganizationSubscription.organization_id == organization_id
        ).first()

        # Get new plan
        new_plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.code == new_plan_code,
            SubscriptionPlan.is_active == True
        ).first()
        if not new_plan:
            raise ValueError(f"Subscription plan not found: {new_plan_code}")

        # Determine change type
        change_type = SubscriptionChangeType.DOWNGRADE
        if current_sub and current_sub.plan:
            if new_plan.tier > current_sub.plan.tier:
                change_type = SubscriptionChangeType.UPGRADE
            elif new_plan.tier == current_sub.plan.tier:
                change_type = SubscriptionChangeType.UPGRADE  # Same tier, treat as upgrade

        # Calculate proration
        proration_amount = 0.0
        if proration and current_sub:
            proration_amount = self._calculate_proration(
                current_sub, new_plan, billing_cycle
            )

        # Update subscription
        effective_date = datetime.now(timezone.utc)
        next_billing = self._calculate_next_billing_date(effective_date, billing_cycle)

        if current_sub:
            current_sub.subscription_plan_id = new_plan.id
            current_sub.billing_cycle = billing_cycle
            db.add(current_sub)
        else:
            new_sub = OrganizationSubscription(
                organization_id=organization_id,
                subscription_plan_id=new_plan.id,
                status="active",
                billing_cycle=billing_cycle,
                start_date=effective_date,
                auto_renew=True,
            )
            db.add(new_sub)
        db.flush()

        # Generate invoice if proration applies
        if proration_amount > 0:
            invoice = self._create_invoice(
                org_id_str,
                new_plan.id,
                billing_cycle,
                proration_amount,
                f"Plan change: {change_type.value}",
            )
            self._record_event(
                org_id_str,
                f"subscription.{change_type.value}",
                f"Plan changed to {new_plan.name} ({change_type.value})",
                amount=proration_amount,
                metadata={"previous_plan": current_sub.plan.name if current_sub and current_sub.plan else "none",
                         "new_plan": new_plan.name, "billing_cycle": billing_cycle},
            )

        # Publish event
        try:
            event = SubscriptionChangedEvent(
                organization_id=org_id_str,
                previous_plan=current_sub.plan.name if current_sub and current_sub.plan else "none",
                new_plan=new_plan.name,
                change_type=change_type.value,
                actor_user_id=actor_user_id,
                reason=reason,
                priority=EventPriority.HIGH,
            )
            event_bus.publish(event)
        except Exception as e:
            logger.warning(f"Failed to publish SubscriptionChangedEvent: {e}")

        # Audit
        audit_service.record(
            module="billing",
            action=f"subscription_{change_type.value}",
            entity_type="subscription",
            entity_id=str(new_plan.id),
            summary=f"Subscription {change_type.value} to {new_plan.name}",
            details={
                "previous_plan": current_sub.plan.name if current_sub and current_sub.plan else "none",
                "new_plan": new_plan.name,
                "proration_amount": proration_amount,
                "reason": reason,
            },
            actor_user_id=actor_user_id,
            organization_id=org_id_str,
        )

        # Send notification
        try:
            from app.services.notification_service import notification_service
            notification_service.send(
                user_id=actor_user_id or 0,
                organization_id=org_id_str,
                channel=NotificationChannel.IN_APP,
                title=f"Subscription {change_type.value}d",
                message=f"Your subscription has been {change_type.value}d to {new_plan.name}.",
                source_module="billing",
                source_event=f"subscription.{change_type.value}",
                priority=NotificationPriority.HIGH,
            )
        except Exception as e:
            logger.warning(f"Failed to send subscription change notification: {e}")

        logger.info(
            f"Subscription {change_type.value} for {organization_id}: "
            f"→ {new_plan.name} (proration: ${proration_amount:.2f})"
        )

        return {
            "success": True,
            "organization_id": org_id_str,
            "previous_plan": current_sub.plan.name if current_sub and current_sub.plan else "none",
            "new_plan": new_plan.name,
            "change_type": change_type.value,
            "effective_date": effective_date.isoformat(),
            "proration_amount": proration_amount,
            "next_billing_date": next_billing.isoformat(),
        }

    def manage_trial(
        self,
        db: Session,
        organization_id: UUID,
        action: str,
        extend_days: int = 14,
        actor_user_id: Optional[int] = None,
    ) -> dict:
        """Extend or end a trial period."""
        org_id_str = str(organization_id)
        sub = db.query(OrganizationSubscription).filter(
            OrganizationSubscription.organization_id == organization_id
        ).first()

        if not sub:
            raise ValueError(f"No subscription found for {organization_id}")

        now = datetime.now(timezone.utc)

        if action == "extend":
            new_trial_end = (
                sub.trial_end.replace(tzinfo=timezone.utc) + timedelta(days=extend_days)
                if sub.trial_end
                else now + timedelta(days=extend_days)
            )
            sub.trial_end = new_trial_end
            sub.status = "trialing"
            db.add(sub)

            audit_service.record(
                module="billing",
                action="trial_extended",
                entity_type="subscription",
                entity_id=str(sub.id),
                summary=f"Trial extended by {extend_days} days",
                details={"new_trial_end": new_trial_end.isoformat()},
                actor_user_id=actor_user_id,
                organization_id=org_id_str,
            )

            return {
                "success": True,
                "action": "trial_extended",
                "new_trial_end": new_trial_end.isoformat(),
                "extend_days": extend_days,
            }

        elif action == "end":
            sub.trial_end = now
            sub.status = "active"
            db.add(sub)

            audit_service.record(
                module="billing",
                action="trial_ended",
                entity_type="subscription",
                entity_id=str(sub.id),
                summary="Trial ended",
                actor_user_id=actor_user_id,
                organization_id=org_id_str,
            )

            return {
                "success": True,
                "action": "trial_ended",
                "message": "Trial period has been ended",
            }

        raise ValueError(f"Invalid trial action: {action}")

    def configure_renewal(
        self,
        db: Session,
        organization_id: UUID,
        auto_renew: bool = True,
        billing_cycle: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> dict:
        """Configure subscription renewal settings."""
        sub = db.query(OrganizationSubscription).filter(
            OrganizationSubscription.organization_id == organization_id
        ).first()

        if not sub:
            raise ValueError(f"No subscription found for {organization_id}")

        sub.auto_renew = auto_renew

        if billing_cycle:
            sub.billing_cycle = billing_cycle

        db.add(sub)

        audit_service.record(
            module="billing",
            action="renewal_configured",
            entity_type="subscription",
            entity_id=str(sub.id),
            summary=f"Renewal configured: auto_renew={auto_renew}",
            details={"auto_renew": auto_renew, "billing_cycle": billing_cycle},
            actor_user_id=actor_user_id,
            organization_id=str(organization_id),
        )

        return {
            "success": True,
            "organization_id": str(organization_id),
            "auto_renew": auto_renew,
            "billing_cycle": billing_cycle or sub.billing_cycle,
        }

    # ──────────────────────────────────────────────────────────────────────
    #  Invoice Management
    # ──────────────────────────────────────────────────────────────────────

    def generate_invoice(
        self,
        db: Session,
        organization_id: UUID,
        billing_cycle: str = "monthly",
    ) -> Invoice:
        """Generate a billing invoice for a tenant."""
        org_id_str = str(organization_id)
        org = db.query(Organization).filter(Organization.id == organization_id).first()
        sub = db.query(OrganizationSubscription).filter(
            OrganizationSubscription.organization_id == organization_id
        ).first()

        if not org or not sub:
            raise ValueError(f"Organization or subscription not found")

        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == sub.subscription_plan_id
        ).first()

        if not plan:
            raise ValueError(f"Subscription plan not found")

        # Calculate invoice amounts
        price = plan.price_monthly if billing_cycle == "monthly" else plan.price_yearly or plan.price_monthly * 12
        tax_rate = 0.0  # Configurable
        tax = price * tax_rate
        total = price + tax

        invoice = self._create_invoice(
            org_id_str,
            plan.id,
            billing_cycle,
            total,
            f"{plan.name} - {billing_cycle} billing",
            line_items=[
                {"description": f"{plan.name} ({billing_cycle})", "quantity": 1, "unit_price": price, "total_price": price},
            ],
            discounts=0.0,
            tax_rate=tax_rate,
            tax=tax,
        )

        # Schedule next invoice
        next_date = self._calculate_next_billing_date(datetime.now(timezone.utc), billing_cycle)
        invoice.due_date = next_date.isoformat()

        # Audit
        audit_service.record(
            module="billing",
            action="invoice_generated",
            entity_type="invoice",
            entity_id=invoice.invoice_number,
            summary=f"Invoice generated: {invoice.invoice_number} (${total:.2f})",
            details={"plan": plan.name, "billing_cycle": billing_cycle},
            organization_id=org_id_str,
        )

        # Send notification
        try:
            from app.services.notification_service import notification_service
            notification_service.send(
                user_id=0,
                organization_id=org_id_str,
                channel=NotificationChannel.IN_APP,
                title="Invoice Generated",
                message=f"Invoice {invoice.invoice_number} for ${total:.2f} has been generated.",
                source_module="billing",
                source_event="billing.invoice_generated",
                priority=NotificationPriority.NORMAL,
            )
        except Exception as e:
            logger.warning(f"Failed to send invoice notification: {e}")

        logger.info(f"Invoice generated: {invoice.invoice_number} for {org.name} (${total:.2f})")
        return invoice

    def mark_invoice_paid(self, invoice_number: str) -> bool:
        """Mark an invoice as paid."""
        for invoice in self._invoices:
            if invoice.invoice_number == invoice_number:
                invoice.status = InvoiceStatus.PAID
                invoice.paid_at = datetime.now(timezone.utc).isoformat()
                self._record_event(
                    invoice.organization_id,
                    "billing.payment_received",
                    f"Payment received for invoice {invoice_number}",
                    amount=invoice.total,
                )
                return True
        return False

    def get_invoices_for_org(self, organization_id: str) -> list[dict]:
        """Get all invoices for a tenant."""
        return [
            self._invoice_to_dict(inv)
            for inv in self._invoices
            if inv.organization_id == organization_id
        ]

    def get_all_invoices(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Get all invoices (admin use)."""
        sorted_invoices = sorted(
            self._invoices, key=lambda i: i.created_at, reverse=True
        )
        return [
            self._invoice_to_dict(inv) for inv in sorted_invoices[offset:offset + limit]
        ]

    # ──────────────────────────────────────────────────────────────────────
    #  Billing Analytics
    # ──────────────────────────────────────────────────────────────────────

    def get_tenant_billing_analytics(
        self, db: Session, organization_id: UUID
    ) -> dict:
        """Get billing analytics for a tenant."""
        org_id_str = str(organization_id)
        org = db.query(Organization).filter(Organization.id == organization_id).first()
        sub = db.query(OrganizationSubscription).filter(
            OrganizationSubscription.organization_id == organization_id
        ).first()

        plan = None
        if sub:
            plan = db.query(SubscriptionPlan).filter(
                SubscriptionPlan.id == sub.subscription_plan_id
            ).first()

        org_invoices = [
            inv for inv in self._invoices
            if inv.organization_id == org_id_str
        ]

        total_invoiced = sum(inv.total for inv in org_invoices if inv.status != InvoiceStatus.CANCELLED)
        total_paid = sum(inv.total for inv in org_invoices if inv.status == InvoiceStatus.PAID)
        total_outstanding = sum(
            inv.total for inv in org_invoices
            if inv.status in (InvoiceStatus.PENDING, InvoiceStatus.OVERDUE)
        )

        now = datetime.now(timezone.utc)
        days_until_renewal = None
        if sub and sub.trial_end:
            days_until_renewal = (sub.trial_end.replace(tzinfo=timezone.utc) - now).days

        return {
            "organization_id": org_id_str,
            "organization_name": org.name if org else "",
            "current_plan": plan.name if plan else "None",
            "plan_tier": plan.tier if plan else 0,
            "status": sub.status if sub else "unknown",
            "billing_cycle": sub.billing_cycle if sub else "monthly",
            "monthly_cost": plan.price_monthly if plan else 0.0,
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "total_outstanding": total_outstanding,
            "invoices_count": len(org_invoices),
            "trial_end_date": sub.trial_end.isoformat() if sub and sub.trial_end else None,
            "next_billing_date": None,
            "subscription_start": sub.start_date.isoformat() if sub and sub.start_date else None,
            "days_until_renewal": days_until_renewal,
            "payment_method_count": 0,
            "currency": "USD",
        }

    def get_billing_events(self, organization_id: str, limit: int = 50) -> list[dict]:
        """Get billing events for a tenant."""
        org_events = [
            e for e in self._events
            if e.organization_id == organization_id
        ]
        org_events.sort(key=lambda e: e.created_at, reverse=True)
        return [
            {
                "id": e.id,
                "organization_id": e.organization_id,
                "event_type": e.event_type,
                "description": e.description,
                "amount": e.amount,
                "currency": e.currency,
                "metadata": e.metadata,
                "created_at": e.created_at,
            }
            for e in org_events[:limit]
        ]

    # ──────────────────────────────────────────────────────────────────────
    #  Trial Expiration & Renewal Scheduling
    # ──────────────────────────────────────────────────────────────────────

    def schedule_trial_expiration_check(self) -> None:
        """Schedule a periodic job to check for expiring trials."""
        try:
            scheduler_service.create_periodic_job(
                name="Trial Expiration Check",
                module="billing",
                task="check_trial_expirations",
                interval_seconds=86400,  # Daily
                params={},
                priority=JobPriority.HIGH,
            )
            logger.info("Scheduled trial expiration check job")
        except Exception as e:
            logger.warning(f"Could not schedule trial expiration check: {e}")

    def schedule_renewal_jobs(self) -> None:
        """Schedule periodic billing jobs."""
        try:
            scheduler_service.create_cron_job(
                name="Invoice Generation",
                module="billing",
                task="generate_recurring_invoices",
                cron_expr="0 3 1 * *",  # 1st day of month at 3 AM
                params={},
                priority=JobPriority.CRITICAL,
            )
            logger.info("Scheduled invoice generation job")
        except Exception as e:
            logger.warning(f"Could not schedule invoice generation: {e}")

    # ──────────────────────────────────────────────────────────────────────
    #  Internal Helpers
    # ──────────────────────────────────────────────────────────────────────

    def _create_invoice(
        self,
        org_id: str,
        plan_id: int,
        billing_cycle: str,
        total: float,
        description: str = "",
        line_items: list[dict] = None,
        discounts: float = 0.0,
        tax_rate: float = 0.0,
        tax: float = 0.0,
    ) -> Invoice:
        """Create an invoice record."""
        self._invoice_counter += 1
        invoice = Invoice(
            id=self._invoice_counter,
            invoice_number=f"INV-{datetime.now(timezone.utc).strftime('%Y%m')}-{self._invoice_counter:04d}",
            organization_id=org_id,
            subscription_plan_id=plan_id,
            status=InvoiceStatus.PENDING,
            billing_cycle=billing_cycle,
            line_items=line_items or [{"description": description, "quantity": 1, "unit_price": total, "total_price": total}],
            subtotal=total + discounts,
            discounts=discounts,
            tax_rate=tax_rate,
            tax=tax,
            total=total,
            due_date=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        )
        self._invoices.append(invoice)
        if len(self._invoices) > self._max_history:
            self._invoices = self._invoices[-self._max_history:]
        return invoice

    def _record_event(
        self,
        org_id: str,
        event_type: str,
        description: str,
        amount: float = 0.0,
        metadata: dict = None,
    ) -> BillingEvent:
        """Record a billing event."""
        event = BillingEvent(
            id=len(self._events) + 1,
            organization_id=org_id,
            event_type=event_type,
            description=description,
            amount=amount,
            metadata=metadata or {},
        )
        self._events.append(event)
        if len(self._events) > self._max_history:
            self._events = self._events[-self._max_history:]
        return event

    @staticmethod
    def _calculate_proration(
        current_sub: OrganizationSubscription,
        new_plan: SubscriptionPlan,
        billing_cycle: str,
    ) -> float:
        """Calculate proration amount for plan change."""
        current_price = current_sub.plan.price_monthly if current_sub.plan else 0
        new_price = new_plan.price_monthly

        if billing_cycle == "yearly":
            current_price = current_sub.plan.price_yearly or current_price * 12 if current_sub.plan else 0
            new_price = new_plan.price_yearly or new_price * 12

        # Simple proration: difference in price
        proration = max(0, new_price - current_price)
        return proration

    @staticmethod
    def _calculate_next_billing_date(
        from_date: datetime, billing_cycle: str
    ) -> datetime:
        """Calculate the next billing date."""
        if billing_cycle == "monthly":
            # Add one month
            month = from_date.month + 1
            year = from_date.year
            if month > 12:
                month = 1
                year += 1
            day = min(from_date.day, 28)
            return from_date.replace(year=year, month=month, day=day)
        elif billing_cycle == "yearly":
            return from_date.replace(year=from_date.year + 1)
        return from_date + timedelta(days=30)

    @staticmethod
    def _invoice_to_dict(invoice: Invoice) -> dict:
        return {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "organization_id": invoice.organization_id,
            "subscription_plan_id": invoice.subscription_plan_id,
            "status": invoice.status.value,
            "billing_cycle": invoice.billing_cycle,
            "line_items": invoice.line_items,
            "subtotal": invoice.subtotal,
            "discounts": invoice.discounts,
            "tax_rate": invoice.tax_rate,
            "tax": invoice.tax,
            "total": invoice.total,
            "currency": invoice.currency,
            "due_date": invoice.due_date,
            "paid_at": invoice.paid_at,
            "notes": invoice.notes,
            "created_at": invoice.created_at,
            "updated_at": invoice.updated_at,
        }


# Singleton
billing_service = BillingService()
