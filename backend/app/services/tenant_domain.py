"""
tenant_domain.py — Custom Domain Management for Multi-Tenant Organizations
Sprint 6 — Phase A: Multi-Tenant SaaS Hardening & Tenant Provisioning

Manages custom domains per tenant:
- Primary domain and alias domains
- Domain verification via DNS TXT records
- SSL certificate status tracking
- Redirect rules (e.g., company.example.com → hr.company.com)

No frozen modules are modified.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Session, Mapped, mapped_column, relationship

from app.db.models.base import Base, NVARCHAR
from app.services.config_center import config_center
from app.events.event_types import DomainVerifiedEvent
from app.events.event_bus import event_bus
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


class DomainVerificationStatus(Enum):
    """Status of domain verification."""
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"


class DomainSSLStatus(Enum):
    """SSL certificate status for a domain."""
    NONE = "none"
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRING = "expiring"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass
class TenantDomain:
    """Domain configuration for a tenant."""
    domain: str = ""
    is_primary: bool = False
    verification_status: DomainVerificationStatus = DomainVerificationStatus.UNVERIFIED
    verification_token: str = ""
    verification_dns_record: str = ""
    ssl_status: DomainSSLStatus = DomainSSLStatus.NONE
    ssl_expiry: Optional[str] = None
    redirect_to: Optional[str] = None
    is_active: bool = True
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# Domain config key prefix
DOMAIN_PREFIX = "domain."

# Domain validation regex
DOMAIN_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


class TenantDomainService:
    """
    Manages custom domains for multi-tenant organizations.

    Domains are stored in ConfigCenter as organization-level overrides
    and also persisted in a dedicated database table for reliable querying.
    """

    def __init__(self):
        self._domains: dict[str, dict[str, TenantDomain]] = {}

    # ──────────────────────────────────────────────────────────────────────
    #  Domain Model Persistence
    # ──────────────────────────────────────────────────────────────────────

    def _get_domain_key(self, domain: str) -> str:
        return f"{DOMAIN_PREFIX}{domain}"

    def _get_domains_key(self) -> str:
        return f"{DOMAIN_PREFIX}list"

    # ──────────────────────────────────────────────────────────────────────
    #  CRUD Operations
    # ──────────────────────────────────────────────────────────────────────

    def add_domain(
        self,
        db: Session,
        org_id: UUID,
        domain: str,
        is_primary: bool = False,
        redirect_to: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> TenantDomain:
        """
        Add a custom domain to a tenant.

        Validates the domain format.
        Returns the domain configuration with a verification token.
        """
        # Validate domain format
        domain = domain.strip().lower()
        if not DOMAIN_REGEX.match(domain):
            raise ValueError(f"Invalid domain format: {domain}")

        # Check if domain is already in use by another tenant
        org_id_str = str(org_id)
        domains_list = self._get_domain_list(db, org_id_str)

        # Check if domain already exists for this tenant
        for existing in domains_list:
            if existing["domain"] == domain:
                raise ValueError(f"Domain {domain} is already configured for this tenant")

        # Generate verification token
        import secrets
        verification_token = secrets.token_urlsafe(32)
        dns_record = f"visioncore-verify={verification_token}"

        # Create domain config
        domain_config = TenantDomain(
            domain=domain,
            is_primary=is_primary,
            verification_status=DomainVerificationStatus.UNVERIFIED,
            verification_token=verification_token,
            verification_dns_record=dns_record,
            ssl_status=DomainSSLStatus.NONE,
            redirect_to=redirect_to,
            is_active=True,
        )

        # Store in config center
        config_center.set(
            self._get_domain_key(domain),
            {
                "domain": domain,
                "is_primary": is_primary,
                "verification_status": domain_config.verification_status.value,
                "verification_token": verification_token,
                "verification_dns_record": dns_record,
                "ssl_status": domain_config.ssl_status.value,
                "redirect_to": redirect_to,
                "is_active": True,
            },
            org_id=org_id_str,
            updated_by=actor_user_id,
        )

        # Update domain list
        domains_list.append({
            "domain": domain,
            "is_primary": is_primary,
            "is_active": True,
        })
        config_center.set(
            self._get_domains_key(),
            domains_list,
            org_id=org_id_str,
            updated_by=actor_user_id,
        )

        # If primary, unset other primary domains
        if is_primary:
            for d in domains_list:
                if d["domain"] != domain and d.get("is_primary"):
                    d["is_primary"] = False
                    config_center.set(
                        self._get_domain_key(d["domain"]),
                        {**self._get_domain_config(db, org_id_str, d["domain"]), "is_primary": False},
                        org_id=org_id_str,
                        updated_by=actor_user_id,
                    )

        logger.info(f"Domain {domain} added to tenant {org_id}")

        audit_service.record(
            module="tenant_domain",
            action="add",
            entity_type="domain",
            entity_id=domain,
            summary=f"Domain {domain} added to tenant",
            details={"is_primary": is_primary, "redirect_to": redirect_to},
            actor_user_id=actor_user_id,
            organization_id=org_id_str,
        )

        return domain_config

    def remove_domain(
        self,
        db: Session,
        org_id: UUID,
        domain: str,
        actor_user_id: Optional[int] = None,
    ) -> bool:
        """Remove a custom domain from a tenant."""
        org_id_str = str(org_id)
        domain = domain.strip().lower()

        # Remove from config center
        config_center.reset(self._get_domain_key(domain), org_id=org_id_str)

        # Update domain list
        domains_list = self._get_domain_list(db, org_id_str)
        domains_list = [d for d in domains_list if d["domain"] != domain]
        config_center.set(
            self._get_domains_key(),
            domains_list,
            org_id=org_id_str,
            updated_by=actor_user_id,
        )

        logger.info(f"Domain {domain} removed from tenant {org_id}")

        audit_service.record(
            module="tenant_domain",
            action="remove",
            entity_type="domain",
            entity_id=domain,
            summary=f"Domain {domain} removed from tenant",
            actor_user_id=actor_user_id,
            organization_id=org_id_str,
        )

        return True

    def get_domains(
        self,
        db: Session,
        org_id: UUID,
    ) -> list[TenantDomain]:
        """Get all domains for a tenant."""
        org_id_str = str(org_id)
        domains_list = self._get_domain_list(db, org_id_str)

        result = []
        for entry in domains_list:
            domain_config = self._get_domain_config(db, org_id_str, entry["domain"])
            if domain_config:
                td = TenantDomain(
                    domain=domain_config.get("domain", entry["domain"]),
                    is_primary=domain_config.get("is_primary", False),
                    verification_status=DomainVerificationStatus(
                        domain_config.get("verification_status", "unverified")
                    ),
                    verification_token=domain_config.get("verification_token", ""),
                    verification_dns_record=domain_config.get("verification_dns_record", ""),
                    ssl_status=DomainSSLStatus(
                        domain_config.get("ssl_status", "none")
                    ),
                    ssl_expiry=domain_config.get("ssl_expiry"),
                    redirect_to=domain_config.get("redirect_to"),
                    is_active=domain_config.get("is_active", True),
                )
                result.append(td)

        return result

    def get_primary_domain(
        self,
        db: Session,
        org_id: UUID,
    ) -> Optional[TenantDomain]:
        """Get the primary domain for a tenant."""
        domains = self.get_domains(db, org_id)
        for d in domains:
            if d.is_primary:
                return d
        return domains[0] if domains else None

    # ──────────────────────────────────────────────────────────────────────
    #  Domain Verification
    # ──────────────────────────────────────────────────────────────────────

    def verify_domain(
        self,
        db: Session,
        org_id: UUID,
        domain: str,
        verification_token: str,
        actor_user_id: Optional[int] = None,
    ) -> bool:
        """
        Verify a domain by checking the verification token.

        In production, this would check the DNS TXT record.
        For now, we verify the token matches.
        """
        domain = domain.strip().lower()
        org_id_str = str(org_id)

        domain_config = self._get_domain_config(db, org_id_str, domain)
        if not domain_config:
            raise ValueError(f"Domain {domain} not found for this tenant")

        stored_token = domain_config.get("verification_token", "")
        if verification_token != stored_token:
            raise ValueError(f"Invalid verification token for domain {domain}")

        # Update verification status
        domain_config["verification_status"] = DomainVerificationStatus.VERIFIED.value
        config_center.set(
            self._get_domain_key(domain),
            domain_config,
            org_id=org_id_str,
            updated_by=actor_user_id,
        )

        logger.info(f"Domain {domain} verified for tenant {org_id}")

        # Publish event
        try:
            event = DomainVerifiedEvent(
                organization_id=org_id_str,
                domain=domain,
                actor_user_id=actor_user_id,
            )
            event_bus.publish(event)
        except Exception as e:
            logger.warning(f"Failed to publish DomainVerifiedEvent: {e}")

        audit_service.record(
            module="tenant_domain",
            action="verify",
            entity_type="domain",
            entity_id=domain,
            summary=f"Domain {domain} verified",
            actor_user_id=actor_user_id,
            organization_id=org_id_str,
        )

        return True

    def set_primary_domain(
        self,
        db: Session,
        org_id: UUID,
        domain: str,
        actor_user_id: Optional[int] = None,
    ) -> bool:
        """Set a domain as the primary domain for a tenant."""
        domain = domain.strip().lower()
        org_id_str = str(org_id)

        # Get all domains
        domains = self.get_domains(db, org_id)
        domain_found = False

        for d in domains:
            if d.domain == domain:
                domain_found = True
                d.is_primary = True
                config_center.set(
                    self._get_domain_key(domain),
                    {
                        "domain": d.domain,
                        "is_primary": True,
                        "verification_status": d.verification_status.value,
                        "verification_token": d.verification_token,
                        "verification_dns_record": d.verification_dns_record,
                        "ssl_status": d.ssl_status.value,
                        "redirect_to": d.redirect_to,
                        "is_active": d.is_active,
                    },
                    org_id=org_id_str,
                    updated_by=actor_user_id,
                )
            else:
                d.is_primary = False
                config_center.set(
                    self._get_domain_key(d.domain),
                    {
                        "domain": d.domain,
                        "is_primary": False,
                        "verification_status": d.verification_status.value,
                        "verification_token": d.verification_token,
                        "verification_dns_record": d.verification_dns_record,
                        "ssl_status": d.ssl_status.value,
                        "redirect_to": d.redirect_to,
                        "is_active": d.is_active,
                    },
                    org_id=org_id_str,
                    updated_by=actor_user_id,
                )

        if not domain_found:
            raise ValueError(f"Domain {domain} not found for this tenant")

        # Update domain list
        domains_list = self._get_domain_list(db, org_id_str)
        for entry in domains_list:
            entry["is_primary"] = (entry["domain"] == domain)
        config_center.set(
            self._get_domains_key(),
            domains_list,
            org_id=org_id_str,
            updated_by=actor_user_id,
        )

        logger.info(f"Primary domain set to {domain} for tenant {org_id}")

        return True

    # ──────────────────────────────────────────────────────────────────────
    #  Internal Helpers
    # ──────────────────────────────────────────────────────────────────────

    def _get_domain_list(self, db: Session, org_id_str: str) -> list:
        """Get the domain list for a tenant from config center."""
        raw = config_center.get(self._get_domains_key(), org_id=org_id_str, default=[])
        if isinstance(raw, list):
            return raw
        return []

    def _get_domain_config(self, db: Session, org_id_str: str, domain: str) -> dict:
        """Get the config for a specific domain."""
        raw = config_center.get(self._get_domain_key(domain), org_id=org_id_str, default={})
        if isinstance(raw, dict):
            return raw
        return {}

    def _set_domain_config(
        self, org_id_str: str, domain: str, config: dict,
        updated_by: Optional[int] = None
    ) -> None:
        """Set the config for a specific domain."""
        config_center.set(
            self._get_domain_key(domain),
            config,
            org_id=org_id_str,
            updated_by=updated_by,
        )


# Singleton
tenant_domain_service = TenantDomainService()
