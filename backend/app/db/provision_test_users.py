"""
provision_test_users.py — Idempotent Provisioning of Standard VisionCore 3.0 Test Accounts

Seeds canonical test persona accounts with full tenant isolation and role permissions:
- superadmin@visioncore.io  (SuperAdmin)
- orgadmin@visioncore.io    (OrgAdmin)
- admin@visioncore.io       (Admin)
- hr@visioncore.io          (OrgHR)
- finance@visioncore.io     (OrgFinance)
- manager@visioncore.io     (OrgManager)
- employee@visioncore.io    (OrgEmployee)
- contractor@visioncore.io  (OrgContractor)

Password for all test accounts: Password123!
"""
from __future__ import annotations

import logging
import sys
import os
from typing import Dict, Any, List, Tuple

from sqlalchemy.orm import Session

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.database import SessionLocal
from app.db.models.all_models import User, Role, Organization, Department, Shift
from app.core.security import get_password_hash
from app.db.seed_rbac import seed_all

logger = logging.getLogger("visioncore.provision_test_users")
logging.basicConfig(level=logging.INFO)


TEST_PERSONAS: List[Tuple[str, str, str, str, str]] = [
    ("Chief Executive SuperAdmin", "superadmin@visioncore.io", "superadmin", "SuperAdmin", "Engineering"),
    ("Enterprise Tenant Admin", "orgadmin@visioncore.io", "orgadmin", "OrgAdmin", "Engineering"),
    ("Platform Enterprise Admin", "admin@visioncore.io", "admin", "Admin", "Operations"),
    ("Head of People Ops", "hr@visioncore.io", "hr", "OrgHR", "HR"),
    ("Director of Finance", "finance@visioncore.io", "finance", "OrgFinance", "Finance"),
    ("Engineering Manager", "manager@visioncore.io", "manager", "OrgManager", "Engineering"),
    ("Senior Staff Engineer", "employee@visioncore.io", "employee", "OrgEmployee", "Engineering"),
    ("External Systems Contractor", "contractor@visioncore.io", "contractor", "OrgContractor", "Operations"),
]


def provision_test_personas(db: Session, default_password: str = "Password123!") -> Dict[str, Any]:
    """
    Idempotently provisions all standard test accounts and binds them to valid roles and org entities.
    """
    logger.info("=== Provisioning Test Accounts ===")

    # 1. Run RBAC seed to ensure roles and permissions exist
    seed_stats = seed_all(db)
    logger.info("RBAC Seeder Stats: %s", seed_stats)

    # 2. Ensure Primary Organization exists
    org = db.query(Organization).filter(Organization.legal_id == "VC-ENT-001").first()
    if not org:
        org = Organization(
            name="VisionCore Enterprise Solutions",
            legal_id="VC-ENT-001",
            zkp_threshold=0.98,
        )
        db.add(org)
        db.commit()
        db.refresh(org)

    # 3. Ensure Default Departments exist
    departments_def = [
        ("Engineering", "Software Engineering & AI Infrastructure"),
        ("HR", "People Operations & Workforce"),
        ("Finance", "Payroll & Financial Accounting"),
        ("Operations", "Global Operations & Support"),
    ]
    dept_map: Dict[str, int] = {}
    for d_name, d_desc in departments_def:
        dept = db.query(Department).filter(Department.name == d_name, Department.org_id == org.id).first()
        if not dept:
            dept = Department(org_id=org.id, name=d_name, description=d_desc)
            db.add(dept)
            db.commit()
            db.refresh(dept)
        dept_map[d_name] = dept.id

    # 4. Ensure Default Shift exists
    shift = db.query(Shift).filter(Shift.shift_name == "Morning General", Shift.org_id == org.id).first()
    if not shift:
        shift = Shift(
            org_id=org.id,
            shift_name="Morning General",
            start_time="09:00:00",
            end_time="17:00:00",
            grace_period_mins=15,
            buffer_mins=30,
        )
        db.add(shift)
        db.commit()
        db.refresh(shift)

    # 5. Provision each test persona
    password_hash = get_password_hash(default_password)
    provisioned_users = []

    for idx, (full_name, email, username, role_name, dept_name) in enumerate(TEST_PERSONAS, start=1):
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            logger.warning("Role %s not found in DB, creating fallback role", role_name)
            role = Role(name=role_name, description=f"Provisioned role for {role_name}", is_system=False)
            db.add(role)
            db.commit()
            db.refresh(role)

        dept_id = dept_map.get(dept_name) if dept_name else None

        existing_user = db.query(User).filter(
            (User.email == email) | (User.username == username)
        ).first()

        emp_code = f"VC-TEST-{idx:03d}"

        if existing_user:
            # Update email, role, organization, department, shift, active status, and password
            existing_user.email = email
            existing_user.username = username
            existing_user.org_id = org.id
            existing_user.role_id = role.id
            existing_user.dept_id = dept_id
            existing_user.shift_id = shift.id
            existing_user.full_name = full_name
            existing_user.hashed_password = password_hash
            existing_user.is_active = 1
            existing_user.is_deleted = 0
            if not existing_user.employee_id:
                existing_user.employee_id = emp_code
            db.add(existing_user)
            provisioned_users.append(existing_user)
            logger.info("Updated test user persona: %s (%s) -> Role: %s", email, full_name, role_name)
        else:
            new_user = User(
                org_id=org.id,
                role_id=role.id,
                dept_id=dept_id,
                shift_id=shift.id,
                full_name=full_name,
                username=username,
                email=email,
                employee_id=emp_code,
                hashed_password=password_hash,
                is_active=1,
                is_deleted=0,
            )
            db.add(new_user)
            provisioned_users.append(new_user)
            logger.info("Created test user persona: %s (%s) -> Role: %s", email, full_name, role_name)

    db.commit()
    logger.info("=== Successfully Provisioned %d Test Personas ===", len(provisioned_users))
    return {
        "status": "success",
        "count": len(provisioned_users),
        "personas": [u.email for u in provisioned_users],
    }


def main():
    db = SessionLocal()
    try:
        results = provision_test_personas(db)
        print(f"Test user provisioning finished: {results}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
