# PHASE4_ATTENDANCE_CORRECTION_ARCHITECTURE.md

## 1) Scope & Goals
**Goal:** Provide an enterprise-grade attendance correction/regularization workflow:
- **Employee:** submits correction request with explanation and evidence (optional)
- **Manager:** approves or rejects request (team-scoped; if team graph not available, fallback to org-scoped pending definition)
- **Admin:** performs final override even after rejection/for exceptional cases
- **Audit integration:** every state transition produces an `AuditLog` record
- **Tenant isolation:** all operations are strictly tenant-scoped via `org_id` (derived from authenticated user)

**Primary non-negotiables:**
- Permission-based authorization only (no role-name checks)
- No cross-tenant reads/writes
- Full audit trail with before/after JSON snapshots (redacted)
- Deterministic state transitions (state machine)

---

## 2) Existing system touchpoints (repository analysis, conceptual)
### Current relevant models
- `AttendanceLog` — source of truth for attendance events and statuses.
- `ManualOverride` — already models an override artifact (target_user/admin_user, reason, and employee approval flags).
- `AuditLog` + `AuditService` — foundation for immutable audit events with correlation id and deep redaction.

### Current relevant router
- `backend/app/routers/attendance.py`
  - Has endpoints:
    - `POST /check-in`
    - `GET /logs`
    - `PATCH /logs/{log_id}` (permission `attendance.override`)

**Phase 4.3 requirement:** implement request/approval workflow rather than using `PATCH /logs/{log_id}` directly.

---

## 3) Business Workflow (state machine)
### Recommendation: explicit workflow tables
Use new entities:
- `attendance_requests`
- `attendance_approvals`

This creates a clean separation between:
- request intent (employee)
- decision artifact (manager)
- terminal finalization (admin override)

### Attendance Request lifecycle
States (recommended enum-like values):
1. `submitted` — employee created request
2. `needs_manager_review` — manager queue
3. `approved` — manager approved; correction is ready to apply
4. `rejected` — manager rejected
5. `admin_overridden` — admin final override (terminal)
6. `expired` — optional: request window expired
7. `cancelled` — optional: employee cancelled while pending

### Manager approval lifecycle (secondary artifact)
`attendance_approvals`:
- `pending` | `approved` | `rejected`
- stored per request, immutable decision snapshot with `decision_notes`

### How `AttendanceLog` is updated
When request becomes `approved` or `admin_overridden`:
- update `AttendanceLog.status` (in-place) and record before/after in `AuditLog`.

**Enterprise reason:** keeps Phase 4.3 aligned with existing persistence model and avoids duplicate “correction record” tables.

---

## 4) User journeys

### Employee
1. View personal attendance logs
2. Click “Request correction” for a log/date
3. Submit:
   - target attendance log identifier (or server-derived date + identity)
   - reason category
   - notes
   - optional evidence metadata/URL
4. Track status via `GET /attendance/corrections/my`

### Manager
1. View pending requests for org/team scope
2. Approve or reject with notes
3. Decision triggers:
   - state transition in request
   - write `attendance_approvals`
   - apply attendance changes if `approved`
   - always write audit events

### Admin
1. View rejected (and optionally pending) requests
2. Override with notes + new attendance status
3. Terminal state `admin_overridden`
4. Updates `AttendanceLog.status` and writes audit events

---

## 5) Tenant isolation model
**Tenant boundary source:** authenticated user resolved from DB.

Enforcement rules (non-negotiable):
- Every read/write query includes org scoping:
  - `User.org_id == current_user.org_id`
- For manager queues:
  - If team relationships exist: filter by team membership.
  - If team relationships do not exist yet: use org-scoped manager access.

---

## 6) Audit integration model
**Audit events for every state transition** using `AuditService`.

For each workflow method:
- request creation => `attendance_corrections.requested`
- approval => `attendance_corrections.approved`
- rejection => `attendance_corrections.rejected`
- admin override => `attendance_corrections.overridden`

Audit record content:
- `actor_user_id`, `actor_role_name`
- `tenant_org_id`
- `target_type` (AttendanceRequest/AttendanceLog)
- `target_id` (request id or attendance log id)
- `before_state` and `after_state` snapshots
- `correlation_id`, `ip_address`, `user_agent`

Redaction:
- rely on `AuditService` deep redaction so embeddings/tokens/passwords never persist in cleartext.

---

## 7) Summary
This architecture adds an explicit, auditable employee→manager→admin correction workflow with strict tenant isolation, permission-first enforcement, and consistent audit integration.

