"""
middleware/observability_middleware.py — Enterprise Observability Middleware
Sprint 6 — Phase C: Cloud Platform, Integrations & Enterprise Production Operations

Provides:
- Auto-instrumentation of all HTTP requests
- Span creation for distributed tracing
- Structured request/response logging
- Error tracking with span context
- Performance metrics collection
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.services.observability_service import observability_service

logger = logging.getLogger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Enterprise observability middleware.

    Auto-instruments all HTTP requests with:
    - Distributed tracing spans
    - Correlation ID propagation
    - Structured logging
    - Performance metrics
    - Error tracking
    """

    def __init__(self, app: FastAPI, service_name: str = "visioncore"):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        start_time = time.time()

        # ── Extract or generate trace context ──
        trace_id = getattr(request.state, "trace_id", None) or observability_service.start_trace(
            service_name=self.service_name
        )
        correlation_id = getattr(request.state, "correlation_id", None) or observability_service.generate_correlation_id()

        # ── Start a span for this request ──
        span_name = f"{request.method} {request.url.path}"
        span = observability_service.start_span(
            name=span_name,
            trace_id=trace_id,
            service_name=self.service_name,
        )
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", str(request.url))
        span.set_attribute("http.host", request.headers.get("host", ""))
        span.set_attribute("http.user_agent", request.headers.get("user-agent", ""))
        span.set_attribute("http.client_ip", request.client.host if request.client else "unknown")

        # Store in request state for downstream use
        request.state.trace_id = trace_id
        request.state.correlation_id = correlation_id
        request.state.span_id = span.span_id

        # ── Process request ──
        try:
            response = await call_next(request)

            # ── Record response metrics ──
            duration_ms = (time.time() - start_time) * 1000
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("http.duration_ms", duration_ms)
            span.end(status="ok" if response.status_code < 500 else "error")

            # Record metrics
            observability_service.record_histogram(
                "http_request_duration_ms", duration_ms,
                labels={
                    "method": request.method,
                    "path": request.url.path,
                    "status": str(response.status_code),
                    "service": self.service_name,
                },
            )
            observability_service.record_counter(
                "http_requests_total",
                labels={
                    "method": request.method,
                    "path": request.url.path,
                    "status": str(response.status_code),
                    "service": self.service_name,
                },
            )

            # Log structured entry
            log_entry = observability_service.format_log(
                level="INFO",
                message=f"{request.method} {request.url.path} → {response.status_code} ({duration_ms:.0f}ms)",
                correlation_id=correlation_id,
                service=self.service_name,
                module="http",
                extra={
                    "trace_id": trace_id,
                    "span_id": span.span_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "client_ip": request.client.host if request.client else "unknown",
                },
            )
            logger.info(log_entry)

            # Add response headers
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Span-ID"] = span.span_id

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            span.set_attribute("http.status_code", 500)
            span.set_attribute("http.error", str(e))
            span.end(status="error")

            observability_service.record_counter(
                "http_errors_total",
                labels={
                    "method": request.method,
                    "path": request.url.path,
                    "error": type(e).__name__,
                    "service": self.service_name,
                },
            )

            log_entry = observability_service.format_log(
                level="ERROR",
                message=f"Request failed: {request.method} {request.url.path}: {e}",
                correlation_id=correlation_id,
                service=self.service_name,
                module="http",
                extra={
                    "trace_id": trace_id,
                    "span_id": span.span_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            logger.error(log_entry)

            raise
        finally:
            # Ensure span is always ended
            if span and span.end_time is None:
                span.end(status="error")


# =============================================================================
#  Factory Function
# =============================================================================

def add_observability_middleware(
    app: FastAPI,
    service_name: str = "visioncore",
) -> None:
    """Add the observability middleware to a FastAPI application."""
    app.add_middleware(ObservabilityMiddleware, service_name=service_name)
    logger.info(f"Observability middleware installed for service: {service_name}")
