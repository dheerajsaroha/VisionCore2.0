<<<<<<< HEAD
import uuid
=======
from datetime import datetime, timezone
>>>>>>> refs/remotes/origin/main
from typing import Optional
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.db.models.all_models import AttendanceLog
from app.schema.attendance import CheckInRequest
from pydantic import BaseModel

from app.core.config import settings

class CheckInUpdate(BaseModel):
    pass

class CRUDAttendance(CRUDBase[AttendanceLog, CheckInRequest, CheckInUpdate]):
    def log_check_in(self, db: Session, *, obj_in: CheckInRequest, status: str) -> AttendanceLog:
        db_obj = AttendanceLog(
            user_id=obj_in.user_id,
            # Always use server-side UTC timestamp — never trust client-supplied time.
            # BUG-10 fix: client previously controlled check_in via obj_in.timestamp.
            check_in=datetime.now(timezone.utc),
            status=status,
            emotion=obj_in.emotion,
            emotion_score=obj_in.emotion_score,
            is_live=obj_in.is_live,
            source=obj_in.source,
            geofence_pass=obj_in.geofence_pass,
            gps_lat=obj_in.gps_lat,
            gps_lng=obj_in.gps_lng,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def verify_user_face(
        self,
        db: Session,
        *,
        user_id: int,
        embedding: list[float],
        threshold: float | None = None,
    ) -> tuple[bool, float | None]:
        """
        Verify that a face embedding matches a specific user's enrolled biometric template.
        Returns (is_match, distance).
        """
        from app.db.models.all_models import FaceEmbedding
        from sqlalchemy import select

        if threshold is None:
            threshold = settings.FACE_DISTANCE_THRESHOLD

        stmt = (
            select(FaceEmbedding, FaceEmbedding.embedding.l2_distance(embedding).label("distance"))
            .where(FaceEmbedding.user_id == user_id)
            .where(FaceEmbedding.is_active == 1)
            .order_by(FaceEmbedding.embedding.l2_distance(embedding))
            .limit(1)
        )
        row = db.execute(stmt).first()

        if not row or row.distance is None:
            # If no active template enrolled, allow or require enrollment
            return True, None

        is_match = row.distance <= threshold
        return is_match, float(row.distance)

    def find_user_by_face(
        self,
        db: Session,
        *,
        embedding: list[float],
        threshold: float | None = None,
        org_id: uuid.UUID | None = None,
    ) -> Optional[int]:
        """
        Find the user who matches the given face embedding.

        CRITICAL TENANT ISOLATION:
        When ``org_id`` is provided, the vector search is scoped to embeddings
        belonging to users in that organization only.
        """
        from app.db.models.all_models import FaceEmbedding, User
        from sqlalchemy import select

        if threshold is None:
            threshold = settings.FACE_DISTANCE_THRESHOLD

        stmt = (
            select(FaceEmbedding, FaceEmbedding.embedding.l2_distance(embedding).label("distance"))
            .join(User, User.id == FaceEmbedding.user_id)
            .where(FaceEmbedding.is_active == 1)
            .where(User.is_deleted == 0)
            .order_by(FaceEmbedding.embedding.l2_distance(embedding))
            .limit(1)
        )
        if org_id is not None:
            stmt = stmt.where(User.org_id == org_id)

        row = db.execute(stmt).first()

        if row and row.distance is not None and row.distance <= threshold:
            return row.FaceEmbedding.user_id
        return None

attendance = CRUDAttendance(AttendanceLog)
