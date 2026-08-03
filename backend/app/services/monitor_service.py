"""
monitor_service.py — Enterprise Monitoring Center
Sprint 5 — Phase C: Enterprise Platform Operations

Monitors:
- API latency, Background jobs, Redis, PostgreSQL, Queue status
- Event Bus, Notification delivery, Workflow processing
- Cache hit ratio, Memory, CPU, Disk, Database connections
- Health status

Provides:
- Real-time dashboard data
- Historical metrics
- Alerts and thresholds
- Health scoring
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import settings
from app.events.event_bus import event_bus
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """A single metric data point."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    value: float = 0.0
    labels: dict = field(default_factory=dict)


@dataclass
class HealthStatus:
    """Health status of a component."""
    component: str = ""
    status: str = "healthy"  # healthy, degraded, down
    latency_ms: float = 0.0
    last_check: str = ""
    message: str = ""
    score: float = 1.0


class MonitorService:
    """
    Enterprise monitoring service.
    
    Collects and exposes metrics from all platform components.
    """

    def __init__(self):
        self._metrics: dict[str, list[MetricPoint]] = defaultdict(list)
        self._health_cache: dict[str, HealthStatus] = {}
        self._alerts: list[dict] = []
        self._max_metrics_per_key: int = 10000
        self._max_alerts: int = 1000
        self._thresholds: dict[str, float] = {
            "api_latency_warning": 500,   # ms
            "api_latency_critical": 2000,  # ms
            "db_connections_warning": 50,
            "db_connections_critical": 80,
            "cache_hit_ratio_warning": 0.7,
            "memory_percent_warning": 80,
            "memory_percent_critical": 95,
            "cpu_percent_warning": 80,
            "cpu_percent_critical": 95,
            "disk_percent_warning": 85,
            "disk_percent_critical": 95,
        }
        self._collecting: bool = False

    # ------------------------------------------------------------------
    #  Metric Recording
    # ------------------------------------------------------------------

    def record_metric(
        self,
        name: str,
        value: float,
        labels: dict | None = None,
    ) -> None:
        """Record a metric data point."""
        point = MetricPoint(value=value, labels=labels or {})
        self._metrics[name].append(point)
        # Trim
        if len(self._metrics[name]) > self._max_metrics_per_key:
            self._metrics[name] = self._metrics[name][-self._max_metrics_per_key:]

    def record_api_latency(self, path: str, method: str, latency_ms: float) -> None:
        """Record API endpoint latency."""
        self.record_metric("api_latency", latency_ms, {
            "path": path, "method": method,
        })

    def record_job_duration(self, job_name: str, duration_ms: float) -> None:
        """Record job execution duration."""
        self.record_metric("job_duration", duration_ms, {"job": job_name})

    def record_cache_hit(self, hit: bool) -> None:
        """Record cache hit or miss."""
        self.record_metric("cache_hit", 1.0 if hit else 0.0)

    def record_event_bus_metric(self, event_type: str) -> None:
        """Record an event publication."""
        self.record_metric("event_bus_publish", 1.0, {"event_type": event_type})

    def record_notification(self, channel: str, success: bool) -> None:
        """Record notification delivery."""
        self.record_metric("notification_delivery", 1.0 if success else 0.0,
                          {"channel": channel})

    def record_system_metric(self, name: str, value: float) -> None:
        """Record a system-level metric (memory, CPU, disk, etc.)."""
        self.record_metric(f"system_{name}", value)

    # ------------------------------------------------------------------
    #  Metric Queries
    # ------------------------------------------------------------------

    def get_metric(
        self,
        name: str,
        minutes: int = 60,
        aggregation: str = "avg",
    ) -> list[dict]:
        """Get metric data points for a time range."""
        cutoff = datetime.now(timezone.utc).timestamp() - (minutes * 60)
        points = [
            p for p in self._metrics.get(name, [])
            if datetime.fromisoformat(p.timestamp).timestamp() >= cutoff
        ]

        if not points:
            return []

        if aggregation == "avg":
            return [{"timestamp": p.timestamp, "value": p.value, "labels": p.labels}
                    for p in points]
        elif aggregation == "sum":
            return [{"timestamp": p.timestamp, "value": p.value}]
        elif aggregation == "count":
            return [{"timestamp": datetime.now(timezone.utc).isoformat(),
                     "value": len(points)}]
        return [{"timestamp": p.timestamp, "value": p.value} for p in points]

    def get_metric_summary(self, name: str, minutes: int = 60) -> dict:
        """Get summary statistics for a metric."""
        raw = self.get_metric(name, minutes)
        values = [p["value"] for p in raw if isinstance(p.get("value"), (int, float))]
        if not values:
            return {"count": 0, "avg": 0, "min": 0, "max": 0, "latest": 0}
        return {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "latest": values[-1] if values else 0,
        }

    def get_all_metrics_summary(self) -> dict:
        """Get summary for all tracked metrics."""
        return {
            name: self.get_metric_summary(name)
            for name in self._metrics
        }

    # ------------------------------------------------------------------
    #  Health Checks
    # ------------------------------------------------------------------

    async def check_all(self) -> list[HealthStatus]:
        """Run all health checks and return statuses."""
        checks = await asyncio.gather(
            self._check_api(),
            self._check_database(),
            self._check_redis(),
            self._check_event_bus(),
            self._check_job_queue(),
            self._check_system_resources(),
            return_exceptions=True,
        )
        results = []
        for check in checks:
            if isinstance(check, Exception):
                results.append(HealthStatus(
                    component="unknown",
                    status="down",
                    message=str(check),
                ))
            else:
                results.append(check)
                self._health_cache[check.component] = check

        return results

    async def _check_api(self) -> HealthStatus:
        """Check API health by measuring response time."""
        import httpx
        start = time.time()
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"http://127.0.0.1:8000/health",
                    timeout=5,
                )
            latency = (time.time() - start) * 1000
            return HealthStatus(
                component="api",
                status="healthy" if r.status_code == 200 else "degraded",
                latency_ms=round(latency, 2),
                last_check=datetime.now(timezone.utc).isoformat(),
                message=f"HTTP {r.status_code}",
            )
        except Exception as e:
            return HealthStatus(
                component="api",
                status="down",
                message=str(e),
                last_check=datetime.now(timezone.utc).isoformat(),
            )

    async def _check_database(self) -> HealthStatus:
        """Check database connectivity."""
        from app.db.database import SessionLocal
        start = time.time()
        try:
            db = SessionLocal()
            db.execute(db.bind.dialect.statement_compiler(
                db.bind.dialect, None
            ).__class__.__module__ and db.bind.execute("SELECT 1"))
            db.close()
            latency = (time.time() - start) * 1000
            return HealthStatus(
                component="database",
                status="healthy",
                latency_ms=round(latency, 2),
                last_check=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            return HealthStatus(
                component="database",
                status="down",
                message=str(e),
                last_check=datetime.now(timezone.utc).isoformat(),
            )

    async def _check_redis(self) -> HealthStatus:
        """Check Redis connectivity."""
        start = time.time()
        try:
            import redis.asyncio as redis_async
            client = redis_async.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            await client.ping()
            await client.aclose()
            latency = (time.time() - start) * 1000
            return HealthStatus(
                component="redis",
                status="healthy",
                latency_ms=round(latency, 2),
                last_check=datetime.now(timezone.utc).isoformat(),
            )
        except Exception:
            return HealthStatus(
                component="redis",
                status="degraded",
                message="Redis unavailable (degraded mode)",
                last_check=datetime.now(timezone.utc).isoformat(),
            )

    async def _check_event_bus(self) -> HealthStatus:
        """Check Event Bus health."""
        try:
            stats = event_bus.get_stats()
            return HealthStatus(
                component="event_bus",
                status="healthy",
                last_check=datetime.now(timezone.utc).isoformat(),
                message=f"{stats['total_events_published']} events published",
            )
        except Exception as e:
            return HealthStatus(
                component="event_bus",
                status="degraded",
                message=str(e),
            )

    async def _check_job_queue(self) -> HealthStatus:
        """Check job queue status."""
        from app.services.scheduler_service import scheduler_service
        stats = scheduler_service.get_stats()
        if stats["failed"] > 0:
            return HealthStatus(
                component="job_queue",
                status="degraded",
                message=f"{stats['failed']} failed jobs",
                last_check=datetime.now(timezone.utc).isoformat(),
            )
        return HealthStatus(
            component="job_queue",
            status="healthy",
            message=f"{stats['running']} running, {stats['pending']} pending",
            last_check=datetime.now(timezone.utc).isoformat(),
        )

    async def _check_system_resources(self) -> HealthStatus:
        """Check system resources."""
        try:
            import psutil
            memory = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=0.5)
            disk = psutil.disk_usage("/")

            self.record_system_metric("memory_percent", memory.percent)
            self.record_system_metric("cpu_percent", cpu)
            self.record_system_metric("disk_percent", disk.percent)

            status = "healthy"
            messages = []
            if memory.percent > self._thresholds["memory_percent_warning"]:
                status = "degraded"
                messages.append(f"Memory at {memory.percent}%")
            if cpu > self._thresholds["cpu_percent_warning"]:
                status = "degraded"
                messages.append(f"CPU at {cpu}%")
            if disk.percent > self._thresholds["disk_percent_warning"]:
                status = "degraded"
                messages.append(f"Disk at {disk.percent}%")

            return HealthStatus(
                component="system",
                status=status,
                message="; ".join(messages) if messages else "All resources OK",
                last_check=datetime.now(timezone.utc).isoformat(),
                score=round(1.0 - (memory.percent / 200), 2),
            )
        except ImportError:
            return HealthStatus(
                component="system",
                status="healthy",
                message="psutil not available",
                last_check=datetime.now(timezone.utc).isoformat(),
            )

    # ------------------------------------------------------------------
    #  Health Score
    # ------------------------------------------------------------------

    def get_health_score(self) -> float:
        """Calculate overall platform health score (0.0 - 1.0)."""
        checks = list(self._health_cache.values())
        if not checks:
            return 1.0
        scores = [c.score for c in checks if hasattr(c, 'score')]
        if not scores:
            return 1.0
        return round(sum(scores) / len(scores), 2)

    def get_dashboard(self) -> dict:
        """Get complete monitoring dashboard data."""
        return {
            "health_score": self.get_health_score(),
            "health_checks": [
                {
                    "component": c.component,
                    "status": c.status,
                    "latency_ms": c.latency_ms,
                    "message": c.message,
                    "last_check": c.last_check,
                }
                for c in self._health_cache.values()
            ],
            "metrics_summary": self.get_all_metrics_summary(),
            "alerts": self._alerts[-50:] if self._alerts else [],
            "thresholds": self._thresholds,
        }

    # ------------------------------------------------------------------
    #  Alerts
    # ------------------------------------------------------------------

    def check_thresholds(self) -> list[dict]:
        """Check all thresholds and generate alerts."""
        alerts = []
        for metric_name, summary in self.get_all_metrics_summary().items():
            latest = summary.get("latest", 0)
            threshold_key = f"{metric_name}_warning"
            critical_key = f"{metric_name}_critical"
            if critical_key in self._thresholds and latest > self._thresholds[critical_key]:
                alerts.append(self._create_alert(metric_name, latest, "critical"))
            elif threshold_key in self._thresholds and latest > self._thresholds[threshold_key]:
                alerts.append(self._create_alert(metric_name, latest, "warning"))
        self._alerts.extend(alerts)
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]
        return alerts

    def _create_alert(self, metric: str, value: float, severity: str) -> dict:
        return {
            "id": f"alert-{datetime.now(timezone.utc).timestamp()}",
            "metric": metric,
            "value": value,
            "severity": severity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"Metric '{metric}' at {value} exceeds {severity} threshold",
        }


# Singleton
monitor_service = MonitorService()
