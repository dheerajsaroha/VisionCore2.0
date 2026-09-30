"""
Offer letter generation.

Renders a per-tenant template into a PDF offer letter for a candidate, and
manages the draft -> sent -> accepted/declined lifecycle.

Two details carry most of the risk here:

* **Escaping.** The rendered document is a ReportLab `Paragraph`, which parses
  a small HTML/XML dialect. Candidate- and employer-supplied text substituted
  into the body must therefore be XML-escaped, or a name containing `&` or
  `<b>` corrupts the document and can inject markup.
* **Tag resolution.** Tags are resolved in a single pass so a value that itself
  contains `{{...}}` is never re-expanded, and unknown tags are reported rather
  than silently dropped — a legal document must not ship with `{{salary}}`
  still visible in it.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.db.models.all_models import (
    Candidate,
    JobApplication,
    OfferLetter,
    OfferTemplate,
    Organization,
)
from app.services.pdf_documents import (
    SUBDIR_OFFER_LETTERS,
    read_pdf,
    sha256_hex,
    store_pdf,
)

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")

# {{ tag_name }} with optional internal whitespace.
TAG_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")

DEFAULT_EXPIRY_DAYS = 7
MAX_EXPIRY_DAYS = 90

STATUS_DRAFT = "draft"
STATUS_SENT = "sent"
STATUS_ACCEPTED = "accepted"
STATUS_DECLINED = "declined"
STATUS_WITHDRAWN = "withdrawn"
STATUS_EXPIRED = "expired"

DEFAULT_CURRENCY = "USD"

DEFAULT_TEMPLATE_NAME = "Standard full-time offer"

DEFAULT_TEMPLATE_SUBJECT = "Your offer to join {{company_name}} as {{designation}}"

DEFAULT_TEMPLATE_BODY = """Dear {{candidate_name}},

We are delighted to offer you the position of {{designation}} at {{company_name}}. We were genuinely impressed by your background and are confident you will do excellent work with our team.

The role is {{employment_type}} and based in {{location}}. You will report to {{manager_name}} and your anticipated start date is {{start_date}}.

Your total annual compensation would be {{annual_ctc}} per annum, comprising a base salary of {{base_pay}} and fixed allowances of {{allowances}}. Full details of your compensation are set out in the summary below.

This offer remains open until {{expiry_date}}. Employment is subject to satisfactory verification of your identity, right to work, and background references.

We would be delighted to have you with us. Please confirm your acceptance by signing and returning this letter.

With best regards,

{{sender_name}}
{{sender_designation}}
{{company_name}}"""


class OfferRenderError(ValueError):
    """Raised when a template cannot be rendered safely."""

    def __init__(self, message: str, unresolved: Sequence[str] = ()):
        super().__init__(message)
        self.unresolved = list(unresolved)


# ── Formatting helpers ──────────────────────────────────────────────────
def _dec(value: Any) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        logger.warning("Non-numeric offer value %r coerced to 0", value)
        return ZERO


def _q(value: Any) -> Decimal:
    return _dec(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def format_money(value: Any, currency: str = DEFAULT_CURRENCY) -> str:
    amount = _q(value)
    try:
        body = format(amount, ",.2f")
    except (ValueError, InvalidOperation):
        body = f"{amount:.2f}"
    return f"{currency} {body}"


def long_date(value: Optional[datetime]) -> str:
    return value.strftime("%d %B %Y") if value else "—"


def _resolve_brand_color(value: Optional[str]):
    if value and re.match(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})$", value.strip()):
        try:
            return colors.HexColor(value.strip())
        except (ValueError, TypeError):
            pass
    return colors.HexColor("#1F3A5F")


# ── Merge tags ──────────────────────────────────────────────────────────
def build_context(
    *,
    offer: OfferLetter,
    organization: Organization,
    candidate: Candidate,
    application: Optional[JobApplication] = None,
    sender: Any = None,
    manager_name: Optional[str] = None,
) -> Dict[str, str]:
    """Assemble the tag -> value map for one offer."""
    job = getattr(application, "job_posting", None) if application else None
    base = _q(offer.base_pay)
    allowances = _q(offer.allowances)
    ctc = _q(offer.annual_ctc) or (base + allowances)

    expiry = offer.expiry_date or (
        _aware(offer.offer_date) + timedelta(days=offer.expires_in_days or DEFAULT_EXPIRY_DAYS)
    )

    sender_role = getattr(getattr(sender, "role", None), "name", None)
    sender_name = getattr(sender, "full_name", None)

    context: Dict[str, str] = {
        "candidate_name": candidate.full_name or "Candidate",
        "candidate_email": candidate.email or "",
        "job_title": offer.designation or (getattr(job, "title", "") if job else "") or "the advertised role",
        "designation": offer.designation or "the advertised role",
        "employment_type": offer.employment_type or "Full-time",
        "location": offer.location or (getattr(job, "location", "") if job else "") or "as arranged",
        "company_name": organization.name or "",
        "company_legal_id": organization.legal_id or "",
        "base_pay": format_money(base, offer.currency),
        "allowances": format_money(allowances, offer.currency),
        "annual_ctc": format_money(ctc, offer.currency),
        "currency": offer.currency or DEFAULT_CURRENCY,
        "offer_date": long_date(offer.offer_date),
        "start_date": long_date(offer.start_date),
        "expiry_date": long_date(expiry),
        "expires_in_days": str(offer.expires_in_days or DEFAULT_EXPIRY_DAYS),
        "sender_name": sender_name or "The Hiring Team",
        "sender_designation": sender_role or "Hiring Manager",
        "manager_name": manager_name or sender_name or "The Hiring Manager",
    }
    return context


def render_tags(
    body: str,
    context: Dict[str, str],
    *,
    strict: bool = True,
    prefix: str = "",
) -> Tuple[str, List[str]]:
    """
    Substitute {{tag}} placeholders in one pass.

    Returns the rendered text and the tags that had no value. Values are
    XML-escaped because the result is embedded in a ReportLab Paragraph.
    Unknown tags are left untouched so a template author can see them, and
    `strict` additionally refuses to produce a document containing them.
    """
    unresolved: List[str] = []

    def substitute(match: "re.Match[str]") -> str:
        key = match.group(1)
        if key in context:
            # re.sub does not rescan replacements, so a value containing
            # {{...}} is never re-expanded.
            value = context[key]
            return "" if value is None else escape(str(value))
        unresolved.append(key)
        return match.group(0)

    rendered = TAG_RE.sub(substitute, body or "")

    if strict and unresolved:
        raise OfferRenderError(
            "Template contains unresolved merge tags: "
            + ", ".join(sorted(f"{{{{{tag}}}}}" for tag in unresolved)),
            unresolved=unresolved,
        )
    if prefix and unresolved:
        logger.warning("Unresolved offer tags in %s: %s", prefix, ", ".join(unresolved))

    return rendered, unresolved


def available_tags() -> List[str]:
    """Tag names an administrator can use in a template body."""
    return [
        "candidate_name", "candidate_email", "job_title", "designation",
        "employment_type", "location", "company_name", "company_legal_id",
        "base_pay", "allowances", "annual_ctc", "currency",
        "offer_date", "start_date", "expiry_date", "expires_in_days",
        "sender_name", "sender_designation", "manager_name",
    ]


# ── PDF rendering ───────────────────────────────────────────────────────
def _body_paragraphs(body: str) -> List[str]:
    """Split a template body on blank lines into paragraphs."""
    blocks: List[str] = []
    current: List[str] = []

    for raw_line in (body or "").splitlines():
        line = raw_line.rstrip()
        if not line:
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def build_offer_letter_pdf(
    *,
    offer: OfferLetter,
    organization: Organization,
    candidate: Candidate,
    application: Optional[JobApplication] = None,
    template: Optional[OfferTemplate] = None,
    context: Optional[Dict[str, str]] = None,
) -> bytes:
    """Render the offer letter to PDF bytes."""
    if context is None:
        context = build_context(
            offer=offer,
            organization=organization,
            candidate=candidate,
            application=application,
        )

    body_source = (template.body if template else DEFAULT_TEMPLATE_BODY) or DEFAULT_TEMPLATE_BODY
    subject_source = (template.subject if template else None) or DEFAULT_TEMPLATE_SUBJECT

    # Fail before building anything if the template cannot be rendered.
    rendered_body, _ = render_tags(
        body_source, context, strict=True,
        prefix=(template.name if template else "built-in default template"),
    )
    rendered_subject, _ = render_tags(subject_source, context, strict=True)

    brand = _resolve_brand_color(getattr(organization, "primary_color", None))
    muted = colors.HexColor("#5A6672")
    rule = colors.HexColor("#D6DCE4")

    styles = getSampleStyleSheet()
    subject_style = ParagraphStyle(
        "OfferSubject", parent=styles["Heading1"], fontSize=13, leading=17,
        textColor=brand, alignment=TA_LEFT, spaceAfter=8,
    )
    org_style = ParagraphStyle(
        "OfferOrg", parent=styles["Normal"], fontSize=9.5, leading=12, textColor=muted,
    )
    body_style = ParagraphStyle(
        "OfferBody", parent=styles["Normal"], fontSize=10, leading=15.5, spaceAfter=9,
    )
    section_style = ParagraphStyle(
        "OfferSection", parent=styles["Heading2"], fontSize=10, leading=13,
        textColor=brand, spaceBefore=8, spaceAfter=4,
    )
    cell = ParagraphStyle("OfferCell", parent=styles["Normal"], fontSize=9, leading=12)
    cell_bold = ParagraphStyle("OfferCellBold", parent=cell, fontName="Helvetica-Bold")
    label = ParagraphStyle("OfferLabel", parent=cell, textColor=muted)
    value = ParagraphStyle("OfferValue", parent=cell, fontName="Helvetica-Bold")
    fine = ParagraphStyle(
        "OfferFine", parent=styles["Normal"], fontSize=7.5, leading=10, textColor=muted,
    )

    import io

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=rendered_subject,
        author=getattr(organization, "name", "") or "Offer",
        subject="Offer of employment",
    )

    story: List[Any] = []

    # ── Letterhead ──────────────────────────────────────────────────────
    story.append(Paragraph(escape(getattr(organization, "name", "") or ""), subject_style))
    identifier = getattr(organization, "legal_id", None)
    if identifier:
        story.append(Paragraph(f"Registered office / identification: {escape(str(identifier))}", org_style))
    story.append(Spacer(1, 5))
    story.append(Table([[""]], colWidths=[174 * mm], rowHeights=[1.4], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), brand),
    ])))
    story.append(Spacer(1, 10))

    # ── Recipient + subject ─────────────────────────────────────────────
    story.append(Paragraph(f"Date: {escape(long_date(offer.offer_date))}", org_style))
    story.append(Spacer(1, 7))
    story.append(Paragraph(escape(rendered_subject), subject_style))

    recipient = [
        [Paragraph(escape(candidate.full_name or "Candidate"), cell_bold)],
        [Paragraph(escape(candidate.email or ""), cell)],
    ]
    story.append(KeepTogether([Table(recipient, colWidths=[174 * mm], style=TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))]))
    story.append(Spacer(1, 8))

    # ── Body ────────────────────────────────────────────────────────────
    for block in _body_paragraphs(rendered_body):
        # Newlines inside a block are preserved as soft line breaks; the text
        # is already escaped by render_tags.
        story.append(Paragraph(block.replace("\n", "<br/>"), body_style))

    # ── Compensation summary ────────────────────────────────────────────
    base = _q(offer.base_pay)
    allowances = _q(offer.allowances)
    ctc = _q(offer.annual_ctc) or (base + allowances)

    story.append(Paragraph("Compensation summary", section_style))
    rows = [
        [Paragraph("Component", cell_bold), Paragraph(f"Annual ({escape(offer.currency or DEFAULT_CURRENCY)})", cell_bold)],
        [Paragraph("Base salary", cell), Paragraph(escape(format_money(base, offer.currency)), cell)],
        [Paragraph("Fixed allowances", cell), Paragraph(escape(format_money(allowances, offer.currency)), cell)],
        [Paragraph("Total annual compensation", cell_bold), Paragraph(escape(format_money(ctc, offer.currency)), cell_bold)],
        [Paragraph("Employment type", cell), Paragraph(escape(offer.employment_type or "Full-time"), cell)],
        [Paragraph("Start date", cell), Paragraph(escape(long_date(offer.start_date)), cell)],
        [Paragraph("Offer valid until", cell), Paragraph(escape(context.get("expiry_date", "—")), cell)],
    ]
    summary = Table(rows, colWidths=[104 * mm, 70 * mm], repeatRows=1)
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F4F8")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, brand),
        ("LINEABOVE", (0, -4), (-1, -4), 0.6, colors.HexColor("#D6DCE4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(summary)

    # ── Acceptance ──────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(Paragraph("Acceptance", section_style))
    story.append(Paragraph(
        "Please sign below to confirm your acceptance of this offer. "
        "Signature confirms your agreement to the terms described above.",
        cell,
    ))
    story.append(Spacer(1, 10))
    story.append(Table([
        [Paragraph("Signature", label), Paragraph("Date", label)],
        [Paragraph("<br/><br/>______________________________", cell),
         Paragraph("____________________", cell)],
    ], colWidths=[120 * mm, 54 * mm], style=TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
    ])))

    story.append(Spacer(1, 14))
    story.append(Table([[""]], colWidths=[174 * mm], rowHeights=[0.6], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), rule),
    ])))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Offer reference {escape(str(offer.id) if offer.id else 'draft')} · "
        "This is a computer-generated document. It becomes binding once signed "
        "by both the candidate and the employer.",
        fine,
    ))

    doc.build(story)
    return buffer.getvalue()


# ── Persistence ─────────────────────────────────────────────────────────
def _aware(value: Optional[datetime]) -> datetime:
    """Treat naive timestamps as UTC so arithmetic never raises."""
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def expiry_for(offer: OfferLetter) -> datetime:
    if offer.expiry_date:
        return _aware(offer.expiry_date)
    return _aware(offer.offer_date) + timedelta(days=offer.expires_in_days or DEFAULT_EXPIRY_DAYS)


def is_expired(offer: OfferLetter, now: Optional[datetime] = None) -> bool:
    """An unanswered offer lapses once its response window closes."""
    if offer.status not in (STATUS_SENT, STATUS_DRAFT):
        return False
    return (now or datetime.now(timezone.utc)) > expiry_for(offer)


def effective_status(offer: OfferLetter, now: Optional[datetime] = None) -> str:
    return STATUS_EXPIRED if is_expired(offer, now) else offer.status


def ensure_default_template(db: Session, org_id) -> OfferTemplate:
    """
    Return the tenant's default template, provisioning one if absent.

    Every tenant gets a usable starter template so offer generation works
    without the administrator writing legal wording first.
    """
    template = (
        db.query(OfferTemplate)
        .filter(
            OfferTemplate.organization_id == org_id,
            OfferTemplate.is_default.is_(True),
            OfferTemplate.is_active.is_(True),
        )
        .first()
    )
    if template:
        return template

    organization = db.query(Organization).filter(Organization.id == org_id).first()
    name = DEFAULT_TEMPLATE_NAME
    existing_name = (
        db.query(OfferTemplate)
        .filter(OfferTemplate.organization_id == org_id, OfferTemplate.name == name)
        .first()
    )
    if existing_name:
        existing_name.is_default = True
        existing_name.is_active = True
        db.commit()
        db.refresh(existing_name)
        return existing_name

    template = OfferTemplate(
        organization_id=org_id,
        name=name,
        subject=DEFAULT_TEMPLATE_SUBJECT,
        body=DEFAULT_TEMPLATE_BODY,
        is_default=True,
        is_active=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    logger.info("Provisioned default offer template for org %s (%s)", org_id, getattr(organization, "name", ""))
    return template


def generate_offer_letter_pdf(
    db: Session,
    offer: OfferLetter,
    *,
    sender: Any = None,
    regenerate: bool = False,
) -> OfferLetter:
    """Render and persist the offer letter PDF."""
    if offer.file_url and not regenerate:
        return offer

    organization = db.query(Organization).filter(Organization.id == offer.organization_id).first()
    if organization is None:
        raise ValueError(f"Organization {offer.organization_id} not found")

    candidate = db.query(Candidate).filter(Candidate.id == offer.candidate_id).first()
    if candidate is None:
        raise ValueError(f"Candidate {offer.candidate_id} not found")

    application = None
    if offer.application_id:
        application = (
            db.query(JobApplication).filter(JobApplication.id == offer.application_id).first()
        )
    template = None
    if offer.template_id:
        template = db.query(OfferTemplate).filter(OfferTemplate.id == offer.template_id).first()

    context = build_context(
        offer=offer,
        organization=organization,
        candidate=candidate,
        application=application,
        sender=sender,
    )

    pdf_bytes = build_offer_letter_pdf(
        offer=offer,
        organization=organization,
        candidate=candidate,
        application=application,
        template=template,
        context=context,
    )

    # Deterministic id keeps regeneration idempotent on disk.
    file_id = f"offer-{offer.organization_id}-{offer.id}.pdf"
    storage_path = store_pdf(
        file_id, pdf_bytes, org_id=offer.organization_id, subdir=SUBDIR_OFFER_LETTERS
    )

    offer.file_url = storage_path
    offer.pdf_sha256 = sha256_hex(pdf_bytes)
    db.commit()
    db.refresh(offer)
    logger.info("Offer letter generated offer=%s sha=%s", offer.id, offer.pdf_sha256[:12])
    return offer


def read_offer_letter_bytes(offer: OfferLetter) -> bytes:
    return read_pdf(offer.file_url)
