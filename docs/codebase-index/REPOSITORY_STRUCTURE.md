# Repository Structure & Directory Hierarchy

> **Phase 1 — Repository Discovery**  
> **Scope:** Full recursive discovery and classification across all directories and file types.

---

## 1. Directory Tree Hierarchy

```
VisionCore2.0/
├── .github/                               # CI/CD automation workflows
│   └── workflows/
│       ├── ci.yml                         # Lint, test, validate, and build pipeline
│       └── deploy.yml                     # AWS ECR build & EC2 SSH deployment pipeline
├── ai-service/                            # Dedicated Biometrics & AI Engine microservice
│   ├── app/
│   │   ├── core/                          # AI service configuration and security settings
│   │   ├── db/                            # Database connection for embedding sync
│   │   ├── models/                        # SQLAlchemy FaceEmbedding model
│   │   ├── routers/                       # FastAPI router: biometrics.py (6 endpoints)
│   │   ├── services/                      # face_engine.py, liveness.py, emotion.py
│   │   └── main.py                        # FastAPI application entry point (port 8002)
│   ├── tests/                             # Unit & integration tests for AI pipelines
│   ├── Dockerfile                         # AI microservice container definition
│   └── requirements.txt                   # DeepFace, PyTorch, MediaPipe, InsightFace
├── backend/                               # Core Application Backend (Modular Monolith)
│   ├── alembic/                           # Database migration management
│   │   ├── versions/                      # 44 Alembic migration scripts
│   │   ├── env.py                         # Migration runtime environment
│   │   └── script.py.mako                 # Migration revision template
│   ├── app/                               # Core backend application package
│   │   ├── adapters/                      # External service adapters (blockchain, storage)
│   │   ├── api/                           # Dependency injection (deps.py, security, scopes)
│   │   ├── contracts/                     # Domain interface contracts & abstractions
│   │   ├── core/                          # Config, security, rate limit, observability
│   │   ├── crud/                          # 22 Database CRUD helper modules
│   │   ├── db/                            # Database session, base model, seeds, and all_models.py
│   │   │   ├── models/                    # all_models.py (224 SQLAlchemy models)
│   │   │   └── seed_*.py                  # Specialized seed data modules
│   │   ├── events/                        # Event publisher & in-memory listeners
│   │   ├── middleware/                    # Tenant context, correlation ID, metrics, security
│   │   ├── repositories/                  # Dedicated repository pattern abstractions
│   │   ├── routers/                       # 53 Router files (48 mounted, 5 unmounted)
│   │   ├── schema/                        # 30 Pydantic V2 request/response schemas
│   │   ├── schemas/                       # Legacy/specialized schema models
│   │   ├── seeder/                        # Production and QA database seeders
│   │   ├── services/                      # 128 Domain services (attendance, payroll, AI)
│   │   │   ├── ai/                        # AI governance & cost tracker
│   │   │   ├── ai_providers/              # Multi-model LLM integrations
│   │   │   ├── attendance_pipeline/       # Verification and clock-in execution
│   │   │   └── copilots/                  # Domain-specific AI assistants (HR, Tech)
│   │   ├── tasks.py                       # Background task definitions
│   │   ├── tests/                         # 72 Test suite files (847 automated test cases)
│   │   └── util/                          # Table creation and calendar loader (init.py)
│   ├── app_data/                          # Local file storage (uploads)
│   │   └── uploads/                       # 516 test-generated PDF artifacts (Offer letters & payslips)
│   ├── domain/                            # Standalone domain logic & decision models
│   ├── gateway/                           # Reverse proxy API Gateway prototype (main.py)
│   ├── scripts/                           # Database maintenance and repro scripts
│   ├── services/                          # Microservice extraction stubs (biometrics, blockchain)
│   ├── Dockerfile                         # Production backend container build
│   ├── main.py                            # Primary backend entry point (FastAPI app on port 8000)
│   ├── pyproject.toml                     # Python dependencies & uv package manager config
│   ├── pytest.ini                         # Pytest test execution configuration
│   ├── requirements.txt                   # Locked production dependencies
│   ├── runtime_validation_*.py            # 19 live integration validation test suites
│   └── uv.lock                            # Deterministic uv dependency lockfile
├── deploy/                                # Production deployment orchestration
│   ├── docker-compose.yml                 # Production compose (postgres, redis, backend, frontend, nginx)
│   ├── init-db.sql                        # PostgreSQL extension enablement script
│   └── nginx.conf                         # Reverse proxy SSL/TLS & rate limiting configuration
├── docs/                                  # Repository documentation
│   ├── codebase-index/                    # Comprehensive 16-part Architectural Index & Diagrams
│   ├── Face_Recognition_...docx           # Original system blueprint specification
│   ├── LOCAL_IMPROVEMENTS_ROADMAP.md      # Engineering backlog and technical debt roadmap
│   ├── SETUP_AUDIT.md                     # Development environment audit report
│   ├── SETUP_LINUX.md                     # Linux developer onboarding guide
│   ├── SETUP_REPORT.md                    # Verification status report
│   ├── SETUP_WINDOWS.md                   # Windows developer setup guide
│   ├── SETUP_WSL2.md                      # WSL2 development instructions
│   └── TROUBLESHOOTING.md                 # Common errors and recovery steps
├── frontend/                              # Client Application Tier (React 19 SPA)
│   ├── public/                            # Static public web assets (favicon, SVG icons)
│   ├── src/
│   │   ├── assets/                        # Images, fonts, and graphics
│   │   ├── components/                    # 70 Reusable React UI components & dialogs
│   │   ├── hooks/                         # Custom React hooks (useApi, usePermission, useSubscription)
│   │   ├── layouts/                       # DashboardLayout with sidebar & notifications
│   │   ├── lib/                           # Utility libraries & route authorization checks
│   │   ├── pages/                         # 60 Page route components (Attendance, HR, AI, Payroll)
│   │   ├── services/                      # 34 Axios HTTP API service wrappers
│   │   ├── store/                         # 3 Zustand stores (authStore, permissionStore, subscriptionStore)
│   │   ├── utils/                         # Frontend helper formatting utilities
│   │   ├── App.jsx                        # Route table and lazy loading definitions
│   │   ├── index.css                      # Tailwind CSS v4 root stylesheet
│   │   └── main.jsx                       # React DOM root render entry point
│   ├── Dockerfile                         # Production frontend container build (Nginx-hosted)
│   ├── eslint.config.js                   # ESLint flat configuration
│   ├── index.html                         # SPA entry HTML page
│   ├── package.json                       # Node dependencies & npm scripts
│   ├── package-lock.json                  # Deterministic Node dependency lockfile
│   ├── tsconfig.json                      # TypeScript configuration (for TS/JSX typing)
│   └── vite.config.js                     # Vite 8 bundling & dev server configuration
├── infrastructure/                        # Local & Cloud Infrastructure
│   ├── database/                          # PostgreSQL init SQL scripts
│   ├── k8s/                               # Kubernetes manifests (ingress, secrets, configmaps)
│   └── docker-compose.yml                 # Full microservices compose stack (gateway, rabbitmq, redis)
├── scripts/                               # Root administrative and deployment automation
│   ├── deploy.sh                          # EC2 production deployment script
│   ├── generate_doc.py                    # Blueprint word document generation script
│   ├── list_users.py                      # Database user inspection script
│   ├── print_test_credentials.py          # Development test user credential utility
│   ├── reset_qa_passwords.py              # QA environment password reset tool
│   └── seed_test_users.py                 # Multi-role test user provisioning
├── Dockerfile.prod                        # Root production Dockerfile
├── docker-compose.prod.yml                # Root production docker compose
├── dev_setup.ps1                          # Windows/PowerShell local setup script
├── start_backend.ps1                      # Windows backend launcher script
├── start_dev.ps1                          # Windows full-stack launcher script
├── start_frontend.ps1                     # Windows frontend launcher script
├── MODULE_ROLE_MATRIX.md                  # Matrix of 21 business modules vs 6 baseline roles
├── RBAC_ROLE_MAPPING.md                   # Mapping of 26 legacy backend roles to 6 baseline roles
├── README.md                              # Main repository introduction and quick-start
└── requirements.txt                       # Global requirements manifest
```

---

## 2. Directory Breakdown & File Metrics

| Directory Path | Total Files | Dominant Types | Primary Role & Responsibility |
|---|---|---|---|
| `backend/app/services` | 128 | `.py` | Core domain business logic, statutory engines, biometric pipeline, AI copilots |
| `backend/app/routers` | 53 | `.py` | FastAPI route controllers, HTTP parameter parsing, gate dependencies |
| `backend/app/tests` | 72 | `.py` | Comprehensive test suite (unit, integration, regression, security) |
| `backend/app/crud` | 22 | `.py` | Database CRUD abstractions and query composition |
| `backend/app/schema` | 32 | `.py` | Pydantic V2 input validation and response serialization schemas |
| `backend/app/db` | 24 | `.py` | Database engine, session, seeder scripts, and `all_models.py` |
| `backend/app/core` | 10 | `.py` | Configuration, security crypto, rate limiters, Prometheus observability |
| `backend/alembic` | 47 | `.py`, `.mako` | 44 Schema migration revisions and Alembic configuration |
| `backend/app_data/uploads` | 516 | `.pdf` | Test-generated offer letters and payslip documents |
| `backend/` (root) | 59 | `.py`, `.json` | Validation suites, reports, root main entry point, lockfiles |
| `frontend/src/components` | 70 | `.jsx` | Reusable UI components, tables, modals, cards, charts |
| `frontend/src/pages` | 60 | `.jsx` | Application page views (Attendance, HR, Payroll, Settings, AI) |
| `frontend/src/services` | 34 | `.js`, `.ts` | Axios client services connecting UI pages to backend endpoints |
| `frontend/src/store` | 3 | `.js` | Zustand reactive state management (auth, permissions, subscriptions) |
| `ai-service/app` | 14 | `.py` | Biometrics microservice: FaceEngine, LivenessEngine, EmotionEngine |
| `infrastructure/` | 6 | `.yaml`, `.sql` | Kubernetes manifests, Docker compose dev setup, init scripts |
| `deploy/` | 3 | `.yml`, `.conf`, `.sql` | Production deployment compose, Nginx reverse proxy, database init |
| `scripts/` | 7 | `.py`, `.sh` | Database seeding, credential printing, deployment scripts |
| `docs/` | 8 | `.md`, `.docx` | Developer onboarding guides, platform roadmap, blueprint |
| `docs/codebase-index` | 21 | `.md`, `.mmd` | This architectural index, guides, and Mermaid diagrams |

---

## 3. Classification of Repository Components

### 3.1 Backend Applications
- **FastAPI Modular Monolith (`backend/main.py`):** The primary monolithic application serving `/api/v1` routes on port `8000`. Houses all identity, attendance, leave, payroll, HCM, asset, and workflow logic.
- **Biometrics Microservice (`ai-service/app/main.py`):** A lightweight FastAPI service on port `8002` dedicated to face detection, 128-dimensional embedding generation, emotion scoring, and liveness verification.
- **API Gateway Prototype (`backend/gateway/main.py`):** An asynchronous HTTP reverse proxy built with Starlette/HTTPX to route traffic between decoupled microservices.

### 3.2 Frontend Applications
- **React 19 Single Page Application (`frontend/`):** Built with React 19.2.4, Vite 8.0.1, and Tailwind CSS v4. Features client-side face detection via `@mediapipe/tasks-vision`, webcam streaming via `react-webcam`, and state management via Zustand.

### 3.3 Database & Migrations
- **Schema & Models (`backend/app/db/models/all_models.py`):** A consolidated 6,588-line file containing all 224 SQLAlchemy ORM models, avoiding circular import risks across models.
- **Alembic Versions (`backend/alembic/versions/`):** 44 versioned migration scripts tracking the schema from initial setup to enterprise EAAC, hiring loops, and payroll enhancements.

### 3.4 Infrastructure & Deployment
- **Docker Compose Production (`deploy/docker-compose.yml`):** Multi-container production stack including Nginx, PostgreSQL (pgvector), Redis, Backend, and Frontend.
- **Kubernetes Manifests (`infrastructure/k8s/`):** Production manifests for Ingress, ConfigMaps, and Secrets.
- **CI/CD Automation (`.github/workflows/`):** `ci.yml` performs linting (Flake8, Black, ESLint), pytest runs with PostgreSQL/Redis service containers, and runtime platform validation. `deploy.yml` builds and pushes images to AWS ECR and triggers EC2 updates via SSH.

---

## 4. Generated Artifacts & Indexing Exclusions

The repository contains files that are runtime outputs or test artifacts:
- **`backend/app_data/uploads/` (516 files):** Contains test-generated PDF documents (offer letters and payslips) created during integration test execution.
  - *Exclusion Action:* These files are excluded from code symbol indexing, AST parsing, and dependency mapping, but documented here for repository inventory completeness.
- **Root Artifacts (`repo_filelist.txt`, `Identify`, `VisionCore`):**
  - `Identify` and `VisionCore` are empty (0-byte) files at the repository root.
  - `repo_filelist.txt` is an exported UTF-16 file list artifact from a Windows PowerShell environment.
  - *Recommendation:* Clean up or add to `.gitignore`.
