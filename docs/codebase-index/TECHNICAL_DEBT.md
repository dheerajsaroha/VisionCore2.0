# Technical Debt & Architecture Audit

> **Phase 10 — Technical Debt, Code Smells & Architectural Risks**  
> **Classification:** P0 (Critical / Immediate), P1 (High Priority), P2 (Medium Priority), P3 (Low / Housekeeping).

---

## 1. Prioritized Technical Debt Matrix

| ID | Priority | Category | Issue Summary | Impact |
|---|---|---|---|---|
| **TD-01** | **P0** | Security / Ops | Contradictory Nginx `Permissions-Policy` | Blocks browser camera; breaks biometric check-in behind Nginx |
| **TD-02** | **P0** | Security | Hardcoded fallback secrets in compose files | Risk of deploying with default predictable cryptographic keys |
| **TD-03** | **P1** | Architecture | 5 Unmounted router files (62 endpoints) | Dead code; features (`benefits`, `billing`, `integration`) unreachable |
| **TD-04** | **P1** | Layering | Inverted import in `password_reset_service` | Services importing from Routers violates unidirectional layering |
| **TD-05** | **P1** | Maintainability | 6,588-line monolithic `all_models.py` | Massive merge conflict risk and IDE performance degradation |
| **TD-06** | **P2** | Repository | 516 Test PDF files in `app_data/uploads/` | Clutters repo history with test artifacts (~50 MB) |
| **TD-07** | **P2** | Code Hygiene | Empty files (`Identify`, `VisionCore`, `attendance_logs.py`) | Orphaned zero-byte artifacts left in root and model folders |
| **TD-08** | **P2** | Architecture | Controller layer pollution in routers | Routers directly executing DB queries instead of service delegation |
| **TD-09** | **P3** | Scalability | In-memory notification event queue | Notification events lost on server restart or across multi-worker clusters |

---

## 2. Detailed Technical Debt Analysis

### TD-01: Contradictory Nginx `Permissions-Policy` (P0)
- **Location:** `deploy/nginx.conf:15` vs `backend/main.py:65`
- **Problem:**
  `backend/main.py` explicitly updated its header to allow the application origin to use webcams:
  ```python
  response.headers["Permissions-Policy"] = "geolocation=(self), camera=(self), microphone=(self)"
  ```
  However, `deploy/nginx.conf` still has the older configuration:
  ```nginx
  add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
  ```
- **Remediation:** Update `deploy/nginx.conf` to match `backend/main.py`.

---

### TD-02: Hardcoded Secrets in Docker Compose Files (P0)
- **Location:** `deploy/docker-compose.yml:49`, `infrastructure/docker-compose.yml:8,99`
- **Problem:** Fallback defaults provide known credentials:
  ```yaml
  SECRET_KEY: ${SECRET_KEY:-lSybLY2ZIQTa4NZ26tQVo00SfYJputFLm4MusMLobHg}
  POSTGRES_PASSWORD: SecretPassword123
  ```
- **Remediation:** Remove `:-<default>` fallbacks; require variable definitions in `.env` and fail container startup if empty.

---

### TD-03: 5 Unmounted Router Files / 62 Dead Endpoints (P1)
- **Location:** `backend/app/routers/` (`benefits.py`, `billing.py`, `health_router.py`, `integration.py`, `onboarding.py`)
- **Problem:** These 5 files contain 62 endpoints that are fully authored but omitted from `app/routers/__init__.py`. As a result, endpoints like `/api/v1/onboarding` and enterprise webhook integrations are completely unreachable at runtime.
- **Remediation:**
  1. Register `integration.py` and `onboarding.py` under `/enterprise/integration` and `/onboarding` behind proper permission gates.
  2. Formally deprecate and remove `billing.py` (superseded by `subscription.py`) and `health_router.py` (superseded by root `/health`).

---

### TD-04: Inverted Layer Import in `password_reset_service.py` (P1)
- **Location:** `backend/app/services/password_reset_service.py:294`
- **Problem:** A domain service lazily imports from a route controller to avoid a circular dependency:
  ```python
  from app.routers.notifications import _push_notification
  ```
- **Remediation:** Move `_push_notification` out of `app/routers/notifications.py` into a dedicated `app/services/notification_service.py`.

---

### TD-05: Monolithic `all_models.py` (6,588 Lines / 224 Tables) (P1)
- **Location:** `backend/app/db/models/all_models.py`
- **Problem:** Consolidating all 224 models into one file avoids circular import issues but harms maintainability.
- **Remediation:** Split `all_models.py` into domain-scoped packages (`models/identity/`, `models/attendance/`, `models/workforce/`, `models/payroll/`) using explicit foreign key string references (e.g. `ForeignKey("users.id")`).

---

### TD-06: Accumulation of 516 PDF Files in `app_data/uploads/` (P2)
- **Location:** `backend/app_data/uploads/`
- **Problem:** 516 test-generated PDFs (payslips and offer letters) are tracked in the repository tree.
- **Remediation:** Add `backend/app_data/uploads/` to `.gitignore` and run `git rm -r --cached backend/app_data/uploads`.

---

### TD-07: Orphaned Zero-Byte Files (P2)
- **Location:** `Identify`, `VisionCore`, `backend/app/db/models/attendance_logs.py`
- **Problem:** Empty placeholder files clutter repository root and model directories.
- **Remediation:** Delete `Identify`, `VisionCore`, and `attendance_logs.py`.

---

### TD-08: Controller-Level Business Logic Pollution (P2)
- **Location:** Multiple router files in `backend/app/routers/`
- **Problem:** Several routers perform direct ORM session operations and business calculations instead of delegating to domain services.
- **Remediation:** Enforce a strict controller pattern across all 48 routers.

---

### TD-09: In-Memory Event Dispatcher Limitation (P3)
- **Location:** `backend/app/events/` and notification handlers
- **Problem:** Notifications and audit queues run in-memory; scaling across multiple Uvicorn worker processes or cluster nodes results in dropped events.
- **Remediation:** Connect event publishers to Redis Pub/Sub or the existing RabbitMQ service container.
