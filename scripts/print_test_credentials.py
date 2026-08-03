#!/usr/bin/env python
"""QA Credential Report

Prints known QA test credentials (without password hashes).

Only prints the known QA default password assigned by reset_qa_passwords.py.
"""

from __future__ import annotations

import argparse
from typing import Optional

from app.db.database import SessionLocal
from app.db.models.all_models import User

DEFAULT_PASSWORD = "Vision@123"


def main() -> None:
    parser = argparse.ArgumentParser(description="Print QA default test credentials.")
    parser.add_argument("--role", type=str, default=None, help="Filter by role name")
    parser.add_argument("--all-qa", action="store_true", help="Include QA users only (heuristic)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        q = db.query(User)
        if args.role:
            # FK/relationship can differ; attempt relationship first.
            q = [
                u
                for u in q.all()
                if getattr(getattr(u, "role", None), "name", None) == args.role
            ]
        else:
            q = q.all()

        def is_qa(u: User) -> bool:
            email = (getattr(u, "email", None) or "").lower()
            username = (getattr(u, "username", None) or "").lower()
            return (
                email.endswith(".qa")
                or "+qa" in email
                or email.startswith("qa")
                or username.startswith("qa")
            )

        if args.all_qa:
            users = [u for u in q if is_qa(u)]
        else:
            users = list(q)

        print("Role\tEmail\tDefault Password\tOrganization\tStatus")
        for u in users:
            role_name: Optional[str] = getattr(getattr(u, "role", None), "name", None)
            email = getattr(u, "email", None)
            org_name = getattr(getattr(u, "org", None), "name", None)
            status = "NULL"
            try:
                is_active = getattr(u, "is_active", None)
                is_locked = getattr(u, "is_locked", None)
                status = f"active={is_active},locked={is_locked}"
            except Exception:
                status = "NULL"

            print(
                "\t".join(
                    [
                        role_name if role_name is not None else "NULL",
                        email if email is not None else "NULL",
                        DEFAULT_PASSWORD,
                        org_name if org_name is not None else "NULL",
                        status,
                    ]
                )
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()

