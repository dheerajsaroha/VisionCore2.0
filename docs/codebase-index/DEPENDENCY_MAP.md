# Internal & External Dependency Map

> **Phase 7 — Dependency Mapping & Coupling Analysis**  
> **Extraction Source:** AST import tree graph traversal across all internal packages and manifest manifests.

---

## 1. Internal Package Coupling Matrix

The internal package architecture of `backend/app` reveals clear layering, with distinct fan-in and fan-out characteristics:

| Package | Inbound Dependencies (Fan-In) | Outbound Dependencies (Fan-Out) | Coupling Category |
|---|---|---|---|
| `app.db` | **343** | 10 | Foundational Persistence Layer (High Fan-In) |
| `app.services` | **238** | **173** | Core Domain Engine (High Centrality) |
| `app.api` (`deps.py`) | **109** | 25 | Dependency Injection & Security Gate |
| `app.core` | **103** | 0 | Fundamental Configuration & Utilities |
| `app.schema` | **77** | 0 | Pure Contracts & Validation DTOs |
| `app.crud` | **56** | 38 | Query Execution Abstraction |
| `app.events` | **17** | 0 | Event Bus & Messaging Hooks |
| `app.repositories` | **13** | 5 | Data Access Layer Abstractions |
| `app.routers` | 8 | **363** | HTTP Request Ingress & Dispatch (High Fan-Out) |
| `app.middleware` | 0 | 8 | Request Pre/Post Processing Filters |
| `app.tests` | 0 | **327** | Automated Test Verification Suite |

---

## 2. Package Dependency Flow Diagram

```
                 [ HTTP Requests ]
                         │
                         ▼
             ┌───────────────────────┐
             │     app.middleware    │
             └───────────┬───────────┘
                         │
                         ▼
             ┌───────────────────────┐
             │      app.routers      │ (Fan-Out: 363)
             └─────┬───────────┬─────┘
                   │           │
         ┌─────────▼──┐     ┌──▼──────────┐
         │  app.api   │     │ app.schema  │
         │  (deps.py) │     │   (DTOs)    │
         └─────┬──────┘     └─────────────┘
               │
               ▼
  ┌─────────────────────────┐
  │      app.services       │ (Fan-In: 238, Fan-Out: 173)
  └─────┬──────────────┬────┘
        │              │
        ▼              ▼
┌──────────────┐ ┌──────────────┐
│   app.crud   │ │  app.repos   │
└───────┬──────┘ └──────┬───────┘
        │               │
        └───────┬───────┘
                │
                ▼
        ┌──────────────┐
        │    app.db    │ (Fan-In: 343 - all_models.py)
        └───────┬──────┘
                │
                ▼
        ┌──────────────┐
        │   app.core   │ (Fan-In: 103 - config/security)
        └──────────────┘
```

---

## 3. External Dependency Mapping

### 3.1 Backend External Packages (from `pyproject.toml`)

| External Package | Version Constraint | Criticality | Architectural Role |
|---|---|---|---|
| `fastapi` | `>=0.115.0` | **Critical** | Core ASGI framework powering all 818 endpoints |
| `sqlalchemy` | `>=2.0.30` | **Critical** | Database ORM, connection pool, and query engine |
| `pgvector` | `>=0.3.0` | **Critical** | Biometric vector cosine similarity indexing |
| `alembic` | `>=1.18.0` | **High** | Schema evolution and database versioning |
| `psycopg2-binary` | `>=2.9.9` | **High** | PostgreSQL synchronous relational database adapter |
| `asyncpg` | `>=0.29.0` | **High** | Asynchronous PostgreSQL driver for high-throughput I/O |
| `python-jose` | `>=3.3.0` | **Critical** | JWT token generation and cryptographic signing |
| `passlib` / `bcrypt` | `>=1.7.4` / `<4.0.0` | **Critical** | Password salting and hash verification |
| `redis` | `>=5.0.0` | **Medium** | Distributed rate limiting and session blacklist |
| `deepface` | `>=0.0.99` | **High** | Facial representation and biometric recognition |
| `face-recognition` | `>=1.3.0` | **High** | dlib face landmark and vector encoding |
| `torch` / `torchvision` | `>=2.10.0` | **High** | Neural network tensor runtime for biometrics |
| `reportlab` | `>=4.0.0` | **Medium** | Programmatic PDF payslip and offer letter generation |
| `web3` | `>=6.0.0` | **Low** | Ethereum smart contract audit log anchoring |
| `polars` | `>=0.20.0` | **Medium** | Fast columnar analytics and attendance metrics |
| `diskcache` | `>=5.6.0` | **Medium** | Local in-process caching fallback |

### 3.2 Frontend External Packages (from `package.json`)

| External Package | Version | Criticality | Architectural Role |
|---|---|---|---|
| `react` / `react-dom` | `^19.2.4` | **Critical** | Core reactive user interface library |
| `vite` | `^8.0.1` | **Critical** | Build tooling, bundling, and hot module reloading |
| `tailwindcss` | `^4.2.2` | **High** | Utility styling and responsive theme engine |
| `react-router-dom` | `^7.14.1` | **Critical** | SPA client-side routing and protected navigators |
| `zustand` | `^5.0.12` | **Critical** | Global state stores (Auth, Permissions, Subscriptions) |
| `axios` | `^1.15.0` | **Critical** | HTTP client communicating with FastAPI endpoints |
| `@mediapipe/tasks-vision`| `^1.2.2` | **High** | Client-side facial detection and landmark validation |
| `react-webcam` | `^7.2.0` | **High** | Browser camera hardware stream capture |
| `recharts` | `^3.8.1` | **Medium** | SVG chart visualizations for dashboard reporting |
| `three` / `@react-three/fiber` | `^0.183.2` / `^9.6.0` | **Low** | 3D rendering for biometric depth visualization |

---

## 4. Coupling Hotspots & Architectural Risks

### 4.1 Monolithic Model Aggregation (`all_models.py`)
- **Observation:** `backend/app/db/models/all_models.py` contains 6,588 lines declaring all 224 SQLAlchemy models in a single file.
- **Architectural Intent:** Explicitly documented in file headers: *"All SQLAlchemy models in one file — zero circular import risk."*
- **Assessment:** While completely eliminating circular imports between relational models with mutual foreign keys, it creates an extreme blast radius. Any model change touches this single file, increasing git merge collision likelihood and IDE indexing overhead.

### 4.2 Inverted Layer Import (Services → Routers)
- **Observation:** In `backend/app/services/password_reset_service.py:294`, a lazy import is executed inside a function:
  ```python
  # Line 290: Imported lazily because the notifications router imports the app,
  # and a module-level import here forms a circular dependency.
  from app.routers.notifications import _push_notification
  ```
- **Architectural Violation:** Layering rules require that Routers import Services, never the reverse. The notification dispatching logic was authored inside `app/routers/notifications.py` rather than in `app/services/notification_service.py`.
- **Remediation:** Extract `_push_notification` into `app/services/notification_service.py` to restore clean unidirectional layering (Routers → Services).

### 4.3 High Fan-Out Routers Layer
- **Observation:** `app.routers` has 363 outbound dependencies directly importing from `services`, `crud`, `db`, `schema`, `core`, and `tasks`.
- **Assessment:** Several router modules contain direct business and database logic rather than delegating purely to the service layer.
- **Recommendation:** Enforce a strict controller pattern where routers solely parse parameters, validate DTOs, invoke a service method, and return serialized responses.
