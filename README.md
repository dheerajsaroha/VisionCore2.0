# VisionCore 2.0

> **AI-Powered Workforce Attendance & Presence Intelligence Platform**

VisionCore 2.0 is a multi-tenant enterprise attendance platform combining face-recognition biometrics, role-based access control (RBAC), and a comprehensive HR operations layer. It replaces manual check-in systems with a camera-based presence pipeline backed by a structured approval workflow.

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-00a393.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19-61dafb.svg)](https://reactjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791.svg)](https://www.postgresql.org/)

---

## What VisionCore Does

| Capability | Status |
|---|---|
| JWT authentication with HttpOnly refresh cookies | Implemented |
| Multi-tenant organization isolation | Implemented |
| Role-Based Access Control (RBAC) | Implemented |
| Employee directory & user management | Implemented |
| Face-recognition attendance check-in | Implemented |
| Liveness / anti-spoofing detection | Implemented |
| Attendance corrections with manager approval | Implemented |
| Leave management | Implemented |
| Payroll management | Implemented |
| Notifications (in-memory) | Implemented |
| Analytics dashboards | Implemented (frontend) |
| Biometric FAR/FRR validation | **Not Verified** |
| Blockchain audit anchoring | Disabled (config flag off) |
| Production deployment | **Not Verified** |

---

## Architecture Overview

```
Browser (React 19 + Vite)
        ↓  HTTP/JSON  (Axios, in-memory JWT)
FastAPI Backend  (Python 3.12)
        ↓
 ┌──────────────────────────────────┐
 │  Router → Service → Repository  │
 └──────────────────────────────────┘
        ↓                   ↓
  PostgreSQL 15+          Redis
  (SQLAlchemy 2 ORM)   (rate-limiting,
  (pgvector embeddings)  token blacklist)
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design.

---

## Quick Start

### Prerequisites

- Python 3.12.x (managed through [`uv`](https://docs.astral.sh/uv/))
- Node.js 22.12 or later in the 22.x LTS line
- PostgreSQL 15+ with `pgvector` extension
- Redis (optional — falls back to local rate limiting)

### 1. Backend

```bash
cd backend

# Install the locked Python 3.12 environment
uv sync --locked --group dev

# Copy and edit environment variables
cp .env.example .env
# Edit .env: set SECRET_KEY, POSTGRES_PASSWORD, etc.

# Run database migrations
uv run --locked alembic upgrade head

# Seed initial data (creates roles, default org, admin user)
uv run --locked python -m app.util.init

# Start development server
uv run --locked uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Backend available at: `http://localhost:8000`
Interactive API docs: `http://localhost:8000/docs`

### 2. Frontend

```bash
cd frontend

# Install exact dependencies from the lockfile
npm ci

# Copy and edit environment
cp .env.example .env   # or create frontend/.env
# VITE_API_URL=http://localhost:8000/api/v1

# Start development server
npm run dev
```

Frontend available at: `http://localhost:5173`

### 3. PostgreSQL Setup

```sql
CREATE DATABASE attendance_db;
CREATE EXTENSION IF NOT EXISTS vector;   -- pgvector for face embeddings
```

### 4. Redis (optional)

```bash
redis-server
```

If Redis is unavailable, the system degrades gracefully to local in-process rate limiting. See [`docs/SECURITY.md`](docs/SECURITY.md) for implications.

---

## Project Structure

```
backend/
  app/
    api/          # Dependency injection (auth, DB session)
    core/         # Config, security utilities
    crud/         # Database CRUD helpers
    db/models/    # SQLAlchemy ORM models
    repositories/ # Data access layer
    routers/      # FastAPI route handlers (37 routers)
    schema/       # Pydantic request/response schemas
    services/     # Business logic (attendance pipeline, biometrics, audit)
    tests/        # pytest test suite
  alembic/        # Database migration scripts
  main.py         # Application entry point

frontend/
  src/
    components/   # Reusable UI components
    layouts/      # DashboardLayout with nav, notifications
    pages/        # Route-level page components
    services/     # API client wrappers
    store/        # Zustand state (auth, permissions)
    hooks/        # React hooks

docs/             # Authoritative documentation (see below)
infrastructure/   # Docker Compose for local services
deploy/           # Production Docker Compose
```

---

## Testing

```bash
# Backend tests
cd backend
DEBUG=false pytest app/tests/ -v

# Frontend production build validation
cd frontend
npm run build
```

See [`docs/TESTING.md`](docs/TESTING.md) for the full testing guide.

---

## Documentation

| Document | Purpose |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, data flow, component responsibilities |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Developer onboarding, setup, conventions |
| [API.md](docs/API.md) | Core API endpoint reference |
| [SECURITY.md](docs/SECURITY.md) | Auth, RBAC, tenant isolation, security model |
| [BIOMETRICS.md](docs/BIOMETRICS.md) | Face recognition pipeline, enrollment, verification |
| [ATTENDANCE.md](docs/ATTENDANCE.md) | Attendance lifecycle, corrections, leave |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker, environment, production configuration |
| [TESTING.md](docs/TESTING.md) | Test architecture, commands, coverage |
| [ROADMAP.md](docs/ROADMAP.md) | Prioritized remaining work |

---

## Security Status

| Area | Status |
|---|---|
| JWT in HttpOnly cookies | Implemented |
| Token rotation on refresh | Implemented |
| Multi-tenant isolation | Implemented |
| RBAC permission enforcement | Implemented |
| Rate limiting (distributed) | Partial (Redis-dependent) |
| Biometric security hardening | Implemented |
| Production security audit | **Not Verified** |

See [`docs/SECURITY.md`](docs/SECURITY.md) for details.

---

## License

Proprietary / Academic Project. All rights reserved.
