"""
ai_governance.py — Enterprise AI Governance Controls
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Implements governance controls for the AI platform:
- Prompt versioning and change tracking
- Model versioning and capability management
- AI decision audit logging with full traceability
- Usage analytics per provider/model/tenant
- Cost analytics and budget tracking
- Safety policy enforcement (strict, moderate, relaxed)
- Tenant AI configuration management
- Provider failover and redundancy
- Compliance reporting for AI operations
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from app.schema.ai import (
    AIAuditEntry,
    AISafetyPolicy,
    AIUsageSummary,
    PromptTemplate,
    TenantAIConfig,
)
from app.services.audit_service import audit_service
from app.services.ai_cost_tracker import ai_cost_tracker
from app.services.notification_service import (
    NotificationChannel,
    NotificationPriority,
    notification_service,
)

logger = logging.getLogger(__name__)


class AIGovernance:
    """
    Enterprise AI governance controls.

    Manages:
    - Prompt versioning with content hashing
    - Model versioning and lifecycle
    - AI decision traceability
    - Safety policy enforcement
    - Tenant-scoped AI configuration
    - Provider failover policies
    - Compliance and audit reporting
    """

    def __init__(self):
        self._prompt_versions: dict[str, list[dict]] = defaultdict(list)  # prompt_id -> versions
        self._model_versions: dict[str, list[dict]] = defaultdict(list)  # model_id -> versions
        self._audit_trail: list[AIAuditEntry] = []
        self._max_audit_entries: int = 100000
        self._safety_policies: dict[str, AISafetyPolicy] = {}
        self._tenant_ai_configs: dict[str, TenantAIConfig] = {}

    # =========================================================================
    #  Prompt Versioning
    # =========================================================================

    def create_prompt_version(
        self,
        prompt_id: str,
        name: str,
        template: str,
        version: str,
        variables: list[str] | None = None,
        created_by: Optional[int] = None,
    ) -> dict:
        """Create a new version of a prompt template."""
        version_id = f"pv-{uuid.uuid4().hex[:12]}"
        content_hash = hashlib.sha256(template.encode()).hexdigest()

        version_entry = {
            "version_id": version_id,
            "prompt_id": prompt_id,
            "name": name,
            "version": version,
            "template": template,
            "variables": variables or [],
            "content_hash": content_hash,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True,
        }
        self._prompt_versions[prompt_id].append(version_entry)

        # Deactivate previous versions
        for v in self._prompt_versions[prompt_id]:
            if v["version_id"] != version_id:
                v["is_active"] = False

        logger.info(f"Prompt version created: {name} v{version} ({version_id})")
        return version_entry

    def get_prompt_versions(self, prompt_id: str) -> list[dict]:
        """Get all versions of a prompt."""
        return self._prompt_versions.get(prompt_id, [])

    def get_active_prompt_version(self, prompt_id: str) -> Optional[dict]:
        """Get the active version of a prompt."""
        versions = self._prompt_versions.get(prompt_id, [])
        for v in versions:
            if v.get("is_active"):
                return v
        return versions[-1] if versions else None

    def rollback_prompt(self, prompt_id: str, version_id: str) -> bool:
        """Rollback a prompt to a specific version."""
        versions = self._prompt_versions.get(prompt_id, [])
        target = None
        for v in versions:
            if v["version_id"] == version_id:
                target = v
                v["is_active"] = True
            else:
                v["is_active"] = False

        if target:
            logger.info(f"Prompt rolled back: {prompt_id} -> v{target.get('version')}")
            return True
        return False

    # =========================================================================
    #  Model Versioning
    # =========================================================================

    def register_model_version(
        self,
        model_id: str,
        model_name: str,
        provider_id: str,
        version: str,
        capabilities: list[str],
        context_window: int,
        created_by: Optional[int] = None,
    ) -> dict:
        """Register a new model version."""
        version_id = f"mv-{uuid.uuid4().hex[:12]}"

        version_entry = {
            "version_id": version_id,
            "model_id": model_id,
            "model_name": model_name,
            "provider_id": provider_id,
            "version": version,
            "capabilities": capabilities,
            "context_window": context_window,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True,
            "deprecated_at": None,
        }
        self._model_versions[model_id].append(version_entry)
        logger.info(f"Model version registered: {model_name} v{version} ({version_id})")
        return version_entry

    def deprecate_model_version(self, model_id: str, version_id: str) -> bool:
        """Deprecate a model version."""
        versions = self._model_versions.get(model_id, [])
        for v in versions:
            if v["version_id"] == version_id:
                v["is_active"] = False
                v["deprecated_at"] = datetime.now(timezone.utc).isoformat()
                logger.info(f"Model version deprecated: {model_id} v{v.get('version')}")
                return True
        return False

    def get_active_models(self, provider_id: Optional[str] = None) -> list[dict]:
        """Get all active model versions."""
        active = []
        for model_id, versions in self._model_versions.items():
            for v in versions:
                if v.get("is_active"):
                    if provider_id and v.get("provider_id") != provider_id:
                        continue
                    active.append(v)
        return active

    # =========================================================================
    #  AI Decision Audit Trail
    # =========================================================================

    def record_decision(
        self,
        event_type: str,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        prompt_text: Optional[str] = None,
        response_text: Optional[str] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[str] = None,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        latency_ms: float = 0.0,
        safety_flagged: bool = False,
        safety_action: Optional[str] = None,
        status: str = "completed",
        error: Optional[str] = None,
    ) -> AIAuditEntry:
        """Record an AI decision for audit trail."""
        entry = AIAuditEntry(
            id=str(uuid.uuid4()),
            event_type=event_type,
            provider_id=provider_id,
            model_id=model_id,
            prompt_version=prompt_version,
            prompt_text=prompt_text,
            response_text=response_text,
            user_id=user_id,
            organization_id=organization_id,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            safety_flagged=safety_flagged,
            safety_action=safety_action,
            status=status,
            error=error,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._audit_trail.append(entry)

        # Trim history
        if len(self._audit_trail) > self._max_audit_entries:
            self._audit_trail = self._audit_trail[-self._max_audit_entries:]

        return entry

    def search_audit_trail(
        self,
        organization_id: Optional[str] = None,
        event_type: Optional[str] = None,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AIAuditEntry], int]:
        """Search AI audit trail."""
        results = self._audit_trail

        if organization_id:
            results = [e for e in results if e.organization_id == organization_id]
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if status:
            results = [e for e in results if e.status == status]

        total = len(results)
        page = results[offset:offset + limit]
        return page, total

    # =========================================================================
    #  Safety Policy Enforcement
    # =========================================================================

    def check_safety(self, prompt: str, response: str,
                     policy: AISafetyPolicy = AISafetyPolicy.MODERATE) -> tuple[bool, Optional[str]]:
        """
        Check content against safety policy.

        Returns:
            Tuple of (is_safe, action_taken)
        """
        flagged_keywords = {
            AISafetyPolicy.STRICT: [
                "ignore previous", "bypass", "hack", "exploit",
                "malicious", "illegal", "unauthorized access",
            ],
            AISafetyPolicy.MODERATE: [
                "bypass", "hack", "exploit", "malicious",
            ],
            AISafetyPolicy.RELAXED: [],
        }

        keywords = flagged_keywords.get(policy, [])
        combined_text = f"{prompt} {response}".lower()

        for keyword in keywords:
            if keyword in combined_text:
                logger.warning(f"Safety policy violation detected: '{keyword}'")
                return False, f"Content flagged: contains prohibited term '{keyword}'"

        return True, None

    def set_safety_policy(self, organization_id: str, policy: AISafetyPolicy) -> None:
        """Set safety policy for an organization."""
        self._safety_policies[organization_id] = policy
        logger.info(f"Safety policy set for org {organization_id}: {policy.value}")

    def get_safety_policy(self, organization_id: str) -> AISafetyPolicy:
        """Get safety policy for an organization."""
        return self._safety_policies.get(organization_id, AISafetyPolicy.MODERATE)

    # =========================================================================
    #  Tenant AI Configuration
    # =========================================================================

    def configure_tenant(
        self, org_id: str, config: TenantAIConfig
    ) -> TenantAIConfig:
        """Configure AI settings for a tenant."""
        self._tenant_ai_configs[org_id] = config
        logger.info(f"AI configuration updated for org {org_id}")
        return config

    def get_tenant_config(self, org_id: str) -> Optional[TenantAIConfig]:
        """Get AI configuration for a tenant."""
        return self._tenant_ai_configs.get(org_id)

    # =========================================================================
    #  Compliance & Reporting
    # =========================================================================

    def get_compliance_report(
        self, organization_id: Optional[str] = None
    ) -> dict:
        """Generate AI governance compliance report."""
        entries, total = self.search_audit_trail(organization_id=organization_id, limit=0)

        # Safety stats
        safety_flagged = sum(1 for e in entries if e.safety_flagged)
        failed = sum(1 for e in entries if e.status == "failed")

        # Event type breakdown
        by_event = defaultdict(int)
        for e in entries:
            by_event[e.event_type] += 1

        # Provider breakdown
        by_provider = defaultdict(int)
        for e in entries:
            if e.provider_id:
                by_provider[e.provider_id] += 1

        return {
            "total_decisions": total,
            "safety_flagged": safety_flagged,
            "safety_rate": round(safety_flagged / max(total, 1) * 100, 2),
            "failed_requests": failed,
            "failure_rate": round(failed / max(total, 1) * 100, 2),
            "by_event_type": dict(by_event),
            "by_provider": dict(by_provider),
            "safety_policy": self.get_safety_policy(organization_id or "global").value,
        }

    def get_dashboard(self) -> dict:
        """Get AI governance dashboard data."""
        return {
            "prompt_versions": sum(len(v) for v in self._prompt_versions.values()),
            "model_versions": sum(len(v) for v in self._model_versions.values()),
            "audit_entries": len(self._audit_trail),
            "safety_policies_configured": len(self._safety_policies),
            "tenant_configs": len(self._tenant_ai_configs),
            "recent_audit": self._audit_trail[-10:] if self._audit_trail else [],
            "safety_policy": self.get_safety_policy("global").value,
        }


# Singleton
ai_governance = AIGovernance()

