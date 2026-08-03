
# Subscription Database Schema Fix — TODO

## Root Cause
`app/db/models/__init__.py` defines its own `Base(DeclarativeBase)` with models that do NOT include subscription tables. `app/util/init.py` imports `Base` from `app.db.models` (the `__init__.py`), so `Base.metadata.create_all()` never creates the 6 subscription tables.

## Steps

- [x] Step 1: Fix `app/db/models/__init__.py` — Re-export from `all_models.py` and `base.py`
- [x] Step 2: Fix `app/util/init.py` — Import `Base` from `app.db.models.base`
- [x] Step 3: Run `alembic upgrade head`
- [x] Step 4: Verify 6 subscription tables exist
- [x] Step 5: Run seeder — 3 plans, 38 features, 75 mappings, 60 limits, 31 org subscriptions
- [x] Step 6: Database verification — all FKs, indexes, constraints present
- [x] Step 7: Generate delivery report — saved to `subscription_fix_report.md`

