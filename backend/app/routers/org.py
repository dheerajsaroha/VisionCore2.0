from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging

import hashlib
import secrets

from app.crud.crud_api_key import api_key as crud_api_key
from app.services.organization_service import organization_service
from app.schema.org import (
    OrganizationResponse,
    OrganizationCreate,
    OrganizationUpdate,
    ApiKeyCreate,
    ApiKeyResponse
)
from app.crud.crud_api_key import ApiKeyCreateInternal
from app.db.database import get_db
from app.api import deps
from app.db.models.all_models import User

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_organization_admin(current_user: User) -> None:
    if current_user.role and current_user.role.name not in {"Admin", "SuperAdmin", "Super Admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization administration is required")


def _require_platform_admin(current_user: User) -> None:
    if current_user.role and current_user.role.name not in {"SuperAdmin", "Super Admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform administration is required")


@router.post("/", response_model=OrganizationResponse)
def create_organization(
    *,
    db: Session = Depends(get_db),
    org_in: OrganizationCreate,
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Create a new organization (Tenant).
    """
    _require_platform_admin(current_user)
    try:
        return organization_service.create_organization(db=db, org_in=org_in)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/", response_model=List[OrganizationResponse])
def list_organizations(
    *,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None, max_length=200),
    include_inactive: bool = False,
    current_user: User = Depends(deps.get_current_active_user),
):
    _require_platform_admin(current_user)
    return organization_service.list_organizations(
        db=db, skip=skip, limit=limit, search=search, include_inactive=include_inactive)


@router.get("/current", response_model=OrganizationResponse)
def read_current_organization(
    *, db: Session = Depends(get_db), current_user: User = Depends(deps.get_current_active_user)
):
    org = organization_service.get_organization(db=db, org_id=current_user.org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.put("/", response_model=OrganizationResponse)
def update_organization(
    *,
    db: Session = Depends(get_db),
    org_in: OrganizationUpdate,
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Update the current user's organization (branding, ZKP threshold).
    """
    _require_organization_admin(current_user)
    org = organization_service.get_organization(db=db, org_id=current_user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return organization_service.update_organization(db=db, org=org, org_in=org_in)


@router.post("/{org_id}/deactivate", response_model=OrganizationResponse)
def deactivate_organization(
    org_id: UUID, *, db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    _require_platform_admin(current_user)
    org = organization_service.set_organization_active(db=db, org_id=org_id, is_active=False)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.post("/{org_id}/restore", response_model=OrganizationResponse)
def restore_organization(
    org_id: UUID, *, db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    _require_platform_admin(current_user)
    org = organization_service.set_organization_active(db=db, org_id=org_id, is_active=True)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.post("/api-keys")
def create_api_key(
    *,
    db: Session = Depends(get_db),
    key_in: ApiKeyCreate,
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Generate a new API key for the organization.
    Returns the raw key ONCE.
    """
    _require_organization_admin(current_user)

    raw_key = f"vc_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    internal_key = ApiKeyCreateInternal(
        org_id=current_user.org_id,
        key_hash=key_hash,
        scope=key_in.scope,
        rate_limit=key_in.rate_limit
    )

    db_obj = crud_api_key.create(db, obj_in=internal_key)

    return {
        "id": db_obj.id,
        "scope": db_obj.scope,
        "rate_limit": db_obj.rate_limit,
        "raw_key": raw_key  # Only time this is returned!
    }


@router.get("/api-keys", response_model=List[ApiKeyResponse])
def list_api_keys(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    List active API keys for the organization.
    """
    _require_organization_admin(current_user)

    keys = crud_api_key.get_multi_by_org(db, org_id=current_user.org_id, skip=skip, limit=limit)
    return keys


@router.delete("/api-keys/{key_id}", response_model=ApiKeyResponse)
def revoke_api_key(
    *,
    db: Session = Depends(get_db),
    key_id: int,
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Revoke an API key.
    """
    _require_organization_admin(current_user)

    key = crud_api_key.get(db, id=key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    if key.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    key = crud_api_key.revoke(db, db_obj=key)
    return key


@router.get("/{org_id}", response_model=OrganizationResponse)
def read_organization(
    org_id: UUID, *, db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Platform-scoped organization detail view."""
    _require_platform_admin(current_user)
    org = organization_service.get_organization(db=db, org_id=org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org
