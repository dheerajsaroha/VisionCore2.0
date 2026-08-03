"""
asset_engine.py — Asset & Device Management Service Engine
Sprint 4 — Entity 3

Handles: Asset lifecycle, depreciation calculations, audit logic, 
         compliance checks, warranty tracking, and analytics aggregation.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.db.models.all_models import (
    Asset, AssetCategory, AssetAssignment, AssetMaintenance,
    AssetDepreciation, AssetDisposal, AssetAudit, AssetAuditResult,
    AssetInsurance, AssetLicense, Vendor, PurchaseOrder, PurchaseOrderItem,
    AssetConsumable, ConsumableIssuance, User, Department
)
from app.crud.crud_asset import (
    crud_asset, crud_asset_category, crud_asset_assignment,
    crud_asset_maintenance, crud_asset_depreciation, crud_asset_disposal,
    crud_asset_audit, crud_asset_audit_result, crud_asset_insurance,
    crud_asset_license, crud_vendor, crud_purchase_order,
    crud_asset_consumable, crud_consumable_issuance
)


class AssetDepreciationEngine:
    """Straight-Line and Written Down Value depreciation calculations."""

    @staticmethod
    def calculate_slm(purchase_cost: float, salvage_value: float, useful_life_months: int, months_elapsed: int) -> Tuple[float, float, float]:
        """Straight-Line Method: equal depreciation each period."""
        if useful_life_months <= 0 or months_elapsed <= 0:
            return 0.0, purchase_cost, 0.0
        depreciable_amount = purchase_cost - salvage_value
        monthly_dep = depreciable_amount / useful_life_months
        depreciation_amount = round(monthly_dep * months_elapsed, 2)
        accumulated_dep = depreciation_amount
        book_value = purchase_cost - accumulated_dep
        if book_value < salvage_value:
            book_value = salvage_value
            accumulated_dep = purchase_cost - salvage_value
            depreciation_amount = accumulated_dep
        return round(depreciation_amount, 2), round(book_value, 2), round(accumulated_dep, 2)

    @staticmethod
    def calculate_wdv(purchase_cost: float, rate_pct: float, months_elapsed: int) -> Tuple[float, float, float]:
        """Written Down Value: depreciation at a fixed rate on reducing balance."""
        if months_elapsed <= 0:
            return 0.0, purchase_cost, 0.0
        years = months_elapsed / 12.0
        book_value = purchase_cost * ((1 - rate_pct / 100.0) ** years)
        depreciation_amount = purchase_cost - book_value
        accumulated_dep = depreciation_amount
        return round(depreciation_amount, 2), round(book_value, 2), round(accumulated_dep, 2)

    @staticmethod
    def compute_and_create_entries(db: Session, org_id: UUID, asset_id: int) -> Optional[AssetDepreciation]:
        """Compute depreciation for an asset and create period entry."""
        asset = crud_asset.get_by_id(db, asset_id)
        if not asset or not asset.is_active:
            return None

        purchase_cost = float(asset.purchase_cost)
        salvage = float(asset.salvage_value)
        useful_life = asset.useful_life_months or 60
        method = asset.depreciation_method or "slm"

        # Determine months elapsed since purchase
        now = datetime.now(timezone.utc)
        purchase_date = asset.purchase_date or asset.created_at
        months_elapsed = max(1, (now.year - purchase_date.year) * 12 + (now.month - purchase_date.month))

        if method == "wdv":
            rate_pct = (100.0 / useful_life) * 1.5  # 1.5x SLM rate
            dep_amount, book_val, accum_dep = AssetDepreciationEngine.calculate_wdv(
                purchase_cost, rate_pct, months_elapsed
            )
        else:
            dep_amount, book_val, accum_dep = AssetDepreciationEngine.calculate_slm(
                purchase_cost, salvage, useful_life, months_elapsed
            )

        # Create period entry
        period_start = purchase_date.replace(day=1)
        if period_start.month == 12:
            period_end = period_start.replace(year=period_start.year + 1, month=1) - timedelta(days=1)
        else:
            period_end = period_start.replace(month=period_start.month + 1) - timedelta(days=1)

        dep_entry = crud_asset_depreciation.create_entry(db, org_id, {
            "asset_id": asset_id,
            "period_start": period_start,
            "period_end": now,
            "opening_value": float(asset.purchase_cost),
            "depreciation_amount": dep_amount,
            "closing_value": book_val,
            "accumulated_depreciation": accum_dep,
            "depreciation_method": method
        })

        # Update asset current_value
        asset.current_value = book_val
        db.commit()

        return dep_entry


class AssetAuditEngine:
    """Asset verification and audit lifecycle management."""

    @staticmethod
    def complete_audit(db: Session, audit: AssetAudit, results: List[Dict[str, Any]]) -> AssetAudit:
        """Mark audit as completed with verified results."""
        verified = missing = damaged = 0
        for r in results:
            result = crud_asset_audit_result.create_result(db, {
                "audit_id": audit.id,
                "asset_id": r["asset_id"],
                "verified_location": r.get("verified_location"),
                "verified_condition": r.get("verified_condition"),
                "is_present": r.get("is_present", True),
                "qr_scanned": r.get("qr_scanned", False),
                "discrepancy_notes": r.get("discrepancy_notes"),
                "verified_by_user_id": r.get("verified_by_user_id"),
                "verified_at": r.get("verified_at", datetime.now(timezone.utc))
            })
            if result.is_present:
                verified += 1
            else:
                missing += 1

        audit.status = "completed"
        audit.completed_date = datetime.now(timezone.utc)
        audit.verified_count = verified
        audit.missing_count = missing
        audit.damaged_count = damaged
        audit.discrepancies = {"verified": verified, "missing": missing, "damaged": damaged}
        db.commit()
        db.refresh(audit)
        return audit


class AssetComplianceEngine:
    """Checks asset compliance (warranty, insurance, licenses)."""

    @staticmethod
    def get_warranty_expiring_soon(db: Session, org_id: UUID, days: int = 30) -> List[Asset]:
        now = datetime.now(timezone.utc)
        threshold = now + timedelta(days=days)
        return db.query(Asset).filter(
            Asset.organization_id == org_id,
            Asset.is_active.is_(True),
            Asset.warranty_expiry.isnot(None),
            Asset.warranty_expiry.between(now, threshold)
        ).all()

    @staticmethod
    def get_license_expiring_soon(db: Session, org_id: UUID, days: int = 30) -> List[AssetLicense]:
        now = datetime.now(timezone.utc)
        threshold = now + timedelta(days=days)
        return db.query(AssetLicense).join(Asset).filter(
            AssetLicense.organization_id == org_id,
            AssetLicense.status == "active",
            AssetLicense.expiry_date.isnot(None),
            AssetLicense.expiry_date.between(now, threshold)
        ).all()


class AssetReportEngine:
    """Analytics and reporting aggregation."""

    @staticmethod
    def get_dashboard_analytics(db: Session, org_id: UUID) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)

        # Asset counts by status
        by_status = crud_asset.get_asset_count_by_status(db, org_id)

        # Asset counts by type
        by_type = dict(
            db.query(Asset.asset_type, func.count(Asset.id))
            .filter(Asset.organization_id == org_id, Asset.is_active.is_(True))
            .group_by(Asset.asset_type).all()
        )

        total_assets = sum(by_status.values()) if by_status else 0
        total_value = crud_asset.get_total_asset_value(db, org_id)

        assigned = by_status.get("assigned", 0)
        available = by_status.get("available", 0)
        maintenance = by_status.get("under_maintenance", 0)
        disposed = by_status.get("disposed", 0)

        # Vendors & POs
        vendors = db.query(Vendor).filter(Vendor.organization_id == org_id, Vendor.is_active.is_(True)).count()
        pos = db.query(PurchaseOrder).filter(PurchaseOrder.organization_id == org_id).count()
        pending_pos = db.query(PurchaseOrder).filter(
            PurchaseOrder.organization_id == org_id,
            PurchaseOrder.status.in_(["draft", "pending"])
        ).count()

        # Consumables
        consumables = db.query(AssetConsumable).filter(
            AssetConsumable.organization_id == org_id, AssetConsumable.is_active.is_(True)
        ).count()
        low_stock = db.query(AssetConsumable).filter(
            AssetConsumable.organization_id == org_id,
            AssetConsumable.is_active.is_(True),
            AssetConsumable.quantity_in_stock <= AssetConsumable.minimum_stock_level
        ).count()

        # Expiring warranty & licenses
        warranty_exp = len(AssetComplianceEngine.get_warranty_expiring_soon(db, org_id))
        license_exp = len(AssetComplianceEngine.get_license_expiring_soon(db, org_id))

        # Upcoming maintenance
        upcoming_maint = db.query(AssetMaintenance).filter(
            AssetMaintenance.organization_id == org_id,
            AssetMaintenance.status == "scheduled"
        ).count()

        return {
            "total_assets": total_assets,
            "total_value": round(total_value, 2),
            "assets_by_status": by_status,
            "assets_by_type": by_type,
            "assigned_count": assigned,
            "available_count": available,
            "maintenance_count": maintenance,
            "disposed_count": disposed,
            "total_vendors": vendors,
            "total_purchase_orders": pos,
            "pending_po_count": pending_pos,
            "total_consumables": consumables,
            "low_stock_count": low_stock,
            "warranty_expiring_30_days": warranty_exp,
            "license_expiring_30_days": license_exp,
            "upcoming_maintenance_count": upcoming_maint
        }


# Singleton instances
asset_depreciation_engine = AssetDepreciationEngine()
asset_audit_engine = AssetAuditEngine()
asset_compliance_engine = AssetComplianceEngine()
asset_report_engine = AssetReportEngine()
