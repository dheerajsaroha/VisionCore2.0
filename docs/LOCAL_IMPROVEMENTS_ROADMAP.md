# VisionCore 2.0 — Local Improvements Master Roadmap

This document serves as the persistent, step-by-step execution plan for upgrading VisionCore 2.0 locally. If any session hits a quota or interruption, simply reference this document to pick up exactly where we left off.

---

## Progress Tracker

| Step | Phase Name | Focus Area | Status | Next Action |
| :---: | :--- | :--- | :---: | :--- |
| **1** | **Client-Side Edge Preprocessing & Liveness** | Frontend (`frontend/src/`) | 🟡 **CURRENT FOCUS** | Install MediaPipe, add real-time face detection bounding box & quality check in attendance camera. |
| **2** | **Decoupled Async Biometric Pipeline** | Backend (`backend/app/`) | ⚪ PENDING | Offload embedding matching to async background queue with fast UI feedback. |
| **3** | **Offline-First Kiosk Queue (IndexedDB)** | Frontend & Backend | ⚪ PENDING | Enable local check-in caching during Wi-Fi drops with auto-sync on reconnect. |
| **4** | **Biometric Privacy & Retention Policies** | Backend & Database | ⚪ PENDING | Add employee biometric consent capture & automated data retention purge scripts. |

---

## Detailed Step Breakdown

### Step 1: Client-Side Edge Preprocessing & Liveness (Frontend)
- **Goal:** Never send bad, blank, or multi-face images to the backend. Detect and guide the user in real time in the browser before clocking in.
- **Components to Update:**
  - `frontend/src/pages/Attendance.jsx`
  - `frontend/src/components/CameraModal.jsx` (or webcam capture components)
- **Features to Implement:**
  1. Real-time canvas overlay bounding box (Green = Centered, Yellow = Too close/far, Red = No face detected).
  2. Blur and lighting quality check in the browser.
  3. Simple liveness guidance (e.g., eye blink or head alignment).
  4. Local image crop & compression to under 50 KB before transmission.

---

### Step 2: Decoupled Async Biometric Pipeline (Backend)
- **Goal:** Ensure 100+ concurrent employees clocking in at 9:00 AM do not block FastAPI worker threads.
- **Components to Update:**
  - `backend/app/routers/attendance.py`
  - `backend/app/services/face_engine.py`
  - `backend/app/services/attendance_service.py`
- **Features to Implement:**
  1. Fast receipt acknowledgment (`{"status": "queued", "ticket_id": "..."}`).
  2. Background execution of vector cosine similarity with `pgvector`.
  3. Real-time result polling or WebSocket push to frontend kiosk.

---

### Step 3: Offline-First Kiosk Queue with IndexedDB (Frontend & Backend Sync)
- **Goal:** Tablets and kiosks must work seamlessly even when office internet drops.
- **Components to Update:**
  - `frontend/src/services/offlineQueue.js` (Dexie / IndexedDB)
  - `backend/app/routers/attendance.py` (`/sync-offline` endpoint)
  - `backend/app/db/models/all_models.py` (`offline_sync_queue` table)
- **Features to Implement:**
  1. Client-side local storage of timestamped check-in attempts with compressed face thumbnails.
  2. Network status listener (`navigator.onLine`).
  3. Automatic idempotent batch upload when network connectivity restores.

---

### Step 4: Biometric Privacy & Retention Safeguards (Backend & DB)
- **Goal:** Full alignment with privacy guidelines (GDPR / Indian DPDP Act).
- **Components to Update:**
  - `backend/app/routers/auth.py` and `users.py`
  - `backend/app/services/privacy_service.py`
- **Features to Implement:**
  1. Explicit biometric consent toggle and audit record during onboarding/enrollment.
  2. One-click employee biometric deletion workflow.
  3. Scheduled background task to automatically purge inactive or resigned employee biometric embeddings after tenant retention window.

---

## Resumption Instructions
If any turn or quota limit is reached:
1. Provide this prompt:  
   `"We are following docs/LOCAL_IMPROVEMENTS_ROADMAP.md. Please check the current step and continue."`
2. The agent will inspect git status, read this roadmap, and proceed directly with the next pending task without repeating any completed work.

---

## Additional Necessary Improvements

These items come from a current repository review. They supplement the four implementation phases above and focus on making the platform verifiable, maintainable, and safer to operate. Mark an item complete only after its acceptance criteria are met.

| Priority | Improvement | Acceptance criteria |
| :---: | :--- | :--- |
| **P0** | Fix frontend lint failures and establish a lint baseline | **Complete:** `npm run lint` exits successfully with zero warnings and zero errors; hook behavior was corrected without blanket suppressions. |
| **P0** | Align runtime versions and dependency installation | **Complete:** Python 3.12.x and Node.js 22.12+ (22.x LTS) are documented and aligned across project config, Dockerfiles, CI, and setup guides; CI uses locked uv/npm installs. |
| **P0** | Make CI validate the delivered application | CI runs backend tests, frontend lint and production build, migration checks, and integration tests against PostgreSQL with pgvector and Redis. Required checks must fail the workflow on errors. |
| **P0** | Verify production deployment configuration | Validate Compose/Docker build contexts, health checks, database extensions, environment variables, and startup ordering in a clean deployment test. Document remaining infrastructure requirements and do not treat unverified Kubernetes manifests as production-ready. |
| **P1** | Establish biometric accuracy and fairness evidence | Define and publish a repeatable evaluation protocol for FAR/FRR, liveness/anti-spoofing, lighting and camera conditions, and relevant demographic performance. Set acceptance thresholds before deployment; do not describe the system as validated until results meet them. |
| **P1** | Complete biometric privacy controls | Capture and audit explicit consent; provide an authorized deletion workflow; implement tenant-configurable retention and verified purge behavior; document data access, storage, and incident procedures. |
| **P1** | Reconcile documentation with the checked-in product | Ensure every document linked from `README.md` exists and reflects the current routes, architecture, setup, security posture, and tested deployment. Clearly distinguish implemented, partially implemented, and unverified features. |
| **P1** | Harden offline attendance synchronization | Persist only the minimum necessary data; define encryption, expiry, retry, duplicate prevention, and conflict handling; make sync idempotent and audit its results. Avoid retaining face images/thumbnails offline unless a documented threat and privacy review justifies it. |
| **P2** | Make biometric processing resilient under peak load | Use a durable queue with bounded concurrency, retries, failure visibility, and idempotency; load-test peak check-in volume and measure acknowledgement and completion latency. |
| **P2** | Add operational observability and recovery practices | Provide structured logs, request/tenant correlation, queue and database health metrics, actionable alerts, and tested backup/restore procedures without logging biometric payloads or secrets. |

### Suggested execution order

1. Resolve lint failures and settle the supported runtime/dependency matrix.
2. Update CI so it validates that matrix, the frontend build, backend tests, and database migrations.
3. Reconcile documentation and verify the actual production deployment path.
4. Complete privacy safeguards and biometric accuracy/fairness validation before relying on face recognition for consequential attendance decisions.
5. Load-test and harden asynchronous/offline operation, then add operational recovery checks.

### Progress: P0 frontend lint baseline

**Complete.** Removed genuine unused imports and bindings, corrected hook dependencies and state patterns, and added JSX-aware unused-variable checking. `npm run lint` exits with zero warnings and zero errors; the production build passes. A small number of effect-rule exceptions remain narrowly scoped and explained.

### Progress: P0 runtime and dependency alignment

**Complete.** Python 3.12.x is pinned in `backend/.python-version` and constrained in `backend/pyproject.toml`; Node.js 22.12+ is the documented minimum, with Node 22 used in CI and containers. Backend and production Dockerfiles use Python 3.12 and locked `uv sync`; frontend installs use `npm ci`. CI uses Python 3.12, Node 22, and a pinned uv version. README and platform setup guides now use the same matrix; older setup reports are explicitly marked historical.

Validation completed: `uv lock --check`, locked Python 3.12 dependency sync/import, `npm ci`, `npm run lint`, and `npm run build`. A focused backend test run had 12 workflow-condition failures because the configured test database had no `OrgHR` role; the other selected tests completed. Existing backend `flake8` and `black --check` violations also remain; resolve those alongside database setup/seeding in the next CI-validation P0.

**Next P0:** Make CI validate the delivered application (frontend build, migrations, and integration tests against the required services).
