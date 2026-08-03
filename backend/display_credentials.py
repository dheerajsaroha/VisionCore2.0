#!/usr/bin/env python3
"""display_credentials.py — Read-only display of existing test credentials."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

import json
from app.db.database import SessionLocal
from app.db.models.all_models import User, Role, Organization, SubscriptionPlan, OrganizationSubscription
from fastapi.testclient import TestClient
from main import app

PASSWORD = "Vision@123"
client = TestClient(app)
db = SessionLocal()

# Check if credentials file exists
creds_file = "manual_test_credentials.json"
if os.path.exists(creds_file):
    with open(creds_file) as f:
        data = json.load(f)
    accounts = data.get("accounts", [])
    print(f"Found {len(accounts)} accounts in credentials file\n")
    print("| Role | Username | Email | Password | Organization | Subscription | Status | Permissions |")
    print("| ---- | -------- | ----- | -------- | ------------ | ------------ | ------ | ----------- |")
    for a in accounts:
        print(f"| {a['role']} | {a['username']} | {a['email']} | {a['password']} | {a['organization']} | {a.get('subscription_plan','N/A')} | {a.get('status','Active')} | {a.get('permission_count',0)} |")
    active = sum(1 for a in accounts if a.get("status") == "Active")
    failed = len(accounts) - active
    print(f"\nTotal Roles: {len(accounts)}")
    print(f"Total Active Accounts: {active}")
    print(f"Total Failed Accounts: {failed}")
    db.close()
    sys.exit(0)

# Read from database
print("Credentials file not found — reading from database\n")
users = db.query(User).filter(User.is_deleted == 0).order_by(User.id).all()
org = db.query(Organization).order_by(Organization.created_at).first()
org_name = org.name if org else "Unknown"
sub_plan_name = "None"
if org:
    org_sub = db.query(OrganizationSubscription).filter(OrganizationSubscription.organization_id == org.id).first()
    if org_sub:
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == org_sub.subscription_plan_id).first()
        sub_plan_name = plan.name if plan else "Unknown"

print(f"Total users in DB: {len(users)}\n")
print("| Role | Username | Email | Password | Organization | Subscription | Status |")
print("| ---- | -------- | ----- | -------- | ------------ | ------------ | ------ |")

for u in users:
    role = db.query(Role).filter(Role.id == u.role_id).first()
    role_name = role.name if role else "Unknown"
    status = "Active" if u.is_active == 1 else "Inactive"
    print(f"| {role_name} | {u.username} | {u.email} | {PASSWORD} | {org_name} | {sub_plan_name} | {status} |")

db.close()
print(f"\nTotal Roles Available: {len(users)}")
print(f"Total Active Accounts: {sum(1 for u in users if u.is_active == 1)}")
print(f"Total Failed Accounts: {sum(1 for u in users if u.is_active != 1)}")
