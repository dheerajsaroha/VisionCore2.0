# Infrastructure

Local development services and deployment artifacts for VisionCore 2.0.

---

## Local Development Services

`infrastructure/docker-compose.yml` starts the **local backing services** required by the backend:

```bash
cd infrastructure
docker compose up -d
```

This starts:

| Service | Image | Port | Purpose |
|---|---|---|---|
| PostgreSQL | `ankane/pgvector:v0.5.1` | `5432` | Primary database (includes pgvector for face embeddings) |
| Redis | `redis:7.2-alpine` | `6379` | Token blacklist, rate limiting cache |

**Note:** The backend application itself is **not** started by this compose file. Run the FastAPI backend separately — see [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md).

---

## Database Initialization

The `database/` subdirectory contains:

- `init.sql` — Initial schema bootstrap script (pgvector extension, base tables)

This script runs automatically when the `postgres` container starts for the first time via Docker's `entrypoint-initdb.d` mechanism.

After the container is running, apply Alembic migrations:

```bash
cd backend
alembic upgrade head
```

---

## Production Deployment

See [`docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md) for the full production deployment guide, including:

- `docker-compose.prod.yml` (repository root) — full-stack production compose
- `deploy/` — Docker Compose, Nginx config, database init scripts, environment template
- Environment variable reference

---

## Kubernetes

The `k8s/` directory contains Kubernetes manifests:

| File | Purpose |
|---|---|
| `k8s/configmaps.yaml` | Environment configuration |
| `k8s/secrets.yaml` | Secret references (DB credentials, JWT key) |
| `k8s/ingress.yaml` | External routing |

> **Status: NOT VERIFIED.** The Kubernetes manifests have not been validated against the current application. Review and update before use in production.

```bash
kubectl apply -f infrastructure/k8s/
```

---

For full setup instructions, see [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md).
