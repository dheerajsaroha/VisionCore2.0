"""
public.py — Unauthenticated, read-only endpoints for public marketing surfaces.

Only non-sensitive catalog data is exposed here: plan names, prices, trial
lengths, feature codes and licensing limits. No tenant data, no subscription
records, no billing history.

The plan list is restricted to ``settings.PUBLIC_PLAN_CODES`` rather than
filtered on ``is_system``: every seeded plan row carries ``is_system=true``
(including ``test_plan_*`` leftovers), so ``is_system`` does not identify the
real catalog and would leak test fixtures onto a public page.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.subscription_service import subscription_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["public"])


@router.get("/plans")
def list_public_plans(db: Session = Depends(get_db)) -> dict:
    """Public plan catalog for the pricing page.

    Returns an empty ``plans`` list rather than an error when the catalog has not
    been seeded, so a fresh install renders no pricing claims instead of failing.
    """
    plans = subscription_service.get_public_plans(db)
    return {
        "plans": plans,
        "count": len(plans),
        "currency": plans[0]["currency"] if plans else "USD",
    }
