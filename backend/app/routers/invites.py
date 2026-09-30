"""
Employee onboarding invites.

Administration endpoints require authentication and are tenant-scoped. The two
recipient endpoints (`validate`, `accept`) are deliberately unauthenticated --
the recipient has no account yet -- so they are rate limited and return a single
generic message for every failure mode so they cannot be used to discover which
tokens exist.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.core.rate_limit import rate_limit_dependency
from app.db.database import get_db
from app.db.models.all_models import (
    Department,
    EmployeeInvite,
    Role,
    User,
)
from app.services import invite_service
from app.services.invite_service import InviteError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["invites"])

# Module-level so tests can override the exact object the routes captured,
# mirroring how offer_letters exposes its MANAGE dependency.
MANAGE = deps.require_permission("users.create")

# Roles an administrator may hand out without holding `roles.assign`: the
# self-service employee tier and the read-only viewer. Anything else is
# privileged and needs the escalation permission.
#
# Names are canonical, because `normalize_role_name` maps the legacy "Employee"
# onto "OrgEmployee" before the lookup — comparing against the raw literal
# would classify an ordinary hire as privileged.
SELF_ASSIGNABLE_ROLES = frozenset({"Employee", "OrgEmployee", "OrgViewer"})

# Recipients are unauthenticated, so the attempt budget is deliberately tight.
RECIPIENT_RATE_LIMIT = rate_limit_dependency(10, 900)
ADMIN_RATE_LIMIT = rate_limit_dependency(30, 3600)


class InviteCreate(BaseModel):
    email: EmailStr
    full_name: Optional[str] = Field(default=None, max_length=100)
    role: str = Field(default="Employee", max_length=50)
    department_id: Optional[int] = None
    manager_id: Optional[int] = None
    valid_days: Optional[int] = Field(default=None, ge=1, le=30)


class InviteAccept(BaseModel):
    password: str = Field(min_length=10, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=100)
    employee_id: Optional[str] = Field(default=None, max_length=50)


class ChecklistUpdate(BaseModel):
    profile: Optional[bool] = None
    documents: Optional[bool] = None
    tax_form: Optional[bool] = None


def _authorised_role(db: Session, current_user: User, role_name: str) -> Role:
    """
    Resolve the role to invite into, applying the same privilege-escalation
    rules as employee creation.

    This runs while an authenticated administrator is present, which is the
    only point at which the decision can be attributed to someone. Accepting
    the link later applies the role authorised here.
    """
    target_name = deps.normalize_role_name(role_name or "Employee")
    role = db.query(Role).filter(Role.name == target_name).first()
    if not role:
        raise HTTPException(status_code=400, detail=f"Role '{target_name}' does not exist.")

    is_superadmin = deps.has_any_role(current_user, "SuperAdmin")
    if target_name not in SELF_ASSIGNABLE_ROLES:
        if not (deps.has_permission(current_user, "roles.assign", db) or is_superadmin):
            raise HTTPException(
                status_code=403,
                detail="Permission roles.assign required to invite a privileged role.",
            )
    if getattr(role, "tier", None) in ("platform", "system") and not is_superadmin:
        raise HTTPException(status_code=403, detail="Cannot assign platform-tier or system roles.")
    return role


def _validate_department(db: Session, org_id, department_id: Optional[int]) -> Optional[int]:
    if department_id is None:
        return None
    department = (
        db.query(Department)
        .filter(Department.id == department_id, Department.org_id == org_id)
        .first()
    )
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    return department.id


def _validate_manager(db: Session, org_id, manager_id: Optional[int]) -> Optional[int]:
    if manager_id is None:
        return None
    manager = (
        db.query(User)
        .filter(User.id == manager_id, User.org_id == org_id)
        .first()
    )
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found in this organisation")
    return manager.id


# ── Administration ──────────────────────────────────────────────────────
@router.post(
    "/org/invites",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(ADMIN_RATE_LIMIT)],
)
def create_invite(
    payload: InviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(MANAGE),
    _seat: None = Depends(deps.require_limit("employees", increment_by=1)),
) -> Dict[str, Any]:
    """
    Invite a new hire by email.

    The returned `token` is the only time the raw link is available; only its
    hash is stored.
    """
    role = _authorised_role(db, current_user, payload.role)
    department_id = _validate_department(db, current_user.org_id, payload.department_id)
    manager_id = _validate_manager(db, current_user.org_id, payload.manager_id)

    try:
        invite, raw_token = invite_service.create_invite(
            db,
            organization_id=current_user.org_id,
            email=payload.email,
            full_name=payload.full_name,
            role_id=role.id,
            department_id=department_id,
            manager_id=manager_id,
            invited_by_user_id=current_user.id,
            valid_days=payload.valid_days,
        )
    except InviteError as exc:
        code = status.HTTP_409_CONFLICT if exc.code == "duplicate" else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=exc.message)

    result = invite_service.serialize(invite)
    result["token"] = raw_token
    result["invite_link"] = f"/onboarding/accept?token={raw_token}"
    return result


@router.get("/org/invites")
def list_invites(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> List[Dict[str, Any]]:
    """List this organisation's invites. Tokens are never returned here."""
    query = db.query(EmployeeInvite).filter(
        EmployeeInvite.organization_id == current_user.org_id
    )
    if status_filter:
        query = query.filter(EmployeeInvite.status == status_filter)
    invites = query.order_by(EmployeeInvite.id.desc()).limit(limit).all()
    return [invite_service.serialize(invite) for invite in invites]


@router.post("/org/invites/{invite_id}/revoke")
def revoke_invite(
    invite_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(MANAGE),
) -> Dict[str, Any]:
    invite = (
        db.query(EmployeeInvite)
        .filter(
            EmployeeInvite.id == invite_id,
            EmployeeInvite.organization_id == current_user.org_id,
        )
        .first()
    )
    if not invite:
        raise HTTPException(status_code=404, detail="Invitation not found")

    try:
        invite = invite_service.revoke_invite(db, invite)
    except InviteError as exc:
        raise HTTPException(status_code=409, detail=exc.message)
    return invite_service.serialize(invite)


# ── Recipient (unauthenticated) ─────────────────────────────────────────
@router.get("/invites/validate")
def validate_invite(
    token: str = Query(..., description="Raw invite token from the emailed link"),
    db: Session = Depends(get_db),
    _rate: bool = Depends(RECIPIENT_RATE_LIMIT),
) -> Dict[str, Any]:
    """Check an invite link before the recipient commits to anything."""
    try:
        return invite_service.validate_invite(db, token)
    except InviteError:
        # One message for unknown, expired, revoked and used tokens alike.
        raise HTTPException(status_code=400, detail=invite_service.GENERIC_INVALID)


@router.post("/invites/accept")
def accept_invite(
    payload: InviteAccept,
    token: str = Query(..., description="Raw invite token from the emailed link"),
    db: Session = Depends(get_db),
    _rate: bool = Depends(RECIPIENT_RATE_LIMIT),
) -> Dict[str, Any]:
    """
    Consume an invite and activate the new hire's account.

    Returns a neutral acknowledgement: the recipient is not logged in here and
    signs in with their chosen password through the normal login route.
    """
    try:
        user = invite_service.accept_invite(
            db, token,
            password=payload.password,
            full_name=payload.full_name,
            employee_id=payload.employee_id,
        )
    except InviteError as exc:
        if exc.code == "name_required":
            raise HTTPException(status_code=422, detail=exc.message)
        if exc.code == "limit":
            raise HTTPException(status_code=402, detail=exc.message)
        raise HTTPException(status_code=400, detail=invite_service.GENERIC_INVALID)
    except Exception:
        logger.exception("Invite acceptance failed")
        raise HTTPException(status_code=500, detail="Could not complete onboarding.")

    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "message": "Your account is ready. Sign in with your new password.",
    }


@router.put("/invites/checklist")
def update_checklist(
    payload: ChecklistUpdate,
    token: str = Query(..., description="Raw invite token from the emailed link"),
    db: Session = Depends(get_db),
    _rate: bool = Depends(RECIPIENT_RATE_LIMIT),
) -> Dict[str, Any]:
    """Record progress on the pre-day-one onboarding checklist."""
    invite = invite_service.lookup_by_token(db, token)
    if invite is None or not invite_service.is_usable(invite):
        raise HTTPException(status_code=400, detail=invite_service.GENERIC_INVALID)

    invite = invite_service.mark_checklist(
        db, invite,
        profile=payload.profile,
        documents=payload.documents,
        tax_form=payload.tax_form,
    )
    return {
        "checklist": invite_service.checklist_progress(invite),
        "onboarding_complete": invite_service.is_onboarding_complete(invite),
    }
