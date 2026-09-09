import uuid
from datetime import datetime, timezone
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
        existing = (
            db.query(AttendanceLog)
            .filter(
                AttendanceLog.user_id == obj_in.user_id,
                AttendanceLog.is_deleted == 0,
                AttendanceLog.check_out.is_(None),
            )
            .first()
        )
        if existing:
            raise ValueError("You already have an active check-in. Please check out first.")

        db_obj = AttendanceLog(
            user_id=obj_in.user_id,
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

    def log_check_out(
        self,
        db: Session,
        *,
        user_id: int,
        timestamp: Optional[datetime] = None,
    ) -> AttendanceLog:
        """
        Record check-out for the user's active check-in record.
        """
        now = timestamp or datetime.now(timezone.utc)
        stmt = (
            db.query(AttendanceLog)
            .filter(
                AttendanceLog.user_id == user_id,
                AttendanceLog.is_deleted == 0,
                AttendanceLog.check_out.is_(None),
            )
            .order_by(AttendanceLog.check_in.desc())
        )
        active_log = stmt.first()
        if not active_log:
            raise ValueError("No active check-in found for check-out.")

        active_log.check_out = now
        db.commit()
        db.refresh(active_log)
        return active_log

    def log_break_start(
        self,
        db: Session,
        *,
        user_id: int,
        timestamp: Optional[datetime] = None,
    ) -> AttendanceLog:
        now = timestamp or datetime.now(timezone.utc)
        active_log = (
            db.query(AttendanceLog)
            .filter(
                AttendanceLog.user_id == user_id,
                AttendanceLog.is_deleted == 0,
                AttendanceLog.check_out.is_(None),
                AttendanceLog.break_start.is_(None),
            )
            .order_by(AttendanceLog.check_in.desc())
            .first()
        )
        if not active_log:
            raise ValueError("No active check-in found for break start.")
        active_log.break_start = now
        db.commit()
        db.refresh(active_log)
        return active_log

    def log_break_end(
        self,
        db: Session,
        *,
        user_id: int,
        timestamp: Optional[datetime] = None,
    ) -> AttendanceLog:
        now = timestamp or datetime.now(timezone.utc)
        active_log = (
            db.query(AttendanceLog)
            .filter(
                AttendanceLog.user_id == user_id,
                AttendanceLog.is_deleted == 0,
                AttendanceLog.check_out.is_(None),
                AttendanceLog.break_start.is_not(None),
                AttendanceLog.break_end.is_(None),
            )
            .order_by(AttendanceLog.check_in.desc())
            .first()
        )
        if not active_log:
            raise ValueError("No active break found for break end.")
        active_log.break_end = now
        db.commit()
        db.refresh(active_log)
        return active_log


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
            stmt = stmt.where(FaceEmbedding.org_id == org_id)

        row = db.execute(stmt).first()

        if row and row.distance is not None and row.distance <= threshold:
            return row.FaceEmbedding.user_id
        return None

attendance = CRUDAttendance(AttendanceLog)
