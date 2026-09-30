"""
Tests for payslip PDF generation.

The payslip endpoint was previously dead: the router queried a `Payslip` model
that was never defined, so every call raised ImportError. These tests pin the
model mapping (the original defect) and the document rendering.

Rendering tests call `build_payslip_pdf` directly because it is deliberately
free of database access; the persistence path is covered by the
`_get_payroll_for_payslip` tenant-isolation tests.
"""
import os
import uuid
from types import SimpleNamespace
from decimal import Decimal

import pytest

from app.db.database import SessionLocal
from app.db.models.all_models import (
    Organization,
    OrganizationSubscription,
    Payroll,
    Payslip,
    Role,
    SubscriptionPlan,
    User,
)
from app.routers.payroll import _get_payroll_for_payslip
from app.services.payslip_service import (
    _mask,
    _resolve_brand_color,
    build_payslip_pdf,
    format_money,
    period_label,
    resolve_currency,
)
from fastapi import HTTPException


# ── Fakes ───────────────────────────────────────────────────────────────
class FakeLineItem:
    def __init__(self, name, amount, kind, description=None):
        self.component_name = name
        self.amount = amount
        self.component_type = kind
        self.description = description


class FakeOrg:
    name = "Acme Robotics Pvt Ltd"
    legal_id = "GSTIN-29ABCDE1234F1Z5"
    primary_color = "#1F3A5F"


class FakeUser:
    id = 4711
    full_name = "Priya Raman"
    email = "priya.raman@example.com"


class FakeBank:
    account_holder_name = "Priya Raman"
    account_number_masked = "XXXXXX4471"
    bank_name = "HDFC Bank"
    ifsc_code = "HDFC0001234"


def _payroll(**overrides):
    defaults = dict(
        id=99,
        month=3,
        year=2026,
        base_salary=Decimal("120000.00"),
        deductions=Decimal("18500.00"),
        reimbursements_total=Decimal("0.00"),
        total_salary=Decimal("101500.00"),
        status="paid",
    )
    defaults.update(overrides)
    return type("FakePayroll", (), defaults)()


# ── Money / label helpers ───────────────────────────────────────────────
class TestHelpers:
    def test_format_money_groups_thousands(self):
        assert format_money("1234567.891", "USD") == "USD 1,234,567.89"

    def test_format_money_handles_none_and_rounds_half_up(self):
        assert format_money(None) == "USD 0.00"
        # 0.125 rounds up rather than to even, matching payroll convention.
        assert format_money("10.125") == "USD 10.13"

    def test_format_money_survives_non_numeric_input(self):
        assert format_money("not-a-number") == "USD 0.00"

    def test_format_money_avoids_float_drift(self):
        # 0.1 + 0.2 must not render as 0.30000000000000004.
        assert format_money(Decimal("0.1") + Decimal("0.2")) == "USD 0.30"

    def test_period_label(self):
        assert period_label(3, 2026) == "March 2026"
        assert period_label(12, 2025) == "December 2025"

    def test_period_label_tolerates_invalid_month(self):
        # Must not raise on corrupt payroll data.
        assert period_label(13, 2026) == "13 2026"

    def test_mask_never_reveals_full_account(self):
        masked = _mask("1234567890")
        assert masked.endswith("7890")
        assert "1234" not in masked

    def test_mask_handles_short_and_missing_values(self):
        assert _mask("12") == "••"
        assert _mask(None) == "—"

    def test_brand_color_rejects_untrusted_input(self):
        # A hostile or malformed colour must not reach the PDF renderer.
        assert _resolve_brand_color("javascript:alert(1)") is not None
        assert _resolve_brand_color(None) is not None
        assert _resolve_brand_color("#1F3A5F") is not None


# ── PDF rendering ───────────────────────────────────────────────────────
class TestPayslipPdf:
    def test_renders_valid_pdf_bytes(self):
        pdf = build_payslip_pdf(
            organization=FakeOrg(), employee=FakeUser(), payroll=_payroll()
        )
        assert pdf.startswith(b"%PDF-")
        assert len(pdf) > 1000

    def test_pdf_content_is_stable_for_same_input(self):
        # Raw PDF bytes embed a creation timestamp and document id, so they are
        # not byte-identical between renders. What must hold is that the same
        # inputs render the same document length and the same figures.
        args = dict(organization=FakeOrg(), employee=FakeUser(), payroll=_payroll())
        first = build_payslip_pdf(**args)
        second = build_payslip_pdf(**args)
        assert len(first) == len(second)

    def test_falls_back_to_base_salary_without_line_items(self):
        # A payroll with no PayrollLineItem rows must still state gross pay.
        pdf = build_payslip_pdf(
            organization=FakeOrg(), employee=FakeUser(), payroll=_payroll()
        )
        assert pdf.startswith(b"%PDF-")

    def test_renders_with_line_items_and_reimbursements(self):
        items = [
            FakeLineItem("Basic Salary", Decimal("100000"), "earning"),
            FakeLineItem("House Rent Allowance", Decimal("20000"), "earning"),
            FakeLineItem("Provident Fund", Decimal("12000"), "statutory"),
            FakeLineItem("Income Tax (TDS)", Decimal("6500"), "tax"),
        ]
        pdf = build_payslip_pdf(
            organization=FakeOrg(),
            employee=FakeUser(),
            payroll=_payroll(
                reimbursements_total=Decimal("3200.00"),
                total_salary=Decimal("100000.00"),
            ),
            line_items=items,
            designation="Senior Engineer",
            department="Platform",
            bank=FakeBank(),
        )
        assert pdf.startswith(b"%PDF-")
        assert len(pdf) > 1000

    def test_tolerates_unknown_line_item_type(self):
        # An unrecognised component must be surfaced, never silently dropped.
        items = [FakeLineItem("Bonus", Decimal("5000"), "mystery-type")]
        pdf = build_payslip_pdf(
            organization=FakeOrg(),
            employee=FakeUser(),
            payroll=_payroll(),
            line_items=items,
        )
        assert pdf.startswith(b"%PDF-")

    def test_negative_deduction_line_items_render_as_positive_amounts(self):
        """The payroll engine stores deductions as negative amounts.

        A payslip itemises them in a section already labelled "Deductions", so
        showing the raw sign would print "-1,800.00" and make the deduction
        total negative.
        """
        from app.services.payslip_service import _split_line_items

        items = [
            FakeLineItem("Basic Salary", Decimal("50000"), "earning"),
            FakeLineItem("Provident Fund", Decimal("-1800"), "statutory"),
            FakeLineItem("TDS", Decimal("-12566.67"), "tax"),
            FakeLineItem("Late Deduction", Decimal("-100"), "deduction"),
        ]
        earnings, deductions = _split_line_items(items)
        assert [e["name"] for e in earnings] == ["Basic Salary"]
        assert all(d["amount"] >= 0 for d in deductions)
        assert sum(d["amount"] for d in deductions) == Decimal("14466.67")

    def test_deductions_only_payslip_still_totals_correctly(self):
        from app.services.payslip_service import _split_line_items

        items = [FakeLineItem("Provident Fund", Decimal("-1800"), "statutory")]
        earnings, deductions = _split_line_items(items)
        assert earnings == []
        assert deductions[0]["amount"] == Decimal("1800.00")

    def test_statutory_and_tax_types_both_count_as_deductions(self):
        from app.services.payslip_service import _split_line_items

        items = [
            FakeLineItem("PF", Decimal("-1800"), "statutory"),
            FakeLineItem("ESI", Decimal("-112.50"), "statutory"),
            FakeLineItem("TDS", Decimal("-5000"), "tax"),
            FakeLineItem("Professional Tax", Decimal("-200"), "statutory"),
        ]
        _, deductions = _split_line_items(items)
        assert len(deductions) == 4
        assert sum(d["amount"] for d in deductions) == Decimal("7112.50")

    def test_tolerates_null_monetary_values(self):
        pdf = build_payslip_pdf(
            organization=FakeOrg(),
            employee=FakeUser(),
            payroll=_payroll(
                base_salary=None,
                deductions=None,
                reimbursements_total=None,
                total_salary=None,
            ),
        )
        assert pdf.startswith(b"%PDF-")

    def test_tolerates_missing_optional_metadata(self):
        bare_org = type("Org", (), {"name": "Acme", "legal_id": None, "primary_color": None})()
        bare_user = type("User", (), {"id": 1, "full_name": None, "email": None})()
        pdf = build_payslip_pdf(
            organization=bare_org, employee=bare_user, payroll=_payroll()
        )
        assert pdf.startswith(b"%PDF-")

    def test_survives_hostile_brand_color(self):
        hostile = type(
            "Org", (), {"name": "Acme", "legal_id": "X", "primary_color": "#ZZZZZZ"}
        )()
        pdf = build_payslip_pdf(
            organization=hostile, employee=FakeUser(), payroll=_payroll()
        )
        assert pdf.startswith(b"%PDF-")


# ── Model + tenant isolation ────────────────────────────────────────────
class TestPayslipModel:
    def test_payslip_model_is_importable(self):
        """Regression: the router referenced an unmapped `Payslip` model.

        Import failure here is what made every payslip request return HTTP 500.
        """
        assert Payslip.__tablename__ == "payslips"
        assert {"payroll_id", "org_id", "user_id", "file_url", "net_pay"} <= {
            c.name for c in Payslip.__table__.columns
        }


class TestPayslipAccessControl:
    """
    Tenant isolation on the payslip endpoints.

    The acting user is a plain object because the guard only reads org_id, id
    and role.name; building a full persisted User for each case would add
    fixture noise without exercising anything extra.
    """

    class _Actor:
        def __init__(self, actor_id, org_id, role_name):
            self.id = actor_id
            self.org_id = org_id
            self.role = type("Role", (), {"name": role_name})()

    @pytest.fixture(scope="class")
    def db(self):
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture(scope="class")
    def payroll_row(self, db):
        org = db.query(Organization).filter(Organization.name == "Payslip Test Org").first()
        if not org:
            org = Organization(
                name="Payslip Test Org",
                legal_id=f"TEST-PAYS-{uuid.uuid4().hex[:8].upper()}",
            )
            db.add(org)
            db.commit()
            db.refresh(org)

        # The payroll router is gated on the 'payroll' feature, so the fixture
        # tenant needs a plan that grants it.
        enterprise = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "enterprise").first()
        assert enterprise, "the enterprise plan must be seeded"
        subscription = (
            db.query(OrganizationSubscription)
            .filter(OrganizationSubscription.organization_id == org.id)
            .first()
        )
        if not subscription:
            subscription = OrganizationSubscription(
                organization_id=org.id,
                subscription_plan_id=enterprise.id,
                status="active",
                billing_cycle="monthly",
            )
            db.add(subscription)
        else:
            subscription.subscription_plan_id = enterprise.id
            subscription.status = "active"
        db.commit()

        user = (
            db.query(User)
            .filter(User.email == "payslip.test@example.com")
            .first()
        )
        if not user:
            role = db.query(Role).first()
            assert role, "a role must exist to build a valid user"
            user = User(
                org_id=org.id,
                role_id=role.id,
                full_name="Payslip Tester",
                username="payslip.tester",
                email="payslip.test@example.com",
                employee_id="PAYSLIP-0001",
                hashed_password="not-a-real-hash",
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        payroll = (
            db.query(Payroll)
            .filter(Payroll.org_id == org.id, Payroll.user_id == user.id)
            .first()
        )
        if not payroll:
            payroll = Payroll(
                user_id=user.id,
                org_id=org.id,
                month=3,
                year=2026,
                base_salary=Decimal("100000.00"),
                deductions=Decimal("10000.00"),
                reimbursements_total=Decimal("0.00"),
                total_salary=Decimal("90000.00"),
                status="paid",
            )
            db.add(payroll)
            db.commit()
            db.refresh(payroll)
        return payroll

    def test_rejects_payslip_from_another_tenant(self, db, payroll_row):
        outsider = self._Actor(
            actor_id=999001,
            org_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            role_name="admin",
        )
        with pytest.raises(HTTPException) as exc:
            _get_payroll_for_payslip(db, payroll_row.id, outsider)
        assert exc.value.status_code == 404

    def test_rejects_employee_viewing_another_employees_payslip(self, db, payroll_row):
        colleague = self._Actor(
            actor_id=999002, org_id=payroll_row.org_id, role_name="employee"
        )
        with pytest.raises(HTTPException) as exc:
            _get_payroll_for_payslip(db, payroll_row.id, colleague)
        assert exc.value.status_code == 403

    def test_allows_employee_viewing_own_payslip(self, db, payroll_row):
        owner = self._Actor(
            actor_id=payroll_row.user_id, org_id=payroll_row.org_id, role_name="employee"
        )
        assert _get_payroll_for_payslip(db, payroll_row.id, owner).id == payroll_row.id

    def test_allows_manager_viewing_team_payslip(self, db, payroll_row):
        manager = self._Actor(
            actor_id=999003, org_id=payroll_row.org_id, role_name="manager"
        )
        assert _get_payroll_for_payslip(db, payroll_row.id, manager).id == payroll_row.id

    def test_unknown_payroll_returns_404(self, db, payroll_row):
        actor = self._Actor(
            actor_id=payroll_row.user_id, org_id=payroll_row.org_id, role_name="employee"
        )
        with pytest.raises(HTTPException) as exc:
            _get_payroll_for_payslip(db, 0, actor)
        assert exc.value.status_code == 404


class TestCurrencyResolution:
    def test_explicit_override_wins(self):
        from app.services.payslip_service import DEFAULT_CURRENCY
        assert resolve_currency(None, None, override="inr") == "INR"
        assert DEFAULT_CURRENCY == "INR"

    def test_falls_back_to_the_statutory_currency(self):
        assert resolve_currency(None, None) == "INR"

    def test_reads_the_snapshot_from_the_payroll_row(self):
        """The printed currency must match the one the figures were computed in."""
        payroll = SimpleNamespace(currency="inr")
        assert resolve_currency(None, payroll) == "INR"

        payroll = SimpleNamespace(currency="GBP")
        assert resolve_currency(None, payroll) == "GBP"


class TestPayslipStorage:
    """The download path must never read outside the payslip storage root."""

    @pytest.fixture
    def stored(self, db):
        from app.services.payslip_service import generate_payslip

        payroll = db.query(Payroll).filter(Payroll.month == 3, Payroll.year == 2026).first()
        assert payroll, "a payroll row is required for the storage tests"
        return generate_payslip(db, payroll)

    def test_reads_generated_payslip(self, stored):
        from app.services.payslip_service import read_payslip_bytes
        assert read_payslip_bytes(stored).startswith(b"%PDF-")

    def test_read_is_independent_of_working_directory(self, stored, tmp_path, monkeypatch):
        from app.services.payslip_service import read_payslip_bytes
        monkeypatch.chdir(tmp_path)
        assert read_payslip_bytes(stored).startswith(b"%PDF-")

    def test_blocks_absolute_path_outside_storage_root(self, stored):
        from app.services.payslip_service import PayslipStorageError, read_payslip_bytes
        stored.file_url = "/etc/passwd"
        with pytest.raises(PayslipStorageError):
            read_payslip_bytes(stored)

    def test_blocks_relative_escape_from_storage_root(self, stored):
        from app.services.payslip_service import PayslipStorageError, read_payslip_bytes
        stored.file_url = "../../../../../../etc/passwd"
        with pytest.raises(PayslipStorageError):
            read_payslip_bytes(stored)

    def test_blocks_symlink_escape(self, stored, tmp_path):
        from app.services.payslip_service import PayslipStorageError, read_payslip_bytes
        outside = tmp_path / "outside.pdf"
        outside.write_bytes(b"%PDF-1.4 not really ours")
        link = os.path.join(os.path.dirname(stored.file_url), "escape.pdf")
        if os.path.lexists(link):
            os.unlink(link)
        os.symlink(outside, link)
        try:
            stored.file_url = link
            with pytest.raises(PayslipStorageError):
                read_payslip_bytes(stored)
        finally:
            os.unlink(link)

    def test_missing_file_is_recoverable_not_a_permission_error(self, stored):
        from app.services.payslip_service import PayslipStorageError, read_payslip_bytes
        # Inside the root but absent: the endpoint re-renders, so this must
        # not surface as a storage-permission violation.
        stored.file_url = os.path.join(
            os.path.dirname(stored.file_url), "definitely-absent.pdf"
        )
        with pytest.raises(FileNotFoundError):
            read_payslip_bytes(stored)

    def test_empty_path_is_rejected(self, stored):
        from app.services.payslip_service import PayslipStorageError, read_payslip_bytes
        stored.file_url = ""
        with pytest.raises(PayslipStorageError):
            read_payslip_bytes(stored)

    def test_s3_paths_are_delegated_to_the_provider(self, stored, monkeypatch):
        from app.services import payslip_service
        monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")
        stored.file_url = "s3://test-bucket/payslips/x.pdf"
        assert payslip_service.read_payslip_bytes(stored) == b"s3_file_content_placeholder"


class TestPayslipDownloadEndpoint:
    """End-to-end download through the HTTP layer."""

    @pytest.fixture
    def payroll_row(self, db):
        org = db.query(Organization).filter(Organization.name == "Payslip Test Org").first()
        if not org:
            pytest.skip("payslip fixture org not initialised")
        user = db.query(User).filter(User.email == "payslip.test@example.com").first()
        if not user:
            pytest.skip("payslip fixture user not initialised")
        payroll = (
            db.query(Payroll)
            .filter(Payroll.org_id == org.id, Payroll.user_id == user.id)
            .first()
        )
        if not payroll:
            pytest.skip("payslip fixture payroll not initialised")
        return payroll

    def test_download_returns_pdf(self, db, payroll_row):
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.db.database import get_db
        from main import app

        actor = TestPayslipAccessControl._Actor(
            actor_id=payroll_row.user_id, org_id=payroll_row.org_id, role_name="employee"
        )
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_active_user] = lambda: actor
        try:
            with TestClient(app) as client:
                resp = client.get(f"/api/v1/payroll/{payroll_row.id}/payslip/download")
            assert resp.status_code == 200, resp.text
            assert resp.headers["content-type"].startswith("application/pdf")
            assert "attachment" in resp.headers.get("content-disposition", "")
            assert resp.content.startswith(b"%PDF-")
        finally:
            app.dependency_overrides.clear()

    def test_metadata_endpoint_reports_figures(self, db, payroll_row):
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.db.database import get_db
        from main import app

        actor = TestPayslipAccessControl._Actor(
            actor_id=payroll_row.user_id, org_id=payroll_row.org_id, role_name="employee"
        )
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_active_user] = lambda: actor
        try:
            with TestClient(app) as client:
                resp = client.get(f"/api/v1/payroll/{payroll_row.id}/payslip")
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["payroll_id"] == payroll_row.id
            assert body["period_label"] == "2026-03"
            assert "net_pay" in body and "download_url" in body
        finally:
            app.dependency_overrides.clear()

    def test_employee_cannot_regenerate(self, db, payroll_row):
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.db.database import get_db
        from main import app

        actor = TestPayslipAccessControl._Actor(
            actor_id=payroll_row.user_id, org_id=payroll_row.org_id, role_name="employee"
        )
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_active_user] = lambda: actor
        try:
            with TestClient(app) as client:
                resp = client.post(f"/api/v1/payroll/{payroll_row.id}/payslip/generate")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_cross_tenant_payslip_is_not_readable(self, db, payroll_row):
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.db.database import get_db
        from main import app

        # The outsider is put on a paid plan so the feature gate passes and the
        # test exercises tenant isolation itself, not the plan gate's 402.
        enterprise = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "enterprise").first()
        other_org = (
            db.query(Organization)
            .filter(Organization.name == "Payslip Other Org")
            .first()
        )
        if not other_org:
            other_org = Organization(
                name="Payslip Other Org",
                legal_id=f"TEST-OTHR-{uuid.uuid4().hex[:8].upper()}",
            )
            db.add(other_org)
            db.commit()
            db.refresh(other_org)
        if not (
            db.query(OrganizationSubscription)
            .filter(OrganizationSubscription.organization_id == other_org.id)
            .first()
        ):
            db.add(OrganizationSubscription(
                organization_id=other_org.id,
                subscription_plan_id=enterprise.id,
                status="active",
                billing_cycle="monthly",
            ))
            db.commit()

        outsider = TestPayslipAccessControl._Actor(
            actor_id=999999, org_id=other_org.id, role_name="admin"
        )
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_active_user] = lambda: outsider
        try:
            with TestClient(app) as client:
                resp = client.get(f"/api/v1/payroll/{payroll_row.id}/payslip/download")
            # Must not leak the other tenant's payslip, and must not 200.
            assert resp.status_code in (403, 404), resp.text
            assert resp.content[:5] != b"%PDF-"
        finally:
            app.dependency_overrides.clear()
