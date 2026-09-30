import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.security import get_password_hash
from app.core.biometric_crypto import encrypt_embedding
from app.db.models.all_models import (
    User,
    FaceEmbedding,
    Organization,
    OrganizationSubscription,
    Role,
)

logger = logging.getLogger(__name__)


class CRUDUser:
    def get(self, db: Session, *, id: int) -> Optional[User]:
        return db.query(User).filter(User.id == id, User.is_deleted == 0).first()

    def get_by_email(self, db: Session, *, email: str, org_id: Optional[uuid.UUID] = None) -> Optional[User]:
        """
        Find a user by email.

        Email is unique per tenant, not globally, so `org_id` is required by
        every caller that is acting on behalf of one organisation. It is
        optional only so the few genuinely cross-tenant callers can ask for the
        single-account case explicitly; with no `org_id` and more than one
        match this returns None rather than an arbitrary one.
        """
        q = db.query(User).filter(
            func.lower(User.email) == (email or "").strip().lower(),
            User.is_deleted == 0,
        )
        if org_id is not None:
            q = q.filter(User.org_id == org_id)
        matches = q.all()
        if len(matches) > 1:
            logger.warning(
                "get_by_email is ambiguous for %s across %d organisations; "
                "pass org_id to disambiguate", email, len(matches),
            )
            return None
        return matches[0] if matches else None

    def get_all_by_email(self, db: Session, *, email: str) -> List[User]:
        """
        Every account registered to an address, across all organisations.

        For callers that must act on all of them -- password reset, where the
        mailbox owner is entitled to reset each account they hold.
        """
        return (
            db.query(User)
            .filter(
                func.lower(User.email) == (email or "").strip().lower(),
                User.is_deleted == 0,
            )
            .all()
        )

    def create(self, db: Session, *, obj_in: Dict[str, Any]) -> User:
        """
        Creates a user from a dict payload (used by /auth/register and /users/).
        Expects keys: email, password, name/full_name, role, organization.
        """
        # Validate required fields
        required_fields = ["email", "password"]
        for field in required_fields:
            if not obj_in.get(field):
                raise ValueError(f"Missing required field: {field}")

        name = obj_in.get("name") or obj_in.get("full_name", "")
        org_name = obj_in.get("organization", "default")

        # 1. Get or Create Organization
        org = db.query(Organization).filter(Organization.name == org_name).first()
        if not org:
            org = Organization(
                name=org_name,
                legal_id=f"ORG-{org_name.upper()[:4]}-{int(datetime.now(timezone.utc).timestamp())}"
            )
            db.add(org)
            db.commit()
            db.refresh(org)

        # 2. Get or Assign Role
        # SECURITY FIX: Only assign valid pre-existing roles from the DB.
        role_name = obj_in.get("role", "Employee")
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            # Fallback to standard Employee role
            role = db.query(Role).filter(Role.name == "Employee").first()
            if not role:
                role = Role(name="Employee", permissions=[])
                db.add(role)
                db.commit()
                db.refresh(role)

        # 3. Create User — use org_id from payload if injected by admin flow
        org_id = obj_in.get("org_id") or org.id

        # Stored lowercase, because uniqueness is enforced by a functional
        # index on `lower(email)`; storing mixed case would let the same mailbox
        # in two spellings slip past it.
        email = (obj_in["email"] or "").strip().lower()

        # BUG-11 fix: derive a unique username by appending a numeric suffix if needed.
        base_username = email.split("@")[0]
        username = base_username
        suffix = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}{suffix}"
            suffix += 1

        employee_id = obj_in.get("employee_id") or f"EMP-{uuid.uuid4().hex[:6].upper()}"

        db_obj = User(
            email=email,
            hashed_password=get_password_hash(obj_in["password"]),
            full_name=name,
            username=username,
            org_id=org_id,
            role_id=role.id,
            dept_id=obj_in.get("dept_id"),
            shift_id=obj_in.get("shift_id"),
            phone=obj_in.get("phone"),
            employee_id=employee_id,
            is_active=obj_in.get("is_active", 1),   # Integer column: 1=active, 0=suspended
            is_deleted=0,  # Integer column: 0=active, 1=soft-deleted
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)

        # 4. Create initial EmploymentRecord if designation, branch, or employment details provided
        designation = obj_in.get("designation")
        employment_type = obj_in.get("employment_type") or "EMPLOYEE"
        reporting_manager_id = obj_in.get("reporting_manager_id")
        branch_id = obj_in.get("branch_id")
        if designation or reporting_manager_id or branch_id or employment_type != "EMPLOYEE":
            from app.db.models.all_models import EmploymentRecord
            emp_rec = EmploymentRecord(
                org_id=org_id,
                user_id=db_obj.id,
                designation=designation,
                employment_type=employment_type,
                reporting_manager_id=reporting_manager_id,
                branch_id=branch_id,
                status="ACTIVE",
            )
            db.add(emp_rec)
            db.commit()

        # 5. Ensure the tenant has a subscription so plan enforcement is meaningful.
        # A tenant without one fails every feature check, so provisioning it here
        # keeps self-service signup working on the default tier.
        if not db.query(OrganizationSubscription).filter(
            OrganizationSubscription.organization_id == org_id
        ).first():
            from app.services.subscription_service import subscription_service

            subscription_service.ensure_default_subscription(db, org_id)

        return db_obj

    def update(self, db: Session, *, user_id: int, org_id: uuid.UUID, obj_in: dict) -> Optional[User]:
        """
        Update editable fields on a user. Scoped to org_id for tenant safety.
        Handles role name → role_id resolution, dept/shift lookups, phone and employment updates.
        """
        db_obj = db.query(User).filter(
            User.id == user_id,
            User.org_id == org_id,
            User.is_deleted == 0,
        ).first()
        if not db_obj:
            return None

        if "full_name" in obj_in and obj_in["full_name"] is not None:
            db_obj.full_name = obj_in["full_name"]
        if "phone" in obj_in and obj_in["phone"] is not None:
            db_obj.phone = obj_in["phone"]
        if "is_active" in obj_in and obj_in["is_active"] is not None:
            db_obj.is_active = obj_in["is_active"]
        if "dept_id" in obj_in:
            db_obj.dept_id = obj_in["dept_id"]
        if "shift_id" in obj_in:
            db_obj.shift_id = obj_in["shift_id"]
        if "role" in obj_in and obj_in["role"] is not None:
            role = db.query(Role).filter(Role.name == obj_in["role"]).first()
            if role:
                db_obj.role_id = role.id

        # Update EmploymentRecord if designation, branch, or manager changed
        if any(k in obj_in for k in ("designation", "employment_type", "reporting_manager_id", "branch_id")):
            from app.db.models.all_models import EmploymentRecord
            emp_rec = db.query(EmploymentRecord).filter(
                EmploymentRecord.org_id == org_id,
                EmploymentRecord.user_id == user_id,
            ).first()
            if not emp_rec:
                emp_rec = EmploymentRecord(
                    org_id=org_id,
                    user_id=user_id,
                    designation=obj_in.get("designation"),
                    employment_type=obj_in.get("employment_type") or "EMPLOYEE",
                    reporting_manager_id=obj_in.get("reporting_manager_id"),
                    branch_id=obj_in.get("branch_id"),
                    status="ACTIVE",
                )
                db.add(emp_rec)
            else:
                if "designation" in obj_in:
                    emp_rec.designation = obj_in["designation"]
                if "employment_type" in obj_in and obj_in["employment_type"] is not None:
                    emp_rec.employment_type = obj_in["employment_type"]
                if "reporting_manager_id" in obj_in:
                    emp_rec.reporting_manager_id = obj_in["reporting_manager_id"]
                if "branch_id" in obj_in:
                    emp_rec.branch_id = obj_in["branch_id"]

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def soft_delete(self, db: Session, *, user_id: int, org_id: uuid.UUID) -> Optional[User]:
        """Soft-delete a user. Sets is_deleted=1. NEVER hard deletes."""
        db_obj = db.query(User).filter(
            User.id == user_id,
            User.org_id == org_id,
            User.is_deleted == 0,
        ).first()
        if not db_obj:
            return None
        db_obj.is_deleted = 1
        db_obj.is_active = 0
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def enroll_face(
        self,
        db: Session,
        *,
        user_id: int,
        embedding: list,
        photo_bytes: Optional[bytes] = None,
        photo_mime: Optional[str] = None,
    ) -> FaceEmbedding:
        """
        Stores or replaces the face embedding for a user.
        Marks any previous embedding as inactive.
        Stores tenant-isolated, encrypted backup of the biometric vector.
        Keeps the enrollment capture so operators can identify the template.
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        db.query(FaceEmbedding).filter(
            FaceEmbedding.user_id == user_id,
            FaceEmbedding.is_active == 1
        ).update({"is_active": 0}, synchronize_session=False)
        db.commit()

        face_obj = FaceEmbedding(
            user_id=user_id,
            org_id=user.org_id,
            embedding=embedding,
            encrypted_embedding=encrypt_embedding(embedding),
            model_name="face_recognition",
            is_active=1,
            enrollment_photo=photo_bytes,
            enrollment_photo_mime=photo_mime or "image/jpeg",
        )

        db.add(face_obj)
        db.commit()
        db.refresh(face_obj)

        return face_obj


user = CRUDUser()
