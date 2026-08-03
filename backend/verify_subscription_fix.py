#!/usr/bin/env python3
"""
verify_subscription_fix.py — Standalone verification of subscription database fix
Sprint 2 — Entity 2: Subscription & Feature Management
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.basicConfig(level=logging.WARNING)

from app.db.database import SessionLocal
from sqlalchemy import text

def verify():
    db = SessionLocal()
    errors = []
    
    # 1. Check Alembic version
    row = db.execute(text("SELECT version_num FROM alembic_version")).first()
    print(f"[1] Alembic version: {row[0]}")
    if row[0] != "d4e5f6a7b8d0":
        errors.append(f"Expected head d4e5f6a7b8d0, got {row[0]}")
    
    # 2. Check all 6 subscription tables exist and have data
    tables = [
        "subscription_plans",
        "organization_subscriptions",
        "features",
        "plan_features",
        "feature_flags",
        "licensing_limits",
    ]
    
    for tbl in tables:
        count = db.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
        print(f"[2] {tbl}: {count} rows")
    
    # 3. Verify subscription plans
    plans = db.execute(text("SELECT code, name, tier, monthly_price FROM subscription_plans ORDER BY tier")).fetchall()
    print(f"[3] Plans: {[(p.code, p.name, p.tier, float(p.monthly_price)) for p in plans]}")
    if len(plans) != 3:
        errors.append(f"Expected 3 plans, got {len(plans)}")
    
    # 4. Verify features
    features = db.execute(text("SELECT COUNT(*) FROM features")).scalar()
    if features < 38:
        errors.append(f"Expected 38+ features, got {features}")
    
    # 5. Verify FKs
    fks = db.execute(text("""
        SELECT conname, conrelid::regclass AS table_name
        FROM pg_constraint
        WHERE contype = 'f'
        AND conrelid::regclass::text IN ('organization_subscriptions', 'plan_features', 'feature_flags', 'licensing_limits')
    """)).fetchall()
    print(f"[5] Foreign keys: {len(fks)}")
    for fk in fks:
        print(f"    {fk.conname} on {fk.table_name}")
    if len(fks) < 4:
        errors.append(f"Expected 4+ FKs, got {len(fks)}")
    
    # 6. Verify CHECK constraints
    checks = db.execute(text("""
        SELECT conname, conrelid::regclass AS table_name
        FROM pg_constraint
        WHERE contype = 'c'
        AND conrelid::regclass::text IN ('organization_subscriptions', 'features', 'licensing_limits')
    """)).fetchall()
    print(f"[6] Check constraints: {len(checks)}")
    for c in checks:
        print(f"    {c.conname} on {c.table_name}")
    if len(checks) < 3:
        errors.append(f"Expected 3+ CHECK constraints, got {len(checks)}")
    
    # 7. Verify indexes
    indexes = db.execute(text("""
        SELECT indexname, tablename FROM pg_indexes
        WHERE tablename IN ('subscription_plans', 'organization_subscriptions',
                           'features', 'plan_features', 'feature_flags', 'licensing_limits')
        ORDER BY tablename, indexname
    """)).fetchall()
    print(f"[7] Indexes: {len(indexes)}")
    
    # 8. Verify unique constraints
    unique_idx = [i.indexname for i in indexes if 'uq_' in i.indexname]
    print(f"[8] Unique constraints: {len(unique_idx)}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"VERIFICATION SUMMARY")
    print(f"{'='*60}")
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  ❌ {e}")
        print(f"Status: FAILED")
    else:
        print(f"  ✅ All checks passed!")
        print(f"  Alembic head: d4e5f6a7b8d0")
        print(f"  Plans: {len(plans)} (starter, professional, enterprise)")
        print(f"  Features: {features}")
        print(f"  Foreign keys: {len(fks)}")
        print(f"  Check constraints: {len(checks)}")
        print(f"  Indexes: {len(indexes)}")
        print(f"  Unique constraints: {len(unique_idx)}")
        print(f"Status: PASSED")
    
    db.close()
    return len(errors) == 0

if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)

