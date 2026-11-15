# Comprehensive Code Symbol Index

> **Phase 3 — Code Symbol Indexing**  
> **Extraction Source:** Python AST Symbol Table Walker & Frontend Static Inspection across 491 Python files and 178 JS/JSX files.

---

## 1. Primary Entry Points

| Entry Point | File Path | Scope & Responsibility |
|---|---|---|
| `app = FastAPI(...)` | `backend/main.py:41` | Primary backend REST API application serving `/api/v1` routes and middleware |
| `lifespan(app)` | `backend/main.py:33` | Application startup/shutdown manager; executes `create_tables()` on launch |
| `app = FastAPI(...)` | `ai-service/app/main.py:5` | Biometrics AI microservice entry point serving face enrollment and verification |
| `app = FastAPI(...)` | `backend/gateway/main.py:14` | Microservice reverse proxy gateway prototype with async HTTPX forwarder |
| `createRoot(...)` | `frontend/src/main.jsx:10` | React 19 DOM root renderer mounting `<App />` |
| `AppRoutes` | `frontend/src/App.jsx:98` | Core React Router v7 route switcher with Suspense boundaries |

---

## 2. Core Dependency Injection Functions (`app/api/deps.py`)

| Function Name | Parameters | Return Type | Responsibility |
|---|---|---|---|
| `get_db()` | None | `Generator[Session, None, None]` | Yields a thread-local SQLAlchemy `SessionLocal` and closes it on request completion |
| `get_current_user(...)` | `db: Session`, `token: str` | `User` | Decodes JWT access token, checks session JTI in `user_sessions`, and fetches active user |
| `get_current_active_user(...)` | `current_user: User` | `User` | Validates `current_user.is_active` and non-deleted status |
| `get_current_superadmin(...)` | `current_user: User` | `User` | Enforces platform-level `SuperAdmin` role requirement |
| `require_admin(...)` | `current_user: User` | `User` | Enforces `OrgAdmin` or `SuperAdmin` administrative role |
| `require_manager_or_admin(...)` | `current_user: User` | `User` | Enforces minimum role elevation of `Manager` |
| `require_permission(...)` | `required_perm: str` | `Callable` | FastAPI dependency factory enforcing fine-grained `module.action` permission checks |
| `has_permission(...)` | `user: User`, `permission: str`, `db: Session` | `bool` | Core evaluator checking role permissions, dynamic roles, and wildcard grants |
| `require_role(...)` | `required_role: str` | `Callable` | Enforces exact baseline or dynamic role membership |
| `require_feature(...)` | `feature_code: str` | `Callable` | Gating dependency checking tenant's active subscription entitlements |
| `require_limit(...)` | `limit_type: str` | `Callable` | Checks resource consumption against licensing quotas (e.g. employee seat cap) |
| `require_subscription(...)` | None | `Callable` | Ensures organization holds an active, non-expired subscription plan |

---

## 3. Core Infrastructure & Security Symbols (`app/core/`)

### 3.1 Configuration (`app/core/config.py`)
- **`Settings` (Class, inherits `BaseSettings`):**
  - `APP_NAME: str` = `"Face Detection Attendance System"`
  - `ENVIRONMENT: str` = `"development" | "staging" | "production"`
  - `SECRET_KEY: str`: Must be at least 32 characters; validated via `@field_validator`.
  - `DATABASE_URL: str`: Dynamically formats PostgreSQL connection string with URL-encoded passwords.
  - `FACE_DISTANCE_THRESHOLD: float` = `0.40` (Cosine distance threshold).
  - `REFRESH_COOKIE_NAME: str` = `"visioncore_refresh"` (HttpOnly cookie name).
  - `ENFORCE_SUBSCRIPTION_LIMITS: bool` = `True`.
  - `EMAIL_TRANSPORT: str` = `"console" | "smtp" | "brevo" | "resend"`.
  - `get_settings()`: `@lru_cache` factory returning singleton `settings`.

### 3.2 Security & Cryptography (`app/core/security.py`)
- **`verify_password(plain_password: str, hashed_password: str) -> bool`:** Bcrypt verification against salt.
- **`get_password_hash(password: str) -> str`:** Generates Bcrypt hash with 12 rounds.
- **`create_access_token(data: dict, expires_delta: timedelta) -> str`:** Signs JWT access token with JTI.
- **`create_refresh_token(data: dict) -> str`:** Signs long-lived refresh token.
- **`is_token_blacklisted(token: str) -> bool`:** Checks token revocation state in Redis or database.

### 3.3 Rate Limiting (`app/core/rate_limit.py`)
- **`rate_limit_dependency(max_requests: int, window_seconds: int)`:** Dependency factory returning an IP-scoped rate limiter. Evaluates Redis token bucket first; falls back gracefully to `_fallback_windows` sliding counter.

---

## 4. Key Domain Service Classes (`app/services/`)

### 4.1 Attendance & Biometrics
- **`AttendanceController` (`app/services/attendance_controller.py`):**
  - `process_checkin(db, user_id, org_id, verification_data)`: Validates shift window, evaluates cooldown period (5 min default), creates `AttendanceLog`.
  - `process_checkout(db, user_id, org_id)`: Finalizes daily attendance session and calculates total worked hours.
- **`BiometricsService` (`app/services/biometrics_service.py`):**
  - `match_face_embedding(db, org_id, vector, threshold=0.40)`: Queries `face_embeddings` using the `<->` cosine operator via pgvector.
  - `enroll_user_face(db, user_id, org_id, embedding_vector)`: Stores or updates enrolled vector.
- **`FaceEngine` (`ai-service/app/services/face_engine.py`):**
  - `extract_embedding(image_bytes: bytes) -> list[float]`: Generates 128-dimensional normalized facial embedding vector using DeepFace/Facenet.
- **`LivenessEngine` (`ai-service/app/services/liveness.py`):**
  - `evaluate_liveness(image_bytes: bytes) -> tuple[bool, float]`: Evaluates texture, eye aspect ratio, and spoof indicators.

### 4.2 Payroll & Statutory Engine
- **`PayrollService` (`app/services/payroll_service.py`):**
  - `run_payroll_cycle(db, org_id, period_start, period_end)`: Gathers attendance records, executes LOP deductions, calculates taxes, and generates payslips.
- **`StatutoryEngine` (`app/services/statutory_engine.py`):**
  - `calculate_deductions(salary_structure, gross_pay)`: Evaluates Provident Fund, ESI, Professional Tax, and Income Tax TDS based on active `StatutoryRule` records.
- **`PayslipPDFService` (`app/services/payslip_pdf_service.py`):**
  - `generate_payslip_pdf(payslip_data) -> bytes`: Compiles programmatic ReportLab PDF document with corporate branding and earnings breakdown.

### 4.3 Leave Engine
- **`LeaveService` (`app/services/leave_service.py`):**
  - `apply_leave(db, user_id, leave_type_id, start_date, end_date)`: Validates leave balance, checks overlap, creates `LeaveRequest`.
  - `approve_leave(db, request_id, approver_id)`: Deducts `LeaveBalance`, updates request status, and dispatches notification.
- **`BusinessCalendarService` (`app/services/business_calendar_service.py`):**
  - `is_working_day(date, org_id)`: Checks date against company holiday calendars and weekend policies.

---

## 5. Core Persistence Entity Classes (`app/db/models/all_models.py`)

All models inherit from `app.db.models.base.Base` (`DeclarativeBase`):

| Model Class | Mapped Table | Primary Key | Key Foreign Keys | Purpose |
|---|---|---|---|---|
| `User` | `users` | `id: int` | `org_id`, `role_id`, `department_id`, `shift_id` | Core user identity, credentials, employment status |
| `Organization` | `organizations` | `id: int` | None | Multi-tenant tenant boundary |
| `Role` | `roles` | `id: int` | None | Baseline RBAC roles (SuperAdmin, OrgAdmin, HR, etc.) |
| `Permission` | `permissions` | `id: int` | None | Granular `module.action` permission definitions |
| `UserSession` | `user_sessions` | `id: int` | `user_id` | Active JWT session tracking with JTI validation |
| `FaceEmbedding` | `face_embeddings` | `id: int` | `user_id`, `org_id` | 128-dimensional biometric vector with HNSW index |
| `AttendanceLog` | `attendance_logs` | `id: int` | `user_id`, `org_id`, `shift_id` | Individual clock-in / clock-out events |
| `LeaveRequest` | `leave_requests` | `id: int` | `user_id`, `org_id`, `leave_type_id`, `approved_by` | Employee leave applications and approval state |
| `Payslip` | `payslips` | `id: int` | `user_id`, `org_id`, `payroll_run_id` | Calculated employee compensation and PDF record |
| `SubscriptionPlan`| `subscription_plans`| `id: int` | None | SaaS pricing tiers (`starter`, `professional`, `enterprise`) |
| `Asset` | `assets` | `id: int` | `org_id`, `category_id` | Enterprise equipment inventory and serial tracking |
| `ApprovalWorkflow`| `approval_workflows`| `id: int` | `org_id` | Multi-stage approval sequence definitions |

---

## 6. Frontend Core Stores & Hooks

- **`useAuthStore` (`frontend/src/store/authStore.js`):**
  - State: `user`, `token`, `isAuthenticated`, `isLoading`.
  - Actions: `login(email, password)`, `logout()`, `refreshSession()`, `updateUserProfile()`.
- **`usePermissionStore` (`frontend/src/store/permissionStore.js`):**
  - State: `myPermissions: string[]`, `userRole: string`.
  - Actions: `fetchMyPermissions()`, `hasPermission(perm) -> bool`.
- **`useSubscriptionStore` (`frontend/src/store/subscriptionStore.js`):**
  - State: `planDetails`, `activeFeatures: string[]`, `limits`.
  - Actions: `fetchSubscription()`, `isFeatureEnabled(code) -> bool`.
- **`ProtectedRoute` (`frontend/src/components/ProtectedRoute.jsx`):**
  - Route wrapper enforcing authentication, role allowlists, and permission scopes before rendering child views.
