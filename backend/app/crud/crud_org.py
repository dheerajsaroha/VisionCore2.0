from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.db.models.all_models import Organization
from app.schema.org import OrganizationCreate, OrganizationUpdate
from typing import Optional
from uuid import UUID

class CRUDOrganization(CRUDBase[Organization, OrganizationCreate, OrganizationUpdate]):
    def get_by_legal_id(self, db: Session, *, legal_id: str) -> Optional[Organization]:
        return db.query(Organization).filter(Organization.legal_id == legal_id).first()

    def list(
        self, db: Session, *, skip: int = 0, limit: int = 50,
        search: Optional[str] = None, include_inactive: bool = False,
    ) -> list[Organization]:
        query = db.query(Organization)
        if not include_inactive:
            query = query.filter(Organization.is_active.is_(True))
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                Organization.name.ilike(term) | Organization.legal_id.ilike(term)
            )
        return query.order_by(Organization.created_at.desc()).offset(skip).limit(limit).all()

    def set_active(self, db: Session, *, org_id: UUID, is_active: bool) -> Optional[Organization]:
        org = self.get(db, id=org_id)
        if not org:
            return None
        org.is_active = is_active
        db.add(org)
        db.commit()
        db.refresh(org)
        return org

organization = CRUDOrganization(Organization)
