import pytest

from app.core.security import verify_token_type


def test_verify_token_type_rejects_invalid_token():
    assert verify_token_type("not-a-jwt", expected_type="access") is False

