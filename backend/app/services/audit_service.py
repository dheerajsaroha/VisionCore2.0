<<<<<<< HEAD
"""
audit_service.py — Centralized Enterprise Audit Service
Sprint 5 — Phase B: Enterprise Platform Integration

Collects audit events from all modules:
- Authentication
- EAAC
- Workflow
- HR
- Performance
- Policies
- Assets

Provides:
- Audit Timeline
- Audit Search
- Audit Export
- Risk Detection
- Compliance Reports
- Immutable audit history
"""
from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
=======
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from typing import Any, Optional, Mapping

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.all_models import User
>>>>>>> refs/remotes/origin/main

logger = logging.getLogger(__name__)


<<<<<<< HEAD
class AuditAction(Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    APPROVE = "approve"
    REJECT = "reject"
    SUBMIT = "submit"
    ASSIGN = "assign"
    TRANSFER = "transfer"
    REVOKE = "revoke"
    EXPORT = "export"
    GENERATE = "generate"
    SYSTEM = "system"


class AuditSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AuditEntry:
    """Single immutable audit record containing all 13 canonical enterprise metadata fields."""
    id: str = ""
    tenant_id: str = ""
    organization_id: str = ""
    actor_user_id: Optional[int] = None
    action: str = ""
    entity_type: str = ""
    entity_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: str = ""
    ip_address: str = ""
    user_agent: str = ""
    old_values: dict = field(default_factory=dict)
    new_values: dict = field(default_factory=dict)
    source_service: str = ""
    # Optional supplementary fields for UI & backward compatibility
    actor_email: str = ""
    summary: str = ""
    details: dict = field(default_factory=dict)
    severity: str = "info"
    immutable: bool = True  # Once written, never modified


class AuditService:
    """
    Centralized, append-only audit service.
    All audit entries are immutable once created.
    """

    def __init__(self):
        self._entries: list[AuditEntry] = []
        self._max_entries: int = 100000

    def record(
        self,
        actor_user_id: int | None = None,
        actor_email: str = "",
        organization_id: str = "",
        tenant_id: str = "",
        module: str = "",
        source_service: str = "",
        action: str = "",
        entity_type: str = "",
        entity_id: str = "",
        summary: str = "",
        details: dict | None = None,
        old_values: dict | None = None,
        new_values: dict | None = None,
        correlation_id: str = "",
        severity: str = "info",
        ip_address: str = "",
        user_agent: str = "",
    ) -> AuditEntry:
        """Record an immutable audit entry enforcing the 13 canonical fields."""
        resolved_tenant_id = tenant_id or organization_id
        resolved_source_service = source_service or module or "platform"

        entry = AuditEntry(
            id=self._generate_id(),
            tenant_id=resolved_tenant_id,
            organization_id=organization_id or resolved_tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
            old_values=old_values or {},
            new_values=new_values or {},
            source_service=resolved_source_service,
            actor_email=actor_email,
            summary=summary or f"{action} on {entity_type}:{entity_id}",
            details=details or {},
            severity=severity,
        )
        self._entries.append(entry)

        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

        logger.info(
            f"Audit: [{severity.upper()}] correlation={correlation_id} "
            f"{resolved_source_service}.{action} on {entity_type}:{entity_id} by actor {actor_user_id}"
        )
        return entry

    # ------------------------------------------------------------------
    #  Convenience Methods
    # ------------------------------------------------------------------

    def record_login(
        self,
        user_id: int,
        email: str,
        organization_id: str,
        success: bool,
        ip_address: str = "",
        failure_reason: str = "",
    ) -> AuditEntry:
        return self.record(
            actor_user_id=user_id,
            actor_email=email,
            organization_id=organization_id,
            module="authentication",
            action="login",
            entity_type="user_session",
            summary=f"User login {'successful' if success else 'failed'}: {email}",
            details={"success": success, "failure_reason": failure_reason},
            severity="info" if success else "warning",
            ip_address=ip_address,
        )

    def record_permission_change(
        self,
        actor_user_id: int,
        target_user_id: int,
        organization_id: str,
        permission: str,
        action: str,
    ) -> AuditEntry:
        return self.record(
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            module="eaac",
            action=action,
            entity_type="permission",
            summary=f"Permission '{permission}' {action}d for user {target_user_id}",
            details={"target_user_id": target_user_id, "permission": permission},
            severity="warning",
        )

    def record_workflow_action(
        self,
        actor_user_id: int,
        request_id: int,
        organization_id: str,
        entity_type: str,
        action: str,
        details: dict | None = None,
    ) -> AuditEntry:
        return self.record(
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            module="workflow",
            action=action,
            entity_type=entity_type,
            entity_id=str(request_id),
            summary=f"Workflow request {request_id} {action}d",
            details=details,
            severity="info",
        )

    def record_data_change(
        self,
        actor_user_id: int,
        organization_id: str,
        module: str,
        entity_type: str,
        entity_id: str,
        action: str,
        summary: str,
        changes: dict | None = None,
    ) -> AuditEntry:
        return self.record(
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            module=module,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            details={"changes": changes or {}},
            severity="info",
        )

    def record_security_event(
        self,
        organization_id: str,
        event_type: str,
        summary: str,
        details: dict | None = None,
        severity: str = "critical",
    ) -> AuditEntry:
        return self.record(
            organization_id=organization_id,
            module="security",
            action=event_type,
            entity_type="security_event",
            summary=summary,
            details=details,
            severity=severity,
        )

    # ------------------------------------------------------------------
    #  Query & Search
    # ------------------------------------------------------------------

    def search(
        self,
        organization_id: str | None = None,
        module: str | None = None,
        action: str | None = None,
        actor_user_id: int | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        severity: str | None = None,
        search_text: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> tuple[list[dict], int]:
        """Search audit entries with filters. Returns (results, total_count)."""
        results = self._entries

        if organization_id:
            results = [e for e in results if e.organization_id == organization_id]
        if module:
            results = [e for e in results if e.module == module]
        if action:
            results = [e for e in results if e.action == action]
        if actor_user_id:
            results = [e for e in results if e.actor_user_id == actor_user_id]
        if entity_type:
            results = [e for e in results if e.entity_type == entity_type]
        if entity_id:
            results = [e for e in results if e.entity_id == entity_id]
        if severity:
            results = [e for e in results if e.severity == severity]
        if search_text:
            search_lower = search_text.lower()
            results = [
                e
                for e in results
                if search_lower in e.summary.lower()
                or search_lower in e.module.lower()
                or search_lower in e.entity_type.lower()
            ]
        if start_date:
            results = [e for e in results if e.timestamp >= start_date]
        if end_date:
            results = [e for e in results if e.timestamp <= end_date]

        # Sort
            results.sort(key=lambda e: e.timestamp, reverse=sort_desc)

        total = len(results)
        page = results[offset:offset + limit]
        return [self._entry_to_dict(e) for e in page], total

    def get_timeline(
        self,
        organization_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Get chronological audit timeline for an organization."""
        return self.search(
            organization_id=organization_id,
            limit=limit,
            offset=offset,
            sort_desc=True,
        )

    def get_module_summary(
        self, organization_id: str, module: str
    ) -> dict:
        """Get summary stats for a specific module."""
        entries, _ = self.search(organization_id=organization_id, module=module, limit=0)
        actions = {}
        severities = {}
        for e in entries:
            actions[e.action] = actions.get(e.action, 0) + 1
            severities[e.severity] = severities.get(e.severity, 0) + 1
        return {
            "module": module,
            "total": len(entries),
            "actions": actions,
            "severities": severities,
        }

    def get_risk_alerts(
        self,
        organization_id: str,
        min_severity: str = "warning",
        limit: int = 50,
    ) -> list[dict]:
        """Get high-severity audit entries for risk detection."""
        results = [
            e
            for e in self._entries
            if e.organization_id == organization_id
            and e.severity in ("warning", "critical")
            and (
                (min_severity == "warning" and e.severity in ("warning", "critical"))
                or (min_severity == "critical" and e.severity == "critical")
            )
        ]
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return [self._entry_to_dict(e) for e in results[:limit]]

    def get_compliance_summary(
        self, organization_id: str
    ) -> dict:
        """Get compliance-oriented audit summary."""
        entries, _ = self.search(organization_id=organization_id, limit=0)
        by_module = {}
        for e in entries:
            if e.module not in by_module:
                by_module[e.module] = {"total": 0, "actions": set()}
            by_module[e.module]["total"] += 1
            by_module[e.module]["actions"].add(e.action)

        return {
            "organization_id": organization_id,
            "total_audit_entries": len(entries),
            "modules_tracked": list(by_module.keys()),
            "by_module": {
                m: {"total": d["total"], "actions": list(d["actions"])}
                for m, d in by_module.items()
            },
            "critical_events": sum(
                1 for e in entries if e.severity == "critical"
            ),
            "warning_events": sum(
                1 for e in entries if e.severity == "warning"
            ),
        }

    # ------------------------------------------------------------------
    #  Export
    # ------------------------------------------------------------------

    def export_csv(
        self,
        organization_id: str | None = None,
        module: str | None = None,
        limit: int = 10000,
    ) -> str:
        """Export audit entries as CSV string."""
        entries, _ = self.search(
            organization_id=organization_id,
            module=module,
            limit=limit,
        )
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "id", "timestamp", "actor_user_id", "actor_email",
                "organization_id", "module", "action", "entity_type",
                "entity_id", "summary", "severity", "ip_address",
            ],
        )
        writer.writeheader()
        for entry in entries:
            writer.writerow({k: entry.get(k, "") for k in writer.fieldnames})
        return output.getvalue()

    def export_json(
        self,
        organization_id: str | None = None,
        module: str | None = None,
        limit: int = 10000,
    ) -> str:
        """Export audit entries as JSON string."""
        entries, _ = self.search(
            organization_id=organization_id,
            module=module,
            limit=limit,
        )
        return json.dumps(entries, indent=2, default=str)

    # ------------------------------------------------------------------
    #  Internal
    # ------------------------------------------------------------------

    def _generate_id(self) -> str:
        import uuid
        return str(uuid.uuid4())

    @staticmethod
    def _entry_to_dict(entry: AuditEntry) -> dict:
        return {
            "id": entry.id,
            "tenant_id": entry.tenant_id,
            "organization_id": entry.organization_id,
            "actor_user_id": entry.actor_user_id,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "timestamp": entry.timestamp,
            "correlation_id": entry.correlation_id,
            "ip_address": entry.ip_address,
            "user_agent": entry.user_agent,
            "old_values": entry.old_values,
            "new_values": entry.new_values,
            "source_service": entry.source_service,
            "actor_email": entry.actor_email,
            "summary": entry.summary,
            "details": entry.details,
            "severity": entry.severity,
            "immutable": entry.immutable,
        }


# Singleton
audit_service = AuditService()
=======
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


SENSITIVE_KEYS = {
    # auth / session
    "token",
    "access_token",
    "refresh_token",
    # credential / password
    "password",
    "hashed_password",
    "new_password",
    "old_password",
    # biometrics
    "embedding",
    "face_embedding",
}


def _redact_value(key: str, value: Any) -> Any:
    if key in SENSITIVE_KEYS:
        return "[REDACTED]"
    return value


def _deep_redact(obj: Any) -> Any:
    """Redact sensitive fields from nested JSON-like structures."""
    if isinstance(obj, Mapping):
        redacted: dict[str, Any] = {}
        for k, v in obj.items():
            # Normalize keys to match SENSITIVE_KEYS
            ks = str(k)
            redacted[ks] = _deep_redact(_redact_value(ks, v))
        return redacted

    if isinstance(obj, list):
        return [_deep_redact(i) for i in obj]

    return obj


@dataclass(frozen=True)
class AuditLogEvent:
    action: str
    target_type: str
    target_id: str
    tenant_org_id: Optional[str]
    actor_user_id: Optional[int]
    actor_role_name: Optional[str]
    before_state: Optional[dict[str, Any]]
    after_state: Optional[dict[str, Any]]
    reason: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    correlation_id: Optional[str]
    status: str  # success|failure
    failure_reason: Optional[str] = None


class AuditService:
    """Enterprise audit logging service.

    Foundation scope:
    - persistence-only (no blockchain anchoring)
    - sensitive redaction
    - safe no-op when AUDIT_ENABLED is false
    """

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def enabled() -> bool:
        # Required by Phase 4.2.1 spec
        return bool(getattr(settings, "AUDIT_ENABLED", False))

    def log_event(self, event: AuditLogEvent):
        """Persist an audit event.

        If AUDIT_ENABLED is false, this is a safe no-op.
        """
        if not self.enabled():
            logger.debug("Audit disabled; skipping event action=%s", event.action)
            return None

        # Allow tests to monkeypatch the persistence model by overriding
        # AuditService.AuditLog (used by Phase 4.2 unit tests).
        AuditLog = getattr(self, "AuditLog", None)
        if AuditLog is None:
            from app.db.models.all_models import AuditLog  # local import to avoid circulars


        before_state = event.before_state
        after_state = event.after_state

        # redact
        before_state_redacted = _deep_redact(before_state) if before_state is not None else None
        after_state_redacted = _deep_redact(after_state) if after_state is not None else None

        audit = AuditLog(
            occurred_at=_utc_now(),
            tenant_org_id=event.tenant_org_id,
            actor_user_id=event.actor_user_id,
            actor_role_name=event.actor_role_name,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            before_state=before_state_redacted,
            after_state=after_state_redacted,
            reason=event.reason,
            ip_address=event.ip_address,
            user_agent=event.user_agent,
            correlation_id=event.correlation_id,
            status=event.status,
            failure_reason=event.failure_reason,
        )

        self.db.add(audit)
        self.db.commit()
        self.db.refresh(audit)
        return audit

    def log_create(
        self,
        *,
        actor: User,
        action: str,
        target_type: str,
        target_id: str,
        after_state: dict[str, Any],
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        tenant_org_id: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        return self.log_event(
            AuditLogEvent(
                action=action,
                target_type=target_type,
                target_id=str(target_id),
                tenant_org_id=tenant_org_id,
                actor_user_id=getattr(actor, "id", None),
                actor_role_name=getattr(getattr(actor, "role", None), "name", None),
                before_state=None,
                after_state=after_state,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
                correlation_id=correlation_id,
                status="success",
                failure_reason=None,
            )
        )

    def log_update(
        self,
        *,
        actor: User,
        action: str,
        target_type: str,
        target_id: str,
        before_state: dict[str, Any],
        after_state: dict[str, Any],
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        tenant_org_id: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        return self.log_event(
            AuditLogEvent(
                action=action,
                target_type=target_type,
                target_id=str(target_id),
                tenant_org_id=tenant_org_id,
                actor_user_id=getattr(actor, "id", None),
                actor_role_name=getattr(getattr(actor, "role", None), "name", None),
                before_state=before_state,
                after_state=after_state,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
                correlation_id=correlation_id,
                status="success",
                failure_reason=None,
            )
        )

    def log_delete(
        self,
        *,
        actor: User,
        action: str,
        target_type: str,
        target_id: str,
        before_state: dict[str, Any],
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        tenant_org_id: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        return self.log_event(
            AuditLogEvent(
                action=action,
                target_type=target_type,
                target_id=str(target_id),
                tenant_org_id=tenant_org_id,
                actor_user_id=getattr(actor, "id", None),
                actor_role_name=getattr(getattr(actor, "role", None), "name", None),
                before_state=before_state,
                after_state=None,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
                correlation_id=correlation_id,
                status="success",
                failure_reason=None,
            )
        )

    def log_failure(
        self,
        *,
        actor: Optional[User],
        action: str,
        target_type: str,
        target_id: str,
        failure_reason: str,
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        tenant_org_id: Optional[str] = None,
        reason: Optional[str] = None,
        before_state: Optional[dict[str, Any]] = None,
        after_state: Optional[dict[str, Any]] = None,
    ):
        return self.log_event(
            AuditLogEvent(
                action=action,
                target_type=target_type,
                target_id=str(target_id),
                tenant_org_id=tenant_org_id,
                actor_user_id=getattr(actor, "id", None) if actor else None,
                actor_role_name=getattr(getattr(actor, "role", None), "name", None) if actor else None,
                before_state=before_state,
                after_state=after_state,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
                correlation_id=correlation_id,
                status="failure",
                failure_reason=failure_reason,
            )
        )

>>>>>>> refs/remotes/origin/main
