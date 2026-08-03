"""
asset.py — FastAPI Router for Enterprise Asset & Device Management System
Sprint 5 — Entity 1: Asset & Device Management

All endpoints are EAAC-protected via require_eaac_authorization dependency.
Integrates with: Authentication, Organization, Permission System, Subscription,
Data Scope Engine, Resource Ownership Engine, Approval Workflow Engine.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.api.deps import get_db, get_current_active_user
from app.api.eaac_deps import require_eaac_authorization
from app.db.models.all_models import (
    Asset, AssetCategory, AssetAssignment, AssetMaintenance,
    AssetDepreciation, AssetDisposal, AssetAudit, AssetAuditResult,
    AssetInsurance, AssetLicense, Vendor, PurchaseOrder,
    PurchaseOrderItem, AssetConsumable, ConsumableIssuance, User, Department
)
from app.crud.crud_asset import (
    crud_asset_category, crud_asset, crud_asset_assignment,
    crud_asset_maintenance, crud_asset_depreciation, crud_asset_disposal,
    crud_asset_audit, crud_asset_audit_result, crud_asset_insurance,
    crud_asset_license, crud_vendor, crud_purchase_order,
    crud_asset_consumable, crud_consumable_issuance
)
from app.schema.asset import (
    AssetCategoryCreate, AssetCategoryUpdate, AssetCategoryResponse,
    AssetCreate, AssetUpdate, AssetResponse,
    AssetAssignmentCreate, AssetReturnData, AssetAssignmentResponse,
    AssetMaintenanceCreate, AssetMaintenanceComplete, AssetMaintenanceResponse,
    AssetDepreciationCreate, AssetDepreciationResponse,
    AssetDisposalCreate, AssetDisposalResponse,
    AssetAuditCreate, AssetAuditResultCreate, AssetAuditResponse,
    AssetInsuranceCreate, AssetInsuranceResponse,
    AssetLicenseCreate, AssetLicenseResponse,
    VendorCreate, VendorUpdate, VendorResponse,
    PurchaseOrderCreate, PurchaseOrderResponse, ReceiveItemData,
    AssetConsumableCreate, AssetConsumableUpdate, AssetConsumableResponse,
    ConsumableIssuanceCreate, ConsumableIssuanceResponse,
    AssetAnalyticsResponse
)
from app.services.asset_engine import (
    asset_depreciation_engine, asset_audit_engine,
    asset_compliance_engine, asset_report_engine
)

router = APIRouter()


# ============================================================================
#  ASSET CATEGORIES
# ============================================================================

@router.get("/categories", response_model=List[AssetCategoryResponse])
def list_asset_categories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """List all asset categories for the organization."""
    return crud_asset_category.get_all_for_org(db, current_user.org_id)[skip:skip + limit]


@router.post("/categories", response_model=AssetCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_asset_category(
    payload: AssetCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.create", action="create"))
):
    """Create a new asset category."""
    return crud_asset_category.create(db, current_user.org_id, payload.model_dump())


@router.get("/categories/{category_id}", response_model=AssetCategoryResponse)
def get_asset_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Get a specific asset category."""
    cat = crud_asset_category.get_by_id(db, category_id)
    if not cat or cat.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


@router.patch("/categories/{category_id}", response_model=AssetCategoryResponse)
def update_asset_category(
    category_id: int,
    payload: AssetCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.update", action="update"))
):
    """Update an asset category."""
    cat = crud_asset_category.get_by_id(db, category_id)
    if not cat or cat.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Category not found")
    return crud_asset_category.update(db, cat, payload.model_dump(exclude_unset=True))


# ============================================================================
#  ASSETS (INVENTORY)
# ============================================================================

@router.get("/inventory", response_model=List[AssetResponse])
def list_assets(
    status: Optional[str] = Query(None),
    asset_type: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """List assets with search and filters."""
    q = db.query(Asset).filter(
        Asset.organization_id == current_user.org_id,
        Asset.is_active.is_(True)
    )
    if status:
        q = q.filter(Asset.status == status)
    if asset_type:
        q = q.filter(Asset.asset_type == asset_type)
    if category_id:
        q = q.filter(Asset.category_id == category_id)
    if search:
        search_term = f"%{search}%"
        q = q.filter(
            or_(
                Asset.name.ilike(search_term),
                Asset.asset_tag.ilike(search_term),
                Asset.serial_no.ilike(search_term),
                Asset.model.ilike(search_term)
            )
        )

    assets = q.order_by(Asset.created_at.desc()).offset(skip).limit(limit).all()
    result = []
    for a in assets:
        cat_name = a.category.name if a.category else None
        assign_name = a.assigned_to.full_name if a.assigned_to else None
        vendor_name = a.vendor.vendor_name if a.vendor else None
        result.append({
            **{c.name: getattr(a, c.name) for c in Asset.__table__.columns},
            "category_name": cat_name,
            "assigned_to_name": assign_name,
            "vendor_name": vendor_name
        })
    return result


@router.post("/inventory", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(
    payload: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.create", action="create"))
):
    """Register a new asset in the inventory."""
    existing = crud_asset.get_by_tag(db, current_user.org_id, payload.asset_tag)
    if existing:
        raise HTTPException(status_code=400, detail=f"Asset tag '{payload.asset_tag}' already exists")

    asset = crud_asset.create(db, current_user.org_id, payload.model_dump(exclude_unset=True))
    cat_name = asset.category.name if asset.category else None
    vendor_name = asset.vendor.vendor_name if asset.vendor else None
    return {**{c.name: getattr(asset, c.name) for c in Asset.__table__.columns},
            "category_name": cat_name, "assigned_to_name": None, "vendor_name": vendor_name}


@router.get("/inventory/{asset_id}", response_model=AssetResponse)
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Get a single asset with full details."""
    asset = crud_asset.get_by_id(db, asset_id)
    if not asset or asset.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    cat_name = asset.category.name if asset.category else None
    assign_name = asset.assigned_to.full_name if asset.assigned_to else None
    vendor_name = asset.vendor.vendor_name if asset.vendor else None
    return {**{c.name: getattr(asset, c.name) for c in Asset.__table__.columns},
            "category_name": cat_name, "assigned_to_name": assign_name, "vendor_name": vendor_name}


@router.patch("/inventory/{asset_id}", response_model=AssetResponse)
def update_asset(
    asset_id: int,
    payload: AssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.update", action="update"))
):
    """Update asset details."""
    asset = crud_asset.get_by_id(db, asset_id)
    if not asset or asset.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    updated = crud_asset.update(db, asset, payload.model_dump(exclude_unset=True))
    cat_name = updated.category.name if updated.category else None
    assign_name = updated.assigned_to.full_name if updated.assigned_to else None
    vendor_name = updated.vendor.vendor_name if updated.vendor else None
    return {**{c.name: getattr(updated, c.name) for c in Asset.__table__.columns},
            "category_name": cat_name, "assigned_to_name": assign_name, "vendor_name": vendor_name}


@router.delete("/inventory/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.delete", action="delete"))
):
    """Soft-delete an asset."""
    asset = crud_asset.get_by_id(db, asset_id)
    if not asset or asset.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset.is_active = False
    asset.status = "archived"
    db.commit()


# ============================================================================
#  ASSIGNMENTS
# ============================================================================

@router.post("/assignments", response_model=AssetAssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_asset(
    payload: AssetAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.assign", action="create"))
):
    """Assign an asset to a user."""
    asset = crud_asset.get_by_id(db, payload.asset_id)
    if not asset or asset.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.status not in ("available", "inventory"):
        raise HTTPException(status_code=400, detail=f"Asset is not available (status: {asset.status})")

    assignment = crud_asset_assignment.create(db, current_user.org_id, current_user.id, payload.model_dump())
    user = db.query(User).filter(User.id == payload.assigned_to_user_id).first()
    return {
        **{c.name: getattr(assignment, c.name) for c in AssetAssignment.__table__.columns},
        "asset_name": asset.name,
        "asset_tag": asset.asset_tag,
        "assigned_to_name": user.full_name if user else None
    }


@router.post("/assignments/{assignment_id}/return", response_model=AssetAssignmentResponse)
def return_asset(
    assignment_id: int,
    payload: AssetReturnData,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.return", action="update"))
):
    """Return an assigned asset."""
    assignment = crud_asset_assignment.get_by_id(db, assignment_id)
    if not assignment or assignment.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.status != "active":
        raise HTTPException(status_code=400, detail="Assignment is not active")

    returned = crud_asset_assignment.return_asset(db, assignment, payload.model_dump())
    asset = crud_asset.get_by_id(db, returned.asset_id)
    user = db.query(User).filter(User.id == returned.assigned_to_user_id).first()
    return {
        **{c.name: getattr(returned, c.name) for c in AssetAssignment.__table__.columns},
        "asset_name": asset.name if asset else None,
        "asset_tag": asset.asset_tag if asset else None,
        "assigned_to_name": user.full_name if user else None
    }


@router.get("/assignments", response_model=List[AssetAssignmentResponse])
def list_assignments(
    asset_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """List asset assignments with filters."""
    q = db.query(AssetAssignment).filter(AssetAssignment.organization_id == current_user.org_id)
    if asset_id:
        q = q.filter(AssetAssignment.asset_id == asset_id)
    if user_id:
        q = q.filter(AssetAssignment.assigned_to_user_id == user_id)
    if status_filter:
        q = q.filter(AssetAssignment.status == status_filter)

    assignments = q.order_by(AssetAssignment.assigned_at.desc()).offset(skip).limit(limit).all()
    result = []
    for a in assignments:
        asset = crud_asset.get_by_id(db, a.asset_id)
        user = db.query(User).filter(User.id == a.assigned_to_user_id).first()
        result.append({
            **{c.name: getattr(a, c.name) for c in AssetAssignment.__table__.columns},
            "asset_name": asset.name if asset else None,
            "asset_tag": asset.asset_tag if asset else None,
            "assigned_to_name": user.full_name if user else None
        })
    return result


@router.get("/assignments/active", response_model=List[AssetAssignmentResponse])
def get_my_assets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Get assets assigned to the current user."""
    assignments = crud_asset_assignment.get_active_for_user(db, current_user.org_id, current_user.id)
    result = []
    for a in assignments:
        asset = crud_asset.get_by_id(db, a.asset_id)
        result.append({
            **{c.name: getattr(a, c.name) for c in AssetAssignment.__table__.columns},
            "asset_name": asset.name if asset else None,
            "asset_tag": asset.asset_tag if asset else None,
            "assigned_to_name": current_user.full_name
        })
    return result


# ============================================================================
#  MAINTENANCE
# ============================================================================

@router.post("/maintenance", response_model=AssetMaintenanceResponse, status_code=status.HTTP_201_CREATED)
def schedule_maintenance(
    payload: AssetMaintenanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.maintenance", action="create"))
):
    """Schedule or log maintenance for an asset."""
    asset = crud_asset.get_by_id(db, payload.asset_id)
    if not asset or asset.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    maint = crud_asset_maintenance.create(db, current_user.org_id, payload.model_dump(exclude_unset=True))
    return {
        **{c.name: getattr(maint, c.name) for c in AssetMaintenance.__table__.columns},
        "asset_name": asset.name,
        "asset_tag": asset.asset_tag
    }


@router.get("/maintenance", response_model=List[AssetMaintenanceResponse])
def list_maintenance(
    asset_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """List maintenance records."""
    if asset_id:
        records = crud_asset_maintenance.get_for_asset(db, asset_id)
    else:
        records = crud_asset_maintenance.get_for_org(db, current_user.org_id, status=status_filter)

    records = records[skip:skip + limit]
    result = []
    for m in records:
        asset = crud_asset.get_by_id(db, m.asset_id)
        result.append({
            **{c.name: getattr(m, c.name) for c in AssetMaintenance.__table__.columns},
            "asset_name": asset.name if asset else None,
            "asset_tag": asset.asset_tag if asset else None
        })
    return result


@router.get("/maintenance/{maint_id}", response_model=AssetMaintenanceResponse)
def get_maintenance(
    maint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Get a maintenance record."""
    maint = crud_asset_maintenance.get_by_id(db, maint_id)
    if not maint or maint.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    asset = crud_asset.get_by_id(db, maint.asset_id)
    return {
        **{c.name: getattr(maint, c.name) for c in AssetMaintenance.__table__.columns},
        "asset_name": asset.name if asset else None,
        "asset_tag": asset.asset_tag if asset else None
    }


@router.post("/maintenance/{maint_id}/complete", response_model=AssetMaintenanceResponse)
def complete_maintenance(
    maint_id: int,
    payload: AssetMaintenanceComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.maintenance", action="update"))
):
    """Mark maintenance as completed."""
    maint = crud_asset_maintenance.get_by_id(db, maint_id)
    if not maint or maint.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Maintenance record not found")

    completed = crud_asset_maintenance.complete(db, maint, payload.model_dump(exclude_unset=True))
    asset = crud_asset.get_by_id(db, completed.asset_id)
    return {
        **{c.name: getattr(completed, c.name) for c in AssetMaintenance.__table__.columns},
        "asset_name": asset.name if asset else None,
        "asset_tag": asset.asset_tag if asset else None
    }


# ============================================================================
#  WARRANTY
# ============================================================================

@router.get("/warranty/expiring")
def get_warranty_expiring(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Get assets with warranty expiring within specified days."""
    assets = asset_compliance_engine.get_warranty_expiring_soon(db, current_user.org_id, days)
    result = []
    for a in assets:
        result.append({
            "id": a.id,
            "asset_tag": a.asset_tag,
            "name": a.name,
            "serial_no": a.serial_no,
            "warranty_expiry": a.warranty_expiry.isoformat() if a.warranty_expiry else None,
            "warranty_provider": a.warranty_provider,
            "days_remaining": (a.warranty_expiry - datetime.now(timezone.utc)).days if a.warranty_expiry else None
        })
    return result


# ============================================================================
#  VENDORS
# ============================================================================

@router.get("/vendors", response_model=List[VendorResponse])
def list_vendors(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """List all vendors."""
    return crud_vendor.get_all_for_org(db, current_user.org_id)[skip:skip + limit]


@router.post("/vendors", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
def create_vendor(
    payload: VendorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.create", action="create"))
):
    """Create a new vendor."""
    return crud_vendor.create(db, current_user.org_id, payload.model_dump())


@router.get("/vendors/{vendor_id}", response_model=VendorResponse)
def get_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Get a vendor by ID."""
    vendor = crud_vendor.get_by_id(db, vendor_id)
    if not vendor or vendor.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


@router.patch("/vendors/{vendor_id}", response_model=VendorResponse)
def update_vendor(
    vendor_id: int,
    payload: VendorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.update", action="update"))
):
    """Update a vendor."""
    vendor = crud_vendor.get_by_id(db, vendor_id)
    if not vendor or vendor.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return crud_vendor.update(db, vendor, payload.model_dump(exclude_unset=True))


# ============================================================================
#  PURCHASE ORDERS
# ============================================================================

@router.get("/purchase-orders", response_model=List[PurchaseOrderResponse])
def list_purchase_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """List purchase orders."""
    pos = crud_purchase_order.get_all_for_org(db, current_user.org_id)[skip:skip + limit]
    result = []
    for po in pos:
        result.append({
            **{c.name: getattr(po, c.name) for c in PurchaseOrder.__table__.columns},
            "vendor_name": po.vendor.vendor_name if po.vendor else None,
            "items": [{"id": i.id, "item_name": i.item_name, "quantity": i.quantity,
                       "received_quantity": i.received_quantity, "unit_price": i.unit_price,
                       "total_price": i.total_price} for i in po.items]
        })
    return result


@router.post("/purchase-orders", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.create", action="create"))
):
    """Create a new purchase order."""
    po = crud_purchase_order.create(db, current_user.org_id, current_user.id, payload.model_dump())
    return {
        **{c.name: getattr(po, c.name) for c in PurchaseOrder.__table__.columns},
        "vendor_name": po.vendor.vendor_name if po.vendor else None,
        "items": [{"id": i.id, "item_name": i.item_name, "quantity": i.quantity,
                   "received_quantity": i.received_quantity, "unit_price": i.unit_price,
                   "total_price": i.total_price} for i in po.items]
    }


@router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderResponse)
def get_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Get a purchase order."""
    po = crud_purchase_order.get_by_id(db, po_id)
    if not po or po.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return {
        **{c.name: getattr(po, c.name) for c in PurchaseOrder.__table__.columns},
        "vendor_name": po.vendor.vendor_name if po.vendor else None,
        "items": [{"id": i.id, "item_name": i.item_name, "quantity": i.quantity,
                   "received_quantity": i.received_quantity, "unit_price": i.unit_price,
                   "total_price": i.total_price} for i in po.items]
    }


@router.post("/purchase-orders/{po_id}/receive", response_model=PurchaseOrderResponse)
def receive_purchase_order(
    po_id: int,
    items_payload: List[ReceiveItemData],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.update", action="update"))
):
    """Receive items for a purchase order."""
    po = crud_purchase_order.get_by_id(db, po_id)
    if not po or po.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    updated_po = crud_purchase_order.receive_items(db, po, [i.model_dump() for i in items_payload])
    return {
        **{c.name: getattr(updated_po, c.name) for c in PurchaseOrder.__table__.columns},
        "vendor_name": updated_po.vendor.vendor_name if updated_po.vendor else None,
        "items": [{"id": i.id, "item_name": i.item_name, "quantity": i.quantity,
                   "received_quantity": i.received_quantity, "unit_price": i.unit_price,
                   "total_price": i.total_price} for i in updated_po.items]
    }


# ============================================================================
#  SOFTWARE LICENSES
# ============================================================================

@router.get("/licenses", response_model=List[AssetLicenseResponse])
def list_licenses(
    asset_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """List software licenses."""
    q = db.query(AssetLicense).filter(AssetLicense.organization_id == current_user.org_id)
    if asset_id:
        q = q.filter(AssetLicense.asset_id == asset_id)
    if status_filter:
        q = q.filter(AssetLicense.status == status_filter)

    licenses = q.order_by(AssetLicense.created_at.desc()).offset(skip).limit(limit).all()
    result = []
    for lic in licenses:
        asset = crud_asset.get_by_id(db, lic.asset_id)
        result.append({
            **{c.name: getattr(lic, c.name) for c in AssetLicense.__table__.columns},
            "asset_name": asset.name if asset else None
        })
    return result


@router.post("/licenses", response_model=AssetLicenseResponse, status_code=status.HTTP_201_CREATED)
def create_license(
    payload: AssetLicenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.create", action="create"))
):
    """Add a software license record."""
    asset = crud_asset.get_by_id(db, payload.asset_id)
    if not asset or asset.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    lic = crud_asset_license.create(db, current_user.org_id, payload.model_dump())
    return {**{c.name: getattr(lic, c.name) for c in AssetLicense.__table__.columns},
            "asset_name": asset.name}


@router.get("/licenses/expiring")
def get_licenses_expiring(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Get licenses expiring within specified days."""
    licenses = asset_compliance_engine.get_license_expiring_soon(db, current_user.org_id, days)
    result = []
    for lic in licenses:
        days_remaining = (lic.expiry_date - datetime.now(timezone.utc)).days if lic.expiry_date else None
        result.append({
            "id": lic.id,
            "license_key": lic.license_key,
            "license_type": lic.license_type,
            "provider": lic.provider,
            "total_seats": lic.total_seats,
            "used_seats": lic.used_seats,
            "expiry_date": lic.expiry_date.isoformat() if lic.expiry_date else None,
            "days_remaining": days_remaining,
            "status": lic.status
        })
    return result


# ============================================================================
#  AUDITS
# ============================================================================

@router.get("/audits", response_model=List[AssetAuditResponse])
def list_audits(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.audit", action="read"))
):
    """List asset audits."""
    audits = crud_asset_audit.get_for_org(db, current_user.org_id)[skip:skip + limit]
    result = []
    for a in audits:
        results = crud_asset_audit_result.get_for_audit(db, a.id)
        result.append({
            **{c.name: getattr(a, c.name) for c in AssetAudit.__table__.columns},
            "conducted_by_name": a.conducted_by.full_name if a.conducted_by else None,
            "results": [{"id": r.id, "asset_id": r.asset_id, "is_present": r.is_present,
                         "verified_condition": r.verified_condition, "discrepancy_notes": r.discrepancy_notes}
                        for r in results]
        })
    return result


@router.post("/audits", response_model=AssetAuditResponse, status_code=status.HTTP_201_CREATED)
def create_audit(
    payload: AssetAuditCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.audit", action="create"))
):
    """Create a new asset audit."""
    audit = crud_asset_audit.create(db, current_user.org_id, payload.model_dump())
    return {**{c.name: getattr(audit, c.name) for c in AssetAudit.__table__.columns},
            "conducted_by_name": None, "results": []}


@router.get("/audits/{audit_id}", response_model=AssetAuditResponse)
def get_audit(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.audit", action="read"))
):
    """Get an audit with results."""
    audit = crud_asset_audit.get_by_id(db, audit_id)
    if not audit or audit.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Audit not found")

    results = crud_asset_audit_result.get_for_audit(db, audit.id)
    return {
        **{c.name: getattr(audit, c.name) for c in AssetAudit.__table__.columns},
        "conducted_by_name": audit.conducted_by.full_name if audit.conducted_by else None,
        "results": [{"id": r.id, "asset_id": r.asset_id, "is_present": r.is_present,
                     "verified_condition": r.verified_condition, "discrepancy_notes": r.discrepancy_notes}
                    for r in results]
    }


@router.post("/audits/{audit_id}/complete", response_model=AssetAuditResponse)
def complete_audit(
    audit_id: int,
    results: List[AssetAuditResultCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.audit", action="update"))
):
    """Complete an audit with verification results."""
    audit = crud_asset_audit.get_by_id(db, audit_id)
    if not audit or audit.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Audit not found")
    if audit.status == "completed":
        raise HTTPException(status_code=400, detail="Audit is already completed")

    completed = asset_audit_engine.complete_audit(db, audit, [r.model_dump() for r in results])
    audit_results = crud_asset_audit_result.get_for_audit(db, completed.id)
    return {
        **{c.name: getattr(completed, c.name) for c in AssetAudit.__table__.columns},
        "conducted_by_name": completed.conducted_by.full_name if completed.conducted_by else None,
        "results": [{"id": r.id, "asset_id": r.asset_id, "is_present": r.is_present,
                     "verified_condition": r.verified_condition, "discrepancy_notes": r.discrepancy_notes}
                    for r in audit_results]
    }


# ============================================================================
#  DEPRECIATION
# ============================================================================

@router.post("/depreciation/compute", response_model=AssetDepreciationResponse)
def compute_depreciation(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.update", action="update"))
):
    """Compute and record depreciation for an asset."""
    asset = crud_asset.get_by_id(db, asset_id)
    if not asset or asset.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    entry = asset_depreciation_engine.compute_and_create_entries(db, current_user.org_id, asset_id)
    if not entry:
        raise HTTPException(status_code=400, detail="Could not compute depreciation (asset may be inactive)")

    return {**{c.name: getattr(entry, c.name) for c in AssetDepreciation.__table__.columns}}


@router.get("/depreciation/{asset_id}", response_model=List[AssetDepreciationResponse])
def get_depreciation_schedule(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Get depreciation schedule for an asset."""
    entries = crud_asset_depreciation.get_for_asset(db, asset_id)
    return [{**{c.name: getattr(e, c.name) for c in AssetDepreciation.__table__.columns}} for e in entries]


# ============================================================================
#  DISPOSALS
# ============================================================================

@router.get("/disposals", response_model=List[AssetDisposalResponse])
def list_disposals(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """List asset disposals."""
    disposals = crud_asset_disposal.get_for_org(db, current_user.org_id)[skip:skip + limit]
    result = []
    for d in disposals:
        asset = crud_asset.get_by_id(db, d.asset_id)
        result.append({
            **{c.name: getattr(d, c.name) for c in AssetDisposal.__table__.columns},
            "asset_name": asset.name if asset else None,
            "asset_tag": asset.asset_tag if asset else None
        })
    return result


@router.post("/disposals", response_model=AssetDisposalResponse, status_code=status.HTTP_201_CREATED)
def dispose_asset(
    payload: AssetDisposalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.delete", action="delete"))
):
    """Dispose/retire an asset."""
    asset = crud_asset.get_by_id(db, payload.asset_id)
    if not asset or asset.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    disp = crud_asset_disposal.create(db, current_user.org_id, current_user.id, payload.model_dump())
    return {
        **{c.name: getattr(disp, c.name) for c in AssetDisposal.__table__.columns},
        "asset_name": asset.name,
        "asset_tag": asset.asset_tag
    }


# ============================================================================
#  INSURANCE
# ============================================================================

@router.post("/insurance", response_model=AssetInsuranceResponse, status_code=status.HTTP_201_CREATED)
def add_insurance(
    payload: AssetInsuranceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.create", action="create"))
):
    """Add insurance policy for an asset."""
    asset = crud_asset.get_by_id(db, payload.asset_id)
    if not asset or asset.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    ins = crud_asset_insurance.create(db, current_user.org_id, payload.model_dump())
    return {**{c.name: getattr(ins, c.name) for c in AssetInsurance.__table__.columns},
            "asset_name": asset.name}


@router.get("/insurance/{asset_id}", response_model=List[AssetInsuranceResponse])
def get_asset_insurance(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Get insurance policies for an asset."""
    policies = crud_asset_insurance.get_for_asset(db, asset_id)
    result = []
    for p in policies:
        asset = crud_asset.get_by_id(db, p.asset_id)
        result.append({
            **{c.name: getattr(p, c.name) for c in AssetInsurance.__table__.columns},
            "asset_name": asset.name if asset else None
        })
    return result


# ============================================================================
#  CONSUMABLES
# ============================================================================

@router.get("/consumables", response_model=List[AssetConsumableResponse])
def list_consumables(
    low_stock_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """List consumable inventory."""
    consumables = crud_asset_consumable.get_all_for_org(db, current_user.org_id, low_stock=low_stock_only)
    consumables = consumables[skip:skip + limit]
    result = []
    for c in consumables:
        vendor_name = c.vendor.vendor_name if c.vendor else None
        result.append({
            **{col.name: getattr(c, col.name) for col in AssetConsumable.__table__.columns},
            "vendor_name": vendor_name,
            "is_low_stock": c.quantity_in_stock <= c.minimum_stock_level
        })
    return result


@router.post("/consumables", response_model=AssetConsumableResponse, status_code=status.HTTP_201_CREATED)
def create_consumable(
    payload: AssetConsumableCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.create", action="create"))
):
    """Add a consumable item."""
    c = crud_asset_consumable.create(db, current_user.org_id, payload.model_dump())
    vendor_name = c.vendor.vendor_name if c.vendor else None
    return {
        **{col.name: getattr(c, col.name) for col in AssetConsumable.__table__.columns},
        "vendor_name": vendor_name,
        "is_low_stock": c.quantity_in_stock <= c.minimum_stock_level
    }


@router.get("/consumables/{consumable_id}", response_model=AssetConsumableResponse)
def get_consumable(
    consumable_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Get a consumable item."""
    c = crud_asset_consumable.get_by_id(db, consumable_id)
    if not c or c.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Consumable not found")
    vendor_name = c.vendor.vendor_name if c.vendor else None
    return {
        **{col.name: getattr(c, col.name) for col in AssetConsumable.__table__.columns},
        "vendor_name": vendor_name,
        "is_low_stock": c.quantity_in_stock <= c.minimum_stock_level
    }


@router.patch("/consumables/{consumable_id}", response_model=AssetConsumableResponse)
def update_consumable(
    consumable_id: int,
    payload: AssetConsumableUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.update", action="update"))
):
    """Update a consumable."""
    c = crud_asset_consumable.get_by_id(db, consumable_id)
    if not c or c.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Consumable not found")
    updated = crud_asset_consumable.update(db, c, payload.model_dump(exclude_unset=True))
    vendor_name = updated.vendor.vendor_name if updated.vendor else None
    return {
        **{col.name: getattr(updated, col.name) for col in AssetConsumable.__table__.columns},
        "vendor_name": vendor_name,
        "is_low_stock": updated.quantity_in_stock <= updated.minimum_stock_level
    }


# ============================================================================
#  CONSUMABLE ISSUANCE
# ============================================================================

@router.get("/consumable-issuances", response_model=List[ConsumableIssuanceResponse])
def list_issuances(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """List consumable issuances."""
    issuances = crud_consumable_issuance.get_for_org(db, current_user.org_id)[skip:skip + limit]
    result = []
    for iss in issuances:
        consumable = crud_asset_consumable.get_by_id(db, iss.consumable_id)
        user = db.query(User).filter(User.id == iss.issued_to_user_id).first()
        result.append({
            **{c.name: getattr(iss, c.name) for c in ConsumableIssuance.__table__.columns},
            "consumable_name": consumable.name if consumable else None,
            "issued_to_name": user.full_name if user else None
        })
    return result


@router.post("/consumable-issuances", response_model=ConsumableIssuanceResponse, status_code=status.HTTP_201_CREATED)
def issue_consumable(
    payload: ConsumableIssuanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.update", action="update"))
):
    """Issue a consumable to an employee."""
    consumable = crud_asset_consumable.get_by_id(db, payload.consumable_id)
    if not consumable or consumable.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Consumable not found")
    if consumable.quantity_in_stock < payload.quantity:
        raise HTTPException(status_code=400, detail=f"Insufficient stock. Available: {consumable.quantity_in_stock}")

    issuance = crud_consumable_issuance.issue(db, current_user.org_id, current_user.id, payload.model_dump())
    user = db.query(User).filter(User.id == payload.issued_to_user_id).first()
    return {
        **{c.name: getattr(issuance, c.name) for c in ConsumableIssuance.__table__.columns},
        "consumable_name": consumable.name,
        "issued_to_name": user.full_name if user else None
    }


# ============================================================================
#  DASHBOARD / ANALYTICS
# ============================================================================

@router.get("/dashboard", response_model=AssetAnalyticsResponse)
def get_asset_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Executive dashboard with aggregated asset metrics."""
    analytics = asset_report_engine.get_dashboard_analytics(db, current_user.org_id)
    return AssetAnalyticsResponse(**analytics)


@router.get("/reports/department-allocation")
def get_department_allocation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Get asset allocation by department."""
    dept_data = db.query(
        Department.name,
        func.count(Asset.id).label("total"),
        func.sum(Asset.purchase_cost).label("total_value")
    ).select_from(Department).join(
        Asset, Asset.department_id == Department.id, isouter=True
    ).filter(
        Department.org_id == current_user.org_id,
        Department.is_deleted == 0
    ).group_by(Department.name).all()

    return [{"department": d.name, "total_assets": d.total, "total_value": float(d.total_value or 0)} for d in dept_data]


@router.get("/reports/asset-utilization")
def get_asset_utilization(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Get asset utilization metrics."""
    total = db.query(Asset).filter(
        Asset.organization_id == current_user.org_id, Asset.is_active.is_(True)
    ).count()
    assigned = db.query(Asset).filter(
        Asset.organization_id == current_user.org_id, Asset.is_active.is_(True),
        Asset.status == "assigned"
    ).count()
    available = db.query(Asset).filter(
        Asset.organization_id == current_user.org_id, Asset.is_active.is_(True),
        Asset.status == "available"
    ).count()
    maintenance = db.query(Asset).filter(
        Asset.organization_id == current_user.org_id, Asset.is_active.is_(True),
        Asset.status == "under_maintenance"
    ).count()

    return {
        "total_assets": total,
        "assigned": assigned,
        "available": available,
        "under_maintenance": maintenance,
        "utilization_pct": round((assigned / max(1, total)) * 100, 2) if total > 0 else 0
    }


@router.get("/reports/procurement-trends")
def get_procurement_trends(
    months: int = Query(12, ge=1, le=60),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Get procurement spending trends."""
    from dateutil.relativedelta import relativedelta
    start_date = datetime.now(timezone.utc) - relativedelta(months=months)

    po_data = db.query(
        func.date_trunc('month', PurchaseOrder.created_at).label("month"),
        func.count(PurchaseOrder.id).label("po_count"),
        func.sum(PurchaseOrder.grand_total).label("total_spend")
    ).filter(
        PurchaseOrder.organization_id == current_user.org_id,
        PurchaseOrder.created_at >= start_date,
        PurchaseOrder.status.in_(["received", "ordered", "partially_received"])
    ).group_by("month").order_by("month").all()

    return [{"month": str(d.month), "po_count": d.po_count, "total_spend": float(d.total_spend or 0)} for d in po_data]


@router.get("/reports/maintenance-costs")
def get_maintenance_costs(
    months: int = Query(12, ge=1, le=60),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Get maintenance cost trends."""
    from dateutil.relativedelta import relativedelta
    start_date = datetime.now(timezone.utc) - relativedelta(months=months)

    cost_data = db.query(
        func.date_trunc('month', AssetMaintenance.completed_date).label("month"),
        func.count(AssetMaintenance.id).label("ticket_count"),
        func.sum(AssetMaintenance.cost).label("total_cost")
    ).filter(
        AssetMaintenance.organization_id == current_user.org_id,
        AssetMaintenance.status == "completed",
        AssetMaintenance.completed_date >= start_date
    ).group_by("month").order_by("month").all()

    return [{"month": str(d.month), "ticket_count": d.ticket_count, "total_cost": float(d.total_cost or 0)} for d in cost_data]


@router.get("/search")
def search_assets(
    q: str = Query(..., min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.read", action="read"))
):
    """Full-text search across assets, vendors, and models."""
    term = f"%{q}%"
    assets = db.query(Asset).filter(
        Asset.organization_id == current_user.org_id,
        Asset.is_active.is_(True),
        or_(
            Asset.name.ilike(term),
            Asset.asset_tag.ilike(term),
            Asset.serial_no.ilike(term),
            Asset.model.ilike(term),
            Asset.manufacturer.ilike(term)
        )
    ).order_by(Asset.created_at.desc()).offset(skip).limit(limit).all()

    return [{
        "id": a.id,
        "asset_tag": a.asset_tag,
        "name": a.name,
        "serial_no": a.serial_no,
        "model": a.model,
        "asset_type": a.asset_type,
        "status": a.status,
        "location": a.location
    } for a in assets]


# ============================================================================
#  EXPORT
# ============================================================================

@router.get("/export")
def export_assets(
    status: Optional[str] = Query(None),
    asset_type: Optional[str] = Query(None),
    format: str = Query("json"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.export", action="read"))
):
    """Export assets in JSON or CSV format."""
    q = db.query(Asset).filter(Asset.organization_id == current_user.org_id, Asset.is_active.is_(True))
    if status:
        q = q.filter(Asset.status == status)
    if asset_type:
        q = q.filter(Asset.asset_type == asset_type)

    assets = q.all()
    export_data = []
    for a in assets:
        export_data.append({
            "id": a.id, "asset_tag": a.asset_tag, "name": a.name, "serial_no": a.serial_no,
            "model": a.model, "manufacturer": a.manufacturer, "asset_type": a.asset_type,
            "status": a.status, "condition": a.condition, "location": a.location,
            "purchase_cost": float(a.purchase_cost), "current_value": float(a.current_value),
            "purchase_date": a.purchase_date.isoformat() if a.purchase_date else None,
            "warranty_expiry": a.warranty_expiry.isoformat() if a.warranty_expiry else None,
            "category": a.category.name if a.category else None,
            "assigned_to": a.assigned_to.full_name if a.assigned_to else None
        })

    if format == "csv":
        import csv, io
        output = io.StringIO()
        if export_data:
            writer = csv.DictWriter(output, fieldnames=export_data[0].keys())
            writer.writeheader()
            writer.writerows(export_data)
        return {"export_format": "csv", "data": output.getvalue()}

    return {"export_format": "json", "data": export_data, "count": len(export_data)}


# ============================================================================
#  BULK OPERATIONS (Enterprise Feature)
# ============================================================================

@router.post("/bulk/assign")
def bulk_assign(
    asset_ids: List[int],
    user_id: int,
    assignment_type: str = "permanent",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.assign", action="create"))
):
    """Bulk assign assets to a user."""
    results = {"success": 0, "failed": 0, "errors": []}
    for asset_id in asset_ids:
        asset = crud_asset.get_by_id(db, asset_id)
        if not asset or asset.organization_id != current_user.org_id:
            results["failed"] += 1
            results["errors"].append(f"Asset {asset_id}: not found")
            continue
        if asset.status not in ("available", "inventory"):
            results["failed"] += 1
            results["errors"].append(f"Asset {asset_id}: not available (status: {asset.status})")
            continue

        crud_asset_assignment.create(db, current_user.org_id, current_user.id, {
            "asset_id": asset_id, "assigned_to_user_id": user_id,
            "assignment_type": assignment_type
        })
        results["success"] += 1

    return results


@router.post("/bulk/import")
def bulk_import_assets(
    assets: List[AssetCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.create", action="create"))
):
    """Bulk import assets."""
    results = {"created": 0, "skipped": 0, "errors": []}
    for asset_data in assets:
        existing = crud_asset.get_by_tag(db, current_user.org_id, asset_data.asset_tag)
        if existing:
            results["skipped"] += 1
            results["errors"].append(f"Asset tag '{asset_data.asset_tag}' already exists")
            continue
        try:
            crud_asset.create(db, current_user.org_id, asset_data.model_dump())
            results["created"] += 1
        except Exception as e:
            results["errors"].append(f"Failed to create {asset_data.asset_tag}: {str(e)}")

    return results


# ============================================================================
#  TRANSFERS (Asset Transfer between users/departments)
# ============================================================================

@router.post("/transfers", response_model=AssetAssignmentResponse)
def transfer_asset(
    assignment_id: int,
    new_user_id: int,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _=Depends(require_eaac_authorization("asset.transfer", action="create"))
):
    """Transfer an asset from current assignee to another user."""
    assignment = crud_asset_assignment.get_by_id(db, assignment_id)
    if not assignment or assignment.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.status != "active":
        raise HTTPException(status_code=400, detail="Assignment is not active")

    # Return current assignment
    crud_asset_assignment.return_asset(db, assignment, {"return_notes": f"Transferred to user {new_user_id}"})

    # Create new assignment
    new_assign = crud_asset_assignment.create(db, current_user.org_id, current_user.id, {
        "asset_id": assignment.asset_id,
        "assigned_to_user_id": new_user_id,
        "assignment_type": assignment.assignment_type,
        "notes": notes or f"Transferred from assignment #{assignment_id}"
    })

    asset = crud_asset.get_by_id(db, new_assign.asset_id)
    user = db.query(User).filter(User.id == new_user_id).first()
    return {
        **{c.name: getattr(new_assign, c.name) for c in AssetAssignment.__table__.columns},
        "asset_name": asset.name if asset else None,
        "asset_tag": asset.asset_tag if asset else None,
        "assigned_to_name": user.full_name if user else None
    }

