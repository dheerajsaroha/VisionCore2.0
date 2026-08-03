"""
recruitment_copilot.py — Recruitment Copilot
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Recruitment domain copilot providing:
- Position management assistance
- Candidate pipeline insights
- Interview scheduling help
- Job description drafting
- Recruitment analytics
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


class RecruitmentCopilot(BaseCopilot):
    """Recruitment domain copilot for talent acquisition and hiring."""

    def __init__(self):
        super().__init__(
            domain=CopilotDomain.RECRUITMENT,
            name="Recruitment Copilot",
            description="talent acquisition, candidate management, and hiring workflows",
        )

    def get_capabilities(self) -> list[str]:
        return super().get_capabilities() + [
            "Job description drafting",
            "Candidate matching insights",
            "Interview question generation",
            "Offer letter drafting",
            "Recruitment pipeline analysis",
        ]

    async def process(
        self,
        request: CopilotRequest,
        context: Optional[dict] = None,
    ) -> CopilotResponse:
        context = context or {}
        domain_data = context.get("domain_data", {})

        recruitment_context = f"""
Recruitment Context:
- Open positions: {domain_data.get('open_positions', 'N/A')}

User Query: {request.query}

Provide recruitment assistance. For job descriptions, follow industry standards.
For interview guidance, follow structured interviewing best practices.
"""
        completion_request = AICompletionRequest(
            prompt=recruitment_context,
            system_prompt=self._system_prompt,
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
            request_type="copilot_recruitment",
        )

        return CopilotResponse(
            id=completion.id,
            domain=self.domain,
            query=request.query,
            answer=completion.content,
            data_sources=["Recruitment Analytics"],
            usage={
                "model": completion.model,
                "provider": completion.provider,
                **completion.usage,
            },
            cost_usd=completion.cost_usd,
            latency_ms=completion.latency_ms,
            conversation_id=request.conversation_id or "",
        )
