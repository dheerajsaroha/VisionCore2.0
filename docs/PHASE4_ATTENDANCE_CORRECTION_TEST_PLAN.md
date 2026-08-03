# PHASE4_ATTENDANCE_CORRECTION_TEST_PLAN.md

## 1) Test Strategy Overview
This workflow is a state machine with strict tenant isolation and permission boundaries. Tests must cover:
- correct state transitions
- immutable decision artifacts
- attendance status updates
- audit emission for every transition
- authorization denial paths (negative tests)

Test levels:
- **Unit tests**: service/state transition logic (no HTTP)
- **Integration tests**: router endpoints with dependency overrides/mocks
- **Security tests**: cross-tenant denial and permission enforcement

---

## 2) Positive Tests

### 2.1 Request creation
**Case:** Employee creates correction request
- Arrange:
  - create org, user, attendance_log (org-scoped)
  - enable audit
- Act:
  - call `POST /attendance/corrections`
- Assert:
  - `attendance_requests.state == 'submitted'`
  - request row belongs to tenant org
  - audit event exists with action `attendance_corrections.requested`
  - before_state/after_state stored with redaction

### 2.2 Manager approval
**Case:** Manager approves pending request
- Arrange:
  - create `submitted` request
  - create manager user with approval permission
- Act:
  - `POST /attendance/corrections/{id}/approve`
- Assert:
  - `attendance_approvals.decision == 'approved'`
  - request state transitions to `approved`
  - `AttendanceLog.status` updated to requested/allowed new status
  - audit event exists with action `attendance_corrections.approved`

### 2.3 Manager rejection
**Case:** Manager rejects pending request
- Assert:
  - request state transitions to `rejected`
  - attendance_approvals row with decision `rejected`
  - AttendanceLog remains unchanged (unless product requires explicit marking)
  - audit event exists with action `attendance_corrections.rejected`

### 2.4 Admin override
**Case:** Admin overrides rejected request
- Act:
  - `POST /attendance/corrections/{id}/override`
- Assert:
  - request state becomes `admin_overridden`
  - AttendanceLog.status updated to `new_attendance_status`
  - (optional) `manual_overrides` created/linked if compatibility mapping enabled
  - audit action `attendance_corrections.overridden`

---

## 3) Security Tests

### 3.1 Cross-tenant access
- Employee from Org A cannot:
  - read Org B’s correction requests via `/my` filters
  - approve/reject/override any request not in their tenant
- Manager and Admin must also be org-scoped.

**Expected:** 404 for tenant-isolated reads; 403 for authorization failures.

### 3.2 Unauthorized approval
- Employee calls approve endpoint without permission
- **Expected:** 403 permission denied

### 3.3 Unauthorized override
- Manager without override permission calls override endpoint
- **Expected:** 403 permission denied

---

## 4) Audit Tests (Foundation)

For each transition ensure:
1. Audit entry exists
2. Actor metadata stored
3. Tenant id stored
4. Correlation id preserved (if middleware provides it)
5. before_state/after_state are redacted
6. Status field is `success` (or appropriate failure semantics)

### 4.1 Request audit
- action: `attendance_corrections.requested`
- target_type/id mapping correct

### 4.2 Approval audit
- action: `attendance_corrections.approved`
- includes attendance log before/after

### 4.3 Rejection audit
- action: `attendance_corrections.rejected`
- includes request state transition

### 4.4 Override audit
- action: `attendance_corrections.overridden`
- includes final admin applied attendance status and reason

---

## 5) Negative/Edge Tests
- Reject/approve when request is already terminal => 409 conflict
- Override in invalid state => 409 or 403 depending on policy
- Invalid `new_attendance_status` => 400 validation
- Invalid reason_category => 400 validation

---

## 6) Recommended Test Fixtures
- Tenant fixtures: orgA, orgB
- Users:
  - employee in orgA
  - manager in orgA
  - admin in orgA
  - actor user in orgB
- Attendance logs:
  - one in orgA
  - one in orgB
- Permission fixtures:
  - ensure `attendance.corrections.*` permissions exist

---

## 7) Success Criteria
- All positive tests pass
- All security tests pass
- Audit tests validate both persistence and redaction
- No cross-tenant data leakage occurs

