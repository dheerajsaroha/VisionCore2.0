# VisionCore 2.0 — WSL2 Setup Guide (Ubuntu on Windows)

WSL2 provides a native Linux kernel execution environment on Windows 10/11, allowing full compilation of Linux-dependent packages (like `dlib`, `face_recognition`, and `deepface`) without requiring a separate Linux workstation.

---

## 1. Enabling WSL2 & Virtualization

If WSL2 is not enabled on your Windows host:

1. **Enable Hardware Virtualization in BIOS/UEFI**:
   - Reboot your machine and enter BIOS/UEFI settings (typically `F2`, `F12`, `Del`, or `Esc`).
   - Enable **Intel VT-x** (Intel Virtualization Technology) or **AMD-V / SVM** (Secure Virtual Machine).
   - Save changes and boot back into Windows.

2. **Enable Virtual Machine Platform in Windows**:
   Open PowerShell as Administrator:
   ```powershell
   wsl --install -d Ubuntu-22.04
   ```
   Or enable optional features manually:
   ```powershell
   dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
   dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
   wsl --set-default-version 2
   ```
   Restart Windows if prompted.

---

## 2. Setting Up the Ubuntu Environment

Inside your WSL2 Ubuntu terminal:

```bash
sudo apt-get update && sudo apt-get upgrade -y

# System dependencies for Python, PostgreSQL client, OpenCV, CMake, and Dlib compilation
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
    git
```

Install Node.js 22.12 or later in the 22.x LTS line (via NodeSource or NVM):
```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
```

Install `uv`:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 3. Cloning and Setting Up VisionCore 2.0

> **Performance Tip:** For optimal I/O throughput in WSL2, clone into the Linux filesystem (e.g. `~/projects/VisionCore2.0`) rather than the mounted Windows drive (`/mnt/c/...`).

```bash
git clone <repo-url> ~/projects/VisionCore2.0
cd ~/projects/VisionCore2.0
```

### Environment Files
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

---

## 4. Backend & Biometrics Setup

```bash
cd backend
uv python install 3.12
uv venv --python 3.12
source .venv/bin/activate

# Install the locked core backend dependencies
uv sync --locked --group dev

# (Optional) Install full local biometric dependencies
uv sync --locked --group dev --extra biometrics
```

---

## 5. Running Infrastructure via Docker in WSL2

### Option A: Docker Desktop WSL2 Backend
Enable "Ubuntu" in **Docker Desktop Settings -> Resources -> WSL Integration**.

### Option B: Native Docker Engine in WSL2
```bash
sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
newgrp docker
```

Start PostgreSQL (pgvector) and Redis:
```bash
docker compose -f deploy/docker-compose.yml up -d postgres redis
```

---

## 6. Database Migrations

With the database running:
```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

---

## 7. Launching the Services

### Backend:
```bash
cd backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Biometric Microservice (`ai-service`):
```bash
cd ai-service
docker build -t visioncore-ai-service .
docker run -p 8002:8002 --env-file ../backend/.env visioncore-ai-service
```

### Frontend:
```bash
cd frontend
npm ci
npm run dev -- --host 0.0.0.0 --port 3000
```

---

## 8. Verification

- Backend Health: `curl -s http://localhost:8000/health`
- Backend API Docs: Open `http://localhost:8000/docs` in your Windows browser.
- Frontend: Open `http://localhost:3000` or `http://localhost:5173` in your Windows browser.
- Run tests:
  ```bash
  cd backend && pytest app/tests/test_health_sprint9.py -v
  ```
