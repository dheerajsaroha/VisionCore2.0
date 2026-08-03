#!/usr/bin/env python
"""QA Password Reset Tool

Resets passwords for selected QA accounts using the existing get_password_hash()
function from app.core.security.

Default password: Vision@123

Idempotent; never modifies users unless they match the selection.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Iterable, List, Optional

from app.core.security import get_password_hash
from app.db.database import SessionLocal
from app.db.models.all_models import User

DEFAULT_PASSWORD = "Vision@123"


@dataclass(frozen=True)
class ResultRow:
    user_id: int
    email: str
    username: Optional[str]
    updated: bool


def _should_update(u: User, *, email: Optional[str], role: Optional[str], all_qa: bool) -> bool:
    if email:
        return (getattr(u, "email", None) == email)

    # Heuristic: QA users are those whose email contains "+qa" OR endswith ".qa" OR username startswith "qa"
    # If your QA naming differs, adjust selection flags rather than code.
    user_email = (getattr(u, "email", None) or "").lower()
    user_username = (getattr(u, "username", None) or "").lower()
    is_qa = (
        user_email.endswith(".qa")
        or "+qa" in user_email
        or user_username.startswith("qa")
        or user_email.startswith("qa")
    )

    if all_qa and not is_qa:
        return False

    if role:
        # role might be relationship (u.role.name) or FK (u.role_id)
        r = getattr(u, "role", None)
        role_name = getattr(r, "name", None)
        if role_name is None:
            return False
        if role_name != role:
            return False

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset QA passwords using existing hashing.")
    parser.add_argument("--email", type=str, default=None, help="Reset password for a single email")
    parser.add_argument("--role", type=str, default=None, help="Reset password for users with the given role")
    parser.add_argument("--all-qa", action="store_true", help="Reset password for all QA users")

    args = parser.parse_args()

    if not args.email and not args.role and not args.all_qa:
        raise SystemExit("Provide at least one selector: --email, --role, or --all-qa")

    db = SessionLocal()
    updated: List[User] = []
    skipped: List[User] = []
    missing: List[str] = []

    try:
        # Precompute hash once.
        new_hash = get_password_hash(DEFAULT_PASSWORD)

        q = db.query(User)
        if args.email:
            q = q.filter(User.email == args.email)

        users = q.all()

        # If --email was provided but no matching user exists.
        if args.email and not users:
            missing.append(args.email)

        for u in users:
            try:
                if not _should_update(u, email=args.email, role=args.role, all_qa=args.all_qa):
                    skipped.append(u)
                    continue

                u.hashed_password = new_hash
                db.add(u)
                updated.append(u)
            except Exception:
                skipped.append(u)

        db.commit()

        def fmt_user(u: User) -> str:
            return f"{getattr(u, 'email', None)} ({getattr(u, 'id', None)})"

        print("Updated users")
        for u in updated:
            print(" -", fmt_user(u))

        print("Skipped users")
        for u in skipped:
            print(" -", fmt_user(u))

        print("Missing users")
        for m in missing:
            print(" -", m)

    finally:
        db.close()


if __name__ == "__main__":
    main()

