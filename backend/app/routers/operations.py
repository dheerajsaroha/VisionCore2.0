"""
operations.py — Enterprise Platform Operations Router
Sprint 6 — Phase C: Cloud Platform, Integrations & Enterprise Production Operations

Consolidates all operations endpoints:
- Scheduler (jobs)
- Monitoring (health, metrics)
- Analytics (dashboards, trends)
- Search (cross-module)
- Reporting (generation, export)
- Configuration Center
- Intelligence (anomalies, insights)
- Cache Metrics (Phase C)
- Integration Health (Phase C)
- Queue Monitoring (Phase C)
- Cluster Status (Phase C)
- Incident Dashboard (Phase C)
- Tenant Health (Phase C)
- Audit Activity (Phase C)
- Observability (Phase C)
- Disaster Recovery (Phase C)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api import deps
from app.api.eaac_deps import require_eaac_authorization
from app.services.scheduler_service import (
    JobPriority,
    JobStatus,
    JobType,
    scheduler_service,
)
from app.services.monitor_service import monitor_service
from app.services.analytics_platform import analytics_platform
from app.services.search_platform import search_platform
from app.services.reporting_engine import reporting_engine
from app.services.config_center import config_center
from app.services.intelligence_service import intelligence_service
from app.services.cache_service import cache_service
from app.services.gateway_service import gateway_service
from app.services.observability_service import observability_service
from app.services.disaster_recovery_service import disaster_recovery_service
from app.services.worker_service import worker_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["operations"])


# =============================================================================
#  Health & Monitoring
# =============================================================================

@router.get("/health")
async def get_platform_health(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.health.read")),
):
    """Get platform-wide health status."""
    checks = await monitor_service.check_all()
    score = monitor_service.get_health_score()
    return {
        "status": "healthy" if score >= 0.7 else "degraded",
        "health_score": score,
        "checks": [
            {
                "component": c.component,
                "status": c.status,
                "latency_ms": c.latency_ms,
                "message": c.message,
            }
            for c in checks
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/metrics")
async def get_platform_metrics(
    name: str = Query(""),
    minutes: int = Query(60, ge=1, le=1440),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.metrics.read")),
):
    """Get platform metrics."""
    return await monitor_service.get_metrics(name=name, minutes=minutes)


@router.get("/dashboard")
async def get_operations_dashboard(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.dashboard.read")),
):
    """Get operations dashboard summary."""
    health_checks = await monitor_service.check_all()
    health_score = monitor_service.get_health_score()
    job_stats = scheduler_service.get_stats()
    worker_stats = worker_service.get_stats()

    return {
        "health": {
            "score": health_score,
            "status": "healthy" if health_score >= 0.7 else "degraded",
            "checks": [
                {
                    "component": c.component,
                    "status": c.status,
                    "latency_ms": c.latency_ms,
                }
                for c in health_checks
            ],
        },
        "scheduler": job_stats,
        "workers": worker_stats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
#  Scheduler / Jobs
# =============================================================================

@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.jobs.read")),
):
    """List scheduled jobs with optional filters."""
    try:
        status_filter = JobStatus(status) if status else None
        type_filter = JobType(job_type) if job_type else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid job filter: {exc}")

    return scheduler_service.list_jobs(
        status=status_filter,
        job_type=type_filter,
        limit=limit,
        offset=offset,
    )


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.jobs.read")),
):
    """Get a specific job by ID."""
    job = scheduler_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs")
async def create_job(
    job_data: dict,
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.jobs.create")),
):
    """Create a new scheduled job."""
    # The enums are raised on a bad value rather than passed straight through:
    # `JobType("nonsense")` raises ValueError, which surfaced to the client as an
    # unhandled 500 instead of a 400.
    try:
        job_type = JobType(job_data.get("job_type", "custom"))
        priority = JobPriority(job_data.get("priority", "normal"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid job type or priority: {exc}")

    # `create_job` takes `params` and `cron_expr`; the router was passing
    # `payload` and `schedule`, neither of which it accepts, so every create
    # raised TypeError.
    return scheduler_service.create_job(
        name=job_data["name"],
        job_type=job_type,
        module=job_data.get("module", ""),
        task=job_data.get("task", ""),
        params=job_data.get("params") or job_data.get("payload") or {},
        cron_expr=job_data.get("cron_expr", ""),
        interval_seconds=int(job_data.get("interval_seconds", 0) or 0),
        delay_seconds=int(job_data.get("delay_seconds", 0) or 0),
        priority=priority,
        max_retries=int(job_data.get("max_retries", 3) or 3),
        organization_id=str(current_user.org_id or ""),
        created_by_user_id=current_user.id,
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.jobs.cancel")),
):
    """Cancel a scheduled job."""
    success = scheduler_service.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or cannot be cancelled")
    return {"success": True, "job_id": job_id}


@router.get("/jobs/definitions")
async def get_job_definitions(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.jobs.read")),
):
    """List the job definitions this scheduler knows how to run.

    There is no `get_job_definitions` on the service. The registered handlers
    are the only honest answer, so they are enumerated from the handler registry
    rather than a method that does not exist.
    """
    handlers = getattr(scheduler_service, "_handlers", {}) or {}
    registered = getattr(scheduler_service, "handlers", None) or handlers
    return {
        "registered_tasks": sorted(registered.keys()),
        "count": len(registered),
    }


@router.post("/scheduler/start")
async def start_scheduler(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.scheduler.manage")),
):
    """Start the scheduler."""
    await scheduler_service.start()
    return {"success": True, "message": "Scheduler started"}


@router.post("/scheduler/stop")
async def stop_scheduler(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.scheduler.manage")),
):
    """Stop the scheduler."""
    await scheduler_service.stop()
    return {"success": True, "message": "Scheduler stopped"}


@router.post("/scheduler/seed")
async def seed_default_jobs(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.scheduler.manage")),
):
    """Seed default system jobs."""
    # `seed_default_jobs` is synchronous and returns the jobs it created;
    # awaiting it raised TypeError.
    created = scheduler_service.seed_default_jobs(
        organization_id=str(current_user.org_id or "")
    )
    return {
        "success": True,
        "message": f"Default jobs seeded ({len(created)} created)",
        "count": len(created),
    }


# =============================================================================
#  Analytics
# =============================================================================

@router.get("/analytics/{section}")
async def get_analytics_section(
    section: str,
    org_id: Optional[str] = Query(None),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.analytics.read")),
):
    """Get analytics data for a specific section."""
    return await analytics_platform.get_section(section, org_id=org_id)


@router.get("/analytics/dashboard")
async def get_executive_dashboard(
    org_id: Optional[str] = Query(None),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.analytics.read")),
):
    """Get executive dashboard."""
    return await analytics_platform.get_dashboard(org_id=org_id)


# =============================================================================
#  Search
# =============================================================================

@router.get("/search")
async def global_search(
    query: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.search.read")),
):
    """Global search across modules."""
    return await search_platform.search(query=query, limit=limit, offset=offset)


@router.get("/search/history")
async def get_search_history(
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.search.read")),
):
    """Get search history."""
    return await search_platform.get_history(limit=limit)


# =============================================================================
#  Reporting
# =============================================================================

@router.post("/reports/generate")
async def generate_report(
    report_data: dict,
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.reports.generate")),
):
    """Generate a report from one of the registered templates.

    The engine exposes `generate_report`, not `generate`, and it is synchronous.
    """
    template_code = report_data.get("template") or report_data.get("template_code") or "executive_summary"
    try:
        return reporting_engine.generate_report(
            template_code=template_code,
            org_id=str(current_user.org_id or ""),
            format=(report_data.get("format") or "json"),
            sections=report_data.get("sections"),
            title=report_data.get("title", ""),
            generated_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/reports")
async def list_reports(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.reports.read")),
):
    """List generated reports.

    `get_reports` is the real method and takes only limit/offset, so the status
    filter is applied here. Generated reports live in an in-process list, so this
    reflects this instance only.
    """
    reports = reporting_engine.get_reports(limit=limit, offset=offset)
    if status:
        reports = [r for r in reports if r.get("status") == status]
    return reports


@router.get("/reports/templates")
async def get_report_templates(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.reports.read")),
):
    """Get available report templates."""
    return reporting_engine.get_templates()


# =============================================================================
#  Configuration Center
# =============================================================================

@router.get("/config")
async def get_configurations(
    category: Optional[str] = Query(None),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.config.read")),
):
    """Get configurations, optionally filtered by category."""
    return config_center.get_all(category=category)


@router.put("/config")
async def update_configuration(
    payload: dict,
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.config.write")),
):
    """Update a configuration value."""
    key = payload.get("key")
    value = payload.get("value")
    if not key:
        raise HTTPException(status_code=400, detail="key is required")
    config_center.set(key, value)
    return {"success": True, "key": key, "value": value}


@router.get("/config/feature-flags")
async def get_feature_flags(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.config.read")),
):
    """Get all feature flags."""
    return config_center.get_feature_flags()


@router.get("/config/categories")
async def get_config_categories(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.config.read")),
):
    """Get configuration categories."""
    return config_center.get_categories()


# =============================================================================
#  Intelligence
# =============================================================================

@router.get("/intelligence/anomalies")
async def get_anomalies(
    org_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.intelligence.read")),
):
    """Get detected anomalies."""
    return await intelligence_service.get_anomalies(org_id=org_id, limit=limit)


@router.get("/intelligence/insights")
async def get_insights(
    org_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.intelligence.read")),
):
    """Get AI-generated insights."""
    return await intelligence_service.get_insights(org_id=org_id, limit=limit)


@router.get("/intelligence/risk")
async def get_risk_assessment(
    org_id: Optional[str] = Query(None),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.intelligence.read")),
):
    """Get risk assessment."""
    return await intelligence_service.get_risk_assessment(org_id=org_id)


@router.get("/intelligence/dashboard")
async def get_intelligence_dashboard(
    org_id: Optional[str] = Query(None),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.intelligence.read")),
):
    """Get intelligence dashboard."""
    return await intelligence_service.get_dashboard(org_id=org_id)


# =============================================================================
#  Events
# =============================================================================

@router.get("/events")
async def get_event_history(
    event_type: Optional[str] = Query(None),
    source_module: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.events.read")),
):
    """Get event history."""
    from app.events.event_bus import event_bus
    return {
        "events": event_bus.get_history(
            event_type=event_type,
            source_module=source_module,
            limit=limit,
            offset=offset,
        ),
        "total": event_bus.get_history_count(
            event_type=event_type,
            source_module=source_module,
        ),
    }


@router.get("/events/stats")
async def get_event_stats(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.events.read")),
):
    """Get event bus statistics."""
    from app.events.event_bus import event_bus
    return event_bus.get_stats()


# =============================================================================
#  Cache Metrics (Phase C)
# =============================================================================

@router.get("/cache/stats")
async def get_cache_stats(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.cache.read")),
):
    """Get cache statistics."""
    return cache_service.get_stats()


@router.post("/cache/clear")
async def clear_cache(
    pattern: Optional[str] = Query(None),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.cache.manage")),
):
    """Clear cache entries matching pattern."""
    count = await cache_service.clear(pattern=pattern)
    return {"success": True, "cleared": count}


# =============================================================================
#  Integration Health (Phase C)
# =============================================================================

@router.get("/integrations/health")
async def get_integration_health(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.integrations.read")),
):
    """Get integration health status."""
    return await gateway_service.check_all()


# =============================================================================
#  Queue Monitoring (Phase C)
# =============================================================================

@router.get("/queues/stats")
async def get_queue_stats(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.queues.read")),
):
    """Get queue statistics."""
    return await worker_service.get_queue_stats()


# =============================================================================
#  Cluster Status (Phase C)
# =============================================================================

@router.get("/cluster/status")
async def get_cluster_status(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.cluster.read")),
):
    """Get cluster status."""
    return await worker_service.get_cluster_status()


# =============================================================================
#  Observability (Phase C)
# =============================================================================

@router.get("/observability/metrics")
async def get_observability_metrics(
    name: str = Query(""),
    minutes: int = Query(60, ge=1, le=1440),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.observability.read")),
):
    """Get observability metrics."""
    return await observability_service.get_metrics(name=name, minutes=minutes)


@router.get("/observability/traces")
async def get_traces(
    service: str = Query(""),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.observability.read")),
):
    """Get distributed traces."""
    return await observability_service.get_traces(service=service, limit=limit)


# =============================================================================
#  Disaster Recovery (Phase C)
# =============================================================================

@router.get("/disaster-recovery/status")
async def get_dr_status(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.dr.read")),
):
    """Get disaster recovery status."""
    return disaster_recovery_service.get_status()


@router.post("/disaster-recovery/backup")
async def trigger_backup(
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.dr.manage")),
):
    """Trigger a manual backup."""
    result = await disaster_recovery_service.create_backup()
    return result


@router.post("/disaster-recovery/restore")
async def restore_backup(
    backup_id: str = Query(...),
    current_user=Depends(deps.get_current_active_user),
    _=Depends(require_eaac_authorization("operations.dr.manage")),
):
    """Restore from backup."""
    result = await disaster_recovery_service.restore(backup_id)
    return result