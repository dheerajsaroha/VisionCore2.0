# PHASE4_ATTENDANCE_CORRECTION_ERD.md

## 1) Decision: Extend `ManualOverride` vs Create `attendance_requests` + `attendance_approvals`

### Option A — Extend existing `ManualOverride`
**Approach:** Add request/approval fields into `manual_overrides` (state machine within same table).

**Pros**
- Minimal tables
- Reuses existing FK to `attendance_logs` and existing admin decision fields

**Cons (enterprise maintainability risks)**
- `manual_overrides` currently mixes concepts:
  - it models an *admin override artifact* and includes employee ZKP approval flags
  - it does not cleanly represent employee → manager → admin lifecycle
- Harder to enforce invariants in code because one table must represent:
  - employee intent
  - manager decision
  - admin finalization
- Audit snapshots become more error-prone because multiple actors write to the same row

### Option B — Create first-class workflow tables (Recommended)
**Approach:**
- Introduce `attendance_requests` (employee-submitted intent)
- Introduce `attendance_approvals` (manager decision snapshots)
- Keep `manual_overrides` as an admin final override artifact (optional linkage)

**Justification (recommended)**
- Clear separation of responsibilities (employee intent vs manager decision vs admin finalization)
- Cleaner state transitions
- Better query performance (pending requests/approvals without scanning overrides)
- Better audit mapping (each transition maps to a clear entity lifecycle)

✅ **Recommendation: Option B**

---

## 2) Current ERD (relevant subset)

### Existing tables (from model snapshot)
- `organizations` (org tenant)
- `users` (employee identity; includes `org_id`)
- `attendance_logs` (attendance events; includes `user_id`, `status`, `is_deleted`)
- `manual_overrides`
  - `target_user_id` → users.id
  - `admin_user_id` → users.id
  - `attendance_log_id` → attendance_logs.id (nullable)
  - `reason_category`, `override_status`, `override_notes`
  - `employee_approved` and `approved_at`

- `audit_logs`
  - exists as `AuditLog` with JSON state fields in `backend/app/db/models/all_models.py`

---

## 3) Recommended ERD (Phase 4.3 additions)

### A) `attendance_requests`
- `id` (PK)
- `org_id` (tenant boundary, FK to `organizations.id`)
- `employee_user_id` (FK → `users.id`)
- `attendance_log_id` (FK → `attendance_logs.id`)
- `reason_category` (enum/text aligned with your attendance correction categories)
- `request_notes` (text)
- `evidence_metadata` (optional JSON/text)
- `state` (enum/text)
- `requested_at`
- `submitted_by_user_id` (optional; usually same as employee)
- `decision_summary` (optional cached text for UI)

### B) `attendance_approvals`
- `id` (PK)
- `attendance_request_id` (FK → `attendance_requests.id`)
- `org_id`
- `manager_user_id` (FK → `users.id`)
- `decision` (approved|rejected)
- `decision_notes`
- `decided_at`

### C) Optional linkage back to existing `manual_overrides`
If you want to preserve current `manual_overrides` meaning as the admin artifact:
- Keep `manual_overrides` as is
- Add one nullable FK from `manual_overrides` to `attendance_requests`:
  - `attendance_request_id` (nullable)

This enables:
- traceability from employee request → manager approval → admin override
- consistent audit snapshots across all stages

---

## 4) ERD Relationships (text form)

- `organizations(1)` ——— `users(N)` (via `users.org_id`)
- `users(1)` ——— `attendance_logs(N)` (via `attendance_logs.user_id`)
- `users(1)` ——— `attendance_requests(N)` (employee requests)
- `attendance_logs(1)` ——— `attendance_requests(N)` (one request per log; enforce via unique constraint if desired)
- `attendance_requests(1)` ——— `attendance_approvals(N)` (one approval row per request; enforce uniqueness)
- `users(1)` ——— `attendance_approvals(N)` (manager decision)
- `attendance_requests(1, optional)` ——— `manual_overrides(N)` (admin artifact linking; nullable)

---

## 5) Constraints & Index recommendations (enterprise)
- Unique constraint:
  - `attendance_requests(employee_user_id, attendance_log_id)` to prevent duplicate requests
- Indexes:
  - `attendance_requests(org_id, state, requested_at)`
  - `attendance_requests(org_id, employee_user_id, requested_at)`
  - `attendance_approvals(org_id, decision, decided_at)`
  - `attendance_approvals(attendance_request_id)`
- Foreign keys always enforce tenant scoping in service layer.

---

## 6) Audit mapping in ERD
- Each state transition is recorded in `audit_logs`:
  - actor, org, action, target_type/target_id
  - before_state/after_state JSON snapshots

