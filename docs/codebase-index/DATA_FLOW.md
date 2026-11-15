# Critical Data Flows

> **Phase 8 — Data Flow & Lifecycle Analysis**  
> **Scope:** End-to-end data transformation pipelines across critical business modules.

---

## 1. Biometric Ingestion & Attendance Clock-In Pipeline

```
[ Client Webcam ]
       │
       ▼
[ MediaPipe Tasks Vision ] ──► (Validates face bounding box, mesh landmarks, blink detection)
       │
       ▼ Base64 / Multipart JPEG (~150 KB)
[ POST /api/v1/attendance/verify-checkin ]
       │
       ▼
[ RateLimiter Check ] ──► (100 req/min per IP via Redis)
       │
       ▼
[ Auth & Session Validation ] ──► (Verifies Bearer JWT + Session JTI against user_sessions)
       │
       ▼
[ AI Biometrics Microservice (ai-service:8002) ]
       │  ├── 1. Liveness Detection: Texture analysis, reflection heuristics, spoof score
       │  └── 2. DeepFace / Facenet: Generates normalized 128-dimensional float32 vector
       ▼
[ PostgreSQL 15+ (pgvector) Cosine Search ]
       │
       │   SELECT id, user_id, (embedding <-> :query_vector) AS cosine_distance
       │   FROM face_embeddings
       │   WHERE org_id = :current_org_id AND is_active = TRUE
       │   ORDER BY embedding <-> :query_vector ASC
       │   LIMIT 1;
       │
       ▼
[ Distance Threshold Check ]
       ├── If cosine_distance <= 0.40: Match Confirmed (Confidence = 1 - distance)
       └── If cosine_distance > 0.40: HTTP 401 Biometric Verification Failed
       │
       ▼
[ Business Rules Validation ]
       ├── Cooldown Check: Ensures > 5 minutes since last check-in (`CHECKIN_COOLDOWN_MINUTES`)
       ├── Geofence Validation: Checks client coordinates against active `geofence_zones`
       └── Shift Alignment: Associates clock-in with current active `shifts` window
       │
       ▼
[ Database Persistence ]
       ├── INSERT INTO attendance_logs (user_id, org_id, timestamp, status, confidence, liveness)
       └── UPDATE attendance_sessions (accumulates daily hours)
       │
       ▼
[ Optional Blockchain Audit Anchoring ]
       ├── Computes SHA-256 of log record: hash(user_id, timestamp, status, location)
       └── Web3 RPC transaction to Ethereum smart contract: `AttendanceAudit.logAttendance(hash)`
       │
       ▼
[ Notification Dispatch ]
       └── In-memory event bus dispatches clock-in confirmation to employee dashboard
```

---

## 2. Multi-Tenant Data Isolation & Query Filtering

Every database query in VisionCore 2.0 is partitioned by organization ID to guarantee multi-tenant security:

```
[ Incoming HTTP Request ]
       │
       ▼
[ HTTP Header: Authorization: Bearer <JWT> ]
       │
       ▼
[ deps.get_current_user ]
       │  ├── Decodes JWT payload: sub=user_id, org_id=token_org_id, jti=session_id
       │  ├── Verifies session_id in user_sessions table (is_active == True)
       │  └── Loads User entity: returns current_user with bound current_user.org_id
       ▼
[ TenantContext Middleware ]
       │  └── Binds org_id to Python contextvars (TenantContext.set(current_user.org_id))
       ▼
[ Service & Repository Layer Execution ]
       │
       ├── Case A: Standard Tenant User (Employee, Manager, OrgAdmin)
       │   └── All repository queries enforce explicit tenant filter:
       │       query.filter(Model.org_id == current_user.org_id)
       │       *Attempting to access another org_id returns HTTP 404 or 403 Forbidden*
       │
       └── Case B: Platform SuperAdmin (`tier='platform'`)
           └── If requesting cross-tenant route under `/tenant`:
               Bypasses single-org filter, allowing platform-wide aggregation.
```

---

## 3. Leave Request Lifecycle & Balance Deduction

```
[ Employee: POST /api/v1/leave/apply ]
       │  (leave_type_id, start_date, end_date, reason)
       ▼
[ Balance & Policy Validation ]
       ├── Checks `leave_policies` for maximum consecutive days and gender scoping
       ├── Checks `business_calendar_service`: computes working days excluding holidays
       └── Queries `leave_balances`: ensures remaining_days >= requested_days
       │
       ▼
[ Approval Workflow Orchestration ]
       ├── Looks up `approval_workflows` for type='leave'
       ├── Evaluates `workflow_conditions` (e.g. if duration > 3 days -> require Director)
       ├── Resolves assigned approver: Department Manager (`departments.manager_id`)
       └── Inserts into `leave_requests` (status='pending') & `approval_requests`
       │
       ▼
[ Manager Action: POST /api/v1/leave/{id}/approve ]
       ├── Validates approver authority (`leave.approve` or assigned stage approver)
       ├── Updates `leave_requests.status = 'approved'`
       ├── Updates `approval_actions.action = 'approved'`
       └── Atomically decrements `leave_balances.remaining_days`
       │
       ▼
[ Event Notification & Calendar Sync ]
       ├── Dispatches push notification and email to employee
       └── Creates entry in department schedule calendar view
```

---

## 4. Payroll Computation & Payslip PDF Generation

```
[ HR / Finance Admin: POST /api/v1/payroll/runs/generate ]
       │  (period_start, period_end, org_id)
       ▼
[ Attendance Aggregation Pipeline ]
       ├── Queries `attendance_logs` for all organization employees across the pay period
       ├── Calculates total scheduled working days via `business_calendar_service`
       ├── Identifies unexcused absent days (excluding approved `leave_requests`)
       └── Computes Loss of Pay (LOP) days: `lop_deduction = (base_salary / total_days) * lop_days`
       │
       ▼
[ Statutory Deduction Engine (`statutory_engine.py`) ]
       ├── Fetches active `salary_structures` for employee pay grade
       ├── Calculates Gross Earnings = Basic + HRA + Special Allowance + Travel
       ├── Computes Statutory Deductions:
       │   ├── Provident Fund (PF): 12% of Basic (capped by statutory limits)
       │   ├── Employee State Insurance (ESI): 0.75% of Gross (if gross < statutory threshold)
       │   ├── Professional Tax (PT): Slabs based on state rules
       │   └── Tax Deducted at Source (TDS): Monthly projected income tax withholding
       └── Net Pay = Gross Earnings - (LOP + PF + ESI + PT + TDS + Loan Repayments)
       │
       ▼
[ Database Record Creation ]
       ├── Inserts master batch record into `payroll_runs` (status='draft')
       └── Inserts itemized lines into `payroll_line_items` and `payrolls`
       │
       ▼
[ Finance Admin Approval: POST /api/v1/payroll/runs/{id}/approve ]
       │
       ▼
[ Programmatic PDF Compilation (`payslip_pdf_service.py`) ]
       ├── Initializes ReportLab `SimpleDocTemplate` canvas
       ├── Renders corporate logo, organization header, employee metadata
       ├── Builds 2-column tabular breakdown (Earnings vs Deductions)
       ├── Calculates alphanumeric checksum and digital signature block
       └── Saves PDF to `app_data/uploads/{org_id}/payslips/{payslip_number}.pdf`
       │
       ▼
[ Payslip Delivery ]
       └── Inserts into `payslips` (status='issued'); makes download link visible in employee portal
```

---

## 5. Employee Invitation & Onboarding Workflow

```
[ OrgAdmin: POST /api/v1/invites/send ]
       │  (email, role_id, department_id, shift_id)
       ▼
[ Token Generation & Email Dispatch ]
       ├── Generates cryptographically secure 64-character token via `secrets.token_urlsafe(48)`
       ├── Inserts into `employee_invites` (expires_at = NOW() + 7 days, status='pending')
       └── Dispatches HTML invitation email with registration link containing token
       │
       ▼
[ Prospective Employee: Opens Registration Link ]
       │  URL: https://attendance.domain/signup?token=<invite_token>
       ▼
[ Frontend: GET /api/v1/public/invites/validate?token=... ]
       │  Validates token existence, expiration, and organization branding
       ▼
[ Prospective Employee: Submits Password & Profile ]
       │  POST /api/v1/public/invites/claim
       ▼
[ User Account Provisioning ]
       ├── Hashes password using Bcrypt (12 rounds)
       ├── Creates record in `users` with preset `org_id`, `role_id`, `department_id`, `shift_id`
       ├── Creates record in `hcm_employee_profiles`
       ├── Marks `employee_invites.status = 'accepted'`
       └── Issues initial JWT access/refresh token pair
       │
       ▼
[ Initial Biometric Enrollment Prompt ]
       └── Directs user to webcam enrollment flow to capture initial facial vector baseline
```
