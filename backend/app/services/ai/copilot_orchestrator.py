"""
copilot_orchestrator.py — Enterprise AI Copilot Permission-Aware Orchestrator
Sprint 8 — Enterprise AI Copilot Expansion

Orchestrates:
1. Intent classification from natural language queries
2. Permission validation BEFORE data access
3. Controlled tool execution via TOOL_REGISTRY only
4. Secure response synthesis (no raw SQL, no credentials, no internal errors)
5. Audit logging of every request, tool call, and authorization decision

SECURITY PRINCIPLES:
- LLM never receives DB credentials or raw connection strings
- Data authorization happens BEFORE reaching the LLM
- All tool results are validated and sanitized before synthesis
- Prompt injection defenses via input sanitization
- Sensitive fields are redacted in tool responses
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.ai.copilot_tools import (
    TOOL_PERMISSION_MAP, TOOL_REGISTRY, list_tools, get_tool,
)
from app.services.audit_service import audit_service
from app.services.event_bus import event_bus

logger = logging.getLogger(__name__)

# ── Intent Patterns ───────────────────────────────────────────────────────────
# Map intent names to (tool_name, query_keywords)
_INTENT_PATTERNS: list[tuple[str, str, list[str]]] = [
    ("attendance_summary",    "get_attendance_summary",    ["attendance", "absent", "present", "late", "checked in"]),
    ("payroll_summary",       "get_payroll_summary",       ["payroll", "salary", "pay", "payslip", "net pay"]),
    ("payroll_run_status",    "get_payroll_run_status",    ["payroll run", "payroll status", "payroll pending"]),
    ("reimbursement_summary", "get_reimbursement_summary", ["reimbursement", "expense", "claim", "pending claim"]),
    ("headcount",             "get_headcount",             ["headcount", "total employee", "how many employee", "employee count"]),
    ("workforce_metrics",     "get_workforce_metrics",     ["workforce", "team size", "department size", "role distribution"]),
    ("employee_attendance",   "get_employee_attendance",   ["attendance for employee", "employee attendance"]),
]

# ── Prompt injection patterns to reject ───────────────────────────────────────
_INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|above) instruction",
    r"forget (your|all|the) (rules|instruction|system prompt)",
    r"you are now",
    r"act as (an? )?(unrestricted|jailbreak|dan|evil)",
    r"(drop|delete|truncate|alter|insert|update)\s+(table|database|db)",
    r"system prompt",
    r"reveal (your )?prompt",
    r"print (the )?password",
    r"show (the )?credentials",
    r"(api|secret) key",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def _sanitize_query(query: str) -> tuple[bool, str]:
    """
    Returns (is_safe, cleaned_query).
    Strips excessive whitespace; detects injection attempts.
    """
    cleaned = query.strip()[:2000]  # Hard limit
    if _INJECTION_RE.search(cleaned):
        return False, cleaned
    return True, cleaned


def _classify_intent(query: str) -> Optional[tuple[str, str]]:
    """
    Simple keyword-based intent classifier.
    Returns (intent_name, tool_name) or None.
    """
    q_lower = query.lower()
    for intent, tool, keywords in _INTENT_PATTERNS:
        if any(kw in q_lower for kw in keywords):
            return intent, tool
    return None


def _user_has_permission(user_permissions: list[str], required: list[str]) -> bool:
    """Check if user holds any of the required permissions. SuperAdmin passes."""
    if not required:
        return True
    return any(p in user_permissions for p in required)


# ─────────────────────────────────────────────────────────────────────────────
#  Main Orchestration Entry Point
# ─────────────────────────────────────────────────────────────────────────────

class CopilotOrchestrator:
    """
    Enterprise AI Copilot Orchestrator.

    Flow:
        sanitize → classify intent → check permission → execute tool
        → compose response → audit
    """

    def process(
        self,
        db: Session,
        query: str,
        org_id: Any,
        actor_user_id: Optional[int],
        user_permissions: list[str],
        user_role: str = "",
        correlation_id: str = "",
        tool_kwargs: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Synchronous orchestration — safe for FastAPI sync routes.
        Returns structured CopilotToolResponse.
        """
        correlation_id = correlation_id or f"cop-{uuid.uuid4().hex[:12]}"
        tool_kwargs = tool_kwargs or {}
        is_superadmin = user_role.lower() in {"superadmin", "super admin"}

        # ── 1. Input Sanitization ─────────────────────────────────────────────
        is_safe, cleaned_query = _sanitize_query(query)
        if not is_safe:
            self._audit_denied(actor_user_id, org_id, query, "prompt_injection_detected", correlation_id)
            return self._denied_response(
                query=cleaned_query,
                reason="Query contains disallowed patterns and cannot be processed.",
                correlation_id=correlation_id,
            )

        # ── 2. Intent Classification ──────────────────────────────────────────
        intent_result = _classify_intent(cleaned_query)
        if not intent_result:
            self._audit_query(actor_user_id, org_id, cleaned_query, "unknown_intent", None, correlation_id)
            return self._generic_response(cleaned_query, correlation_id)

        intent_name, tool_name = intent_result

        # ── 3. Permission Check (BEFORE data access) ──────────────────────────
        required_perms = TOOL_PERMISSION_MAP.get(tool_name, [])
        if not is_superadmin and not _user_has_permission(user_permissions, required_perms):
            self._audit_denied(actor_user_id, org_id, cleaned_query, f"missing_permission:{required_perms}", correlation_id)
            return self._denied_response(
                query=cleaned_query,
                reason="You do not have permission to access this information.",
                correlation_id=correlation_id,
            )

        # ── 4. Execute Tool ────────────────────────────────────────────────────
        tool_fn = get_tool(tool_name)
        if not tool_fn:
            return self._error_response(cleaned_query, "Requested capability is not available.", correlation_id)

        try:
            result = tool_fn(db, org_id, actor_user_id=actor_user_id, **tool_kwargs)
        except Exception as e:
            logger.error("Tool '%s' execution failed: %s", tool_name, e)
            self._audit_query(actor_user_id, org_id, cleaned_query, intent_name, tool_name, correlation_id, error=str(e))
            return self._error_response(cleaned_query, "An error occurred while retrieving data.", correlation_id)

        # ── 5. Compose Response ───────────────────────────────────────────────
        self._audit_query(actor_user_id, org_id, cleaned_query, intent_name, tool_name, correlation_id)
        # Emit domain event
        try:
            event_bus.publish(
                "copilot.query.executed",
                tenant_id=str(org_id),
                payload={"intent": intent_name, "tool": tool_name, "query_length": len(cleaned_query)},
                actor_id=actor_user_id,
                correlation_id=correlation_id,
            )
        except Exception:
            pass

        return {
            "success": result.get("status") in {"success", "empty"},
            "answer": self._synthesize_answer(intent_name, result),
            "intent": intent_name,
            "tool": tool_name,
            "data": result.get("data", []),
            "summary": result.get("summary", ""),
            "suggestions": self._follow_up_suggestions(intent_name),
            "actions": self._suggested_actions(intent_name),
            "correlation_id": correlation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── Response Synthesizers ─────────────────────────────────────────────────

    def _synthesize_answer(self, intent: str, result: dict) -> str:
        if result.get("status") == "empty":
            return result.get("summary", "No data found for your query.")
        if result.get("status") == "error":
            return "I was unable to retrieve that information. Please check your permissions or try again later."
        return result.get("summary", "Here is what I found.")

    def _denied_response(self, query: str, reason: str, correlation_id: str) -> dict:
        return {
            "success": False,
            "answer": reason,
            "intent": "denied",
            "tool": None,
            "data": [],
            "summary": reason,
            "suggestions": ["Ask about data you have access to."],
            "actions": [],
            "correlation_id": correlation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _error_response(self, query: str, msg: str, correlation_id: str) -> dict:
        return {
            "success": False,
            "answer": msg,
            "intent": "error",
            "tool": None,
            "data": [],
            "summary": msg,
            "suggestions": [],
            "actions": [],
            "correlation_id": correlation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _generic_response(self, query: str, correlation_id: str) -> dict:
        return {
            "success": True,
            "answer": (
                "I can help you with attendance, payroll summaries, workforce metrics, "
                "headcount, and reimbursement information. Try asking: 'How many employees "
                "were absent today?' or 'What is the current payroll status?'"
            ),
            "intent": "unknown",
            "tool": None,
            "data": [],
            "summary": "No specific data query matched. Showing capabilities.",
            "suggestions": [
                "How many employees were absent this month?",
                "Show payroll summary for this period",
                "What is the current headcount?",
                "Show pending reimbursements",
            ],
            "actions": [{"type": "navigate", "label": "View Dashboard", "url": "/dashboard"}],
            "correlation_id": correlation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _follow_up_suggestions(self, intent: str) -> list[str]:
        suggestions_map = {
            "attendance_summary": ["Show late arrivals this month", "Which departments have highest absenteeism?"],
            "payroll_summary":    ["Show payroll run status", "Show pending reimbursements"],
            "headcount":          ["Show workforce metrics by role", "Show attendance summary"],
            "workforce_metrics":  ["Show headcount breakdown", "Show attendance trends"],
            "reimbursement_summary": ["Show payroll summary", "Show pending approvals"],
        }
        return suggestions_map.get(intent, ["Ask me another workforce question"])

    def _suggested_actions(self, intent: str) -> list[dict]:
        actions_map = {
            "attendance_summary": [{"type": "navigate", "label": "Open Attendance Dashboard", "url": "/dashboard/workforce/attendance"}],
            "payroll_summary":    [{"type": "navigate", "label": "Open Payroll Dashboard",    "url": "/dashboard/payroll"}],
            "reimbursement_summary": [{"type": "navigate", "label": "Open Reimbursements",   "url": "/dashboard/reimbursements"}],
            "headcount":          [{"type": "navigate", "label": "View All Employees",        "url": "/dashboard/users"}],
        }
        return actions_map.get(intent, [])

    # ── Audit Helpers ─────────────────────────────────────────────────────────

    def _audit_query(
        self, actor_id: Optional[int], org_id: Any, query: str,
        intent: str, tool: Optional[str], correlation_id: str, error: Optional[str] = None,
    ) -> None:
        try:
            audit_service.record(
                module="copilot",
                action="copilot_query",
                entity_type="copilot_query",
                entity_id=correlation_id,
                summary=f"Copilot query: intent={intent}, tool={tool}",
                details={"intent": intent, "tool": tool, "query_length": len(query), "error": error},
                organization_id=str(org_id),
                actor_user_id=actor_id,
            )
        except Exception:
            pass

    def _audit_denied(
        self, actor_id: Optional[int], org_id: Any,
        query: str, reason: str, correlation_id: str,
    ) -> None:
        try:
            audit_service.record(
                module="copilot",
                action="copilot_query_denied",
                entity_type="copilot_security",
                entity_id=correlation_id,
                summary=f"Copilot query denied: {reason}",
                details={"reason": reason, "query_length": len(query)},
                organization_id=str(org_id),
                actor_user_id=actor_id,
            )
            event_bus.publish(
                "copilot.query.denied",
                tenant_id=str(org_id),
                payload={"reason": reason},
                actor_id=actor_id,
                correlation_id=correlation_id,
            )
        except Exception:
            pass


# Singleton
copilot_orchestrator = CopilotOrchestrator()
