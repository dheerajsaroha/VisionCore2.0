# Comprehensive Testing Guide

> **Phase 9 — Testing Infrastructure & Verification Suites**  
> **Extraction Source:** AST inspection of 71 test files across `backend/app/tests` and `ai-service/tests`, plus 19 runtime validation scripts.  
> **Total Automated Test Cases:** 847 tests.

---

## 1. Test Architecture & Harness Configuration

The testing infrastructure is built upon **pytest 8.0+** using FastAPI's `TestClient` and isolated database session fixtures:

### 1.1 Global Configuration (`backend/pytest.ini` & `conftest.py`)
- **`pytest.ini`:**
  ```ini
  [pytest]
  addopts = -q -p no:anyio
  testpaths = app/tests
  pythonpath = .
  ```
- **Plugin Autoload Suppression (`backend/conftest.py`):**
  Sets `os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")` to prevent external AnyIO plugins from interfering with FastAPI test clients in Python 3.12/3.14.

### 1.2 Suite Fixtures (`backend/app/tests/conftest.py`)
1. **`TESTING="true"` Environment Flag:** Informs the rate limiting engine to bypass strict per-IP rate limits during high-volume test runs.
2. **`reset_rate_limiters` (Autouse Fixture):** Clears both in-process `_fallback_windows` and Redis keys (`rate_limit:*`) before every single test case, preventing rate-limit leakage across tests.
3. **`client` Fixture:** Yields an active `TestClient(app)` with the full middleware and lifespan context.
4. **`db` Fixture:** Yields an isolated SQLAlchemy `SessionLocal` database connection and guarantees rollback/closure.

---

## 2. Test Suite Breakdown by Functional Domain (847 Tests)

### 2.1 Authentication & Session Management (15 Files / 63 Tests)
- `auth/test_login.py` (2 tests): Valid credentials, invalid password rejection.
- `auth/test_logout.py` (1 test): Token revocation and session invalidation.
- `auth/test_refresh.py` (1 test): HttpOnly refresh cookie rotation and access token reissue.
- `auth/test_password_reset_flow.py` (18 tests): Token/OTP lifecycle, expiration, account lockout.
- `auth/test_password_reset_delivery.py` (25 tests): Email transport selection (Console, SMTP, Brevo, Resend).
- `auth/test_session_lifecycle_db.py` (3 tests): Database persistence of concurrent user sessions.
- `auth/test_session_token_binding.py` (1 test): Access token JTI validation against `user_sessions`.
- `auth/test_rate_limit_fallback.py` (2 tests): In-memory sliding window rate limiter fallback when Redis is absent.
- `auth/test_change_password.py`, `auth/test_profile_update.py`, `auth/test_token_validation.py` (10 tests).

### 2.2 Attendance & Biometric Pipeline (7 Files / 80 Tests)
- `test_attendance_correction_router.py` (27 tests): Full HTTP lifecycle of correction requests.
- `test_attendance_correction_service.py` (22 tests): Manager approvals, shift duration adjustments.
- `test_attendance_phase6.py` (19 tests): Core attendance check-in, cooldown enforcement, checkout.
- `test_checkin_geofence.py` (6 tests): Validating lat/long coordinates against geofence polygons.
- `test_biometrics_integration.py` (2 tests): Face embedding similarity search against pgvector.
- `test_biometric_security_scope.py` (2 tests): Ensuring biometric vectors are tenant-isolated.
- `test_checkout_workflow.py` (2 tests): Daily working hour accumulation.

### 2.3 Payroll & Statutory Compensation (5 Files / 136 Tests)
- `test_statutory_engine.py` (60 tests): Deep calculation tests for PF, ESI, Professional Tax, and Income Tax withholding across diverse pay grade slabs.
- `test_offer_letters.py` (45 tests): Digital offer letter templating, signing, and PDF creation.
- `test_payslip_pdf.py` (41 tests): ReportLab PDF compilation, table alignment, formatting, and file streaming.
- `test_payroll_lop.py` (14 tests): Loss of Pay (LOP) calculations derived from unapproved attendance absences.
- `test_payslip_self_service.py` (7 tests): Employee access controls for historical payslip retrieval.

### 2.4 Leave & Absence Management (4 Files / 68 Tests)
- `test_organization_leave_policy.py` (40 tests): Leave accrual rules, max consecutive day limits, carry-forward rules.
- `test_gender_scoped_leave.py` (11 tests): Verifying gender restrictions on maternity and paternity policies.
- `test_leave_balance_kpi.py` (8 tests): Accrual computations and leave metrics.
- `test_leave_notifications.py` (9 tests): Email and in-app alerts on leave state transitions.

### 2.5 Recruitment, Onboarding & Invites (5 Files / 141 Tests)
- `test_invites.py` (44 tests): Cryptographic invite token generation, email dispatch, claiming, and expiration.
- `test_referrals_and_careers.py` (32 tests): Candidate referral submissions, public careers job board.
- `test_recruitment_access.py` (21 tests): Role permissions governing candidate pipelines and interview stages.
- `test_hiring_loop.py` (20 tests): Multi-stage interview feedback, scorecard ratings, and candidate transitions.
- `test_offer_letters.py` (24 additional tests included above).

### 2.6 RBAC, EAAC & Data Scopes (7 Files / 62 Tests)
- `test_eaac_static_role_fallback.py` (14 tests): Graceful fallback to static roles when EAAC dynamic policies are unconfigured.
- `test_deps_permission.py` (12 tests): FastAPI `require_permission` dependency evaluation.
- `test_subscription_enforcement.py` (16 tests): Plan gating (`starter` vs `enterprise`) and seat limit checks.
- `test_tenant_security_regression.py` (1 test): Cross-tenant data isolation regression audit.
- `test_rbac_permission_schema.py` (4 tests), `test_rbac_permissions.py` (3 tests), `test_auth_guards.py` (2 tests).

### 2.7 Workforce, Operations & AI Service (12 Files / 175 Tests)
- `test_platform_services.py` (54 tests): System settings, health checks, platform tenant onboarding.
- `test_workflow_conditions.py` (21 tests): Approval workflow boolean condition evaluation engine.
- `test_mounted_routers.py` (20 tests): Route existence verification for all registered routers.
- `test_operations_and_sync.py` (18 tests): Background job queues and offline sync queue processing.
- `test_holiday_calendar.py` (16 tests): Working-day vs holiday calendar calculations.
- `test_hcm_domain.py` (16 tests): Employee profiles, talent pools, and documents.
- `test_ai.py` (14 tests in `ai-service`): Face embedding extraction, emotion scoring, liveness heuristics.
- `test_workflow_domain_bridge.py` (10 tests), `test_workforce_domain.py` (8 tests).

---

## 3. Runtime Integration Validation Suite (19 Scripts)

In addition to the standard pytest test suite, the repository includes 19 standalone **Runtime Validation Scripts** in `backend/` that test the end-to-end running server via live HTTP requests and output verifiable JSON certification reports:

| Validation Script | Output Certification Report | Tested Capability |
|---|---|---|
| `runtime_validation_eaac_final.py` | `eaac_final_certification_report.json` | Complete EAAC dynamic role and permission certification |
| `runtime_validation_subscription.py` | `subscription_validation_report.json` | Multi-tier plan gating and licensing limits |
| `runtime_validation_permission.py` | `permission_validation_report.json` | Comprehensive test across all 21 permission modules |
| `runtime_validation_roles.py` | `roles_validation_report.json` | 26-to-6 RBAC role resolution |
| `runtime_validation_scope.py` | `scope_validation_report.json` | Organization and department data boundary scoping |
| `runtime_validation_workflow.py` | `workflow_validation_report.json` | Multi-stage approval workflow execution |
| `runtime_validation_policy.py` | `runtime_validation_policy_report.json` | Policy center versioning and acknowledgment flows |
| `runtime_validation_performance.py` | `runtime_validation_performance_report.json` | Performance review cycles and goal management |
| `runtime_validation_platform.py` | Console Summary | Core platform health, routes, and baseline data |
| `runtime_validation_ga.py` | Console Summary | General Availability production readiness audit |
| `runtime_validation_rc1.py` | Console Summary | Release Candidate 1 regression test suite |
| `runtime_validation_sprint6_phaseA.py` | Console Summary | Workforce domain core scheduling features |
| `runtime_validation_sprint6_phaseB.py` | Console Summary | Human Capital Management profile features |
| `runtime_validation_sprint6_phaseC.py` | Console Summary | Enterprise integrations and webhook connectors |
| `runtime_validation_sprint7.py` | Console Summary | AI platform, multi-provider LLMs, and copilots |

---

## 4. Test Execution Instructions

### 4.1 Running Backend Pytest Tests
```bash
cd backend

# Execute all 847 tests
uv run --locked pytest app/tests/ -v

# Execute specific functional domain (e.g. payroll)
uv run --locked pytest app/tests/test_statutory_engine.py -v

# Execute with coverage report
uv run --locked pytest app/tests/ --cov=app --cov-report=term-missing
```

### 4.2 Running AI Service Tests
```bash
cd ai-service
pytest tests/ -v
```

### 4.3 Running Live Runtime Validation
```bash
# Ensure backend server is running on localhost:8000
cd backend
uv run --locked python runtime_validation_platform.py
uv run --locked python runtime_validation_eaac_final.py
```

### 4.4 Running Frontend Linting & Production Build
```bash
cd frontend

# Run ESLint static check
npm run lint

# Validate production bundle compilation
npm run build
```
