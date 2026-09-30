from typing import List, Optional
from sqlalchemy.orm import Session
import uuid

from app.crud.base import CRUDBase
from app.db.models.all_models import OrgApiKey
from pydantic import BaseModel

class ApiKeyCreateInternal(BaseModel):
    org_id: uuid.UUID
    key_hash: str
    scope: str = "camera_edge"
    rate_limit: int = 60

class ApiKeyUpdateInternal(BaseModel):
    is_revoked: Optional[bool] = None

class CRUDOrgApiKey(CRUDBase[OrgApiKey, ApiKeyCreateInternal, ApiKeyUpdateInternal]):
    def get_multi_by_org(
        self, db: Session, *, org_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> List[OrgApiKey]:
        return (
            db.query(self.model)
            .filter(OrgApiKey.org_id == org_id)
            .order_by(OrgApiKey.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        
    def revoke(self, db: Session, *, db_obj: OrgApiKey) -> OrgApiKey:
        db_obj.is_revoked = True
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

api_key = CRUDOrgApiKey(OrgApiKey)
