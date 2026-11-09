# VisionCore 2.0 — Setup & Cross-Platform Compatibility Report

## 1. Overview
This report summarizes the modifications, verifications, and cross-platform enhancements performed to ensure reliable development of VisionCore 2.0 on Windows 10/11 while preserving complete compatibility with Ubuntu/Linux environments.

> **Runtime note:** This report records an earlier setup run. Its Python 3.15 test results and installation commands are historical, not the current support matrix. Use the current platform guides; supported versions are Python 3.12.x and Node.js 22.12 or later in the 22.x LTS line.

---

## 2. Changes Made

### Configuration & Path Portability
- **`backend/app/core/config.py`**:
  - Replaced hardcoded `/tmp` fallback with `tempfile.gettempdir()` for `CACHE_DIR`.
  - Added support for `DATABASE_URL` environment override (`DATABASE_URL_OVERRIDE` with alias `DATABASE_URL`), providing automatic dialect normalization between `postgresql+psycopg2` (synchronous) and `postgresql+asyncpg` (asynchronous) while preserving discrete `POSTGRES_*` defaults.
- **`backend/app/services/cache.py`**:
  - Added safe directory creation `os.makedirs(cache_dir, exist_ok=True)` with exception handling and `tempfile.gettempdir()` fallback.
- **`backend/.env.example`**:
  - Updated cache path documentation to portable relative path `./.cache`.
- **`backend/.env`**:
  - Generated development `.env` configuration with secure default secret key and sensible defaults.
- **`frontend/.env.example`**:
  - Created frontend template with `VITE_API_URL=http://localhost:8000/api/v1` and `VITE_ENVIRONMENT=development`.

### Container & Infrastructure Alignments
- **`backend/Dockerfile`**:
  - Created a streamlined Python 3.11 Debian-based Dockerfile with `build-essential`, `libpq-dev`, and `curl` for containerized backend execution.
- **`deploy/docker-compose.yml`**:
  - Upgraded PostgreSQL image from `postgres:15-alpine` to `pgvector/pgvector:pg15` to ensure native support for `init-db.sql` vector extensions.
  - Aligned backend build context and Dockerfile reference (`../backend` + `Dockerfile`).
  - Added fallback defaults for `SECRET_KEY`.
  - Aligned frontend container port mapping to `3000:3000`.

### Line Endings & Git Configuration
- **`.gitattributes`**:
  - Added repository-wide `.gitattributes` enforcing LF (`eol=lf`) on shell scripts, SQL initialization scripts, and Dockerfiles to prevent `\r: command not found` errors inside Linux containers.
- **`scripts/deploy.sh`**:
  - Normalized line endings from CRLF to LF.

### Documentation Created
- `docs/SETUP_AUDIT.md`: Phase 1 findings and minimal fix strategy.
- `docs/SETUP_WINDOWS.md`: Native Windows setup, dependencies, and configuration.
- `docs/SETUP_WSL2.md`: WSL2 setup, Linux compilation of biometric dependencies, and Docker integration.
- `docs/SETUP_LINUX.md`: Native Ubuntu/Linux instructions.
- `docs/TROUBLESHOOTING.md`: Common issues, port conflicts, BIOS virtualization fixes, and workarounds.

---

## 3. Exact Setup Commands

### A. Windows Native (PowerShell)
```powershell
# 1. Clone & Line Endings
git clone <repo-url> VisionCore2.0
cd VisionCore2.0

# 2. Configure Environment
cd backend
Copy-Item .env.example .env
cd ..\frontend
Copy-Item .env.example .env

# 3. Setup Python Backend Environment
cd ..\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 4. Setup Frontend
cd ..\frontend
npm install
npm run build

# 5. Run Backend Server (Port 8000 or 8001)
cd ..\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 6. Run Frontend Dev Server
cd ..\frontend
npm run dev
```

### B. WSL2 (Ubuntu on Windows)
```bash
# 1. Clone into Linux filesystem
git clone <repo-url> ~/VisionCore2.0
cd ~/VisionCore2.0

# 2. Environments
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# 3. Start Database & Cache
docker compose -f deploy/docker-compose.yml up -d postgres redis

# 4. Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements_face_local.txt
alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 5. Frontend
cd ../frontend
npm install
npm run dev
```

### C. Native Ubuntu / Linux
```bash
# 1. Dependencies & Clone
sudo apt-get update && sudo apt-get install -y build-essential cmake libpq-dev libgl1-mesa-glx python3-venv
git clone <repo-url> VisionCore2.0
cd VisionCore2.0

# 2. Start Services via Docker Compose
docker compose -f deploy/docker-compose.yml up -d postgres redis

# 3. Backend & Migrations
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 4. Frontend
cd ../frontend
npm install && npm run build
npm run dev
```

---

## 4. Tests Executed & Actual Results

| Test / Verification Check | Result | Details |
| :--- | :---: | :--- |
| **Frontend Dependency Install (`npm install`)** | **PASS** | 293 packages installed cleanly |
| **Frontend Production Build (`npm run build`)** | **PASS** | Vite built client dist in 2.31s with zero errors |
| **Backend Virtualenv Creation (`venv`)** | **PASS** | Isolated `.venv` created with Python 3.15.2 |
| **Backend Core Requirements Install** | **PASS** | All dependencies from `requirements.txt` installed |
| **Backend Syntax Compilation (`py_compile`)** | **PASS** | Verified clean compilation on `config.py` & `cache.py` |
| **Backend Application & Route Import** | **PASS** | `Face Recognition Based Attendance System v1.0.0` loaded |
| **Backend Health Endpoint (`GET /health`)** | **PASS** | Returned HTTP 200: `{"status":"healthy","version":"1.0.0","environment":"development"}` |
| **Backend Root Endpoint (`GET /`)** | **PASS** | Returned HTTP 200: `{"message":"Welcome to Face Recognition Based Attendance System v1.0.0"}` |
| **Backend Statutory Engine & Unit Tests** | **PASS** | 55 unit tests passed in `test_statutory_engine.py`, `test_workflow_conditions.py`, and `test_health_sprint9.py` |
| **Alembic Migration Graph Validation** | **PASS** | 42 migration files validated, unified at single head `a1c4e7b93d15` |
| **Database Integration Tests (`test_mounted_routers.py`)** | **BLOCKED** | Requires active PostgreSQL database instance |
| **Docker Engine & Daemon Connectivity** | **BLOCKED** | Hardware virtualization disabled in host machine BIOS/firmware |
| **Full Stack Docker Compose (`up -d`)** | **NOT RUN** | Blocked by host virtualization/Docker daemon availability |

---

## 5. Remaining Blockers & Unverified Items

1. **Host Virtualization Disabled in BIOS**:
   - `wsl --status` reports virtualization is not enabled on this machine. Docker Desktop cannot start the Linux engine daemon without VT-x/AMD-V enabled in BIOS.
   - *Action required:* Enable virtualization in BIOS to run Docker containers locally on Windows.
2. **Database Integration Suite Execution**:
   - The full database test suite requires a running PostgreSQL instance with the `vector` extension. Once PostgreSQL is available (via Docker or native service), running `alembic upgrade head` and `pytest app/tests/` will execute the remaining integration tests.
3. **Local Port 8000 Collision**:
   - Host PID 6128 currently listens on port 8000. Running VisionCore requires terminating that process or starting Uvicorn on an alternate port (e.g. `--port 8001`) with matching `VITE_API_URL` configuration.
