from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

class CheckInRequest(BaseModel):
    user_id: Optional[int] = None
    image_base64: Optional[str] = Field(None, max_length=5000000) # 5MB limit
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    face_embedding: Optional[List[float]] = None
    is_live: int = 0
    emotion: Optional[str] = None
    emotion_score: Optional[float] = None
    source: str = Field("ai", pattern="^(ai|manual|edge|bulk_import)$")
    geofence_pass: Optional[int] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None


class AttendanceLogResponse(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    check_in: datetime
    check_out: Optional[datetime] = None
    break_start: Optional[datetime] = None
    break_end: Optional[datetime] = None
    status: str
    emotion: Optional[str] = None
    is_live: int
    recognition_distance: Optional[float] = None
    source: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

        
class CheckOutRequest(BaseModel):
    user_id: Optional[int] = None
    image_base64: Optional[str] = Field(None, max_length=5000000)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SyncLogsRequest(BaseModel):
    logs: List[CheckInRequest]
