import sys
import os
import types
import pytest

# Make backend package importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.api import deps
from fastapi import HTTPException

# Importing real app.api.deps here; tests use monkeypatch to isolate side effects.



class DummyRole:
    def __init__(self, name, permissions=None, id=1):
        self.name = name
        self.permissions = permissions or []
        self.id = id


class DummyUser:
    def __init__(self, user_id=1, role=None, role_id=1, is_active=True):
        self.id = user_id
        self.role = role or DummyRole("Employee", permissions=[])
        self.role_id = role_id
        self.is_active = is_active


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


class DummyDB:
    def __init__(self, permission_exists=False):
        self.permission_exists = permission_exists

    def query(self, model):
        # deps.require_permission expects Permission, RolePermission, UserRole.
        name = getattr(model, '__name__', '')
        if name == 'Permission':
            if self.permission_exists:
                perm = types.SimpleNamespace(id=123, is_active=True)
                return DummyQuery(perm)
            return DummyQuery(None)
        if name == 'RolePermission':
            # Return a mapping row if permission_exists is True.
            return DummyQuery(types.SimpleNamespace(id=1) if self.permission_exists else None)
        if name == 'UserRole':
            # No extra roles.
            return DummyQuery([])
        return DummyQuery(None)


@pytest.fixture(autouse=True)
def scoped_stubs():
    pass



def asyncio_run(coro):
    """Run async coroutine safely on Py3.12+ (no current event loop)."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        raise RuntimeError("asyncio_run cannot be used while an event loop is running")

    return asyncio.run(coro)



def test_permission_allowed_via_role_json_permissions():
    user = DummyUser(role=DummyRole('Employee', permissions=['users.view']))
    dep = deps.require_permission('users.view')

    db = DummyDB(permission_exists=True)
    result = asyncio_run(dep(current_user=user, db=db))
    assert result is user


def test_permission_denied_when_not_in_role_json_and_mapping_absent():
    user = DummyUser(role=DummyRole('Employee', permissions=[]), role_id=2)
    dep = deps.require_permission('users.delete')

    db = DummyDB(permission_exists=False)

    with pytest.raises(HTTPException):
        asyncio_run(dep(current_user=user, db=db))


def test_permission_allowed_via_role_permission_mapping():
    user = DummyUser(role=DummyRole('Employee', permissions=[]), role_id=2)
    dep = deps.require_permission('attendance.view')

    db = DummyDB(permission_exists=True)
    result = asyncio_run(dep(current_user=user, db=db))
    assert result is user

