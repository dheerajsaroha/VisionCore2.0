"""
analytics_router.py — Centralized Analytics & KPI API Router
Sprint 9 — Enterprise Intelligence & Analytics Layer

Endpoints:
  GET  /api/v1/analytics/dashboard           — Get executive platform analytics summary
  GET  /api/v1/analytics/metrics             — List registered metric definitions
  GET  /api/v1/analytics/metrics/{metric_key}/value — Calculate realtime metric value
  POST /api/v1/analytics/snapshots           — Record a metric snapshot
  GET  /api/v1/analytics/snapshots           — Query historical metric snapshots
  GET  /api/v1/analytics/trends              — Retrieve trend analysis for KPI
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models.all_models import User
from app.services.analytics_platform import AnalyticsPlatform
from app.services.metric_registry import metric_registry_service

logger = logging.getLogger(__name__)
router = APIRouter()
analytics_platform = AnalyticsPlatform()


# The executive dashboard, the metric registry and the snapshot history are
# organization-wide workforce data. The registry's per-metric rules are applied
# in `_require_metric_permission`; these gates cover the aggregate surfaces.
_can_read_analytics = deps.require_permission("analytics.read")


def _holds(db: Session, user: User, permission_name: str) -> bool:
    """Whether `user` holds `permission_name`.

    Only SuperAdmin is treated as holding everything, matching
    `require_permission`.
    """
    from app.api.deps import normalize_role_name
    from app.services.permission_service import PermissionService

    if user.role and normalize_role_name(user.role.name) == "SuperAdmin":
        return True
    return PermissionService.has_any_permission(db, user, [permission_name])


def _require_metric_permission(
    db: Session, user: User, metric_key: str, required: str
) -> None:
    """Enforce the permission a metric declares for itself.

    `MetricDefinition.required_permission` was seeded per metric and never read
    by anything, so `payroll_monthly_cost` and `security_login_failures` were
    reachable by any active session. The column describes the access rule that
    was always intended; this applies it.

    A metric whose required permission does not exist in the RBAC catalog fails
    closed rather than open — an unrecognised rule is a configuration error, and
    treating it as "no restriction" would re-open the hole this closes.
    """
    if not _holds(db, user, required):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Metric '{metric_key}' requires the '{required}' permission.",
        )


def _require_metric_key_permission(db: Session, user: User, metric_key: str) -> None:
    """Apply the declared permission for a metric identified only by key."""
    defn = metric_registry_service.get_metric_definition(db, metric_key)
    if not defn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metric key '{metric_key}' not found in registry.",
        )
    _require_metric_permission(db, user, metric_key, defn.required_permission)


# ── Schemas ───────────────────────────────────────────────────────────────────

class MetricDefinitionResponse(BaseModel):
    id: int
    metric_key: str
    name: str
    description: Optional[str] = None
    category: str
    required_permission: str
    unit: str
    is_active: bool

    class Config:
        from_attributes = True


class SnapshotCreateRequest(BaseModel):
    metric_key: str = Field(..., min_length=1, max_length=100)
    value: float = Field(...)
    dimensions: Optional[Dict[str, Any]] = None


class SnapshotResponse(BaseModel):
    id: int
    organization_id: str
    metric_key: str
    metric_value: float
    dimensions: Optional[Dict[str, Any]] = None
    snapshot_date: str
    created_at: str

    class Config:
        from_attributes = True


class MetricValueResponse(BaseModel):
    metric_key: str
    value: float
    unit: str
    calculated_at: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    summary="Get executive dashboard analytics summary",
    tags=["analytics"],
)
async def get_executive_dashboard(
    current_user: User = Depends(_can_read_analytics),
    db: Session = Depends(deps.get_db),
):
    """
    Returns platform-wide executive analytics aggregated across modules.
    """
    org_id_str = str(current_user.org_id) if current_user.org_id else ""
    # Ensure default metrics exist in registry
    metric_registry_service.seed_default_metrics(db)
    
    dashboard = analytics_platform.get_executive_dashboard(org_id_str)
    return dashboard


@router.get(
    "/metrics",
    response_model=List[MetricDefinitionResponse],
    summary="List all registered metric definitions",
    tags=["analytics"],
)
async def list_metrics(
    category: Optional[str] = Query(None, description="Optional category filter (e.g. workforce, attendance, payroll)"),
    current_user: User = Depends(_can_read_analytics),
    db: Session = Depends(deps.get_db),
):
    """Lists registered metric definitions from Metric Registry."""
    metric_registry_service.seed_default_metrics(db)
    definitions = metric_registry_service.list_metric_definitions(db, category=category)
    return definitions


@router.get(
    "/metrics/{metric_key}/value",
    response_model=MetricValueResponse,
    summary="Calculate realtime metric value for tenant",
    tags=["analytics"],
)
async def get_metric_value(
    metric_key: str,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
):
    """Calculates realtime value of a registered metric key."""
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to an organization.",
        )
    defn = metric_registry_service.get_metric_definition(db, metric_key)
    if not defn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metric key '{metric_key}' not found in registry.",
        )
    _require_metric_permission(db, current_user, metric_key, defn.required_permission)
    val = metric_registry_service.calculate_metric(db, current_user.org_id, metric_key)
    return MetricValueResponse(
        metric_key=metric_key,
        value=val,
        unit=defn.unit,
        calculated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post(
    "/snapshots",
    summary="Record historical metric snapshot",
    tags=["analytics"],
)
async def record_snapshot(
    body: SnapshotCreateRequest,
    current_user: User = Depends(_can_read_analytics),
    db: Session = Depends(deps.get_db),
):
    """Records a metric snapshot for historical analytics and trend tracking."""
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to an organization.",
        )
    snapshot = metric_registry_service.record_snapshot(
        db=db,
        org_id=current_user.org_id,
        metric_key=body.metric_key,
        value=body.value,
        dimensions=body.dimensions,
    )
    return {
        "id": snapshot.id,
        "organization_id": str(snapshot.organization_id),
        "metric_key": snapshot.metric_key,
        "metric_value": float(snapshot.metric_value),
        "dimensions": snapshot.dimensions,
        "snapshot_date": snapshot.snapshot_date.isoformat() if snapshot.snapshot_date else "",
    }


@router.get(
    "/snapshots",
    summary="Query historical metric snapshots",
    tags=["analytics"],
)
async def get_snapshots(
    metric_key: Optional[str] = Query(None, description="Metric key filter"),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(_can_read_analytics),
    db: Session = Depends(deps.get_db),
):
    """Retrieves historical metric snapshots for tenant."""
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to an organization.",
        )
    _require_metric_key_permission(db, current_user, metric_key)
    snapshots = metric_registry_service.get_snapshots(
        db=db,
        org_id=current_user.org_id,
        metric_key=metric_key,
        limit=limit,
    )
    return [
        {
            "id": s.id,
            "organization_id": str(s.organization_id),
            "metric_key": s.metric_key,
            "metric_value": float(s.metric_value),
            "dimensions": s.dimensions,
            "snapshot_date": s.snapshot_date.isoformat() if s.snapshot_date else "",
        }
        for s in snapshots
    ]


@router.get(
    "/trends",
    summary="Get trend analysis for metric",
    tags=["analytics"],
)
async def get_trend_analysis(
    metric_key: str = Query(..., description="Metric key to analyze"),
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(_can_read_analytics),
    db: Session = Depends(deps.get_db),
):
    """Calculates trend direction and historical data points for metric."""
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to an organization.",
        )
    _require_metric_key_permission(db, current_user, metric_key)
    snapshots = metric_registry_service.get_snapshots(
        db=db,
        org_id=current_user.org_id,
        metric_key=metric_key,
        limit=100,
    )
    data_points = [
        {
            "date": s.snapshot_date.isoformat() if s.snapshot_date else "",
            "value": float(s.metric_value),
        }
        for s in reversed(snapshots)
    ]
    trend_direction = "stable"
    if len(data_points) >= 2:
        diff = data_points[-1]["value"] - data_points[0]["value"]
        if diff > 0:
            trend_direction = "upward"
        elif diff < 0:
            trend_direction = "downward"

    return {
        "metric_key": metric_key,
        "period_days": days,
        "trend": trend_direction,
        "data_points": data_points,
    }
