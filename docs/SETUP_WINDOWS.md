# VisionCore 2.0 — Windows Setup Guide (Native Development)

This guide documents the verified setup for developing VisionCore 2.0 natively on Windows 10/11.

---

## 1. Prerequisites

- **Python**: Python 3.12.x, managed through `uv`.
- **Node.js**: Node.js 22.12 or later in the 22.x LTS line.
- **uv**: Python package and environment manager.
- **Git**: Git for Windows with standard command-line tools.
- **Database Services**:
  - Option A (Recommended): Docker Desktop (with WSL2 backend enabled in BIOS).
  - Option B: Native Windows PostgreSQL 15/16 with `pgvector` extension and Redis for Windows.
  - Option C: Cloud PostgreSQL with pgvector (e.g., Supabase, Neon, AWS RDS) + Redis Cloud.

---

## 2. Clone & Environment Configuration

### Step 2.1: Clone Repository
```powershell
git clone <repo-url> VisionCore2.0
cd VisionCore2.0
```

### Step 2.2: Ensure Correct Line Endings
Repository includes `.gitattributes` to enforce LF line endings on shell scripts and Dockerfiles.
```powershell
git checkout-index --force --all
```

### Step 2.3: Configure Backend Environment
Copy the example environment template:
```powershell
cd backend
Copy-Item .env.example .env
```
Key configuration settings in `backend/.env`:
```ini
ENVIRONMENT=development
DEBUG=True
API_V1_STR=/api/v1
SECRET_KEY=lSybLY2ZIQTa4NZ26tQVo00SfYJputFLm4MusMLobHg

# Database (Local Docker or Native PostgreSQL)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=attendance_db

# Cache & Rate Limiting
CACHE_DIR=./.cache
REDIS_URL=redis://localhost:6379/0

# Biometrics
FACE_MODEL_NAME=Facenet
LIVENESS_CHECK_ENABLED=True
```

### Step 2.4: Configure Frontend Environment
```powershell
cd ..\frontend
Copy-Item .env.example .env
```
Default content in `frontend/.env`:
```ini
VITE_API_URL=http://localhost:8000/api/v1
VITE_ENVIRONMENT=development
```

---

## 3. Backend Setup

### Step 3.1: Install the Locked Python Environment
```powershell
cd ..\backend
irm https://astral.sh/uv/install.ps1 | iex
uv sync --locked --group dev
```

> **Note on Biometrics:** If `face_recognition` / `dlib` is not installed natively, `backend/app/services/face_engine.py` operates in safe fallback mode. Full facial recognition can be run in the Docker container (`ai-service`) or in WSL2.

---

## 4. Frontend Setup

### Step 4.1: Install Dependencies
```powershell
cd ..\frontend
npm ci
```

### Step 4.2: Verify Production Build
```powershell
npm run build
```
Production assets are generated in `frontend/dist/`.

---

## 5. Starting the Infrastructure (PostgreSQL & Redis)

### Option A: Via Docker (Preferred when virtualization is enabled)
From the repository root:
```powershell
docker compose -f deploy/docker-compose.yml up -d postgres redis
```
This automatically provisions `pgvector/pgvector:pg15` and `redis:7-alpine`.

### Option B: Pre-configured Remote / Local Services
Update `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_PASSWORD`, and `REDIS_URL` in `backend/.env`.

---

## 6. Running Migrations & Seeding

Ensure your database is running and reachable, then run Alembic migrations:
```powershell
cd ..\backend
uv run --locked alembic upgrade head
```

Optionally seed initial test users and credentials:
```powershell
python scripts/seed_test_users.py
```

---

## 7. Starting the Applications

### Start Backend API Server
```powershell
cd backend
uv run --locked python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
- API Docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

*(Note: If port 8000 is occupied by another local service, change `--port 8001` and update `VITE_API_URL=http://localhost:8001/api/v1` in `frontend/.env`)*.

### Start Frontend Dev Server
In a separate terminal:
```powershell
cd frontend
npm run dev
```
Open `http://localhost:5173` or `http://localhost:3000` in your browser.

---

## 8. Running Tests

Run backend unit tests:
```powershell
cd backend
uv run --locked python -m pytest app/tests/test_statutory_engine.py app/tests/test_health_sprint9.py -v
```
Run frontend linting:
```powershell
cd frontend
npm run lint
```
