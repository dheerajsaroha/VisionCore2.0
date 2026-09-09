"""
users.py — RBAC-protected user management router.
All queries are scoped to current_user.org_id for strict multi-tenancy.
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.crud.crud_user import user as crud_user
from app.api import deps
from app.schema.user import UserResponse, UserCreate, UserUpdate, UserUpdateMe, UserListResponse, FaceEnroll
from app.db.models.all_models import User, EnrollmentEvent, SpoofDetectionLog
import base64
from app.services.face_engine import face_engine
from app.services.audit_service import AuditService
from app.core.config import settings
from app.db.database import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def read_user_me(current_user: User = Depends(deps.get_current_active_user)) -> Any:
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_user_me(
    *,
    db: Session = Depends(get_db),
    user_in: UserUpdateMe,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Allow authenticated users to update their own profile (full_name, email).
    Strictly protects role, org_id, employee_id, and permissions from alteration.
    """
    user = db.query(User).filter(User.id == current_user.id, User.is_deleted == 0).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_in.full_name is not None:
        name = user_in.full_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        user.full_name = name

    if user_in.email is not None:
        email = user_in.email.strip().lower()
        if email != user.email:
            existing = crud_user.get_by_email(db, email=email)
            if existing and existing.id != user.id:
                raise HTTPException(status_code=400, detail="Email is already in use")
            user.email = email

    db.add(user)
    db.commit()
    db.refresh(user)

    AuditService(db).log_update(
        actor=user,
        action="UPDATE_SELF_PROFILE",
        target_type="User",
        target_id=str(user.id),
        before_state={"full_name": current_user.full_name, "email": current_user.email},
        after_state={"full_name": user.full_name, "email": user.email},
        tenant_org_id=str(user.org_id),
    )


    return user




@router.get("/", response_model=UserListResponse)
def read_users(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    role: Optional[str] = Query(None, description="Filter by role name"),
    is_active: Optional[int] = Query(None, description="Filter by active status: 1=active, 0=inactive"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    current_user: User = Depends(deps.require_permission("users.read")),
) -> Any:
    """STRICT MULTI-TENANCY: Authorized users only see users in their own org."""
    query = db.query(User).filter(
        User.org_id == current_user.org_id,
        User.is_deleted == 0,
    )

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    if role:
        from app.db.models.all_models import Role
        query = query.join(Role, User.role_id == Role.id).filter(Role.name == role)

    if search:
        term = f"%{search}%"
        query = query.filter(
            (User.full_name.ilike(term)) | (User.email.ilike(term)) | (User.employee_id.ilike(term))
        )

    total = query.with_entities(func.count(User.id)).scalar()
    users = query.offset(skip).limit(limit).all()

    return {"total": total, "users": users}


@router.post("/", response_model=UserResponse)
def create_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
    current_user: User = Depends(deps.require_permission("users.create")),
) -> Any:
    user_in.org_id = current_user.org_id
    user_in.organization = current_user.organization.name if current_user.organization else "default"

    existing = crud_user.get_by_email(db, email=user_in.email)
    if existing:
        raise HTTPException(status_code=400, detail="Identity already registered.")

    return crud_user.create(db, obj_in=user_in.model_dump())


@router.get("/{user_id}", response_model=UserResponse)
def read_user_by_id(
    user_id: int,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    user = db.query(User).filter(
        User.id == user_id,
        User.org_id == current_user.org_id,
        User.is_deleted == 0,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Identity not found")
    if current_user.id != user_id and not deps.has_permission(current_user, "users.read", db):
        raise HTTPException(status_code=403, detail="Forbidden")

    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    *,
    db: Session = Depends(get_db),
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update an employee's profile. Users can update themselves; admins can update anyone."""
    if current_user.id != user_id and not deps.has_permission(current_user, "users.update", db):
        raise HTTPException(status_code=403, detail="Unauthorized")

    updated = crud_user.update(
        db,
        user_id=user_id,
        org_id=current_user.org_id,
        obj_in=user_in.model_dump(exclude_none=True),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Identity not found")
    return updated


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("users.delete")),
) -> Any:
    """Soft-delete an employee. Sets is_deleted=1. Admin only. Self-deletion is blocked."""
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    deleted = crud_user.soft_delete(db, user_id=user_id, org_id=current_user.org_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Identity not found")
    return {"detail": f"Employee {user_id} has been deactivated and archived."}


@router.post("/{user_id}/enroll")
def enroll_user_face_json(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    enroll_in: FaceEnroll,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    user = db.query(User).filter(
        User.id == user_id,
        User.org_id == current_user.org_id,
        User.is_deleted == 0,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Identity not found")
    if current_user.id != user_id and not deps.has_permission(current_user, "users.update", db):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Never accept a client-supplied embedding: it bypasses image detection and
    # enables an authenticated caller to register an arbitrary biometric vector.
    if enroll_in.face_embedding is not None:
        raise HTTPException(status_code=400, detail="Client-supplied biometric embeddings are not accepted")

    embedding = None
    if enroll_in.image_base64:
        try:
            image_bytes = base64.b64decode(enroll_in.image_base64, validate=True)
            if len(image_bytes) > settings.MAX_BIOMETRIC_IMAGE_BYTES:
                raise HTTPException(status_code=413, detail="Biometric image exceeds the permitted size")
            embedding = face_engine.get_embedding(image_bytes)
            if not embedding:
                raise HTTPException(status_code=400, detail="No face detected in submitted image")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed base64 image data")

    if not embedding:
        raise HTTPException(status_code=400, detail="A valid biometric image is required")

    crud_user.enroll_face(db, user_id=user_id, embedding=embedding)
    AuditService(db).log_create(
        actor=current_user,
        action="biometric.enroll",
        target_type="FaceEmbedding",
        target_id=str(user_id),
        after_state={"user_id": user_id, "source": "image_base64"},
        tenant_org_id=str(current_user.org_id),
    )
    return {"status": "success", "message": "Neural identity registered."}


@router.post("/{user_id}/enroll-face")
async def enroll_user_face_file(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    user = db.query(User).filter(
        User.id == user_id,
        User.org_id == current_user.org_id,
        User.is_deleted == 0,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Identity not found")
    if current_user.id != user_id and not deps.has_permission(current_user, "users.update", db):
        raise HTTPException(status_code=403, detail="Forbidden")

    logger.info("Enrollment started for user=%s", user_id)
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Biometric enrollment requires an image file")
    image_bytes = await file.read()

    org_id = current_user.org_id
    min_bytes = 1024
    try:
        if not image_bytes or len(image_bytes) < min_bytes:
            raise ValueError("Image resolution too low")
        if len(image_bytes) > settings.MAX_BIOMETRIC_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Biometric image exceeds the permitted size")

        embedding = face_engine.get_embedding(image_bytes)
        if not embedding:
            raise ValueError("No face or multiple faces detected in the image")

        quality_score = min(9.9, max(0.1, len(image_bytes) / 100000.0))
        embedding_version = "face_recognition_v1"

        crud_user.enroll_face(db, user_id=user_id, embedding=embedding)

        db.add(
            EnrollmentEvent(
                user_id=user_id,
                org_id=org_id,
                status="success",
                quality_score=quality_score,
                embedding_version=embedding_version,
                image_resolution=f"{len(image_bytes)}bytes",
                brightness_score=None,
                blur_score=None,
            )
        )

        db.add(
            SpoofDetectionLog(
                user_id=user_id,
                org_id=org_id,
                attempt_type="enrollment",
                is_spoof=0,
                spoof_score=None,
                model_name=None,
            )
        )

        db.commit()
        AuditService(db).log_create(
            actor=current_user,
            action="biometric.enroll",
            target_type="FaceEmbedding",
            target_id=str(user_id),
            after_state={"user_id": user_id, "source": "file"},
            tenant_org_id=str(org_id),
        )
        return {"status": "success", "message": "Neural identity registered."}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.exception("Face enrollment failed: %s", str(e))
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
