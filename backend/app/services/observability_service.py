"""
observability_service.py — Enterprise Observability Service
Sprint 6 — Phase C: Cloud Platform, Integrations & Enterprise Production Operations

Provides:
- Distributed tracing with OpenTelemetry compatibility
- Structured logging with context
- Metrics collection (Prometheus-compatible)
- Service dependency graph
- Correlation ID propagation
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


class Span:
    """A single trace span."""
    
    def __init__(
        self,
        name: str,
        trace_id: str,
        span_id: str,
        parent_span_id: Optional[str] = None,
        service_name: str = "",
        start_time: Optional[float] = None,
    ):
        self.name = name
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.service_name = service_name
        self.start_time = start_time or time.time()
        self.end_time: Optional[float] = None
        self.duration_ms: float = 0.0
        self.status: str = "ok"
        self.attributes: dict = {}
        self.events: list[dict] = []

    def add_event(self, name: str, attributes: Optional[dict] = None) -> None:
        """Add an event to the span."""
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute."""
        self.attributes[key] = value

    def end(self, status: str = "ok") -> None:
        """End the span."""
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.status = status

    def to_dict(self) -> dict:
        """Serialize span to dict."""
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "service_name": self.service_name,
            "start_time": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time, tz=timezone.utc).isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


class ObservabilityService:
    """
    Enterprise observability service.
    
    Features:
    - Distributed tracing with span hierarchy
    - Correlation ID management
    - Structured log formatting
    - Metrics collection with Prometheus format
    - Service dependency graph building
    """

    def __init__(self):
        self._traces: dict[str, list[Span]] = defaultdict(list)
        self._active_spans: dict[str, Span] = {}
        self._metrics: dict[str, list[dict]] = defaultdict(list)
        self._service_dependencies: dict[str, set[str]] = defaultdict(set)
        self._max_traces: int = 1000
        self._max_metrics: int = 10000

    # =========================================================================
    #  Correlation ID
    # =========================================================================

    def generate_correlation_id(self) -> str:
        """Generate a unique correlation ID."""
        return f"corr-{uuid.uuid4().hex[:24]}"

    def extract_correlation_id(self, headers: dict) -> str:
        """Extract correlation ID from request headers."""
        return headers.get(
            "X-Correlation-ID",
            headers.get("x-correlation-id", self.generate_correlation_id()),
        )

    # =========================================================================
    #  Distributed Tracing
    # =========================================================================

    def start_trace(self, service_name: str = "") -> str:
        """Start a new trace. Returns trace ID."""
        trace_id = f"trace-{uuid.uuid4().hex[:24]}"
        return trace_id

    def start_span(
        self,
        name: str,
        trace_id: str,
        parent_span_id: Optional[str] = None,
        service_name: str = "",
    ) -> Span:
        """Start a new span."""
        span_id = f"span-{uuid.uuid4().hex[:16]}"
        span = Span(
            name=name,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            service_name=service_name,
        )
        self._active_spans[span_id] = span
        return span

    def end_span(self, span_id: str, status: str = "ok") -> Optional[Span]:
        """End a span."""
        span = self._active_spans.pop(span_id, None)
        if span:
            span.end(status)
            self._traces[span.trace_id].append(span)

            # Track service dependency
            if span.parent_span_id:
                parent = self._find_span(span.parent_span_id)
                if parent and parent.service_name and span.service_name:
                    self._service_dependencies[parent.service_name].add(span.service_name)

            # Trim traces
            if len(self._traces) > self._max_traces:
                oldest = min(self._traces.keys(), key=lambda k: min(
                    (s.start_time for s in self._traces[k]), default=0
                ))
                del self._traces[oldest]

        return span

    def _find_span(self, span_id: str) -> Optional[Span]:
        """Find a span by ID."""
        # Check active spans
        span = self._active_spans.get(span_id)
        if span:
            return span
        # Check completed traces
        for spans in self._traces.values():
            for s in spans:
                if s.span_id == span_id:
                    return s
        return None

    def get_trace(self, trace_id: str) -> list[dict]:
        """Get all spans for a trace."""
        spans = self._traces.get(trace_id, [])
        return [s.to_dict() for s in spans]

    def get_recent_traces(self, limit: int = 50) -> list[dict]:
        """Get recent traces."""
        traces = []
        for trace_id, spans in list(self._traces.items())[-limit:]:
            traces.append({
                "trace_id": trace_id,
                "span_count": len(spans),
                "root_span": spans[0].to_dict() if spans else None,
                "duration_ms": max(s.duration_ms for s in spans) if spans else 0,
            })
        return sorted(traces, key=lambda t: t.get("duration_ms", 0), reverse=True)

    # =========================================================================
    #  Structured Logging
    # =========================================================================

    def format_log(
        self,
        level: str,
        message: str,
        correlation_id: str = "",
        service: str = "",
        module: str = "",
        extra: Optional[dict] = None,
    ) -> str:
        """Format a structured log entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            "correlation_id": correlation_id,
            "service": service,
            "module": module,
            **(extra or {}),
        }
        return json.dumps(entry, default=str)

    # =========================================================================
    #  Metrics
    # =========================================================================

    def record_metric(
        self,
        name: str,
        value: float,
        labels: Optional[dict] = None,
        metric_type: str = "gauge",
    ) -> None:
        """Record a metric value."""
        self._metrics[name].append({
            "value": value,
            "labels": labels or {},
            "type": metric_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Trim
        if len(self._metrics[name]) > self._max_metrics:
            self._metrics[name] = self._metrics[name][-self._max_metrics:]

    def record_counter(self, name: str, value: float = 1.0, labels: Optional[dict] = None) -> None:
        """Record a counter metric."""
        self.record_metric(name, value, labels, "counter")

    def record_histogram(self, name: str, value: float, labels: Optional[dict] = None) -> None:
        """Record a histogram metric."""
        self.record_metric(name, value, labels, "histogram")

    def get_metrics_prometheus(self) -> str:
        """Get metrics in Prometheus text format."""
        lines = []
        for name, points in self._metrics.items():
            if not points:
                continue
            metric_type = points[0].get("type", "gauge")
            lines.append(f"# HELP {name} {name}")
            lines.append(f"# TYPE {name} {metric_type}")
            for point in points[-10:]:  # Last 10 points
                labels = point.get("labels", {})
                label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
                if label_str:
                    lines.append(f'{name}{{{label_str}}} {point["value"]}')
                else:
                    lines.append(f'{name} {point["value"]}')
        return "\n".join(lines)

    def get_metrics_json(self) -> dict:
        """Get all metrics as JSON."""
        return {
            name: points[-100:]  # Last 100 points
            for name, points in self._metrics.items()
        }

    # =========================================================================
    #  Service Dependency Graph
    # =========================================================================

    def get_service_dependency_graph(self) -> dict:
        """Get the service dependency graph."""
        graph = {}
        for service, dependencies in self._service_dependencies.items():
            graph[service] = list(dependencies)
        return graph

    # =========================================================================
    #  Dashboard
    # =========================================================================

    def get_dashboard(self) -> dict:
        """Get observability dashboard data."""
        return {
            "active_traces": len(self._traces),
            "active_spans": len(self._active_spans),
            "total_metrics": sum(len(v) for v in self._metrics.values()),
            "metric_names": list(self._metrics.keys()),
            "service_dependencies": self.get_service_dependency_graph(),
            "recent_traces": self.get_recent_traces(limit=10),
        }

    def get_stats(self) -> dict:
        """Get observability statistics."""
        return {
            "total_traces": len(self._traces),
            "active_spans": len(self._active_spans),
            "metric_count": sum(len(v) for v in self._metrics.values()),
            "unique_metrics": len(self._metrics),
            "service_count": len(self._service_dependencies),
            "dependency_edges": sum(len(v) for v in self._service_dependencies.values()),
        }


# Singleton
observability_service = ObservabilityService()
