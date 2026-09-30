"""
Leave policy — the organization-level rules the leave ledger is run against.

`LeavePolicy` was created with the right shape (`accrual_type`,
`allow_negative_balance`, `auto_approve_after_days`, `policy_config`) and then
never used: it was imported in the service and never read. So every tenant
silently behaved as though the same rules applied everywhere.

The defaults here are deliberately permissive, because applying a restrictive
default to existing tenants on deployment would start rejecting leave that
previously worked. An organization opts in by saving its own policy.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.all_models import LeavePolicy, LeaveType

# How an entitlement is granted across the policy year.
ACCRUAL_TYPES = ("annual_grant", "monthly_accrual", "per_payroll", "unlimited")

# The policy every organization gets until it saves one of its own.
DEFAULT_POLICY: Dict[str, Any] = {
    "name": "Default",
    "accrual_type": "annual_grant",
    "allow_negative_balance": True,
    "auto_approve_after_days": None,
    "policy_config": {},
}

# Keys accepted inside `policy_config`, with their defaults. Anything else is
# rejected rather than stored, so a typo cannot silently disable a rule.
CONFIG_DEFAULTS: Dict[str, Any] = {
    # An employee must have started before this date in the policy year to earn.
    "probation_days": 0,
    # Rounding granularity when computing day fractions.
    "day_rounding": 0.5,
    # Whether carry-forward from the prior year is applied at year rollover.
    "apply_carry_forward": True,
    # Whether a request may span non-working days without splitting.
    "allow_half_day": True,
    # Whether a request may exceed the per-request cap (the per-year cap is
    # always enforced).
    "allow_exceeding_per_request": False,
}


def get_policy(db: Session, org_id: UUID, year: Optional[int] = None) -> Dict[str, Any]:
    """The organization's effective policy for a year, falling back to defaults.

    A policy row is scoped to a `policy_year`, so a year without an explicit row
    must not inherit one from a different year: entitlements granted last year
    are not this year's rules.
    """
    year = year if year is not None else date.today().year
    row = (
        db.query(LeavePolicy)
        .filter(
            LeavePolicy.organization_id == org_id,
            LeavePolicy.policy_year == year,
            LeavePolicy.is_active.is_(True),
        )
        .order_by(LeavePolicy.id.desc())
        .first()
    )
    if row is None:
        return {**DEFAULT_POLICY, "policy_year": year, "is_default": True, "config": dict(CONFIG_DEFAULTS)}

    config = dict(CONFIG_DEFAULTS)
    stored = row.policy_config or {}
    if isinstance(stored, dict):
        for key in CONFIG_DEFAULTS:
            if key in stored:
                config[key] = stored[key]

    return {
        "name": row.name,
        "policy_year": row.policy_year,
        "accrual_type": row.accrual_type or DEFAULT_POLICY["accrual_type"],
        "allow_negative_balance": bool(row.allow_negative_balance),
        "auto_approve_after_days": row.auto_approve_after_days,
        "is_default": False,
        "config": config,
    }


def save_policy(
    db: Session,
    org_id: UUID,
    year: Optional[int] = None,
    name: Optional[str] = None,
    accrual_type: Optional[str] = None,
    allow_negative_balance: Optional[bool] = None,
    auto_approve_after_days: Optional[int] = None,
    policy_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    year = year if year is not None else date.today().year
    current = get_policy(db, org_id, year)

    if accrual_type is not None and accrual_type not in ACCRUAL_TYPES:
        raise ValueError(
            f"Unknown accrual_type {accrual_type!r}; expected one of {', '.join(ACCRUAL_TYPES)}"
        )

    config = dict(current["config"])
    if policy_config:
        unknown = set(policy_config) - set(CONFIG_DEFAULTS)
        if unknown:
            raise ValueError(f"Unknown policy_config keys: {', '.join(sorted(unknown))}")
        config.update(policy_config)

    row = (
        db.query(LeavePolicy)
        .filter(LeavePolicy.organization_id == org_id, LeavePolicy.policy_year == year)
        .order_by(LeavePolicy.id.desc())
        .first()
    )
    if row is None:
        row = LeavePolicy(organization_id=org_id, policy_year=year)
        db.add(row)

    row.name = name or current.get("name") or "Organization policy"
    row.accrual_type = accrual_type or current["accrual_type"]
    row.allow_negative_balance = (
        current["allow_negative_balance"]
        if allow_negative_balance is None
        else bool(allow_negative_balance)
    )
    row.auto_approve_after_days = (
        auto_approve_after_days
        if auto_approve_after_days is not None
        else current.get("auto_approve_after_days")
    )
    row.policy_config = config
    row.is_active = True
    db.commit()
    return get_policy(db, org_id, year)


def entitlement_for(leave_type: LeaveType, policy: Dict[str, Any], month: Optional[int] = None) -> float:
    """Days an employee earns for a type under this policy, for this point in time.

    `annual_grant` awards the whole year's entitlement up front, which is how
    the ledger behaved before policy existed. The accruing types award a
    fraction of the year that has elapsed, so a mid-year joiner or a monthly
    payroll cannot take the full year immediately.
    """
    per_year = float(leave_type.max_days_per_year or 0.0)
    accrual = policy.get("accrual_type", "annual_grant")

    if accrual == "unlimited":
        return per_year
    if accrual == "annual_grant":
        return per_year
    if accrual == "per_payroll":
        return per_year
    if accrual == "monthly_accrual":
        elapsed = 12 if month is None else max(0, min(12, month))
        return round(per_year * elapsed / 12.0, 2)
    return per_year


def evaluate_request(
    db: Session,
    org_id: UUID,
    user_id: int,
    leave_type: LeaveType,
    requested_days: float,
    available_days: float,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """Decide whether a leave request is permitted, and whether it auto-approves.

    Returns a structured verdict rather than a bare boolean so the caller can
    tell a policy refusal (400, with a reason the employee can act on) apart
    from a cap breach.
    """
    policy = get_policy(db, org_id, year)
    reasons: list[str] = []
    days = float(requested_days or 0.0)

    if days <= 0:
        return {
            "allowed": False, "auto_approve": False,
            "reasons": ["A leave request must cover at least one day."],
            "policy": policy,
        }

    per_year = float(leave_type.max_days_per_year or 0.0)
    per_request = leave_type.max_days_per_request
    unlimited = policy.get("accrual_type") == "unlimited"

    if not unlimited and per_year and days > per_year:
        reasons.append(
            f"{leave_type.name} allows {per_year:g} days per year; {days:g} were requested."
        )

    # A NULL per-request cap means unrestricted. The previous hardcoded check
    # compared against it unconditionally, which would have raised a TypeError
    # for any type created without that limit.
    if (
        per_request is not None
        and days > float(per_request)
        and not policy["config"].get("allow_exceeding_per_request", False)
    ):
        reasons.append(
            f"{leave_type.name} allows at most {float(per_request):g} days in a single request; {days:g} were requested."
        )

    if not policy["allow_negative_balance"] and not unlimited:
        if days > available_days:
            reasons.append(
                f"Insufficient {leave_type.name} balance: {days:g} requested, {available_days:g} available. "
                "This policy does not permit a negative balance."
            )

    min_notice = int(leave_type.min_notice_days or 0)
    threshold = policy.get("auto_approve_after_days")
    auto_approve = False
    if not reasons and threshold is not None and days <= float(threshold):
        auto_approve = True

    return {
        "allowed": not reasons,
        "auto_approve": auto_approve,
        "reasons": reasons,
        "policy": policy,
        "min_notice_days": min_notice,
    }
