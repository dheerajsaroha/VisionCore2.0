"""
crud_asset.py — CRUD Operations for Asset & Device Management System
Sprint 4 — Entity 3
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.db.models.all_models import (
    AssetCategory, Asset, AssetAssignment, AssetMaintenance,
    AssetDepreciation, AssetDisposal, AssetAudit, AssetAuditResult,
    AssetInsurance, AssetLicense, Vendor, PurchaseOrder,
    PurchaseOrderItem, AssetConsumable, ConsumableIssuance, User
)


class CRUDAssetCategory:
    def get_by_id(self, db: Session, cat_id: int) -> Optional[AssetCategory]:
        return db.query(AssetCategory).filter(AssetCategory.id == cat_id).first()

    def get_all_for_org(self, db: Session, org_id: UUID) -> List[AssetCategory]:
        return db.query(AssetCategory).filter(AssetCategory.organization_id == org_id).order_by(AssetCategory.name).all()

    def create(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> AssetCategory:
        db_obj = AssetCategory(organization_id=org_id, **obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: AssetCategory, updates: Dict[str, Any]) -> AssetCategory:
        for f, v in updates.items():
            if v is not None and hasattr(db_obj, f):
                setattr(db_obj, f, v)
        db.commit()
        db.refresh(db_obj)
        return db_obj


class CRUDAsset:
    def get_by_id(self, db: Session, asset_id: int) -> Optional[Asset]:
        return db.query(Asset).filter(Asset.id == asset_id).first()

    def get_by_tag(self, db: Session, org_id: UUID, tag: str) -> Optional[Asset]:
        return db.query(Asset).filter(Asset.organization_id == org_id, Asset.asset_tag == tag).first()

    def get_all_for_org(self, db: Session, org_id: UUID, status: Optional[str] = None, asset_type: Optional[str] = None) -> List[Asset]:
        q = db.query(Asset).filter(Asset.organization_id == org_id, Asset.is_active.is_(True))
        if status:
            q = q.filter(Asset.status == status)
        if asset_type:
            q = q.filter(Asset.asset_type == asset_type)
        return q.order_by(Asset.created_at.desc()).all()

    def create(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> Asset:
        current_val = obj_in.get("purchase_cost", 0.0)
        db_obj = Asset(
            organization_id=org_id,
            asset_tag=obj_in["asset_tag"],
            name=obj_in["name"],
            description=obj_in.get("description"),
            serial_no=obj_in.get("serial_no"),
            model=obj_in.get("model"),
            manufacturer=obj_in.get("manufacturer"),
            asset_type=obj_in.get("asset_type", "it_equipment"),
            category_id=obj_in.get("category_id"),
            location=obj_in.get("location"),
            room_no=obj_in.get("room_no"),
            assigned_to_user_id=obj_in.get("assigned_to_user_id"),
            department_id=obj_in.get("department_id"),
            purchase_date=obj_in.get("purchase_date"),
            purchase_cost=current_val,
            current_value=current_val,
            warranty_expiry=obj_in.get("warranty_expiry"),
            warranty_provider=obj_in.get("warranty_provider"),
            vendor_id=obj_in.get("vendor_id"),
            purchase_order_id=obj_in.get("purchase_order_id"),
            depreciation_method=obj_in.get("depreciation_method"),
            useful_life_months=obj_in.get("useful_life_months", 60),
            salvage_value=obj_in.get("salvage_value", 0.0),
            image_url=obj_in.get("image_url"),
            meta_data=obj_in.get("meta_data", {}),
            condition=obj_in.get("condition", "new"),
            status=obj_in.get("status", "available")
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: Asset, updates: Dict[str, Any]) -> Asset:
        for f, v in updates.items():
            if v is not None and hasattr(db_obj, f):
                setattr(db_obj, f, v)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_asset_count_by_status(self, db: Session, org_id: UUID) -> Dict[str, int]:
        counts = db.query(Asset.status, func.count(Asset.id)).filter(
            Asset.organization_id == org_id, Asset.is_active.is_(True)
        ).group_by(Asset.status).all()
        return {s: c for s, c in counts}

    def get_total_asset_value(self, db: Session, org_id: UUID) -> float:
        val = db.query(func.sum(Asset.current_value)).filter(
            Asset.organization_id == org_id, Asset.is_active.is_(True)
        ).scalar()
        return float(val or 0.0)


class CRUDAssetAssignment:
    def get_by_id(self, db: Session, assign_id: int) -> Optional[AssetAssignment]:
        return db.query(AssetAssignment).filter(AssetAssignment.id == assign_id).first()

    def get_active_for_asset(self, db: Session, asset_id: int) -> Optional[AssetAssignment]:
        return db.query(AssetAssignment).filter(
            AssetAssignment.asset_id == asset_id, AssetAssignment.status == "active"
        ).first()

    def get_active_for_user(self, db: Session, org_id: UUID, user_id: int) -> List[AssetAssignment]:
        return db.query(AssetAssignment).filter(
            AssetAssignment.organization_id == org_id,
            AssetAssignment.assigned_to_user_id == user_id,
            AssetAssignment.status == "active"
        ).all()

    def get_history_for_asset(self, db: Session, asset_id: int) -> List[AssetAssignment]:
        return db.query(AssetAssignment).filter(AssetAssignment.asset_id == asset_id).order_by(AssetAssignment.assigned_at.desc()).all()

    def create(self, db: Session, org_id: UUID, assigned_by: int, obj_in: Dict[str, Any]) -> AssetAssignment:
        assign = AssetAssignment(
            organization_id=org_id,
            asset_id=obj_in["asset_id"],
            assigned_to_user_id=obj_in["assigned_to_user_id"],
            assigned_by_user_id=assigned_by,
            assignment_type=obj_in.get("assignment_type", "permanent"),
            expected_return_at=obj_in.get("expected_return_at"),
            notes=obj_in.get("notes"),
            status="active"
        )
        db.add(assign)

        # Update asset status
        asset = db.query(Asset).filter(Asset.id == obj_in["asset_id"]).first()
        if asset:
            asset.status = "assigned"
            asset.assigned_to_user_id = obj_in["assigned_to_user_id"]

        db.commit()
        db.refresh(assign)
        return assign

    def return_asset(self, db: Session, assignment: AssetAssignment, return_data: Dict[str, Any]) -> AssetAssignment:
        assignment.returned_at = datetime.now(timezone.utc)
        assignment.returned_condition = return_data.get("returned_condition")
        assignment.return_notes = return_data.get("return_notes")
        assignment.status = "returned"

        # Update asset
        asset = db.query(Asset).filter(Asset.id == assignment.asset_id).first()
        if asset:
            asset.status = "available"
            asset.assigned_to_user_id = None
            if return_data.get("returned_condition"):
                asset.condition = return_data["returned_condition"]

        db.commit()
        db.refresh(assignment)
        return assignment


class CRUDAssetMaintenance:
    def get_by_id(self, db: Session, maint_id: int) -> Optional[AssetMaintenance]:
        return db.query(AssetMaintenance).filter(AssetMaintenance.id == maint_id).first()

    def get_for_asset(self, db: Session, asset_id: int) -> List[AssetMaintenance]:
        return db.query(AssetMaintenance).filter(AssetMaintenance.asset_id == asset_id).order_by(AssetMaintenance.scheduled_date.desc()).all()

    def get_for_org(self, db: Session, org_id: UUID, status: Optional[str] = None) -> List[AssetMaintenance]:
        q = db.query(AssetMaintenance).filter(AssetMaintenance.organization_id == org_id)
        if status:
            q = q.filter(AssetMaintenance.status == status)
        return q.order_by(AssetMaintenance.scheduled_date.desc()).all()

    def create(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> AssetMaintenance:
        maint = AssetMaintenance(organization_id=org_id, **obj_in)
        db.add(maint)

        # Update asset status
        asset = db.query(Asset).filter(Asset.id == obj_in["asset_id"]).first()
        if asset and asset.status not in ("disposed", "retired"):
            asset.status = "under_maintenance"

        db.commit()
        db.refresh(maint)
        return maint

    def complete(self, db: Session, maint: AssetMaintenance, obj_in: Dict[str, Any]) -> AssetMaintenance:
        maint.status = "completed"
        maint.completed_date = datetime.now(timezone.utc)
        for f, v in obj_in.items():
            if v is not None and hasattr(maint, f):
                setattr(maint, f, v)

        # Restore asset to available
        asset = db.query(Asset).filter(Asset.id == maint.asset_id).first()
        if asset and asset.status == "under_maintenance":
            if asset.assigned_to_user_id:
                asset.status = "assigned"
            else:
                asset.status = "available"

        db.commit()
        db.refresh(maint)
        return maint


class CRUDAssetDepreciation:
    def get_for_asset(self, db: Session, asset_id: int) -> List[AssetDepreciation]:
        return db.query(AssetDepreciation).filter(AssetDepreciation.asset_id == asset_id).order_by(AssetDepreciation.period_start.desc()).all()

    def create_entry(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> AssetDepreciation:
        dep = AssetDepreciation(organization_id=org_id, **obj_in)
        db.add(dep)

        # Update asset current value
        asset = db.query(Asset).filter(Asset.id == obj_in["asset_id"]).first()
        if asset:
            asset.current_value = obj_in["closing_value"]

        db.commit()
        db.refresh(dep)
        return dep


class CRUDAssetDisposal:
    def get_by_id(self, db: Session, disp_id: int) -> Optional[AssetDisposal]:
        return db.query(AssetDisposal).filter(AssetDisposal.id == disp_id).first()

    def get_for_org(self, db: Session, org_id: UUID) -> List[AssetDisposal]:
        return db.query(AssetDisposal).filter(AssetDisposal.organization_id == org_id).order_by(AssetDisposal.disposal_date.desc()).all()

    def create(self, db: Session, org_id: UUID, approved_by: Optional[int], obj_in: Dict[str, Any]) -> AssetDisposal:
        asset = db.query(Asset).filter(Asset.id == obj_in["asset_id"]).first()
        book_val = float(asset.current_value) if asset else 0.0
        disp_val = obj_in.get("disposal_value", 0.0)

        disp = AssetDisposal(
            organization_id=org_id,
            asset_id=obj_in["asset_id"],
            disposal_type=obj_in["disposal_type"],
            disposal_date=obj_in.get("disposal_date", datetime.now(timezone.utc)),
            disposal_value=disp_val,
            book_value_at_disposal=book_val,
            gain_loss=disp_val - book_val,
            approved_by_user_id=approved_by,
            reason=obj_in.get("reason", ""),
            notes=obj_in.get("notes")
        )
        db.add(disp)

        if asset:
            asset.status = "disposed"
            asset.is_active = False

        db.commit()
        db.refresh(disp)
        return disp


class CRUDAssetAudit:
    def get_by_id(self, db: Session, audit_id: int) -> Optional[AssetAudit]:
        return db.query(AssetAudit).filter(AssetAudit.id == audit_id).first()

    def get_for_org(self, db: Session, org_id: UUID) -> List[AssetAudit]:
        return db.query(AssetAudit).filter(AssetAudit.organization_id == org_id).order_by(AssetAudit.scheduled_date.desc()).all()

    def create(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> AssetAudit:
        audit = AssetAudit(
            organization_id=org_id,
            audit_code=obj_in["audit_code"],
            title=obj_in["title"],
            audit_type=obj_in.get("audit_type", "physical"),
            scheduled_date=obj_in.get("scheduled_date"),
            conducted_by_user_id=obj_in.get("conducted_by_user_id"),
            total_assets=obj_in.get("total_assets", 0),
            notes=obj_in.get("notes"),
            status="planned"
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit


class CRUDAssetAuditResult:
    def get_for_audit(self, db: Session, audit_id: int) -> List[AssetAuditResult]:
        return db.query(AssetAuditResult).filter(AssetAuditResult.audit_id == audit_id).all()

    def create_result(self, db: Session, obj_in: Dict[str, Any]) -> AssetAuditResult:
        result = AssetAuditResult(**obj_in)
        db.add(result)
        db.commit()
        db.refresh(result)
        return result


class CRUDAssetInsurance:
    def get_by_id(self, db: Session, ins_id: int) -> Optional[AssetInsurance]:
        return db.query(AssetInsurance).filter(AssetInsurance.id == ins_id).first()

    def get_for_asset(self, db: Session, asset_id: int) -> List[AssetInsurance]:
        return db.query(AssetInsurance).filter(AssetInsurance.asset_id == asset_id).order_by(AssetInsurance.start_date.desc()).all()

    def create(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> AssetInsurance:
        ins = AssetInsurance(organization_id=org_id, **obj_in)
        db.add(ins)
        db.commit()
        db.refresh(ins)
        return ins


class CRUDAssetLicense:
    def get_by_id(self, db: Session, lic_id: int) -> Optional[AssetLicense]:
        return db.query(AssetLicense).filter(AssetLicense.id == lic_id).first()

    def get_for_asset(self, db: Session, asset_id: int) -> List[AssetLicense]:
        return db.query(AssetLicense).filter(AssetLicense.asset_id == asset_id).all()

    def create(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> AssetLicense:
        lic = AssetLicense(organization_id=org_id, **obj_in)
        db.add(lic)
        db.commit()
        db.refresh(lic)
        return lic


class CRUDVendor:
    def get_by_id(self, db: Session, vendor_id: int) -> Optional[Vendor]:
        return db.query(Vendor).filter(Vendor.id == vendor_id).first()

    def get_all_for_org(self, db: Session, org_id: UUID) -> List[Vendor]:
        return db.query(Vendor).filter(Vendor.organization_id == org_id, Vendor.is_active.is_(True)).order_by(Vendor.vendor_name).all()

    def create(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> Vendor:
        vendor = Vendor(organization_id=org_id, **obj_in)
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        return vendor

    def update(self, db: Session, db_obj: Vendor, updates: Dict[str, Any]) -> Vendor:
        for f, v in updates.items():
            if v is not None and hasattr(db_obj, f):
                setattr(db_obj, f, v)
        db.commit()
        db.refresh(db_obj)
        return db_obj


class CRUDPurchaseOrder:
    def get_by_id(self, db: Session, po_id: int) -> Optional[PurchaseOrder]:
        return db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()

    def get_all_for_org(self, db: Session, org_id: UUID) -> List[PurchaseOrder]:
        return db.query(PurchaseOrder).filter(PurchaseOrder.organization_id == org_id).order_by(PurchaseOrder.created_at.desc()).all()

    def create(self, db: Session, org_id: UUID, created_by: int, obj_in: Dict[str, Any]) -> PurchaseOrder:
        po = PurchaseOrder(
            organization_id=org_id,
            po_number=obj_in["po_number"],
            vendor_id=obj_in["vendor_id"],
            order_date=obj_in.get("order_date", datetime.now(timezone.utc)),
            expected_delivery_date=obj_in.get("expected_delivery_date"),
            total_amount=obj_in.get("total_amount", 0.0),
            tax_amount=obj_in.get("tax_amount", 0.0),
            grand_total=obj_in.get("grand_total", 0.0),
            currency=obj_in.get("currency", "INR"),
            notes=obj_in.get("notes"),
            created_by_user_id=created_by,
            status="draft"
        )
        db.add(po)

        # Add items
        for item in obj_in.get("items", []):
            po_item = PurchaseOrderItem(
                purchase_order_id=po.id,
                item_name=item["item_name"],
                description=item.get("description"),
                quantity=item.get("quantity", 1),
                unit_price=item.get("unit_price", 0.0),
                total_price=item.get("quantity", 1) * item.get("unit_price", 0.0),
                category_id=item.get("category_id")
            )
            db.add(po_item)

        db.commit()
        db.refresh(po)
        return po

    def receive_items(self, db: Session, po: PurchaseOrder, items_data: List[Dict[str, Any]]) -> PurchaseOrder:
        for item_data in items_data:
            item = db.query(PurchaseOrderItem).filter(
                PurchaseOrderItem.id == item_data["item_id"],
                PurchaseOrderItem.purchase_order_id == po.id
            ).first()
            if item:
                item.received_quantity += item_data.get("quantity", 0)

        all_received = all(
            item.quantity <= item.received_quantity
            for item in po.items
        )
        po.status = "received" if all_received else "partially_received"
        if all_received:
            po.delivery_date = datetime.now(timezone.utc)

        db.commit()
        db.refresh(po)
        return po


class CRUDAssetConsumable:
    def get_by_id(self, db: Session, consumable_id: int) -> Optional[AssetConsumable]:
        return db.query(AssetConsumable).filter(AssetConsumable.id == consumable_id).first()

    def get_all_for_org(self, db: Session, org_id: UUID, low_stock: bool = False) -> List[AssetConsumable]:
        q = db.query(AssetConsumable).filter(AssetConsumable.organization_id == org_id, AssetConsumable.is_active.is_(True))
        if low_stock:
            q = q.filter(AssetConsumable.quantity_in_stock <= AssetConsumable.minimum_stock_level)
        return q.order_by(AssetConsumable.name).all()

    def create(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> AssetConsumable:
        c = AssetConsumable(organization_id=org_id, **obj_in)
        db.add(c)
        db.commit()
        db.refresh(c)
        return c

    def update_stock(self, db: Session, consumable: AssetConsumable, quantity_change: int) -> AssetConsumable:
        consumable.quantity_in_stock += quantity_change
        if consumable.quantity_in_stock < 0:
            consumable.quantity_in_stock = 0
        db.commit()
        db.refresh(consumable)
        return consumable


class CRUDConsumableIssuance:
    def get_by_id(self, db: Session, issuance_id: int) -> Optional[ConsumableIssuance]:
        return db.query(ConsumableIssuance).filter(ConsumableIssuance.id == issuance_id).first()

    def get_for_org(self, db: Session, org_id: UUID) -> List[ConsumableIssuance]:
        return db.query(ConsumableIssuance).filter(ConsumableIssuance.organization_id == org_id).order_by(ConsumableIssuance.issued_at.desc()).all()

    def issue(self, db: Session, org_id: UUID, issued_by: int, obj_in: Dict[str, Any]) -> ConsumableIssuance:
        issuance = ConsumableIssuance(
            organization_id=org_id,
            consumable_id=obj_in["consumable_id"],
            issued_to_user_id=obj_in["issued_to_user_id"],
            issued_by_user_id=issued_by,
            quantity=obj_in["quantity"],
            purpose=obj_in.get("purpose")
        )
        db.add(issuance)

        # Reduce stock
        consumable = db.query(AssetConsumable).filter(AssetConsumable.id == obj_in["consumable_id"]).first()
        if consumable:
            consumable.quantity_in_stock -= obj_in["quantity"]
            if consumable.quantity_in_stock < 0:
                consumable.quantity_in_stock = 0

        db.commit()
        db.refresh(issuance)
        return issuance


# Singleton instances
crud_asset_category = CRUDAssetCategory()
crud_asset = CRUDAsset()
crud_asset_assignment = CRUDAssetAssignment()
crud_asset_maintenance = CRUDAssetMaintenance()
crud_asset_depreciation = CRUDAssetDepreciation()
crud_asset_disposal = CRUDAssetDisposal()
crud_asset_audit = CRUDAssetAudit()
crud_asset_audit_result = CRUDAssetAuditResult()
crud_asset_insurance = CRUDAssetInsurance()
crud_asset_license = CRUDAssetLicense()
crud_vendor = CRUDVendor()
crud_purchase_order = CRUDPurchaseOrder()
crud_asset_consumable = CRUDAssetConsumable()
crud_consumable_issuance = CRUDConsumableIssuance()
