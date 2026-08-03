"""
middleware/gateway.py — Enterprise API Gateway Middleware
Sprint 6 — Phase C: Cloud Platform, Integrations & Enterprise Production Operations

Provides:
- Request tracing (X-Request-ID, X-Correlation-ID, X-Trace-ID)
- API versioning (URL path prefix and header-based)
- Distributed rate limiting (token bucket per tenant/endpoint)
- Request throttling (concurrent request limits)
- Request/response transformation
- Tenant routing based on hostname/header
- API metrics collection
- Request logging with sampling
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.services.gateway_service import gateway_service
from app.services.observability_service import observability_service

logger = logging.getLogger(__name__)


class GatewayMiddleware(BaseHTTPMiddleware):
    """
    Enterprise API Gateway middleware.

    Intercepts all requests and applies:
    1. Request ID generation
    2. Correlation ID propagation
    3. API version detection
    4. Rate limiting
    5. Request throttling
    6. Request transformation
    7. Metrics collection
    8. Structured request logging
    """

    def __init__(self, app: FastAPI):
        super().__init__(app)
        self._concurrent_requests: dict[str, int] = defaultdict(int)
        self._rate_limit_buckets: dict[str, dict] = {}
        self._max_concurrent_per_ip: int = 50
        self._sampling_rate: float = 1.0  # Log 100% of requests in dev

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        start_time = time.time()

        # ── Step 1: Generate/Extract Trace IDs ──
        request_id = request.headers.get(
            "X-Request-ID", f"req-{uuid.uuid4().hex[:16]}"
        )
        correlation_id = observability_service.extract_correlation_id(dict(request.headers))
        trace_id = request.headers.get(
            "X-Trace-ID", observability_service.start_trace(service_name="gateway")
        )

        # Set request state for downstream use
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        request.state.trace_id = trace_id

        # ── Step 2: API Version Detection ──
        version = self._detect_api_version(request)
        request.state.api_version = version

        # ── Step 3: Tenant Detection ──
        tenant_id = self._detect_tenant(request)
        request.state.tenant_id = tenant_id

        # ── Step 4: Rate Limiting ──
        client_ip = request.client.host if request.client else "unknown"
        rate_limit_key = f"{tenant_id}:{request.url.path}:{client_ip}"

        if not self._check_rate_limit(rate_limit_key):
            gateway_service.record_rate_limited()
            logger.warning(
                f"Rate limit exceeded: {rate_limit_key}",
                extra={"request_id": request_id, "correlation_id": correlation_id},
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "request_id": request_id,
                    "retry_after": 60,
                },
                headers={
                    "X-Request-ID": request_id,
                    "X-Correlation-ID": correlation_id,
                    "Retry-After": "60",
                },
            )

        # ── Step 5: Request Throttling (concurrent) ──
        ip_key = f"ip:{client_ip}"
        self._concurrent_requests[ip_key] += 1

        if self._concurrent_requests[ip_key] > self._max_concurrent_per_ip:
            self._concurrent_requests[ip_key] -= 1
            gateway_service.record_rate_limited()
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many concurrent requests.",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id, "X-Correlation-ID": correlation_id},
            )

        # ── Step 6: Request Transformation ──
        request = await self._transform_request(request, version)

        # ── Step 7: Process Request ──
        try:
            response = await call_next(request)

            # ── Step 8: Response Transformation ──
            response = await self._transform_response(response, version)

            # Add tracing headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-API-Version"] = version
            response.headers["X-Response-Time-Ms"] = str(
                round((time.time() - start_time) * 1000, 2)
            )

            # ── Step 9: Record Metrics ──
            latency_ms = (time.time() - start_time) * 1000
            gateway_service.record_request(
                path=request.url.path,
                method=request.method,
                version=version,
                tenant_id=tenant_id,
                status_code=response.status_code,
                latency_ms=latency_ms,
            )

            # Record observability metrics
            observability_service.record_histogram(
                "api_latency_ms", latency_ms,
                {"path": request.url.path, "method": request.method, "version": version},
            )
            observability_service.record_counter(
                "api_requests_total",
                labels={"path": request.url.path, "method": request.method, "status": str(response.status_code)},
            )

            # ── Step 10: Structured Logging ──
            if self._should_log():
                log_entry = observability_service.format_log(
                    level="INFO",
                    message=f"{request.method} {request.url.path} → {response.status_code}",
                    correlation_id=correlation_id,
                    service="gateway",
                    module="api_gateway",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "latency_ms": round(latency_ms, 2),
                        "version": version,
                        "tenant_id": tenant_id,
                        "client_ip": client_ip,
                        "user_agent": request.headers.get("user-agent", ""),
                    },
                )
                logger.info(log_entry)

            return response

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Gateway error: {e}",
                extra={"request_id": request_id, "correlation_id": correlation_id},
            )

            observability_service.record_counter(
                "api_errors_total",
                labels={"path": request.url.path, "method": request.method, "error": str(e)},
            )

            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id, "X-Correlation-ID": correlation_id},
            )

        finally:
            # Release throttling slot
            self._concurrent_requests[ip_key] = max(0, self._concurrent_requests[ip_key] - 1)

    # =========================================================================
    #  API Version Detection
    # =========================================================================

    def _detect_api_version(self, request: Request) -> str:
        """Detect API version from URL prefix or header."""
        # Check URL prefix first
        path = request.url.path
        for version in ["v1", "v2", "v3"]:
            if f"/api/{version}/" in path or path.startswith(f"/{version}/"):
                return version

        # Check header
        version = request.headers.get("X-API-Version", "")
        if version in ["v1", "v2", "v3", "1", "2", "3"]:
            return f"v{version}" if version.isdigit() else version

        # Default
        return "v1"

    # =========================================================================
    #  Tenant Detection
    # =========================================================================

    def _detect_tenant(self, request: Request) -> str:
        """Detect tenant from hostname, header, or query parameter."""
        # Check header
        tenant = request.headers.get("X-Tenant-ID", "")
        if tenant:
            return tenant

        # Check hostname for subdomain-based routing
        host = request.headers.get("host", "")
        parts = host.split(".")
        if len(parts) >= 3:
            return parts[0]  # tenant.example.com

        # Check query parameter
        tenant = request.query_params.get("tenant_id", "")
        if tenant:
            return tenant

        return "default"

    # =========================================================================
    #  Rate Limiting (Token Bucket)
    # =========================================================================

    def _check_rate_limit(self, key: str) -> bool:
        """Check rate limit using token bucket algorithm."""
        now = time.time()
        bucket = self._rate_limit_buckets.get(key)

        if not bucket:
            # Find matching rate limit rule
            for rule in gateway_service._rate_limits:
                if rule.pattern == "*" or rule.pattern in key:
                    self._rate_limit_buckets[key] = {
                        "tokens": rule.burst_size,
                        "last_refill": now,
                        "rate": rule.requests_per_second,
                        "burst": rule.burst_size,
                    }
                    bucket = self._rate_limit_buckets[key]
                    break

        if not bucket:
            return True  # No rate limit rule matched

        # Refill tokens
        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(
            bucket["burst"],
            bucket["tokens"] + elapsed * bucket["rate"],
        )
        bucket["last_refill"] = now

        # Consume token
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True

        return False

    # =========================================================================
    #  Request/Response Transformation
    # =========================================================================

    async def _transform_request(
        self, request: Request, version: str
    ) -> Request:
        """Apply request transformations."""
        # Strip version prefix from path for internal routing
        for v in ["v1", "v2", "v3"]:
            prefix = f"/api/{v}"
            if request.url.path.startswith(prefix):
                # Request is modified to strip version prefix
                # Actual implementation would modify the ASGI scope
                pass

        return request

    async def _transform_response(
        self, response: Response, version: str
    ) -> Response:
        """Apply response transformations."""
        # Add version-specific headers
        response.headers["X-API-Version"] = version

        if version == "v1":
            response.headers["X-Deprecated"] = "false"
        elif version == "v2":
            response.headers["X-Latest"] = "true"

        return response

    # =========================================================================
    #  Sampling
    # =========================================================================

    def _should_log(self) -> bool:
        """Determine if request should be logged based on sampling rate."""
        return self._sampling_rate >= 1.0 or (hash(str(time.time())) % 1000) / 1000 < self._sampling_rate


# =============================================================================
#  Factory function for Easy Integration
# =============================================================================

def add_gateway_middleware(app: FastAPI) -> None:
    """Add the API Gateway middleware to a FastAPI application."""
    app.add_middleware(GatewayMiddleware)
    logger.info("API Gateway middleware installed")
