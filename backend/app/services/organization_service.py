from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import validate_password_strength
from app.crud.crud_org import organization as crud_org
from app.crud.crud_user import user as crud_user
from app.schema.org import OrganizationCreate, OrganizationUpdate
from app.db.models.all_models import (
    Department,
    Organization,
    Role,
    Shift,
    User,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkspaceContext:
    org_id: str
    workspace_name: str
    owner_user_id: int
    owner_email: str


class OrganizationService:
    """Single entry point for tenant/workspace provisioning.

    Stage 1 foundation: this service encapsulates all business logic for workspace
    onboarding. Wiring into /auth/register is intentionally NOT done in this stage.

    NOTE: Persistence details remain in CRUD modules (e.g., crud_org, crud_user).
    """

    def create_organization(self, *, db: Session, org_in: OrganizationCreate) -> Organization:
        existing = crud_org.get_by_legal_id(db, legal_id=org_in.legal_id)
        if existing:
            raise ValueError("An organization with this legal ID already exists")
        return crud_org.create(db, obj_in=org_in)

    def get_organization(self, *, db: Session, org_id: UUID) -> Optional[Organization]:
        return crud_org.get(db, id=org_id)

    def list_organizations(
        self, *, db: Session, skip: int, limit: int, search: Optional[str],
        include_inactive: bool,
    ) -> list[Organization]:
        return crud_org.list(
            db, skip=skip, limit=limit, search=search, include_inactive=include_inactive)

    def update_organization(
        self, *, db: Session, org: Organization, org_in: OrganizationUpdate,
    ) -> Organization:
        return crud_org.update(db, db_obj=org, obj_in=org_in)

    def set_organization_active(
        self, *, db: Session, org_id: UUID, is_active: bool,
    ) -> Optional[Organization]:
        return crud_org.set_active(db, org_id=org_id, is_active=is_active)

    def create_workspace(self, *, db: Session, workspace_name: str, legal_id: str) -> Organization:
        existing = crud_org.get_by_legal_id(db, legal_id=legal_id)
        if existing:
            # Idempotency: reuse existing organization when legal_id already exists.
            return existing

        org_in = {
            "name": workspace_name,
            "legal_id": legal_id,
            "is_active": 1,
        }
        return crud_org.create(db, obj_in=org_in)  # type: ignore[arg-type]


    def create_workspace_owner(
        self,
        *,
        db: Session,
        org_id,
        owner_name: str,
        owner_email: str,
        password: str,
        username: Optional[str] = None,
    ) -> User:
        ok, err = validate_password_strength(password)
        if not ok:
            raise ValueError(err)

        role_name = "SuperAdmin"

        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            logger.error("Workspace owner role lookup failed: role_name=%s", role_name)
            raise ValueError(
                "SuperAdmin role is missing. Ensure RBAC seed/migrations create it."
            )

        logger.info(
            "Creating workspace owner with SuperAdmin role: owner_email=%s role_id=%s role_name=%s",
            owner_email,
            role.id,
            role.name,
        )

        # Idempotency: if the workspace owner user already exists by email,
        # reuse it instead of attempting to insert (prevents unique constraint
        # violations on users.email / users.username / users.employee_id).
        existing_owner = (
            db.query(User)
            .filter(User.email == owner_email, User.is_deleted == 0)
            .first()
        )

        if existing_owner:
            # Ensure the owner points to the current org and has the expected role.
            existing_owner.org_id = org_id
            existing_owner.role_id = role.id
            if existing_owner.full_name != owner_name:
                existing_owner.full_name = owner_name
            db.add(existing_owner)
            logger.info(
                "Workspace owner reused: owner_user_id=%s owner_email=%s org_id=%s role_id=%s",
                existing_owner.id,
                owner_email,
                org_id,
                role.id,
            )
            return existing_owner

        if not username:
            base_username = owner_email.split("@")[0]
            username_candidate = base_username
            suffix = 1
            while db.query(User).filter(User.username == username_candidate).first():
                username_candidate = f"{base_username}{suffix}"
                suffix += 1
            username = username_candidate

        return crud_user.create(
            db,
            obj_in={
                "email": owner_email,
                "password": password,
                "full_name": owner_name,
                "username": username,
                "org_id": org_id,
                "role_id": role.id,
            },
        )

    def assign_owner_role(self, *, db: Session, owner_user_id: int, role_name: str = "SuperAdmin") -> None:
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            logger.error(
                "assign_owner_role failed: role_name=%s owner_user_id=%s",
                role_name,
                owner_user_id,
            )
            raise ValueError("Owner role does not exist: %s" % role_name)

        owner = db.query(User).filter(User.id == owner_user_id).first()
        if not owner:
            raise ValueError("Owner user does not exist")

        owner.role_id = role.id
        db.add(owner)

        logger.info(
            "assign_owner_role prepared: owner_user_id=%s new_role_id=%s role_name=%s",
            owner_user_id,
            role.id,
            role.name,
        )

    def initialize_workspace(self, *, db: Session, org_id) -> None:
        self.seed_default_departments(db=db, org_id=org_id)
        self.seed_default_shifts(db=db, org_id=org_id)
        self.seed_default_permissions(db=db, org_id=org_id)
        self.seed_default_settings(db=db, org_id=org_id)

    def seed_default_departments(self, *, db: Session, org_id) -> None:
        defaults = [
            ("Operations", "Default operations department"),
            ("Human Resources", "Default HR department"),
            ("Finance", "Default finance department"),
        ]
        for name, desc in defaults:
            exists = (
                db.query(Department)
                .filter(Department.org_id == org_id, Department.name == name)
                .first()
            )
            if not exists:
                db.add(Department(org_id=org_id, name=name, description=desc, is_deleted=0))

    def seed_default_shifts(self, *, db: Session, org_id) -> None:
        from datetime import time

        defaults = [
            ("General Shift", time(9, 0), time(18, 0), 5, 15, 0),
        ]
        for shift_name, start_t, end_t, grace, buffer_mins, break_deduct in defaults:
            exists = db.query(Shift).filter(Shift.org_id == org_id, Shift.shift_name == shift_name).first()
            if not exists:
                db.add(
                    Shift(
                        org_id=org_id,
                        shift_name=shift_name,
                        start_time=start_t,
                        end_time=end_t,
                        grace_period_mins=grace,
                        buffer_mins=buffer_mins,
                        break_deduct_mins=break_deduct,
                        is_deleted=0,
                    )
                )

    def seed_default_permissions(self, *, db: Session, org_id) -> None:
        """Seed baseline permissions and role mappings.

        This is required for Phase 1 acceptance invariants.

        Notes:
        - RBAC is modeled via Role.permissions (JSONB string list) and the
          role_permissions join table.
        - Permissions are global (no org_id FK in Permission model).
          We therefore seed Permission/RolePermission idempotently globally.
        - org_id is accepted to preserve the current service signature and
          for future scoping; it is not used for Permission/RolePermission
          persistence because the schema is global.
        """

        # Import locally to avoid widening import surface.
        from app.db.models.all_models import Permission, RolePermission

        # Minimal baseline used by existing backend dependencies/tests/UI.
        # Keep this conservative: add permissions only if they are missing.
        default_permission_names = [
            # RBAC / Roles / Permissions
            "role.view",
            "role.manage",
            "user.manage",
            # Users
            "users.read",
            "users.create",
            "users.update",
            "users.delete",
            # Attendance
            "attendance.checkin",
            "attendance.checkout",
            "attendance.history",
            "attendance.corrections",
            # Departments & Shifts
            "departments.read",
            "departments.create",
            "departments.update",
            "departments.delete",
            "shifts.read",
            "shifts.create",
            "shifts.update",
            "shifts.delete",
            # Payroll
            "payroll.generate",
            "payroll.approve",
            "payroll.export",
            # Reports
            "reports.attendance.export",
            "reports.payroll.export",
            "reports.employee.export",
            # Tickets
            "tickets.read",
            "tickets.create",
            "tickets.update",
            "tickets.delete",
            # Reimbursements
            "reimbursements.read",
            "reimbursements.create",
            "reimbursements.approve",
            "reimbursements.reject",
            # Notifications
            "notifications.read",
        ]

        for perm_name in default_permission_names:
            exists = db.query(Permission).filter(Permission.name == perm_name).first()
            if not exists:
                db.add(Permission(name=perm_name, description=None, category=None, is_active=True))

        # Role-to-permission mappings.
        # Ensure each role exists before mapping.
        role_names = ["SuperAdmin", "Admin", "Manager", "Employee"]
        roles = {
            r.name: r
            for r in db.query(Role).filter(Role.name.in_(role_names)).all()
        }

        # If roles do not exist, provisioning should fail loudly rather than
        # creating a broken tenant. create_workspace_owner already requires
        # SuperAdmin, but we keep this explicit.
        missing_roles = [rn for rn in role_names if rn not in roles]
        if missing_roles:
            raise ValueError(f"Missing RBAC roles for provisioning: {missing_roles}")

        # SuperAdmin gets all baseline permissions.
        superadmin = roles["SuperAdmin"]
        all_perm_ids = [
            p.id for p in db.query(Permission).filter(Permission.name.in_(default_permission_names)).all()
        ]

        for perm_id in all_perm_ids:
            exists = (
                db.query(RolePermission)
                .filter(RolePermission.role_id == superadmin.id, RolePermission.permission_id == perm_id)
                .first()
            )
            if not exists:
                db.add(RolePermission(role_id=superadmin.id, permission_id=perm_id))

        # Admin/Manager/Employee receive a conservative subset.
        def add_subset(role, subset_names):
            subset_ids = [
                p.id for p in db.query(Permission).filter(Permission.name.in_(subset_names)).all()
            ]
            for pid in subset_ids:
                exists = (
                    db.query(RolePermission)
                    .filter(RolePermission.role_id == role.id, RolePermission.permission_id == pid)
                    .first()
                )
                if not exists:
                    db.add(RolePermission(role_id=role.id, permission_id=pid))

        add_subset(roles["Admin"], [
            "users.read",
            "users.create",
            "users.update",
            "attendance.checkin",
            "attendance.checkout",
            "attendance.history",
            "departments.read",
            "departments.create",
            "departments.update",
            "shifts.read",
            "shifts.create",
            "shifts.update",
            "payroll.generate",
            "payroll.approve",
            "reports.attendance.export",
            "reports.payroll.export",
            "tickets.read",
            "tickets.create",
            "tickets.update",
            "reimbursements.read",
            "reimbursements.create",
            "reimbursements.approve",
            "notifications.read",
        ])

        add_subset(roles["Manager"], [
            "users.read",
            "attendance.checkin",
            "attendance.checkout",
            "attendance.history",
            "departments.read",
            "shifts.read",
            "reports.attendance.export",
            "tickets.read",
            "tickets.create",
            "tickets.update",
            "reimbursements.read",
            "reimbursements.create",
            "notifications.read",
        ])

        add_subset(roles["Employee"], [
            "attendance.checkin",
            "attendance.checkout",
            "attendance.history",
            "tickets.read",
            "tickets.create",
            "reimbursements.read",
            "reimbursements.create",
            "notifications.read",
        ])

    def seed_default_settings(self, *, db: Session, org_id) -> None:
        """Seed default settings.

        SystemSetting model is global; we seed required keys idempotently.
        """
        from app.db.models.all_models import SystemSetting

        default_settings = {
            # Values are string-typed in SystemSetting.setting_value.
            "blockchain_enabled": "false",
            "attendance_corrections_enabled": "true",
            "face_recognition_liveness_enabled": "true",
        }

        # Idempotency: prefetch existing keys in one query to avoid attempting
        # duplicate inserts within the same seeding run.
        keys = list(default_settings.keys())
        existing_keys = {
            row[0]
            for row in db.query(SystemSetting.setting_key)
            .filter(SystemSetting.setting_key.in_(keys))
            .all()
        }

        for key, value in default_settings.items():
            if key in existing_keys:
                continue
            db.add(
                SystemSetting(
                    setting_key=key,
                    setting_value=value,
                    description=None,
                )
            )



    def create_workspace_owner_and_seed(
        self,
        *,
        db: Session,
        workspace_name: str,
        owner_name: str,
        owner_email: str,
        password: str,
    ) -> WorkspaceContext:
        legal_id = (
            f"ORG-{owner_email.split('@')[0].upper()[:4]}-"
            f"{int(datetime.now(timezone.utc).timestamp())}"
        )

        try:
            # IMPORTANT: transaction boundary is owned by the caller (CLI / seed.py).
            # Do not start a nested transaction on the same Session.
            org = self.create_workspace(
                db=db,
                workspace_name=workspace_name,
                legal_id=legal_id,
            )
            org_id = org.id

            owner = self.create_workspace_owner(
                db=db,
                org_id=org_id,
                owner_name=owner_name,
                owner_email=owner_email,
                password=password,
            )

            logger.info(
                "Workspace owner created: org_id=%s owner_user_id=%s owner_email=%s role_id=%s",
                org_id,
                owner.id,
                owner_email,
                getattr(owner, "role_id", None),
            )

            self.assign_owner_role(
                db=db,
                owner_user_id=owner.id,
                role_name="SuperAdmin",
            )

            logger.info(
                "Assigned owner role: org_id=%s owner_user_id=%s role_name=%s",
                org_id,
                owner.id,
                "SuperAdmin",
            )

            self.initialize_workspace(db=db, org_id=org_id)

            return WorkspaceContext(
                org_id=str(org_id),
                workspace_name=org.name,
                owner_user_id=owner.id,
                owner_email=owner.email,
            )

        except IntegrityError as e:
            raise ValueError("Registration failed due to a uniqueness constraint") from e



organization_service = OrganizationService()
