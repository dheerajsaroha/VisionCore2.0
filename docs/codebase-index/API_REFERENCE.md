# Centralized API Reference

> **Phase 6 — API Indexing & Route Compilation**  
> **Extraction Source:** AST traversal across all 53 router files in `backend/app/routers/`, `backend/main.py`, and `ai-service/app/routers/biometrics.py`.  
> **Total Endpoints Cataloged:** 827 (756 mounted in modular monolith, 62 unmounted router endpoints, 6 AI service endpoints, 3 root endpoints).

---

## 1. Global Endpoints & Ingress Routes

| Method | Full Path | Router / Source | Handler Function | Auth / Gate Requirements | Description |
|---|---|---|---|---|---|
| `GET` | `/` | `backend/main.py` | `read_root` | None (Public) | Root service welcome banner and version string |
| `GET` | `/health` | `backend/main.py` | `health_check` | None (Public) | Basic liveness probe returning status and environment |
| `GET` | `/metrics` | `backend/main.py` | `metrics_endpoint` | None (Prometheus) | Prometheus text-format system metrics export |
| `OPTIONS` | `/{rest_of_path:path}` | `backend/main.py` | `options_handler` | None (CORS) | Global preflight CORS response handler |

---

## 2. AI Biometrics Microservice Endpoints (`ai-service:8002`)

| Method | Path | Handler Function | Request Payload | Response | Description |
|---|---|---|---|---|---|
| `POST` | `/enroll` | `enroll_face` | Multipart Image + `user_id` | `EnrollmentResponse` | Enrolls face image and extracts 128-dim vector |
| `POST` | `/verify` | `verify_face` | Multipart Image + `org_id` | `VerificationResult` | Matches face against enrolled organization vectors |
| `GET` | `/status/{user_id}` | `get_enrollment_status` | Path Parameter `user_id` | `StatusResponse` | Checks if user has an active face enrollment |
| `POST` | `/extract` | `extract_embedding_granular`| Image bytes | `EmbeddingVector` | Low-level normalized vector extraction |
| `POST` | `/liveness` | `extract_liveness_granular` | Image bytes | `LivenessResult` | Evaluates anti-spoof texture and eye aspect ratio |
| `POST` | `/emotion` | `extract_emotion_granular` | Image bytes | `EmotionScores` | Classifies dominant facial expression |

---

## 3. Core Mounted Backend Routers (`backend/app/routers/`)

### 3.1 Authentication & Sessions (`/api/v1/auth`)
- **Prefix:** `/api/v1/auth` (mounted from `auth.py` and `sessions_router.py`)

| Method | Path | Handler Function | Auth / Permission | Description |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/login` | `login` | RateLimit(5/min) | Authenticates credentials; issues access token & HttpOnly refresh cookie |
| `POST` | `/api/v1/auth/refresh` | `refresh_token` | HttpOnly Cookie | Rotates refresh token and issues new session-bound access token |
| `POST` | `/api/v1/auth/logout` | `logout` | `get_current_user` | Revokes current session JTI and blacklists bearer token |
| `POST` | `/api/v1/auth/change-password` | `change_password`| `get_current_user` | Updates user password and revokes all active sessions |
| `POST` | `/api/v1/auth/forgot-password` | `forgot_password`| RateLimit(3/hr) | Initiates password reset flow via configured email transport |
| `POST` | `/api/v1/auth/reset-password` | `reset_password` | Token / OTP | Completes password reset using verified token or 6-digit OTP |
| `GET` | `/api/v1/auth/sessions` | `list_sessions` | `get_current_user` | Lists all active concurrent login sessions for the authenticated user |
| `DELETE`| `/api/v1/auth/sessions/{id}` | `revoke_session` | `get_current_user` | Terminates a specific session by ID |

### 3.2 Users & Identity (`/api/v1/users`)
- **Prefix:** `/api/v1/users` (mounted from `users.py`)

| Method | Path | Handler Function | Auth / Permission | Description |
|---|---|---|---|---|
| `GET` | `/api/v1/users/me` | `get_current_user_info` | `get_current_user` | Returns authenticated user profile and roles |
| `PUT` | `/api/v1/users/me` | `update_current_user` | `get_current_user` | Updates current user's personal profile fields |
| `GET` | `/api/v1/users/` | `list_users` | `users.read` | Paginated search of organization employees |
| `POST` | `/api/v1/users/` | `create_user` | `users.create` | Provisions a new employee record |
| `GET` | `/api/v1/users/{user_id}` | `get_user_by_id` | `users.read` | Fetches single user record by ID |
| `PUT` | `/api/v1/users/{user_id}` | `update_user` | `users.update` | Modifies user details, role, department, or shift |
| `DELETE`| `/api/v1/users/{user_id}` | `delete_user` | `users.delete` | Soft-deletes user record (`is_deleted = 1`) |

### 3.3 Attendance & Clock-In (`/api/v1/attendance`)
- **Prefix:** `/api/v1/attendance` (mounted from `attendance.py`)

| Method | Path | Handler Function | Auth / Permission | Description |
|---|---|---|---|---|
| `POST` | `/api/v1/attendance/verify-checkin` | `verify_and_checkin`| `attendance.checkin` | Live biometric clock-in using face image |
| `POST` | `/api/v1/attendance/checkout` | `checkout` | `attendance.checkout`| Records clock-out and updates session duration |
| `GET` | `/api/v1/attendance/today` | `get_today_attendance` | `get_current_user` | Returns current user's today status |
| `GET` | `/api/v1/attendance/history` | `get_attendance_history` | `attendance.history` | Paginated attendance history with date filters |
| `POST` | `/api/v1/attendance/manual-entry` | `manual_attendance_entry`| `require_admin` | Administrative attendance override creation |
| `GET` | `/api/v1/attendance/export` | `export_attendance_csv` | `attendance.export` | Exports attendance logs to CSV/Excel |

### 3.4 Attendance Corrections (`/api/v1/attendance-corrections`)
- **Prefix:** `/api/v1/attendance-corrections` (mounted from `attendance_correction.py`)
- **27 Endpoints:** Includes `/apply`, `/my-requests`, `/pending-approvals`, `/{id}/approve`, `/{id}/reject`.

### 3.5 Organization, Departments & Shifts (`/api/v1/org`)
- **Prefix:** `/api/v1/org` (mounted from `org.py` and `departments.py`)
- **Endpoints:** `/api/v1/org/current`, `/api/v1/org/settings`, `/api/v1/org/departments`, `/api/v1/org/shifts`, `/api/v1/org/api-keys`.

### 3.6 Leave Management (`/api/v1/leave`)
- **Prefix:** `/api/v1/leave` (mounted from `leave.py`)
- **Endpoints:**
  - `POST /api/v1/leave/apply`: Apply for leave (`leave.apply`).
  - `GET /api/v1/leave/my-balances`: Fetch accrued balances per leave type.
  - `GET /api/v1/leave/requests`: View team/org leave requests (`leave.view_team`).
  - `POST /api/v1/leave/{id}/approve`: Manager approval (`leave.approve`).
  - `POST /api/v1/leave/{id}/reject`: Manager rejection (`leave.reject`).
  - `POST /api/v1/leave/policies`: Configure leave policy (`leave.manage`).

### 3.7 Payroll & Finance Administration (`/api/v1/payroll` & `/api/v1/finance-admin`)
- **Prefixes:** `/api/v1/payroll`, `/api/v1/finance-admin` (mounted from `payroll.py` and `finance_admin.py`)
- **Endpoints:**
  - `POST /api/v1/payroll/runs/generate`: Triggers batch payroll run.
  - `POST /api/v1/payroll/runs/{id}/approve`: Approves payroll batch for disbursement.
  - `GET /api/v1/payroll/my-payslips`: Employee self-service payslip list.
  - `GET /api/v1/payroll/payslips/{id}/download`: Streams ReportLab-generated PDF.
  - `GET /api/v1/finance-admin/statutory-rules`: Statutory tax & deduction parameters.

### 3.8 Workforce Core & Scheduling (`/api/v1/workforce`)
- **Prefix:** `/api/v1/workforce` (mounted from `workforce_router.py`)
- **69 Endpoints:** Complete scheduling, rosters, shift swaps, time entries, breaks, overtime, comp-off, headcount plans, and capacity snapshots.

### 3.9 Human Capital Management (`/api/v1/hcm`)
- **Prefix:** `/api/v1/hcm` (mounted from `hcm_router.py`)
- **60 Endpoints:** Employee education, prior work experience, professional awards, licenses, emergency contacts, talent pools, and employee documents.

### 3.10 Asset Management (`/api/v1/assets`)
- **Prefix:** `/api/v1/assets` (mounted from `asset.py`)
- **55 Endpoints:** Asset registration, barcode tagging, assignment, maintenance logs, depreciation schedules, audits, and vendor purchase orders.

### 3.11 Performance Management (`/api/v1/performance`)
- **Prefix:** `/api/v1/performance` (mounted from `performance.py`)
- **47 Endpoints:** Cycles, goals, reviews, feedback, competency matrices, and PIPs.

### 3.12 Policy Center & Compliance (`/api/v1/policy` & `/api/v1/compliance`)
- **Prefixes:** `/api/v1/policy`, `/api/v1/compliance` (mounted from `policy.py` and `compliance_router.py`)
- **44 Policy Endpoints & 15 Compliance Endpoints:** Policy versions, acknowledgments, legal holds, and GDPR privacy data erasure requests.

### 3.13 AI Platform & Copilots (`/api/v1/ai` & `/api/v1/copilot`)
- **Prefixes:** `/api/v1/ai`, `/api/v1/copilot` (mounted from `ai.py` and `copilot_router.py`)
- **30 AI Endpoints & 8 Copilot Endpoints:** Model providers, prompt manager, cost attribution, and interactive domain copilot sessions.

### 3.14 Cross-Tenant Platform Administration (`/tenant`)
- **Prefix:** `/tenant` (mounted from `tenant_admin.py`)
- **18 Endpoints:** SuperAdmin-only endpoints for provisioning new tenant organizations, viewing cross-tenant usage metrics, and managing global plan catalogs. Gated via `deps.get_current_superadmin`.

---

## 4. Unmounted / Orphaned Router Audit (62 Endpoints)

Static analysis identified 5 router files located in `backend/app/routers/` that are **NOT mounted** in `backend/app/routers/__init__.py`:

| Router File | Defined Endpoints | Intended Business Functionality | Status & Impact |
|---|---|---|---|
| `benefits.py` | 12 endpoints | Employee benefits plans, enrollment, and claims | **Dead Code:** Unreachable at runtime |
| `billing.py` | 10 endpoints | Organization subscription billing and invoice history | **Dead Code:** Superseded by `subscription.py` |
| `health_router.py` | 4 endpoints | Secondary subsystem health probes and checks | **Dead Code:** Root `/health` in `main.py` is used |
| `integration.py` | 28 endpoints | Enterprise webhook connectors and external gateways | **Dead Code:** Referenced in validation scripts |
| `onboarding.py` | 8 endpoints | Multi-step employee onboarding wizard state machine | **Dead Code:** Unreachable at runtime |

**Recommendation:** In accordance with Phase 11 & Phase 12 recommendations, mount `integration.py` and `onboarding.py` behind appropriate permission gates, or formally archive and deprecate them.
