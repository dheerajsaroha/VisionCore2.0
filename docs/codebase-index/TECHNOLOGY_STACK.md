# Technology Stack Analysis

> **Phase 2 — Technology Stack Analysis**  
> **Extraction Source:** Actual repository manifest files (`backend/pyproject.toml`, `backend/requirements.txt`, `ai-service/requirements.txt`, `frontend/package.json`, `.github/workflows/ci.yml`).

---

## 1. Programming Languages & Runtime Environments

| Language | Runtime Version | Manifest Location | Usage Context |
|---|---|---|---|
| **Python** | `>=3.12, <3.13` (Locked 3.12) | `backend/pyproject.toml` | Backend modular monolith, AI microservice, scripts, tests |
| **JavaScript / TypeScript** | `Node.js >=22.12.0` | `frontend/package.json` | React 19 Frontend application, Vite tooling |
| **SQL** | PostgreSQL 15+ / 16 | `deploy/docker-compose.yml`, `backend/app/db` | Relational schemas, pgvector cosine search, migrations |
| **Shell / Bash** | Bash / POSIX | `scripts/deploy.sh`, CI workflows | Deployment automation and Docker execution |
| **PowerShell** | PS 5.1+ / 7+ | `dev_setup.ps1`, `start_*.ps1` | Local Windows development environment scripts |

---

## 2. Package Managers & Dependency Management

- **Backend Package Manager:** [`uv`](https://docs.astral.sh/uv/) (v0.13.6 in CI). Fast Python package resolver and environment manager.
  - Configuration: `backend/pyproject.toml`
  - Lockfile: `backend/uv.lock`
  - Exported Fallback: `backend/requirements.txt` (902 lines with SHA256 hashes)
- **Frontend Package Manager:** `npm` (Node 22 LTS line).
  - Configuration: `frontend/package.json`
  - Lockfile: `frontend/package-lock.json`
  - Verification: `npm ci` enforced in CI/CD pipeline

---

## 3. Backend Technology Stack

### 3.1 Web & Application Frameworks
- **FastAPI (`>=0.115.0`):** Core ASGI REST framework providing asynchronous request handling, OpenAPI/Swagger specification generation, and dependency injection.
- **Starlette (`>=0.40.0`):** Underlying ASGI toolkit powering middleware, routing, and HTTP exception handling.
- **Uvicorn (`[standard] >=0.30.0`):** High-performance ASGI web server implementing uvloop and httptools.
- **Pydantic V2 (`>=2.8.0`):** Data validation and serialization using Python type annotations.
- **Pydantic-Settings (`>=2.3.0`):** Environment variable loading, `.env` parsing, and configuration validation.

### 3.2 Database & ORM
- **SQLAlchemy (`>=2.0.30`):** Object Relational Mapper configured with SQLAlchemy 2.0 2.0-style `Mapped[T]` and `mapped_column()` annotations across 224 tables.
- **Alembic (`>=1.18.0`):** Schema migration management tool with 44 versioned migration scripts.
- **psycopg2-binary (`>=2.9.9`):** Synchronous PostgreSQL driver used for relational operations.
- **asyncpg (`>=0.29.0`):** High-speed asynchronous PostgreSQL driver.
- **pgvector (`>=0.3.0`):** Vector similarity search extension for PostgreSQL, supporting cosine distance operators (`<->`) over 128-dimensional biometric embeddings.

### 3.3 Security, Cryptography & Authentication
- **python-jose (`[cryptography] >=3.3.0`):** JWT token encoding, decoding, signature verification, and JTI session validation.
- **passlib (`>=1.7.4`) & bcrypt (`<4.0.0`):** Password hashing engine operating with 12 salt rounds (`BCRYPT_ROUNDS=12`).
- **cryptography (`>=41.0.0`):** Symmetric AES encryption for biometric vector security and cryptographic key handling.
- **email-validator (`>=2.1.0`):** RFC-compliant email syntax and domain validation.

### 3.4 Data Processing & Reporting
- **ReportLab (`>=4.0.0`):** Programmatic PDF document generation engine for enterprise payslips and offer letters.
- **Polars (`>=0.20.0`):** Fast DataFrame library for analytical aggregations and attendance metrics.
- **Matplotlib (`>=3.8.0`):** Chart and visualization generation for PDF exports.

### 3.5 Networking & External Integration
- **HTTPX (`>=0.24.1`):** Asynchronous HTTP client used for microservice proxying in the API gateway and webhook delivery.
- **Requests (`>=2.32.0`):** Synchronous HTTP client for third-party integration connectors.
- **Web3.py (`>=6.0.0`):** Ethereum / EVM blockchain RPC client for anchoring cryptographic audit hashes into smart contracts.

---

## 4. AI, Machine Learning & Biometrics Stack

| Library | Version | Role in Architecture |
|---|---|---|
| **DeepFace** | `>=0.0.99` | Facial recognition wrapper supporting Facenet, VGG-Face, and ArcFace models |
| **face-recognition** | `>=1.3.0` | dlib-based facial detection and 128-dimensional embedding extraction |
| **face-recognition-models** | `>=0.3.0` | Pre-trained deep learning weights for shape prediction and face encodings |
| **InsightFace** | `>=0.7.3` | High-accuracy facial analysis and 2D/3D landmark detection (in `ai-service`) |
| **MediaPipe** | `>=0.10.0` | Real-time face mesh, iris tracking, and blink/liveness detection |
| **OpenCV Headless** | `>=4.10.0` | Haar Cascade detection, image color conversions, and frame preprocessing |
| **Pillow (PIL)** | `>=10.3.0` | Image format conversion, resizing, and memory stream buffering |
| **PyTorch (`torch`)** | `>=2.10.0` / `>=2.3.0` | Deep neural network runtime for tensor operations and GPU acceleration |
| **torchvision** | `>=0.25.0` / `>=0.18.0` | Image transformations and vision datasets |
| **tf-keras** | `>=2.21.0` / `>=2.16.0` | Keras compatibility layer for TensorFlow-trained face models |

---

## 5. Frontend Technology Stack

### 5.1 Core Framework & Tooling
- **React (`^19.2.4`) & React DOM (`^19.2.4`):** Latest React release utilizing React Server Components readiness, Suspense boundaries, and lazy page loading.
- **Vite (`^8.0.1`):** High-speed frontend build tool and development server with HMR.
- **React Router DOM (`^7.14.1`):** Client-side SPA routing, dynamic route segments, and protected route wrappers.

### 5.2 Styling & User Interface
- **Tailwind CSS (`^4.2.2`):** Utility-first styling framework integrated via `@tailwindcss/vite` (`^4.2.4`).
- **Lucide React (`^1.11.0`):** Iconography library for UI actions, navigation, and badges.
- **Framer Motion (`^12.38.0`):** Declarative animation library for page transitions, modals, and toasts.
- **Tailwind Merge (`^3.5.0`) & Clsx (`^2.1.1`):** Conditional CSS class name composition.

### 5.3 Biometrics & 3D Visualization
- **`@mediapipe/tasks-vision` (`^1.2.2`):** WebAssembly/WebGL browser-based face landmark detection and client-side anti-spoof checks.
- **React Webcam (`^7.2.0`):** Webcam video stream capture component for live face verification.
- **Three.js (`^0.183.2`), `@react-three/fiber` (`^9.6.0`), `@react-three/drei` (`^10.7.7`):** 3D WebGL rendering pipeline for interactive UI elements and facial depth visualization.

### 5.4 State Management & Networking
- **Zustand (`^5.0.12`):** Lightweight reactive state management powering `authStore`, `permissionStore`, and `subscriptionStore`.
- **Axios (`^1.15.0`):** HTTP client with request/response interceptors for token attachment and 401 refresh handling.
- **Recharts (`^3.8.1`):** Composable SVG charting library for analytics dashboards.

---

## 6. Persistence, Caching & Message Queues

| Component | Technology | Role & Deployment |
|---|---|---|
| **Primary Relational DB** | PostgreSQL 15+ / 16 (Alpine) | Multi-tenant relational storage, foreign keys, ACID transactions |
| **Vector Search Engine** | `pgvector` extension (`v0.3.0+`) | HNSW index on 128-dim vectors using cosine similarity |
| **In-Memory Cache & Limiter** | Redis 7.0+ (Alpine) | Distributed token-bucket rate limiter, token revocation blacklist |
| **Local Cache Fallback** | DiskCache (`>=5.6.0`) | In-process filesystem cache when Redis is unavailable |
| **Message Broker** | RabbitMQ 3.12 (Management Alpine) | Event message queue defined in `infrastructure/docker-compose.yml` |

---

## 7. Infrastructure & Deployment Technologies

- **Containerization:** Docker (Multi-stage builds, Alpine base images, NVIDIA GPU passthrough reservations).
- **Orchestration:**
  - Local / Dev: Docker Compose (`deploy/docker-compose.yml`, `infrastructure/docker-compose.yml`).
  - Cloud / Enterprise: Kubernetes manifests (`infrastructure/k8s/` Ingress, ConfigMaps, Secrets).
- **Web Server & Reverse Proxy:** Nginx (Alpine) handling SSL/TLS termination, HTTP request rate limiting (`zone=login:10m rate=5r/m`), and security headers.
- **Cloud Hosting Target:** AWS EC2 (Ubuntu) with Amazon ECR (Elastic Container Registry) for container image versioning.
- **CI/CD Platform:** GitHub Actions (`.github/workflows/ci.yml`, `.github/workflows/deploy.yml`).

---

## 8. Monitoring & Observability Systems

- **Prometheus Metrics:** Integrated via `app/core/observability.py` and `MetricsMiddleware`, exposing standard metrics at `/metrics`.
- **Structured Logging:** Standard library `logging` configured with request correlation IDs (`X-Request-ID`), process latency (`X-Process-Time-Ms`), and tenant isolation tags.
