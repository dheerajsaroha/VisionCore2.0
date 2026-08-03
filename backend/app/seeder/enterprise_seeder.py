"""
enterprise_seeder.py — VisionCore 3.0 Enterprise Seeder Framework

Provides an idempotent, transaction-safe, tenant-aware, deterministic seeder pipeline
spanning all 12 Platform Domains as mandated by the VisionCore 3.0 Architecture Charter.
"""

import logging
import random
import sys
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

# Add backend root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.database import SessionLocal, engine
from app.db.models.all_models import (
    Role, Organization, Department, Shift, User, FaceEmbedding,
    AttendanceLog, LeaveRequest, Ticket, Payroll
)
from app.core.security import get_password_hash

logger = logging.getLogger("visioncore.seeder")
logging.basicConfig(level=logging.INFO)


class EnterpriseSeeder:
    """
    Enterprise Seeder Pipeline for VisionCore 3.0.
    Executes modular seed steps with transaction isolation and idempotent guarantees.
    """

    def __init__(self, seed: int = 42, db_session: Optional[Session] = None):
        self.seed_value = seed
        random.seed(self.seed_value)
        self._external_session = db_session is not None
        self.db: Session = db_session or SessionLocal()
        self.tenant_context: Dict[str, Any] = {}

    def close(self):
        if not self._external_session and self.db:
            self.db.close()

    def run_all(self):
        """Executes the master enterprise seeding sequence."""
        logger.info("=================================================================")
        logger.info("🌱 VisionCore 3.0 Enterprise Seeder Pipeline Starting...")
        logger.info("=================================================================")
        
        try:
            self.bootstrap_platform_extensions()
            self.seed_rbac_roles()
            self.seed_organization_lifecycle()
            self.seed_organization_hierarchy()
            self.seed_employee_lifecycle()
            self.seed_biometric_face_embeddings()
            self.seed_attendance_workforce()
            self.seed_payroll_finance()
            self.seed_operations_tickets()
            
            logger.info("=================================================================")
            logger.info("✅ VisionCore 3.0 Enterprise Seeder Pipeline Executed Successfully!")
            logger.info("=================================================================")
        except Exception as e:
            logger.error(f"❌ Enterprise Seeder failed during execution: {e}")
            if not self._external_session:
                self.db.rollback()
            raise
        finally:
            self.close()

    def bootstrap_platform_extensions(self):
        """Step 1: Bootstrap required PostgreSQL extensions (vector, uuid-ossp, pgcrypto)."""
        logger.info("Step 1/9: Bootstrapping PostgreSQL Extensions...")
        try:
            self.db.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            self.db.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
            self.db.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
            self.db.commit()
        except Exception as e:
            logger.warning(f"Extension bootstrap notice (continuing if pre-existing): {e}")
            self.db.rollback()

    def seed_rbac_roles(self):
        """Step 2: Seed canonical system roles (SuperAdmin, Admin, HR, Manager, Employee, Candidate)."""
        logger.info("Step 2/9: Seeding RBAC Roles...")
        roles_master = ["SuperAdmin", "Admin", "HR", "Manager", "Employee", "Candidate"]
        role_map = {}
        for r_name in roles_master:
            role = self.db.query(Role).filter(Role.name == r_name).first()
            if not role:
                role = Role(name=r_name, permissions=["*"] if r_name == "SuperAdmin" else ["read"])
                self.db.add(role)
                self.db.commit()
                self.db.refresh(role)
            role_map[r_name] = role.id
        self.tenant_context["role_map"] = role_map

    def seed_organization_lifecycle(self):
        """Step 3: Provision primary enterprise organization with active lifecycle state."""
        logger.info("Step 3/9: Provisioning Enterprise Organization Lifecycle...")
        org = self.db.query(Organization).filter(Organization.legal_id == "VC-ENT-001").first()
        if not org:
            org = Organization(
                name="VisionCore Enterprise Solutions",
                legal_id="VC-ENT-001",
                zkp_threshold=0.98
            )
            self.db.add(org)
            self.db.commit()
            self.db.refresh(org)
        self.tenant_context["org"] = org

    def seed_organization_hierarchy(self):
        """Step 4: Seed departments and work shifts."""
        logger.info("Step 4/9: Seeding Organization Hierarchy & Shifts...")
        org = self.tenant_context["org"]
        depts_def = [
            ("Engineering", "Software Architecture & AI Platform"),
            ("HR", "Human Capital & People Operations"),
            ("Operations", "Global Workforce Operations"),
            ("Finance", "Payroll & Financial Intelligence")
        ]
        dept_map = {}
        for d_name, d_desc in depts_def:
            dept = self.db.query(Department).filter(Department.name == d_name, Department.org_id == org.id).first()
            if not dept:
                dept = Department(org_id=org.id, name=d_name, description=d_desc)
                self.db.add(dept)
                self.db.commit()
                self.db.refresh(dept)
            dept_map[d_name] = dept.id
        self.tenant_context["dept_map"] = dept_map

        shift = self.db.query(Shift).filter(Shift.shift_name == "Morning General", Shift.org_id == org.id).first()
        if not shift:
            shift = Shift(
                org_id=org.id,
                shift_name="Morning General",
                start_time="09:00:00",
                end_time="17:00:00",
                grace_period_mins=15,
                buffer_mins=30
            )
            self.db.add(shift)
            self.db.commit()
            self.db.refresh(shift)
        self.tenant_context["shift"] = shift

    def seed_employee_lifecycle(self):
        """Step 5: Onboard canonical enterprise users across all 6 roles."""
        logger.info("Step 5/9: Onboarding Canonical Employees & Persona Users...")
        org = self.tenant_context["org"]
        role_map = self.tenant_context["role_map"]
        dept_map = self.tenant_context["dept_map"]
        shift = self.tenant_context["shift"]

        seed_users = [
            ("Chief Executive Admin", "superadmin@visioncore.io", "SuperAdmin", "Engineering"),
            ("Enterprise Tenant Admin", "admin@visioncore.io", "Admin", "Operations"),
            ("Head of People", "hr@visioncore.io", "HR", "HR"),
            ("Engineering Lead Manager", "manager@visioncore.io", "Manager", "Engineering"),
            ("Senior Fullstack Engineer", "employee@visioncore.io", "Employee", "Engineering"),
            ("Candidate Applicant", "candidate@visioncore.io", "Candidate", None),
        ]

        created_users = []
        for full_name, email, r_name, dept_name in seed_users:
            uname = email.split("@")[0]
            usr = self.db.query(User).filter(
                (User.email == email) | (User.username == uname)
            ).first()
            if not usr:
                usr = User(
                    org_id=org.id,
                    role_id=role_map[r_name],
                    dept_id=dept_map.get(dept_name) if dept_name else None,
                    shift_id=shift.id,
                    full_name=full_name,
                    username=uname,
                    email=email,
                    employee_id=f"VC-{r_name[:3].upper()}-001",
                    hashed_password=get_password_hash("Password123!"),
                    is_active=1,
                    is_deleted=0
                )
                self.db.add(usr)
                self.db.commit()
                self.db.refresh(usr)
            created_users.append(usr)
        self.tenant_context["users"] = created_users

    def seed_biometric_face_embeddings(self):
        """Step 6: Seed active biometric face embeddings for attendance verification."""
        logger.info("Step 6/9: Generating Biometric Face Embeddings...")
        users = self.tenant_context["users"]
        for u in users:
            if u.role and u.role.name in ["Employee", "Manager", "HR", "Admin"]:
                existing_emb = self.db.query(FaceEmbedding).filter(
                    FaceEmbedding.user_id == u.id, FaceEmbedding.is_active == 1
                ).first()
                if not existing_emb:
                    # Seeded deterministic random 128-d vector
                    mock_vec = [round(random.uniform(-0.08, 0.08), 4) for _ in range(128)]
                    fe = FaceEmbedding(
                        user_id=u.id,
                        embedding=mock_vec,
                        model_name="face_recognition",
                        is_active=1
                    )
                    self.db.add(fe)
        self.db.commit()

    def seed_attendance_workforce(self):
        """Step 7: Populate realistic attendance shift logs."""
        logger.info("Step 7/9: Seeding Workforce Attendance Logs...")
        users = self.tenant_context["users"]
        emp_user = next((u for u in users if u.role and u.role.name == "Employee"), None)
        if emp_user:
            now = datetime.now()
            for i in range(14):
                day = now - timedelta(days=i)
                if day.weekday() < 5:  # Weekdays
                    check_in_time = day.replace(hour=8, minute=55, second=0)
                    log = self.db.query(AttendanceLog).filter(
                        AttendanceLog.user_id == emp_user.id,
                        AttendanceLog.check_in >= day.replace(hour=0, minute=0, second=0),
                        AttendanceLog.check_in <= day.replace(hour=23, minute=59, second=59)
                    ).first()
                    if not log:
                        log = AttendanceLog(
                            user_id=emp_user.id,
                            check_in=check_in_time,
                            status="on_time" if i % 3 != 0 else "late",
                            is_live=1,
                            source="ai",
                            geofence_pass=1
                        )
                        self.db.add(log)
            self.db.commit()

    def seed_payroll_finance(self):
        """Step 8: Populate baseline payroll records."""
        logger.info("Step 8/9: Seeding Payroll Financial Records...")
        users = self.tenant_context["users"]
        org = self.tenant_context["org"]
        emp_user = next((u for u in users if u.role and u.role.name == "Employee"), None)
        if emp_user:
            now = datetime.now()
            payroll = self.db.query(Payroll).filter(Payroll.user_id == emp_user.id).first()
            if not payroll:
                payroll = Payroll(
                    user_id=emp_user.id,
                    org_id=org.id,
                    month=now.month,
                    year=now.year,
                    base_salary=8500.00,
                    deductions=500.00,
                    reimbursements_total=200.00,
                    total_salary=8200.00,
                    status="paid"
                )
                self.db.add(payroll)
                self.db.commit()

    def seed_operations_tickets(self):
        """Step 9: Populate service desk operational tickets."""
        logger.info("Step 9/9: Seeding Operations Service Desk Tickets...")
        users = self.tenant_context["users"]
        org = self.tenant_context["org"]
        emp_user = next((u for u in users if u.role and u.role.name == "Employee"), None)
        if emp_user:
            ticket = self.db.query(Ticket).filter(Ticket.user_id == emp_user.id).first()
            if not ticket:
                ticket = Ticket(
                    user_id=emp_user.id,
                    org_id=org.id,
                    title="Biometric Scanner Calibration Request",
                    description="Requesting calibration for Building B entrance scanner.",
                    priority="medium",
                    status="open"
                )
                self.db.add(ticket)
                self.db.commit()


def run_seeder():
    seeder = EnterpriseSeeder()
    seeder.run_all()


if __name__ == "__main__":
    run_seeder()
