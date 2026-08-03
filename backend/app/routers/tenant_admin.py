"""
tenant_admin.py — Enterprise Multi-Tenant Admin Router
Sprint 6 — Phase B: Extended with branding, config, domain, analytics endpoints

SuperAdmin-only endpoints for tenant management.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.api.deps import get_current_superadmin
from app.db.models.all_models import User, Organization
from app.services.tenant_provisioning import TenantProvisioningService
from app.services.tenant_lifecycle import TenantLifecycleService
from app.services.tenant_branding import tenant_branding_service
from app.services.tenant_domain import TenantDomainService
from app.services.isolation_service import isolation_service
from app.services.tenant_analytics import tenant_analytics_service
from app.services.config_center import config_center

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenant", tags=["tenant"])

provisioning = TenantProvisioningService()
lifecycle = TenantLifecycleService()
domain_service = TenantDomainService()


# ── Tenant List ──────────────────────────────────────────────────────────

@router.get("/")
def list_tenants(
    search: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """List all tenants (SuperAdmin)."""
    query = db.query(Organization)

    if search:
        query = query.filter(Organization.name.ilike(f"%{search}%"))
    if status:
        if status == "active":
            query = query.filter(Organization.is_active == True)
        elif status == "inactive":
            query = query.filter(Organization.is_active == False)

    total = query.count()
    orgs = query.offset((page - 1) * limit).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": [
            {
                "id": str(o.id),
                "name": o.name,
                "legal_id": o.legal_id,
                "is_active": o.is_active,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orgs
        ],
    }


# ── Tenant Branding ──────────────────────────────────────────────────────

@router.get("/{org_id}/branding")
def get_tenant_branding(
    org_id: str,
    current_user: User = Depends(get_current_superadmin),
):
    """Get tenant branding configuration."""
    try:
        branding = tenant_branding_service.get_branding(UUID(org_id))
        return branding
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{org_id}/branding")
def update_tenant_branding(
    org_id: str,
    branding_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Update tenant branding configuration."""
    try:
        branding = tenant_branding_service.update_branding(
            db=db,
            org_id=UUID(org_id),
            branding_data=branding_data,
            updated_by=current_user.id,
        )
        return branding
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{org_id}/branding/reset")
def reset_tenant_branding(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Reset tenant branding to defaults."""
    try:
        branding = tenant_branding_service.reset_branding(
            db=db, org_id=UUID(org_id), updated_by=current_user.id
        )
        return branding
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{org_id}/branding/preview")
def get_branding_preview(
    org_id: str,
    current_user: User = Depends(get_current_superadmin),
):
    """Get branding preview."""
    try:
        preview = tenant_branding_service.get_branding_preview(UUID(org_id))
        return preview
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── Custom Domain ────────────────────────────────────────────────────────

@router.post("/{org_id}/domain")
def set_custom_domain(
    org_id: str,
    domain: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Set a custom domain for a tenant."""
    try:
        result = tenant_branding_service.set_custom_domain(
            db=db, org_id=UUID(org_id), domain=domain, updated_by=current_user.id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{org_id}/domain/verify")
def verify_domain(
    org_id: str,
    domain: str,
    verified: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Verify a custom domain for a tenant."""
    try:
        result = tenant_branding_service.verify_domain(
            db=db, org_id=UUID(org_id), domain=domain,
            verified=verified, updated_by=current_user.id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── Tenant Configuration ─────────────────────────────────────────────────

@router.get("/{org_id}/config")
def get_tenant_config(
    org_id: str,
    category: Optional[str] = None,
    current_user: User = Depends(get_current_superadmin),
):
    """Get tenant configuration."""
    if category:
        return config_center.get_category(category, org_id=org_id)
    return config_center.get_all(org_id=org_id)


@router.put("/{org_id}/config")
def update_tenant_config(
    org_id: str,
    config: dict,
    current_user: User = Depends(get_current_superadmin),
):
    """Update tenant configuration."""
    count = config_center.set_many(config, org_id=org_id)
    return {"updated": count, "organization_id": org_id}


@router.get("/config/definitions")
def get_config_definitions(
    current_user: User = Depends(get_current_superadmin),
):
    """Get all configuration definitions."""
    return {
        "definitions": config_center.get_definitions(),
        "categories": config_center.get_categories(),
    }


# ── Tenant Lifecycle ─────────────────────────────────────────────────────

@router.post("/{org_id}/suspend")
def suspend_tenant(
    org_id: str,
    reason: str = "Administrative action",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Suspend a tenant."""
    try:
        result = lifecycle.suspend_tenant(
            db=db,
            org_id=UUID(org_id),
            actor_user_id=current_user.id,
            reason=reason,
        )
        return {"success": True, "organization_id": org_id, "status": "suspended", "message": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{org_id}/activate")
def activate_tenant(
    org_id: str,
    reason: str = "Administrative action",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Activate a tenant."""
    try:
        result = lifecycle.activate_tenant(
            db=db,
            org_id=UUID(org_id),
            actor_user_id=current_user.id,
            reason=reason,
        )
        return {"success": True, "organization_id": org_id, "status": "active", "message": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{org_id}")
def delete_tenant(
    org_id: str,
    reason: str = "Administrative action",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Delete (soft) a tenant."""
    try:
        result = lifecycle.delete_tenant(
            db=db,
            org_id=UUID(org_id),
            actor_user_id=current_user.id,
            reason=reason,
        )
        return {"success": True, "organization_id": org_id, "status": "deleted", "message": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── Tenant Isolation ─────────────────────────────────────────────────────

@router.get("/{org_id}/isolation")
def get_tenant_isolation(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Get tenant isolation verification report."""
    report = isolation_service.run_comprehensive_audit(db=db, org_id=UUID(org_id))
    return report


@router.get("/isolation/summary")
def get_isolation_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Get global isolation summary."""
    summary = isolation_service.get_isolation_summary(db=db)
    return summary


# ── Tenant Analytics ─────────────────────────────────────────────────────

@router.get("/{org_id}/analytics")
def get_tenant_analytics(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Get tenant analytics dashboard."""
    try:
        dashboard = tenant_analytics_service.get_tenant_dashboard(
            db=db, org_id=UUID(org_id)
        )
        return dashboard
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/analytics/platform-summary")
def get_platform_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Get platform-wide tenant summary."""
    summary = tenant_analytics_service.get_platform_summary(db=db)
    return summary


# ── Tenant Provisioning ──────────────────────────────────────────────────

@router.post("/provision")
def provision_tenant(
    organization_name: str,
    admin_email: str,
    admin_password: str,
    admin_full_name: str = "System Administrator",
    subscription_plan_code: str = "starter",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Provision a new tenant manually (SuperAdmin)."""
    try:
        result = provisioning.provision_tenant(
            db=db,
            organization_name=organization_name,
            admin_email=admin_email,
            admin_password=admin_password,
            admin_full_name=admin_full_name,
            subscription_plan_code=subscription_plan_code,
        )
        return {
            "success": True,
            "organization_id": result.organization_id,
            "organization_name": result.organization_name,
            "admin_user_id": result.admin_user_id,
            "admin_email": result.admin_email,
            "subscription_plan": result.subscription_plan_name,
            "provisioning_time_ms": result.provisioning_time_ms,
        }
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
