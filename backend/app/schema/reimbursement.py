from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
import uuid

class ReimbursementBase(BaseModel):
    amount: float
    reason: str
    receipt_url: Optional[str] = None

class ReimbursementCreate(ReimbursementBase):
    pass

class ReimbursementUpdate(BaseModel):
    status: Optional[str] = None
    processed_at: Optional[datetime] = None

class ReimbursementResponse(ReimbursementBase):
    id: int
    user_id: int
    org_id: uuid.UUID
    status: str
    submitted_at: datetime
    processed_at: Optional[datetime]
    approved_by: Optional[int]

    model_config = ConfigDict(from_attributes=True)
