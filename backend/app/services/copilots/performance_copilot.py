"""
performance_copilot.py — Performance Copilot
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Performance domain copilot providing:
- Review insights and summaries
- Goal tracking assistance
- Performance trend analysis
- Promotion readiness assessment
- Feedback draft generation
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


class PerformanceCopilot(BaseCopilot):
    """Performance domain copilot for reviews, goals, and development."""

    def __init__(self):
        super().__init__(
            domain=CopilotDomain.PERFORMANCE,
            name="Performance Copilot",
            description="performance reviews, goals, KPIs, and employee development",
        )

    def get_capabilities(self) -> list[str]:
        return super().get_capabilities() + [
            "Review summary generation",
            "Goal progress insights",
            "Performance trend analysis",
            "Feedback draft assistance",
            "Development plan suggestions",
        ]

    async def process(
        self,
        request: CopilotRequest,
        context: Optional[dict] = None,
    ) -> CopilotResponse:
        context = context or {}
        domain_data = context.get("domain_data", {})

        perf_context = f"""
Performance Analytics:
- Total reviews: {domain_data.get('total_reviews', 'N/A')}
- Reviews by action: {domain_data.get('reviews_by_action', {})}

User Query: {request.query}

Provide performance management assistance. Maintain objectivity and
focus on data-driven insights. Follow best practices for reviews.
"""
        completion_request = AICompletionRequest(
            prompt=perf_context,
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
            request_type="copilot_performance",
        )

        return CopilotResponse(
            id=completion.id,
            domain=self.domain,
            query=request.query,
            answer=completion.content,
            data_sources=["Performance Analytics"],
            usage={
                "model": completion.model,
                "provider": completion.provider,
                **completion.usage,
            },
            cost_usd=completion.cost_usd,
            latency_ms=completion.latency_ms,
            conversation_id=request.conversation_id or "",
        )
