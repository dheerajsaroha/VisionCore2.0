import functools
import logging
import io
import numpy as np
from typing import Tuple

logger = logging.getLogger(__name__)


class LivenessEngineUnavailableError(RuntimeError):
    """Raised when the anti-spoofing backend itself cannot run.

    This is an infrastructure/dependency fault, not a spoof verdict. It must
    never be reported to the caller as "LIVENESS_FAILED", otherwise a missing
    package looks identical to a presentation-attack rejection.
    """


@functools.lru_cache(maxsize=1)
def _load_deepface():
    """Import DeepFace once and cache the result (success or failure)."""
    try:
        from deepface import DeepFace  # type: ignore[import-untyped]
    except Exception as exc:
        raise LivenessEngineUnavailableError(
            "Anti-spoofing backend is not installed or failed to import. "
            "Install the biometric extras (deepface/tensorflow) or set "
            "LIVENESS_STRICT_MODE=False for local development. "
            f"Import error: {exc}"
        ) from exc
    return DeepFace


_ENGINE_FAULT_MARKERS = (
    "no module named",
    "cannot import name",
    "modulenotfounderror",
    "importerror",
    "failed to download",
    "downloaderror",
    "connectionerror",
    "max retries exceeded",
    "urlopen error",
    "urlerror",
    "temporary failure in name resolution",
    "unauthorized",
    "confirm that opencv is installed",
)


def _is_engine_fault(exc: BaseException) -> bool:
    """True when the anti-spoofing backend could not run at all.

    Distinguishes a broken/uninstalled model stack or an unreachable weight
    download from a genuine "this is a spoof" verdict.
    """
    if isinstance(exc, (ImportError, OSError, ConnectionError)):
        return True
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in _ENGINE_FAULT_MARKERS)


class LivenessService:
    @staticmethod
    def detect_liveness(image_bytes: bytes) -> Tuple[bool, float]:
        """Detects if the face in the image is a real person or a spoof.

        Uses DeepFace's MiniFASNet anti-spoofing model.
        Returns (is_live, confidence_score).

        Raises LivenessEngineUnavailableError when the anti-spoofing backend
        cannot run; any genuine detection/decoding failure returns (False, 0.0).
        """
        try:
            from PIL import Image

            DeepFace = _load_deepface()

            if not image_bytes:
                logger.warning("Liveness detect_liveness: empty image_bytes")
                return False, 0.0

            logger.info("Starting liveness detection")

            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            image_array = np.array(image)

            logger.info(
                "Liveness image size: %s",
                getattr(image_array, "shape", None),
            )
            logger.info("Liveness image dtype: %s", getattr(image_array, "dtype", None))

            # Ensure uint8 RGB array
            if image_array.dtype != np.uint8:
                logger.info("Converting liveness array dtype %s -> uint8", image_array.dtype)
                image_array = image_array.astype(np.uint8)

            if image_array.ndim != 3 or image_array.shape[2] != 3:
                logger.warning(
                    "Unexpected liveness image channels/ndim: ndim=%s shape=%s",
                    image_array.ndim,
                    image_array.shape,
                )

            logger.info(
                "DeepFace liveness preprocessing ready. height=%s width=%s channels=%s",
                image_array.shape[0] if image_array.ndim >= 1 else None,
                image_array.shape[1] if image_array.ndim >= 2 else None,
                image_array.shape[2] if image_array.ndim >= 3 else None,
            )

            # DeepFace: attempt 1 strict detection, then fallback non-strict.
            faces = None
            detection_path = None
            try:
                detection_path = "enforce_detection=True"
                faces = DeepFace.extract_faces(
                    img_path=image_array,
                    anti_spoofing=True,
                    enforce_detection=True,
                )
                logger.info(
                    "DeepFace extract_faces path=%s returned faces=%s",
                    detection_path,
                    len(faces) if faces is not None else None,
                )
            except Exception as e1:
                logger.warning(
                    "DeepFace enforce_detection=True failed; attempting enforce_detection=False. err=%s",
                    str(e1),
                )
                detection_path = "enforce_detection=False"
                faces = DeepFace.extract_faces(
                    img_path=image_array,
                    anti_spoofing=True,
                    enforce_detection=False,
                )
                logger.info(
                    "DeepFace extract_faces path=%s returned faces=%s",
                    detection_path,
                    len(faces) if faces is not None else None,
                )

            detected_faces_count = len(faces) if faces is not None else 0
            logger.info("Faces detected: %s (path=%s)", detected_faces_count, detection_path)

            if detected_faces_count == 0:
                # Prevent hard failure; caller decides whether to block.
                return False, 0.0

            face_info = faces[0] if faces else {}
            is_live = face_info.get("is_real", False)
            confidence = face_info.get("antispoof_score", 0.0)

            logger.info("Liveness score=%s is_live=%s", confidence, is_live)
            return bool(is_live), float(confidence)

        except LivenessEngineUnavailableError:
            raise
        except ValueError as e:
            logger.warning("Liveness detection: No face detected. %s", e)
            return False, 0.0
        except Exception as e:
            if _is_engine_fault(e):
                logger.error("Liveness engine fault: %s", e)
                raise LivenessEngineUnavailableError(
                    "Anti-spoofing backend failed to run: %s" % e
                ) from e
            logger.exception("Liveness detection error: %s", e)
            return False, 0.0


liveness_service = LivenessService()







