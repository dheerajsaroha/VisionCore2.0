# PHASE4_ATTENDANCE_CORRECTION_API_SPEC.md

## 0) Security/Permissions Principles (mandatory)
- **Permission-first** authorization (no hard-coded role-name checks)
- All endpoints are tenant-scoped using `User.org_id` resolved from authenticated user
- Every state transition emits an `AuditLog` via `AuditService`
- All protected endpoints require explicit permissions

> Permission strings must match your RBAC `permissions.name` values.

---

## 1) Common Payload/Response Types

### 1.1 AttendanceCorrectionRequestPayload (Employee)
- `attendance_log_id: int`
- `reason_category: string` (enum-aligned)
- `notes: string` (required, non-empty)
- `evidence_url?: string`
- `evidence_metadata?: object`

Validation rules:
- `attendance_log_id` must belong to authenticated employee’s `org_id`
- reason_category must be from the allowed set
- terminal states cannot be re-submitted

### 1.2 DecisionNotesPayload (Manager)
- `decision_notes?: string`

### 1.3 OverridePayload (Admin)
- `override_notes: string` (required)
- `new_attendance_status: string` (must be valid `AttendanceLog.status`)
- `reason_category: string`

---

## 2) Employee APIs

### 2.1 POST `/attendance/corrections`
**Permission:** `attendance.corrections.request`  
**Request body:** `AttendanceCorrectionRequestPayload`

**Response (200/201):**
- `request_id: int`
- `state: string`
- `created_at: datetime`

**Server behavior:**
- creates `attendance_requests` row (`state=submitted`)
- if manager auto-queue exists, transition to `needs_manager_review`
- emits audit action: `attendance_corrections.requested`

### 2.2 GET `/attendance/corrections/my`
**Permission:** `attendance.corrections.view.my`

**Query params (optional):**
- `status?: string`
- `from?: datetime`
- `to?: datetime`
- `skip?: int`
- `limit?: int`

**Response:** array of request summaries:
- `request_id`
- `attendance_log_id`
- `current_state`
- `requested_at`
- `last_manager_decision?: {decision, decided_at}`
- `final_admin_status?: {status, overridden_at}`

---

## 3) Manager APIs

### 3.1 GET `/attendance/corrections/pending`
**Permission:** `attendance.corrections.view.pending`

**Response:** list of pending requests for manager scope:
- `request_id`
- `employee_id` (target user id)
- `employee_name`
- `attendance_log_id`
- `requested_at`
- `reason_category`
- `notes`

### 3.2 POST `/attendance/corrections/{id}/approve`
**Permission:** `attendance.corrections.approve`

**Request body:** `DecisionNotesPayload`

**Response:**
- `request_id`
- `state: 'approved'`
- `decided_at`

**Rules:**
- request must be in `submitted` or `needs_manager_review`
- write immutable `attendance_approvals` decision row
- update request state to `approved`
- apply correction to `AttendanceLog.status` (audit-captured)
- emit audit action: `attendance_corrections.approved`

### 3.3 POST `/attendance/corrections/{id}/reject`
**Permission:** `attendance.corrections.reject`

**Request body:** `DecisionNotesPayload`

**Response:**
- `request_id`
- `state: 'rejected'`
- `decided_at`

**Rules:**
- request must be in `submitted` or `needs_manager_review`
- approval/decision writes `attendance_approvals` row
- update request state to `rejected`
- AttendanceLog remains unchanged (unless product requires marking it)
- emit audit action: `attendance_corrections.rejected`

---

## 4) Admin APIs

### 4.1 POST `/attendance/corrections/{id}/override`
**Permission:** `attendance.corrections.override`

**Request body:** `OverridePayload`

**Response:**
- `request_id`
- `state: 'admin_overridden'`
- `overridden_at`

**Rules:**
- request must be in `approved` or `rejected` (product may allow `submitted`)
- admin override transitions request to `admin_overridden`
- update `AttendanceLog.status` to `new_attendance_status`
- optionally create a `manual_overrides` row as compatibility artifact
- emit audit action: `attendance_corrections.overridden`

---

## 5) Error Responses (standard)
- 400: validation error (invalid status/category/date)
- 401: auth missing/invalid token
- 403: permission denied
- 404: target request/log not found within tenant
- 409: conflict (request already in terminal state)

---

## 6) Notes on backward compatibility
- Existing `PATCH /attendance/logs/{log_id}` must remain but be permission-guarded.
- Phase 4.3 UI and workflow should use the correction endpoints; direct log patch remains admin-only emergency path.

