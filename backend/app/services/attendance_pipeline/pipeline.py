from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.user_repo import UserRepository
import logging

from app.services.attendance_pipeline.metric import get_face_matching_config
from app.services.attendance_pipeline import stages
from app.services.liveness import LivenessEngineUnavailableError

logger = logging.getLogger(__name__)


class LivenessFailedError(PermissionError):
    def __init__(self, message="Liveness verification failed", code="LIVENESS_FAILED", score: float = 0.0):
        super().__init__(message)
        self.code = code
        self.score = score


class LivenessUnavailableError(RuntimeError):
    """Anti-spoofing engine is not runnable (missing/broken dependency).

    Distinct from LivenessFailedError so the API can answer 503 instead of a
    403 spoof rejection.
    """

    code = "LIVENESS_UNAVAILABLE"

    def __init__(self, message="Liveness verification is temporarily unavailable"):
        super().__init__(message)


@dataclass(frozen=True)
class FacePipelineOutput:
    user_id: int
    emotion: Optional[str]
    is_live: int


class FaceAttendancePipeline:
    """Detection → Liveness → Embedding → Vector search → Thresholding."""

    def __init__(
        self,
        *,
        attendance_repo: AttendanceRepository,
        user_repo: UserRepository,
    ):
        self.attendance_repo = attendance_repo
        self.user_repo = user_repo

    def run(
        self,
        db: Session,
        *,
        image_bytes: bytes,
        existing_user_id: Optional[int] = None,
        org_id: UUID | None = None,
    ) -> FacePipelineOutput:
        liveness_enabled = getattr(settings, "LIVENESS_CHECK_ENABLED", True)
        strict_mode = getattr(settings, "LIVENESS_STRICT_MODE", True)

        if not liveness_enabled:
            logger.warning("Liveness check disabled via LIVENESS_CHECK_ENABLED; skipping verification")
            return self._run_recognition(
                db,
                image_bytes=image_bytes,
                existing_user_id=existing_user_id,
                org_id=org_id,
                is_live=0,
            )

        try:
            liveness_res = stages.extract_liveness(image_bytes)
        except LivenessEngineUnavailableError as exc:
            logger.error("Liveness engine unavailable: %s", exc)
            if strict_mode:
                raise LivenessUnavailableError() from exc
            logger.warning(
                "Anti-spoofing engine unavailable but LIVENESS_STRICT_MODE is OFF; continuing"
            )
            return self._run_recognition(
                db,
                image_bytes=image_bytes,
                existing_user_id=existing_user_id,
                org_id=org_id,
                is_live=0,
            )

        is_live = liveness_res.is_live

        # Phase-3 requirement: block recognition if liveness is not passed.
        # Development/debug mode: allow fallback when liveness is unreliable.
        if is_live != 1:
            if strict_mode is False:
                logger.warning("Liveness failed (is_live=%s) but strict mode is OFF; continuing to recognition", is_live)
            else:
                raise LivenessFailedError("Liveness check failed", score=float(is_live))

        return self._run_recognition(
            db,
            image_bytes=image_bytes,
            existing_user_id=existing_user_id,
            org_id=org_id,
            is_live=is_live,
        )

    def _run_recognition(
        self,
        db: Session,
        *,
        image_bytes: bytes,
        existing_user_id: Optional[int],
        org_id: UUID | None,
        is_live: int,
    ) -> FacePipelineOutput:
        if existing_user_id is not None:
            return FacePipelineOutput(user_id=existing_user_id, emotion=None, is_live=is_live)

        embedding_res = stages.extract_embedding(image_bytes)
        match_cfg = get_face_matching_config()

        match_res = stages.match_by_vector(
            db,
            embedding=embedding_res.embedding,
            threshold=match_cfg.threshold,
            org_id=org_id,
            attendance_repo=self.attendance_repo,
        )

        if not match_res.matched_user_id:
            raise LookupError("Identity not found")

        emotion_res = stages.extract_emotion(image_bytes)

        return FacePipelineOutput(
            user_id=match_res.matched_user_id,
            emotion=emotion_res.emotion,
            is_live=is_live,
        )
