"""
asset.py — Pydantic Schemas for Asset & Device Management System
Sprint 4 — Entity 3
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# ── Asset Category Schemas ──
class AssetCategoryCreate(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    parent_category_id: Optional[int] = None
    is_active: bool = True


class AssetCategoryUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    parent_category_id: Optional[int] = None
    is_active: Optional[bool] = None


class AssetCategoryResponse(BaseModel):
    id: int
    organization_id: UUID
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    parent_category_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Asset Schemas ──
class AssetCreate(BaseModel):
    asset_tag: str
    name: str
    description: Optional[str] = None
    category_id: Optional[int] = None
    serial_no: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    asset_type: str = "it_equipment"
    status: str = "available"
    condition: str = "new"
    location: Optional[str] = None
    room_no: Optional[str] = None
    assigned_to_user_id: Optional[int] = None
    department_id: Optional[int] = None
    purchase_date: Optional[datetime] = None
    purchase_cost: float = 0.0
    warranty_expiry: Optional[datetime] = None
    warranty_provider: Optional[str] = None
    warranty_notes: Optional[str] = None
    vendor_id: Optional[int] = None
    purchase_order_id: Optional[int] = None
    depreciation_method: Optional[str] = None
    useful_life_months: int = 60
    salvage_value: float = 0.0
    image_url: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    serial_no: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    asset_type: Optional[str] = None
    status: Optional[str] = None
    condition: Optional[str] = None
    location: Optional[str] = None
    room_no: Optional[str] = None
    current_value: Optional[float] = None
    warranty_expiry: Optional[datetime] = None
    warranty_provider: Optional[str] = None
    is_active: Optional[bool] = None


class AssetResponse(BaseModel):
    id: int
    organization_id: UUID
    asset_tag: str
    name: str
    description: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    serial_no: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    asset_type: str
    status: str
    condition: str
    location: Optional[str] = None
    room_no: Optional[str] = None
    assigned_to_user_id: Optional[int] = None
    assigned_to_name: Optional[str] = None
    department_id: Optional[int] = None
    purchase_date: Optional[datetime] = None
    purchase_cost: float
    current_value: float
    warranty_expiry: Optional[datetime] = None
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None
    depreciation_method: Optional[str] = None
    useful_life_months: int
    salvage_value: float
    image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Asset Assignment Schemas ──
class AssetAssignmentCreate(BaseModel):
    asset_id: int
    assigned_to_user_id: int
    assignment_type: str = "permanent"
    expected_return_at: Optional[datetime] = None
    notes: Optional[str] = None


class AssetReturnData(BaseModel):
    returned_condition: Optional[str] = None
    return_notes: Optional[str] = None


class AssetAssignmentResponse(BaseModel):
    id: int
    organization_id: UUID
    asset_id: int
    asset_name: Optional[str] = None
    asset_tag: Optional[str] = None
    assigned_to_user_id: int
    assigned_to_name: Optional[str] = None
    assigned_by_user_id: int
    assignment_type: str
    assigned_at: datetime
    expected_return_at: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    returned_condition: Optional[str] = None
    return_notes: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Asset Maintenance Schemas ──
class AssetMaintenanceCreate(BaseModel):
    asset_id: int
    maintenance_type: str
    title: str
    description: Optional[str] = None
    vendor_id: Optional[int] = None
    cost: float = 0.0
    scheduled_date: Optional[datetime] = None
    performed_by: Optional[str] = None
    notes: Optional[str] = None
    next_maintenance_date: Optional[datetime] = None


class AssetMaintenanceComplete(BaseModel):
    cost: Optional[float] = None
    performed_by: Optional[str] = None
    notes: Optional[str] = None
    next_maintenance_date: Optional[datetime] = None


class AssetMaintenanceResponse(BaseModel):
    id: int
    organization_id: UUID
    asset_id: int
    asset_name: Optional[str] = None
    asset_tag: Optional[str] = None
    maintenance_type: str
    title: str
    description: Optional[str] = None
    cost: float
    scheduled_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    status: str
    performed_by: Optional[str] = None
    notes: Optional[str] = None
    next_maintenance_date: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Asset Depreciation Schemas ──
class AssetDepreciationCreate(BaseModel):
    asset_id: int
    period_start: datetime
    period_end: datetime
    opening_value: float
    depreciation_amount: float
    closing_value: float
    accumulated_depreciation: float
    depreciation_method: str = "slm"


class AssetDepreciationResponse(BaseModel):
    id: int
    organization_id: UUID
    asset_id: int
    period_start: datetime
    period_end: datetime
    opening_value: float
    depreciation_amount: float
    closing_value: float
    accumulated_depreciation: float
    depreciation_method: str
    is_posted: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Asset Disposal Schemas ──
class AssetDisposalCreate(BaseModel):
    asset_id: int
    disposal_type: str
    disposal_date: Optional[datetime] = None
    disposal_value: float = 0.0
    reason: str
    notes: Optional[str] = None


class AssetDisposalResponse(BaseModel):
    id: int
    organization_id: UUID
    asset_id: int
    asset_name: Optional[str] = None
    asset_tag: Optional[str] = None
    disposal_type: str
    disposal_date: datetime
    disposal_value: float
    book_value_at_disposal: float
    gain_loss: float
    approved_by_user_id: Optional[int] = None
    reason: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Asset Audit Schemas ──
class AssetAuditCreate(BaseModel):
    audit_code: str
    title: str
    audit_type: str = "physical"
    scheduled_date: Optional[datetime] = None
    conducted_by_user_id: Optional[int] = None
    total_assets: int = 0
    notes: Optional[str] = None


class AssetAuditResultCreate(BaseModel):
    audit_id: int
    asset_id: int
    verified_location: Optional[str] = None
    verified_condition: Optional[str] = None
    is_present: bool = True
    qr_scanned: bool = False
    discrepancy_notes: Optional[str] = None
    verified_by_user_id: Optional[int] = None
    verified_at: Optional[datetime] = None


class AssetAuditResultResponse(BaseModel):
    id: int
    audit_id: int
    asset_id: int
    asset_name: Optional[str] = None
    asset_tag: Optional[str] = None
    verified_location: Optional[str] = None
    verified_condition: Optional[str] = None
    is_present: bool
    qr_scanned: bool
    discrepancy_notes: Optional[str] = None
    verified_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AssetAuditResponse(BaseModel):
    id: int
    organization_id: UUID
    audit_code: str
    title: str
    audit_type: str
    status: str
    scheduled_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    conducted_by_user_id: Optional[int] = None
    conducted_by_name: Optional[str] = None
    total_assets: int
    verified_count: int
    missing_count: int
    damaged_count: int
    discrepancies: Optional[dict] = None
    notes: Optional[str] = None
    created_at: datetime
    results: List[AssetAuditResultResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ── Asset Insurance Schemas ──
class AssetInsuranceCreate(BaseModel):
    asset_id: int
    policy_no: str
    insurance_provider: str
    coverage_type: str = "comprehensive"
    sum_insured: float = 0.0
    premium_amount: float = 0.0
    premium_frequency: str = "annual"
    start_date: datetime
    expiry_date: datetime
    documents_url: Optional[str] = None
    notes: Optional[str] = None


class AssetInsuranceResponse(BaseModel):
    id: int
    organization_id: UUID
    asset_id: int
    asset_name: Optional[str] = None
    policy_no: str
    insurance_provider: str
    coverage_type: str
    sum_insured: float
    premium_amount: float
    premium_frequency: str
    start_date: datetime
    expiry_date: datetime
    status: str
    documents_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Asset License Schemas ──
class AssetLicenseCreate(BaseModel):
    asset_id: int
    license_key: str
    license_type: str = "perpetual"
    total_seats: int = 1
    used_seats: int = 0
    purchase_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    renewal_cost: float = 0.0
    is_subscription: bool = False
    provider: Optional[str] = None
    notes: Optional[str] = None


class AssetLicenseResponse(BaseModel):
    id: int
    organization_id: UUID
    asset_id: int
    asset_name: Optional[str] = None
    license_key: str
    license_type: str
    total_seats: int
    used_seats: int
    purchase_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    renewal_cost: float
    status: str
    is_subscription: bool
    provider: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Vendor Schemas ──
class VendorCreate(BaseModel):
    vendor_name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    gst_no: Optional[str] = None
    payment_terms: Optional[str] = None
    is_active: bool = True


class VendorUpdate(BaseModel):
    vendor_name: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    gst_no: Optional[str] = None
    payment_terms: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None


class VendorResponse(BaseModel):
    id: int
    organization_id: UUID
    vendor_name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    gst_no: Optional[str] = None
    payment_terms: Optional[str] = None
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Purchase Order Schemas ──
class PurchaseOrderItemCreate(BaseModel):
    item_name: str
    description: Optional[str] = None
    quantity: int = 1
    unit_price: float = 0.0
    category_id: Optional[int] = None


class PurchaseOrderCreate(BaseModel):
    po_number: str
    vendor_id: int
    order_date: Optional[datetime] = None
    expected_delivery_date: Optional[datetime] = None
    total_amount: float = 0.0
    tax_amount: float = 0.0
    grand_total: float = 0.0
    currency: str = "INR"
    notes: Optional[str] = None
    items: List[PurchaseOrderItemCreate] = []


class ReceiveItemData(BaseModel):
    item_id: int
    quantity: int = 1


class PurchaseOrderResponse(BaseModel):
    id: int
    organization_id: UUID
    po_number: str
    vendor_id: int
    vendor_name: Optional[str] = None
    order_date: datetime
    expected_delivery_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    status: str
    total_amount: float
    tax_amount: float
    grand_total: float
    currency: str
    approved_by_user_id: Optional[int] = None
    notes: Optional[str] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    items: List[Dict[str, Any]] = []

    model_config = ConfigDict(from_attributes=True)


# ── Asset Consumable Schemas ──
class AssetConsumableCreate(BaseModel):
    name: str
    consumable_type: str = "stationery"
    description: Optional[str] = None
    unit_of_measure: str = "pieces"
    quantity_in_stock: int = 0
    minimum_stock_level: int = 0
    unit_price: float = 0.0
    location: Optional[str] = None
    vendor_id: Optional[int] = None


class AssetConsumableUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    unit_of_measure: Optional[str] = None
    quantity_in_stock: Optional[int] = None
    minimum_stock_level: Optional[int] = None
    unit_price: Optional[float] = None
    location: Optional[str] = None
    vendor_id: Optional[int] = None
    is_active: Optional[bool] = None


class AssetConsumableResponse(BaseModel):
    id: int
    organization_id: UUID
    name: str
    consumable_type: str
    description: Optional[str] = None
    unit_of_measure: str
    quantity_in_stock: int
    minimum_stock_level: int
    unit_price: float
    location: Optional[str] = None
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None
    is_active: bool
    is_low_stock: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Consumable Issuance Schemas ──
class ConsumableIssuanceCreate(BaseModel):
    consumable_id: int
    issued_to_user_id: int
    quantity: int = 1
    purpose: Optional[str] = None


class ConsumableIssuanceResponse(BaseModel):
    id: int
    organization_id: UUID
    consumable_id: int
    consumable_name: Optional[str] = None
    issued_to_user_id: int
    issued_to_name: Optional[str] = None
    issued_by_user_id: int
    quantity: int
    purpose: Optional[str] = None
    issued_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Analytics Schemas ──
class AssetAnalyticsResponse(BaseModel):
    total_assets: int
    total_value: float
    assets_by_status: Dict[str, int]
    assets_by_type: Dict[str, int]
    assigned_count: int
    available_count: int
    maintenance_count: int
    disposed_count: int
    total_vendors: int
    total_purchase_orders: int
    pending_po_count: int
    total_consumables: int
    low_stock_count: int
    warranty_expiring_30_days: int
    license_expiring_30_days: int
