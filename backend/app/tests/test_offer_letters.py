"""
Tests for offer letter generation.

Covers the two properties that make this feature safe to put in front of
candidates: merge-tag resolution (escaping, no recursive expansion, unresolved
tags refused) and the draft -> sent -> accepted/declined lifecycle including
the response window.

Rendering is tested through the pure `build_offer_letter_pdf`; the HTTP layer
through dependency overrides so tenant isolation is exercised end to end.
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.db.database import SessionLocal
from app.db.models.all_models import (
    Candidate,
    JobApplication,
    JobPosting,
    Organization,
    OfferLetter,
    OfferTemplate,
    Role,
    User,
)
from app.routers import offer_letters
from app.services import offer_letter_service as svc
from app.services.offer_letter_service import (
    DEFAULT_TEMPLATE_BODY,
    DEFAULT_TEMPLATE_NAME,
    MAX_EXPIRY_DAYS,
    OfferRenderError,
    available_tags,
    build_offer_letter_pdf,
    expiry_for,
    is_expired,
    render_tags,
)


def D(value):
    return Decimal(str(value))


# ── Fakes ───────────────────────────────────────────────────────────────
class FakeOrg:
    name = "Acme Robotics Pvt Ltd"
    legal_id = "GSTIN-29ABCDE1234F1Z5"
    primary_color = "#1F3A5F"


class FakeCandidate:
    id = 77
    full_name = "Priya Raman"
    email = "priya.raman@example.com"


class FakeApplication:
    class job_posting:
        title = "Senior Backend Engineer"
        location = "Bengaluru"


def _offer(**overrides):
    now = datetime.now(timezone.utc)
    # Mirrors every attribute of the ORM row the service touches, so the fake
    # cannot hide a missing-column bug behind a getattr default.
    defaults = dict(
        id=1,
        organization_id=None,
        candidate_id=77,
        application_id=None,
        job_posting_id=None,
        template_id=None,
        designation="Senior Backend Engineer",
        employment_type="Full-time",
        location="Bengaluru",
        currency="INR",
        base_pay=D("2400000.00"),
        allowances=D("600000.00"),
        annual_ctc=D("3000000.00"),
        offer_date=now,
        start_date=now + timedelta(days=30),
        expiry_date=None,
        expires_in_days=7,
        status="draft",
        file_url=None,
        pdf_sha256=None,
        sent_at=None,
        responded_at=None,
        decline_reason=None,
    )
    defaults.update(overrides)
    return type("FakeOffer", (), defaults)()


# ── Merge tags ──────────────────────────────────────────────────────────
class TestMergeTags:
    def test_default_template_resolves_completely(self):
        """The shipped template must not contain an unknown tag."""
        context = {tag: "x" for tag in available_tags()}
        rendered, unresolved = render_tags(DEFAULT_TEMPLATE_BODY, context)
        assert unresolved == []
        assert "{{" not in rendered

    def test_available_tags_cover_the_default_template(self):
        context = {tag: "x" for tag in available_tags()}
        _, unresolved = render_tags(DEFAULT_TEMPLATE_BODY, context)
        assert unresolved == []

    def test_substitutes_a_value(self):
        rendered, _ = render_tags("Hello {{name}}", {"name": "Ada"})
        assert rendered == "Hello Ada"

    def test_tolerates_internal_whitespace_in_tag(self):
        assert render_tags("{{ name }}", {"name": "Ada"})[0] == "Ada"

    def test_xml_escapes_substituted_values(self):
        """ReportLab paragraphs parse XML, so unescaped values corrupt the PDF."""
        rendered, _ = render_tags("Hi {{name}}", {"name": "Tom & Jerry <b>x</b>"})
        assert rendered == "Hi Tom &amp; Jerry &lt;b&gt;x&lt;/b&gt;"

    def test_does_not_recursively_expand_values(self):
        """A value that looks like a tag must never be re-expanded."""
        rendered, _ = render_tags("{{a}}", {"a": "{{b}}", "b": "LEAKED"})
        assert "LEAKED" not in rendered
        assert rendered == "{{b}}"

    def test_strict_mode_refuses_unresolved_tags(self):
        with pytest.raises(OfferRenderError) as exc:
            render_tags("Hello {{mystery}}", {"name": "Ada"})
        assert "mystery" in exc.value.unresolved

    def test_non_strict_mode_reports_unresolved_tags(self):
        rendered, unresolved = render_tags("Hello {{mystery}}", {}, strict=False)
        assert unresolved == ["mystery"]
        assert rendered == "Hello {{mystery}}"

    def test_empty_context_renders_none_of_the_values(self):
        rendered, unresolved = render_tags("{{a}}-{{b}}", {}, strict=False)
        assert unresolved == ["a", "b"]
        assert rendered == "{{a}}-{{b}}"

    def test_null_value_renders_as_empty_not_none(self):
        assert render_tags("[{{a}}]", {"a": None})[0] == "[]"


# ── Money / dates ───────────────────────────────────────────────────────
class TestFormatting:
    def test_money_is_grouped(self):
        assert svc.format_money("2400000", "INR") == "INR 2,400,000.00"

    def test_money_survives_bad_input(self):
        assert svc.format_money(None) == "USD 0.00"
        assert svc.format_money("abc") == "USD 0.00"

    def test_money_avoids_float_drift(self):
        assert svc.format_money(D("0.1") + D("0.2")) == "USD 0.30"

    def test_long_date_handles_none(self):
        assert svc.long_date(None) == "—"

    def test_long_date_formats(self):
        assert svc.long_date(datetime(2026, 10, 5, tzinfo=timezone.utc)) == "05 October 2026"


# ── PDF rendering ───────────────────────────────────────────────────────
class TestOfferLetterPdf:
    def _pdf(self, **overrides):
        offer = _offer(**overrides)
        return build_offer_letter_pdf(
            offer=offer,
            organization=FakeOrg(),
            candidate=FakeCandidate(),
            application=FakeApplication(),
        )

    def test_renders_valid_pdf(self):
        assert self._pdf().startswith(b"%PDF-")

    def test_renders_with_a_custom_template(self):
        template = OfferTemplate(
            organization_id=None,
            name="Contract",
            subject="Offer: {{designation}}",
            body="Hi {{candidate_name}}, your {{job_title}} role pays {{annual_ctc}}.",
        )
        offer = _offer()
        pdf = build_offer_letter_pdf(
            offer=offer,
            organization=FakeOrg(),
            candidate=FakeCandidate(),
            application=FakeApplication(),
            template=template,
        )
        assert pdf.startswith(b"%PDF-")

    def test_refuses_template_with_unknown_tag(self):
        template = OfferTemplate(
            organization_id=None,
            name="Broken",
            subject=None,
            body="Hello {{nonexistent_tag}}",
        )
        with pytest.raises(OfferRenderError):
            build_offer_letter_pdf(
                offer=_offer(),
                organization=FakeOrg(),
                candidate=FakeCandidate(),
                template=template,
            )

    def test_hostile_candidate_name_does_not_break_rendering(self):
        """A candidate name is untrusted text that reaches the document."""
        hostile = type("C", (), {
            "id": 1, "full_name": "A & B <script>alert(1)</script>", "email": "x@y.z",
        })()
        pdf = build_offer_letter_pdf(
            offer=_offer(),
            organization=FakeOrg(),
            candidate=hostile,
            application=FakeApplication(),
        )
        assert pdf.startswith(b"%PDF-")

    def test_tolerates_missing_optional_metadata(self):
        bare_org = type("O", (), {"name": "Acme", "legal_id": None, "primary_color": None})()
        bare_candidate = type("C", (), {"id": 1, "full_name": None, "email": None})()
        pdf = build_offer_letter_pdf(
            offer=_offer(location=None, currency="USD"),
            organization=bare_org,
            candidate=bare_candidate,
            application=None,
        )
        assert pdf.startswith(b"%PDF-")

    def test_annual_ctc_defaults_to_base_plus_allowances(self):
        offer = _offer(annual_ctc=D("0"))
        context = svc.build_context(
            offer=offer, organization=FakeOrg(), candidate=FakeCandidate()
        )
        assert context["annual_ctc"] == "INR 3,000,000.00"

    def test_body_paragraphs_split_on_blank_lines(self):
        assert svc._body_paragraphs("a\nb\n\nc") == ["a\nb", "c"]

    def test_body_paragraphs_tolerate_empty_input(self):
        assert svc._body_paragraphs("") == []
        assert svc._body_paragraphs(None) == []


# ── Response window ─────────────────────────────────────────────────────
class TestResponseWindow:
    def test_expiry_is_derived_from_the_window(self):
        offer = _offer(
            offer_date=datetime(2026, 10, 1, tzinfo=timezone.utc), expires_in_days=7
        )
        assert expiry_for(offer) == datetime(2026, 10, 8, tzinfo=timezone.utc)

    def test_explicit_expiry_date_wins(self):
        offer = _offer(expiry_date=datetime(2026, 11, 1, tzinfo=timezone.utc))
        assert expiry_for(offer) == datetime(2026, 11, 1, tzinfo=timezone.utc)

    def test_naive_timestamps_are_treated_as_utc(self):
        offer = _offer(offer_date=datetime(2026, 10, 1))
        assert expiry_for(offer).tzinfo is not None

    def test_sent_offer_expires_after_the_window(self):
        offer = _offer(
            status="sent",
            offer_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
            expires_in_days=7,
        )
        assert is_expired(offer, now=datetime(2026, 10, 9, tzinfo=timezone.utc)) is True
        assert is_expired(offer, now=datetime(2026, 10, 7, tzinfo=timezone.utc)) is False

    def test_answered_offer_never_expires(self):
        for status in ("accepted", "declined", "withdrawn"):
            offer = _offer(status=status, offer_date=datetime(2020, 1, 1, tzinfo=timezone.utc))
            assert is_expired(offer, now=datetime(2030, 1, 1, tzinfo=timezone.utc)) is False

    def test_effective_status_reflects_expiry(self):
        offer = _offer(
            status="sent", offer_date=datetime(2020, 1, 1, tzinfo=timezone.utc)
        )
        assert svc.effective_status(offer, now=datetime(2030, 1, 1, tzinfo=timezone.utc)) == "expired"

    def test_default_window_is_bounded(self):
        assert MAX_EXPIRY_DAYS == 90


# ── Templates, persistence and tenant isolation ─────────────────────────
class TestOfferLetterPersistence:
    @pytest.fixture(scope="class")
    def db(self):
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def org(self, db):
        organization = Organization(
            name="Offer Test Org", legal_id=f"TEST-OFFER-{uuid.uuid4().hex[:8].upper()}"
        )
        db.add(organization)
        db.commit()
        db.refresh(organization)
        return organization

    @pytest.fixture
    def candidate(self, db, org):
        candidate = Candidate(
            organization_id=org.id, full_name="Priya Raman", email="priya.offer@example.com"
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        return candidate

    def test_default_template_is_provisioned_on_demand(self, db, org):
        template = svc.ensure_default_template(db, org.id)
        assert template.is_default is True
        assert template.is_active is True
        # Provisioning twice must not create a second default.
        again = svc.ensure_default_template(db, org.id)
        assert again.id == template.id

    def test_default_template_renders_without_errors(self, db, org, candidate):
        template = svc.ensure_default_template(db, org.id)
        offer = OfferLetter(
            organization_id=org.id,
            candidate_id=candidate.id,
            designation="Engineer",
            employment_type="Full-time",
            location="Remote",
            currency="USD",
            base_pay=D("100000"),
            allowances=D("10000"),
            annual_ctc=D("110000"),
            offer_date=datetime.now(timezone.utc),
            start_date=datetime.now(timezone.utc),
            expires_in_days=7,
            template_id=template.id,
        )
        db.add(offer)
        db.commit()
        db.refresh(offer)

        svc.generate_offer_letter_pdf(db, offer)
        assert offer.file_url
        assert offer.pdf_sha256 and len(offer.pdf_sha256) == 64
        assert svc.read_offer_letter_bytes(offer).startswith(b"%PDF-")

    def test_generation_is_idempotent_by_default(self, db, org, candidate):
        offer = _persist_offer(db, org, candidate)
        svc.generate_offer_letter_pdf(db, offer)
        first = offer.file_url
        svc.generate_offer_letter_pdf(db, offer)
        assert offer.file_url == first

    def test_regenerate_replaces_the_document(self, db, org, candidate):
        offer = _persist_offer(db, org, candidate)
        svc.generate_offer_letter_pdf(db, offer)
        first = offer.file_url
        svc.generate_offer_letter_pdf(db, offer, regenerate=True)
        assert offer.file_url == first  # deterministic id

    def test_missing_candidate_is_reported(self, db, org):
        """A dangling candidate must be refused, not rendered as blank."""
        # Deliberately unpersisted: the FK constraint would otherwise reject
        # the insert before the service's own check runs.
        offer = OfferLetter(
            organization_id=org.id,
            candidate_id=999999,
            designation="Engineer",
            base_pay=D("1"),
            allowances=D("0"),
            annual_ctc=D("1"),
            offer_date=datetime.now(timezone.utc),
            start_date=datetime.now(timezone.utc),
            expires_in_days=7,
        )
        with pytest.raises(ValueError):
            svc.generate_offer_letter_pdf(db, offer)

    def test_offer_model_rejects_negative_money(self, db, org, candidate):
        # The database check constraint must reject negative compensation.
        from sqlalchemy.exc import IntegrityError

        offer = _persist_offer(db, org, candidate)
        offer.base_pay = D("-1")
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_template_name_is_unique_per_organisation(self, db, org):
        db.add(OfferTemplate(organization_id=org.id, name="T1", body="x"))
        db.commit()
        from sqlalchemy.exc import IntegrityError

        db.add(OfferTemplate(organization_id=org.id, name="T1", body="y"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def _persist_offer(db, org, candidate, **overrides):
    defaults = dict(
        organization_id=org.id,
        candidate_id=candidate.id,
        designation="Engineer",
        employment_type="Full-time",
        location="Remote",
        currency="USD",
        base_pay=D("100000"),
        allowances=D("10000"),
        annual_ctc=D("110000"),
        offer_date=datetime.now(timezone.utc),
        start_date=datetime.now(timezone.utc),
        expires_in_days=7,
    )
    defaults.update(overrides)
    offer = OfferLetter(**defaults)
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer


# ── HTTP layer ──────────────────────────────────────────────────────────
class TestOfferLetterEndpoints:
    @pytest.fixture(scope="class")
    def db(self):
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    class _Actor:
        def __init__(self, org_id, user_id=None, role_name="admin"):
            self.id = user_id
            self.org_id = org_id
            self.role = type("Role", (), {"name": role_name})()

    @pytest.fixture
    def org(self, db):
        organization = Organization(
            name="Offer HTTP Org", legal_id=f"TEST-HTTP-{uuid.uuid4().hex[:8].upper()}"
        )
        db.add(organization)
        db.commit()
        db.refresh(organization)
        return organization

    @pytest.fixture
    def subscribed(self, db, org):
        """Attach the tenant to a plan granting the `recruitment` feature."""
        from app.db.models.all_models import OrganizationSubscription, SubscriptionPlan

        plan = (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.code == "enterprise")
            .first()
        )
        assert plan, "the enterprise plan must be seeded"
        db.add(OrganizationSubscription(
            organization_id=org.id,
            subscription_plan_id=plan.id,
            status="active",
            billing_cycle="monthly",
        ))
        db.commit()
        return org

    def test_tags_endpoint_lists_available_tags(self, db, subscribed):
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.db.database import get_db
        from main import app

        actor = self._Actor(subscribed.id)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_active_user] = lambda: actor
        try:
            with TestClient(app) as client:
                resp = client.get("/api/v1/recruitment/offer-templates/tags")
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["syntax"] == "{{tag_name}}"
            assert "candidate_name" in body["tags"]
            assert "annual_ctc" in body["tags"]
        finally:
            app.dependency_overrides.clear()

    def test_create_and_download_offer(self, db, subscribed):
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.db.database import get_db
        from main import app

        candidate = Candidate(
            organization_id=subscribed.id,
            full_name="Arun Kumar",
            email="arun.offer@example.com",
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        actor = self._Actor(subscribed.id)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_active_user] = lambda: actor
        app.dependency_overrides[offer_letters.MANAGE] = lambda: actor
        try:
            with TestClient(app) as client:
                created = client.post("/api/v1/recruitment/offer-letters", json={
                    "candidate_id": candidate.id,
                    "designation": "Product Designer",
                    "base_pay": 900000,
                    "allowances": 100000,
                    "currency": "inr",
                    "expires_in_days": 5,
                })
                assert created.status_code == 201, created.text
                offer = created.json()
                assert offer["status"] == "draft"
                # Currency is normalised to an ISO-style uppercase code.
                assert offer["currency"] == "INR"
                # Annual CTC is derived when not supplied.
                assert offer["annual_ctc"] == 1000000.0

                generated = client.post(
                    f"/api/v1/recruitment/offer-letters/{offer['id']}/generate"
                )
                assert generated.status_code == 200, generated.text
                assert generated.json()["pdf_sha256"]

                download = client.get(
                    f"/api/v1/recruitment/offer-letters/{offer['id']}/download"
                )
                assert download.status_code == 200, download.text
                assert download.headers["content-type"].startswith("application/pdf")
                assert download.content.startswith(b"%PDF-")
        finally:
            app.dependency_overrides.clear()

    def test_offer_lifecycle_draft_to_accepted(self, db, subscribed):
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.db.database import get_db
        from main import app

        candidate = Candidate(
            organization_id=subscribed.id, full_name="Meera Iyer", email="meera.offer@example.com"
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        actor = self._Actor(subscribed.id)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_active_user] = lambda: actor
        app.dependency_overrides[offer_letters.MANAGE] = lambda: actor
        try:
            with TestClient(app) as client:
                offer = client.post("/api/v1/recruitment/offer-letters", json={
                    "candidate_id": candidate.id,
                    "designation": "Data Analyst",
                    "base_pay": 600000,
                }).json()

                # A draft cannot be answered directly.
                early = client.post(
                    f"/api/v1/recruitment/offer-letters/{offer['id']}/respond",
                    json={"accepted": True},
                )
                assert early.status_code == 409

                sent = client.post(f"/api/v1/recruitment/offer-letters/{offer['id']}/send")
                assert sent.status_code == 200, sent.text
                assert sent.json()["status"] == "sent"
                assert sent.json()["pdf_sha256"]

                # Sending twice is a conflict.
                assert client.post(
                    f"/api/v1/recruitment/offer-letters/{offer['id']}/send"
                ).status_code == 409

                accepted = client.post(
                    f"/api/v1/recruitment/offer-letters/{offer['id']}/respond",
                    json={"accepted": True},
                )
                assert accepted.status_code == 200, accepted.text
                assert accepted.json()["status"] == "accepted"
                assert accepted.json()["responded_at"]
        finally:
            app.dependency_overrides.clear()

    def test_decline_requires_a_reason(self, db, subscribed):
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.db.database import get_db
        from main import app

        candidate = Candidate(
            organization_id=subscribed.id, full_name="Decline Case", email="decline.offer@example.com"
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        offer = _persist_offer(db, subscribed, candidate, status="sent")
        actor = self._Actor(subscribed.id)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_active_user] = lambda: actor
        app.dependency_overrides[offer_letters.MANAGE] = lambda: actor
        try:
            with TestClient(app) as client:
                path = f"/api/v1/recruitment/offer-letters/{offer.id}/respond"
                assert client.post(path, json={"accepted": False}).status_code == 422
                declined = client.post(
                    path, json={"accepted": False, "reason": "Accepted another offer"}
                )
                assert declined.status_code == 200
                assert declined.json()["status"] == "declined"
                assert declined.json()["decline_reason"] == "Accepted another offer"
        finally:
            app.dependency_overrides.clear()

    def test_expired_offer_cannot_be_answered(self, db, subscribed):
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.db.database import get_db
        from main import app

        candidate = Candidate(
            organization_id=subscribed.id, full_name="Late Case", email="late.offer@example.com"
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        offer = _persist_offer(
            db, subscribed, candidate, status="sent",
            offer_date=datetime.now(timezone.utc) - timedelta(days=30),
        )
        actor = self._Actor(subscribed.id)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_active_user] = lambda: actor
        app.dependency_overrides[offer_letters.MANAGE] = lambda: actor
        try:
            with TestClient(app) as client:
                resp = client.post(
                    f"/api/v1/recruitment/offer-letters/{offer.id}/respond",
                    json={"accepted": True},
                )
                assert resp.status_code == 409
                assert "window" in resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_cross_tenant_offer_is_not_readable(self, db, subscribed):
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.db.database import get_db
        from main import app

        candidate = Candidate(
            organization_id=subscribed.id, full_name="Private Case", email="private.offer@example.com"
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        offer = _persist_offer(db, subscribed, candidate)
        svc.generate_offer_letter_pdf(db, offer)

        other = Organization(
            name="Other Tenant", legal_id=f"TEST-OTH-{uuid.uuid4().hex[:8].upper()}"
        )
        db.add(other)
        db.commit()
        db.refresh(other)
        from app.db.models.all_models import OrganizationSubscription, SubscriptionPlan
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "enterprise").first()
        db.add(OrganizationSubscription(
            organization_id=other.id, subscription_plan_id=plan.id,
            status="active", billing_cycle="monthly",
        ))
        db.commit()

        actor = self._Actor(other.id)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_active_user] = lambda: actor
        app.dependency_overrides[offer_letters.MANAGE] = lambda: actor
        try:
            with TestClient(app) as client:
                resp = client.get(
                    f"/api/v1/recruitment/offer-letters/{offer.id}/download"
                )
                assert resp.status_code == 404
                assert resp.content[:5] != b"%PDF-"
        finally:
            app.dependency_overrides.clear()

    def test_candidate_from_another_tenant_is_rejected(self, db, subscribed):
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.db.database import get_db
        from main import app

        other = Organization(
            name="Foreign Candidate Org", legal_id=f"TEST-FC-{uuid.uuid4().hex[:8].upper()}"
        )
        db.add(other)
        db.commit()
        db.refresh(other)
        foreign = Candidate(
            organization_id=other.id, full_name="Foreign", email="foreign.offer@example.com"
        )
        db.add(foreign)
        db.commit()
        db.refresh(foreign)

        actor = self._Actor(subscribed.id)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_active_user] = lambda: actor
        app.dependency_overrides[offer_letters.MANAGE] = lambda: actor
        try:
            with TestClient(app) as client:
                resp = client.post("/api/v1/recruitment/offer-letters", json={
                    "candidate_id": foreign.id,
                    "designation": "Intruder",
                    "base_pay": 1,
                })
                assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_expires_in_days_is_bounded(self, db, subscribed):
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.db.database import get_db
        from main import app

        candidate = Candidate(
            organization_id=subscribed.id, full_name="Bounds Case", email="bounds.offer@example.com"
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        actor = self._Actor(subscribed.id)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_active_user] = lambda: actor
        app.dependency_overrides[offer_letters.MANAGE] = lambda: actor
        try:
            with TestClient(app) as client:
                resp = client.post("/api/v1/recruitment/offer-letters", json={
                    "candidate_id": candidate.id,
                    "designation": "Too Long",
                    "base_pay": 1,
                    "expires_in_days": MAX_EXPIRY_DAYS + 1,
                })
                assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()
