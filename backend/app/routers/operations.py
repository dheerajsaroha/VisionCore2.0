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
from typing import Any

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
