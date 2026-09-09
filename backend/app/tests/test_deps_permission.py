import sys
import types
import os
import pytest
from unittest.mock import MagicMock

# Ensure the backend package root is on sys.path so 'app' is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# NOTE:
# This test file previously mutated sys.modules at import-time, which polluted the
# global interpreter state and broke other tests (including SQLAlchemy mapper
# configuration due to stubbing sqlalchemy.orm).
#
# Production code must not be modified; therefore, we scope all stubs using
# pytest's monkeypatch fixture.

from app.api import deps
from fastapi import HTTPException



@pytest.fixture(autouse=True)
def scoped_stubs():
    pass



class DummyRole:
    def __init__(self, name, permissions=None, id=1):
        self.name = name
        self.permissions = permissions or []
        self.id = id


class DummyUser:
    def __init__(self, id=1, role=None, role_id=1):
        self.id = id
        self.role = role or DummyRole("Employee", permissions=[])
        self.role_id = role_id


class DummyQuery:
    def __init__(self, result=None):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def first(self):
        return self._result

    def all(self):
        return self._result or []


class DummyDB(MagicMock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def query(self, model):
        # Return a dummy query; tests will set _result appropriately
        return DummyQuery(getattr(self, "_query_result", None))


def test_permission_allowed_via_role_permissions_list():
    user = DummyUser(role=DummyRole("Employee", permissions=["attendance.view"]))
    dep = deps.require_permission("attendance.view")

    # call the inner dependency with a DB placeholder
    db = DummyDB()
    coro = dep(current_user=user, db=db)
    # dep returns coroutine because it's async; run it
    result = asyncio_run(coro)
    assert result is user


def test_permission_allowed_via_role_permission_mapping(monkeypatch):
    user = DummyUser(role=DummyRole("Employee", permissions=[]), role_id=2)
    dep = deps.require_permission("attendance.export")

    # Prepare DB mock to return a Permission and RolePermission mapping
    db = DummyDB()
    perm = MagicMock()
    perm.id = 123
    db._query_result = None

    # Monkeypatch db.query to return specific results depending on model
    def query_side_effect(model):
        if model.__name__ == "Permission":
            return DummyQuery(perm)
        if model.__name__ == "RolePermission":
            return DummyQuery(MagicMock())
        if model.__name__ == "UserRole":
            return DummyQuery([])
        return DummyQuery(None)

    db.query = query_side_effect

    result = asyncio_run(dep(current_user=user, db=db))
    assert result is user


def test_permission_denied_when_missing(monkeypatch):
    user = DummyUser(role=DummyRole("Employee", permissions=[]), role_id=3)
    dep = deps.require_permission("non.existent")
    db = DummyDB()
    db.query = lambda model: DummyQuery(None)

    with pytest.raises(HTTPException):
        asyncio_run(dep(current_user=user, db=db))


# Small helper to run async coroutines in pytest without adding pytest-asyncio
import asyncio


def asyncio_run(coro):
    return asyncio.run(coro)

