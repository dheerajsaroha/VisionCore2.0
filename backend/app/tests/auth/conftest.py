import os
import uuid
from typing import Generator, Optional, Tuple


import pytest
from fastapi.testclient import TestClient

from main import app
from app.core.security import get_password_hash
from app.db.database import SessionLocal
from app.db.models.all_models import User, Role, Organization



@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


def _discover_first_qa_user_email() -> Optional[str]:
    """Best-effort discovery of a QA user from the DB.

    This intentionally does NOT guess credentials. It only reads the DB
    and returns an email/username if any QA-like user exists.

    QA heuristic kept in sync with reset_qa_passwords.py tooling.
    """
    db = SessionLocal()
    try:
        users = db.query(User).all()
        for u in users:
            email = (getattr(u, "email", None) or "").lower()
            username = (getattr(u, "username", None) or "").lower()
            is_qa = (
                email.endswith(".qa")
                or "+qa" in email
                or email.startswith("qa")
                or username.startswith("qa")
            )
            if is_qa:
                return getattr(u, "email", None)
        return None
    finally:
        db.close()


@pytest.fixture(scope="session")
def qa_identity() -> Tuple[str, str, str, str]:
    """Deterministic QA identity for auth regression tests.

    Returns: (email, password, role, organization)

    Behavior:
    - If QA user exists: ensure its password is Vision@123 and return its details.
    - If missing: create a minimal QA user using existing Role/Organization rows.
    """

    # Deterministic password used by tests + reset tool
    password = os.getenv("QA_PASSWORD", "Vision@123")

    # Prefer explicit email if provided; still ensure password is correct.
    requested_email = os.getenv("QA_EMAIL")

    db = SessionLocal()
    try:
        # Select a QA-like user by heuristic unless email is explicitly provided.
        qa_user: Optional[User] = None
        if requested_email:
            qa_user = db.query(User).filter(User.email == requested_email).first()

        if not qa_user:
            qa_email_found = _discover_first_qa_user_email()
            if qa_email_found:
                qa_user = db.query(User).filter(User.email == qa_email_found).first()

        # If still missing, create QA user.
        if not qa_user:
            # Pick any existing organization and role to satisfy FKs.
            org: Optional[Organization] = db.query(Organization).first()
            role: Optional[Role] = db.query(Role).first()
            if not org or not role:
                raise RuntimeError("Cannot create QA user: missing Organization/Role seed data")

            qa_email = requested_email or "qa.qauser@qa"
            # Ensure unique username/email/employee_id.
            existing = db.query(User).filter(
                (User.email == qa_email) | (User.username == qa_email.split("@")[0])
            ).first()
            if existing:
                qa_email = f"{qa_email.split('@')[0]}-{existing.id}@qa"

            username = qa_email.split("@")[0]
            employee_id = f"QA-EMP-{uuid.uuid4().hex[:8]}"
            qa_user = User(
                org_id=org.id,
                role_id=role.id,
                full_name="QA User",
                username=username,
                email=qa_email,
                phone=None,
                employee_id=employee_id,
                hashed_password=get_password_hash(password),
                is_deleted=0,
                is_active=1,
            )
            db.add(qa_user)
            db.commit()
            db.refresh(qa_user)

        # Ensure password is correct (do not leak hashes)
        qa_user.hashed_password = get_password_hash(password)
        db.add(qa_user)
        db.commit()
        db.refresh(qa_user)

        # Fetch role/org names for return.
        role_name = getattr(getattr(qa_user, "role", None), "name", None) or str(getattr(qa_user, "role_id", ""))
        org_name = getattr(getattr(qa_user, "organization", None), "name", None) or str(getattr(qa_user, "org_id", ""))

        return qa_user.email, password, role_name, org_name
    finally:
        db.close()


@pytest.fixture(scope="session")
def qa_identity_tuple(qa_identity) -> Tuple[str, str, str, str]:
    return qa_identity


@pytest.fixture(scope="session")
def qa_email(qa_identity_tuple: Tuple[str, str, str, str]) -> str:
    return qa_identity_tuple[0]


@pytest.fixture(scope="session")
def qa_password(qa_identity_tuple: Tuple[str, str, str, str]) -> str:
    return qa_identity_tuple[1]


@pytest.fixture(scope="session")
def qa_role(qa_identity_tuple: Tuple[str, str, str, str]) -> str:
    return qa_identity_tuple[2]


@pytest.fixture(scope="session")
def qa_organization(qa_identity_tuple: Tuple[str, str, str, str]) -> str:
    return qa_identity_tuple[3]



