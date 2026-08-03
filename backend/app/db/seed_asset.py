"""
seed_asset.py — Asset & Device Management System Seeder
Sprint 5 — Entity 1
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.models.all_models import (
    AssetCategory, Asset, Vendor, AssetConsumable, AssetLicense,
    AssetAssignment, User
)

logger = logging.getLogger(__name__)


def seed_asset_defaults_for_org(db: Session, org_id: UUID, user_id: int) -> dict:
    """Seed default asset categories and vendors for an organization."""
    results = {"categories_created": 0, "vendors_created": 0}

    # Default categories
    default_categories = [
        {"name": "Laptop", "code": "LAP", "description": "Laptop computers", "asset_type": "it_equipment"},
        {"name": "Desktop", "code": "DESK", "description": "Desktop computers", "asset_type": "it_equipment"},
        {"name": "Mobile Phone", "code": "MOB", "description": "Mobile phones and smartphones", "asset_type": "it_equipment"},
        {"name": "Tablet", "code": "TAB", "description": "Tablet devices", "asset_type": "it_equipment"},
        {"name": "Printer", "code": "PRN", "description": "Printers and scanners", "asset_type": "office_equipment"},
        {"name": "Monitor", "code": "MON", "description": "Computer monitors", "asset_type": "it_equipment"},
        {"name": "Server", "code": "SRV", "description": "Server hardware", "asset_type": "it_equipment"},
        {"name": "Networking", "code": "NET", "description": "Network equipment (routers, switches)", "asset_type": "it_equipment"},
        {"name": "Furniture", "code": "FUR", "description": "Office furniture", "asset_type": "furniture"},
        {"name": "Vehicle", "code": "VEH", "description": "Company vehicles", "asset_type": "vehicle"},
        {"name": "Software License", "code": "SWL", "description": "Software licenses", "asset_type": "software_license"},
        {"name": "Cloud Subscription", "code": "CLD", "description": "Cloud service subscriptions", "asset_type": "digital_asset"},
        {"name": "Biometric Device", "code": "BIO", "description": "Biometric attendance devices", "asset_type": "device"},
        {"name": "Camera", "code": "CAM", "description": "Face recognition cameras", "asset_type": "device"},
        {"name": "Accessories", "code": "ACC", "description": "Computer accessories", "asset_type": "consumable"},
    ]

    for cat in default_categories:
        existing = db.query(AssetCategory).filter(
            AssetCategory.organization_id == org_id,
            AssetCategory.code == cat["code"]
        ).first()
        if not existing:
            new_cat = AssetCategory(
                organization_id=org_id,
                name=cat["name"],
                code=cat["code"],
                description=cat["description"],
                is_active=True
            )
            db.add(new_cat)
            results["categories_created"] += 1

    # Default vendors
    default_vendors = [
        {"vendor_name": "Dell Technologies", "contact_person": "Sales Team", "email": "sales@dell.com"},
        {"vendor_name": "HP India", "contact_person": "Partner Support", "email": "support@hp.com"},
        {"vendor_name": "Lenovo Group", "contact_person": "Account Manager", "email": "sales@lenovo.com"},
        {"vendor_name": "Amazon Business", "contact_person": "Business Support", "email": "biz@amazon.com"},
        {"vendor_name": "Cisco Systems", "contact_person": "Channel Partner", "email": "partner@cisco.com"},
    ]

    for v in default_vendors:
        existing = db.query(Vendor).filter(
            Vendor.organization_id == org_id,
            Vendor.vendor_name == v["vendor_name"]
        ).first()
        if not existing:
            vendor = Vendor(organization_id=org_id, **v, is_active=True)
            db.add(vendor)
            results["vendors_created"] += 1

    db.commit()
    logger.info(f"Seeded {results} for org {org_id}")
    return results
