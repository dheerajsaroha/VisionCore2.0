"""
organization_domain_service.py — VisionCore 3.0 Organization & Provisioning Domain Services

Encapsulates enterprise organization model, multi-step stateful provisioning engine,
legal entities, business units, branches, teams, cost centers, and visual hierarchy builder.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.all_models import (
    Branch,
    BusinessUnit,
    CostCenter,
    Department,
    JobPosition,
    LegalEntity,
    Organization,
    OrganizationProvisioning,
    Role,
    Team,
    User,
)
from app.services.audit_service import audit_service
from app.services.event_bus import event_bus

logger = logging.getLogger(__name__)

# Valid state machine transitions
LIFECYCLE_TRANSITIONS = {
    "PENDING": ["VALIDATING"],
    "VALIDATING": ["PROVISIONING", "FAILED"],
    "PROVISIONING": ["CONFIGURING", "FAILED"],
    "CONFIGURING": ["ACTIVE", "FAILED"],
    "ACTIVE": ["SUSPENDED", "ARCHIVED"],
    "SUSPENDED": ["ACTIVE", "ARCHIVED"],
    "ARCHIVED": ["DELETED", "ACTIVE"],
    "DELETED": [],
}


class OrganizationProvisioningService:
    """Stateful, transactional, idempotent organization provisioning engine."""

    def start_provisioning(
        self, db: Session, org_id: UUID, initiated_by_email: Optional[str] = None
    ) -> OrganizationProvisioning:
        rec = (
            db.query(OrganizationProvisioning)
            .filter(OrganizationProvisioning.org_id == org_id)
            .first()
        )
        if not rec:
            rec = OrganizationProvisioning(
                org_id=org_id,
                state="PENDING",
                steps_completed=[],
                initiated_by_email=initiated_by_email,
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)
        return rec

    def transition_state(
        self, db: Session, org_id: UUID, new_state: str, error_info: Optional[Dict] = None
    ) -> OrganizationProvisioning:
        rec = (
            db.query(OrganizationProvisioning)
            .filter(OrganizationProvisioning.org_id == org_id)
            .first()
        )
        if not rec:
            rec = OrganizationProvisioning(org_id=org_id, state="PENDING", steps_completed=[])
            db.add(rec)

        current_state = rec.state
        if new_state not in LIFECYCLE_TRANSITIONS.get(current_state, []) and new_state != "FAILED":
            logger.warning(
                "Bypassing strict state transition check for provisioning: %s -> %s",
                current_state,
                new_state,
            )

        rec.state = new_state
        if error_info:
            rec.error_log = error_info
        db.add(rec)

        # Update Organization model status as well
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if org:
            org.status = new_state
            if new_state == "ACTIVE":
                org.is_active = True
            elif new_state in ["SUSPENDED", "ARCHIVED", "DELETED"]:
                org.is_active = False
            db.add(org)

        db.commit()
        db.refresh(rec)

        # Audit log and event publish
        audit_service.record(
            tenant_id=str(org_id),
            actor_id="system",
            action="organization.state_changed",
            target_type="organization",
            target_id=str(org_id),
            after_state={"state": new_state, "previous": current_state},
        )

        event_bus.publish(
            "organization.state_changed",
            {
                "org_id": str(org_id),
                "previous_state": current_state,
                "new_state": new_state,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return rec

    def execute_full_provisioning_workflow(
        self,
        db: Session,
        org_name: str,
        legal_id: str,
        admin_email: str,
        admin_name: str,
        primary_color: str = "#4F46E5",
    ) -> Dict[str, Any]:
        """Runs complete multi-step transactional provisioning workflow."""
        org = db.query(Organization).filter(Organization.legal_id == legal_id).first()
        if not org:
            org = Organization(
                name=org_name,
                legal_id=legal_id,
                primary_color=primary_color,
                is_active=True,
                status="PENDING",
            )
            db.add(org)
            db.commit()
            db.refresh(org)

            # Provision the default plan immediately so the new tenant is not
            # locked out by subscription enforcement before an admin can act.
            from app.services.subscription_service import subscription_service

            subscription_service.ensure_default_subscription(db, org.id)

        prov = self.start_provisioning(db, org.id, initiated_by_email=admin_email)
        completed_steps = list(prov.steps_completed or [])

        def _step(step_name: str, fn):
            nonlocal completed_steps
            if step_name in completed_steps:
                return
            fn()
            completed_steps.append(step_name)
            prov.steps_completed = list(completed_steps)
            db.add(prov)
            db.commit()

        try:
            self.transition_state(db, org.id, "VALIDATING")
            # Step 1: Legal Entity Baseline
            def step_1():
                le = (
                    db.query(LegalEntity)
                    .filter(LegalEntity.org_id == org.id, LegalEntity.registration_number == legal_id)
                    .first()
                )
                if not le:
                    db.add(
                        LegalEntity(
                            org_id=org.id,
                            name=f"{org_name} Legal Corp",
                            legal_name=f"{org_name} Private Limited",
                            registration_number=legal_id,
                            tax_id=f"TAX-{legal_id}",
                            country="India",
                            currency="INR",
                        )
                    )

            _step("step_1_legal_entity", step_1)

            self.transition_state(db, org.id, "PROVISIONING")
            # Step 2: Business Unit Baseline
            def step_2():
                bu = db.query(BusinessUnit).filter(BusinessUnit.org_id == org.id).first()
                if not bu:
                    db.add(
                        BusinessUnit(
                            org_id=org.id,
                            code="BU-HQ",
                            name="Headquarters Division",
                            description="Primary corporate division",
                        )
                    )

            _step("step_2_business_unit", step_2)

            # Step 3: Branch Baseline
            def step_3():
                br = db.query(Branch).filter(Branch.org_id == org.id).first()
                if not br:
                    db.add(
                        Branch(
                            org_id=org.id,
                            code="BR-HQ",
                            name="Main Corporate Office",
                            branch_type="HQ",
                            city="Bengaluru",
                            country="India",
                            timezone="Asia/Kolkata",
                        )
                    )

            _step("step_3_branch", step_3)

            # Step 4: Departments Baseline
            def step_4():
                depts = ["Executive", "Engineering", "Human Resources", "Finance & Operations"]
                for d_name in depts:
                    exists = (
                        db.query(Department)
                        .filter(Department.org_id == org.id, Department.name == d_name)
                        .first()
                    )
                    if not exists:
                        db.add(
                            Department(
                                org_id=org.id,
                                name=d_name,
                                description=f"Default {d_name} Department",
                                is_deleted=0,
                            )
                        )

            _step("step_4_departments", step_4)

            # Step 5: Cost Center Baseline
            def step_5():
                cc = db.query(CostCenter).filter(CostCenter.org_id == org.id).first()
                if not cc:
                    db.add(
                        CostCenter(
                            org_id=org.id,
                            code="CC-100",
                            name="Corporate Operations",
                            annual_budget=1000000.0,
                        )
                    )

            _step("step_5_cost_center", step_5)

            self.transition_state(db, org.id, "CONFIGURING")
            # Step 6: Platform Settings & Policies Initialization
            def step_6():
                org.primary_color = primary_color
                db.add(org)

            _step("step_6_settings_branding", step_6)

            self.transition_state(db, org.id, "ACTIVE")

            event_bus.publish(
                "OrganizationCreated",
                {
                    "org_id": str(org.id),
                    "org_name": org.name,
                    "legal_id": legal_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            return {
                "org_id": str(org.id),
                "org_name": org.name,
                "status": "ACTIVE",
                "steps_completed": prov.steps_completed,
            }

        except Exception as exc:
            logger.error("Provisioning failed for org %s: %s", org.id, str(exc))
            self.transition_state(db, org.id, "FAILED", error_info={"error": str(exc)})
            raise


class LegalEntityService:
    def create(self, db: Session, org_id: UUID, data: Dict[str, Any]) -> LegalEntity:
        entity = LegalEntity(org_id=org_id, **data)
        db.add(entity)
        db.commit()
        db.refresh(entity)
        return entity

    def list(self, db: Session, org_id: UUID) -> List[LegalEntity]:
        return (
            db.query(LegalEntity)
            .filter(LegalEntity.org_id == org_id, LegalEntity.is_deleted == 0)
            .order_by(LegalEntity.name)
            .all()
        )


class BusinessUnitService:
    def create(self, db: Session, org_id: UUID, data: Dict[str, Any]) -> BusinessUnit:
        bu = BusinessUnit(org_id=org_id, **data)
        db.add(bu)
        db.commit()
        db.refresh(bu)
        return bu

    def list(self, db: Session, org_id: UUID) -> List[BusinessUnit]:
        return (
            db.query(BusinessUnit)
            .filter(BusinessUnit.org_id == org_id, BusinessUnit.is_deleted == 0)
            .order_by(BusinessUnit.name)
            .all()
        )


class BranchService:
    def create(self, db: Session, org_id: UUID, data: Dict[str, Any]) -> Branch:
        branch = Branch(org_id=org_id, **data)
        db.add(branch)
        db.commit()
        db.refresh(branch)
        return branch

    def list(self, db: Session, org_id: UUID) -> List[Branch]:
        return (
            db.query(Branch)
            .filter(Branch.org_id == org_id, Branch.is_deleted == 0)
            .order_by(Branch.name)
            .all()
        )


class TeamService:
    def create(self, db: Session, org_id: UUID, data: Dict[str, Any]) -> Team:
        team = Team(org_id=org_id, **data)
        db.add(team)
        db.commit()
        db.refresh(team)
        return team

    def list_by_dept(self, db: Session, org_id: UUID, dept_id: int) -> List[Team]:
        return (
            db.query(Team)
            .filter(Team.org_id == org_id, Team.dept_id == dept_id, Team.is_deleted == 0)
            .order_by(Team.name)
            .all()
        )


class CostCenterService:
    def create(self, db: Session, org_id: UUID, data: Dict[str, Any]) -> CostCenter:
        cc = CostCenter(org_id=org_id, **data)
        db.add(cc)
        db.commit()
        db.refresh(cc)
        return cc

    def list(self, db: Session, org_id: UUID) -> List[CostCenter]:
        return (
            db.query(CostCenter)
            .filter(CostCenter.org_id == org_id, CostCenter.is_deleted == 0)
            .order_by(CostCenter.code)
            .all()
        )


class HierarchyService:
    """Builds unified tree structure for visual hierarchy rendering."""

    def build_org_tree(self, db: Session, org_id: UUID) -> Dict[str, Any]:
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            return {}

        legal_entities = (
            db.query(LegalEntity)
            .filter(LegalEntity.org_id == org_id, LegalEntity.is_deleted == 0)
            .all()
        )
        business_units = (
            db.query(BusinessUnit)
            .filter(BusinessUnit.org_id == org_id, BusinessUnit.is_deleted == 0)
            .all()
        )
        departments = (
            db.query(Department)
            .filter(Department.org_id == org_id, Department.is_deleted == 0)
            .all()
        )
        teams = (
            db.query(Team)
            .filter(Team.org_id == org_id, Team.is_deleted == 0)
            .all()
        )
        positions = (
            db.query(JobPosition)
            .filter(JobPosition.org_id == org_id, JobPosition.is_deleted == 0)
            .all()
        )

        dept_tree = []
        for d in departments:
            d_teams = [
                {"id": t.id, "name": t.name, "lead_id": t.lead_user_id}
                for t in teams
                if t.dept_id == d.id
            ]
            d_positions = [
                {"id": p.id, "title": p.title, "code": p.code, "grade": p.grade}
                for p in positions
                if p.dept_id == d.id
            ]
            dept_tree.append(
                {
                    "id": d.id,
                    "name": d.name,
                    "description": d.description,
                    "teams": d_teams,
                    "positions": d_positions,
                }
            )

        return {
            "id": str(org.id),
            "name": org.name,
            "legal_id": org.legal_id,
            "status": org.status,
            "legal_entities": [
                {
                    "id": str(le.id),
                    "name": le.name,
                    "legal_name": le.legal_name,
                    "country": le.country,
                }
                for le in legal_entities
            ],
            "business_units": [
                {"id": bu.id, "code": bu.code, "name": bu.name} for bu in business_units
            ],
            "departments": dept_tree,
        }


organization_provisioning_service = OrganizationProvisioningService()
legal_entity_service = LegalEntityService()
business_unit_service = BusinessUnitService()
branch_service = BranchService()
team_service = TeamService()
cost_center_service = CostCenterService()
hierarchy_service = HierarchyService()
