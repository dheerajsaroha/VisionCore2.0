"""
hr_copilot.py — HR Copilot
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

HR domain copilot providing:
- Leave policy Q&A
- Attendance analytics
- Payroll inquiries
- Onboarding assistance
- Workflow guidance
- Draft generation (policies, letters)
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.schema.ai import (
    AICompletionRequest,
    CopilotDomain,
    CopilotRequest,
    CopilotResponse,
)
from app.services.ai_provider_manager import ai_provider_manager
from app.services.ai_cost_tracker import ai_cost_tracker
from app.services.copilot_service import BaseCopilot

logger = logging.getLogger(__name__)


class HRCopilot(BaseCopilot):
    """HR domain copilot for leave, attendance, payroll, and HR operations."""

    def __init__(self):
        super().__init__(
            domain=CopilotDomain.HR,
            name="HR Copilot",
            description="HR operations including leave, attendance, payroll, and employee management",
        )

    def get_capabilities(self) -> list[str]:
        return super().get_capabilities() + [
            "Leave balance inquiries",
            "Attendance pattern analysis",
            "Payroll explanation",
            "Onboarding checklist generation",
            "HR policy draft generation",
            "Employee data insights",
        ]

    async def process(
        self,
        request: CopilotRequest,
        context: Optional[dict] = None,
    ) -> CopilotResponse:
        """Process an HR copilot request with domain context."""
        context = context or {}
        domain_data = context.get("domain_data", {})

        hr_context = f"""
Current HR Analytics:
- Leave requests: {domain_data.get('leave', {}).get('total_requests', 'N/A')}
- Approved leaves: {domain_data.get('leave', {}).get('approved', 'N/A')}
- Rejected leaves: {domain_data.get('leave', {}).get('rejected', 'N/A')}

User Query: {request.query}

Provide helpful HR assistance based on available data and company policies.
"""
        system_prompt = self._system_prompt + (
            "\nYou have access to HR analytics data. Use it to provide "
            "data-driven answers. For policy questions, refer to standard "
            "HR best practices. Always maintain confidentiality."
        )

        completion_request = AICompletionRequest(
            prompt=hr_context,
            system_prompt=system_prompt,
            model_id=request.model_id,
            temperature=request.temperature or 0.5,
            max_tokens=2048,
            organization_id=request.organization_id,
            user_id=request.user_id,
        )

        completion = await ai_provider_manager.complete(completion_request)

        ai_cost_tracker.track_completion(
            provider=completion.provider,
            model=completion.model,
            prompt_tokens=completion.usage.get("prompt_tokens", 0),
            completion_tokens=completion.usage.get("completion_tokens", 0),
            total_tokens=completion.usage.get("total_tokens", 0),
            cost_usd=completion.cost_usd,
            organization_id=request.organization_id,
            user_id=request.user_id,
            request_type="copilot_hr",
        )

        return CopilotResponse(
            id=completion.id,
            domain=self.domain,
            query=request.query,
            answer=completion.content,
            data_sources=["HR Analytics", "HR Policies"],
            usage={
                "model": completion.model,
                "provider": completion.provider,
                **completion.usage,
            },
            cost_usd=completion.cost_usd,
            latency_ms=completion.latency_ms,
            conversation_id=request.conversation_id or "",
        )
