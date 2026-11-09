# VisionCore 2.0 — Troubleshooting & Operational Guide

This document covers solutions to common cross-platform setup, dependency, database, and container issues.

## 1. Python JWT Import Error (`No module named 'jose'`)

### Cause
The app's `jose` import is provided by the **`python-jose`** distribution in the backend's locked Python 3.12 environment. The separate PyPI package named `jose` is not a substitute. Running global Python (or a different virtual environment) can also make the project dependency unavailable.

### Resolution (PowerShell)
From the repository root, install/sync and run through `uv`:
```powershell
Set-Location backend
uv sync --locked --group dev
uv run --locked python -c "from jose import jwt; print('python-jose is available')"
uv run --locked python -m uvicorn main:app --reload
```
Do not run `pip install jose`. `uv run` selects the backend's locked Python 3.12 environment, regardless of which global Python appears first on `PATH`.

---

## 2. Password Reset Email Is Not Arriving

The default `EMAIL_TRANSPORT=console` writes reset messages to `backend/dev_mail/`; it does not send email. To use Gmail SMTP in `backend/.env`, set `EMAIL_TRANSPORT=smtp`, configure `SMTP_USER` and a Google App Password in `SMTP_PASSWORD`, and set `EMAIL_FROM` to the authenticated sender address. Restart the backend after changing `.env`; a running process does not automatically reload settings from that file.

The reset endpoint limits each address to three requests per hour and enforces a cooldown. A throttled request intentionally returns the same generic response as a successful request, but it does not send another email. Check the backend logs and `password_reset_requests` delivery status rather than repeatedly submitting the form.

If a newly received link opens but submitting the new password says the link is invalid, restart the backend to load the latest fix. Link single-use state is stored with its reset request in PostgreSQL, so Redis being unavailable no longer invalidates a legitimate reset link. Use a link within its expiry window and only once.

---

## 3. PowerShell Says `deactivate` Is Not Recognized

`deactivate` is only defined while a Python virtual environment is active in the current PowerShell session. After it succeeds once, running it again produces a command-not-found error; this does not affect the project or `uv`.

You can skip deactivation entirely when using `uv run`. If you want to deactivate an environment only when one is active, run this from the repository root:
```powershell
if (Get-Command deactivate -ErrorAction SilentlyContinue) { deactivate }
Set-Location .\backend
uv run --locked python -m uvicorn main:app --reload
```

---

## 4. Login Fails While Loading the User Profile (`employment_records` Column Missing)

### Cause
The password login can succeed, then `GET /api/v1/users/me` can fail while serializing the profile. The ORM reads optional employment fields such as `business_unit_id`, `branch_id`, and `cost_center_id` that may not exist in an older database. Application startup's `create_all()` creates missing tables, but does not add columns to tables that already exist.

### Resolution (PowerShell)
Run migrations from the backend directory, then restart the API:
```powershell
Set-Location .\backend
uv sync --locked --group dev
uv run --locked alembic upgrade head
uv run --locked python -m uvicorn main:app --reload
```

---

## 5. Docker Desktop / WSL2 Fails to Start

### Symptoms:
- Docker commands hang indefinitely or return `npipe:////./pipe/dockerDesktopLinuxEngine` connection errors.
- Running `wsl --status` outputs:
  ```
  WSL2 is unable to start since virtualization is not enabled on this machine.
  Please ensure the "Virtual Machine Platform" optional component is enabled and virtualization is turned on in your computer's firmware settings.
  ```

### Resolution:
1. **Enable Hardware Virtualization in BIOS/UEFI**:
   - Reboot PC, press `F2` / `Del` to enter BIOS.
   - Look for **Intel Virtualization Technology (VT-x)** or **AMD SVM (Secure Virtual Machine)** and set to **Enabled**.
   - Save and exit.
2. **Enable Virtual Machine Platform in Windows**:
   Run PowerShell as Administrator:
   ```powershell
   dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
   dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
   wsl --install --no-distribution
   ```
   Restart Windows.
3. Once restarted, launch Docker Desktop.

---

## 6. Port 8000 Conflict (Address Already in Use)

### Symptoms:
- Uvicorn fails to start:
  ```
  [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000): only one usage of each socket address is normally permitted
  ```

### Resolution:
1. **Identify the conflicting process:**
   ```powershell
   Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
   ```
2. **Option A: Stop the conflicting process** (e.g. if it is another local dev server):
   ```powershell
   Stop-Process -Id <OwningProcessId>
   ```
3. **Option B: Run VisionCore on an alternative port:**
   Start backend on port 8001:
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
   ```
   Update `frontend/.env`:
   ```ini
   VITE_API_URL=http://localhost:8001/api/v1
   ```

---

## 7. Biometrics, Dlib, and C-Extension Compilation Failures on Windows

### Symptoms:
- `pip install face-recognition` or `dlib` fails with:
  ```
  CMake must be installed to build dlib
  error: [WinError 2] The system cannot find the file specified
  ```
- `Building wheel for ckzg ... exit code 1`

### Resolution:
- `backend/app/services/face_engine.py` is architected with graceful fallback when `face_recognition` is missing:
  ```python
  FACE_RECOGNITION_AVAILABLE = False
  ```
  The core attendance system, auth, permissions, payroll, statutory calculations, and workflows function without `dlib`.
- To run full biometric extraction:
  1. **Recommended:** Run the dedicated `ai-service` container in Docker/WSL2 where Linux compilers are pre-installed.
  2. Alternatively, install Visual Studio C++ Build Tools and CMake on Windows, or use pre-compiled wheels compatible with the supported Python 3.12 runtime.

---

## 8. PostgreSQL Extension Error: `extension "vector" is not available`

### Symptoms:
- Database initialization or migration fails with:
  ```
  ERROR: extension "vector" is not available
  DETAIL: Could not open extension control file ".../extension/vector.control"
  ```

### Resolution:
- Standard `postgres:alpine` images do not include `pgvector`.
- In `deploy/docker-compose.yml`, ensure the image is set to:
  ```yaml
  image: pgvector/pgvector:pg15
  ```
  or `ankane/pgvector:v0.5.1`.

---

## 9. Line Endings / Shell Script Execution Errors in Containers (`\r: command not found`)

### Symptoms:
- Linux container or bash fails to run shell scripts:
  ```
  /bin/bash^M: bad interpreter: No such file or directory
  ```

### Resolution:
- `.gitattributes` at project root enforces LF line endings:
  ```gitattributes
  *.sh text eol=lf
  Dockerfile* text eol=lf
  ```
- To convert existing files on Windows:
  ```powershell
  python -c "open('scripts/deploy.sh', 'wb').write(open('scripts/deploy.sh', 'rb').read().replace(b'\r\n', b'\n'))"
  ```

---

## 6. Database Connection Refused During Alembic Migrations or Tests

### Symptoms:
- `psycopg2.OperationalError: could not connect to server: Connection refused (10061)`

### Resolution:
1. Ensure the PostgreSQL service is running and listening on port 5432:
   ```powershell
   Test-NetConnection -ComputerName 127.0.0.1 -Port 5432
   ```
2. Verify credentials in `backend/.env`:
   ```ini
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   POSTGRES_DB=attendance_db
   ```
3. If using an external/cloud database, you can supply `DATABASE_URL` directly in `backend/.env`:
   ```ini
   DATABASE_URL=postgresql://user:password@cloud-host:5432/attendance_db
   ```

---

## 7. CORS Origin Errors on Frontend

### Symptoms:
- Browser console reports CORS rejection when contacting `http://localhost:8000/api/v1`.

### Resolution:
- Verify `ALLOWED_ORIGINS` in `backend/.env`:
  ```ini
  ALLOWED_ORIGINS=["http://localhost:3000", "http://localhost:5173"]
  ```
- For comma-separated format:
  ```ini
  ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
  ```
  The parser in `backend/app/core/config.py` automatically normalizes both JSON array and comma-delimited strings.
