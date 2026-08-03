"""
test_org_identity_domain.py — Unit & Integration Tests for Organization & Identity Domain
"""

import uuid
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock, patch

from app.db.models.all_models import (
    Branch,
    BusinessUnit,
    CostCenter,
    EmploymentRecord,
    IdentityHistory,
    JobPosition,
    LegalEntity,
    Organization,
    OrganizationProvisioning,
    Team,
    User,
)
from app.services.identity_employment_service import (
    employment_service,
    identity_service,
    position_service,
)
from app.services.organization_domain_service import (
    branch_service,
    business_unit_service,
    cost_center_service,
    hierarchy_service,
    legal_entity_service,
    organization_provisioning_service,
    team_service,
)


def test_provisioning_service_flow():
    db = MagicMock()
    org_id = uuid.uuid4()

    org = Organization(id=org_id, name="Acme Test", legal_id="REG-100", status="PENDING")
    prov = OrganizationProvisioning(org_id=org_id, state="PENDING", steps_completed=[])

    def mock_query(model):
        m = MagicMock()
        if model == OrganizationProvisioning:
            m.filter.return_value.first.return_value = prov
        elif model == Organization:
            m.filter.return_value.first.return_value = org
        else:
            m.filter.return_value.first.return_value = None
        return m

    db.query.side_effect = mock_query

    with patch("app.services.audit_service.audit_service.record") as mock_audit, \
         patch("app.services.event_bus.event_bus.publish") as mock_event:
        res = organization_provisioning_service.execute_full_provisioning_workflow(
            db=db,
            org_name="Acme Test",
            legal_id="REG-100",
            admin_email="admin@acme.com",
            admin_name="Test Admin",
        )
        assert res["status"] == "ACTIVE"
        assert "step_1_legal_entity" in res["steps_completed"]


def test_identity_service_activate_suspend():
    db = MagicMock()
    org_id = uuid.uuid4()
    user = User(id=1, org_id=org_id, email="emp@acme.com", is_active=1)
    db.query().filter().first.return_value = user

    with patch("app.services.audit_service.audit_service.record"), \
         patch("app.services.event_bus.event_bus.publish"):
        # Suspend
        suspended_user = identity_service.suspend_identity(
            db=db, org_id=org_id, user_id=1, reason="Test suspension"
        )
        assert suspended_user.is_active == 0

        # Activate
        activated_user = identity_service.activate_identity(
            db=db, org_id=org_id, user_id=1
        )
        assert activated_user.is_active == 1


def test_position_and_employment_service():
    db = MagicMock()
    org_id = uuid.uuid4()

    with patch("app.services.event_bus.event_bus.publish"):
        # Create Position
        pos = position_service.create_position(
            db=db,
            org_id=org_id,
            data={"code": "POS-ENG", "title": "Staff Engineer", "grade": "L4"},
        )
        assert pos.code == "POS-ENG"

        # Hire Employee
        db.query().filter().first.return_value = None
        rec = employment_service.hire_employee(
            db=db,
            org_id=org_id,
            user_id=10,
            data={"employment_type": "EMPLOYEE", "joining_date": datetime.now(timezone.utc)},
        )
        assert rec.status == "ACTIVE"


def test_hierarchy_service_builder():
    db = MagicMock()
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="Tree Org", legal_id="TREE-1", status="ACTIVE")

    db.query().filter().first.return_value = org
    db.query().filter().all.side_effect = [
        [LegalEntity(id=uuid.uuid4(), org_id=org_id, name="Tree Legal", legal_name="Tree Ltd", country="India")],
        [BusinessUnit(id=1, org_id=org_id, code="BU-1", name="Tree BU")],
        [],
        [],
        [],
    ]

    tree = hierarchy_service.build_org_tree(db=db, org_id=org_id)
    assert tree["name"] == "Tree Org"
    assert len(tree["legal_entities"]) == 1
    assert len(tree["business_units"]) == 1
