from fastapi import APIRouter
<<<<<<< HEAD
from app.routers import auth, users, attendance, org, ticketing, payroll, reimbursement, departments, sessions_router, rbac, subscription, scope, workflow, dynamic_roles, eaac_router, leave, recruitment, hr, performance, learning, succession, policy, asset, enterprise, operations, ai
from app.routers import platform_services_router, org_identity_router, workforce_router, hcm_router
=======
from app.routers import auth, users, attendance, org, ticketing, payroll, reimbursement, admin, attendance_correction
>>>>>>> refs/remotes/origin/main

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
api_router.include_router(org.router, prefix="/org", tags=["organization"])
api_router.include_router(departments.router, prefix="/org", tags=["departments"])
api_router.include_router(ticketing.router, prefix="/ticketing", tags=["ticketing"])
api_router.include_router(payroll.router, prefix="/payroll", tags=["payroll"])
api_router.include_router(reimbursement.router, prefix="/reimbursement", tags=["reimbursement"])
<<<<<<< HEAD
api_router.include_router(leave.router, prefix="/leave", tags=["leave"])
api_router.include_router(recruitment.router, prefix="/recruitment", tags=["recruitment"])
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
=======
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(attendance_correction.router, prefix="/attendance-corrections", tags=["attendance-corrections"])

>>>>>>> refs/remotes/origin/main
