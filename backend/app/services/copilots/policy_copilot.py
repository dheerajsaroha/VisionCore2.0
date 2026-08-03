"""
policy_copilot.py — Policy Copilot
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Policy domain copilot providing:
- Policy Q&A and interpretation
- Compliance guidance
- Policy search and retrieval
- Acknowledgement status
- Policy draft generation
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


class PolicyCopilot(BaseCopilot):
    """Policy domain copilot for company policies and compliance."""

    def __init__(self):
        super().__init__(
            domain=CopilotDomain.POLICY,
            name="Policy Copilot",
            description="company policies, compliance, and regulatory guidance",
        )

    def get_capabilities(self) -> list[str]:
        return super().get_capabilities() + [
            "Policy interpretation",
            "Compliance requirement Q&A",
            "Policy search across knowledge base",
            "Acknowledgement status checks",
            "New policy draft generation",
        ]

    async def process(
        self,
        request: CopilotRequest,
        context: Optional[dict] = None,
    ) -> CopilotResponse:
        context = context or {}
        domain_data = context.get("domain_data", {})
        notif_data = domain_data.get("notification_analytics", {})

        policy_context = f"""
Policy Center Context:
- Total policy events: {domain_data.get('total_policy_events', 'N/A')}
- Acknowledgements: {notif_data.get('total', 'N/A')}

User Query: {request.query}

Provide policy and compliance assistance. Always clarify that you reference
company policies. For compliance questions, note relevant regulations.
"""
        completion_request = AICompletionRequest(
            prompt=policy_context,
            system_prompt=self._system_prompt,
            model_id=request.model_id,
            temperature=request.temperature or 0.4,
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
            request_type="copilot_policy",
        )

        return CopilotResponse(
            id=completion.id,
            domain=self.domain,
            query=request.query,
            answer=completion.content,
            data_sources=["Policy Center", "Compliance Database"],
            usage={
                "model": completion.model,
                "provider": completion.provider,
                **completion.usage,
            },
            cost_usd=completion.cost_usd,
            latency_ms=completion.latency_ms,
            conversation_id=request.conversation_id or "",
        )
