"""
Regression tests for RBAC permission name validation.

GET /api/v1/rbac/permissions returned 500 because the PermissionResponse schema
rejected permission names that exist in the seeded catalog:

  ai_governance.manage           (underscore in the module segment)
  attendance_correction:approve  (colon separator)

Both forms are referenced verbatim by require_permission() guards, so the
schema had to be widened rather than the data renamed. These tests assert that
every permission row can be serialized, which is what the 500 came from.
"""
import pytest
from pydantic import ValidationError

from app.db.database import SessionLocal
from app.db.models.all_models import Permission
from app.schema.rbac import PERMISSION_NAME_PATTERN, PermissionResponse


@pytest.fixture(scope="module")
def permissions():
    db = SessionLocal()
    try:
        yield db.query(Permission).all()
    finally:
        db.close()


def test_pattern_accepts_documented_forms():
    import re

    pattern = re.compile(PERMISSION_NAME_PATTERN)
    for name in (
        "users.read",
        "attendance.checkin",
        "reports.attendance.export",
        "ai_governance.manage",
        "attendance_correction:approve",
    ):
        assert pattern.match(name), f"{name} should be a valid permission name"


def test_pattern_rejects_malformed_names():
    import re

    pattern = re.compile(PERMISSION_NAME_PATTERN)
    for name in ("nodots", "Users.read", ".leading", "trailing.", "UPPER.case"):
        assert not pattern.match(name), f"{name} should be rejected"


def test_every_seeded_permission_validates(permissions):
    """This is the exact assertion whose failure produced the 500."""
    assert permissions, "permission catalog must be seeded"
    failures = []
    for permission in permissions:
        try:
            PermissionResponse.model_validate(permission)
        except ValidationError as exc:
            failures.append((permission.name, exc.error_count()))
    assert not failures, f"permissions failing response validation: {failures}"


def test_non_dot_permission_names_are_covered(permissions):
    """Guard against the catalog regressing to shapes the schema rejects."""
    names = [p.name for p in permissions]
    assert any(n.startswith("attendance_correction:") for n in names), (
        "expected colon-separated attendance_correction permissions to exist"
    )
