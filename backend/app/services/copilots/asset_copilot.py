"""
asset_copilot.py — Asset Copilot
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Asset domain copilot providing:
- Asset inventory Q&A
- Assignment and tracking assistance
- Maintenance scheduling help
- License management insights
- Procurement guidance
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


class AssetCopilot(BaseCopilot):
    """Asset domain copilot for inventory, assignments, and maintenance."""

    def __init__(self):
        super().__init__(
            domain=CopilotDomain.ASSET,
            name="Asset Copilot",
            description="asset management, inventory tracking, and maintenance planning",
        )

    def get_capabilities(self) -> list[str]:
        return super().get_capabilities() + [
            "Asset inventory Q&A",
            "Assignment status checks",
            "Maintenance schedule insights",
            "License expiry tracking",
            "Utilization analysis",
        ]

    async def process(
        self,
        request: CopilotRequest,
        context: Optional[dict] = None,
    ) -> CopilotResponse:
        context = context or {}
        domain_data = context.get("domain_data", {})

        asset_context = f"""
Asset Management Analytics:
- Total assets: {domain_data.get('total_assets', 'N/A')}
- Assigned: {domain_data.get('assigned', 'N/A')}
- Available: {domain_data.get('available', 'N/A')}
- Under maintenance: {domain_data.get('under_maintenance', 'N/A')}
- Utilization rate: {domain_data.get('utilization_rate', 'N/A')}%

User Query: {request.query}

Provide asset management assistance. Focus on actionable insights
about inventory status, maintenance needs, and optimization.
"""
        completion_request = AICompletionRequest(
            prompt=asset_context,
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
            request_type="copilot_asset",
        )

        return CopilotResponse(
            id=completion.id,
            domain=self.domain,
            query=request.query,
            answer=completion.content,
            data_sources=["Asset Management"],
            usage={
                "model": completion.model,
                "provider": completion.provider,
                **completion.usage,
            },
            cost_usd=completion.cost_usd,
            latency_ms=completion.latency_ms,
            conversation_id=request.conversation_id or "",
        )
