# Configuration & Environment Variable Guide

> **Phase 10 — Configuration Architecture**  
> **Extraction Source:** `backend/app/core/config.py` (Pydantic Settings definition) and service environment files.

---

## 1. Configuration Loading & Precedence

Backend configuration is managed through Pydantic V2 Settings in `app/core/config.py`:
- **Precedence Order:**
  1. System environment variables (e.g. Docker / Kubernetes injected env).
  2. `.env` file in the working directory (`backend/.env`).
  3. Default values declared in the `Settings` class.
- **Validation:** Pydantic validators run at startup; invalid or missing required variables (such as a short `SECRET_KEY`) halt process startup immediately.

---

## 2. Exhaustive Environment Variable Reference

### 2.1 Core Application & Security Settings

| Variable Name | Type | Default Value | Description & Constraints |
|---|---|---|---|
| `APP_NAME` | `str` | `"Face Detection Attendance System"` | Platform application display name |
| `APP_VERSION` | `str` | `"1.0.0"` | Semantic version string |
| `ENVIRONMENT` | `str` | `"development"` | Target environment: `development`, `staging`, `production` |
| `DEBUG` | `bool` | `False` | Debug mode; strict parsing ensures `production` forces `False` |
| `API_V1_STR` | `str` | `"/api/v1"` | URL prefix for all primary REST API routers |
| `SECRET_KEY` | `str` | `""` (Required) | **Critical:** Must be at least 32 characters; used for JWT HS256 signing |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `int` | `60` | Lifespan of short-lived bearer access tokens |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `int` | `7` | Lifespan of session refresh credentials |
| `REFRESH_COOKIE_NAME` | `str` | `"visioncore_refresh"` | Name of the HttpOnly refresh token cookie |
| `REFRESH_COOKIE_SAMESITE` | `str` | `"lax"` | Cookie SameSite policy: `lax`, `strict`, `none` |
| `SESSION_IDLE_TIMEOUT_MINUTES`| `int` | `60` | Inactivity window before user session expiration |
| `ALGORITHM` | `str` | `"HS256"` | Cryptographic algorithm for JWT encoding |
| `BCRYPT_ROUNDS` | `int` | `12` | Cost factor for Bcrypt password hashing |
| `ALLOWED_ORIGINS` | `list` | `["http://localhost:3000", "http://localhost:5173"]` | CORS allowlist (accepts comma-separated string or JSON array) |

### 2.2 Relational Database Settings

| Variable Name | Type | Default Value | Description & Constraints |
|---|---|---|---|
| `POSTGRES_HOST` | `str` | `"localhost"` | PostgreSQL server hostname |
| `POSTGRES_PORT` | `int` | `5432` | PostgreSQL listening port |
| `POSTGRES_USER` | `str` | `"postgres"` | Database administrative username |
| `POSTGRES_PASSWORD` | `str` | `""` | Database password (URL-encoded dynamically) |
| `POSTGRES_DB` | `str` | `"attendance_db"` | Primary database name |
| `DB_ECHO` | `bool` | `False` | If True, logs all raw SQL queries to stdout |
| `DATABASE_URL` | `str` | `None` | Optional direct connection string override |

### 2.3 Biometrics & Facial Recognition Settings

| Variable Name | Type | Default Value | Description & Constraints |
|---|---|---|---|
| `FACE_MODEL_NAME` | `str` | `"Facenet"` | Face embedding extraction model (`Facenet`, `VGG-Face`) |
| `FACE_DISTANCE_THRESHOLD` | `float`| `0.40` | Max cosine distance for valid match (lower is stricter) |
| `LIVENESS_CHECK_ENABLED` | `bool` | `True` | Enables texture & anti-spoof analysis |
| `LIVENESS_STRICT_MODE` | `bool` | `True` | Enforces multi-factor eye-blink and reflection checks |
| `EMBEDDING_DIMENSIONS` | `int` | `128` | Vector length (must match pgvector column schema) |
| `MAX_BIOMETRIC_IMAGE_BYTES`| `int` | `10485760` (10 MB) | Max file size accepted for biometric payloads |

### 2.4 SaaS Subscription & Entitlement Settings

| Variable Name | Type | Default Value | Description & Constraints |
|---|---|---|---|
| `ENFORCE_SUBSCRIPTION_LIMITS`| `bool`| `True` | Gates endpoints by tenant subscription tier |
| `DEFAULT_PLAN_CODE` | `str` | `"starter"` | Plan assigned to self-service provisioned tenants |
| `DEFAULT_TRIAL_DAYS` | `int` | `14` | Duration of initial free trial period |
| `PUBLIC_PLAN_CODES` | `str` | `"starter,professional,enterprise"` | Publicly visible subscription plans |

### 2.5 Email & Notification Delivery Settings

| Variable Name | Type | Default Value | Description & Constraints |
|---|---|---|---|
| `EMAIL_TRANSPORT` | `str` | `"console"` | Transport provider: `console`, `smtp`, `brevo`, `resend` |
| `SMTP_HOST` | `str` | `"smtp.gmail.com"` | Outgoing SMTP server address |
| `SMTP_PORT` | `int` | `587` | Outgoing SMTP server port |
| `SMTP_USER` | `str` | `""` | SMTP authentication username |
| `SMTP_PASSWORD` | `str` | `""` | SMTP authentication password |
| `SMTP_USE_TLS` | `bool` | `True` | Enables STARTTLS encryption |
| `EMAIL_FROM` | `str` | `"noreply@attendance.local"` | Sender email address in outgoing headers |
| `EMAIL_FROM_NAME` | `str` | `"VisionCore"` | Sender display name in outgoing headers |
| `BREVO_API_KEY` | `str` | `""` | API key for Brevo HTTP email delivery |
| `RESEND_API_KEY` | `str` | `""` | API key for Resend HTTP email delivery |
| `FRONTEND_URL` | `str` | `"http://localhost:5173"` | Base URL used to build reset and invite links |

### 2.6 Password Reset & Anti-Abuse Settings

| Variable Name | Type | Default Value | Description & Constraints |
|---|---|---|---|
| `PASSWORD_RESET_EXPIRE_MINUTES` | `int` | `30` | Valid lifetime of a password reset link token |
| `PASSWORD_RESET_OTP_EXPIRE_MINUTES` | `int` | `10` | Valid lifetime of a 6-digit OTP code |
| `PASSWORD_RESET_OTP_MAX_ATTEMPTS` | `int` | `5` | Maximum failed OTP attempts before invalidation |
| `PASSWORD_RESET_ACCOUNT_COOLDOWN_SECONDS`| `int`| `60` | Rate cooldown between consecutive reset requests |
| `PASSWORD_RESET_ACCOUNT_HOURLY_LIMIT` | `int` | `3` | Max reset requests allowed per account per hour |

### 2.7 Blockchain & External Integrations

| Variable Name | Type | Default Value | Description & Constraints |
|---|---|---|---|
| `BLOCKCHAIN_ENABLED` | `bool` | `False` | Toggles Web3 smart contract audit anchoring |
| `BLOCKCHAIN_URL` | `str` | `"http://127.0.0.1:8545"`| Ethereum / EVM RPC node URL |
| `BLOCKCHAIN_PRIVATE_KEY` | `str` | `""` | Private key for transaction signing |
| `BLOCKCHAIN_CONTRACT_ADDRESS`| `str` | `""` | Deployed `AttendanceAudit` contract address |
| `GEOFENCE_ENABLED` | `bool` | `False` | Toggles geographic boundary enforcement |
| `GEOFENCE_RADIUS_METERS` | `int` | `50` | Default allowable clock-in radius |
| `CHECKIN_COOLDOWN_MINUTES` | `int` | `5` | Minimum cooldown between consecutive check-ins |
| `REDIS_URL` | `str` | `"redis://localhost:6379/0"`| Connection string for Redis rate limiting & cache |

---

## 3. Frontend Configuration (`frontend/.env`)

| Variable Name | Default Value | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000/api/v1` | Base URL of backend REST API |
