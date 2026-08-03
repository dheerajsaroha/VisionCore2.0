import pytest

from app.core.security import get_password_hash, verify_password


def test_password_hashing_roundtrip():
    # Pure unit-level check; does not hit auth flow.
    password = "Vision@123"
    hashed = get_password_hash(password)
    assert hashed and isinstance(hashed, str)
    assert verify_password(password, hashed) is True
    assert verify_password("wrong", hashed) is False

