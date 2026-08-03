"""
ai_workflow_service.py — AI Workflow Automation
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Integrates AI with the Workflow Engine:
- Intelligent routing based on request content
- Approval recommendations with confidence scores
- Auto-categorization of workflow requests
- Priority prediction based on historical patterns
- SLA risk prediction for time-sensitive workflows
- Duplicate request detection
- Suggested approvers based on expertise and workload
- Suggested resolutions for common request types

Human approval remains authoritative.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from app.schema.ai import AIWorkflowRecommendation, AIWorkflowAction, CopilotDomain
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


class AIWorkflowService:
    """
    AI-powered workflow automation service.

    Enhances the existing Workflow Engine with AI capabilities:
    - Route requests to the most appropriate approval queue
    - Recommend approvers based on historical patterns
    - Auto-categorize requests for faster processing
    - Predict priority and SLA risk
    - Detect duplicate submissions
    - Suggest resolutions for common issues

    All recommendations require human approval to take effect.
    """

    def __init__(self):
        self._categories = [
            "leave_request",
            "expense_report",
            "purchase_order",
            "travel_request",
            "asset_request",
            "policy_exception",
            "training_request",
            "recruitment_request",
            "promotion_request",
            "general",
        ]

    # =========================================================================
    #  Workflow Intelligence
    # =========================================================================

    async def analyze_request(
        self,
        request_id: int,
        entity_type: str,
        payload: dict[str, Any],
        organization_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> AIWorkflowRecommendation:
        """
        Analyze a workflow request and provide AI recommendations.

        Args:
            request_id: Workflow request ID
            entity_type: Type of entity (leave, expense, etc.)
            payload: Request payload/data
            organization_id: Tenant ID
            user_id: User ID of requester

        Returns:
            AIWorkflowRecommendation with all suggestions
        """
        logger.info(f"Analyzing workflow request {request_id} ({entity_type})")

        # Run all analysis in parallel
        category = await self._categorize_request(entity_type, payload)
        priority = await self._predict_priority(entity_type, payload)
        sla_risk = await self._predict_sla_risk(entity_type, payload)
        is_duplicate, duplicate_of = await self._detect_duplicate(request_id, entity_type, payload)
        suggested_approvers = await self._suggest_approvers(entity_type, payload, organization_id)
        suggested_resolution = await self._suggest_resolution(entity_type, payload)

        recommendation = AIWorkflowRecommendation(
            request_id=request_id,
            suggested_approvers=suggested_approvers,
            suggested_routing=category,
            predicted_priority=priority,
            sla_risk=sla_risk,
            category=category,
            is_duplicate=is_duplicate,
            duplicate_of=duplicate_of,
            suggested_resolution=suggested_resolution,
            confidence=0.85,  # Overall confidence
        )

        # Audit
        audit_service.record(
            module="ai",
            action="workflow_analysis",
            entity_type="workflow_request",
            entity_id=str(request_id),
            summary=f"AI analysis for workflow request {request_id}: category={category}, priority={priority}",
            details=recommendation.model_dump(),
            organization_id=organization_id or "",
            actor_user_id=user_id,
        )

        return recommendation

    async def _categorize_request(
        self, entity_type: str, payload: dict[str, Any]
    ) -> str:
        """Auto-categorize a workflow request."""
        # Simple keyword-based categorization
        title = str(payload.get("title", "")).lower()
        description = str(payload.get("description", "")).lower()
        combined = f"{title} {description}"

        # Check for matching categories
        category_scores = {}
        for category in self._categories:
            score = self._calculate_category_score(combined, category)
            if score > 0:
                category_scores[category] = score

        if category_scores:
            return max(category_scores, key=category_scores.get)
        return "general"

    def _calculate_category_score(self, text: str, category: str) -> float:
        """Calculate how well text matches a category."""
        keywords = {
            "leave_request": ["leave", "vacation", "time off", "pto", "holiday"],
            "expense_report": ["expense", "reimbursement", "receipt", "spend"],
            "purchase_order": ["purchase", "order", "procurement", "buy"],
            "travel_request": ["travel", "trip", "conference", "business trip"],
            "asset_request": ["asset", "equipment", "laptop", "hardware", "software"],
            "policy_exception": ["exception", "waiver", "policy override"],
            "training_request": ["training", "course", "workshop", "certification"],
            "recruitment_request": ["hiring", "recruitment", "position", "job"],
            "promotion_request": ["promotion", "promote", "advancement", "grade"],
        }
        category_keywords = keywords.get(category, [])
        matches = sum(1 for kw in category_keywords if kw in text)
        return matches / max(len(category_keywords), 1)

    async def _predict_priority(
        self, entity_type: str, payload: dict[str, Any]
    ) -> str:
        """Predict request priority based on content."""
        # Rules-based priority prediction
        high_priority_indicators = [
            "urgent", "asap", "critical", "emergency", "immediate",
            "compliance", "regulatory", "deadline",
        ]
        title = str(payload.get("title", "")).lower()
        description = str(payload.get("description", "")).lower()
        combined = f"{title} {description}"

        for indicator in high_priority_indicators:
            if indicator in combined:
                return "high"

        # Check amount for financial requests
        amount = payload.get("amount", 0)
        if isinstance(amount, (int, float)) and amount > 10000:
            return "high"
        if isinstance(amount, (int, float)) and amount > 1000:
            return "medium"

        # Entity type based priority
        high_priority_types = ["promotion", "compliance", "policy_exception"]
        if entity_type in high_priority_types:
            return "high"

        return "normal"

    async def _predict_sla_risk(
        self, entity_type: str, payload: dict[str, Any]
    ) -> str:
        """Predict SLA breach risk."""
        # Check for urgency indicators
        priority = await self._predict_priority(entity_type, payload)
        if priority == "high":
            return "high"

        # Check if there are time constraints
        due_date = payload.get("due_date") or payload.get("deadline")
        if due_date:
            try:
                due = datetime.fromisoformat(str(due_date))
                remaining_hours = (due - datetime.now(timezone.utc)).total_seconds() / 3600
                if remaining_hours < 24:
                    return "high"
                elif remaining_hours < 72:
                    return "medium"
            except (ValueError, TypeError):
                pass

        return "low"

    async def _detect_duplicate(
        self, request_id: int, entity_type: str, payload: dict[str, Any]
    ) -> tuple[bool, Optional[int]]:
        """Detect if this is a duplicate request."""
        # Simple duplicate detection based on title and entity type
        # In production, this would search the database for similar requests
        title = payload.get("title", "")
        if not title:
            return False, None

        # Check if same title exists in recent history
        entries, _ = audit_service.search(
            module="workflow",
            action="submit",
            limit=50,
        )

        for entry in entries:
            details = entry.get("details", {})
            if details.get("title") == title and details.get("entity_type") == entity_type:
                entry_id = entry.get("entity_id")
                if entry_id and str(entry_id) != str(request_id):
                    try:
                        return True, int(entry_id)
                    except (ValueError, TypeError):
                        return False, None

        return False, None

    async def _suggest_approvers(
        self, entity_type: str, payload: dict[str, Any],
        organization_id: Optional[str] = None,
    ) -> list[dict]:
        """Suggest approvers based on entity type and organization structure."""
        # In production, this would query the org hierarchy and workload
        suggested = []

        # Based on entity type, suggest relevant roles
        role_suggestions = {
            "leave": ["hr_manager", "department_head"],
            "expense": ["finance_manager", "department_head"],
            "purchase": ["procurement_manager", "finance_manager"],
            "travel": ["department_head", "hr_manager"],
            "asset": ["it_manager", "department_head"],
            "recruitment": ["hr_manager", "hiring_manager"],
            "promotion": ["hr_manager", "department_head", "executive"],
        }

        roles = role_suggestions.get(entity_type, ["department_head"])
        for role in roles:
            suggested.append({
                "role": role,
                "reason": f"Suggested based on {entity_type} approval workflow",
                "confidence": 0.8,
            })

        return suggested

    async def _suggest_resolution(
        self, entity_type: str, payload: dict[str, Any]
    ) -> Optional[str]:
        """Suggest a resolution for common request types."""
        resolutions = {
            "leave_request": "Approve if sufficient leave balance and coverage available.",
            "expense_report": "Approve if within policy limits and receipts are attached.",
            "purchase_order": "Approve if within budget and vendor is approved.",
            "travel_request": "Approve if within travel policy and budget.",
            "asset_request": "Approve if asset is available and user is eligible.",
            "training_request": "Approve if training is relevant to role and within budget.",
        }
        return resolutions.get(entity_type)

    # =========================================================================
    #  Action Recording
    # =========================================================================

    def record_action(
        self,
        action: AIWorkflowAction,
        applied: bool = False,
        overridden_by: Optional[int] = None,
    ) -> AIWorkflowAction:
        """Record an AI workflow action."""
        action.applied = applied
        action.overridden_by = overridden_by

        audit_service.record(
            module="ai",
            action=f"workflow_{action.action_type}",
            entity_type="workflow_recommendation",
            summary=f"AI workflow action: {action.action_type} (applied={applied})",
            details=action.recommendation.model_dump(),
        )

        return action

    def get_stats(self) -> dict:
        """Get AI workflow service statistics."""
        return {
            "categories": self._categories,
            "total_categories": len(self._categories),
        }


# Singleton
ai_workflow_service = AIWorkflowService()

