# VisionCore 2.0 — Native Ubuntu/Linux Setup Guide

This guide details setting up VisionCore 2.0 natively on Ubuntu 20.04 / 22.04 / 24.04 or Debian Linux.

---

## 1. System Dependencies

Update packages and install standard build tools, OpenCV dependencies, and PostgreSQL development libraries:

```bash
sudo apt-get update && sudo apt-get upgrade -y

sudo apt-get install -y \
    build-essential \
    cmake \
    gcc \
    g++ \
    libpq-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    python3-dev \
    python3-venv \
    python3-pip \
    curl \
    git \
    docker.io \
    docker-compose-v2
```

Configure Docker for non-root user execution:
```bash
sudo usermod -aG docker $USER
newgrp docker
```

Install Node.js 22.12 or later in the 22.x LTS line:
```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
```

Install `uv`:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 2. Clone & Environment Setup

```bash
git clone <repo-url> VisionCore2.0
cd VisionCore2.0

# Create environment files from templates
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Ensure file permissions and line endings are clean:
```bash
chmod +x scripts/*.sh
```

---

## 3. Database & Cache Infrastructure

Start PostgreSQL with pgvector and Redis using Docker Compose:

```bash
docker compose -f deploy/docker-compose.yml up -d postgres redis
```

Verify services are healthy:
```bash
docker compose -f deploy/docker-compose.yml ps
```

---

## 4. Backend Setup & Migrations

### Create Virtual Environment
```bash
cd backend
uv python install 3.12
uv venv --python 3.12
source .venv/bin/activate
```

### Install Dependencies
```bash
uv sync --locked --group dev

# (Optional) Full local biometric dependencies
uv sync --locked --group dev --extra biometrics
```

### Apply Database Migrations
```bash
alembic upgrade head
```

Verify migration status:
```bash
alembic current
```

---

## 5. Frontend Setup

In a separate terminal or window:
```bash
cd frontend
npm ci
npm run build   # Production asset test
npm run dev     # Starts development server on port 3000 / 5173
```

---

## 6. Starting Backend

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 7. Running Full Production Stack (All Services in Docker)

To run backend, frontend, PostgreSQL (pgvector), Redis, and Nginx together:

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

- Web App: `http://localhost:80`
- API Direct: `http://localhost:8000`
- API Health: `http://localhost:8000/health`

---

## 8. Testing

```bash
cd backend
source .venv/bin/activate
pytest app/tests/test_health_sprint9.py app/tests/test_statutory_engine.py -v
```
