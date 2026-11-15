# Comprehensive Module Index

> **Phase 3 & 4 — Module Inventory and Boundary Analysis**  
> **Scope:** Complete mapping of functional domains across Backend, AI Microservice, Frontend, and Infrastructure.

---

## 1. Domain Catalog Overview

The codebase is partitioned into 20 functional domains spanning backend services, routers, models, schemas, and frontend page views:

```
┌────────────────────────────────────────────────────────────────────────┐
│                       VISIONCORE 2.0 DOMAIN CATALOG                    │
├───────────────────────────────┬────────────────────────────────────────┤
│ 1. Identity, Auth & RBAC      │ 11. Performance Management             │
│ 2. Attendance & Biometrics    │ 12. Learning & Development (L&D)       │
│ 3. Workforce & Scheduling     │ 13. Succession Planning & Careers      │
│ 4. Human Capital Mgmt (HCM)   │ 14. Policy Center & Compliance         │
│ 5. Leave & Absence Mgmt       │ 15. Asset Management                   │
│ 6. Payroll & Statutory Engine │ 16. Enterprise Integrations & Webhooks │
│ 7. Ticketing & Helpdesk       │ 17. AI Platform & Domain Copilots      │
│ 8. Subscription & Licensing   │ 18. Recruitment & Candidate Pipeline   │
│ 9. Dynamic Roles & EAAC       │ 19. Blockchain & Audit Explorer        │
│ 10. Workflow & Approvals      │ 20. Infrastructure, Gateway & Core     │
└───────────────────────────────┴────────────────────────────────────────┘
```

---

## 2. Functional Domain Specifications

### 2.1 Identity, Authentication & RBAC Domain
- **Primary Purpose:** Manages user identity, secure JWT issuance, refresh cookie rotation, session tracking, password recovery, and role/permission enforcement.
- **Backend Components:**
  - Routers: `app/routers/auth.py`, `app/routers/users.py`, `app/routers/sessions_router.py`, `app/routers/invites.py`, `app/routers/rbac.py`
  - Services: `app/services/auth_service.py`, `app/services/password_reset_service.py`, `app/services/email_service.py`
  - CRUD: `app/crud/crud_user.py`, `app/crud/crud_session.py`, `app/crud/crud_rbac.py`
  - Models: `User`, `Role`, `Permission`, `RolePermission`, `UserRole`, `UserSession`, `PasswordResetToken`, `EmployeeInvite`
  - Schemas: `app/schema/token.py`, `app/schema/user.py`, `app/schema/rbac.py`
- **Frontend Components:**
  - Pages: `LoginPage.jsx`, `SignupPage.jsx`, `ForgotPasswordPage.jsx`, `ResetPasswordPage.jsx`, `UserManagement.jsx`, `PermissionManagement.jsx`
  - Services: `services/authService.js`, `services/userService.js`
  - Store: `store/authStore.js`, `store/permissionStore.js`
- **Public Exports / Entry Points:** `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `GET /api/v1/users/me`

### 2.2 Attendance & Biometric Pipeline Domain
- **Primary Purpose:** Ingests live webcam frames, extracts 128-dimensional biometric embeddings, performs anti-spoof liveness validation, runs HNSW cosine similarity search against enrolled vectors, logs attendance records, and processes correction requests.
- **Backend Components:**
  - Routers: `app/routers/attendance.py`, `app/routers/attendance_correction.py`, `app/routers/ws_video.py`
  - Services: `app/services/attendance_controller.py`, `app/services/attendance_pipeline/`, `app/services/biometrics_service.py`, `app/services/attendance_correction_service.py`
  - AI Engine: `ai-service/app/services/face_engine.py`, `ai-service/app/services/liveness.py`, `ai-service/app/services/emotion.py`
  - Models: `AttendanceLog`, `FaceEmbedding`, `EnrollmentEvent`, `SpoofDetectionLog`, `RecognitionEvent`, `EmotionLog`, `AttendanceCorrection`, `AttendanceDevice`, `GeofenceZone`
  - Schemas: `app/schema/attendance.py`, `app/schema/biometrics.py`
- **Frontend Components:**
  - Pages: `Attendance.jsx`, `AttendanceDashboardPage.jsx`, `AttendanceTimelinePage.jsx`, `AttendanceDevicesPage.jsx`, `AttendanceAnalyticsPage.jsx`
  - Components: Webcam capture dialogs, MediaPipe face mesh canvas overlay
  - Services: `services/attendanceService.js`, `services/biometricService.js`

### 2.3 Workforce Management & Scheduling Domain
- **Primary Purpose:** Shift creation, shift template scheduling, employee roster planning, break tracking, overtime calculation, comp-off balances, holiday calendars, and capacity forecasting.
- **Backend Components:**
  - Routers: `app/routers/workforce_router.py`, `app/routers/departments.py`
  - Services: `app/services/business_calendar_service.py`, `app/services/distribution_engine.py`
  - Models: `ShiftTemplate`, `ShiftAssignment`, `Roster`, `RosterEntry`, `ShiftSwapRequest`, `TimeEntry`, `BreakLog`, `OvertimeRecord`, `CompOffBalance`, `HolidayCalendar`, `HolidayEntry`, `HeadcountPlan`, `CapacitySnapshot`
  - Schemas: `app/schema/workforce.py`
- **Frontend Components:**
  - Pages: `ShiftCalendarPage.jsx`, `RosterPlannerPage.jsx`, `WorkforcePlanningPage.jsx`, `CapacityDashboardPage.jsx`, `HolidayManagementPage.jsx`
  - Services: `services/workforceService.js`

### 2.4 Human Capital Management (HCM) Domain
- **Primary Purpose:** Comprehensive employee profile records, educational credentials, work experience history, honors/awards, professional licenses, emergency contacts, talent pools, and HR documents.
- **Backend Components:**
  - Routers: `app/routers/hcm_router.py`, `app/routers/hr.py`
  - Services: `app/services/hr_command_center.py`
  - Models: `EmployeeProfile`, `EmployeeEducation`, `EmployeeExperience`, `EmployeeAward`, `EmployeeLicense`, `EmployeeEmergencyContact`, `TalentPool`, `TalentPoolMember`, `EmployeeDocument`
  - Schemas: `app/schema/hcm.py`
- **Frontend Components:**
  - Pages: `HRDashboardPage.jsx`, `IdentityDirectoryPage.jsx`
  - Modals: `EmployeeDetailModal.jsx`
  - Services: `services/hrService.js`

### 2.5 Leave & Absence Management Domain
- **Primary Purpose:** Multi-tier leave policy configuration, gender-scoped rules (e.g., maternity/paternity), accrual rules, leave balance tracking, request submissions, manager approval workflows, and encashment.
- **Backend Components:**
  - Routers: `app/routers/leave.py`
  - Services: `app/services/leave_service.py`, `app/services/leave_policy_engine.py`
  - CRUD: `app/crud/crud_leave.py`
  - Models: `LeaveTemplate`, `LeaveTemplateItem`, `LeaveType`, `LeavePolicy`, `LeaveBalance`, `LeaveRequest`, `LeaveAdjustment`
  - Schemas: `app/schema/leave.py`
- **Frontend Components:**
  - Pages: `LeaveManagementPage.jsx`, `LeaveCalendarPage.jsx`, `LeaveRequestsPage.jsx`
  - Components: Leave balance meters, leave request modal dialog
  - Services: `services/leaveService.js`

### 2.6 Payroll & Financial Operations Domain
- **Primary Purpose:** Pay grade definitions, salary structures, attendance aggregation for Loss of Pay (LOP) deductions, statutory rules (provident fund, professional tax, income tax brackets), payroll cycle runs, and programmatic PDF payslip generation.
- **Backend Components:**
  - Routers: `app/routers/payroll.py`, `app/routers/finance_admin.py`, `app/routers/reimbursement.py`
  - Services: `app/services/payroll_service.py`, `app/services/statutory_engine.py`, `app/services/payslip_pdf_service.py`, `app/services/reimbursement_service.py`
  - CRUD: `app/crud/crud_payroll.py`
  - Models: `PayGrade`, `SalaryStructure`, `PayrollRun`, `PayrollLineItem`, `StatutoryRule`, `PayrollAdvance`, `LoanRepayment`, `Payslip`, `Reimbursement`, `ExpenseCategory`, `ReimbursementClaim`
  - Schemas: `app/schema/payroll.py`, `app/schema/reimbursement.py`
- **Frontend Components:**
  - Pages: `Payroll.jsx`, `MyPayslipsPage.jsx`, `Reimbursements.jsx`
  - Services: `services/payrollService.js`, `services/reimbursementService.js`

### 2.7 Ticketing & Operations Domain
- **Primary Purpose:** Internal HR, IT, and administrative ticketing system with SLA tracking, ticket assignment, commenting, attachments, and resolution audits.
- **Backend Components:**
  - Routers: `app/routers/ticketing.py`, `app/routers/operations.py`
  - Services: `app/services/ticketing_service.py`, `app/services/operations_service.py`
  - Models: `Ticket`, `TicketComment`, `TicketAttachment`, `TicketSLA`, `TicketAudit`
  - Schemas: `app/schema/ticketing.py`
- **Frontend Components:**
  - Pages: `Ticketing.jsx`, `OperationsPage.jsx`
  - Services: `services/ticketingService.js`

### 2.8 Subscription, Licensing & Enterprise Billing Domain
- **Primary Purpose:** Multi-tenant SaaS subscription management, tier-based feature gating (`starter`, `professional`, `enterprise`), seat limits, license enforcement, and usage tracking.
- **Backend Components:**
  - Routers: `app/routers/subscription.py`, `app/routers/tenant_admin.py`
  - Services: `app/services/subscription_service.py`, `app/services/billing_service.py`
  - Models: `SubscriptionPlan`, `OrganizationSubscription`, `Feature`, `PlanFeature`, `FeatureFlag`, `LicensingLimit`
  - Schemas: `app/schema/subscription.py`
- **Frontend Components:**
  - Pages: `TenantAdminPage.jsx`
  - Store: `store/subscriptionStore.js`
  - Hooks: `hooks/useSubscription.js`

### 2.9 Dynamic Roles & EAAC Domain
- **Primary Purpose:** Enterprise Adaptive Access Control engine supporting dynamic role creation, role inheritance hierarchies, versioned role changes, and cross-organization scope boundaries.
- **Backend Components:**
  - Routers: `app/routers/dynamic_roles.py`, `app/routers/eaac_router.py`, `app/routers/scope.py`
  - Services: `app/services/dynamic_role_service.py`, `app/services/eaac_service.py`, `app/services/scope_service.py`
  - Models: `DynamicRole`, `RoleTemplate`, `RoleInheritance`, `RoleVersion`, `UserRoleAssignment`, `DataScope`, `RoleDataScope`, `ResourceOwnership`
  - Schemas: `app/schema/dynamic_role.py`, `app/schema/scope.py`
- **Frontend Components:**
  - Pages: `DynamicRoleManagementPage.jsx`, `ScopeOwnershipPage.jsx`
  - Services: `services/dynamicRoleService.js`

### 2.10 Workflow & Approval Engine Domain
- **Primary Purpose:** Configurable multi-stage approval workflows for attendance corrections, leave requests, expenses, and role elevations with delegation, proxies, and escalation rules.
- **Backend Components:**
  - Routers: `app/routers/workflow.py`
  - Services: `app/services/workflow_engine.py`, `app/services/approval_service.py`
  - Models: `ApprovalWorkflow`, `ApprovalStage`, `ApprovalStageApprover`, `ApprovalTemplate`, `ApprovalRequest`, `ApprovalAction`, `ApprovalHistory`, `ApprovalEscalation`, `WorkflowCondition`
  - Schemas: `app/schema/workflow.py`
- **Frontend Components:**
  - Pages: `ApprovalWorkflowPage.jsx`
  - Services: `services/workflowService.js`

### 2.11 Performance Management Domain
- **Primary Purpose:** Review cycles, OKR/goal setting, 360-degree feedback, competency matrices, skill assessments, and performance improvement plans (PIPs).
- **Backend Components:**
  - Routers: `app/routers/performance.py`
  - Services: `app/services/performance_service.py`, `app/services/calibration_engine.py`
  - Models: `PerformanceCycle`, `PerformanceGoal`, `PerformanceReview`, `ReviewFeedback`, `CompetencyMatrix`, `SkillAssessment`, `PerformanceImprovementPlan`
  - Schemas: `app/schema/performance.py`
- **Frontend Components:**
  - Pages: `PerformanceManagementPage.jsx`
  - Services: `services/performanceService.js`

### 2.12 Learning & Development (L&D) Domain
- **Primary Purpose:** Course catalog, structured learning paths, module tracking, employee enrollment, certifications, training budgets, and skill inventories.
- **Backend Components:**
  - Routers: `app/routers/learning.py`
  - Services: `app/services/learning_service.py`
  - Models: `Course`, `CourseModule`, `CourseEnrollment`, `LearningPath`, `Certification`, `TrainingBudget`, `SkillInventory`
  - Schemas: `app/schema/learning.py`
- **Frontend Components:**
  - Pages: `LearningDevelopmentPage.jsx`
  - Services: `services/learningService.js`

### 2.13 Succession Planning & Career Paths Domain
- **Primary Purpose:** Identifying talent pipelines, 9-box grid assessments, flight risk analysis, succession plan candidate ranking, and career trajectory mapping.
- **Backend Components:**
  - Routers: `app/routers/succession.py`
  - Services: `app/services/succession_service.py`
  - Models: `SuccessionPlan`, `SuccessionCandidate`, `CareerPath`, `JobRoleMatrix`, `TalentReview`
  - Schemas: `app/schema/succession.py`
- **Frontend Components:**
  - Pages: `SuccessionCareerPage.jsx`
  - Services: `services/successionService.js`

### 2.14 Policy Center & Compliance Domain
- **Primary Purpose:** Publishing company policies, tracking versioned employee acknowledgments, managing legal holds, GDPR/privacy data deletion requests, retention schedules, and security audits.
- **Backend Components:**
  - Routers: `app/routers/policy.py`, `app/routers/compliance_router.py`, `app/routers/audit_explorer_router.py`
  - Services: `app/services/policy_service.py`, `app/services/compliance_engine.py`, `app/services/audit_service.py`
  - Models: `CompanyPolicy`, `PolicyVersion`, `PolicyAcknowledgment`, `ComplianceAudit`, `AuditLog`, `RetentionPolicy`, `LegalHold`, `PrivacyRequest`, `SecurityEventLog`
  - Schemas: `app/schema/policy.py`, `app/schema/compliance.py`
- **Frontend Components:**
  - Pages: `PolicyCenterPage.jsx`
  - Services: `services/policyService.js`

### 2.15 Asset Management Domain
- **Primary Purpose:** Hardware and asset tagging, inventory lifecycle tracking, assignment to employees, maintenance logs, depreciation schedules, vendor warranties, and consumables.
- **Backend Components:**
  - Routers: `app/routers/asset.py`
  - Services: `app/services/asset_engine.py`
  - Models: `Asset`, `AssetCategory`, `AssetAssignment`, `AssetMaintenance`, `AssetDepreciation`, `AssetDisposal`, `AssetAudit`, `Vendor`, `PurchaseOrder`
  - Schemas: `app/schema/asset.py`
- **Frontend Components:**
  - Pages: `AssetManagementPage.jsx`
  - Services: `services/assetService.js`

### 2.16 Enterprise Integrations & Webhooks Domain
- **Primary Purpose:** External API connector management, webhook dispatching with delivery attempt tracking, gateway route configurations, and API key provisioning.
- **Backend Components:**
  - Routers: `app/routers/enterprise.py` (and unmounted `integration.py`)
  - Services: `app/services/integration_service.py`, `app/services/webhook_dispatcher.py`
  - Models: `IntegrationConnector`, `WebhookSubscription`, `WebhookDeliveryRecord`, `GatewayRouteConfig`, `ApiKeyMetadata`
  - Schemas: `app/schema/enterprise.py`
- **Frontend Components:**
  - Pages: `EnterpriseIntegrationPage.jsx`
  - Services: `services/enterpriseService.js`

### 2.17 AI Platform & Domain Copilots Domain
- **Primary Purpose:** Multi-provider LLM routing, AI usage tracking, token cost attribution, prompt template management, and domain copilots (HR Copilot, Policy Copilot, Workforce Copilot).
- **Backend Components:**
  - Routers: `app/routers/ai.py`, `app/routers/copilot_router.py`
  - Services: `app/services/ai_provider_manager.py`, `app/services/ai_cost_tracker.py`, `app/services/ai_governance.py`, `app/services/copilots/`
  - Models: `AIModelConfig`, `PromptTemplate`, `CopilotSession`, `CopilotMessage`, `AIGovernanceLog`, `AIUsageRecord`
  - Schemas: `app/schema/ai.py`, `app/schema/copilot.py`
- **Frontend Components:**
  - Pages: `AIStudioPage.jsx`, `AICopilotHubPage.jsx`, `AIAnalyticsPage.jsx`, `PromptManagerPage.jsx`, `ModelManagerPage.jsx`, `AIUsageDashboardPage.jsx`, `AIGovernanceDashboardPage.jsx`, `KnowledgeCenterPage.jsx`
  - Services: `services/aiService.js`, `services/knowledgeService.js`

### 2.18 Recruitment & Candidate Pipeline Domain
- **Primary Purpose:** Public careers board, job requisition posting, candidate tracking, interview loop scheduling, interviewer scorecards, candidate referral management, and digital offer letter generation.
- **Backend Components:**
  - Routers: `app/routers/careers.py`, `app/routers/recruitment.py`, `app/routers/offer_letters.py`, `app/routers/referrals.py`
  - Services: `app/services/recruitment_service.py`, `app/services/offer_letter_service.py`
  - Models: `JobOpening`, `Candidate`, `CandidateApplication`, `InterviewStage`, `InterviewSchedule`, `InterviewFeedback`, `OfferTemplate`, `OfferLetter`, `CandidateReferral`
  - Schemas: `app/schema/recruitment.py`
- **Frontend Components:**
  - Pages: `OpenPositionsPage.jsx`, `CandidatePipelinePage.jsx`
  - Services: `services/recruitmentService.js`

### 2.19 Blockchain & Audit Explorer Domain
- **Primary Purpose:** Cryptographic anchoring of attendance hashes into an Ethereum/EVM smart contract (`AttendanceAudit`), providing non-repudiation and immutable verification logs.
- **Backend Components:**
  - Routers: `app/routers/audit_explorer_router.py`, `app/routers/sse_audit.py`
  - Services: `app/services/blockchain.py`, `app/services/audit_service.py`
  - Models: `BlockchainAuditLog`, `MonthlyGrowthSummary`
- **Public Exports / Entry Points:** `GET /api/v1/audit-explorer/logs`, `GET /api/v1/sse/audit`

### 2.20 Core Infrastructure, Middleware & Gateway Domain
- **Primary Purpose:** Application lifecycle management, rate limiting, request timing, correlation tracking, database initialization, and reverse proxy routing.
- **Components:**
  - Entry Points: `backend/main.py`, `backend/gateway/main.py`
  - Middleware: `app/middleware/correlation_id.py`, `app/middleware/tenant_context.py`, `app/middleware/tenant_isolation.py`, `app/middleware/observability_middleware.py`
  - Core: `app/core/config.py`, `app/core/security.py`, `app/core/rate_limit.py`, `app/core/observability.py`
  - Utilities: `app/util/init.py`
