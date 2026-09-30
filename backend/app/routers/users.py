"""
users.py — RBAC-protected user management router.
All queries are scoped to current_user.org_id for strict multi-tenancy.
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.crud.crud_user import user as crud_user
from app.api import deps
from app.schema.user import UserResponse, UserCreate, UserUpdate, UserUpdateMe, UserListResponse, FaceEnroll
from app.db.models.all_models import User, EnrollmentEvent, SpoofDetectionLog, FaceEmbedding
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
            # Scoped to this user's tenant: the same address may legitimately
            # belong to an employee of a different organisation, and that must
            # not block the change.
            existing = crud_user.get_by_email(db, email=email, org_id=user.org_id)
            if existing and existing.id != user.id:
                raise HTTPException(
                    status_code=400,
                    detail="Email is already in use in this organisation",
                )
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


@router.get("/summary")
def get_users_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("users.read")),
) -> Any:
    """STRICT MULTI-TENANCY: Return real metrics for identities in current user's org."""
    from app.db.models.all_models import Role, FaceEmbedding

    base_query = db.query(User).filter(
        User.org_id == current_user.org_id,
        User.is_deleted == 0,
    )
    total = base_query.count()
    active_count = base_query.filter(User.is_active == 1).count()
    inactive_count = base_query.filter(User.is_active == 0).count()
    privileged_roles = ["Admin", "OrgAdmin", "SuperAdmin", "PlatformAdmin", "OrgManager", "Manager", "OrgDepartmentHead"]
    privileged_count = base_query.join(Role, User.role_id == Role.id).filter(Role.name.in_(privileged_roles)).count()
    enrolled_count = base_query.join(FaceEmbedding, (FaceEmbedding.user_id == User.id) & (FaceEmbedding.is_active == 1)).count()

    return {
        "total": total,
        "active_count": active_count,
        "inactive_count": inactive_count,
        "privileged_count": privileged_count,
        "enrolled_count": enrolled_count,
    }


@router.get("/", response_model=UserListResponse)
def read_users(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    role: Optional[str] = Query(None, description="Filter by role name"),
    is_active: Optional[int] = Query(None, description="Filter by active status: 1=active, 0=inactive"),
    dept_id: Optional[int] = Query(None, description="Filter by department ID"),
    employment_type: Optional[str] = Query(None, description="Filter by employment type: EMPLOYEE, CONTRACTOR, etc."),
    branch_id: Optional[int] = Query(None, description="Filter by branch/location ID"),
    manager_id: Optional[int] = Query(None, description="Filter by reporting manager ID"),
    search: Optional[str] = Query(None, description="Search by name, email, employee ID, designation, or department"),
    sort_by: Optional[str] = Query("created_at", description="Field to sort by: created_at, full_name, email, employee_id"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    current_user: User = Depends(deps.require_permission("users.read")),
) -> Any:
    """STRICT MULTI-TENANCY: Authorized users only see users in their own org."""
    from sqlalchemy.orm import joinedload
    from app.db.models.all_models import Role, Department, EmploymentRecord

    query = db.query(User).filter(
        User.org_id == current_user.org_id,
        User.is_deleted == 0,
    )

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    if dept_id is not None:
        query = query.filter(User.dept_id == dept_id)

    if role:
        query = query.join(Role, User.role_id == Role.id).filter(Role.name == role)

    has_emp_join = False
    if employment_type:
        query = query.outerjoin(
            EmploymentRecord,
            (EmploymentRecord.user_id == User.id) & (EmploymentRecord.org_id == User.org_id),
        )
        has_emp_join = True
        query = query.filter(EmploymentRecord.employment_type == employment_type)

    if branch_id is not None:
        if not has_emp_join:
            query = query.outerjoin(
                EmploymentRecord,
                (EmploymentRecord.user_id == User.id) & (EmploymentRecord.org_id == User.org_id),
            )
            has_emp_join = True
        query = query.filter(EmploymentRecord.branch_id == branch_id)

    if manager_id is not None:
        if not has_emp_join:
            query = query.outerjoin(
                EmploymentRecord,
                (EmploymentRecord.user_id == User.id) & (EmploymentRecord.org_id == User.org_id),
            )
            has_emp_join = True
        query = query.filter(EmploymentRecord.reporting_manager_id == manager_id)

    if search:
        term = f"%{search.strip()}%"
        if not has_emp_join:
            query = query.outerjoin(
                EmploymentRecord,
                (EmploymentRecord.user_id == User.id) & (EmploymentRecord.org_id == User.org_id),
            )
        query = query.outerjoin(Department, Department.id == User.dept_id)
        query = query.filter(
            (User.full_name.ilike(term))
            | (User.email.ilike(term))
            | (User.employee_id.ilike(term))
            | (EmploymentRecord.designation.ilike(term))
            | (Department.name.ilike(term))
        )

    total = query.with_entities(func.count(func.distinct(User.id))).scalar() or 0

    sort_field_map = {
        "created_at": User.created_at,
        "full_name": User.full_name,
        "email": User.email,
        "employee_id": User.employee_id,
        "id": User.id,
    }
    sort_column = sort_field_map.get(sort_by, User.created_at)
    if sort_order and sort_order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    users = (
        query.options(
            joinedload(User.role),
            joinedload(User.department),
            joinedload(User.shift),
            joinedload(User.face_embedding),
            joinedload(User.employment_record).joinedload(EmploymentRecord.branch),
            joinedload(User.employment_record).joinedload(EmploymentRecord.reporting_manager),
            joinedload(User.sessions),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {"total": total, "users": users}


@router.post("/", response_model=UserResponse)
def create_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
    current_user: User = Depends(deps.require_permission("users.create")),
    _seat: None = Depends(deps.require_limit("employees", increment_by=1)),
) -> Any:
    user_in.org_id = current_user.org_id
    user_in.organization = current_user.organization.name if current_user.organization else "default"

    # Duplicate means duplicate *within this tenant*. Email is unique per
    # organisation, so an address already registered elsewhere is a different
    # person and must not block the invite.
    existing_email = crud_user.get_by_email(
        db, email=user_in.email, org_id=current_user.org_id
    )
    if existing_email:
        raise HTTPException(
            status_code=400, detail="Identity already registered in this organisation."
        )

    # Validate duplicate employee_id if provided
    if user_in.employee_id:
        existing_emp = db.query(User).filter(
            User.employee_id == user_in.employee_id,
            User.is_deleted == 0
        ).first()
        if existing_emp:
            raise HTTPException(status_code=400, detail="Identity with this Employee ID already exists.")

    # Validate role and enforce privilege escalation guards
    from app.db.models.all_models import Role
    target_role_name = user_in.role or "Employee"
    target_role = db.query(Role).filter(Role.name == target_role_name).first()
    if not target_role:
        raise HTTPException(status_code=400, detail=f"Role '{target_role_name}' does not exist.")

    is_superadmin = bool(current_user.role and current_user.role.name == "SuperAdmin")
    if target_role_name != "Employee":
        if not (deps.has_permission(current_user, "roles.assign", db) or is_superadmin):
            raise HTTPException(status_code=403, detail="Permission roles.assign required to assign privileged roles.")

    if target_role.tier in ("platform", "system") and not is_superadmin:
        raise HTTPException(status_code=403, detail="Cannot assign platform-tier or system roles.")

    created = crud_user.create(db, obj_in=user_in.model_dump())

    AuditService(db).log_create(
        actor=current_user,
        action="identity.created",
        target_type="User",
        target_id=str(created.id),
        after_state={"full_name": created.full_name, "email": created.email, "role": user_in.role},
        tenant_org_id=str(current_user.org_id),
    )

    return created


@router.get("/{user_id}", response_model=UserResponse)
def read_user_by_id(
    user_id: int,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    from sqlalchemy.orm import joinedload

    from app.db.models.all_models import EmploymentRecord

    user = db.query(User).options(
        joinedload(User.role),
        joinedload(User.department),
        joinedload(User.shift),
        joinedload(User.face_embedding),
        joinedload(User.employment_record).joinedload(EmploymentRecord.branch),
        joinedload(User.employment_record).joinedload(EmploymentRecord.reporting_manager),
        joinedload(User.sessions),
    ).filter(
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
    """Update an employee's profile. Scoped to org_id. RBAC enforced on sensitive fields."""
    target_user = db.query(User).filter(
        User.id == user_id,
        User.org_id == current_user.org_id,
        User.is_deleted == 0,
    ).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Identity not found")

    is_self = (current_user.id == user_id)
    has_update_perm = deps.has_permission(current_user, "users.update", db)

    if not is_self and not has_update_perm:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # If role change requested: require roles.assign or SuperAdmin
    if user_in.role is not None:
        is_superadmin = bool(current_user.role and current_user.role.name == "SuperAdmin")
        if not (deps.has_permission(current_user, "roles.assign", db) or is_superadmin):
            raise HTTPException(status_code=403, detail="Permission roles.assign required to modify role")

        from app.db.models.all_models import Role
        target_role = db.query(Role).filter(Role.name == user_in.role).first()
        if not target_role:
            raise HTTPException(status_code=400, detail=f"Role '{user_in.role}' does not exist.")
        if target_role.tier in ("platform", "system") and not is_superadmin:
            raise HTTPException(status_code=403, detail="Cannot assign platform-tier or system roles.")

    # If deactivation requested:
    if user_in.is_active is not None and user_in.is_active == 0:
        if is_self:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        if not has_update_perm:
            raise HTTPException(status_code=403, detail="Permission users.update required to change account status")
        # Check last administrator guard
        from app.db.models.all_models import Role
        admin_roles = ["Admin", "OrgAdmin"]
        if target_user.role and target_user.role.name in admin_roles:
            admin_count = db.query(User).join(Role, User.role_id == Role.id).filter(
                User.org_id == current_user.org_id,
                User.is_deleted == 0,
                User.is_active == 1,
                Role.name.in_(admin_roles)
            ).count()
            if admin_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot deactivate the organization's sole administrator")

        from app.crud.crud_session import user_session
        user_session.revoke_all_for_user(db, user_id=user_id, reason="account_deactivated", logout=True)

    before_state = {
        "full_name": target_user.full_name,
        "is_active": target_user.is_active,
        "role": target_user.role.name if target_user.role else None,
        "dept_id": target_user.dept_id,
    }

    updated = crud_user.update(
        db,
        user_id=user_id,
        org_id=current_user.org_id,
        obj_in=user_in.model_dump(exclude_none=True),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Identity not found")

    AuditService(db).log_update(
        actor=current_user,
        action="identity.updated",
        target_type="User",
        target_id=str(user_id),
        before_state=before_state,
        after_state=user_in.model_dump(exclude_none=True),
        tenant_org_id=str(current_user.org_id),
    )

    return updated


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("users.delete")),
) -> Any:
    """Soft-delete an employee. Sets is_deleted=1. Admin only. Self-deletion & sole admin deletion blocked."""
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    target_user = db.query(User).filter(
        User.id == user_id,
        User.org_id == current_user.org_id,
        User.is_deleted == 0,
    ).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Identity not found")

    from app.db.models.all_models import Role
    admin_roles = ["Admin", "OrgAdmin"]
    if target_user.role and target_user.role.name in admin_roles:
        admin_count = db.query(User).join(Role, User.role_id == Role.id).filter(
            User.org_id == current_user.org_id,
            User.is_deleted == 0,
            User.is_active == 1,
            Role.name.in_(admin_roles)
        ).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the organization's sole administrator")

    deleted = crud_user.soft_delete(db, user_id=user_id, org_id=current_user.org_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Identity not found")

    from app.crud.crud_session import user_session
    user_session.revoke_all_for_user(db, user_id=user_id, reason="account_deleted", logout=True)

    AuditService(db).log_event(
        actor=current_user,
        action="identity.deleted",
        target_type="User",
        target_id=str(user_id),
        before_state={"full_name": target_user.full_name, "email": target_user.email},
        after_state={"is_deleted": 1, "is_active": 0},
        tenant_org_id=str(current_user.org_id),
    )

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
    photo_bytes = None
    if enroll_in.image_base64:
        try:
            image_bytes = base64.b64decode(enroll_in.image_base64, validate=True)
            if len(image_bytes) > settings.MAX_BIOMETRIC_IMAGE_BYTES:
                raise HTTPException(status_code=413, detail="Biometric image exceeds the permitted size")
            embedding = face_engine.get_embedding(image_bytes)
            if not embedding:
                raise HTTPException(status_code=400, detail="No face detected in submitted image")
            photo_bytes = image_bytes
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed base64 image data")

    if not embedding:
        raise HTTPException(status_code=400, detail="A valid biometric image is required")

    crud_user.enroll_face(
        db,
        user_id=user_id,
        embedding=embedding,
        photo_bytes=photo_bytes,
        photo_mime="image/jpeg" if photo_bytes else None,
    )
    AuditService(db).log_create(
        actor=current_user,
        action="biometric.enroll",
        target_type="FaceEmbedding",
        target_id=str(user_id),
        after_state={"user_id": user_id, "source": "image_base64"},
        tenant_org_id=str(current_user.org_id),
    )
    return {"status": "success", "message": "Neural identity registered."}


@router.get("/{user_id}/face-photo")
def get_user_face_photo(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Return the capture stored with the active biometric template.

    Tenant-scoped and permission-gated: a caller may always read their own
    template, another identity requires users.update. The bytes are never
    exposed through list endpoints.
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.org_id == current_user.org_id,
        User.is_deleted == 0,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Identity not found")
    if current_user.id != user_id and not deps.has_permission(current_user, "users.update", db):
        raise HTTPException(status_code=403, detail="Forbidden")

    embedding = db.query(FaceEmbedding).filter(
        FaceEmbedding.user_id == user_id,
        FaceEmbedding.is_active == 1,
    ).first()
    if embedding is None or not embedding.enrollment_photo:
        raise HTTPException(status_code=404, detail="No enrollment photo on record")

    return Response(
        content=embedding.enrollment_photo,
        media_type=embedding.enrollment_photo_mime or "image/jpeg",
        headers={"Cache-Control": "private, max-age=300"},
    )


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

        crud_user.enroll_face(
            db,
            user_id=user_id,
            embedding=embedding,
            photo_bytes=image_bytes,
            photo_mime=file.content_type or "image/jpeg",
        )

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
