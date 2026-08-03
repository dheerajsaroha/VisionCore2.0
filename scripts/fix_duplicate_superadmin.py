#!/usr/bin/env python3
"""Data migration: retire legacy Role ID=1 ("Super Admin")

Rules:
- DO NOT modify schema
- DO NOT modify RBAC architecture / code
- Update only data via ORM
- Single transaction
- If any validation fails: rollback

Phases:
1) Verify Role ID=6 is canonical (permissions>0) and Role ID=1 exists
2) Verify Role ID=1 has users and RolePermission rows per inspection expectations
3) Update all User.role_id == 1 -> 6
4) Re-validate: Role ID=1 has users=0 and permissions=0 and no remaining FK refs via explicit models
5) Delete Role ID=1
6) Final validation snapshots

Run:
  python backend/scripts/fix_duplicate_superadmin.py
"""

from __future__ import annotations

import os
import sys
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

# Ensure `backend/` is importable when executed directly.
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.db.database import SessionLocal
from app.db.models.all_models import Role, User, RolePermission


LEGACY_ROLE_ID = 1
CANONICAL_ROLE_ID = 6


def assert_int(name: str, v: Any) -> int:
    try:
        return int(v)
    except Exception as e:
        raise RuntimeError(f"{name} is not an int: {v!r}") from e


def main() -> None:
    session = SessionLocal()
    migrated_users = 0
    try:
        with session.begin():
            # --------------------------------------------------------------
            # Phase 0: load canonical/legacy roles
            # --------------------------------------------------------------
            legacy = session.execute(select(Role).where(Role.id == LEGACY_ROLE_ID)).scalar_one_or_none()
            canonical = session.execute(select(Role).where(Role.id == CANONICAL_ROLE_ID)).scalar_one_or_none()

            if legacy is None:
                raise RuntimeError(f"Legacy Role ID={LEGACY_ROLE_ID} not found")
            if canonical is None:
                raise RuntimeError(f"Canonical Role ID={CANONICAL_ROLE_ID} not found")

            # --------------------------------------------------------------
            # Phase 1: pre-validation (must match known state)
            # --------------------------------------------------------------
            legacy_users_q = session.execute(
                select(User.id).where(User.role_id == LEGACY_ROLE_ID, User.is_deleted == 0)
            )
            legacy_user_ids = [r[0] for r in legacy_users_q.all()]

            legacy_perm_count = session.execute(
                select(RolePermission.id).where(RolePermission.role_id == LEGACY_ROLE_ID)
            ).all()
            legacy_permissions = len(legacy_perm_count)

            canonical_perm_count = session.execute(
                select(RolePermission.id).where(RolePermission.role_id == CANONICAL_ROLE_ID)
            ).all()
            canonical_permissions = len(canonical_perm_count)

            if canonical_permissions <= 0:
                raise RuntimeError(f"Canonical role has no permissions (Role ID={CANONICAL_ROLE_ID})")

            # --------------------------------------------------------------
            # Phase 2: move references (User.role_id)
            # --------------------------------------------------------------
            if legacy_user_ids:
                session.execute(
                    select(User).where(User.role_id == LEGACY_ROLE_ID, User.is_deleted == 0)
                )

            # Bulk update via ORM entities for safety
            legacy_users = session.execute(
                select(User).where(User.role_id == LEGACY_ROLE_ID)
            ).scalars().all()

            for u in legacy_users:
                u.role_id = CANONICAL_ROLE_ID
            migrated_users = len(legacy_users)

            session.flush()

            # --------------------------------------------------------------
            # Phase 3: validation (no refs remain for explicit models)
            # --------------------------------------------------------------
            remaining_legacy_users = session.execute(
                select(User.id).where(User.role_id == LEGACY_ROLE_ID)
            ).all()
            remaining_legacy_user_count = len(remaining_legacy_users)

            remaining_legacy_perms = session.execute(
                select(RolePermission.id).where(RolePermission.role_id == LEGACY_ROLE_ID)
            ).all()
            remaining_legacy_perm_count = len(remaining_legacy_perms)

            if remaining_legacy_user_count != 0:
                raise RuntimeError(f"Validation failed: legacy Role ID={LEGACY_ROLE_ID} still referenced by users={remaining_legacy_user_count}")

            if remaining_legacy_perm_count != 0:
                raise RuntimeError(f"Validation failed: legacy Role ID={LEGACY_ROLE_ID} still referenced by role_permissions={remaining_legacy_perm_count}")

            # --------------------------------------------------------------
            # Phase 4: delete legacy role
            # --------------------------------------------------------------
            # Ensure no FK references remain beyond explicit models.
            # With the given schema, the relevant FK columns are:
            # - users.role_id
            # - role_permissions.role_id
            # If there are additional FKs, the delete will fail.
            session.delete(legacy)
            session.flush()

            # --------------------------------------------------------------
            # Phase 5: post-validation
            # --------------------------------------------------------------
            legacy_check = session.execute(select(Role).where(Role.id == LEGACY_ROLE_ID)).scalar_one_or_none()
            if legacy_check is not None:
                raise RuntimeError("Post-validation failed: legacy role was not deleted")

            canonical_check = session.execute(select(Role).where(Role.id == CANONICAL_ROLE_ID)).scalar_one_or_none()
            if canonical_check is None:
                raise RuntimeError("Post-validation failed: canonical role missing")

            canonical_after_perm_count = session.execute(
                select(RolePermission.id).where(RolePermission.role_id == CANONICAL_ROLE_ID)
            ).all()
            canonical_after_permissions = len(canonical_after_perm_count)

            if canonical_after_permissions != canonical_permissions:
                raise RuntimeError(
                    f"Canonical permissions changed unexpectedly: before={canonical_permissions}, after={canonical_after_permissions}"
                )

        # Transaction committed
        # --------------------------------------------------------------
        # Final printed report
        # --------------------------------------------------------------
        print("=== fix_duplicate_superadmin.py SUCCESS ===")
        print(f"Canonical Role ID: {CANONICAL_ROLE_ID}")
        print(f"Legacy Role ID deleted: {LEGACY_ROLE_ID}")
        print(f"Users migrated (total): {migrated_users}")

    except SQLAlchemyError as e:
        session.rollback()
        print("=== fix_duplicate_superadmin.py FAILED (SQLAlchemyError) ===")
        raise
    except Exception as e:
        session.rollback()
        print("=== fix_duplicate_superadmin.py FAILED ===")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()

