"""
Statutory deduction engine.

Replaces the flat `base * 0.10` TDS and `base * 0.12` PF placeholders that
previously drove every payslip. Those placeholders were applied to `base`
rather than to gross, ignored wage ceilings and slab structure, and produced
payslips that were not compliant with Indian statutory requirements.

Design notes:

* All money is `Decimal`; tax computation never touches binary floats.
* Rules are data, not code. Built-in defaults cover India; an organisation can
  override any component through a `StatutoryRule` row whose
  `parameter_json` carries a partial config, so a tenant never needs a
  deployment to change a rate.
* Income tax is computed annually from projected annual gross, then spread
  across the year with year-to-date awareness, because a slab-based annual
  liability cannot be derived correctly one month at a time.

Rates verified against the Indian Income Tax Act 2025 (in force 1 April 2026),
which carries the same slab structure as FY 2025-26.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, replace
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")

COUNTRY_INDIA = "IN"
REGIME_NEW = "new"
REGIME_OLD = "old"

# Rule codes an organisation may override.
RULE_INCOME_TAX = "INCOME_TAX"
RULE_EPF = "EPF"
RULE_ESI = "ESI"
RULE_PROFESSIONAL_TAX = "PROFESSIONAL_TAX"

# Statutory months in an Indian financial year.
FY_MONTHS = 12


def _dec(value: Any) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        logger.warning("Non-numeric statutory value %r coerced to 0", value)
        return ZERO


def _q(value: Decimal) -> Decimal:
    return _dec(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Slab:
    """A marginal rate band. `up_to` None means the top band."""
    up_to: Optional[Decimal]
    rate: Decimal


@dataclass(frozen=True)
class SurchargeBand:
    above: Decimal
    rate: Decimal


@dataclass(frozen=True)
class AmountBand:
    """
    A flat monetary amount payable once the band is reached.

    Used by professional tax, which is levied as a fixed rupee amount per
    state-defined band (e.g. "above 20,000 -> 200 per month") rather than as
    a percentage of wages.
    """
    up_to: Optional[Decimal]
    amount: Decimal


@dataclass(frozen=True)
class Regime:
    """An income-tax regime (the Indian default/new pair)."""
    code: str
    name: str
    standard_deduction: Decimal
    slabs: Tuple[Slab, ...]
    rebate_income_limit: Decimal
    rebate_max: Decimal
    cess_rate: Decimal
    surcharge: Tuple[SurchargeBand, ...]


# ── India defaults (Income Tax Act 2025, in force 1 April 2026) ─────────
# Slab structure is unchanged from FY 2025-26.
NEW_REGIME = Regime(
    code=REGIME_NEW,
    name="Default (new) regime",
    standard_deduction=Decimal("75000"),
    slabs=(
        Slab(Decimal("400000"), Decimal("0")),
        Slab(Decimal("800000"), Decimal("0.05")),
        Slab(Decimal("1200000"), Decimal("0.10")),
        Slab(Decimal("1600000"), Decimal("0.15")),
        Slab(Decimal("2000000"), Decimal("0.20")),
        Slab(Decimal("2400000"), Decimal("0.25")),
        Slab(None, Decimal("0.30")),
    ),
    # Full rebate below 12L taxable income.
    rebate_income_limit=Decimal("1200000"),
    rebate_max=Decimal("60000"),
    cess_rate=Decimal("0.04"),
    # Surcharge is capped at 25% under the new regime.
    surcharge=(
        SurchargeBand(Decimal("5000000"), Decimal("0.10")),
        SurchargeBand(Decimal("10000000"), Decimal("0.15")),
        SurchargeBand(Decimal("20000000"), Decimal("0.25")),
        SurchargeBand(Decimal("50000000"), Decimal("0.25")),
    ),
)

OLD_REGIME = Regime(
    code=REGIME_OLD,
    name="Old regime",
    standard_deduction=Decimal("50000"),
    slabs=(
        Slab(Decimal("250000"), Decimal("0")),
        Slab(Decimal("500000"), Decimal("0.05")),
        Slab(Decimal("1000000"), Decimal("0.20")),
        Slab(None, Decimal("0.30")),
    ),
    rebate_income_limit=Decimal("500000"),
    rebate_max=Decimal("12500"),
    cess_rate=Decimal("0.04"),
    surcharge=(
        SurchargeBand(Decimal("5000000"), Decimal("0.10")),
        SurchargeBand(Decimal("10000000"), Decimal("0.15")),
        SurchargeBand(Decimal("20000000"), Decimal("0.25")),
        SurchargeBand(Decimal("50000000"), Decimal("0.37")),
    ),
)

REGIMES: Dict[str, Regime] = {NEW_REGIME.code: NEW_REGIME, OLD_REGIME.code: OLD_REGIME}


@dataclass(frozen=True)
class StatutoryConfig:
    country: str = COUNTRY_INDIA
    currency: str = "INR"
    income_tax_enabled: bool = True
    regime: Regime = NEW_REGIME

    # Employees' Provident Fund
    epf_enabled: bool = True
    epf_employee_rate: Decimal = Decimal("0.12")
    epf_employer_rate: Decimal = Decimal("0.12")
    epf_wage_ceiling: Decimal = Decimal("15000")
    # Employee Pension Fund share, carved out of the employer's 12%.
    eps_rate: Decimal = Decimal("0.0415")

    # Employees' State Insurance
    esi_enabled: bool = True
    esi_employee_rate: Decimal = Decimal("0.0075")
    esi_employer_rate: Decimal = Decimal("0.0325")
    esi_wage_ceiling: Decimal = Decimal("21000")

    # Professional tax is levied by states on a state-specific slab table.
    professional_tax_enabled: bool = False
    professional_tax_slabs: Tuple[AmountBand, ...] = ()

    # How the PF base is derived when the caller only supplies components.
    epf_base_includes: Tuple[str, ...] = ("basic", "da")
    sources: Tuple[str, ...] = ()

DEFAULT_CONFIG = StatutoryConfig(regime=NEW_REGIME)


# ── Config resolution ───────────────────────────────────────────────────
def _parse_slabs(raw: Any) -> Optional[Tuple[Slab, ...]]:
    """Accept `[[up_to, rate], ...]` or `[{"up_to":..,"rate":..}]`."""
    if not raw:
        return None
    slabs: List[Slab] = []
    for item in raw:
        if isinstance(item, dict):
            up_to = item.get("up_to", item.get("upTo"))
            rate = item.get("rate", item.get("rate_percent", item.get("ratePercent")))
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            up_to, rate = item
        else:
            logger.warning("Ignoring malformed statutory slab entry %r", item)
            continue
        rate_dec = _dec(rate)
        # Accept either a fraction (0.05) or a percentage (5).
        if rate_dec > 1:
            rate_dec = rate_dec / Decimal("100")
        slabs.append(Slab(None if up_to in (None, "", "null") else _dec(up_to), rate_dec))
    return tuple(slabs) or None


def _parse_amount_bands(raw: Any) -> Optional[Tuple[AmountBand, ...]]:
    """Accept `[[up_to, amount], ...]` or `[{"up_to":..,"amount":..}]`."""
    if not raw:
        return None
    bands: List[AmountBand] = []
    for item in raw:
        if isinstance(item, dict):
            up_to = item.get("up_to", item.get("upTo"))
            amount = item.get("amount", item.get("value"))
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            up_to, amount = item
        else:
            logger.warning("Ignoring malformed professional tax band %r", item)
            continue
        bands.append(
            AmountBand(
                None if up_to in (None, "", "null") else _dec(up_to),
                _dec(amount),
            )
        )
    return tuple(bands) or None


def _parse_surcharge(raw: Any) -> Optional[Tuple[SurchargeBand, ...]]:
    if not raw:
        return None
    bands: List[SurchargeBand] = []
    for item in raw:
        if isinstance(item, dict):
            above = item.get("above", item.get("threshold"))
            rate = item.get("rate", item.get("rate_percent"))
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            above, rate = item
        else:
            continue
        rate_dec = _dec(rate)
        if rate_dec > 1:
            rate_dec = rate_dec / Decimal("100")
        bands.append(SurchargeBand(_dec(above), rate_dec))
    return tuple(bands) or None


def _apply_rule(config: StatutoryConfig, rule_code: str, params: Dict[str, Any]) -> StatutoryConfig:
    """Merge one tenant rule's parameters into the base config."""
    def flag(name: str, default: bool) -> bool:
        if name not in params:
            return default
        value = params[name]
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        return bool(value)

    def rate(name: str, default: Decimal) -> Decimal:
        if name not in params or params[name] is None:
            return default
        value = _dec(params[name])
        # Tolerate percentages expressed as 12 rather than 0.12.
        if value > 1:
            value = value / Decimal("100")
        return value

    if rule_code == RULE_INCOME_TAX:
        regime = config.regime
        regime_code = str(params.get("regime", regime.code)).strip().lower()
        if regime_code in REGIMES:
            regime = REGIMES[regime_code]
        slabs = _parse_slabs(params.get("slabs"))
        if slabs:
            regime = replace(regime, slabs=slabs)
        surcharge = _parse_surcharge(params.get("surcharge"))
        if surcharge:
            regime = replace(regime, surcharge=surcharge)
        for field_name in (
            "standard_deduction", "rebate_income_limit", "rebate_max", "cess_rate",
        ):
            if params.get(field_name) is not None:
                regime = replace(regime, **{field_name: _dec(params[field_name])})
        return replace(
            config,
            income_tax_enabled=flag("enabled", config.income_tax_enabled),
            regime=regime,
        )

    if rule_code == RULE_EPF:
        return replace(
            config,
            epf_enabled=flag("enabled", config.epf_enabled),
            epf_employee_rate=rate("employee_rate", config.epf_employee_rate),
            epf_employer_rate=rate("employer_rate", config.epf_employer_rate),
            epf_wage_ceiling=_dec(params.get("wage_ceiling", config.epf_wage_ceiling)),
            eps_rate=rate("eps_rate", config.eps_rate),
            epf_base_includes=tuple(
                params.get("base_includes", config.epf_base_includes)
            ),
        )

    if rule_code == RULE_ESI:
        return replace(
            config,
            esi_enabled=flag("enabled", config.esi_enabled),
            esi_employee_rate=rate("employee_rate", config.esi_employee_rate),
            esi_employer_rate=rate("employer_rate", config.esi_employer_rate),
            esi_wage_ceiling=_dec(params.get("wage_ceiling", config.esi_wage_ceiling)),
        )

    if rule_code == RULE_PROFESSIONAL_TAX:
        bands = _parse_amount_bands(params.get("bands") or params.get("slabs"))
        return replace(
            config,
            professional_tax_enabled=flag("enabled", config.professional_tax_enabled),
            professional_tax_slabs=bands or config.professional_tax_slabs,
        )

    logger.warning("Unknown statutory rule code %r ignored", rule_code)
    return config


def load_config(
    db: Optional[Session],
    org_id: Any = None,
    *,
    country: str = COUNTRY_INDIA,
    regime: Optional[str] = None,
) -> StatutoryConfig:
    """
    Resolve the statutory configuration for a tenant.

    Built-in India defaults, overlaid with any active `StatutoryRule` rows for
    the organisation. A malformed rule is skipped rather than allowed to break
    payroll, because a configuration error must not halt salary payment.
    """
    config = StatutoryConfig(country=country, regime=REGIMES.get(REGIME_NEW, NEW_REGIME))
    if regime and regime in REGIMES:
        config = replace(config, regime=REGIMES[regime])
    if country.upper() != COUNTRY_INDIA:
        # No other jurisdiction is modelled yet; statutory deductions must not
        # silently apply Indian rates outside India.
        logger.warning("No statutory rules modelled for country %r; disabling deductions", country)
        return replace(
            config,
            country=country,
            income_tax_enabled=False,
            epf_enabled=False,
            esi_enabled=False,
        )

    if db is None or org_id is None:
        return config

    try:
        from app.db.models.all_models import StatutoryRule

        rules = (
            db.query(StatutoryRule)
            .filter(
                StatutoryRule.organization_id == org_id,
                StatutoryRule.is_active.is_(True),
            )
            .all()
        )
    except Exception:
        logger.warning("Could not load statutory rules for org %s", org_id, exc_info=True)
        return config

    applied: List[str] = []
    for rule in rules:
        raw = getattr(rule, "parameter_json", None)
        if not raw:
            continue
        try:
            params = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except (TypeError, ValueError):
            logger.warning("Statutory rule %s has invalid JSON; ignored", rule.rule_code)
            continue
        if not isinstance(params, dict):
            continue
        config = _apply_rule(config, str(rule.rule_code).upper(), params)
        applied.append(str(rule.rule_code).upper())

    return replace(config, sources=tuple(applied))


def fy_month_index(month: int) -> int:
    """
    Zero-based position of a calendar month within the financial year.

    The Indian financial year runs April (position 0) to March (position 11).
    Using the raw calendar number would make March look like the third month
    of the year, spreading an annual tax liability over ten months instead of
    the one that remains.
    """
    if not 1 <= month <= 12:
        raise ValueError(f"month must be 1-12, got {month}")
    return (month - 4) % 12


# ── Component calculations ──────────────────────────────────────────────
def slab_tax(taxable_income: Decimal, slabs: Sequence[Slab]) -> Decimal:
    """Apply marginal bands progressively."""
    income = _dec(taxable_income)
    if income <= 0:
        return ZERO
    tax = ZERO
    lower = ZERO
    for slab in slabs:
        upper = slab.up_to
        if upper is None or income > upper:
            band = income - lower if upper is None else upper - lower
            if band > 0:
                tax += band * slab.rate
            lower = upper if upper is not None else lower
            if upper is None:
                break
        else:
            band = income - lower
            if band > 0:
                tax += band * slab.rate
            break
    return tax


def compute_epf(
    basic_plus_da: Decimal,
    config: StatutoryConfig,
) -> Dict[str, Decimal]:
    """
    Employees' Provident Fund.

    The wage ceiling means contributions stop at `epf_wage_ceiling` even for
    higher earners, and the employer's share is split with the Employee
    Pension Fund carved out of the employer's contribution, not added to it.
    """
    if not config.epf_enabled:
        return {"employee": ZERO, "employer": ZERO, "eps": ZERO, "edli": ZERO}

    base = min(_dec(basic_plus_da), _dec(config.epf_wage_ceiling))
    if base <= 0:
        return {"employee": ZERO, "employer": ZERO, "eps": ZERO, "edli": ZERO}

    employee = base * config.epf_employee_rate
    employer = base * config.epf_employer_rate
    eps = base * config.eps_rate
    edli = base * Decimal("0.005")
    return {
        "employee": _q(employee),
        "employer": _q(employer),
        "eps": _q(eps),
        "edli": _q(edli),
    }


def compute_esi(gross_monthly: Decimal, config: StatutoryConfig) -> Dict[str, Decimal]:
    """Employees' State Insurance. Not payable at all above the wage ceiling."""
    if not config.esi_enabled:
        return {"employee": ZERO, "employer": ZERO, "applicable": ZERO}

    gross = _dec(gross_monthly)
    if gross <= 0 or gross > _dec(config.esi_wage_ceiling):
        return {"employee": ZERO, "employer": ZERO, "applicable": ZERO}

    return {
        "employee": _q(gross * config.esi_employee_rate),
        "employer": _q(gross * config.esi_employer_rate),
        "applicable": Decimal("1"),
    }


def compute_professional_tax(
    gross_monthly: Decimal, config: StatutoryConfig
) -> Decimal:
    """
    State professional tax, charged on a state-specific band table.

    The band value is a flat rupee amount for the month, not a percentage, so
    it is resolved by finding the highest band the wages reach.
    """
    if not config.professional_tax_enabled or not config.professional_tax_slabs:
        return ZERO

    gross = _dec(gross_monthly)
    payable = ZERO
    for band in config.professional_tax_slabs:
        if band.up_to is None or gross <= band.up_to:
            payable = band.amount
            break
    return _q(payable)


def compute_annual_income_tax(
    gross_annual: Decimal,
    config: StatutoryConfig,
    *,
    deductions: Optional[Dict[str, Decimal]] = None,
) -> Dict[str, Decimal]:
    """
    Annual income tax on salary income.

    Returns the full breakdown so a payslip or a tax report can show how the
    liability was reached, rather than only the final number.
    """
    if not config.income_tax_enabled:
        return {
            "taxable_income": ZERO, "tax": ZERO, "cess": ZERO, "surcharge": ZERO,
            "rebate": ZERO, "total": ZERO,
        }

    regime = config.regime
    gross = _dec(gross_annual)
    deductions = deductions or {}

    taxable = gross - regime.standard_deduction
    # Old-regime deductions (80C, 80D, HRA, ...) are opt-in and capped.
    for key, cap in (
        ("section_80c", Decimal("150000")),
        ("section_80d", Decimal("25000")),
        ("other_deductions", None),
    ):
        amount = _dec(deductions.get(key))
        if amount <= 0:
            continue
        if cap is not None:
            amount = min(amount, cap)
        taxable -= amount

    if taxable < 0:
        taxable = ZERO

    tax = slab_tax(taxable, regime.slabs)

    # Section 87A / 156 rebate, with marginal relief.
    #
    # Below the limit the rebate wipes the tax out entirely. Just above it the
    # rebate must taper rather than vanish, otherwise a single rupee of extra
    # income triggers the full ~60,000 liability as a cliff. Relief continues
    # until the slab tax naturally exceeds the excess over the limit.
    rebate = ZERO
    if taxable <= regime.rebate_income_limit:
        rebate = min(tax, regime.rebate_max)
        tax = max(ZERO, tax - rebate)
    else:
        excess = taxable - regime.rebate_income_limit
        if tax > excess:
            rebate = tax - excess
            tax = excess

    # Surcharge, with marginal relief at the entry threshold so a salary just
    # above the limit is not surcharged on the whole amount.
    surcharge = ZERO
    bands = regime.surcharge
    for index, band in enumerate(bands):
        if taxable <= band.above:
            break
        surcharge = tax * band.rate
        if index == 0:
            # Marginal relief: the surcharge may not exceed the excess income.
            excess_over_threshold = taxable - band.above
            if surcharge > excess_over_threshold:
                surcharge = excess_over_threshold

    cess = (tax + surcharge) * regime.cess_rate
    total = tax + surcharge + cess

    return {
        "taxable_income": _q(taxable),
        "tax": _q(tax),
        "surcharge": _q(surcharge),
        "cess": _q(cess),
        "rebate": _q(rebate),
        "total": _q(total),
    }


def compute_monthly_tds(
    annual_tax: Decimal,
    *,
    months_paid: int = 0,
    tax_deducted_ytd: Decimal = ZERO,
    months_in_year: int = FY_MONTHS,
) -> Decimal:
    """
    Withhold TDS for the current month.

    Spread as an equal share of the annual liability, then trued up against
    what has already been deducted so the year totals the correct liability
    rather than 12x an early-month guess.
    """
    annual = _dec(annual_tax)
    if annual <= 0:
        return ZERO

    remaining_months = max(1, months_in_year - months_paid)
    due = annual - _dec(tax_deducted_ytd)
    monthly = due / Decimal(remaining_months)
    return _q(monthly if monthly > 0 else ZERO)


# ── Combined entry point ────────────────────────────────────────────────
@dataclass
class StatutoryResult:
    pf_employee: Decimal = ZERO
    pf_employer: Decimal = ZERO
    pf_eps: Decimal = ZERO
    pf_edli: Decimal = ZERO
    esi_employee: Decimal = ZERO
    esi_employer: Decimal = ZERO
    professional_tax: Decimal = ZERO
    tds: Decimal = ZERO
    annual_tax: Decimal = ZERO
    taxable_income: Decimal = ZERO
    total_employee_deduction: Decimal = ZERO
    total_employer_contribution: Decimal = ZERO
    breakdown: Dict[str, Decimal] = field(default_factory=dict)


def compute_statutory(
    *,
    gross_monthly: Decimal,
    basic_monthly: Decimal = ZERO,
    da_monthly: Decimal = ZERO,
    config: StatutoryConfig,
    months_paid: int = 0,
    tax_deducted_ytd: Decimal = ZERO,
    deductions: Optional[Dict[str, Decimal]] = None,
) -> StatutoryResult:
    """
    Compute every statutory item for one month of salary.

    TDS is derived from the *annual* projection of this month's gross, so the
    slab structure is respected instead of applying a flat percentage.
    """
    gross = _dec(gross_monthly)
    basic = _dec(basic_monthly)
    da = _dec(da_monthly)

    epf = compute_epf(basic + da, config)
    esi = compute_esi(gross, config)
    pt = compute_professional_tax(gross, config)

    annual = compute_annual_income_tax(
        gross * FY_MONTHS, config, deductions=deductions
    )
    tds = compute_monthly_tds(
        annual["total"], months_paid=months_paid, tax_deducted_ytd=tax_deducted_ytd
    )

    # An employer cannot withhold more tax than the salary being paid.
    #
    # This matters when a month is processed without the prior months' payroll
    # rows — e.g. a back-dated run, a re-run after payroll records were
    # removed, or the first run of a financial year. The true-up would then
    # land the entire annual liability in a single month and drive net pay
    # negative. The excess liability is not lost: it is picked up in the
    # following month's true-up.
    #
    # Provident fund, ESI and professional tax are withheld by law and are not
    # capped here, so the cap is what remains of the salary after them. If they
    # alone exceed the salary, the input is internally inconsistent.
    mandatory = epf["employee"] + esi["employee"] + pt
    headroom = gross - mandatory
    if tds > headroom:
        if headroom < 0:
            logger.warning(
                "Statutory contributions (%s) exceed gross salary (%s) for a "
                "month; salary structure appears inconsistent",
                mandatory, gross,
            )
        logger.info(
            "Capping TDS at the salary headroom for the month (tds=%s "
            "headroom=%s); balance carries to a later month",
            tds, headroom,
        )
        tds = headroom if headroom > 0 else ZERO

    employee_total = epf["employee"] + esi["employee"] + pt + tds
    employer_total = epf["employer"] + esi["employer"]

    return StatutoryResult(
        pf_employee=epf["employee"],
        pf_employer=epf["employer"],
        pf_eps=epf["eps"],
        pf_edli=epf["edli"],
        esi_employee=esi["employee"],
        esi_employer=esi["employer"],
        professional_tax=pt,
        tds=tds,
        annual_tax=annual["total"],
        taxable_income=annual["taxable_income"],
        total_employee_deduction=_q(employee_total),
        total_employer_contribution=_q(employer_total),
        breakdown=annual,
    )
