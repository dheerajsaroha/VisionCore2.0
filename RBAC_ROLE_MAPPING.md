# RBAC Role Mapping: 26 Backend Roles → 6 Baseline Roles

## Baseline Role Model (Target)

| Baseline Role | Scope | Description |
|---------------|-------|-------------|
| **SuperAdmin** | Platform | Full platform access — all tenants, all features, all settings |
| **OrgAdmin** | Organization | Full organization administration — users, settings, departments, shifts, payroll, policy center |
| **HR** | Organization | HR operations — employee management, payroll, reimbursements, reports, policy center, leave, L&D |
| **Finance** | Organization | Financial operations — payroll, reimbursements, billing reports |
| **Manager** | Team/Department | Team supervision — attendance oversight, shift management, team reports, leave approval |
| **Employee** | Self | Self-service attendance, tickets, reimbursements, leave requests |

---

## Current 26 Backend Roles → Baseline Mapping

### Platform Tier (8 roles)

| Backend Role | Baseline Role | Notes |
|--------------|---------------|-------|
| SuperAdmin | **SuperAdmin** | Already has `__all__` permissions |
| PlatformAdmin | **SuperAdmin** | Subset of SuperAdmin; merge |
| PlatformViewer | **SuperAdmin** (read-only) | Merge as read-only SuperAdmin |
| PlatformAuditor | **SuperAdmin** (audit-only) | Merge as audit-only SuperAdmin |
| PlatformSupport | **SuperAdmin** (support) | Merge as support-tier SuperAdmin |
| PlatformBilling | **Finance** (platform) | Platform-level billing; keep separate or merge to Finance |
| PlatformDevOps | **SuperAdmin** (devops) | Merge as devops-tier SuperAdmin |
| PlatformSecurity | **SuperAdmin** (security) | Merge as security-tier SuperAdmin |

**Recommendation**: Collapse all Platform tier roles into **SuperAdmin** with permission scopes (full, read-only, audit, support, billing, devops, security) — or keep as distinct for granular platform access. For baseline model, map all to SuperAdmin.

---

### Organization Tier (12 roles)

| Backend Role | Baseline Role | Key Permissions | Gap Analysis |
|--------------|---------------|-----------------|--------------|
| OrgAdmin | **OrgAdmin** | `__org_admin__` (all org permissions) | ✅ Direct mapping |
| OrgManager | **Manager** | users, attendance, departments, shifts, reports, tickets, reimbursements, payroll, leave.approve | Has `departments.read`, `shifts.read`, `leave.approve` |
| OrgHR | **HR** | users, departments, shifts, reports, payroll, reimbursements, policy, leave (view_self, view_team, view_org, approve, manage) | ✅ Has `leave.manage`, `learning` gaps |
| OrgFinance | **Finance** | payroll, reimbursements, reports.payroll, users.read | ✅ Direct mapping |
| OrgSupervisor | **Manager** | attendance, shifts.read, departments.read, reports, tickets, leave.view_team, leave.approve | ✅ Direct mapping |
| OrgTeamLead | **Manager** (limited) | attendance.history, reports, tickets, users.read, leave.view_self, leave.view_team | Missing `leave.approve` |
| OrgEmployee | **Employee** | attendance, tickets, reimbursements, leave.apply, leave.view_self | ✅ Direct mapping |
| OrgContractor | **Employee** (limited) | attendance, tickets, leave.view_self | No payroll/reimbursements create |
| OrgIntern | **Employee** (limited) | attendance, tickets.read, leave.view_self | Read-only tickets |
| OrgViewer | **Employee** (read-only) | attendance.history, reports, tickets.read, users.read, leave.view_self | Read-only |
| OrgDepartmentHead | **Manager** (dept-scoped) | users, attendance, departments, shifts, reports, tickets, reimbursements, policy, leave.view_team | Has `departments.update` |
| OrgShiftManager | **Manager** (shift-focused) | shifts CRUD, attendance.history, users.read | Missing leave permissions |

**Consolidation Plan**:
- **OrgAdmin** → OrgAdmin (keep)
- **OrgManager, OrgSupervisor, OrgTeamLead, OrgDepartmentHead, OrgShiftManager** → **Manager** (with scope variants: org, dept, team, shift)
- **OrgHR** → **HR** (keep distinct for policy/leave/L&D ownership)
- **OrgFinance** → **Finance** (keep distinct)
- **OrgEmployee, OrgContractor, OrgIntern, OrgViewer** → **Employee** (with tier variants: full, contractor, intern, viewer)

---

### System Tier (6 roles) — Keep as-is (internal service accounts)

| Backend Role | Purpose | Baseline Mapping |
|--------------|---------|------------------|
| SystemService | Backend-to-backend | N/A (system) |
| SystemDevice | Edge device check-in | N/A (system) |
| SystemWebhook | Webhook integration | N/A (system) |
| SystemCron | Scheduled jobs | N/A (system) |
| SystemAnalytics | BI read-only | N/A (system) |
| SystemMigration | Data migration | N/A (system) |

---

## Permission Gaps Identified

### 1. Learning Module (L&D) — Missing from Most Roles
| Role | Has learning.* permissions? |
|------|----------------------------|
| OrgAdmin | ✅ (via __org_admin__) |
| OrgHR | ❌ — Should have `learning.view`, `learning.create`, `learning.manage` |
| OrgManager | ❌ |
| OrgFinance | ❌ |
| OrgSupervisor | ❌ |
| OrgDepartmentHead | ❌ |
| OrgShiftManager | ❌ |

**Fix**: Add learning permissions to OrgHR (manage), OrgAdmin (manage), Manager (view), Employee (view)

### 2. Departments/Shifts Read — Missing from Some Manager Roles
| Role | departments.read | shifts.read |
|------|------------------|-------------|
| OrgManager | ✅ | ✅ |
| OrgHR | ✅ | ✅ |
| OrgSupervisor | ✅ | ✅ |
| OrgTeamLead | ❌ | ❌ |
| OrgDepartmentHead | ✅ | ✅ |
| OrgShiftManager | ❌ | ✅ (CRUD) |
| OrgEmployee | ❌ | ❌ |

**Fix**: Ensure `departments.read` and `shifts.read` for all Manager variants and HR

### 3. Leave Module — Inconsistent Approval Permissions
| Role | leave.apply | leave.view_self | leave.view_team | leave.view_org | leave.approve | leave.manage |
|------|-------------|-----------------|-----------------|----------------|---------------|--------------|
| OrgAdmin | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OrgHR | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OrgManager | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| OrgSupervisor | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| OrgTeamLead | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| OrgDepartmentHead | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| OrgEmployee | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |

**Issue**: OrgTeamLead and OrgDepartmentHead missing `leave.approve` — they should approve team/dept leave

### 4. Route Authorization Mismatches
| Route | routeAuthorization.js | Backend Permission | Match? |
|-------|----------------------|-------------------|--------|
| `/dashboard/learning` | `learning.course.read` | `learning.view` | ❌ MISMATCH |
| `/dashboard/leave` | `authenticated` | N/A (frontend) | ✅ |
| `/dashboard/workforce/shifts` | `shifts.read` | `shifts.read` | ✅ |
| `/dashboard/business-units` | `departments.read` | `departments.read` | ✅ |

---

## Recommended Seed Changes

### Add to OrgHR (in seed_rbac.py):
```python
"learning.view", "learning.create", "learning.update", "learning.manage",
```

### Add to Manager roles (OrgManager, OrgSupervisor, OrgDepartmentHead):
```python
"learning.view",
```

### Add to OrgTeamLead:
```python
"leave.approve",
"learning.view",
```

### Add to OrgShiftManager:
```python
"departments.read",
"leave.view_team",
"leave.approve",
```

### Fix routeAuthorization.js:
```javascript
'/dashboard/learning': { permission: 'learning.view' },  // not learning.course.read
```

---

## Frontend Role Name Normalization

Backend role names vs Frontend expected names:

| Backend | Frontend (in DashboardLayout) | Action |
|---------|-------------------------------|--------|
| SuperAdmin | SuperAdmin | ✅ Match |
| PlatformAdmin | — | Collapse to SuperAdmin |
| OrgAdmin | Admin | Map: OrgAdmin → Admin |
| OrgManager | Manager | Map: OrgManager → Manager |
| OrgHR | HR | Keep |
| OrgFinance | Finance | Keep |
| OrgSupervisor | Supervisor | Map to Manager |
| OrgTeamLead | TeamLead | Map to Manager |
| OrgEmployee | Employee | ✅ Match |
| OrgContractor | Contractor | Map to Employee |
| OrgIntern | Intern | Map to Employee |
| OrgViewer | Viewer | Map to Employee |
| OrgDepartmentHead | DeptHead | Map to Manager |
| OrgShiftManager | ShiftManager | Map to Manager |

**In usePermission.js hasScope()**: Update role checks to use normalized baseline roles