"""
ai_cost_tracker.py — Enterprise AI Cost Tracker & Token Usage Analytics
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Tracks and analyzes AI usage costs:
- Per-provider cost tracking
- Per-model token usage
- Per-tenant cost allocation
- Budget enforcement and alerts
- Cost forecasting
- Token usage analytics
- Monthly/periodic cost reports
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.services.audit_service import audit_service
from app.services.notification_service import (
    NotificationChannel,
    NotificationPriority,
    notification_service,
)

logger = logging.getLogger(__name__)


# Standard model pricing per 1K tokens (USD)
MODEL_PRICING: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
    "text-embedding-3-large": {"input": 0.00013, "output": 0.0},
    "text-embedding-ada-002": {"input": 0.0001, "output": 0.0},
    # Anthropic
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    # Google Gemini
    "gemini-pro": {"input": 0.0005, "output": 0.0015},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
    "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
    "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
    "text-embedding-004": {"input": 0.0001, "output": 0.0},
}


class AICostTracker:
    """
    Enterprise AI cost tracking and analytics.

    Features:
    - Real-time cost tracking per request
    - Per-provider, per-model, per-tenant cost breakdowns
    - Monthly budget enforcement with alerts
    - Cost forecasting based on historical usage
    - Token usage analytics
    - Periodic cost reports
    """

    def __init__(self):
        self._usage_entries: list[dict] = []
        self._max_entries: int = 500000
        self._budgets: dict[str, dict] = {}  # org_id -> {monthly_budget, alert_threshold}
        self._cost_alerts_sent: dict[str, set] = defaultdict(set)

    # =========================================================================
    #  Cost Tracking
    # =========================================================================

    def track_completion(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_usd: float,
        organization_id: Optional[str] = None,
        user_id: Optional[int] = None,
        request_type: str = "completion",
    ) -> dict:
        """Track a completion request cost."""
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": request_type,
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": round(cost_usd, 8),
            "organization_id": organization_id or "global",
            "user_id": user_id,
        }
        self._usage_entries.append(entry)
        self._trim_history()

        # Check budget
        if organization_id:
            self._check_budget(organization_id, cost_usd)

        return entry

    def track_embedding(
        self,
        provider: str,
        model: str,
        tokens: int,
        dimensions: int,
        organization_id: Optional[str] = None,
    ) -> dict:
        """Track an embedding request cost."""
        # Calculate cost from pricing or estimate
        pricing = MODEL_PRICING.get(model, {"input": 0.0001, "output": 0.0})
        cost = (tokens / 1000) * pricing["input"]

        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "embedding",
            "provider": provider,
            "model": model,
            "prompt_tokens": tokens,
            "completion_tokens": 0,
            "total_tokens": tokens,
            "dimensions": dimensions,
            "cost_usd": round(cost, 8),
            "organization_id": organization_id or "global",
            "user_id": None,
        }
        self._usage_entries.append(entry)
        self._trim_history()

        if organization_id:
            self._check_budget(organization_id, cost)

        return entry

    def track_rag(
        self,
        provider: str,
        model: str,
        total_tokens: int,
        cost_usd: float,
        documents_retrieved: int,
        organization_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> dict:
        """Track a RAG query cost."""
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "rag",
            "provider": provider,
            "model": model,
            "prompt_tokens": total_tokens,
            "completion_tokens": 0,
            "total_tokens": total_tokens,
            "cost_usd": round(cost_usd, 8),
            "documents_retrieved": documents_retrieved,
            "organization_id": organization_id or "global",
            "user_id": user_id,
        }
        self._usage_entries.append(entry)
        self._trim_history()
        return entry

    # =========================================================================
    #  Usage Analytics
    # =========================================================================

    def get_usage_summary(
        self,
        organization_id: Optional[str] = None,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
    ) -> dict:
        """Get usage summary with aggregation."""
        entries = self._filter_entries(organization_id, period_start, period_end)

        total_requests = len(entries)
        total_tokens = sum(e.get("total_tokens", 0) for e in entries)
        total_cost = sum(e.get("cost_usd", 0) for e in entries)

        # By provider
        by_provider = defaultdict(lambda: {"requests": 0, "tokens": 0, "cost": 0.0})
        by_model = defaultdict(lambda: {"requests": 0, "tokens": 0, "cost": 0.0})
        by_type = defaultdict(lambda: {"requests": 0, "tokens": 0, "cost": 0.0})
        by_org = defaultdict(lambda: {"requests": 0, "tokens": 0, "cost": 0.0})

        for e in entries:
            prov = e.get("provider", "unknown")
            model = e.get("model", "unknown")
            rtype = e.get("type", "unknown")
            org = e.get("organization_id", "unknown")

            by_provider[prov]["requests"] += 1
            by_provider[prov]["tokens"] += e.get("total_tokens", 0)
            by_provider[prov]["cost"] += e.get("cost_usd", 0)

            by_model[model]["requests"] += 1
            by_model[model]["tokens"] += e.get("total_tokens", 0)
            by_model[model]["cost"] += e.get("cost_usd", 0)

            by_type[rtype]["requests"] += 1
            by_type[rtype]["tokens"] += e.get("total_tokens", 0)
            by_type[rtype]["cost"] += e.get("cost_usd", 0)

            by_org[org]["requests"] += 1
            by_org[org]["tokens"] += e.get("total_tokens", 0)
            by_org[org]["cost"] += e.get("cost_usd", 0)

        return {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "avg_cost_per_request": round(total_cost / max(total_requests, 1), 6),
            "avg_tokens_per_request": round(total_tokens / max(total_requests, 1), 1),
            "by_provider": {k: {**v, "cost": round(v["cost"], 4)} for k, v in by_provider.items()},
            "by_model": {k: {**v, "cost": round(v["cost"], 4)} for k, v in by_model.items()},
            "by_type": {k: {**v, "cost": round(v["cost"], 4)} for k, v in by_type.items()},
            "by_organization": {k: {**v, "cost": round(v["cost"], 4)} for k, v in by_org.items()},
        }

    def get_daily_cost(self, organization_id: Optional[str] = None,
                       days: int = 30) -> list[dict]:
        """Get daily cost breakdown for the last N days."""
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=days)).isoformat()
        entries = self._filter_entries(organization_id, period_start=start)

        daily = defaultdict(float)
        for e in entries:
            day = e.get("timestamp", "")[:10]
            daily[day] += e.get("cost_usd", 0)

        result = []
        for i in range(days):
            day = (now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            result.append({"date": day, "cost_usd": round(daily.get(day, 0.0), 4)})
        return result

    def get_top_models(self, organization_id: Optional[str] = None,
                       limit: int = 10) -> list[dict]:
        """Get top models by cost."""
        summary = self.get_usage_summary(organization_id)
        models = summary.get("by_model", {})
        sorted_models = sorted(models.items(), key=lambda x: x[1]["cost"], reverse=True)
        return [
            {"model": model, **stats}
            for model, stats in sorted_models[:limit]
        ]

    # =========================================================================
    #  Budget Management
    # =========================================================================

    def set_budget(self, organization_id: str, monthly_budget_usd: float,
                   alert_threshold_pct: float = 0.8) -> None:
        """Set a monthly budget for an organization."""
        self._budgets[organization_id] = {
            "monthly_budget": monthly_budget_usd,
            "alert_threshold": alert_threshold_pct,
            "set_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"Budget set for org {organization_id}: ${monthly_budget_usd}/month")

    def get_budget(self, organization_id: str) -> Optional[dict]:
        """Get budget for an organization."""
        return self._budgets.get(organization_id)

    def _check_budget(self, organization_id: str, cost: float) -> None:
        """Check budget and send alerts if thresholds exceeded."""
        budget = self._budgets.get(organization_id)
        if not budget:
            return

        # Get current month's cost
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_entries = [e for e in self._usage_entries
                        if e.get("organization_id") == organization_id
                        and e.get("timestamp", "") >= month_start.isoformat()]
        month_cost = sum(e.get("cost_usd", 0) for e in month_entries)

        monthly_budget = budget["monthly_budget"]
        usage_pct = month_cost / monthly_budget if monthly_budget > 0 else 1.0

        # Check alert thresholds
        threshold = budget["alert_threshold"]
        alert_levels = [0.5, 0.8, 0.9, 1.0]

        for level in alert_levels:
            if usage_pct >= level and level not in self._cost_alerts_sent.get(organization_id, set()):
                self._cost_alerts_sent[organization_id].add(level)
                self._send_budget_alert(organization_id, month_cost, monthly_budget, usage_pct, level)

    def _send_budget_alert(self, org_id: str, current_cost: float,
                          budget: float, usage_pct: float, level: float) -> None:
        """Send a budget alert notification."""
        notification_service.send(
            user_id=0,  # System/Admin
            organization_id=org_id,
            channel=NotificationChannel.IN_APP,
            priority=NotificationPriority.HIGH if level >= 0.9 else NotificationPriority.NORMAL,
            title=f"AI Budget Alert: {level:.0%} Used",
            message=f"AI usage has reached {usage_pct:.1%} of monthly budget (${budget:.2f}). "
                    f"Current spend: ${current_cost:.2f}",
            source_module="ai",
            source_event="budget.alert",
        )
        logger.warning(f"Budget alert for org {org_id}: {usage_pct:.1%} of ${budget:.2f} used")

    # =========================================================================
    #  Cost Forecasting
    # =========================================================================

    def forecast_monthly_cost(self, organization_id: Optional[str] = None) -> dict:
        """Forecast end-of-month cost based on current usage."""
        now = datetime.now(timezone.utc)
        days_in_month = (now.replace(month=now.month % 12 + 1, day=1) - timedelta(days=1)).day
        day_of_month = now.day

        summary = self.get_usage_summary(organization_id)
        current_cost = summary["total_cost_usd"]
        daily_avg = current_cost / max(day_of_month, 1)
        projected_cost = daily_avg * days_in_month

        return {
            "current_cost_usd": round(current_cost, 4),
            "daily_avg_usd": round(daily_avg, 4),
            "projected_monthly_usd": round(projected_cost, 4),
            "days_elapsed": day_of_month,
            "days_in_month": days_in_month,
            "confidence": round(1.0 - (day_of_month / days_in_month) * 0.5, 2),
        }

    # =========================================================================
    #  Token Analytics
    # =========================================================================

    def get_token_analytics(self, organization_id: Optional[str] = None) -> dict:
        """Get detailed token usage analytics."""
        summary = self.get_usage_summary(organization_id)

        # Token distribution
        entries = self._filter_entries(organization_id)
        input_tokens = sum(e.get("prompt_tokens", 0) for e in entries)
        output_tokens = sum(e.get("completion_tokens", 0) for e in entries)

        # Efficiency metrics
        total = summary["total_tokens"]
        total_cost = summary["total_cost_usd"]
        cost_per_1k_tokens = (total_cost / (total / 1000)) if total > 0 else 0

        return {
            "total_input_tokens": input_tokens,
            "total_output_tokens": output_tokens,
            "input_output_ratio": round(input_tokens / max(output_tokens, 1), 2),
            "cost_per_1k_tokens_usd": round(cost_per_1k_tokens, 6),
            "total_requests": summary["total_requests"],
            "by_type": summary["by_type"],
        }

    # =========================================================================
    #  Reporting
    # =========================================================================

    def generate_cost_report(self, organization_id: Optional[str] = None,
                             period: str = "monthly") -> dict:
        """Generate a comprehensive cost report."""
        summary = self.get_usage_summary(organization_id)
        forecast = self.forecast_monthly_cost(organization_id)
        daily_costs = self.get_daily_cost(organization_id)
        top_models = self.get_top_models(organization_id)
        token_analytics = self.get_token_analytics(organization_id)

        budget = self._budgets.get(organization_id) if organization_id else None
        budget_status = None
        if budget:
            usage_pct = summary["total_cost_usd"] / budget["monthly_budget"] if budget["monthly_budget"] > 0 else 0
            budget_status = {
                "monthly_budget_usd": budget["monthly_budget"],
                "used_usd": round(summary["total_cost_usd"], 4),
                "remaining_usd": round(budget["monthly_budget"] - summary["total_cost_usd"], 4),
                "usage_pct": round(usage_pct * 100, 1),
            }

        return {
            "report_period": period,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "organization_id": organization_id or "all",
            "usage_summary": summary,
            "forecast": forecast,
            "daily_costs": daily_costs,
            "top_models": top_models,
            "token_analytics": token_analytics,
            "budget_status": budget_status,
        }

    # =========================================================================
    #  Internal
    # =========================================================================

    def _filter_entries(self, organization_id: Optional[str] = None,
                        period_start: Optional[str] = None,
                        period_end: Optional[str] = None) -> list[dict]:
        """Filter usage entries by criteria."""
        entries = self._usage_entries
        if organization_id:
            entries = [e for e in entries if e.get("organization_id") == organization_id]
        if period_start:
            entries = [e for e in entries if e.get("timestamp", "") >= period_start]
        if period_end:
            entries = [e for e in entries if e.get("timestamp", "") <= period_end]
        return entries

    def _trim_history(self) -> None:
        """Trim usage history if over max."""
        if len(self._usage_entries) > self._max_entries:
            self._usage_entries = self._usage_entries[-self._max_entries:]

    def get_stats(self) -> dict:
        """Get cost tracker statistics."""
        return {
            "total_entries": len(self._usage_entries),
            "budgets_configured": len(self._budgets),
            "total_cost_usd": round(sum(e.get("cost_usd", 0) for e in self._usage_entries), 4),
            "total_tokens": sum(e.get("total_tokens", 0) for e in self._usage_entries),
        }


# Singleton
ai_cost_tracker = AICostTracker()

