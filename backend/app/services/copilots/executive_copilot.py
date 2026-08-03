"""
executive_copilot.py — Executive Copilot
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Executive domain copilot providing:
- Platform-wide insights and analytics
- Executive dashboard summaries
- Trend analysis and forecasting
- Risk assessment overview
- Strategic recommendations
- Business intelligence insights
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


class ExecutiveCopilot(BaseCopilot):
    """Executive domain copilot for platform-wide insights and strategic decisions."""

    def __init__(self):
        super().__init__(
            domain=CopilotDomain.EXECUTIVE,
            name="Executive Copilot",
            description="executive insights, platform analytics, and strategic decision support",
        )

    def get_capabilities(self) -> list[str]:
        return super().get_capabilities() + [
            "Platform health overview",
            "Key performance metrics",
            "Trend analysis and forecasting",
            "Risk assessment summaries",
            "Strategic recommendations",
            "Cross-module insights",
        ]

    async def process(
        self,
        request: CopilotRequest,
        context: Optional[dict] = None,
    ) -> CopilotResponse:
        context = context or {}
        domain_data = context.get("domain_data", {})

        # Extract key metrics for executive context
        auth_data = domain_data.get("authentication", {})
        hr_data = domain_data.get("hr", {})
        perf_data = domain_data.get("performance", {})
        asset_data = domain_data.get("asset", {})
        workflow_data = domain_data.get("workflow", {})
        system_data = domain_data.get("system", {})

        exec_context = f"""
Executive Dashboard Summary:

Authentication: {auth_data.get('total_logins', 0)} logins, {auth_data.get('failure_rate', 0)}% failure rate
HR: {hr_data.get('leave', {}).get('total_requests', 0)} leave requests
Performance: {perf_data.get('total_reviews', 0)} reviews completed
Assets: {asset_data.get('total_assets', 0)} total, {asset_data.get('utilization_rate', 0)}% utilized
Workflow: {workflow_data.get('total_workflow_events', 0)} events, {workflow_data.get('approval_rate', 0)}% approval rate
System: {system_data.get('total_security_events', 0)} security events

User Query: {request.query}

Provide executive-level insights and recommendations. Focus on strategic
implications, trends, and actionable recommendations. Be data-driven.
"""
        completion_request = AICompletionRequest(
            prompt=exec_context,
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
            request_type="copilot_executive",
        )

        return CopilotResponse(
            id=completion.id,
            domain=self.domain,
            query=request.query,
            answer=completion.content,
            data_sources=["Executive Dashboard", "Analytics Platform", "All Modules"],
            usage={
                "model": completion.model,
                "provider": completion.provider,
                **completion.usage,
            },
            cost_usd=completion.cost_usd,
            latency_ms=completion.latency_ms,
            conversation_id=request.conversation_id or "",
        )
