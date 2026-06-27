# PHASE4_ATTENDANCE_CORRECTION_IMPLEMENTATION_PLAN.md

## 0) Goal
Implement Phase 4.3 Attendance Correction Workflow as an enterprise-grade, auditable, permission-first, tenant-scoped state machine.

No duplicate business logic; reuse existing patterns:
- RBAC permission enforcement via `Depends(require_permission(...))`
- Audit emission via existing `AuditService`

---

## 1) Dependency-aware exact implementation order (analysis-to-code sequence)

### Step 1 — Database migration plan (design-first)
1. Add table `attendance_requests`
2. Add table `attendance_approvals`
3. (Optional compatibility mapping) Decide link strategy with existing `manual_overrides`:
   - **Recommended:** keep `manual_overrides` as admin final artifact only
   - Add nullable `attendance_request_id` reference in `manual_overrides` (preferred for traceability)
4. Ensure indexes/constraints for:
   - uniqueness of employee+attendance_log request
   - fast manager pending queue queries
   - audit-friendly lookups by request id

**Acceptance criteria:** tenant boundary can be enforced at query-time without joins that lack `org_id` filtering.

---

### Step 2 — Model creation plan
1. Create SQLAlchemy models:
   - `AttendanceRequest` with state enum + timestamps
   - `AttendanceApproval` immutable decision snapshot
2. Add relationships:
   - request → approvals (one-to-many or one-to-one depending on policy)
   - request → employee user
   - request → linked attendance log
3. Add state constraints:
   - enforce transitions in service layer (and optionally DB check constraints)

**Acceptance criteria:** all models are tenant-aware (store org_id explicitly or infer reliably).

---

### Step 3 — Repository layer plan
Create repositories (or reuse CRUD pattern if already present):
1. `attendance_request_repo`
   - `create_request(employee, attendance_log_id, ...)`
   - `get_my_requests(org_id, user_id, filters)`
   - `get_pending_requests_for_manager(org_id, manager_scope, ...)`
2. `attendance_approval_repo`
   - `create_approval(request, manager, decision, notes)`

**Tenant rule:** every repository method must accept `org_id` and enforce it in query filters.

---

### Step 4 — Service layer plan (state machine + audit)
Create a workflow service `attendance_corrections_service` implementing methods:
1. `submit_correction_request(employee_user, attendance_log_id, reason_category, notes, evidence)`
2. `approve_request(manager_user, request_id, decision_notes)`
3. `reject_request(manager_user, request_id, decision_notes)`
4. `admin_override(admin_user, request_id, new_attendance_status, override_reason_category, override_notes)`

**State transitions (mandatory):**
- submitted → needs_manager_review
- submitted/needs_manager_review → approved
- submitted/needs_manager_review → rejected
- approved/rejected → admin_overridden

**AttendanceLog update policy:**
- Update `AttendanceLog.status` only on `approved` and `admin_overridden` (per business rules).
- Keep `AttendanceLog.is_deleted` checks intact.

**Audit integration (mandatory):**
For every transition method:
- Build before_state/after_state payloads (without sensitive/biometric data)
- Call `AuditService` with:
  - `actor`, `action` names: 
    - `attendance_corrections.requested`
    - `attendance_corrections.approved`
    - `attendance_corrections.rejected`
    - `attendance_corrections.overridden`
  - `target_type`: `AttendanceRequest` or `AttendanceLog`
  - `tenant_org_id`
  - `correlation_id` (from middleware if available)

**Transaction rule:** state transition + audit write must be in the same DB transaction where possible (or guarantee audit eventual consistency).

---

### Step 5 — Router plan
Add a dedicated router:
- `backend/app/routers/attendance_corrections.py`

Endpoints mapping to spec:
- POST `/attendance/corrections` (employee)
- GET `/attendance/corrections/my` (employee)
- GET `/attendance/corrections/pending` (manager)
- POST `/attendance/corrections/{id}/approve` (manager)
- POST `/attendance/corrections/{id}/reject` (manager)
- POST `/attendance/corrections/{id}/override` (admin)

**Authorization rule:**
- Every endpoint uses permission dependencies only:
  - Employee: `attendance.corrections.request`, `attendance.corrections.view.my`
  - Manager: `attendance.corrections.view.pending`, approve/reject perms
  - Admin: `attendance.corrections.override`

**Tenant rule:**
- Manager endpoints and employee endpoints must not allow tenant bypass.

---

### Step 6 — Audit integration plan (cross-cutting validation)
1. Ensure `AuditLog` supports JSON before/after states in the configured DB.
2. Ensure `AuditService` redaction is invoked on all state payloads.
3. Ensure correlation id is passed through.
4. Ensure audit logging occurs:
   - on request creation
   - on each approval decision
   - on admin override

---

### Step 7 — Test plan execution order
1. Request creation tests (positive + 403/404 security)
2. Approval workflow tests
3. Rejection workflow tests
4. Admin override tests
5. Audit integration assertions for every transition
6. Permission boundary tests for each endpoint and role
7. Cross-tenant negative tests

---

### Step 8 — Frontend plan (later implementation phase)
- Employee correction request form
- Employee request history timeline
- Manager pending approvals dashboard
- Manager approve/reject UI
- Admin override panel

---

## 2) Risk & Mitigation
- **Risk:** mismatched `AttendanceLog.status` allowed values
  - Mitigation: align `new_attendance_status` with existing constraint (`on_time|late|early|absent|excused|manual_override` or expanded set)
- **Risk:** permission catalog mismatch
  - Mitigation: verify seeded `permissions.name` entries for `attendance.corrections.*`
- **Risk:** audit redaction gaps
  - Mitigation: ensure AuditService redacts known sensitive keys; test with representative payloads
- **Risk:** tenant scoping not consistent
  - Mitigation: repository methods always require org_id and enforce it.

---

## 3) Go/No-Go for coding
**Go** if:
- permissions exist and are enforced uniformly
- audit emission is confirmed end-to-end
- tenant scoping strategy for manager queues is defined
- AttendanceLog status update policy is signed off

**No-Go** if:
- `attendance.corrections.*` permissions are missing/inconsistent
- audit emission fails or cannot persist JSON state
- tenant scoping cannot be enforced reliably for manager queue queries

