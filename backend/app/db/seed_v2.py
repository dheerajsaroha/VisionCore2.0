#!/usr/bin/env python3
"""
seed_v2.py — Enterprise Seed Framework v2
Populates realistic test data across all 6 core roles (SuperAdmin, Admin, HR, Manager, Employee, Candidate),
departments, shifts, face embeddings, attendance logs, leaves, tickets, and payroll summaries.
"""
import os
import sys
import uuid
import random
from datetime import datetime, timedelta, timezone

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models.all_models import (
    Role, Organization, Department, Shift, User, FaceEmbedding, AttendanceLog,
    AttendanceCorrection, LeaveRequest, Ticket, Payroll
)
from app.core.security import get_password_hash
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_enterprise_v2():
    db = SessionLocal()
    try:
        logger.info("🌱 Starting Enterprise Seed Framework v2...")

        # 1. Extensions
        try:
            db.execute(text('CREATE EXTENSION IF NOT EXISTS vector;'))
            db.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
            db.execute(text('CREATE EXTENSION IF NOT EXISTS pgcrypto;'))
            db.commit()
        except Exception as e:
            logger.warning(f"Note on extensions: {e}")
            db.rollback()

        # 2. Roles
        roles_master = ["SuperAdmin", "Admin", "HR", "Manager", "Employee", "Candidate"]
        role_map = {}
        for r_name in roles_master:
            role = db.query(Role).filter(Role.name == r_name).first()
            if not role:
                role = Role(name=r_name, permissions=[])
                db.add(role)
                db.commit()
                db.refresh(role)
            role_map[r_name] = role.id

        # 3. Organization
        org = db.query(Organization).filter(Organization.legal_id == "VC-ENT-001").first()
        if not org:
            org = Organization(
                name="VisionCore Enterprise Solutions",
                legal_id="VC-ENT-001",
                zkp_threshold=0.98
            )
            db.add(org)
            db.commit()
            db.refresh(org)

        # 4. Departments
        depts_def = [("Engineering", "Software & AI"), ("HR", "People Ops"), ("Operations", "Global Operations")]
        dept_map = {}
        for d_name, d_desc in depts_def:
            d = db.query(Department).filter(Department.name == d_name, Department.org_id == org.id).first()
            if not d:
                d = Department(org_id=org.id, name=d_name, description=d_desc)
                db.add(d)
                db.commit()
                db.refresh(d)
            dept_map[d_name] = d.id

        # 5. Shift
        shift = db.query(Shift).filter(Shift.shift_name == "Morning General", Shift.org_id == org.id).first()
        if not shift:
            shift = Shift(
                org_id=org.id,
                shift_name="Morning General",
                start_time="09:00:00",
                end_time="17:00:00",
                grace_period_mins=15,
                buffer_mins=30
            )
            db.add(shift)
            db.commit()
            db.refresh(shift)

        # 6. Users for all 6 Roles
        seed_users = [
            ("SuperAdmin User", "superadmin@visioncore.io", "SuperAdmin", "Engineering"),
            ("Org Admin User", "admin@visioncore.io", "Admin", "Operations"),
            ("HR Director", "hr@visioncore.io", "HR", "HR"),
            ("Engineering Manager", "manager@visioncore.io", "Manager", "Engineering"),
            ("Lead Developer", "employee@visioncore.io", "Employee", "Engineering"),
            ("Sarah Candidate", "candidate@visioncore.io", "Candidate", None),
        ]

        created_users = []
        for full_name, email, r_name, dept_name in seed_users:
            uname = email.split("@")[0]
            usr = db.query(User).filter(
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
                    employee_id=f"VC-{r_name[:3].upper()}-{random.randint(100, 999)}",
                    hashed_password=get_password_hash("Password123!"),
                    is_active=1,
                    is_deleted=0
                )
                db.add(usr)
                db.commit()
                db.refresh(usr)
            created_users.append(usr)

        # 7. Biometric Face Embeddings (128-d mock vector for active employees)
        for u in created_users:
            if u.role.name in ["Employee", "Manager", "HR", "Admin"]:
                existing_emb = db.query(FaceEmbedding).filter(FaceEmbedding.user_id == u.id, FaceEmbedding.is_active == 1).first()
                if not existing_emb:
                    mock_vec = [random.uniform(-0.1, 0.1) for _ in range(128)]
                    fe = FaceEmbedding(
                        user_id=u.id,
                        embedding=mock_vec,
                        model_name="face_recognition",
                        is_active=1
                    )
                    db.add(fe)
        db.commit()

        # 8. Attendance Logs (Past 7 days for employees)
        emp_user = next((u for u in created_users if u.role.name == "Employee"), None)
        if emp_user:
            now = datetime.now()
            for i in range(7):
                day = now - timedelta(days=i)
                if day.weekday() < 5:  # Weekdays only
                    check_in_time = day.replace(hour=8, minute=55, second=0)
                    log = db.query(AttendanceLog).filter(
                        AttendanceLog.user_id == emp_user.id,
                        AttendanceLog.check_in >= day.replace(hour=0, minute=0, second=0),
                        AttendanceLog.check_in <= day.replace(hour=23, minute=59, second=59)
                    ).first()
                    if not log:
                        log = AttendanceLog(
                            user_id=emp_user.id,
                            check_in=check_in_time,
                            status="on_time" if i % 2 == 0 else "late",
                            is_live=1,
                            source="ai",
                            geofence_pass=1
                        )
                        db.add(log)
            db.commit()

        logger.info("✅ Enterprise Seed Framework v2 completed successfully!")
    except Exception as e:
        logger.error(f"❌ Seed v2 failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_enterprise_v2()
