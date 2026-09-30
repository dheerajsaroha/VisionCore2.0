"""
Offer letters: templates, generation, and the candidate response lifecycle.

Gated on the `recruitment` feature like the rest of the hiring module, and
scoped to the caller's organisation. Reads are open to anyone on the hiring
team; template edits, generation, and state transitions require the
`recruitment.manage` permission.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.db.models.all_models import (
    Candidate,
    JobApplication,
    OfferLetter,
    OfferTemplate,
    User,
)
from app.services import offer_letter_service
from app.services.offer_letter_service import OfferRenderError
from app.services.pdf_documents import PDFStorageError

router = APIRouter(dependencies=[Depends(deps.require_feature("recruitment"))])
logger = logging.getLogger(__name__)

# Built once and reused so the exact dependency object is addressable (tests
# override `offer_letters.MANAGE`; calling the factory per route would produce a
# different callable each time and make the override key unmatchable).
MANAGE = deps.require_permission("recruitment.manage")


# ── Schemas ─────────────────────────────────────────────────────────────
class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1)
    subject: Optional[str] = Field(default=None, max_length=200)
    is_default: bool = False


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    body: Optional[str] = Field(default=None, min_length=1)
    subject: Optional[str] = Field(default=None, max_length=200)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class OfferCreate(BaseModel):
    candidate_id: int
    application_id: Optional[int] = None
    job_posting_id: Optional[int] = None
    template_id: Optional[int] = None
    designation: str = Field(min_length=1, max_length=150)
    employment_type: str = Field(default="Full-time", max_length=50)
    location: Optional[str] = Field(default=None, max_length=100)
    currency: str = Field(default="USD", min_length=3, max_length=8)
    base_pay: float = Field(ge=0)
    allowances: float = Field(default=0.0, ge=0)
    annual_ctc: Optional[float] = Field(default=None, ge=0)
    start_date: Optional[str] = None
    expires_in_days: int = Field(default=7, ge=1, le=90)

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("expires_in_days")
    @classmethod
    def _bound_window(cls, value: int) -> int:
        if value > offer_letter_service.MAX_EXPIRY_DAYS:
            raise ValueError(
                f"expires_in_days must not exceed {offer_letter_service.MAX_EXPIRY_DAYS}"
            )
        return value


class OfferRespond(BaseModel):
    accepted: bool
    reason: Optional[str] = Field(default=None, max_length=2000)


class TemplateOut(BaseModel):
    id: int
    name: str
    subject: Optional[str]
    body: str
    is_default: bool
    is_active: bool


class OfferOut(BaseModel):
    id: int
    candidate_id: int
    application_id: Optional[int]
    job_posting_id: Optional[int]
    template_id: Optional[int]
    status: str
    designation: str
    employment_type: str
    location: Optional[str]
    currency: str
    base_pay: float
    allowances: float
    annual_ctc: float
    offer_date: str
    start_date: str
    expiry_date: Optional[str]
    expires_in_days: int
    sent_at: Optional[str]
    responded_at: Optional[str]
    decline_reason: Optional[str]
    pdf_sha256: Optional[str]
    download_url: Optional[str] = None


def _serialize(offer: OfferLetter) -> Dict[str, Any]:
    return {
        "id": offer.id,
        "candidate_id": offer.candidate_id,
        "application_id": offer.application_id,
        "job_posting_id": offer.job_posting_id,
        "template_id": offer.template_id,
        "status": offer_letter_service.effective_status(offer),
        "designation": offer.designation,
        "employment_type": offer.employment_type,
        "location": offer.location,
        "currency": offer.currency,
        "base_pay": float(offer.base_pay),
        "allowances": float(offer.allowances),
        "annual_ctc": float(offer.annual_ctc),
        "offer_date": offer.offer_date.isoformat() if offer.offer_date else None,
        "start_date": offer.start_date.isoformat() if offer.start_date else None,
        "expiry_date": offer_letter_service.expiry_for(offer).isoformat(),
        "expires_in_days": offer.expires_in_days,
        "sent_at": offer.sent_at.isoformat() if offer.sent_at else None,
        "responded_at": offer.responded_at.isoformat() if offer.responded_at else None,
        "decline_reason": offer.decline_reason,
        "pdf_sha256": offer.pdf_sha256,
        "download_url": f"/api/v1/recruitment/offer-letters/{offer.id}/download"
        if offer.file_url else None,
    }


def _load_offer(db: Session, offer_id: int, current_user: User) -> OfferLetter:
    offer = (
        db.query(OfferLetter)
        .filter(
            OfferLetter.id == offer_id,
            OfferLetter.organization_id == current_user.org_id,
        )
        .first()
    )
    if not offer:
        raise HTTPException(status_code=404, detail="Offer letter not found")
    return offer


def _load_template(db: Session, template_id: int, current_user: User) -> OfferTemplate:
    template = (
        db.query(OfferTemplate)
        .filter(
            OfferTemplate.id == template_id,
            OfferTemplate.organization_id == current_user.org_id,
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Offer template not found")
    return template


# ── Merge tag discovery ─────────────────────────────────────────────────
@router.get("/offer-templates/tags")
def list_tags() -> Dict[str, Any]:
    """
    Merge tags available in a template body.

    Advertised in the UI so an administrator can build a template without
    guessing tag names, and so a typo can be spotted before sending a legally
    binding document.
    """
    return {
        "tags": offer_letter_service.available_tags(),
        "syntax": "{{tag_name}}",
    }


# ── Templates ───────────────────────────────────────────────────────────
@router.get("/offer-templates", response_model=List[TemplateOut])
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    return (
        db.query(OfferTemplate)
        .filter(OfferTemplate.organization_id == current_user.org_id)
        .order_by(OfferTemplate.name)
        .all()
    )


@router.post("/offer-templates", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(MANAGE),
):
    # Only one template may be the default, so clear the incumbent first.
    if payload.is_default:
        db.query(OfferTemplate).filter(
            OfferTemplate.organization_id == current_user.org_id,
            OfferTemplate.is_default.is_(True),
        ).update({"is_default": False}, synchronize_session=False)

    template = OfferTemplate(
        organization_id=current_user.org_id,
        name=payload.name.strip(),
        subject=payload.subject,
        body=payload.body,
        is_default=payload.is_default,
        is_active=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.patch("/offer-templates/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: int,
    payload: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(MANAGE),
):
    template = _load_template(db, template_id, current_user)

    if payload.is_default:
        db.query(OfferTemplate).filter(
            OfferTemplate.organization_id == current_user.org_id,
            OfferTemplate.id != template_id,
            OfferTemplate.is_default.is_(True),
        ).update({"is_default": False}, synchronize_session=False)

    if payload.name is not None:
        template.name = payload.name.strip()
    if payload.body is not None:
        template.body = payload.body
    if payload.subject is not None:
        template.subject = payload.subject
    if payload.is_default is not None:
        template.is_default = payload.is_default
    if payload.is_active is not None:
        template.is_active = payload.is_active

    db.commit()
    db.refresh(template)
    return template


@router.delete("/offer-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(MANAGE),
):
    """
    Retire a template.

    Soft delete: offers already generated from it reference the row and must
    keep rendering, and deleting would cascade a gap into past hiring records.
    """
    template = _load_template(db, template_id, current_user)
    template.is_active = False
    template.is_default = False
    db.commit()


@router.post("/offer-templates/{template_id}/preview")
def preview_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Render a template against sample data to check tags before use."""
    template = _load_template(db, template_id, current_user)
    candidate = (
        db.query(Candidate)
        .filter(Candidate.organization_id == current_user.org_id)
        .first()
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="No candidate available to preview with")

    organization = current_user.organization
    from datetime import datetime, timezone
    from decimal import Decimal

    probe = OfferLetter(
        organization_id=current_user.org_id,
        candidate_id=candidate.id,
        designation="Sample Role",
        employment_type="Full-time",
        location="Remote",
        currency="USD",
        base_pay=Decimal("120000.00"),
        allowances=Decimal("12000.00"),
        annual_ctc=Decimal("132000.00"),
        offer_date=datetime.now(timezone.utc),
        start_date=datetime.now(timezone.utc),
        expires_in_days=7,
    )
    context = offer_letter_service.build_context(
        offer=probe,
        organization=organization,
        candidate=candidate,
        sender=current_user,
    )
    body, unresolved = offer_letter_service.render_tags(
        template.body, context, strict=False, prefix=template.name
    )
    subject, _ = offer_letter_service.render_tags(
        template.subject or "", context, strict=False
    )
    return {
        "subject": subject,
        "body": body,
        "unresolved_tags": sorted(set(unresolved)),
    }


# ── Offer letters ───────────────────────────────────────────────────────
@router.post("/offer-letters", status_code=status.HTTP_201_CREATED)
def create_offer(
    payload: OfferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(MANAGE),
):
    """Create a draft offer letter for a candidate."""
    candidate = (
        db.query(Candidate)
        .filter(
            Candidate.id == payload.candidate_id,
            Candidate.organization_id == current_user.org_id,
        )
        .first()
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    application = None
    if payload.application_id:
        application = (
            db.query(JobApplication)
            .filter(
                JobApplication.id == payload.application_id,
                JobApplication.organization_id == current_user.org_id,
                JobApplication.candidate_id == candidate.id,
            )
            .first()
        )
        if not application:
            raise HTTPException(
                status_code=404,
                detail="Application not found for this candidate",
            )

    template = None
    if payload.template_id:
        template = _load_template(db, payload.template_id, current_user)
    else:
        template = offer_letter_service.ensure_default_template(db, current_user.org_id)

    from datetime import datetime, timezone

    start_date = _parse_date(payload.start_date) or datetime.now(timezone.utc)
    annual = payload.annual_ctc if payload.annual_ctc is not None else (
        payload.base_pay + payload.allowances
    )

    offer = OfferLetter(
        organization_id=current_user.org_id,
        candidate_id=candidate.id,
        application_id=application.id if application else None,
        job_posting_id=(payload.job_posting_id or (application.job_posting_id if application else None)),
        template_id=template.id,
        designation=payload.designation.strip(),
        employment_type=payload.employment_type,
        location=payload.location,
        currency=payload.currency,
        base_pay=payload.base_pay,
        allowances=payload.allowances,
        annual_ctc=annual,
        offer_date=datetime.now(timezone.utc),
        start_date=start_date,
        expires_in_days=payload.expires_in_days,
        created_by_user_id=current_user.id,
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return _serialize(offer)


def _parse_date(value: Optional[str]):
    if not value:
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"start_date must be ISO-8601, got {value!r}"
        )


@router.get("/offer-letters")
def list_offers(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    candidate_id: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    query = db.query(OfferLetter).filter(
        OfferLetter.organization_id == current_user.org_id
    )
    if candidate_id is not None:
        query = query.filter(OfferLetter.candidate_id == candidate_id)
    if status_filter:
        query = query.filter(OfferLetter.status == status_filter)
    offers = query.order_by(OfferLetter.id.desc()).limit(limit).all()
    return [_serialize(offer) for offer in offers]


@router.get("/offer-letters/{offer_id}")
def get_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    return _serialize(_load_offer(db, offer_id, current_user))


@router.post("/offer-letters/{offer_id}/generate")
def generate_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(MANAGE),
):
    """Render the offer letter to PDF."""
    offer = _load_offer(db, offer_id, current_user)
    try:
        offer_letter_service.generate_offer_letter_pdf(
            db, offer, sender=current_user, regenerate=True
        )
    except OfferRenderError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": str(exc), "unresolved_tags": exc.unresolved},
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("Offer letter generation failed for offer %s", offer_id)
        raise HTTPException(status_code=500, detail="Failed to generate offer letter.")
    return _serialize(offer)


@router.get("/offer-letters/{offer_id}/download")
def download_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Download the rendered offer letter as a PDF."""
    offer = _load_offer(db, offer_id, current_user)

    if not offer.file_url:
        try:
            offer_letter_service.generate_offer_letter_pdf(
                db, offer, sender=current_user
            )
        except OfferRenderError as exc:
            raise HTTPException(
                status_code=422,
                detail={"error": str(exc), "unresolved_tags": exc.unresolved},
            )
        except Exception:
            logger.exception("Offer letter generation failed for offer %s", offer_id)
            raise HTTPException(status_code=500, detail="Failed to generate offer letter.")

    try:
        pdf_bytes = offer_letter_service.read_offer_letter_bytes(offer)
    except FileNotFoundError:
        # The record exists but the file is gone; re-render rather than
        # returning a broken download.
        try:
            offer = offer_letter_service.generate_offer_letter_pdf(
                db, offer, sender=current_user, regenerate=True
            )
            pdf_bytes = offer_letter_service.read_offer_letter_bytes(offer)
        except PDFStorageError:
            raise HTTPException(status_code=403, detail="Offer storage path is not permitted.")
        except Exception:
            logger.exception("Offer regeneration produced no file for offer %s", offer_id)
            raise HTTPException(status_code=500, detail="Offer document is unavailable.")
    except PDFStorageError:
        raise HTTPException(status_code=403, detail="Offer storage path is not permitted.")
    except Exception:
        logger.exception("Offer read failed for offer %s", offer_id)
        raise HTTPException(status_code=500, detail="Failed to read offer document.")

    filename = f"offer-{offer.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/offer-letters/{offer_id}/send")
def send_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(MANAGE),
):
    """
    Mark an offer as sent, which starts its response window.

    Renders the document if it has not been generated yet, so a sent offer is
    always a document the candidate can actually receive.
    """
    from datetime import datetime, timezone

    offer = _load_offer(db, offer_id, current_user)
    if offer.status not in (offer_letter_service.STATUS_DRAFT,):
        raise HTTPException(
            status_code=409,
            detail=f"Only a draft offer can be sent (current status: {offer.status})",
        )

    try:
        offer_letter_service.generate_offer_letter_pdf(
            db, offer, sender=current_user, regenerate=bool(offer.file_url)
        )
    except OfferRenderError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": str(exc), "unresolved_tags": exc.unresolved},
        )

    offer.status = offer_letter_service.STATUS_SENT
    offer.sent_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(offer)
    return _serialize(offer)


@router.post("/offer-letters/{offer_id}/respond")
def respond_to_offer(
    offer_id: int,
    payload: OfferRespond,
    db: Session = Depends(get_db),
    current_user: User = Depends(MANAGE),
):
    """Record the candidate's acceptance or refusal."""
    from datetime import datetime, timezone

    offer = _load_offer(db, offer_id, current_user)

    if offer.status != offer_letter_service.STATUS_SENT:
        raise HTTPException(
            status_code=409,
            detail=f"Only a sent offer can be answered (current status: {offer.status})",
        )
    if offer_letter_service.is_expired(offer):
        raise HTTPException(
            status_code=409, detail="The response window for this offer has closed"
        )
    if not payload.accepted and not (payload.reason or "").strip():
        raise HTTPException(
            status_code=422, detail="A decline reason is required when refusing an offer"
        )

    offer.status = (
        offer_letter_service.STATUS_ACCEPTED
        if payload.accepted
        else offer_letter_service.STATUS_DECLINED
    )
    offer.responded_at = datetime.now(timezone.utc)
    offer.decline_reason = None if payload.accepted else payload.reason.strip()
    db.commit()
    db.refresh(offer)
    return _serialize(offer)


@router.post("/offer-letters/{offer_id}/withdraw")
def withdraw_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(MANAGE),
):
    """Withdraw an offer that has not yet been answered."""
    offer = _load_offer(db, offer_id, current_user)
    if offer.status in (
        offer_letter_service.STATUS_ACCEPTED,
        offer_letter_service.STATUS_DECLINED,
        offer_letter_service.STATUS_WITHDRAWN,
    ):
        raise HTTPException(
            status_code=409,
            detail=f"A {offer.status} offer cannot be withdrawn",
        )
    offer.status = offer_letter_service.STATUS_WITHDRAWN
    db.commit()
    db.refresh(offer)
    return _serialize(offer)
