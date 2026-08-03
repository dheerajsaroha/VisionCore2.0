"""
seed_subscription.py — Subscription & Feature Management Seeder

Seeds:
- 3 subscription plans (Starter, Professional, Enterprise)
- 38+ features across all modules
- Plan-feature mappings (which features are enabled per plan)
- Licensing limits per plan
- Organization subscription defaults

This is designed to be idempotent — safe to run multiple times.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.models.all_models import (
    SubscriptionPlan,
    OrganizationSubscription,
    Feature,
    PlanFeature,
    FeatureFlag,
    LicensingLimit,
    Organization,
)

logger = logging.getLogger(__name__)


# =============================================================================
#  SUBSCRIPTION PLAN DEFINITIONS
# =============================================================================

SUBSCRIPTION_PLANS: Dict[str, Dict] = {
    "starter": {
        "name": "Starter",
        "description": "Essential attendance tracking for small teams. Includes face recognition, leave management, policies, and basic reports.",
        "tier": 0,
        "monthly_price": 0,
        "yearly_price": 0,
        "currency": "USD",
        "trial_days": 14,
        "is_active": True,
        "is_system": True,
        "display_order": 0,
    },
    "professional": {
        "name": "Professional",
        "description": "Full-featured workforce management for growing organizations. Includes payroll, recruitment, assets, AI chat, and more.",
        "tier": 1,
        "monthly_price": 49.99,
        "yearly_price": 499.99,
        "currency": "USD",
        "trial_days": 14,
        "is_active": True,
        "is_system": True,
        "display_order": 1,
    },
    "enterprise": {
        "name": "Enterprise",
        "description": "Complete enterprise HRMS with all modules, custom roles, white label, SSO, blockchain audit, and dedicated support.",
        "tier": 2,
        "monthly_price": 199.99,
        "yearly_price": 1999.99,
        "currency": "USD",
        "trial_days": 30,
        "is_active": True,
        "is_system": True,
        "display_order": 2,
    },
}


# =============================================================================
#  FEATURE CATALOG
# =============================================================================

FEATURES: Dict[str, Dict] = {
    # ── Core Features ──────────────────────────────────────────────────────
    "attendance": {
        "module": "attendance",
        "name": "Attendance Tracking",
        "description": "Core attendance tracking with face recognition, check-in/out, and history",
        "category": "core",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "face_recognition": {
        "module": "attendance",
        "name": "Face Recognition",
        "description": "AI-powered face recognition for attendance check-in",
        "category": "core",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "liveness_detection": {
        "module": "attendance",
        "name": "Liveness Detection",
        "description": "Anti-spoofing liveness detection for face recognition",
        "category": "core",
        "dependencies": ["face_recognition"],
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "geofencing": {
        "module": "attendance",
        "name": "Geofencing",
        "description": "GPS-based location verification for check-in",
        "category": "core",
        "dependencies": ["attendance"],
        "beta": True,
        "deprecated": False,
        "visibility": "public",
    },
    "leave_management": {
        "module": "attendance",
        "name": "Leave Management",
        "description": "Leave application, approval, and balance tracking",
        "category": "core",
        "dependencies": ["attendance"],
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    # ── HR Features ────────────────────────────────────────────────────────
    "employee_management": {
        "module": "hr",
        "name": "Employee Management",
        "description": "Employee profile management, onboarding, and offboarding",
        "category": "hr",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "payroll": {
        "module": "hr",
        "name": "Payroll Processing",
        "description": "Payroll generation, approval, and disbursement",
        "category": "hr",
        "dependencies": ["attendance", "employee_management"],
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "recruitment": {
        "module": "hr",
        "name": "Recruitment",
        "description": "Job postings, application management, and offer management",
        "category": "hr",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "referral_program": {
        "module": "hr",
        "name": "Employee Referral Program",
        "description": "Employee referral submission, tracking, and rewards",
        "category": "hr",
        "dependencies": ["recruitment"],
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "performance_reviews": {
        "module": "hr",
        "name": "Performance Reviews",
        "description": "Performance review cycles, goals, and feedback",
        "category": "hr",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "training": {
        "module": "hr",
        "name": "Training & Courses",
        "description": "Course management, enrollment, and training tracking",
        "category": "hr",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "wellness": {
        "module": "hr",
        "name": "Employee Wellness",
        "description": "Wellness analytics, stress detection, and burnout prevention",
        "category": "hr",
        "dependencies": ["attendance"],
        "beta": True,
        "deprecated": False,
        "visibility": "public",
    },
    # ── Finance Features ───────────────────────────────────────────────────
    "expenses": {
        "module": "finance",
        "name": "Expense Management",
        "description": "Expense submission, approval, and reimbursement",
        "category": "finance",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "travel": {
        "module": "finance",
        "name": "Travel Management",
        "description": "Travel requests, itineraries, and approvals",
        "category": "finance",
        "dependencies": ["expenses"],
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    # ── Operations Features ─────────────────────────────────────────────────
    "assets": {
        "module": "operations",
        "name": "Asset Management",
        "description": "Asset registration, assignment, and tracking",
        "category": "operations",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "projects": {
        "module": "operations",
        "name": "Project Management",
        "description": "Project creation, tasks, and team collaboration",
        "category": "operations",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "visitor_management": {
        "module": "operations",
        "name": "Visitor Management",
        "description": "Visitor check-in, badge printing, and host notifications",
        "category": "operations",
        "dependencies": ["attendance"],
        "beta": True,
        "deprecated": False,
        "visibility": "public",
    },
    "bulk_operations": {
        "module": "operations",
        "name": "Bulk Operations",
        "description": "Bulk import/export of employees, attendance, and payroll",
        "category": "operations",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    # ── Governance Features ─────────────────────────────────────────────────
    "policies": {
        "module": "governance",
        "name": "Policy Center",
        "description": "Policy creation, publishing, acknowledgment, and archiving",
        "category": "governance",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "documents": {
        "module": "governance",
        "name": "Document Management",
        "description": "Document upload, sharing, versioning, and access control",
        "category": "governance",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    # ── Communication Features ─────────────────────────────────────────────
    "announcements": {
        "module": "communication",
        "name": "Announcements",
        "description": "Organization-wide announcements and broadcasts",
        "category": "communication",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "notifications": {
        "module": "communication",
        "name": "Notification Center",
        "description": "Email, in-app, and push notification delivery",
        "category": "communication",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    # ── Analytics Features ─────────────────────────────────────────────────
    "reports": {
        "module": "analytics",
        "name": "Reports",
        "description": "Report generation, scheduling, and export",
        "category": "analytics",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "analytics": {
        "module": "analytics",
        "name": "Advanced Analytics",
        "description": "Custom dashboards, data visualization, and BI tools",
        "category": "analytics",
        "dependencies": ["reports"],
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "ai_analytics": {
        "module": "analytics",
        "name": "AI Analytics",
        "description": "AI-powered insights, predictions, and trend analysis",
        "category": "analytics",
        "dependencies": ["analytics"],
        "beta": True,
        "deprecated": False,
        "visibility": "public",
    },
    # ── AI Features ────────────────────────────────────────────────────────
    "ai_chat": {
        "module": "ai",
        "name": "AI Chat Assistant",
        "description": "AI-powered chat assistant for HR queries and support",
        "category": "ai",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "ai_face_recognition": {
        "module": "ai",
        "name": "AI Face Recognition Engine",
        "description": "Advanced face recognition, spoof detection, and emotion analysis",
        "category": "ai",
        "dependencies": ["face_recognition"],
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    # ── Platform Features ───────────────────────────────────────────────────
    "marketplace": {
        "module": "platform",
        "name": "App Marketplace",
        "description": "Third-party app marketplace and integrations",
        "category": "platform",
        "dependencies": None,
        "beta": True,
        "deprecated": False,
        "visibility": "public",
    },
    "integrations": {
        "module": "platform",
        "name": "Third-Party Integrations",
        "description": "Connect with external systems via API and webhooks",
        "category": "platform",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "webhooks": {
        "module": "platform",
        "name": "Webhook Support",
        "description": "Outgoing webhooks for event-driven integrations",
        "category": "platform",
        "dependencies": ["integrations"],
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "custom_roles": {
        "module": "platform",
        "name": "Custom Roles",
        "description": "Create and manage custom roles with granular permissions",
        "category": "platform",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "custom_workflows": {
        "module": "platform",
        "name": "Custom Approval Workflows",
        "description": "Design custom multi-stage approval workflows",
        "category": "platform",
        "dependencies": ["custom_roles"],
        "beta": True,
        "deprecated": False,
        "visibility": "public",
    },
    "white_label": {
        "module": "platform",
        "name": "White Label Branding",
        "description": "Custom branding, logo, colors, and domain",
        "category": "platform",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    # ── Security Features ──────────────────────────────────────────────────
    "sso": {
        "module": "security",
        "name": "Single Sign-On (SSO)",
        "description": "SAML, OAuth, and OpenID Connect SSO integration",
        "category": "security",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "mfa": {
        "module": "security",
        "name": "Multi-Factor Authentication",
        "description": "TOTP, SMS, and email-based MFA",
        "category": "security",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "audit_trail": {
        "module": "security",
        "name": "Audit Trail",
        "description": "Comprehensive audit logging with retention policies",
        "category": "security",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
    "blockchain_audit": {
        "module": "security",
        "name": "Blockchain Audit",
        "description": "Tamper-evident blockchain-anchored audit trail",
        "category": "security",
        "dependencies": ["audit_trail"],
        "beta": True,
        "deprecated": False,
        "visibility": "public",
    },
    "api_access": {
        "module": "security",
        "name": "API Access",
        "description": "API key management and programmatic access",
        "category": "security",
        "dependencies": None,
        "beta": False,
        "deprecated": False,
        "visibility": "public",
    },
}


# =============================================================================
#  PLAN-FEATURE MAPPING (which features are enabled per plan)
# =============================================================================

PLAN_FEATURES: Dict[str, List[str]] = {
    "starter": [
        # Core
        "attendance", "face_recognition", "leave_management",
        # HR
        "employee_management",
        # Governance
        "policies", "documents",
        # Communication
        "announcements", "notifications",
        # Analytics
        "reports",
        # Security
        "api_access",
    ],
    "professional": [
        # Core
        "attendance", "face_recognition", "liveness_detection", "leave_management",
        # HR
        "employee_management", "payroll", "recruitment",
        "performance_reviews", "training",
        # Finance
        "expenses",
        # Operations
        "assets", "projects", "bulk_operations",
        # Governance
        "policies", "documents",
        # Communication
        "announcements", "notifications",
        # Analytics
        "reports", "analytics",
        # AI
        "ai_chat", "ai_face_recognition",
        # Platform
        "integrations", "webhooks", "custom_roles",
        # Security
        "mfa", "audit_trail", "api_access",
    ],
    "enterprise": [
        # Core
        "attendance", "face_recognition", "liveness_detection", "geofencing", "leave_management",
        # HR
        "employee_management", "payroll", "recruitment", "referral_program",
        "performance_reviews", "training", "wellness",
        # Finance
        "expenses", "travel",
        # Operations
        "assets", "projects", "visitor_management", "bulk_operations",
        # Governance
        "policies", "documents",
        # Communication
        "announcements", "notifications",
        # Analytics
        "reports", "analytics", "ai_analytics",
        # AI
        "ai_chat", "ai_face_recognition",
        # Platform
        "marketplace", "integrations", "webhooks", "custom_roles", "custom_workflows",
        "white_label",
        # Security
        "sso", "mfa", "audit_trail", "blockchain_audit", "api_access",
    ],
}


# =============================================================================
#  LICENSING LIMITS PER PLAN
# =============================================================================

LICENSING_LIMITS: Dict[str, List[Dict]] = {
    "starter": [
        {"limit_type": "employees", "soft_limit": 50, "hard_limit": 50, "is_unlimited": False,
         "description": "Maximum 50 employees"},
        {"limit_type": "departments", "soft_limit": 5, "hard_limit": 5, "is_unlimited": False,
         "description": "Maximum 5 departments"},
        {"limit_type": "teams", "soft_limit": 10, "hard_limit": 10, "is_unlimited": False,
         "description": "Maximum 10 teams"},
        {"limit_type": "projects", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited projects"},
        {"limit_type": "storage_gb", "soft_limit": 5, "hard_limit": 5, "is_unlimited": False,
         "description": "5 GB storage"},
        {"limit_type": "api_calls_per_min", "soft_limit": 60, "hard_limit": 60, "is_unlimited": False,
         "description": "60 API calls per minute"},
        {"limit_type": "api_keys", "soft_limit": 5, "hard_limit": 5, "is_unlimited": False,
         "description": "Maximum 5 API keys"},
        {"limit_type": "camera_devices", "soft_limit": 2, "hard_limit": 2, "is_unlimited": False,
         "description": "Maximum 2 camera devices"},
        {"limit_type": "biometric_devices", "soft_limit": 1, "hard_limit": 1, "is_unlimited": False,
         "description": "Maximum 1 biometric device"},
        {"limit_type": "reports_per_day", "soft_limit": 10, "hard_limit": 20, "is_unlimited": False,
         "description": "Maximum 20 reports per day"},
        {"limit_type": "exports_per_day", "soft_limit": 5, "hard_limit": 10, "is_unlimited": False,
         "description": "Maximum 10 exports per day"},
        {"limit_type": "concurrent_sessions", "soft_limit": 1, "hard_limit": 1, "is_unlimited": False,
         "description": "1 concurrent session per user"},
        {"limit_type": "notification_templates", "soft_limit": 5, "hard_limit": 5, "is_unlimited": False,
         "description": "Maximum 5 notification templates"},
        {"limit_type": "training_courses", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited training courses"},
        {"limit_type": "workflow_definitions", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited workflow definitions"},
        {"limit_type": "automation_rules", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited automation rules"},
        {"limit_type": "marketplace_apps", "soft_limit": 0, "hard_limit": 0, "is_unlimited": False,
         "description": "No marketplace access"},
        {"limit_type": "integrations", "soft_limit": 0, "hard_limit": 0, "is_unlimited": False,
         "description": "No third-party integrations"},
        {"limit_type": "custom_roles", "soft_limit": 0, "hard_limit": 0, "is_unlimited": False,
         "description": "No custom roles"},
        {"limit_type": "custom_dashboards", "soft_limit": 1, "hard_limit": 1, "is_unlimited": False,
         "description": "1 custom dashboard"},
    ],
    "professional": [
        {"limit_type": "employees", "soft_limit": 450, "hard_limit": 500, "is_unlimited": False,
         "description": "Maximum 500 employees"},
        {"limit_type": "departments", "soft_limit": 20, "hard_limit": 25, "is_unlimited": False,
         "description": "Maximum 25 departments"},
        {"limit_type": "teams", "soft_limit": 40, "hard_limit": 50, "is_unlimited": False,
         "description": "Maximum 50 teams"},
        {"limit_type": "projects", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited projects"},
        {"limit_type": "storage_gb", "soft_limit": 80, "hard_limit": 100, "is_unlimited": False,
         "description": "100 GB storage"},
        {"limit_type": "api_calls_per_min", "soft_limit": 500, "hard_limit": 600, "is_unlimited": False,
         "description": "600 API calls per minute"},
        {"limit_type": "api_keys", "soft_limit": 20, "hard_limit": 25, "is_unlimited": False,
         "description": "Maximum 25 API keys"},
        {"limit_type": "camera_devices", "soft_limit": 20, "hard_limit": 25, "is_unlimited": False,
         "description": "Maximum 25 camera devices"},
        {"limit_type": "biometric_devices", "soft_limit": 8, "hard_limit": 10, "is_unlimited": False,
         "description": "Maximum 10 biometric devices"},
        {"limit_type": "reports_per_day", "soft_limit": 50, "hard_limit": 100, "is_unlimited": False,
         "description": "Maximum 100 reports per day"},
        {"limit_type": "exports_per_day", "soft_limit": 25, "hard_limit": 50, "is_unlimited": False,
         "description": "Maximum 50 exports per day"},
        {"limit_type": "concurrent_sessions", "soft_limit": 3, "hard_limit": 3, "is_unlimited": False,
         "description": "3 concurrent sessions per user"},
        {"limit_type": "notification_templates", "soft_limit": 20, "hard_limit": 25, "is_unlimited": False,
         "description": "Maximum 25 notification templates"},
        {"limit_type": "training_courses", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited training courses"},
        {"limit_type": "workflow_definitions", "soft_limit": 10, "hard_limit": 10, "is_unlimited": False,
         "description": "Maximum 10 workflow definitions"},
        {"limit_type": "automation_rules", "soft_limit": 5, "hard_limit": 5, "is_unlimited": False,
         "description": "Maximum 5 automation rules"},
        {"limit_type": "marketplace_apps", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited marketplace apps"},
        {"limit_type": "integrations", "soft_limit": 5, "hard_limit": 5, "is_unlimited": False,
         "description": "Maximum 5 integrations"},
        {"limit_type": "custom_roles", "soft_limit": 5, "hard_limit": 5, "is_unlimited": False,
         "description": "Maximum 5 custom roles"},
        {"limit_type": "custom_dashboards", "soft_limit": 5, "hard_limit": 5, "is_unlimited": False,
         "description": "Maximum 5 custom dashboards"},
    ],
    "enterprise": [
        {"limit_type": "employees", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited employees"},
        {"limit_type": "departments", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited departments"},
        {"limit_type": "teams", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited teams"},
        {"limit_type": "projects", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited projects"},
        {"limit_type": "storage_gb", "soft_limit": 800, "hard_limit": 1000, "is_unlimited": False,
         "description": "1 TB storage"},
        {"limit_type": "api_calls_per_min", "soft_limit": 5000, "hard_limit": 6000, "is_unlimited": False,
         "description": "6000 API calls per minute"},
        {"limit_type": "api_keys", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited API keys"},
        {"limit_type": "camera_devices", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited camera devices"},
        {"limit_type": "biometric_devices", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited biometric devices"},
        {"limit_type": "reports_per_day", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited reports"},
        {"limit_type": "exports_per_day", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited exports"},
        {"limit_type": "concurrent_sessions", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited concurrent sessions"},
        {"limit_type": "notification_templates", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited notification templates"},
        {"limit_type": "training_courses", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited training courses"},
        {"limit_type": "workflow_definitions", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited workflow definitions"},
        {"limit_type": "automation_rules", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited automation rules"},
        {"limit_type": "marketplace_apps", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited marketplace apps"},
        {"limit_type": "integrations", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited integrations"},
        {"limit_type": "custom_roles", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited custom roles"},
        {"limit_type": "custom_dashboards", "soft_limit": None, "hard_limit": None, "is_unlimited": True,
         "description": "Unlimited custom dashboards"},
    ],
}


# =============================================================================
#  SEEDING FUNCTIONS
# =============================================================================

def seed_subscription_plans(db: Session) -> Dict[str, int]:
    """Seed all 3 subscription plans idempotently. Returns {code: id} map."""
    plan_map = {}
    for code, plan_def in SUBSCRIPTION_PLANS.items():
        existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == code).first()
        if existing:
            # Update existing plan
            for key, value in plan_def.items():
                setattr(existing, key, value)
            db.add(existing)
            plan_map[code] = existing.id
        else:
            plan = SubscriptionPlan(code=code, **plan_def)
            db.add(plan)
            db.flush()
            plan_map[code] = plan.id
    db.commit()
    logger.info("Seeded %d subscription plans", len(plan_map))
    return plan_map


def seed_features(db: Session) -> Dict[str, int]:
    """Seed all features idempotently. Returns {code: id} map."""
    feature_map = {}
    for code, feature_def in FEATURES.items():
        existing = db.query(Feature).filter(Feature.code == code).first()
        if existing:
            # Update existing feature
            for key, value in feature_def.items():
                if key == "dependencies":
                    setattr(existing, key, {"depends_on": value} if value else None)
                else:
                    setattr(existing, key, value)
            db.add(existing)
            feature_map[code] = existing.id
        else:
            deps = {"depends_on": feature_def["dependencies"]} if feature_def["dependencies"] else None
            feat = Feature(
                code=code,
                module=feature_def["module"],
                name=feature_def["name"],
                description=feature_def["description"],
                category=feature_def["category"],
                dependencies=deps,
                beta=feature_def["beta"],
                deprecated=feature_def["deprecated"],
                visibility=feature_def["visibility"],
            )
            db.add(feat)
            db.flush()
            feature_map[code] = feat.id
    db.commit()
    logger.info("Seeded %d features", len(feature_map))
    return feature_map


def seed_plan_features(db: Session, plan_map: Dict[str, int], feature_map: Dict[str, int]) -> int:
    """Map plans to features. Returns count of plan-feature links created."""
    count = 0
    for plan_code, feature_codes in PLAN_FEATURES.items():
        plan_id = plan_map.get(plan_code)
        if not plan_id:
            continue
        for feature_code in feature_codes:
            feature_id = feature_map.get(feature_code)
            if not feature_id:
                logger.warning("Feature %s not found for plan %s", feature_code, plan_code)
                continue
            existing = db.query(PlanFeature).filter(
                PlanFeature.plan_id == plan_id,
                PlanFeature.feature_id == feature_id,
            ).first()
            if not existing:
                pf = PlanFeature(
                    plan_id=plan_id,
                    feature_id=feature_id,
                    enabled=True,
                    default_on=True,
                    configurable=True,
                )
                db.add(pf)
                count += 1
    db.commit()
    logger.info("Created %d plan-feature mappings", count)
    return count


def seed_licensing_limits(db: Session, plan_map: Dict[str, int]) -> int:
    """Seed licensing limits per plan. Returns count of limit records created."""
    count = 0
    for plan_code, limits in LICENSING_LIMITS.items():
        plan_id = plan_map.get(plan_code)
        if not plan_id:
            continue
        for limit_def in limits:
            existing = db.query(LicensingLimit).filter(
                LicensingLimit.plan_id == plan_id,
                LicensingLimit.limit_type == limit_def["limit_type"],
            ).first()
            if not existing:
                ll = LicensingLimit(plan_id=plan_id, **limit_def)
                db.add(ll)
                count += 1
    db.commit()
    logger.info("Created %d licensing limits", count)
    return count


def seed_default_organization_subscriptions(db: Session, plan_map: Dict[str, int]) -> int:
    """Assign default 'Professional' plan to all existing organizations without a subscription."""
    professional_plan_id = plan_map.get("professional")
    if not professional_plan_id:
        logger.warning("Professional plan not found — skipping org subscription defaults")
        return 0

    count = 0
    orgs = db.query(Organization).all()
    for org in orgs:
        existing = db.query(OrganizationSubscription).filter(
            OrganizationSubscription.organization_id == org.id
        ).first()
        if not existing:
            sub = OrganizationSubscription(
                organization_id=org.id,
                subscription_plan_id=professional_plan_id,
                status="active",
                billing_cycle="monthly",
                start_date=datetime.now(timezone.utc),
                auto_renew=True,
            )
            db.add(sub)
            count += 1
    db.commit()
    logger.info("Created %d default organization subscriptions", count)
    return count


def seed_all(db: Session) -> Dict[str, int]:
    """Run the full subscription seeding pipeline. Returns stats."""
    logger.info("=== Subscription Seeding Started ===")

    # Step 1: Seed subscription plans
    plan_map = seed_subscription_plans(db)
    logger.info("Plans seeded: %d", len(plan_map))

    # Step 2: Seed features
    feature_map = seed_features(db)
    logger.info("Features seeded: %d", len(feature_map))

    # Step 3: Seed plan-feature mappings
    pf_count = seed_plan_features(db, plan_map, feature_map)
    logger.info("Plan-feature mappings: %d", pf_count)

    # Step 4: Seed licensing limits
    limit_count = seed_licensing_limits(db, plan_map)
    logger.info("Licensing limits: %d", limit_count)

    # Step 5: Seed default organization subscriptions
    sub_count = seed_default_organization_subscriptions(db, plan_map)
    logger.info("Default org subscriptions: %d", sub_count)

    total = len(plan_map) + len(feature_map) + pf_count + limit_count + sub_count
    logger.info("=== Subscription Seeding Complete: %d total records ===", total)

    return {
        "plans": len(plan_map),
        "features": len(feature_map),
        "plan_features": pf_count,
        "licensing_limits": limit_count,
        "org_subscriptions": sub_count,
        "total": total,
    }


def validate_subscription_seed(db: Session) -> List[str]:
    """Validate the seeded subscription data. Returns list of issues found."""
    issues = []

    # Check all plans exist
    for code in SUBSCRIPTION_PLANS:
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == code).first()
        if not plan:
            issues.append(f"Missing subscription plan: {code}")

    # Check all features exist
    for code in FEATURES:
        feature = db.query(Feature).filter(Feature.code == code).first()
        if not feature:
            issues.append(f"Missing feature: {code}")

    # Check plan-feature mappings
    for plan_code, feature_codes in PLAN_FEATURES.items():
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == plan_code).first()
        if plan:
            for feature_code in feature_codes:
                feature = db.query(Feature).filter(Feature.code == feature_code).first()
                if feature:
                    mapping = db.query(PlanFeature).filter(
                        PlanFeature.plan_id == plan.id,
                        PlanFeature.feature_id == feature.id,
                    ).first()
                    if not mapping:
                        issues.append(f"Missing plan-feature mapping: {plan_code} -> {feature_code}")

    # Check licensing limits
    for plan_code, limits in LICENSING_LIMITS.items():
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == plan_code).first()
        if plan:
            for limit_def in limits:
                limit = db.query(LicensingLimit).filter(
                    LicensingLimit.plan_id == plan.id,
                    LicensingLimit.limit_type == limit_def["limit_type"],
                ).first()
                if not limit:
                    issues.append(f"Missing licensing limit: {plan_code} -> {limit_def['limit_type']}")

    if not issues:
        logger.info("Subscription validation passed — all plans, features, mappings, and limits correct")

    return issues
