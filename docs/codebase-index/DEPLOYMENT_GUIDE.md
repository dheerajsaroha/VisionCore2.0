# Production Deployment & Infrastructure Guide

> **Phase 10 — Deployment & Infrastructure Architecture**  
> **Extraction Source:** Dockerfiles, Compose manifests, Kubernetes definitions, and CI/CD automation.

---

## 1. Supported Deployment Topologies

VisionCore 2.0 supports three operational deployment models depending on organizational scale:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TOPOLOGY COMPARISON                             │
├─────────────────────┬──────────────────┬───────────────────────────────┤
│ Model               │ Manifests        │ Best Suited For               │
├─────────────────────┼──────────────────┼───────────────────────────────┤
│ 1. Production Stack │ deploy/          │ Small to Medium Enterprises   │
│    (Monolith + Nginx│ docker-compose   │ (Single VM / EC2 Instance)    │
├─────────────────────┼──────────────────┼───────────────────────────────┤
│ 2. Microservice Grid│ infrastructure/  │ High-Volume Distributed Clocks│
│    (Decoupled Svc)  │ docker-compose   │ (Dedicated Biometric Nodes)   │
├─────────────────────┼──────────────────┼───────────────────────────────┤
│ 3. Cloud Kubernetes │ infrastructure/  │ High-Availability Enterprise  │
│    (K8s Ingress)    │ k8s/             │ (EKS, GKE, Auto-Scaling)      │
└─────────────────────┴──────────────────┴───────────────────────────────┘
```

---

## 2. Docker Container Analysis

### 2.1 Backend Container (`backend/Dockerfile`)
- **Base Image:** `python:3.12-slim`
- **System Dependencies:** `libgl1-mesa-glx`, `libglib2.0-0`, `curl`, `gcc`, `libpq-dev` (required for OpenCV and PostgreSQL compilation).
- **Package Management:** Installs locked dependencies via `uv sync --locked --no-dev`.
- **Runtime Command:** `uvicorn main:app --host 0.0.0.0 --port 8000`
- **Healthcheck:** `curl -f http://localhost:8000/health` (interval: 30s, retries: 3).

### 2.2 Frontend Container (`frontend/Dockerfile`)
- **Stage 1 (Builder):** `node:22-alpine` running `npm ci` and `npm run build` to generate static production assets in `/dist`.
- **Stage 2 (Server):** Lightweight `nginx:alpine` serving static web assets on port `80` with SPA HTML5 push-state routing fallback (`try_files $uri $uri/ /index.html`).

### 2.3 AI Biometrics Container (`ai-service/Dockerfile`)
- **Base Image:** `python:3.12-slim` with NVIDIA GPU driver compatibility reservations.
- **Role:** Hosts the dedicated FaceEngine, LivenessEngine, and EmotionEngine on port `8002`.

---

## 3. Production Deployment via Docker Compose (`deploy/`)

The recommended production stack is defined in `deploy/docker-compose.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg15
    container_name: visioncore-db
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB:-attendance_db}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]

  redis:
    image: redis:7-alpine
    container_name: visioncore-redis
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]

  backend:
    build:
      context: ../backend
      dockerfile: Dockerfile
    container_name: visioncore-backend
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
      ENVIRONMENT: production
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }

  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
    container_name: visioncore-frontend
    depends_on: [backend]

  nginx:
    image: nginx:alpine
    container_name: visioncore-nginx
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on: [backend, frontend]

volumes:
  postgres_data:
```

---

## 4. Database Bootstrap & Migration Sequence

Execute migrations and initial data seeding before directing production traffic to the application:

```bash
cd deploy

# 1. Start database and cache services
docker compose up -d postgres redis

# 2. Wait for PostgreSQL to become healthy
docker compose ps

# 3. Apply all 44 Alembic database migrations
docker compose run --rm backend alembic upgrade head

# 4. Initialize PostgreSQL extensions and business calendar
docker compose run --rm backend python -m app.util.init

# 5. Provision initial platform SuperAdmin account
docker compose run --rm backend python -m app.db.create_superadmin

# 6. Launch the full application stack
docker compose up -d
```

---

## 5. Automated CI/CD Deployment Pipeline (AWS ECR + EC2)

The repository includes complete GitHub Actions CI/CD automation in `.github/workflows/`:

```
git push origin main
       │
       ▼
[ CI Workflow: .github/workflows/ci.yml ]
       ├── 1. Lint Backend (Flake8 & Black) & Frontend (ESLint)
       ├── 2. Test Backend (pytest with live Postgres & Redis services)
       └── 3. Validate (runs runtime_validation_platform.py)
       │
       ▼
[ Deploy Workflow: .github/workflows/deploy.yml ]
       ├── 1. Authenticates to AWS via AWS_ACCESS_KEY_ID
       ├── 2. Builds backend Docker image and pushes to Amazon ECR
       └── 3. SSH into production EC2 instance (appleboy/ssh-action)
              ├── Runs git pull origin main
              └── Executes scripts/deploy.sh
                     ├── aws ecr get-login-password
                     ├── docker compose -f docker-compose.prod.yml pull
                     ├── docker compose run --rm backend alembic upgrade head
                     └── docker compose -f docker-compose.prod.yml up -d
```

---

## 6. Production Hardening Checklist

- [ ] **Generate Production Secret Key:** Run `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` and set `SECRET_KEY`.
- [ ] **Configure Strong Database Passwords:** Override all default passwords in `.env` and `deploy/docker-compose.yml`.
- [ ] **Update Nginx Permissions-Policy:** Ensure `deploy/nginx.conf` sets `Permissions-Policy "geolocation=(self), microphone=(self), camera=(self)"` so webcams operate.
- [ ] **SSL/TLS Certificates:** Place valid Certbot / Let's Encrypt certificates into `deploy/ssl/cert.pem` and `deploy/ssl/key.pem`.
- [ ] **Email Provider Credentials:** Set `EMAIL_TRANSPORT=smtp` (or `brevo` / `resend`) with valid credentials to enable real password reset emails.
- [ ] **Verify Backup Retention:** Configure daily automated snapshots of the `postgres_data` volume.
