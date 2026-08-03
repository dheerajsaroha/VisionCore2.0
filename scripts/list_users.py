#!/usr/bin/env python
"""QA User Discovery Tool

Print QA/admin users currently present in the DB.

Do NOT modify any data.
"""

from __future__ import annotations

import argparse
from datetime import datetime

from app.db.database import SessionLocal
from app.db.models.all_models import User, Role, Organization


def _dt_or_none(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def main() -> None:
    parser = argparse.ArgumentParser(description="List users from the database (QA tooling).")
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Only show users where is_active == 1",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        q = db.query(User)
        if args.active_only:
            q = q.filter(User.is_active == 1)

        rows = q.all()

        # Print a clean table (tab-separated for deterministic parsing)
        headers = [
            "Email",
            "Username",
            "Full Name",
            "Role",
            "Organization",
            "Workspace",
            "Active Status",
            "Verified Status",
            "Locked Status",
            "Created Date",
        ]
        print("\t".join(headers))

        for u in rows:
            role_name = None
            try:
                if hasattr(u, "role") and u.role is not None and getattr(u.role, "name", None):
                    role_name = u.role.name
            except Exception:
                role_name = None

            org_name = None
            try:
                if hasattr(u, "org") and u.org is not None and getattr(u.org, "name", None):
                    org_name = u.org.name
            except Exception:
                org_name = None

            workspace = getattr(u, "workspace", None)

            active = getattr(u, "is_active", None)
            verified = getattr(u, "is_verified", None)
            locked = getattr(u, "is_locked", None)

            created_at = getattr(u, "created_at", None) or getattr(u, "created_date", None)

            # If relationships are missing, fall back to FK columns where possible.
            if role_name is None:
                try:
                    rid = getattr(u, "role_id", None)
                    if rid is not None:
                        rr = db.query(Role).filter(Role.id == rid).first()
                        role_name = rr.name if rr is not None else None
                except Exception:
                    role_name = None

            if org_name is None:
                try:
                    oid = getattr(u, "org_id", None)
                    if oid is not None:
                        oo = db.query(Organization).filter(Organization.id == oid).first()
                        org_name = oo.name if oo is not None else None
                except Exception:
                    org_name = None

            # NULL instead of failing
            def nv(x):
                return "NULL" if x is None else str(x)

            print(
                "\t".join(
                    [
                        nv(getattr(u, "email", None)),
                        nv(getattr(u, "username", None)),
                        nv(getattr(u, "full_name", None)),
                        nv(role_name),
                        nv(org_name),
                        nv(workspace),
                        nv(active),
                        nv(verified),
                        nv(locked),
                        nv(_dt_or_none(created_at)),
                    ]
                )
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()

