# Application Architecture & System Design

> **Phase 4 — Architecture Discovery**  
> **Pattern:** Multi-Tenant Modular Monolith with Extracted AI Microservice & Reverse Proxy Ingress.

---

## 1. Architectural Pattern Overview

VisionCore 2.0 employs a **Modular Monolith** architecture pattern with targeted microservice extraction for computationally intensive workloads (deep learning biometrics) and edge reverse proxying:

```
┌─────────────────────────────────────────────────────────────┐
│                   React 19 SPA (Client)                     │
│    Webcam Capture + MediaPipe Face Mesh + Zustand Stores    │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS / JSON
┌──────────────────────────────▼──────────────────────────────┐
│                  Nginx Reverse Proxy / Ingress              │
│       TLS Termination + Rate Limiting + Security Headers    │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / Reverse Proxy
┌──────────────────────────────▼──────────────────────────────┐
│             FastAPI Modular Monolith (Backend)              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │   Middleware: Security, Correlation ID, Metrics, CORS │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │   Dependency Injection: Auth, RBAC, EAAC, TenantCtx   │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │   API Routers (48 Mounted Modules / 756 Endpoints)    │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │   Domain Services (128 Modules): Attendance, Payroll  │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │   Data Access: CRUD (22) + Repositories (4)           │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │   SQLAlchemy 2.0 ORM Models (all_models.py - 224 Tbl) │  │
│  └───────────────────────────┬───────────────────────────┘  │
└──────────────┬───────────────┴───────────────┬──────────────┘
               │                               │
┌──────────────▼──────────────┐ ┌──────────────▼──────────────┐
│  AI Biometrics Service      │ │   PostgreSQL 15+ + pgvector │
│  (FastAPI on Port 8002)     │ │   - 224 Relational Tables   │
│  - DeepFace / InsightFace   │ │   - 128-dim Cosine Vector   │
│  - Strict Liveness Engine   │ │   - HNSW Index (m=16,ef=64) │
└─────────────────────────────┘ └─────────────────────────────┘
```

The system organizes domain concerns into cohesive modules that share a centralized database schema (`backend/app/db/models/all_models.py`), while isolating data queries by organization boundary (`org_id`).

---

## 2. Architectural Layers & Responsibilities

### 2.1 Presentation Layer (Frontend SPA)
- **Framework:** React 19.2.4 with Vite 8.0.1.
- **Responsibilities:**
  - Rendering responsive dashboard views across 60 application pages.
  - Video stream ingestion from client webcams via `react-webcam`.
  - Client-side face landmark and liveness validation via `@mediapipe/tasks-vision` before server upload.
  - State management via Zustand stores (`authStore`, `permissionStore`, `subscriptionStore`).
  - Route authorization guards (`ProtectedRoute.jsx`, `accessControl.js`).

### 2.2 Ingress & Security Middleware Layer
- **Components:** `Nginx` and FastAPI middleware stack (`main.py`, `app/middleware/`).
- **Responsibilities:**
  - TLS termination and standard security header injection (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`).
  - Request correlation tracking via `correlation_id.py` (injects `X-Request-ID`).
  - Distributed request rate limiting via Redis token bucket with fallback to in-memory sliding windows.
  - Prometheus metrics instrumentation via `MetricsMiddleware` recording request counts and latency histograms.

### 2.3 Dependency Injection & Authorization Layer (`app/api/deps.py`)
- **Responsibilities:**
  - Database session lifecycle management (`get_db` yielding `SessionLocal`).
  - Bearer JWT decoding, signature verification, and expiration enforcement.
  - Active session binding: validates `jti` in token against active database records in `user_sessions`.
  - Permission enforcement via `require_permission("module.action")`.
  - Role scoping: `require_role()`, `require_admin()`, and `get_current_superadmin()`.
  - SaaS entitlement gating: `require_feature("feature_code")` and `require_subscription()`.

### 2.4 Domain Service Layer (`app/services/`)
- **128 Domain Service Modules:**
  - `attendance_controller.py` & `attendance_pipeline/`: Coordinates biometric matching, cooldown checks, and shift window logic.
  - `biometrics_service.py` & `biometric_queue.py`: Manages face embeddings, similarity thresholds, and encryption.
  - `payroll_service.py` & `statutory_engine.py`: Computes gross-to-net pay, loss of pay (LOP), and tax deductions.
  - `leave_service.py` & `leave_policy_engine.py`: Manages leave accrual, gender-scoped rules, and approval escalation.
  - `workflow_engine.py` & `approval_service.py`: Multi-stage approval state machines for attendance and reimbursements.
  - `audit_service.py` & `blockchain.py`: Immutable audit logging and optional Ethereum smart contract anchoring.

### 2.5 Data Access Layer (`app/crud/` & `app/repositories/`)
- **Components:** 22 CRUD modules and 4 dedicated repositories.
- **Responsibilities:**
  - Encapsulating database queries and transactions.
  - Applying mandatory multi-tenant filter clauses (`WHERE org_id = :org_id`).
  - Enforcing soft-delete filtering (`WHERE is_deleted = 0`).

### 2.6 Persistence Layer
- **PostgreSQL 15+:** Relational storage for 224 tables.
- **`pgvector` Extension:** Stores 128-dimensional facial embedding vectors with an HNSW cosine index (`CREATE INDEX idx_face_embeddings_hnsw ON face_embeddings USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)`).
- **Redis 7.0+:** Distributed cache, token blacklist, and rate-limiting counters.

---

## 3. Multi-Tenancy Architecture

VisionCore 2.0 implements **Logical Multi-Tenancy (Row-Level Isolation)** within a shared database:

```
Request Header: Authorization Bearer JWT
          │
          ▼
   Extract user_id ──► Fetch User ──► User.org_id
                                            │
          ┌─────────────────────────────────┴─────────────────────────────────┐
          │                                                                   │
          ▼                                                                   ▼
Regular Tenant User                                              SuperAdmin (Cross-Tenant)
Queries automatically injected with:                             Bypasses org filter when org_id
  filter(Model.org_id == current_user.org_id)                     is not explicitly supplied
```

### Key Multi-Tenant Safeguards:
1. **Tenant Isolation Foreign Key:** More than 200 domain tables carry a mandatory `org_id` column referencing `organizations.id`.
2. **Context Enforcement:** `tenant_context.py` and `tenant_isolation.py` middleware bind the authenticated organization ID to the request execution state.
3. **Repository Scope Enforcement:** CRUD helpers require `org_id` on all write and search operations.
4. **SuperAdmin Privilege Separation:** SuperAdmin accounts operate at the platform level (`tier='platform'`), allowing cross-tenant administration through the dedicated `/tenant` router (`deps.get_current_superadmin`).

---

## 4. Role-Based Access Control (RBAC) & EAAC Model

The system implements Enterprise Adaptive Access Control (EAAC), reconciling 26 fine-grained backend roles into 6 baseline enterprise roles:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        6 BASELINE ROLES                                │
├──────────────┬──────────────────┬──────────────────────────────────────┤
│ Role         │ Scope            │ Primary Responsibilities             │
├──────────────┼──────────────────┼──────────────────────────────────────┤
│ SuperAdmin   │ Platform-wide    │ Full platform access, all tenants     │
│ OrgAdmin     │ Organization     │ Full organization administration     │
│ HR           │ Organization     │ Employee records, leave, hiring, L&D │
│ Finance      │ Organization     │ Payroll runs, reimbursements, billing│
│ Manager      │ Team/Department  │ Attendance approvals, team rosters   │
│ Employee     │ Self             │ Self-service clock-in, leave, tickets│
└──────────────┴──────────────────┴──────────────────────────────────────┘
```

### Permission Taxonomy
Permissions follow the strict `module.action` format:
- `attendance.checkin`, `attendance.corrections`, `attendance.export`
- `leave.apply`, `leave.approve`, `leave.view_team`, `leave.manage`
- `payroll.generate`, `payroll.approve`, `payroll.export`
- `users.read`, `users.create`, `users.impersonate`

### SaaS Subscription Feature Gating
In addition to RBAC permissions, routes are gated by tenant subscription plans (`starter`, `professional`, `enterprise`):
- `require_feature("biometrics_advanced")`
- `require_feature("ai_copilots")`
- `require_limit("max_employees")`

---

## 5. Communication Patterns

1. **Synchronous HTTP/REST:** Primary client-to-server and inter-service protocol using JSON payloads.
2. **Real-Time Video Stream WebSocket:** `ws_video.py` mounts `/ws/video` for low-latency frame ingestion during continuous attendance tracking.
3. **Server-Sent Events (SSE):** `sse_audit.py` streams live security and compliance audit events to administrative dashboards.
4. **Asynchronous Background Processing:** FastAPI `BackgroundTask` primitives execute non-blocking operations (audit log persistence, email dispatch, notification pushes).
5. **Smart Contract RPC:** Synchronous JSON-RPC to Ethereum/EVM nodes via `web3.py` for immutable audit anchoring.

---

## 6. Resilience & Graceful Degradation

- **Redis Unavailability:** If the Redis cluster goes offline, `rate_limit.py` seamlessly falls back to an in-memory sliding window counter (`_fallback_windows`), and session blacklisting falls back to synchronous PostgreSQL lookups in `user_sessions`.
- **Database Connection Pooling:** Managed via SQLAlchemy `QueuePool` with pool pre-ping enabled to discard dead connections.
- **Biometric Microservice Fallback:** If the standalone `ai-service` is unreachable, backend modules can fall back to local CPU-based Haar cascade and face recognition processing where configured.
