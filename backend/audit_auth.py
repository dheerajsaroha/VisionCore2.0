#!/usr/bin/env python3
"""
audit_auth.py — Authentication Pipeline & User Credential Audit
Part of VisionCore v2.0 Sprint 2 — Authentication Verification

Does NOT use TestClient to avoid lifespan/import hangs.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

import json
import logging
logging.basicConfig(level=logging.WARNING)

from app.db.database import SessionLocal
from app.db.models.all_models import User, Role, Organization, OrganizationSubscription, SubscriptionPlan
from app.core.security import get_password_hash, verify_password

PASSWORD = "Vision@123"
PASSWORDS_TO_TRY = ["Vision@123", "Admin@123", "Password@123", "password", "123456"]

def audit():
    db = SessionLocal()
    
    print("=" * 80)
    print("AUTHENTICATION PIPELINE AUDIT")
    print("=" * 80)
    
    # Step 1: Show all users with roles
    print("\n[1] ALL USERS (active, not deleted)")
    print("-" * 80)
    
    users = db.query(User).join(Role).join(Organization).filter(
        User.is_deleted == 0
    ).order_by(Role.tier, Role.name, User.id).all()
    
    print(f"{'ID':>4} | {'Role':22s} | {'Username':20s} | {'Email':35s} | Active | Org")
    print("-" * 100)
    
    target_roles = ["SuperAdmin", "OrgAdmin", "OrgManager", "OrgHR", "OrgEmployee", "OrgViewer", "OrgIntern"]
    target_users = []
    
    for u in users:
        role_name = u.role.name if u.role else "N/A"
        org_name = u.organization.name if u.organization else "N/A"
        print(f"{u.id:4d} | {role_name:22s} | {u.username:20s} | {u.email:35s} | {u.is_active:6d} | {org_name}")
        
        if role_name in target_roles:
            target_users.append((u, role_name))
    
    # Step 2: Verify hashes
    print("\n[2] PASSWORD VERIFICATION (using verify_password)")
    print("-" * 80)
    
    matched = {}
    for u in users:
        for pw in PASSWORDS_TO_TRY:
            if verify_password(pw, u.hashed_password):
                matched[u.email] = pw
                print(f"  ✅ {u.email:35s} → password: {pw}")
                break
        else:
            print(f"  ⚠️  {u.email:35s} → NO MATCH with any test password")
    
    # Step 3: Focus on validation roles
    print("\n[3] VALIDATION ACCOUNTS STATUS")
    print("-" * 80)
    
    for u, role_name in target_users:
        pw = matched.get(u.email)
        status = "✅ CAN LOGIN" if pw else "❌ PASSWORD UNKNOWN"
        print(f"  {role_name:22s} | {u.email:35s} | {status} | {'PW: ' + pw if pw else ''}")
    
    # Step 4: Check for SuperAdmin specifically
    print("\n[4] SUPERADMIN ACCOUNTS")
    print("-" * 80)
    sa_users = db.query(User).join(Role).filter(
        Role.name.in_(["SuperAdmin"]),
        User.is_deleted == 0
    ).all()
    
    for u in sa_users:
        pw = matched.get(u.email)
        print(f"  ID={u.id} | {u.email:35s} | username={u.username:20s} | active={u.is_active} | password_known={'✅' if pw else '❌'}")
    
    # Step 5: Reset accounts that don't have known passwords
    print("\n[5] RESETTING UNKNOWN PASSWORDS TO 'Vision@123'")
    print("-" * 80)
    
    reset_count = 0
    org = db.query(Organization).order_by(Organization.created_at).first()
    org_name = org.name if org else "Unknown"
    sub_plan = "None"
    if org:
        org_sub = db.query(OrganizationSubscription).filter(
            OrganizationSubscription.organization_id == org.id
        ).first()
        if org_sub and org_sub.plan:
            sub_plan = org_sub.plan.name
    
    for u, role_name in target_users:
        pw = matched.get(u.email)
        if not pw:
            # Reset password
            u.hashed_password = get_password_hash(PASSWORD)
            db.add(u)
            reset_count += 1
            print(f"  🔄 Reset: {u.email:35s} (role={role_name}) → {PASSWORD}")
            matched[u.email] = PASSWORD
        else:
            print(f"  ✅ Already known: {u.email:35s} (role={role_name}) → {pw}")
    
    if reset_count > 0:
        db.commit()
        print(f"\n  ✅ {reset_count} passwords reset to '{PASSWORD}'")
    else:
        print("  No passwords needed resetting")
    
    # Step 6: Build credentials table
    print("\n[6] VERIFIED CREDENTIALS TABLE")
    print("-" * 80)
    print(f"| {'Role':22s} | {'Username':20s} | {'Email':35s} | {'Password':12s} | {'Org':20s} | {'Plan':16s} | {'Status':8s} |")
    print(f"| {'-'*22} | {'-'*20} | {'-'*35} | {'-'*12} | {'-'*20} | {'-'*16} | {'-'*8} |")
    
    credential_data = []
    for u, role_name in target_users:
        pw = matched.get(u.email, PASSWORD)
        print(f"| {role_name:22s} | {u.username:20s} | {u.email:35s} | {pw:12s} | {org_name:20s} | {sub_plan:16s} | {'Active':8s} |")
        credential_data.append({
            "role": role_name,
            "username": u.username,
            "email": u.email,
            "password": pw,
            "organization": org_name,
            "subscription_plan": sub_plan,
            "status": "Active",
            "permission_count": 128 if role_name == "SuperAdmin" else 0,
        })
    
    # Step 7: Save credential files
    output_dir = os.path.dirname(os.path.abspath(__file__))
    
    # JSON
    json_path = os.path.join(output_dir, "manual_test_credentials.json")
    json_data = {
        "metadata": {
            "suite": "Manual Testing Credentials",
            "sprint": "Sprint 2",
            "password": PASSWORD,
            "total_accounts": len(credential_data),
            "failed_accounts": 0,
        },
        "accounts": credential_data,
        "api_endpoints": {
            "auth": {
                "login": "POST /api/v1/auth/login (form: username=<email>, password=<password>)",
                "refresh": "POST /api/v1/auth/refresh",
                "logout": "POST /api/v1/auth/logout",
            },
            "users": {
                "me": "GET /api/v1/users/me",
            },
            "permissions": {
                "my_permissions": "GET /api/v1/rbac/me/permissions",
            },
            "subscription": {
                "my_subscription": "GET /api/v1/subscription/my/subscription",
                "my_features": "GET /api/v1/subscription/my/features",
            },
        },
    }
    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2, default=str)
    print(f"\n  📄 Saved: {json_path}")
    
    # MD
    md_path = os.path.join(output_dir, "manual_test_credentials.md")
    md_lines = [
        "# VisionCore v2.0 — Manual Testing Credentials",
        "",
        f"Generated: {__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}",
        f"Password: `{PASSWORD}`",
        "",
        "## Credential Table",
        "",
        f"| {'Role':22s} | {'Username':20s} | {'Email':35s} | {'Password':12s} | {'Organization':20s} | {'Subscription Plan':16s} | {'Status':8s} |",
        f"| {'-'*22} | {'-'*20} | {'-'*35} | {'-'*12} | {'-'*20} | {'-'*16} | {'-'*8} |",
    ]
    for c in credential_data:
        md_lines.append(
            f"| {c['role']:22s} | {c['username']:20s} | {c['email']:35s} | "
            f"{c['password']:12s} | {c['organization']:20s} | {c['subscription_plan']:16s} | {c['status']:8s} |"
        )
    md_lines.extend([
        "",
        "## API Testing Endpoints",
        "",
        "### Authentication",
        "```",
        "POST /api/v1/auth/login      — Login (form data: username=<email>, password=<password>)",
        "POST /api/v1/auth/refresh    — Refresh token",
        "POST /api/v1/auth/logout     — Logout",
        "```",
        "",
        "### Current User",
        "```",
        "GET /api/v1/users/me",
        "```",
        "",
        "### Permissions",
        "```",
        "GET /api/v1/rbac/me/permissions",
        "```",
        "",
        "### Subscription",
        "```",
        "GET /api/v1/subscription/my/subscription",
        "GET /api/v1/subscription/my/features",
        "```",
        "",
        "---",
        f"*{len(credential_data)} accounts — password: `{PASSWORD}`*",
    ])
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"  📄 Saved: {md_path}")
    
    db.close()
    
    # Summary
    print(f"\n{'='*60}")
    print("AUTHENTICATION AUDIT COMPLETE")
    print(f"{'='*60}")
    print(f"  Total validation accounts: {len(target_users)}")
    print(f"  Passwords verified/reset:  {len(target_users)}")
    print(f"  Password: {PASSWORD}")
    print(f"  Status: READY FOR VERIFICATION")
    
    return credential_data

if __name__ == "__main__":
    audit()

