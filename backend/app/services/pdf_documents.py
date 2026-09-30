"""
Shared PDF document storage.

Payslips and offer letters both need to persist a rendered document and later
serve it back. The storage boundary matters: a database row is trusted input
here, and a tampered or stale row must never be able to read arbitrary files
off disk. Keeping one implementation means one security boundary to audit
rather than two that can drift apart.

Local paths are resolved against a base directory that is anchored to the
backend package root, not the process working directory, so documents stay
readable regardless of how the app was launched (gunicorn, uvicorn, pytest).
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from typing import Optional

from app.services.file_service import LocalStorageProvider, S3StorageProvider

logger = logging.getLogger(__name__)

# Root directory for locally stored documents.
#
# Anchored to the backend package root rather than os.getcwd(): a CWD-relative
# base would make stored paths unreadable under a different launcher.
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_STORAGE_DIR = os.path.join(BACKEND_ROOT, "app_data", "uploads")

# Subdirectory per document class, so payslips and offers stay separated.
SUBDIR_PAYSLIPS = "payslips"
SUBDIR_OFFER_LETTERS = "offer_letters"


class PDFStorageError(Exception):
    """Raised when a stored path points outside the document storage root."""


def storage_provider():
    """Local disk by default; S3 when the bucket is configured."""
    bucket = os.getenv("AWS_S3_BUCKET")
    if bucket:
        return S3StorageProvider(bucket_name=bucket)
    base_dir = os.getenv("PDF_STORAGE_DIR") or DEFAULT_STORAGE_DIR
    return LocalStorageProvider(base_dir=os.path.abspath(base_dir))


def store_pdf(
    file_id: str,
    content: bytes,
    *,
    org_id,
    subdir: str,
) -> str:
    """
    Persist a rendered PDF and return its storage path.

    `file_id` must be derived from server-side values (never raw user input),
    since it becomes a filesystem name.
    """
    provider = storage_provider()
    if _safe_name(file_id) != file_id:
        raise ValueError("Document id must not contain path separators")
    return provider.store(file_id, content, path_prefix=f"{org_id}/{subdir}")


def read_pdf(storage_path: str) -> bytes:
    """
    Read a stored PDF.

    Raises:
        PDFStorageError: the path escapes the storage root.
        FileNotFoundError: the path is valid but the file is gone.
    """
    if not storage_path:
        raise PDFStorageError("Document has no stored file path")

    provider = storage_provider()

    # S3 keys are addressed by the provider, not the local filesystem.
    if storage_path.startswith("s3://"):
        return provider.retrieve(storage_path)

    base_real = os.path.realpath(getattr(provider, "base_dir", DEFAULT_STORAGE_DIR))

    candidates = (
        [storage_path]
        if os.path.isabs(storage_path)
        else [os.path.join(base_real, storage_path)]
    )
    # Paths written before the base dir was package-anchored carry a redundant
    # 'app_data/uploads' prefix relative to the base dir; strip and retry.
    legacy_prefix = "app_data" + os.sep + "uploads" + os.sep
    if not os.path.isabs(storage_path) and storage_path.startswith(legacy_prefix):
        candidates.append(os.path.join(base_real, storage_path[len(legacy_prefix):]))

    contained = False
    for candidate in candidates:
        target_real = os.path.realpath(candidate)
        if target_real != base_real and not target_real.startswith(base_real + os.sep):
            # Never open a candidate that escapes the storage root.
            continue
        contained = True
        if os.path.isfile(target_real):
            return provider.retrieve(target_real)

    # A valid location with no file is recoverable by re-rendering, so it must
    # not be reported as a permissions problem.
    if contained:
        raise FileNotFoundError(f"Document not found: {storage_path}")
    raise PDFStorageError("Refusing to read a document outside the storage directory")


def _safe_name(value: str) -> str:
    """Reject anything that could escape the target directory."""
    if not value:
        raise ValueError("Document id is required")
    if os.path.basename(value) != value:
        raise ValueError("Document id must be a bare filename")
    if ".." in value or "\x00" in value:
        raise ValueError("Document id contains an illegal sequence")
    return value


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def long_date(value: Optional[datetime]) -> str:
    """e.g. '05 Oct 2026'."""
    if value is None:
        return "—"
    return value.strftime("%d %b %Y")
