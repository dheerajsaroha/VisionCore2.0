# VisionCore 2.0 — Setup & Cross-Platform Compatibility Audit

## 1. Executive Summary
This audit inspects the VisionCore 2.0 repository to identify cross-platform (Windows 10/11 and Linux/Ubuntu) compatibility bottlenecks, dependency constraints, container orchestration discrepancies, and migration integrity.

> **Runtime note:** This is a historical audit. The supported runtime is now Python 3.12.x and Node.js 22.12 or later in the 22.x LTS line; references below to Python 3.15 describe the machine used for the original diagnosis, not a supported project runtime.

---

## 2. Confirmed Issues & Minimal Fixes Required

### Issue 1: Missing `.gitattributes` and CRLF Line Endings
- **Finding:** Git checkout on Windows converts shell scripts (`scripts/deploy.sh`), Dockerfiles, and SQL init scripts to CRLF (`\r\n`). In Linux containers or bash, `\r` causes syntax and interpreter errors (`\r: command not found`).
- **Severity:** High
- **Minimal Fix:**
  - Create a root `.gitattributes` file enforcing `* text=auto`, `*.sh text eol=lf`, `Dockerfile* text eol=lf`, `*.sql text eol=lf`, and `*.py text eol=lf`.
  - Normalize line endings of `scripts/deploy.sh` to LF.

### Issue 2: Hardcoded Unix Temp Paths in Cache & Configuration
- **Finding:** Default cache path previously defaulted to `/tmp/visioncore_cache` which does not exist on native Windows. Uncommitted working changes introduce `tempfile.gettempdir()`, but path handling requires verified portability without breaking Linux `/tmp`.
- **Severity:** Medium
- **Minimal Fix:**
  - Standardize `backend/app/core/config.py` and `backend/app/services/cache.py` to use `tempfile.gettempdir()` fallback and `os.makedirs(cache_dir, exist_ok=True)`.
  - Maintain relative `.cache` default in `backend/.env.example`.

### Issue 3: Incompatible PostgreSQL Image in `deploy/docker-compose.yml`
- **Finding:** `deploy/docker-compose.yml` uses image `postgres:15-alpine`. However, `deploy/init-db.sql` executes `CREATE EXTENSION IF NOT EXISTS vector;`. Standard PostgreSQL Alpine does not include the `pgvector` extension, causing database initialization to fail.
- **Severity:** Critical (for Docker-based deployment)
- **Minimal Fix:**
  - Change PostgreSQL image in `deploy/docker-compose.yml` to a verified pgvector image (e.g. `pgvector/pgvector:pg15` or `ankane/pgvector:v0.5.1`).

### Issue 4: Dockerfile and Context Mismatch in Compose Files
- **Finding:**
  - `deploy/docker-compose.yml` configures `backend` with context `../backend` and dockerfile `../Dockerfile.prod`. However, `Dockerfile.prod` executes `COPY backend/pyproject.toml .` and defines a final multi-stage `nginx:alpine` image unless targeted.
  - Root `docker-compose.prod.yml` specifies `dockerfile: Dockerfile` inside `./backend`, but `./backend/Dockerfile` does not exist.
  - `infrastructure/docker-compose.yml` references non-existent top-level sibling directories (`../gateway`, `../auth-service`, `../attendance-service`, `../blockchain-service`, `../analytics-service`).
- **Severity:** High
- **Minimal Fix:**
  - Provide a standardized, clean `backend/Dockerfile` for local/containerized backend execution.
  - Fix build context and target in `deploy/docker-compose.yml`.

### Issue 5: C-Extension Biometric Dependencies on Windows (`dlib`, `face_recognition`)
- **Finding:**
  - `face-recognition` requires `dlib` which requires CMake, C++ compiler (MSVC), and precompiled binary wheels. On Windows with Python 3.15, compiling `dlib` from source fails without dedicated build tools.
  - Biometric processing is already designed as an isolated microservice in `ai-service` (with dedicated Dockerfile) and `backend/app/services/face_engine.py` provides graceful fallback when `face_recognition` is not present (`FACE_RECOGNITION_AVAILABLE = False`).
- **Severity:** Medium
- **Minimal Fix:**
  - Keep `backend/requirements.txt` decoupled from `face-recognition` and `dlib` for lightweight, reliable native Windows/Linux backend development.
  - Document that full biometric feature extraction runs either via WSL2/Docker container (`ai-service`) or with precompiled wheels when available.

### Issue 6: Missing Environment Templates & Local Configuration
- **Finding:**
  - `backend/.env` is absent; only `.env.example` exists.
  - `frontend/.env.example` is missing.
- **Severity:** Low
- **Minimal Fix:**
  - Create `frontend/.env.example` documenting `VITE_API_URL` and `VITE_ENVIRONMENT`.
  - Provide safe, clear instructions for creating `backend/.env` from `backend/.env.example`.

### Issue 7: Host Virtualization / Docker Desktop State
- **Finding:**
  - Windows hardware virtualization is disabled in machine firmware / BIOS (`WSL2 is unable to start since virtualization is not enabled on this machine`).
  - Docker Desktop daemon is not responding because its WSL2/Hyper-V Linux engine cannot start.
- **Severity:** High (Environment constraint)
- **Minimal Fix:**
  - Provide explicit instructions for enabling Virtual Machine Platform / BIOS virtualization in `docs/TROUBLESHOOTING.md`.
  - Provide a dual-path development workflow: Native Windows local development (with standalone or cloud PostgreSQL/pgvector and Redis) and WSL2/Docker containerized workflow.

### Issue 8: Port 8000 Conflict
- **Finding:**
  - Port 8000 is currently bound by an active background process (`PID 6128`, running Django `runserver`).
- **Severity:** Medium (Operational conflict)
- **Minimal Fix:**
  - Document port conflict resolution (stopping conflicting process or running backend on alternative port `8001` with matching `VITE_API_URL`).

---

## 3. Verified Repository Health

- **Git Branch:** `main` (synced with `origin/main`).
- **Database Migrations:** Alembic migration graph has 42 versions culminating in a single clean head (`a1c4e7b93d15`).
- **Application Startup Logic:** `backend/app/util/init.py` cleanly handles extension checks (`uuid-ossp`, `pgcrypto`, `vector`) and HNSW index creation with exception guards.
- **Frontend Build Configuration:** `frontend/package.json` and `frontend/vite.config.js` are properly configured with Vite, React 19, and Tailwind CSS.
