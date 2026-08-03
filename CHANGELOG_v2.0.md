# Changelog — VisionCore v2.0

## [2.0.0-ga] — 2026-07-27 — General Availability

### Added
- **GA Runtime Validation Suite** (`backend/runtime_validation_ga.py`)
  - 13-phase platform-wide validation
  - API consistency verification (201, 422, 409, 423)
  - Security verification (SQL injection, XSS, CORS)
  - Performance benchmarks
  - Regression verification
  - Frontend file verification
- **RC1.1 Patch Release** (`TODO_rc1_1.md`)
  - Repository re-audit
  - API standardization patches
  - GA readiness tracking

### Changed
- **Sessions router** now registered with `prefix="/auth"` and `tags=["sessions"]`
- **`POST /auth/register`** now returns `201 Created` (was 200)
- **Validation errors** now return `422 Unprocessable Entity` (was 400)
- **Duplicate email** now returns `409 Conflict` (was 400)
- **Account suspended** now returns `423 Locked` (was 400)
- **Change password** validation errors return `422` (was 400)

### Fixed
- Sessions router tag inconsistency (`auth-sessions` → `sessions`)
- Non-standard HTTP status codes for validation errors
- Missing OpenAPI documentation for sessions endpoints

---

## [2.0.0-rc1] — 2026-07-27 — Release Candidate 1

### Added
- **Platform Freeze Baseline** (`PLATFORM_FREEZE_MANIFEST.md`, `PLATFORM_FREEZE_CERTIFICATE.md`)
- **RC1 Certification** (`RC1_CERTIFICATE.md`)
- **RC1 Runtime Validation** (`backend/runtime_validation_rc1.py`) — 13 phases
- **Repository Audit** (`docs/RC1_REPOSITORY_AUDIT.md`)
- **Code Quality Review** (`docs/RC1_CODE_QUALITY_REVIEW.md`)
- **API Standardization Report** (`docs/RC1_API_STANDARDIZATION.md`)
- **Frontend Audit** (`docs/RC1_FRONTEND_AUDIT.md`)
- **Database Optimization Report** (`docs/RC1_DATABASE_OPTIMIZATION.md`)
- **Performance Profile** (`docs/RC1_PERFORMANCE_PROFILE.md`)
- **Security Review** (`docs/RC1_SECURITY_REVIEW.md`)
- **User Journey Documentation** (`docs/RC1_USER_JOURNEYS.md`)
- **Production Deployment Artifacts**
  - Docker Compose (`deploy/docker-compose.yml`)
  - NGINX configuration (`deploy/nginx.conf`)
  - Database init script (`deploy/init-db.sql`)
  - Environment template (`deploy/.env.example`)
  - CI/CD pipeline (`.github/workflows/ci.yml`)
- **Validation Evidence Matrix** (`docs/VALIDATION_EVIDENCE_MATRIX.md`)
- **Performance Benchmark Report** (`docs/PERFORMANCE_BENCHMARK_REPORT.md`)
- **Security Verification Report** (`docs/SECURITY_VERIFICATION_REPORT.md`)
- **Cross-Module Integration Report** (`docs/CROSS_MODULE_INTEGRATION_REPORT.md`)
- **Regression Report** (`docs/REGRESSION_REPORT.md`)

---

## [2.0.0-sprint5] — 2026-07-27 — Asset & Device Management

### Added
- **Asset & Device Management** (Sprint 5)
  - 15 database models (AssetCategory, Asset, Assignment, Maintenance, etc.)
  - 14 CRUD classes
  - 4 service engines (Depreciation, Audit, Compliance, Reports)
  - 40+ EAAC-protected endpoints
  - 8-tab frontend dashboard
  - 12-phase runtime validation suite
- **Asset Management Freeze Manifest** (`ASSET_MANAGEMENT_FROZEN_MANIFEST.md`)

---

## [2.0.0-sprint4] — 2026-07-26 — Talent & Governance

### Added
- **Performance Management** (Sprint 4, Entity 1)
  - 9 modules: Cycles, KPIs, Goals, Reviews, Feedback, Ratings, PIPs, Promotions, Analytics
  - 6 service engines (KPI, Goal Scoring, Rating Normalization, Analytics, Calibration, Promotion)
  - 46 runtime tests
- **Policy Center & Compliance** (Sprint 4, Entity 2)
  - 17 modules: Categories, Tags, Documents, Versions, Distribution, etc.
  - 6 service engines (Policy, Distribution, Compliance, Signature, Reminder, Search)
  - 55 runtime tests
- **Sprint 4 Freeze Certificate** (`SPRINT4_FREEZE_CERTIFICATE.md`)
- **Performance Freeze Manifest** (`PERFORMANCE_FROZEN_MANIFEST.md`)
- **Policy Center Freeze Manifest** (`POLICY_CENTER_FROZEN_MANIFEST.md`)

---

## [2.0.0-sprint3] — 2026-07-25 — Enterprise HR Core

### Added
- **Leave Management** — types, policies, balances, requests, adjustments
- **Attendance Enhancement** — check-in/out, geofencing, emotion detection
- **Payroll Enhancement** — salary structures, pay grades, advances
- **Recruitment & ATS** — job postings, candidates, applications, interviews
- **HR Command Center** — unified HR dashboard widget

---

## [2.0.0-sprint2] — 2026-07-25 — EAAC

### Added
- **Enterprise Permission System** (Entity 2) — 169 permissions, RBAC
- **Subscription & Feature Management** (Entity 3) — 179 plan configurations
- **Enterprise Data Scope Engine** (Entity 3) — 96 scope rules
- **Resource Ownership Engine** (Entity 3) — 96 ownership policies
- **Approval Workflow Engine** (Entity 4) — 36 workflow templates
- **Dynamic Roles Engine** (Entity 5) — 26 role templates
- **EAAC Integration** (Entity 6) — 18 integration tests
- **EAAC Final Certification** (Entity 7) — 42/42 tests, 100%
- **EAAC Freeze Manifest** (`EAAC_FROZEN_MANIFEST.md`)

---

## [2.0.0-sprint1] — 2026-07-24 — Platform Foundation

### Added
- **Authentication** — JWT, refresh tokens, session management, token blacklist
- **Organization Management** — multi-tenancy, departments, workspace loading
- **Health check endpoint** — `/health`
- **Security headers middleware** — HSTS, XSS, XFO, Content-Type
- **CORS middleware** — configurable allowed origins
- **Rate limiting** — per-endpoint rate limiting dependency
- **Request logging & timing** — middleware with request IDs

---

**Legend**: GA = General Availability, RC = Release Candidate
