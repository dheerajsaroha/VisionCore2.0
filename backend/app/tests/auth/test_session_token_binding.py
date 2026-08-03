from datetime import timedelta

from jose import jwt

from app.core import security
from app.core.config import settings


def test_access_and_refresh_tokens_bind_distinct_session_identifiers():
    access_token = security.create_access_token(
        42, expires_delta=timedelta(minutes=1), session_jti="access-jti"
    )
    refresh_token = security.create_refresh_token(
        42, expires_delta=timedelta(minutes=1), session_jti="refresh-jti"
    )

    access_payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
    refresh_payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])

    assert access_payload["type"] == "access"
    assert access_payload["jti"] == "access-jti"
    assert refresh_payload["type"] == "refresh"
    assert refresh_payload["jti"] == "refresh-jti"
    assert security.verify_token_type(access_token, "access")
    assert security.verify_token_type(refresh_token, "refresh")
    assert not security.verify_token_type(access_token, "refresh")
