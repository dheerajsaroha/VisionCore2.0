# Module-to-Role Ownership Matrix

## Baseline Roles (6)

| Role | Scope | Description |
|------|-------|-------------|
| **SuperAdmin** | Platform | Full platform access — all tenants, all features, all settings |
| **OrgAdmin** | Organization | Full organization administration — users, settings, departments, shifts, payroll, policy center |
| **HR** | Organization | HR operations — employee management, payroll, reimbursements, reports, policy center, leave, L&D |
| **Finance** | Organization | Financial operations — payroll, reimbursements, billing reports |
| **Manager** | Team/Department | Team supervision — attendance oversight, shift management, team reports, leave approval (dept-scoped) |
| **Employee** | Self | Self-service attendance, tickets, reimbursements, leave requests |

---

## Module Ownership Matrix

| Module | SuperAdmin | OrgAdmin | HR | Finance | Manager | Employee | Notes |
|--------|:----------:|:--------:|:--:|:-------:|:-------:|:--------:|-------|
| **Authentication** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | All roles |
| **Users/Identity** | ✅ | ✅ | ✅ R | ✅ R | ✅ R | ✅ R | R = read only |
| **Organizations** | ✅ | ✅ R | ❌ | ❌ | ❌ | ❌ | Platform only |
| **Departments** | ✅ | ✅ | ✅ R | ❌ | ✅ R | ❌ | |
| **Shifts** | ✅ | ✅ | ✅ R | ❌ | ✅ R | ❌ | |
| **Attendance** | ✅ | ✅ | ✅ R | ❌ | ✅ | ✅ | Manager: corrections |
| **Leave** | ✅ | ✅ | ✅ | ❌ | ✅ A | ✅ A/S | A = apply, S = self-view |
| **Payroll** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | |
| **Reimbursements** | ✅ | ✅ | ✅ | ✅ | ✅ A | ✅ A | A = apply |
| **Tickets** | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | |
| **Reports/Analytics** | ✅ | ✅ | ✅ | ✅ R | ✅ | ✅ R | |
| **Policies** | ✅ | ✅ | ✅ | ❌ | ✅ R | ✅ R | HR: manage |
| **Learning & Development** | ✅ | ✅ | ✅ | ❌ | ✅ R | ✅ R | HR: manage |
| **Performance** | ✅ | ✅ | ✅ R | ❌ | ✅ | ✅ R | |
| **Succession** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | HR/Admin only |
| **Recruitment** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | HR/Admin only |
| **Assets** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | Admin only |
| **Enterprise/Integrations** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | Admin only |
| **AI Platform** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | Admin only |
| **Knowledge Center** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | Admin only |
| **Settings (Org)** | ✅ | ✅ | ✅ R | ✅ R | ✅ R | ✅ R | |
| **Settings (Platform)** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | Platform only |

---

## Permission Taxonomy (Module.Action)

### Auth Module
- `auth.login`, `auth.refresh`, `auth.logout`, `auth.change_password`, `auth.register`

### Users Module
- `users.read`, `users.create`, `users.update`, `users.delete`, `users.impersonate`, `users.manage`

### Organization Module
- `org.view`, `org.create`, `org.update`, `org.delete`, `org.deactivate`, `org.restore`
- `org.settings.view`, `org.settings.manage`, `org.api_keys.manage`

### Departments Module
- `departments.read`, `departments.create`, `departments.update`, `departments.delete`

### Shifts Module
- `shifts.read`, `shifts.create`, `shifts.update`, `shifts.delete`

### Attendance Module
- `attendance.checkin`, `attendance.checkout`, `attendance.history`, `attendance.corrections`, `attendance.export`

### Leave Module
- `leave.apply`, `leave.view_self`, `leave.view_team`, `leave.view_org`, `leave.approve`, `leave.approve_team`, `leave.reject`, `leave.cancel`, `leave.manage`

### Payroll Module
- `payroll.generate`, `payroll.approve`, `payroll.export`, `payroll.manage`

### Reimbursements Module
- `reimbursements.read`, `reimbursements.create`, `reimbursements.approve`, `reimbursements.reject`

### Tickets Module
- `tickets.read`, `tickets.create`, `tickets.update`, `tickets.delete`

### Reports Module
- `reports.attendance.export`, `reports.payroll.export`, `reports.employee.export`, `reports.billing`

### Notifications Module
- `notifications.read`, `notifications.send`, `notifications.platform`, `notifications.manage`

### Billing Module
- `billing.view`, `billing.manage`

### Audit Module
- `audit.view`, `audit.export`, `audit.write`

### Platform Module
- `platform.settings.view`, `platform.settings.manage`, `features.manage`, `system.maintenance`, `system.health`

### Security Module
- `security.manage`, `incidents.manage`

### Roles Module
- `roles.view`, `roles.create`, `roles.update`, `roles.delete`, `roles.assign`

### Policy Module
- `policy.create`, `policy.read`, `policy.update`, `policy.delete`, `policy.publish`, `policy.archive`, `policy.acknowledge`, `policy.sign`, `policy.distribute`, `policy.compliance.view`, `policy.compliance.manage`, `policy.reminders.manage`, `policy.templates.manage`, `policy.versions.view`, `policy.attachments.manage`, `policy.categories.manage`, `policy.tags.manage`, `policy.analytics.view`

### Asset Module
- `asset.create`, `asset.read`, `asset.update`, `asset.delete`, `asset.assign`, `asset.transfer`, `asset.return`, `asset.maintenance`, `asset.audit`, `asset.export`, `asset.manage`

### Learning Module
- `learning.view`, `learning.create`, `learning.update`, `learning.manage`

### Succession Module
- `succession.view`, `succession.create`, `succession.update`, `succession.manage`

### Performance Module
- `performance.view`, `performance.create`, `performance.update`, `performance.manage`

### Recruitment Module
- `recruitment.view`, `recruitment.create`, `recruitment.update`, `recruitment.manage`

### HCM Module
- `hcm.view`, `hcm.update`, `hcm.manage`

### Workforce Module
- `workforce.view`, `workforce.manage`

### Integration Module
- `integration.view`, `integration.create`, `integration.update`, `integration.manage`

### AI Module
- `ai.studio.use`, `ai.copilot.use`, `ai.analytics.read`, `ai.prompt.manage`, `ai.model.manage`, `ai.governance.manage`

### Knowledge Module
- `knowledge.read`, `knowledge.create`, `knowledge.update`, `knowledge.manage`

---

## Role-to-Permission Assignments (Seed)

### SuperAdmin
- `__all__` (all permissions)

### OrgAdmin
- `__org_admin__` (all org-scoped permissions, excluding platform-only)

### HR
- users: read, create, update
- departments: read
- shifts: read
- reports: attendance.export, payroll.export, employee.export
- payroll: generate, approve, export
- reimbursements: read, create, approve
- tickets: read
- notifications: read
- policy: full (create, read, update, publish, archive, compliance, reminders, analytics, versions, attachments)
- leave: view_self, view_team, view_org, approve, manage
- learning: view, create, update, manage

### Finance
- payroll: generate, approve, export
- reimbursements: read, create, approve, reject
- reports: payroll.export
- users: read
- notifications: read

### Manager (OrgManager, OrgSupervisor, OrgDepartmentHead, OrgShiftManager)
- users: read, create, update (OrgManager), read (others)
- attendance: checkin, checkout, history, corrections (OrgManager, OrgSupervisor), history (others)
- departments: read, update (OrgManager, OrgDepartmentHead), read (OrgSupervisor, OrgShiftManager)
- shifts: read, update (OrgManager), read (OrgSupervisor, OrgDepartmentHead, OrgShiftManager)
- reports: attendance.export, employee.export (OrgManager), attendance.export (OrgSupervisor, OrgDepartmentHead)
- tickets: read, create, update
- reimbursements: read, create, approve (OrgManager), read, approve (OrgDepartmentHead)
- payroll: generate, approve (OrgManager)
- notifications: read
- policy: read, acknowledge, compliance.view
- leave: view_self, view_team, approve, approve_team (OrgTeamLead, OrgSupervisor, OrgDepartmentHead), approve (OrgManager, OrgShiftManager)
- learning: view (OrgManager, OrgSupervisor, OrgDepartmentHead, OrgShiftManager)

### Employee (OrgEmployee, OrgContractor, OrgIntern, OrgViewer)
- attendance: checkin, checkout, history (OrgEmployee, OrgContractor, OrgIntern), history (OrgViewer)
- tickets: read, create (OrgEmployee, OrgContractor), read (OrgIntern, OrgViewer)
- reimbursements: read, create (OrgEmployee), none (Contractor/Intern/Viewer)
- notifications: read
- leave: apply, view_self (OrgEmployee), view_self (Contractor/Intern/Viewer)
- learning: view (OrgEmployee)

---

## Route-to-Permission Mapping (Frontend)

| Route | Permission Required |
|-------|---------------------|
| `/dashboard` | authenticated |
| `/dashboard/leave` | authenticated |
| `/dashboard/settings` | authenticated |
| `/dashboard/organization` | org.view |
| `/dashboard/org-hierarchy` | org.view |
| `/dashboard/business-units` | departments.read |
| `/dashboard/branches` | org.view |
| `/dashboard/positions` | departments.read |
| `/dashboard/identity-directory` | users.read |
| `/dashboard/workforce/attendance` | attendance.history |
| `/dashboard/workforce/timeline` | attendance.history |
| `/dashboard/workforce/devices` | platform.settings.manage |
| `/dashboard/workforce/shifts` | shifts.read |
| `/dashboard/workforce/rosters` | shifts.read |
| `/dashboard/workforce/leave-calendar` | leave.view_self |
| `/dashboard/workforce/leave-requests` | leave.view_self |
| `/dashboard/workforce/planning` | users.read |
| `/dashboard/workforce/capacity` | users.read |
| `/dashboard/workforce/analytics` | reports.attendance.export |
| `/dashboard/workforce/holidays` | org.settings.manage |
| `/dashboard/scope-ownership` | platform.settings.manage |
| `/dashboard/approval-workflows` | platform.settings.manage |
| `/dashboard/dynamic-roles` | roles.view |
| `/dashboard/hr` | users.read |
| `/dashboard/performance` | performance.view |
| `/dashboard/learning` | learning.view |
| `/dashboard/succession` | succession.view |
| `/dashboard/policies` | policy.read |
| `/dashboard/assets` | asset.read |
| `/dashboard/enterprise` | integration.manage |
| `/dashboard/operations` | platform.settings.manage |
| `/dashboard/reports` | reports.attendance.export |
| `/dashboard/ai-studio` | ai.studio.use |
| `/dashboard/knowledge-center` | knowledge.read |
| `/dashboard/ai-copilot-hub` | ai.copilot.use |
| `/dashboard/ai-analytics` | ai.analytics.read |
| `/dashboard/prompt-manager` | ai.prompt.manage |
| `/dashboard/model-manager` | ai.model.manage |
| `/dashboard/ai-usage` | ai.analytics.read |
| `/dashboard/ai-governance` | ai.governance.manage |
| `/dashboard/open-positions` | recruitment.view |
| `/dashboard/candidate-pipeline` | recruitment.view |
| `/dashboard/org-settings` | org.settings.view |
| `/dashboard/tenant-admin` | admin.tenant.manage |
| `/dashboard/permissions` | roles.view |

---

## API Endpoint Protection (Backend)

### Leave Router (`/api/v1/leave/`)
| Endpoint | Method | Permission | Scope |
|----------|--------|------------|-------|
| `/types` | POST | leave.manage | Org |
| `/types` | GET | authenticated | Org |
| `/types/{id}` | PUT | leave.manage | Org |
| `/balance` | GET | authenticated + view_team/view_org | Org/Dept/Self |
| `/requests` | POST | leave.apply | Self |
| `/requests` | GET | authenticated + view_team/view_org | Org/Dept/Self |
| `/requests/{id}/approve` | POST | leave.approve | Dept |
| `/requests/{id}/approve-team` | POST | leave.approve_team | Team |
| `/requests/{id}/cancel` | POST | owner or leave.manage | Self/Org |

### Learning Router (`/api/v1/learning/`)
| Endpoint | Method | Permission | Scope |
|----------|--------|------------|-------|
| `/categories` | POST | learning.create | Org |
| `/categories` | GET | authenticated | Org |
| `/courses` | POST | learning.create | Org |
| `/courses` | GET | authenticated | Org |
| `/courses/{id}/modules` | POST | learning.create | Org |
| `/enrollments` | POST | learning.view | Self/Org |
| `/enrollments` | GET | learning.view + view_org | Org/Self |
| `/enrollments/{id}/progress` | POST | learning.manage or owner | Self/Org |
| `/sessions` | POST | learning.create | Org |
| `/sessions` | GET | authenticated | Org |
| `/quizzes` | POST | learning.create | Org |
| `/quizzes` | GET | authenticated | Org |
| `/quizzes/{id}/submit` | POST | authenticated | Self |
| `/skills` | POST | learning.manage | Org |
| `/skills` | GET | authenticated | Org |
| `/employee-skills` | POST | learning.update | Self/Org |
| `/employee-skills` | GET | learning.view + view_org | Org/Self |
| `/certificates` | GET | learning.view + view_org | Org/Self |
| `/budget` | GET | learning.view_org | Org |
| `/analytics/dashboard` | GET | learning.view_org | Org |

### Departments/Shifts Router (`/api/v1/org/`)
| Endpoint | Method | Permission | Scope |
|----------|--------|------------|-------|
| `/departments/` | GET | departments.read | Org |
| `/shifts/` | GET | shifts.read | Org |

### Workforce Shift Swaps (`/api/v1/workforce/`)
| Endpoint | Method | Permission | Scope |
|----------|--------|------------|-------|
| `/shifts/swaps` | GET | shifts.read | Org |
| `/shifts/swaps` | POST | shifts.update | Org |
| `/shifts/swaps/{id}/resolve` | POST | shifts.update | Org |

---

## Critical Fixes Applied

1. **Route Authorization Fixes** (`routeAuthorization.js`):
   - `/dashboard/learning`: `learning.view` (was `learning.course.read`)
   - `/dashboard/performance`: `performance.view` (was `performance.cycle.read`)
   - `/dashboard/succession`: `succession.view` (was `succession.plan.read`)
   - `/dashboard/open-positions`: `recruitment.view` (was `recruitment.read`)
   - `/dashboard/candidate-pipeline`: `recruitment.view` (was `recruitment.read`)

2. **Shift Swaps API Alignment** (`workforceService.js`):
   - Frontend now calls `/workforce/shifts/swaps` (matches backend)

3. **Departments/Shifts 403 Fix** (`seed_rbac.py`):
   - Added `departments.read` and `shifts.read` to OrgTeamLead, OrgShiftManager
   - All Manager roles now have department/shift read access

4. **Learning Permissions** (`seed_rbac.py`):
   - Added `learning.*` permissions to OrgHR (manage), OrgManager/OrgSupervisor/OrgDepartmentHead/OrgShiftManager (view), OrgEmployee (view)

5. **Leave Approval Permissions** (`seed_rbac.py`):
   - Added `leave.approve_team` permission for team-scoped approvals
   - Assigned to OrgTeamLead, OrgSupervisor, OrgDepartmentHead
   - Updated OrgManager, OrgShiftManager, OrgDepartmentHead with `leave.approve`

6. **Theme System** (`index.css`):
   - Gray scale now uses CSS variables (`--gray-50` through `--gray-950`)
   - Dark mode: variables defined in `:root`
   - Light mode: variables overridden in `html.light`
   - All Tailwind `gray-*` utilities now theme-aware
   - Scrollbar, selection, focus states use CSS variables

7. **Leave Module Team-Scoped Approval** (`leave.py`):
   - New endpoint: `POST /requests/{id}/approve-team` with `leave.approve_team` permission
   - Department-scoped approval on existing `/approve` endpoint (managers)
   - Team-scoped approval on new `/approve-team` endpoint (team leads)
   - Self-approval prevention on both endpoints

8. **Permission Definitions** (`seed_rbac.py`):
   - Added `leave.approve_team` permission
   - Added `integration.*`, `ai.*`, `knowledge.*` permission modules
   - Fixed permission taxonomy alignment

---

## Remaining Considerations

1. **Team Membership Resolution**: The `leave.approve_team` endpoint assumes Team model has `lead_user_id`. Verify team membership logic matches your org structure.

2. **Carry-Forward Leave**: Not yet implemented in leave balance accrual logic.

3. **Automated RBAC Tests**: No automated tests exist for role-permission validation.

4. **Duplicate API Calls**: React StrictMode + useEffect + Zustand hydration may cause duplicate fetches. Consider using `useSyncExternalStore` or request deduplication.

5. **Frontend Role Normalization**: `usePermission.js` `hasScope()` still checks legacy role names (OrgDepartmentHead, OrgTeamLead). Consider normalizing to baseline roles.

6. **Seed Validation**: Run `validate_rbac_seed()` after seeding to verify SuperAdmin has all permissions.