"""
operations_copilot.py — Operations Copilot
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Operations domain copilot providing:
- System health monitoring
- Incident response guidance
- Performance optimization suggestions
- Alert management assistance
- Deployment support
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


class OperationsCopilot(BaseCopilot):
    """Operations domain copilot for system monitoring and platform operations."""

    def __init__(self):
        super().__init__(
            domain=CopilotDomain.OPERATIONS,
            name="Operations Copilot",
            description="system operations, monitoring, incident response, and platform health",
        )

    def get_capabilities(self) -> list[str]:
        return super().get_capabilities() + [
            "System health status checks",
            "Alert analysis and response",
            "Incident management guidance",
            "Performance optimization tips",
            "Deployment best practices",
        ]

    async def process(
        self,
        request: CopilotRequest,
        context: Optional[dict] = None,
    ) -> CopilotResponse:
        context = context or {}
        domain_data = context.get("domain_data", {})

        ops_context = f"""
Operations Context:
- Platform health score: {domain_data.get('health_score', 'N/A')}
- Recent alerts: {domain_data.get('alerts', [])}

User Query: {request.query}

Provide operations assistance. Focus on system health, incident response,
and operational best practices. Be specific about remediation steps.
"""
        completion_request = AICompletionRequest(
            prompt=ops_context,
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
            request_type="copilot_operations",
        )

        return CopilotResponse(
            id=completion.id,
            domain=self.domain,
            query=request.query,
            answer=completion.content,
            data_sources=["Monitoring Service", "Operations Center"],
            usage={
                "model": completion.model,
                "provider": completion.provider,
                **completion.usage,
            },
            cost_usd=completion.cost_usd,
            latency_ms=completion.latency_ms,
            conversation_id=request.conversation_id or "",
        )
