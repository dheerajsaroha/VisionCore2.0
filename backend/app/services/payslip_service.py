"""
Payslip PDF generation.

Renders a statutory payslip document for a single payroll row and persists the
result through the configured storage provider, so a payslip remains
retrievable years later (unlike the in-memory `FileService` registry, which is
not durable and is therefore not used here).

`build_payslip_pdf` is deliberately free of database access so the layout can
be unit tested directly; `generate_payslip` handles the persistence concerns.
"""
from __future__ import annotations

import io
import logging
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
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
    BankAccount,
    EmploymentRecord,
    Organization,
    Payroll,
    PayrollLineItem,
    Payslip,
    User,
)
from app.services.pdf_documents import (
    PDFStorageError,
    SUBDIR_PAYSLIPS,
    read_pdf,
    sha256_hex,
    store_pdf,
)

# Backwards-compatible alias; the guard is shared with offer letters.
PayslipStorageError = PDFStorageError

logger = logging.getLogger(__name__)

MONTH_NAMES = (
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

EARNING_TYPES = {"earning"}
DEDUCTION_TYPES = {"deduction", "statutory", "tax"}

# Last-resort fallback only. A payroll row snapshots its own currency; this
# matches the statutory engine's default so a row without a snapshot is not
# labelled with a currency its figures were never computed in.
DEFAULT_CURRENCY = "INR"


_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def _to_decimal(value: Any) -> Decimal:
    """Coerce a DB numeric / float / str to Decimal without float drift."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        logger.warning("Non-numeric monetary value %r coerced to 0", value)
        return Decimal("0")


def _quantize(value: Decimal) -> Decimal:
    return _to_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_money(value: Any, currency: str = "USD") -> str:
    """Render a monetary amount with thousands separators and a currency code."""
    amount = _quantize(_to_decimal(value))
    try:
        symbol = format(amount, ",.2f")
    except (ValueError, InvalidOperation):
        symbol = f"{amount:.2f}"
    return f"{currency} {symbol}"


def period_label(month: int, year: int) -> str:
    """Human-readable period, e.g. 'March 2026'."""
    name = MONTH_NAMES[month] if 0 < month <= 12 else str(month)
    return f"{name} {year}"


def _iso_period(month: int, year: int) -> str:
    return f"{year:04d}-{month:02d}"


def _resolve_brand_color(value: Optional[str]):
    """Parse an organization brand colour, falling back to a safe navy."""
    if value and _HEX_COLOR.match(value.strip()):
        try:
            return colors.HexColor(value.strip())
        except (ValueError, TypeError):
            pass
    return colors.HexColor("#1F3A5F")


def _mask(value: Optional[str]) -> str:
    """Render a bank/account identifier masked, never in full."""
    if not value:
        return "—"
    text = str(value).strip()
    if len(text) <= 4:
        return "•" * len(text)
    return "•" * (len(text) - 4) + text[-4:]


def _split_line_items(
    line_items: Optional[Sequence[PayrollLineItem]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Partition line items into earnings and deductions, preserving order.

    The payroll engine stores deductions as negative amounts, but a payslip
    itemises them in a section already labelled "Deductions", so the magnitude
    is what belongs there; keeping the sign would print "-1,800.00" and invert
    the totals shown to the employee.
    """
    earnings: List[Dict[str, Any]] = []
    deductions: List[Dict[str, Any]] = []
    for item in line_items or []:
        kind = (getattr(item, "component_type", "") or "").strip().lower()
        amount = _to_decimal(getattr(item, "amount", 0))
        entry = {
            "name": getattr(item, "component_name", "") or "Unnamed",
            "amount": abs(amount) if kind in DEDUCTION_TYPES else amount,
            "description": getattr(item, "description", None),
        }
        if kind in DEDUCTION_TYPES:
            deductions.append(entry)
        elif kind in EARNING_TYPES or not kind:
            # An unrecognised type is surfaced as an earning rather than
            # silently dropped, so payroll never under-reports pay.
            earnings.append(entry)
    return earnings, deductions


def build_payslip_pdf(
    *,
    organization: Organization,
    employee: User,
    payroll: Payroll,
    line_items: Optional[Sequence[PayrollLineItem]] = None,
    designation: Optional[str] = None,
    department: Optional[str] = None,
    bank: Optional[BankAccount] = None,
    currency: str = "USD",
    generated_at: Optional[datetime] = None,
) -> bytes:
    """
    Render a payslip to PDF bytes.

    The document is the employee-facing artefact: it states gross, deductions
    and net pay, and itemises every component supplied by the payroll engine.
    """
    generated_at = generated_at or datetime.now(timezone.utc)
    brand = _resolve_brand_color(getattr(organization, "primary_color", None))
    muted = colors.HexColor("#5A6672")
    rule = colors.HexColor("#D6DCE4")

    base = _to_decimal(payroll.base_salary)
    payroll_deductions = _to_decimal(payroll.deductions)
    reimbursements = _to_decimal(payroll.reimbursements_total)
    total = _to_decimal(payroll.total_salary)

    earnings, deductions = _split_line_items(line_items)

    # Fall back to the payroll row when no line items were produced, so the
    # payslip is never blank for a valid payroll record.
    if not earnings:
        earnings = [{"name": "Basic Salary", "amount": base, "description": None}]
    if not deductions and payroll_deductions > 0:
        deductions = [{"name": "Total Deductions", "amount": payroll_deductions, "description": None}]

    earnings_total = sum((e["amount"] for e in earnings), Decimal("0")) or base
    if reimbursements > 0:
        earnings.append({
            "name": "Reimbursements",
            "amount": reimbursements,
            "description": None,
        })
        earnings_total += reimbursements
    deductions_total = sum((d["amount"] for d in deductions), Decimal("0")) or payroll_deductions
    net_pay = _quantize(total)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PayslipTitle", parent=styles["Heading1"], fontSize=15, leading=19,
        textColor=brand, spaceAfter=0,
    )
    org_style = ParagraphStyle(
        "PayslipOrg", parent=styles["Normal"], fontSize=10, leading=13, textColor=muted,
    )
    section_style = ParagraphStyle(
        "PayslipSection", parent=styles["Heading2"], fontSize=9.5, leading=12,
        textColor=brand, spaceBefore=8, spaceAfter=3,
    )
    cell = ParagraphStyle("PayslipCell", parent=styles["Normal"], fontSize=8.5, leading=11)
    cell_right = ParagraphStyle("PayslipCellRight", parent=cell, alignment=TA_RIGHT)
    cell_bold = ParagraphStyle("PayslipCellBold", parent=cell, fontName="Helvetica-Bold")
    cell_bold_right = ParagraphStyle("PayslipCellBoldRight", parent=cell_right, fontName="Helvetica-Bold")
    label_style = ParagraphStyle("PayslipLabel", parent=cell, textColor=muted, fontSize=8)
    value_style = ParagraphStyle("PayslipValue", parent=cell, fontName="Helvetica-Bold")
    footer_style = ParagraphStyle(
        "PayslipFooter", parent=styles["Normal"], fontSize=7, leading=9, textColor=muted,
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=14 * mm, bottomMargin=16 * mm,
        title=f"Payslip {period_label(payroll.month, payroll.year)} - {employee.full_name}",
        author=getattr(organization, "name", "VisionCore"),
        subject="Salary payslip",
    )

    story: List[Any] = []

    # ── Header ────────────────────────────────────────────────────────────
    story.append(Paragraph("PAYSLIP", title_style))
    story.append(Paragraph(
        f"{getattr(organization, 'name', '—')}"
        + (f" &middot; {organization.legal_id}" if getattr(organization, "legal_id", None) else ""),
        org_style,
    ))
    story.append(Spacer(1, 5))
    story.append(Table([[""]], colWidths=[178 * mm], rowHeights=[1.4], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), brand),
    ])))
    story.append(Spacer(1, 7))

    # ── Employee / period block ───────────────────────────────────────────
    employee_name = getattr(employee, "full_name", None) or "—"
    employee_id = getattr(employee, "id", None)
    email = getattr(employee, "email", None) or "—"
    period = period_label(payroll.month, payroll.year)

    details = [
        [Paragraph("Employee", label_style), Paragraph(employee_name, value_style),
         Paragraph("Pay Period", label_style), Paragraph(period, value_style)],
        [Paragraph("Employee ID", label_style), Paragraph(str(employee_id), cell),
         Paragraph("Payroll Status", label_style),
         Paragraph(str(getattr(payroll, "status", "—")).title(), cell)],
        [Paragraph("Designation", label_style), Paragraph(designation or "—", cell),
         Paragraph("Department", label_style), Paragraph(department or "—", cell)],
        [Paragraph("Email", label_style), Paragraph(email, cell),
         Paragraph("Currency", label_style), Paragraph(currency, cell)],
    ]
    story.append(Table(details, colWidths=[26 * mm, 62 * mm, 28 * mm, 62 * mm], style=TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ])))

    # ── Earnings / deductions ────────────────────────────────────────────
    def _component_table(entries: List[Dict[str, Any]], total_value: Decimal) -> Table:
        rows: List[List[Any]] = [[
            Paragraph("Component", cell_bold),
            Paragraph("Amount (" + currency + ")", cell_bold_right),
        ]]
        for entry in entries:
            label = entry["name"]
            if entry.get("description"):
                label += f"<br/><font size=7 color='#5A6672'>{entry['description']}</font>"
            rows.append([
                Paragraph(label, cell),
                Paragraph(format_money(entry["amount"]), cell_right),
            ])
        rows.append([
            Paragraph("Total", cell_bold),
            Paragraph(format_money(total_value), cell_bold_right),
        ])
        table = Table(rows, colWidths=[126 * mm, 52 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F4F8")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, brand),
            ("LINEABOVE", (0, -1), (-1, -1), 0.6, rule),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table

    earnings_block: List[Any] = [Paragraph("Earnings", section_style),
                                 _component_table(earnings, _quantize(earnings_total))]
    if deductions:
        earnings_block += [Spacer(1, 3),
                           Paragraph("Deductions", section_style),
                           _component_table(deductions, _quantize(deductions_total))]
    story.append(KeepTogether(earnings_block))

    # ── Net pay summary ───────────────────────────────────────────────────
    summary_rows = [
        [Paragraph("Gross Pay", cell), Paragraph(format_money(earnings_total), cell_bold_right)],
        [Paragraph("Total Deductions", cell), Paragraph(f"({format_money(deductions_total)})", cell_bold_right)],
    ]
    if reimbursements > 0:
        summary_rows.insert(1, [Paragraph("Reimbursements", cell),
                                Paragraph(format_money(reimbursements), cell_bold_right)])
    summary_rows.append([
        Paragraph("Net Pay", value_style),
        Paragraph(format_money(net_pay), ParagraphStyle(
            "Net", parent=cell_bold_right, fontSize=11, textColor=brand)),
    ])
    story.append(Spacer(1, 7))
    story.append(Table(summary_rows, colWidths=[126 * mm, 52 * mm], style=TableStyle([
        ("BACKGROUND", (0, -1), (-1, -1), brand),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("LINEABOVE", (0, -1), (-1, -1), 0.6, brand),
    ])))

    # ── Payment details ───────────────────────────────────────────────────
    if bank is not None:
        story.append(Spacer(1, 7))
        story.append(Paragraph("Payment Details", section_style))
        story.append(Table([
            [Paragraph("Account Holder", label_style),
             Paragraph(getattr(bank, "account_number_masked", "—") or "—", cell),
             Paragraph("Bank", label_style),
             Paragraph(getattr(bank, "bank_name", "—") or "—", cell)],
            [Paragraph("Account Number", label_style),
             Paragraph(_mask(getattr(bank, "account_number_masked", None)), cell),
             Paragraph("Reference", label_style),
             Paragraph(_iso_period(payroll.month, payroll.year), cell)],
        ], colWidths=[26 * mm, 62 * mm, 28 * mm, 62 * mm], style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ])))

    # ── Footer ────────────────────────────────────────────────────────────
    stamp = generated_at.strftime("%d %b %Y %H:%M UTC")
    story.append(Spacer(1, 9))
    story.append(Paragraph(
        "This is a computer-generated payslip and does not require a signature. "
        f"Generated {stamp}. Figures are a point-in-time record; contact your "
        "payroll administrator if any value appears incorrect.",
        footer_style,
    ))

    doc.build(story)
    return buffer.getvalue()


# ── Persistence ──────────────────────────────────────────────────────────

def resolve_currency(
    db: Session,
    payroll: Payroll,
    override: Optional[str] = None,
) -> str:
    """
    Resolve the ISO 4217 currency code to print on a payslip.

    Read from the snapshot taken on the payroll row when it was calculated, so
    the printed currency always matches the currency its deductions were
    computed in. Falling back to a hard-coded default would label an
    India-computed payslip "USD", which is wrong on a legal document.

    An explicit `override` still wins.
    """
    if override:
        return str(override).strip().upper()[:3]
    return (getattr(payroll, "currency", None) or DEFAULT_CURRENCY).upper()[:3]


def generate_payslip(
    db: Session,
    payroll: Payroll,
    *,
    generated_by_user_id: Optional[int] = None,
    regenerate: bool = False,
) -> Payslip:
    """
    Render and persist the payslip for `payroll`.

    Idempotent: one payslip per payroll row (enforced by uq_payslip_payroll).
    An existing payslip is returned untouched unless `regenerate` is set.
    """
    existing = db.query(Payslip).filter(Payslip.payroll_id == payroll.id).first()
    if existing and not regenerate:
        return existing

    organization = db.query(Organization).filter(Organization.id == payroll.org_id).first()
    if organization is None:
        raise ValueError(f"Organization {payroll.org_id} not found for payroll {payroll.id}")

    employee = db.query(User).filter(User.id == payroll.user_id).first()
    if employee is None:
        raise ValueError(f"Employee {payroll.user_id} not found for payroll {payroll.id}")

    line_items = (
        db.query(PayrollLineItem)
        .filter(PayrollLineItem.payroll_id == payroll.id)
        .order_by(PayrollLineItem.id)
        .all()
    )

    employment = (
        db.query(EmploymentRecord)
        .filter(EmploymentRecord.user_id == payroll.user_id)
        .order_by(EmploymentRecord.id.desc())
        .first()
    )
    bank = (
        db.query(BankAccount)
        .filter(BankAccount.user_id == payroll.user_id)
        .order_by(BankAccount.id.desc())
        .first()
    )

    designation = getattr(employment, "designation", None)
    department = getattr(getattr(employee, "department", None), "name", None)
    currency = resolve_currency(db, payroll)
    generated_at = datetime.now(timezone.utc)

    pdf_bytes = build_payslip_pdf(
        organization=organization,
        employee=employee,
        payroll=payroll,
        line_items=line_items,
        designation=designation,
        department=department,
        bank=bank,
        currency=currency,
        generated_at=generated_at,
    )
    digest = sha256_hex(pdf_bytes)

    # Deterministic id keeps regeneration idempotent on disk.
    file_id = f"payslip-{payroll.org_id}-{payroll.id}.pdf"
    storage_path = store_pdf(
        file_id, pdf_bytes, org_id=payroll.org_id, subdir=SUBDIR_PAYSLIPS
    )

    base = _to_decimal(payroll.base_salary)
    deductions = _to_decimal(payroll.deductions)
    reimbursements = _to_decimal(payroll.reimbursements_total)
    gross = base + reimbursements

    if existing:
        existing.file_url = storage_path
        existing.pdf_sha256 = digest
        existing.period_label = _iso_period(payroll.month, payroll.year)
        existing.currency = currency
        existing.gross_salary = _quantize(gross)
        existing.total_deductions = _quantize(deductions)
        existing.net_pay = _quantize(payroll.total_salary)
        existing.generated_at = generated_at
        existing.generated_by_user_id = generated_by_user_id
        record = existing
    else:
        record = Payslip(
            payroll_id=payroll.id,
            org_id=payroll.org_id,
            user_id=payroll.user_id,
            file_url=storage_path,
            pdf_sha256=digest,
            period_label=_iso_period(payroll.month, payroll.year),
            currency=currency,
            gross_salary=_quantize(gross),
            total_deductions=_quantize(deductions),
            net_pay=_quantize(payroll.total_salary),
            generated_at=generated_at,
            generated_by_user_id=generated_by_user_id,
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    logger.info("Payslip generated payroll=%s path=%s sha=%s", payroll.id, storage_path, digest[:12])
    return record


def get_or_generate_payslip(db: Session, payroll: Payroll) -> Payslip:
    """Return the payslip for a payroll row, rendering it on first access."""
    existing = db.query(Payslip).filter(Payslip.payroll_id == payroll.id).first()
    return existing if existing else generate_payslip(db, payroll)


def read_payslip_bytes(payslip: Payslip) -> bytes:
    """Read the stored PDF via the shared, storage-confined reader."""
    return read_pdf(payslip.file_url)
