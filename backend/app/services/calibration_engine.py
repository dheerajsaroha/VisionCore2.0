"""
calibration_engine.py — Calibration Session Engine for Rating Normalization
Sprint 4 — Entity 1: Performance Management System
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db.models.all_models import (
    CalibrationSession, PerformanceRating, PerformanceReview,
    User, Department
)
from app.services.rating_normalization import rating_normalization


class CalibrationEngine:
    """Enterprise calibration session management for cross-team
    rating normalization and fairness enforcement."""

    @staticmethod
    def create_session(db: Session, org_id: UUID, cycle_id: int,
                       facilitator_user_id: int,
                       notes: Optional[str] = None) -> CalibrationSession:
        """Create a new calibration session."""
        session = CalibrationSession(
            organization_id=org_id,
            cycle_id=cycle_id,
            facilitator_user_id=facilitator_user_id,
            status="open",
            notes=notes,
            calibration_data={}
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def calibrate_rating(db: Session, session_id: int, user_id: int,
                         calibrated_rating: float) -> Dict[str, Any]:
        """Apply calibration adjustment to a user's rating within a session."""
        session = db.query(CalibrationSession).filter(CalibrationSession.id == session_id).first()
        if not session:
            return {"error": "Calibration session not found"}

        # Update the calibration data
        cal_data = session.calibration_data or {}
        cal_data[str(user_id)] = {
            "calibrated_rating": calibrated_rating,
            "calibrated_at": datetime.now(timezone.utc).isoformat()
        }
        session.calibration_data = cal_data
        db.add(session)

        # Update the actual PerformanceRating
        rating = db.query(PerformanceRating).filter(
            PerformanceRating.organization_id == session.organization_id,
            PerformanceRating.cycle_id == session.cycle_id,
            PerformanceRating.user_id == user_id
        ).first()

        if rating:
            rating.is_calibrated = True
            rating.calibrated_rating = calibrated_rating
            rating.final_rating = calibrated_rating
            rating.rating_label = rating_normalization.resolve_rating_label(calibrated_rating)
            db.add(rating)

        db.commit()
        db.refresh(session)

        return {
            "session_id": session.id,
            "user_id": user_id,
            "calibrated_rating": calibrated_rating,
            "session_status": session.status,
            "total_calibrated": len(session.calibration_data or {})
        }

    @staticmethod
    def complete_session(db: Session, session_id: int,
                         final_notes: Optional[str] = None) -> CalibrationSession:
        """Mark a calibration session as completed."""
        session = db.query(CalibrationSession).filter(CalibrationSession.id == session_id).first()
        if session:
            session.status = "completed"
            if final_notes:
                session.notes = (session.notes or "") + "\n\n" + final_notes
            db.add(session)
            db.commit()
            db.refresh(session)
        return session

    @staticmethod
    def get_session_details(db: Session, session_id: int,
                            org_id: UUID) -> Dict[str, Any]:
        """Get detailed calibration session info with ratings."""
        session = db.query(CalibrationSession).filter(
            CalibrationSession.id == session_id,
            CalibrationSession.organization_id == org_id
        ).first()

        if not session:
            return {}

        # Get all ratings for this cycle
        ratings = db.query(PerformanceRating).filter(
            PerformanceRating.organization_id == org_id,
            PerformanceRating.cycle_id == session.cycle_id
        ).all()

        cal_data = session.calibration_data or {}
        rating_details = []
        for r in ratings:
            user = db.query(User).filter(User.id == r.user_id).first()
            user_cal = cal_data.get(str(r.user_id), {})
            rating_details.append({
                "user_id": r.user_id,
                "user_name": user.full_name if user else "Unknown",
                "department": user.department.name if user and user.department else "N/A",
                "original_rating": float(r.final_rating or r.kpi_score or 3.0) if not r.is_calibrated else None,
                "calibrated_rating": float(user_cal.get("calibrated_rating", r.calibrated_rating)) if r.is_calibrated else None,
                "is_calibrated": r.is_calibrated,
                "rating_label": r.rating_label
            })

        # Bell curve before and after
        pre_curve = rating_normalization.compute_bell_curve(db, org_id, session.cycle_id)

        return {
            "session_id": session.id,
            "cycle_id": session.cycle_id,
            "facilitator_user_id": session.facilitator_user_id,
            "status": session.status,
            "notes": session.notes,
            "total_participants": len(rating_details),
            "calibrated_count": len(cal_data),
            "ratings": rating_details,
            "bell_curve": pre_curve,
            "created_at": session.created_at.isoformat()
        }

    @staticmethod
    def get_session_list(db: Session, org_id: UUID,
                          cycle_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List calibration sessions for an organization."""
        q = db.query(CalibrationSession).filter(CalibrationSession.organization_id == org_id)
        if cycle_id:
            q = q.filter(CalibrationSession.cycle_id == cycle_id)

        sessions = q.order_by(CalibrationSession.created_at.desc()).all()

        results = []
        for s in sessions:
            facilitator = db.query(User).filter(User.id == s.facilitator_user_id).first()
            results.append({
                "id": s.id,
                "cycle_id": s.cycle_id,
                "facilitator_name": facilitator.full_name if facilitator else "Unknown",
                "status": s.status,
                "total_calibrated": len(s.calibration_data or {}),
                "notes": s.notes,
                "created_at": s.created_at.isoformat()
            })

        return results


calibration_engine = CalibrationEngine()

