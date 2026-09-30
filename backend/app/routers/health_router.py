from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.api.deps import get_db

router = APIRouter()


@router.get("/health")
def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "service": "VisionCore 2.0"}


@router.get("/health/liveness")
def liveness_check():
    """Kubernetes liveness probe endpoint."""
    return {"status": "ALIVE", "service": "VisionCore 2.0"}


@router.get("/health/readiness")
def readiness_check(db: Session = Depends(get_db)):
    """Kubernetes readiness probe endpoint."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "READY", "service": "VisionCore 2.0", "database": "connected"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"status": "NOT_READY", "database": str(e)})