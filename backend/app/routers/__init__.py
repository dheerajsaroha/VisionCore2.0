from fastapi import APIRouter
from app.routers import (
    auth, users, attendance, org, ticketing, payroll, reimbursement,
    departments, sessions_router, rbac, subscription, scope, workflow,
    dynamic_roles, eaac_router, leave, recruitment, hr, performance,
    learning, succession, policy, asset, enterprise, operations, ai,
    platform_services_router, org_identity_router, workforce_router,
    hcm_router, admin, attendance_correction, notifications, dashboard,
    public, offer_letters, invites, finance_admin,
    analytics_router, compliance_router, copilot_router,
    audit_explorer_router, tenant_admin, referrals, careers,
)

api_router = APIRouter()
api_router.include_router(public.router, prefix="/public", tags=["public"])
# Public careers board: intentionally unauthenticated so an
# organization's vacancies are visible on its own careers page.
api_router.include_router(careers.router, prefix="/careers", tags=["careers"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
# Before the org router: it declares /org/{org_id}, which would otherwise
# swallow the literal /org/invites. Declares its own full paths because the
# admin and recipient halves live at different roots.
api_router.include_router(invites.router, tags=["invites"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
api_router.include_router(org.router, prefix="/org", tags=["organization"])
api_router.include_router(departments.router, prefix="/org", tags=["departments"])
api_router.include_router(ticketing.router, prefix="/ticketing", tags=["ticketing"])
api_router.include_router(payroll.router, prefix="/payroll", tags=["payroll"])
# Was never registered, so every endpoint it declares was unreachable:
# statutory rules, tax configuration, salary components, payroll
# periods and the payroll-run lifecycle.
api_router.include_router(finance_admin.router, prefix="/finance-admin", tags=["finance-admin"])
api_router.include_router(reimbursement.router, prefix="/reimbursement", tags=["reimbursement"])
api_router.include_router(leave.router, prefix="/leave", tags=["leave"])
api_router.include_router(recruitment.router, prefix="/recruitment", tags=["recruitment"])
api_router.include_router(offer_letters.router, prefix="/recruitment", tags=["offer-letters"])
api_router.include_router(referrals.router, prefix="/recruitment", tags=["referrals"])
api_router.include_router(hr.router, prefix="/hr", tags=["hr"])
api_router.include_router(performance.router, prefix="/performance", tags=["performance"])
api_router.include_router(learning.router, prefix="/learning", tags=["learning"])
api_router.include_router(succession.router, prefix="/succession", tags=["succession"])
api_router.include_router(policy.router, prefix="/policy", tags=["policy"])
api_router.include_router(sessions_router.router, prefix="/auth", tags=["sessions"])
api_router.include_router(rbac.router, prefix="/rbac", tags=["rbac"])
api_router.include_router(subscription.router, prefix="/subscription", tags=["subscription"])
api_router.include_router(scope.router, prefix="/scope", tags=["scope"])
api_router.include_router(workflow.router, prefix="/workflow", tags=["workflow"])
api_router.include_router(dynamic_roles.router, prefix="/dynamic-roles", tags=["dynamic-roles"])
api_router.include_router(eaac_router.router, prefix="/eaac", tags=["eaac"])
api_router.include_router(asset.router, prefix="/assets", tags=["assets"])
api_router.include_router(enterprise.router, prefix="/enterprise", tags=["enterprise"])
api_router.include_router(operations.router, prefix="/operations", tags=["operations"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(platform_services_router.router, prefix="/platform", tags=["platform-services"])
api_router.include_router(org_identity_router.router, tags=["organization-identity-domain"])
api_router.include_router(workforce_router.router, prefix="/workforce", tags=["workforce"])
api_router.include_router(hcm_router.router, prefix="/hcm", tags=["hcm"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(attendance_correction.router, prefix="/attendance-corrections", tags=["attendance-corrections"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])

# These five were written but never registered, so every endpoint each declared
# was unreachable at runtime — which silently deleted a large amount of
# already-implemented analytics, compliance and platform tooling.
#
# Each required a permission gate that did not exist before it was mounted:
# mounting them as written would have exposed audit logs, security events,
# privacy requests, retention policies and payroll-cost metrics to any
# authenticated session. Those gates are applied inside the routers.
api_router.include_router(analytics_router.router, prefix="/analytics", tags=["analytics"])
# Register real‑time routers
from .ws_video import router as ws_video_router
from .sse_audit import router as sse_audit_router
api_router.include_router(ws_video_router, tags=["realtime"])
api_router.include_router(sse_audit_router, tags=["audit-sse"])
api_router.include_router(compliance_router.router, prefix="/compliance", tags=["compliance"])
api_router.include_router(copilot_router.router, prefix="/copilot", tags=["copilot"])
# Prefix avoids colliding with the existing /enterprise/audit surface.
api_router.include_router(audit_explorer_router.router, prefix="/audit-explorer", tags=["compliance"])
# Cross-tenant platform administration. Its own router carries the /tenant
# prefix and is SuperAdmin-only via deps.get_current_superadmin.
api_router.include_router(tenant_admin.router, tags=["tenant-admin"])
