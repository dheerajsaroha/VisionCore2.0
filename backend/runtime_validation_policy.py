"""
runtime_validation_policy.py — End-to-End Validation Script for Sprint 4 Entity 5 (Policy Center)
"""
import sys
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import SQLALCHEMY_DATABASE_URL
from app.db.models.all_models import (
    Organization, User, Role, PolicyDocument, PolicyCategory, PolicyTag,
    PolicyVersion, PolicyDistribution, PolicyAcknowledgement, PolicySignature,
    PolicyTemplate, PolicyReminder, PolicyNotification, ComplianceRule, ComplianceRecord
)
from app.crud.crud_policy import (
    crud_policy_category, crud_policy_tag, crud_policy_document, crud_policy_version,
    crud_policy_acknowledgement, crud_policy_signature, crud_policy_template,
    crud_policy_reminder, crud_policy_notification, crud_compliance_rule, crud_compliance_record
)
from app.services.distribution_engine import distribution_engine
from app.services.compliance_engine import compliance_engine
from app.services.policy_search_service import policy_search_service
from app.services.policy_engine import policy_engine
from app.db.seed_policy import seed_policy_defaults_for_org


def main():
    print("=" * 70)
    print("🚀 SPRINT 4 ENTITY 5 — POLICY CENTER & COMPLIANCE MODULE VALIDATION")
    print("=" * 70)

    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    try:
        # 1. Fetch test org & admin user
        org = db.query(Organization).first()
        admin = db.query(User).filter(User.org_id == org.id).first() if org else None

        if not org or not admin:
            print("❌ Test database does not have an Organization or User record. Please initialize DB first.")
            sys.exit(1)

        print(f"✅ Found Organization: {org.name} ({org.id})")
        print(f"✅ Found User: {admin.full_name} ({admin.email})")

        # 2. Test Seeder
        print("\n🔹 Step 1: Seeding Default Policy Categories...")
        seed_policy_defaults_for_org(db, org.id, admin.id)
        cats = crud_policy_category.get_all_for_org(db, org.id)
        print(f"   ✓ Seeded Policy Categories Count: {len(cats)}")
        assert len(cats) >= 5, f"Expected >=5 categories, got {len(cats)}"

        # 3. Test Policy Tag CRUD
        print("\n🔹 Step 2: Testing Policy Tag CRUD...")
        tag = crud_policy_tag.create(db, org.id, {
            "name": "Confidential",
            "color": "#FF0000"
        })
        print(f"   ✓ Tag Created: ID={tag.id}, Name='{tag.name}'")
        tags = crud_policy_tag.get_all_for_org(db, org.id)
        print(f"   ✓ Total Tags: {len(tags)}")

        # 4. Test Policy Document CRUD
        print("\n🔹 Step 3: Testing Policy Document Engine...")
        doc = crud_policy_document.create(db, org.id, admin.id, {
            "title": "Data Protection Policy",
            "policy_type": "hr",
            "content": "All employee data must be handled in compliance with GDPR and local regulations.",
            "category_id": cats[0].id if cats else None,
            "tags": [tag.id] if tag else [],
            "effective_date": datetime.now(timezone.utc),
            "expiry_date": datetime.now(timezone.utc) + timedelta(days=365),
        })
        print(f"   ✓ Policy Document Created: ID={doc.id}, Title='{doc.title}', Status='{doc.status}'")
        assert doc.status == "draft"

        # 5. Test Policy Version CRUD
        print("\n🔹 Step 4: Testing Policy Version Engine...")
        ver = crud_policy_version.create(db, doc.id, admin.id, {
            "version": 1,
            "content": doc.content,
            "change_summary": "Initial version"
        })
        print(f"   ✓ Policy Version Created: ID={ver.id}, Version={ver.version}")
        versions = crud_policy_version.get_versions_for_doc(db, doc.id)
        print(f"   ✓ Total Versions for doc: {len(versions)}")

        # 6. Test Policy Publish Workflow
        print("\n🔹 Step 5: Testing Policy Publish Workflow...")
        pub_doc = crud_policy_document.publish(db, doc, admin.id)
        print(f"   ✓ Policy Published: Status='{pub_doc.status}', Published At={pub_doc.published_at}")
        assert pub_doc.status == "published"

        # 7. Test Distribution Engine
        print("\n🔹 Step 6: Testing Policy Distribution...")
        dist_org = distribution_engine.distribute_policy_to_org(db, doc.id, org.id)
        print(f"   ✓ Distributed Org-Wide: ID={dist_org.id}")
        dists = crud_policy_document.get_by_id(db, doc.id).distributions
        dist_count = len(dists) if hasattr(dists, '__len__') else 1
        print(f"   ✓ Distribution Records: {dist_count}")

        # 8. Test Policy Acknowledgement
        print("\n🔹 Step 7: Testing Policy Acknowledgement...")
        ack = crud_policy_acknowledgement.acknowledge(db, doc.id, admin.id, {
            "comment": "I have read and understand the policy."
        })
        print(f"   ✓ Policy Acknowledged: ID={ack.id}, is_acknowledged={ack.is_acknowledged}")
        assert ack.is_acknowledged is True

        # 9. Test Digital Signature
        print("\n🔹 Step 8: Testing Digital Signature Engine...")
        sig = crud_policy_signature.create(db, admin.id, {
            "document_id": doc.id,
            "signature_hash": "test_hash_abc123",
            "ip_address": "192.168.1.1",
            "device_info": "ValidationScript/1.0"
        })
        print(f"   ✓ Digital Signature Created: ID={sig.id}")
        sigs = crud_policy_signature.get_for_doc(db, doc.id)
        print(f"   ✓ Signatures for doc: {len(sigs)}")

        # 10. Test Policy Templates
        print("\n🔹 Step 9: Testing Policy Template Engine...")
        tmpl = crud_policy_template.create(db, org.id, admin.id, {
            "name": "Standard HR Policy Template",
            "content": "## Policy\n\n{{content}}\n\n## Effective Date\n\n{{effective_date}}",
            "category_id": cats[0].id if cats else None,
        })
        print(f"   ✓ Policy Template Created: ID={tmpl.id}, Name='{tmpl.name}'")
        templates = crud_policy_template.get_all_for_org(db, org.id)
        print(f"   ✓ Total Templates: {len(templates)}")

        # 11. Test Reminder Engine
        print("\n🔹 Step 10: Testing Policy Reminder Engine...")
        rem = crud_policy_reminder.create(db, org.id, {
            "document_id": doc.id,
            "reminder_type": "acknowledgement",
            "interval_days": 1,
        })
        print(f"   ✓ Policy Reminder Created: ID={rem.id}, Type='{rem.reminder_type}'")
        reminders = crud_policy_reminder.get_for_doc(db, doc.id)
        print(f"   ✓ Reminders for doc: {len(reminders)}")

        # 12. Test Notifications
        print("\n🔹 Step 11: Testing Policy Notifications...")
        from app.db.models.all_models import PolicyNotification as PolicyNotificationModel
        notif = PolicyNotificationModel(
            organization_id=org.id,
            document_id=doc.id,
            user_id=admin.id,
            notification_type="policy_published",
            title="New Policy Published",
            message="Data Protection Policy has been published and requires your acknowledgement.",
            is_read=False
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        print(f"   ✓ Notification Created: ID={notif.id}, Type='{notif.notification_type}'")

        notifs = crud_policy_notification.get_for_user(db, org.id, admin.id)
        print(f"   ✓ Notifications for user: {len(notifs)}")

        if notifs:
            read_notif = crud_policy_notification.mark_read(db, notif.id)
            print(f"   ✓ Notification Marked Read: is_read={read_notif.is_read}")

        # 13. Test Compliance Engine
        print("\n🔹 Step 12: Testing Compliance Rules & Engine...")
        rule = crud_compliance_rule.create(db, org.id, admin.id, {
            "name": "Policy Acknowledgement Compliance",
            "rule_type": "acknowledgement_deadline",
            "description": "Employees must acknowledge all HR policies within 7 days",
        })
        print(f"   ✓ Compliance Rule Created: ID={rule.id}, Type='{rule.rule_type}'")

        comp_summary = compliance_engine.get_org_compliance_summary(db, org.id)
        print(f"   ✓ Compliance Summary: {comp_summary.get('compliance_percentage', 'N/A')}%")

        comp_check = policy_engine.run_compliance_check(db, org.id, admin.id)
        print(f"   ✓ Compliance Check Result: {comp_check.get('is_compliant', comp_check)}")

        breaches = compliance_engine.detect_compliance_breaches(db, org.id)
        print(f"   ✓ Compliance Breaches Detected: {len(breaches)}")

        trend = compliance_engine.get_compliance_trend(db, org.id, 30)
        print(f"   ✓ Compliance Trend Data Points: {len(trend)}")

        # 14. Test Policy Search & Statistics
        print("\n🔹 Step 13: Testing Policy Search Engine...")
        search_result = policy_search_service.search_policies(db, org.id, query="Data Protection")
        total = search_result.get("total", 0)
        print(f"   ✓ Policy Search Results: {total}")
        assert total >= 1, f"Expected >=1 search result, got {total}"

        stats = policy_search_service.get_policy_statistics(db, org.id)
        print(f"   ✓ Policy Statistics: {stats}")

        # 15. Test Dashboard Analytics
        print("\n🔹 Step 14: Testing Policy Dashboard Analytics...")
        analytics = policy_engine.get_dashboard_analytics(db, org.id)
        print(f"   ✓ Dashboard Analytics Keys: {list(analytics.keys())}")
        assert analytics.get("total_policies", 0) >= 1, "Expected >=1 policy"

        # 16. Test Distribution Stats
        print("\n🔹 Step 15: Testing Distribution & Reminder Stats...")
        dist_stats = distribution_engine.get_distribution_stats(db, org.id)
        print(f"   ✓ Distribution Stats: {dist_stats}")

        # 17. Test Policy Archive
        print("\n🔹 Step 16: Testing Policy Archive Workflow...")
        arch_doc = crud_policy_document.archive(db, pub_doc, admin.id)
        print(f"   ✓ Policy Archived: Status='{arch_doc.status}'")
        assert arch_doc.status == "archived"

        # 18. Test Pending Acknowledgements
        print("\n🔹 Step 17: Testing Pending Acknowledgements...")
        pending = policy_engine.get_user_pending_acknowledgements(db, org.id, admin.id)
        print(f"   ✓ Pending Acknowledgements: {len(pending)}")

        print("\n" + "=" * 70)
        print("🎉 ALL SPRINT 4 ENTITY 5 (POLICY CENTER) VALIDATION CHECKS PASSED WITH 100% SUCCESS!")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    main()

