"""
gateway_service.py — Enterprise API Gateway Service
Sprint 6 — Phase C: Cloud Platform, Integrations & Enterprise Production Operations

Provides:
- API versioning configuration
- Rate limiting rules
- Request/response transformation templates
- Tenant routing rules
- Gateway metrics collection
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class VersioningRule:
    """API versioning rule configuration."""
    
    def __init__(
        self,
        version: str = "v1",
        prefix: str = "/v1",
        header: str = "X-API-Version",
        deprecated: bool = False,
        sunset_date: Optional[str] = None,
    ):
        self.version = version
        self.prefix = prefix
        self.header = header
        self.deprecated = deprecated
        self.sunset_date = sunset_date


class RateLimitRule:
    """Rate limiting rule configuration."""
    
    def __init__(
        self,
        pattern: str = "*",
        requests_per_second: float = 100.0,
        burst_size: int = 200,
        tenant_id: str = "",
        tier: str = "STANDARD",
    ):
        self.pattern = pattern
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size
        self.tenant_id = tenant_id
        self.tier = tier


class TransformationRule:
    """Request/response transformation rule."""
    
    def __init__(
        self,
        pattern: str = "*",
        request_headers: Optional[dict] = None,
        response_headers: Optional[dict] = None,
        strip_prefix: str = "",
        add_prefix: str = "",
    ):
        self.pattern = pattern
        self.request_headers = request_headers or {}
        self.response_headers = response_headers or {}
        self.strip_prefix = strip_prefix
        self.add_prefix = add_prefix


class GatewayService:
    """
    Enterprise API Gateway configuration service.
    
    Manages:
    - API versioning
    - Rate limiting rules
    - Request/response transformation
    - Tenant routing
    - Gateway metrics
    """

    def __init__(self):
        self._versions: dict[str, VersioningRule] = {}
        self._rate_limits: list[RateLimitRule] = []
        self._transformations: list[TransformationRule] = []
        self._tenant_routes: dict[str, str] = {}
        self._metrics: dict[str, Any] = {
            "total_requests": 0,
            "requests_by_version": defaultdict(int),
            "requests_by_tenant": defaultdict(int),
            "requests_by_path": defaultdict(int),
            "requests_by_method": defaultdict(int),
            "status_codes": defaultdict(int),
            "latency_buckets": defaultdict(int),
            "rate_limited_requests": 0,
            "errors_4xx": 0,
            "errors_5xx": 0,
        }
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Initialize default API versions."""
        self.add_version("v1", "/v1", deprecated=False)
        self.add_version("v2", "/v2", deprecated=False)
        self.add_default_rate_limits()

    def add_version(
        self,
        version: str,
        prefix: str,
        header: str = "X-API-Version",
        deprecated: bool = False,
        sunset_date: Optional[str] = None,
    ) -> VersioningRule:
        """Add an API version."""
        rule = VersioningRule(version, prefix, header, deprecated, sunset_date)
        self._versions[version] = rule
        return rule

    def get_version(self, version: str) -> Optional[VersioningRule]:
        """Get versioning rule for a version."""
        return self._versions.get(version)

    def get_version_by_prefix(self, prefix: str) -> Optional[VersioningRule]:
        """Get versioning rule by URL prefix."""
        for rule in self._versions.values():
            if rule.prefix == prefix:
                return rule
        return None

    def get_all_versions(self) -> list[dict]:
        """Get all API versions."""
        return [
            {
                "version": v.version,
                "prefix": v.prefix,
                "header": v.header,
                "deprecated": v.deprecated,
                "sunset_date": v.sunset_date,
            }
            for v in self._versions.values()
        ]

    def add_default_rate_limits(self) -> None:
        """Add default rate limiting rules."""
        self._rate_limits = [
            RateLimitRule(pattern="*", requests_per_second=100, burst_size=200),
            RateLimitRule(pattern="/api/v1/auth/*", requests_per_second=10, burst_size=20),
            RateLimitRule(pattern="/api/v1/integration/webhooks/*", requests_per_second=50, burst_size=100),
        ]

    def add_rate_limit(
        self,
        pattern: str,
        requests_per_second: float,
        burst_size: int,
        tenant_id: str = "",
        tier: str = "STANDARD",
    ) -> RateLimitRule:
        """Add a rate limiting rule."""
        rule = RateLimitRule(pattern, requests_per_second, burst_size, tenant_id, tier)
        self._rate_limits.append(rule)
        return rule

    def get_rate_limits(self) -> list[dict]:
        """Get all rate limiting rules."""
        return [
            {
                "pattern": r.pattern,
                "requests_per_second": r.requests_per_second,
                "burst_size": r.burst_size,
                "tenant_id": r.tenant_id,
            }
            for r in self._rate_limits
        ]

    def add_transformation(
        self,
        pattern: str,
        request_headers: Optional[dict] = None,
        response_headers: Optional[dict] = None,
        strip_prefix: str = "",
        add_prefix: str = "",
    ) -> TransformationRule:
        """Add a request/response transformation rule."""
        rule = TransformationRule(pattern, request_headers, response_headers, strip_prefix, add_prefix)
        self._transformations.append(rule)
        return rule

    def get_transformations(self) -> list[dict]:
        """Get all transformation rules."""
        return [
            {
                "pattern": t.pattern,
                "request_headers": t.request_headers,
                "response_headers": t.response_headers,
                "strip_prefix": t.strip_prefix,
                "add_prefix": t.add_prefix,
            }
            for t in self._transformations
        ]

    def set_tenant_route(self, tenant_id: str, base_url: str) -> None:
        """Set tenant routing rule."""
        self._tenant_routes[tenant_id] = base_url

    def get_tenant_route(self, tenant_id: str) -> Optional[str]:
        """Get tenant route."""
        return self._tenant_routes.get(tenant_id)

    def get_tenant_routes(self) -> dict:
        """Get all tenant routes."""
        return dict(self._tenant_routes)

    # =========================================================================
    #  Metrics
    # =========================================================================

    def record_request(
        self,
        path: str,
        method: str,
        version: str,
        tenant_id: str,
        status_code: int,
        latency_ms: float,
    ) -> None:
        """Record an API request metric."""
        self._metrics["total_requests"] += 1
        self._metrics["requests_by_version"][version] += 1
        self._metrics["requests_by_tenant"][tenant_id] += 1
        self._metrics["requests_by_path"][path] += 1
        self._metrics["requests_by_method"][method.upper()] += 1
        self._metrics["status_codes"][str(status_code)] += 1

        # Latency buckets
        if latency_ms < 50:
            self._metrics["latency_buckets"]["<50ms"] += 1
        elif latency_ms < 100:
            self._metrics["latency_buckets"]["50-100ms"] += 1
        elif latency_ms < 200:
            self._metrics["latency_buckets"]["100-200ms"] += 1
        elif latency_ms < 500:
            self._metrics["latency_buckets"]["200-500ms"] += 1
        elif latency_ms < 1000:
            self._metrics["latency_buckets"]["500-1000ms"] += 1
        else:
            self._metrics["latency_buckets"][">1000ms"] += 1

        if 400 <= status_code < 500:
            self._metrics["errors_4xx"] += 1
        elif status_code >= 500:
            self._metrics["errors_5xx"] += 1

    def record_rate_limited(self) -> None:
        """Record a rate-limited request."""
        self._metrics["rate_limited_requests"] += 1

    def get_metrics(self) -> dict:
        """Get gateway metrics."""
        metrics = dict(self._metrics)
        # Convert defaultdicts to regular dicts
        for key in ["requests_by_version", "requests_by_tenant", "requests_by_path", "requests_by_method", "status_codes", "latency_buckets"]:
            metrics[key] = dict(metrics[key])
        return metrics

    def reset_metrics(self) -> None:
        """Reset gateway metrics."""
        self._metrics = {
            "total_requests": 0,
            "requests_by_version": defaultdict(int),
            "requests_by_tenant": defaultdict(int),
            "requests_by_path": defaultdict(int),
            "requests_by_method": defaultdict(int),
            "status_codes": defaultdict(int),
            "latency_buckets": defaultdict(int),
            "rate_limited_requests": 0,
            "errors_4xx": 0,
            "errors_5xx": 0,
        }

    def get_stats(self) -> dict:
        """Get gateway statistics."""
        return {
            "versions": len(self._versions),
            "rate_limit_rules": len(self._rate_limits),
            "transformation_rules": len(self._transformations),
            "tenant_routes": len(self._tenant_routes),
            "metrics": self.get_metrics(),
        }


# Singleton
gateway_service = GatewayService()
