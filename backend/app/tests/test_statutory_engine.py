"""
Tests for the statutory deduction engine.

These pin the statutory behaviour that replaced flat `base * 0.10` TDS and
`base * 0.12` PF placeholders. Figures are checked against hand-computed
values under the Indian default (new) regime and Income Tax Act 2025 rates,
which are in force from 1 April 2026.
"""
import dataclasses
import json
import uuid
from decimal import Decimal

import pytest

from app.db.database import SessionLocal
from app.db.models.all_models import Organization, StatutoryRule
from app.services.statutory_engine import (
    NEW_REGIME,
    OLD_REGIME,
    RULE_EPF,
    RULE_ESI,
    RULE_INCOME_TAX,
    RULE_PROFESSIONAL_TAX,
    REGIMES,
    StatutoryConfig,
    compute_annual_income_tax,
    compute_epf,
    compute_esi,
    compute_monthly_tds,
    compute_professional_tax,
    compute_statutory,
    fy_month_index,
    load_config,
    slab_tax,
)

D = Decimal


def config(**overrides):
    """Build a config with overrides. StatutoryConfig is frozen, so use replace."""
    return dataclasses.replace(StatutoryConfig(regime=NEW_REGIME), **overrides)


# ── Slab mechanics ──────────────────────────────────────────────────────
class TestSlabTax:
    def test_income_below_first_band_is_untaxed(self):
        assert slab_tax(D("300000"), NEW_REGIME.slabs) == D("0")

    def test_single_band_amount(self):
        # 4L-8L band at 5% on the 1.25L above 4L
        assert slab_tax(D("525000"), NEW_REGIME.slabs) == D("6250.00")

    def test_multiple_bands_accumulate(self):
        # 14.25L: 20k (4-8L) + 40k (8-12L) + 33.75k (12-14.25L @15%)
        assert slab_tax(D("1425000"), NEW_REGIME.slabs) == D("93750.00")

    def test_top_open_ended_band(self):
        # 59.25L crosses every band including the 30% open-ended top band.
        assert slab_tax(D("5925000"), NEW_REGIME.slabs) == D("1357500.00")

    def test_zero_and_negative_income(self):
        assert slab_tax(D("0"), NEW_REGIME.slabs) == D("0")
        assert slab_tax(D("-5000"), NEW_REGIME.slabs) == D("0")

    def test_old_regime_slabs_differ(self):
        # Old regime: 0-2.5L nil, 2.5-5L @5% = 12,500, 5-6L @20% = 20,000
        assert slab_tax(D("600000"), OLD_REGIME.slabs) == D("32500.00")


# ── Income tax ──────────────────────────────────────────────────────────
class TestAnnualIncomeTax:
    def test_salaried_up_to_12_75L_pays_nothing(self):
        # 12.75L gross - 75k standard deduction = 12L taxable = rebate limit.
        result = compute_annual_income_tax(D("1275000"), config())
        assert result["taxable_income"] == D("1200000.00")
        assert result["total"] == D("0.00")

    def test_taxable_just_below_rebate_limit(self):
        assert compute_annual_income_tax(D("1274999"), config())["total"] == D("0.00")

    def test_marginal_relief_removes_the_cliff(self):
        """One rupee above the limit must not trigger the full ~60,000 tax."""
        at_limit = compute_annual_income_tax(D("1275000"), config())
        above = compute_annual_income_tax(D("1275001"), config())
        assert at_limit["total"] == D("0.00")
        # Relief caps the tax at the excess income over the limit.
        assert above["tax"] <= D("1.00")

    def test_relief_tapers_monotonically(self):
        totals = [
            compute_annual_income_tax(D(str(g)), config())["total"]
            for g in (1275000, 1300000, 1350000, 1400000, 1500000, 2000000, 2500000)
        ]
        assert totals == sorted(totals), f"tax must not decrease as income rises: {totals}"

    def test_high_earner_total_includes_cess_and_surcharge(self):
        result = compute_annual_income_tax(D("6000000"), config())
        # Slab 1,357,500 + 10% surcharge 135,750 + 4% cess 59,730
        assert result["tax"] == D("1357500.00")
        assert result["surcharge"] == D("135750.00")
        assert result["cess"] == D("59730.00")
        assert result["total"] == D("1552980.00")

    def test_cess_is_four_percent_of_tax_plus_surcharge(self):
        result = compute_annual_income_tax(D("6000000"), config())
        expected = (result["tax"] + result["surcharge"]) * D("0.04")
        assert result["cess"] == expected.quantize(D("0.01"))

    def test_surcharge_marginal_relief_at_threshold(self):
        # Just above 50L taxable, surcharge may not exceed the excess.
        result = compute_annual_income_tax(D("5075000"), config())
        taxable = result["taxable_income"]
        assert result["surcharge"] <= taxable - D("5000000")

    def test_income_tax_can_be_disabled(self):
        result = compute_annual_income_tax(D("6000000"), config(income_tax_enabled=False))
        assert result["total"] == D("0.00")

    def test_old_regime_applies_larger_standard_deduction_allowance(self):
        old = compute_annual_income_tax(D("1500000"), config(regime=OLD_REGIME))
        new = compute_annual_income_tax(D("1500000"), config())
        # Old regime standard deduction is 50k, so it taxes more here.
        assert old["taxable_income"] == D("1450000.00")
        assert old["total"] > new["total"]

    def test_80c_deduction_reduces_taxable_income(self):
        without = compute_annual_income_tax(D("4000000"), config())
        with_deduction = compute_annual_income_tax(
            D("4000000"), config(), deductions={"section_80c": D("150000")}
        )
        assert with_deduction["taxable_income"] == without["taxable_income"] - D("150000")
        assert with_deduction["total"] < without["total"]

    def test_80c_deduction_is_capped(self):
        result = compute_annual_income_tax(
            D("4000000"), config(), deductions={"section_80c": D("999999")}
        )
        assert result["taxable_income"] == (
            D("4000000") - NEW_REGIME.standard_deduction - D("150000")
        )


# ── Provident fund ──────────────────────────────────────────────────────
class TestEpf:
    def test_wage_ceiling_caps_the_contribution(self):
        result = compute_epf(D("50000"), config())
        assert result["employee"] == D("1800.00")   # 15,000 * 12%
        assert result["employer"] == D("1800.00")

    def test_contribution_below_ceiling_uses_actual_wages(self):
        result = compute_epf(D("10000"), config())
        assert result["employee"] == D("1200.00")   # 10,000 * 12%

    def test_eps_is_carved_out_of_employer_share(self):
        result = compute_epf(D("50000"), config())
        assert result["eps"] == D("622.50")         # 15,000 * 4.15%
        assert result["eps"] <= result["employer"]

    def test_zero_and_negative_wages(self):
        assert compute_epf(D("0"), config())["employee"] == D("0.00")
        assert compute_epf(D("-5000"), config())["employee"] == D("0.00")

    def test_can_be_disabled(self):
        assert compute_epf(D("50000"), config(epf_enabled=False))["employee"] == D("0.00")

    def test_custom_rate_is_honoured(self):
        result = compute_epf(D("50000"), config(epf_employee_rate=D("0.10")))
        assert result["employee"] == D("1500.00")


# ── ESI ─────────────────────────────────────────────────────────────────
class TestEsi:
    def test_applies_below_ceiling(self):
        result = compute_esi(D("15000"), config())
        assert result["employee"] == D("112.50")   # 0.75%
        assert result["employer"] == D("487.50")    # 3.25%
        assert result["applicable"] == D("1")

    def test_does_not_apply_above_ceiling(self):
        result = compute_esi(D("25000"), config())
        assert result["employee"] == D("0")
        assert result["applicable"] == D("0")

    def test_exactly_at_ceiling_still_applies(self):
        assert compute_esi(D("21000"), config())["applicable"] == D("1")

    def test_can_be_disabled(self):
        assert compute_esi(D("15000"), config(esi_enabled=False))["employee"] == D("0")


# ── Professional tax ────────────────────────────────────────────────────
class TestProfessionalTax:
    def test_disabled_by_default(self):
        assert compute_professional_tax(D("50000"), config()) == D("0")

    def test_applies_state_bands_when_configured(self):
        """Professional tax is a flat rupee amount, not a percentage of wages."""
        from app.services.statutory_engine import AmountBand

        cfg = config(
            professional_tax_enabled=True,
            professional_tax_slabs=(
                AmountBand(D("20000"), D("0")),
                AmountBand(None, D("200")),
            ),
        )
        assert compute_professional_tax(D("15000"), cfg) == D("0.00")
        assert compute_professional_tax(D("25000"), cfg) == D("200.00")
        # A flat amount must not scale with wages.
        assert compute_professional_tax(D("500000"), cfg) == D("200.00")


# ── Monthly TDS ─────────────────────────────────────────────────────────
class TestMonthlyTds:
    def test_even_split_across_the_year(self):
        assert compute_monthly_tds(D("120000")) == D("10000.00")

    def test_trued_up_against_year_to_date(self):
        # 60k of a 120k liability already taken over 6 months leaves 60k.
        assert compute_monthly_tds(
            D("120000"), months_paid=6, tax_deducted_ytd=D("60000")
        ) == D("10000.00")

    def test_reduces_when_more_tax_was_already_taken(self):
        # 60k already taken of a 120k liability leaves 60k over 6 months,
        # which is below the naive even split of 10,000.
        assert compute_monthly_tds(
            D("120000"), months_paid=6, tax_deducted_ytd=D("70000")
        ) == D("8333.33")

    def test_last_month_absorbs_the_remaining_liability(self):
        assert compute_monthly_tds(
            D("120000"), months_paid=11, tax_deducted_ytd=D("110000")
        ) == D("10000.00")

    def test_no_liability_means_no_withholding(self):
        assert compute_monthly_tds(D("0")) == D("0.00")

    def test_never_deducts_a_negative_amount(self):
        assert compute_monthly_tds(
            D("1000"), months_paid=11, tax_deducted_ytd=D("5000")
        ) == D("0.00")


class TestFinancialYearPosition:
    def test_financial_year_starts_in_april(self):
        assert fy_month_index(4) == 0

    def test_march_is_the_last_month_of_the_year(self):
        assert fy_month_index(3) == 11

    def test_calendar_month_numbers_are_not_used(self):
        # A raw calendar index would place March third and spread an annual
        # liability over ten months instead of the one remaining.
        assert fy_month_index(3) == 11 != 2
        assert fy_month_index(1) == 9 != 0

    def test_all_twelve_months_map_to_distinct_positions(self):
        positions = [fy_month_index(m) for m in range(1, 13)]
        assert sorted(positions) == list(range(12))

    def test_rejects_invalid_month(self):
        for bad in (0, 13, -1):
            with pytest.raises(ValueError):
                fy_month_index(bad)

    def test_tds_spreads_to_exactly_the_annual_liability(self):
        annual = D("292500")
        deducted_ytd = D("0.00")
        for month in range(4, 13):
            deducted_ytd += compute_monthly_tds(
                annual, months_paid=fy_month_index(month), tax_deducted_ytd=deducted_ytd
            )
        for month in (1, 2, 3):
            deducted_ytd += compute_monthly_tds(
                annual, months_paid=fy_month_index(month), tax_deducted_ytd=deducted_ytd
            )
        assert deducted_ytd == annual


# ── Combined ────────────────────────────────────────────────────────────
class TestComputeStatutory:
    def test_low_earner_pays_pf_and_esi_but_no_tax(self):
        result = compute_statutory(
            gross_monthly=D("15000"), basic_monthly=D("7000"), config=config()
        )
        assert result.pf_employee == D("840.00")   # 7,000 basic * 12%
        assert result.esi_employee == D("112.50")
        assert result.tds == D("0.00")

    def test_employee_and_employer_contributions_are_separate(self):
        result = compute_statutory(
            gross_monthly=D("50000"), basic_monthly=D("20000"), config=config()
        )
        assert result.pf_employee == D("1800.00")
        assert result.pf_employer == D("1800.00")
        # Employer contributions must not reduce the employee's take-home.
        assert result.total_employer_contribution == D("1800.00")

    def test_totals_are_internally_consistent(self):
        result = compute_statutory(
            gross_monthly=D("150000"), basic_monthly=D("80000"), config=config()
        )
        assert result.total_employee_deduction == (
            result.pf_employee
            + result.esi_employee
            + result.professional_tax
            + result.tds
        )

    def test_non_india_disables_indian_rules(self):
        cfg = load_config(None, None, country="US")
        assert cfg.income_tax_enabled is False
        assert cfg.epf_enabled is False
        result = compute_statutory(
            gross_monthly=D("150000"), basic_monthly=D("80000"), config=cfg
        )
        assert result.total_employee_deduction == D("0.00")

    def test_tds_never_exceeds_the_salary_being_paid(self):
        """A late-month true-up must not drive net pay negative."""
        annual = D("292500")
        result = compute_statutory(
            gross_monthly=D("200000"),
            basic_monthly=D("150000"),
            config=config(),
            # The whole year lands in one month when prior months are missing.
            months_paid=fy_month_index(3),
            tax_deducted_ytd=D("0"),
        )
        assert result.tds <= D("200000")
        # Total withholding may reach the full salary, yielding net zero, but
        # must never exceed it.
        assert result.total_employee_deduction <= D("200000")
        assert result.pf_employee == D("1800.00")

    def test_uncapped_tds_would_have_exceeded_gross(self):
        """Guards the scenario the cap exists for."""
        annual = D("292500")
        uncapped = compute_monthly_tds(
            annual, months_paid=fy_month_index(3), tax_deducted_ytd=D("0")
        )
        assert uncapped > D("200000")

    def test_cap_does_not_bind_in_a_normal_month(self):
        result = compute_statutory(
            gross_monthly=D("200000"),
            basic_monthly=D("150000"),
            config=config(),
            months_paid=fy_month_index(4),
        )
        assert result.tds == D("24375.00")

    def test_regime_selection_by_code(self):
        assert load_config(None, None, regime="old").regime.code == "old"
        assert load_config(None, None, regime="new").regime.code == "new"
        assert set(REGIMES) == {"new", "old"}


# ── Tenant overrides ────────────────────────────────────────────────────
class TestTenantOverrides:
    """
    Tenant-configured statutory rules.

    Each test provisions its own organisation so the suite is order
    independent: a shared org would let one test's rule rows leak into
    another's assertions.
    """

    @pytest.fixture(scope="class")
    def db(self):
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def org(self, db, request):
        org = Organization(
            name=f"Statutory {request.node.name}",
            legal_id=f"TEST-STAT-{uuid.uuid4().hex[:12].upper()}",
        )
        db.add(org)
        db.commit()
        db.refresh(org)
        return org

    def _add_rule(self, db, org, code, params, is_active=True):
        rule = StatutoryRule(
            organization_id=org.id,
            rule_code=code,
            rule_name=code,
            parameter_json=json.dumps(params),
            is_active=is_active,
        )
        db.add(rule)
        db.commit()
        return rule

    def test_epf_rate_override_is_applied(self, db, org):
        self._add_rule(db, org, RULE_EPF, {"employee_rate": 0.10, "wage_ceiling": 20000})
        cfg = load_config(db, org.id)
        assert cfg.epf_employee_rate == D("0.10")
        assert cfg.epf_wage_ceiling == D("20000")
        # A configured statutory rule must actually change the calculation.
        assert compute_epf(D("20000"), cfg)["employee"] == D("2000.00")

    def test_esi_wage_ceiling_override(self, db, org):
        self._add_rule(db, org, RULE_ESI, {"wage_ceiling": 15000})
        cfg = load_config(db, org.id)
        assert cfg.esi_wage_ceiling == D("15000")
        assert compute_esi(D("20000"), cfg)["employee"] == D("0")

    def test_regime_and_slab_override(self, db, org):
        self._add_rule(db, org, RULE_INCOME_TAX, {
            "regime": "old",
            "slabs": [["300000", 0], [None, "0.10"]],
            "standard_deduction": 100000,
        })
        cfg = load_config(db, org.id)
        assert cfg.regime.code == "old"
        assert cfg.regime.standard_deduction == D("100000")
        result = compute_annual_income_tax(D("2000000"), cfg)
        # 20L gross - 10L standard deduction = 19L taxable; 3L nil, 16L @10%
        assert result["taxable_income"] == D("1900000.00")
        assert result["tax"] == D("160000.00")

    def test_percentage_style_rates_are_normalised(self, db, org):
        self._add_rule(db, org, RULE_EPF, {"employee_rate": 12})
        assert load_config(db, org.id).epf_employee_rate == D("0.12")

    def test_professional_tax_override(self, db, org):
        self._add_rule(db, org, RULE_PROFESSIONAL_TAX, {
            "enabled": True, "bands": [["20000", 0], [None, "200"]],
        })
        cfg = load_config(db, org.id)
        assert cfg.professional_tax_enabled is True
        assert compute_professional_tax(D("15000"), cfg) == D("0.00")
        assert compute_professional_tax(D("30000"), cfg) == D("200.00")

    def test_disabling_income_tax_via_override(self, db, org):
        self._add_rule(db, org, RULE_INCOME_TAX, {"enabled": False})
        assert load_config(db, org.id).income_tax_enabled is False

    def test_malformed_json_rule_is_skipped_not_fatal(self, db, org):
        """A configuration error must never halt salary payment."""
        rule = StatutoryRule(
            organization_id=org.id,
            rule_code="GARBAGE",
            rule_name="Garbage",
            parameter_json="{not valid json",
            is_active=True,
        )
        db.add(rule)
        db.commit()
        cfg = load_config(db, org.id)
        assert cfg.income_tax_enabled is True
        assert compute_epf(D("50000"), cfg)["employee"] == D("1800.00")

    def test_unknown_rule_code_is_ignored(self, db, org):
        self._add_rule(db, org, "NOT_A_REAL_CODE", {"x": 1})
        assert load_config(db, org.id).income_tax_enabled is True

    def test_inactive_rules_are_not_applied(self, db, org):
        self._add_rule(db, org, RULE_EPF, {"employee_rate": 0.10}, is_active=True)
        self._add_rule(db, org, RULE_EPF, {"employee_rate": 0.99}, is_active=False)
        # The active rule wins; the inactive one must have no effect.
        assert load_config(db, org.id).epf_employee_rate == D("0.10")

    def test_rules_are_scoped_to_their_organisation(self, db, org):
        self._add_rule(db, org, RULE_EPF, {"employee_rate": 0.05})
        other = Organization(
            name="Statutory unrelated org",
            legal_id=f"TEST-STAT-{uuid.uuid4().hex[:12].upper()}",
        )
        db.add(other)
        db.commit()
        db.refresh(other)
        assert load_config(db, org.id).epf_employee_rate == D("0.05")
        assert load_config(db, other.id).epf_employee_rate == D("0.12")

    def test_multiple_rules_combine(self, db, org):
        self._add_rule(db, org, RULE_EPF, {"employee_rate": 0.10})
        self._add_rule(db, org, RULE_ESI, {"wage_ceiling": 12000})
        cfg = load_config(db, org.id)
        assert cfg.epf_employee_rate == D("0.10")
        assert cfg.esi_wage_ceiling == D("12000")
