import hashlib
import base64
import logging
from typing import List

from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_biometric_key() -> bytes:
    raw = settings.SECRET_KEY.encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return base64.urlsafe_b64encode(digest[:32])


_cipher: Fernet | None = None


def _get_cipher() -> Fernet:
    global _cipher
    if _cipher is None:
        _cipher = Fernet(_get_biometric_key())
    return _cipher


def encrypt_embedding(embedding: List[float]) -> bytes:
    payload = ",".join(f"{v:.6f}" for v in embedding).encode("utf-8")
    return _get_cipher().encrypt(payload)


def decrypt_embedding(token: bytes) -> List[float]:
    payload = _get_cipher().decrypt(token)
    return [float(v) for v in payload.decode("utf-8").split(",") if v]


def safe_decrypt_embedding(token: bytes | None) -> List[float] | None:
    if token is None:
        return None
    try:
        return decrypt_embedding(token)
    except InvalidToken:
        logger.warning("Biometric embedding decrypt failed — invalid token")
        return None
    except Exception as exc:
        logger.error("Biometric embedding decrypt error: %s", exc)
        return None
