# Application Execution Flow

> **Phase 8 — Runtime Control Flow & Execution Lifecycle**  
> **Scope:** Exact procedural execution pathways from process boot to request termination and shutdown.

---

## 1. Application Startup & Initialization Sequence

When the backend process is launched (`uvicorn main:app --host 127.0.0.1 --port 8000`), execution proceeds through the following deterministic phases:

```
Process Launch: uvicorn main:app
       │
       ▼
[ Module Import & Evaluation ]
       ├── backend/main.py loads settings from app/core/config.py
       ├── Pydantic validates .env variables (SECRET_KEY, DATABASE_URL, ALLOWED_ORIGINS)
       ├── Logging initialized with ISO 8601 timestamps and formatters
       └── FastAPI instance instantiated: title, version, docs_url (/docs enabled if dev)
       │
       ▼
[ Middleware Stack Registration (Outer to Inner) ]
       ├── 1. SecurityHeadersMiddleware (X-Frame-Options, Permissions-Policy, HSTS)
       ├── 2. MetricsMiddleware (Prometheus request counters and latency histograms)
       ├── 3. CORSMiddleware (Origin allowlist, credentials, allowed methods)
       └── 4. Request Logging & Timing Middleware (assigns 8-char uuid request_id)
       │
       ▼
[ Router Mounting (app.include_router) ]
       ├── Global rate limiter dependency attached: rate_limit_dependency(100 req/60s)
       └── 48 router modules mounted under prefix /api/v1 (756 endpoints total)
       │
       ▼
[ Lifespan Context Manager Execution: lifespan(app) ]
       ├── Calls app.util.init.create_tables():
       │   ├── 1. Opens connection to PostgreSQL; executes:
       │   │      CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
       │   │      CREATE EXTENSION IF NOT EXISTS "pgcrypto";
       │   │      CREATE EXTENSION IF NOT EXISTS "vector";
       │   ├── 2. Base.metadata.create_all(bind=engine) ensures all 224 tables exist
       │   ├── 3. Creates HNSW cosine vector index:
       │   │      CREATE INDEX IF NOT EXISTS idx_face_embeddings_hnsw 
       │   │      ON face_embeddings USING hnsw (embedding vector_cosine_ops)
       │   │      WITH (m = 16, ef_construction = 64);
       │   └── 4. Calls _load_business_calendar():
       │          Populates in-memory holiday calendar from holiday_calendars table
       ▼
[ Server Ready ] ──► Uvicorn enters async event loop listening for HTTP/WebSocket traffic
```

---

## 2. HTTP Request Lifecycle Sequence

Every incoming HTTP request traverses a multi-stage execution pipeline:

```
[ Incoming Client TCP Request ]
       │
       ▼
[ 1. Ingress & Security Headers Middleware ]
       ├── Evaluates request headers
       ├── Adds Security Headers:
       │   ├── X-Content-Type-Options: nosniff
       │   ├── X-Frame-Options: DENY
       │   ├── X-XSS-Protection: 1; mode=block
       │   ├── Strict-Transport-Security: max-age=31536000; includeSubDomains
       │   ├── Referrer-Policy: strict-origin-when-cross-origin
       │   └── Permissions-Policy: geolocation=(self), camera=(self), microphone=(self)
       ▼
[ 2. Metrics & Observability Middleware ]
       └── Records start time; tracks active HTTP connection gauges
       ▼
[ 3. CORS Enforcement ]
       ├── Validates Origin against settings.ALLOWED_ORIGINS
       └── Evaluates OPTIONS preflight requests; short-circuits with 200 OK
       ▼
[ 4. Request Correlation & Latency Tracker ]
       ├── Assigns request_id = str(uuid.uuid4())[:8] to request.state.request_id
       └── Logs: "[{request_id}] {method} {path} - Started"
       ▼
[ 5. Global Rate Limiter Dependency ]
       ├── Extracts client IP from request.client.host (or X-Forwarded-For)
       ├── Tries Redis sliding window token bucket (100 req/min)
       ├── Falls back to in-memory _fallback_windows if Redis is offline
       └── If exceeded: Raises HTTP 429 Too Many Requests ("Rate limit exceeded")
       ▼
[ 6. Route Matching & Dependency Injection (`app/api/deps.py`) ]
       ├── Resolves matching route handler in mounted router
       ├── Resolves get_db: Creates SessionLocal instance
       ├── Resolves get_current_user:
       │   ├── Extracts Bearer token from Authorization header
       │   ├── Checks token blacklist (Redis or DB)
       │   ├── Decodes JWT payload using SECRET_KEY & HS256
       │   ├── Validates token type == "access"
       │   ├── Verifies session JTI against user_sessions table in database
       │   └── Queries User where id = user_id AND is_deleted = 0
       ├── Resolves require_permission / require_feature:
       │   └── Validates user role permissions and organization subscription plan
       ▼
[ 7. Route Controller & Domain Service Execution ]
       ├── Router parses validated Pydantic request model
       ├── Invokes domain service method (e.g. AttendanceController.process_checkin)
       ├── Service executes business logic and delegates queries to CRUD / Repositories
       └── Database transaction commits or rolls back on unhandled error
       ▼
[ 8. Response Generation & Serialization ]
       ├── Service returns ORM entity or domain dictionary
       ├── Pydantic serializes response model to JSON
       ├── Middleware adds:
       │   ├── X-Request-ID: {request_id}
       │   └── X-Process-Time-Ms: {duration_ms}
       └── Logs: "[{request_id}] {method} {path} - {status_code} - {duration_ms}ms"
       ▼
[ 9. Connection Cleanup ]
       └── get_db finally block executes: db.close() releases connection to pool
```

---

## 3. Detailed Authentication Execution Flow (`/api/v1/auth/login`)

```
POST /api/v1/auth/login
       │  Payload: { "email": "admin@example.com", "password": "SecretPassword" }
       ▼
1. Rate Limit Gate: Enforces strict 5 attempts/minute per IP
       ▼
2. User Lookup:
       SELECT * FROM users WHERE email = :email AND is_deleted = 0;
       If not found: Raises HTTP 401 Unauthorized ("Incorrect email or password")
       ▼
3. Password Hash Verification:
       passlib.verify(password, user.hashed_password)
       If False: Logs failed attempt; raises HTTP 401 Unauthorized
       ▼
4. Inactive Check:
       If not user.is_active: Raises HTTP 403 Forbidden ("Inactive account")
       ▼
5. Session Creation:
       jti = str(uuid.uuid4())
       session_token = secrets.token_urlsafe(32)
       INSERT INTO user_sessions (user_id, jti, session_token, is_active, expires_at)
       VALUES (:user_id, :jti, :session_token, TRUE, NOW() + INTERVAL '7 days');
       ▼
6. Token Generation:
       access_token = jwt.encode({
           "sub": str(user.id),
           "org_id": user.org_id,
           "role": user.role.name,
           "type": "access",
           "jti": jti,
           "exp": NOW() + 60 minutes
       }, SECRET_KEY, algorithm="HS256")
       
       refresh_token = jwt.encode({
           "sub": str(user.id),
           "session_token": session_token,
           "type": "refresh",
           "exp": NOW() + 7 days
       }, SECRET_KEY, algorithm="HS256")
       ▼
7. Response Cookie & Payload Assembly:
       response.set_cookie(
           key="visioncore_refresh",
           value=refresh_token,
           httponly=True,
           secure=(ENVIRONMENT in ["staging", "production"]),
           samesite="lax",
           max_age=7 * 86400
       )
       RETURN {
           "access_token": access_token,
           "token_type": "bearer",
           "expires_in": 3600,
           "user": { "id": user.id, "email": user.email, "role": user.role.name }
       }
```

---

## 4. Biometric Clock-In Execution Sequence (`/api/v1/attendance/verify-checkin`)

```
POST /api/v1/attendance/verify-checkin
       │  Header: Authorization: Bearer <access_token>
       │  Body: Multipart Form (image: JPEG bytes, device_id, location, coords)
       ▼
1. Pre-validation:
       ├── Validates payload image size <= 10 MB (MAX_BIOMETRIC_IMAGE_BYTES)
       └── Validates user permission: attendance.checkin
       ▼
2. Cooldown Gate:
       SELECT timestamp FROM attendance_logs 
       WHERE user_id = :user_id AND org_id = :org_id 
       ORDER BY timestamp DESC LIMIT 1;
       If (NOW() - last_timestamp) < 5 minutes:
           Raises HTTP 400 ("Clock-in cooldown active. Wait 5 minutes.")
       ▼
3. Facial Analysis & Liveness (AI Microservice / Local Engine):
       ├── Haar Cascade / MediaPipe validates face detection bounding box
       ├── Anti-spoofing engine analyzes image frequency texture and eye ratio:
       │   liveness_score = evaluate_liveness(image_bytes)
       │   If liveness_score < 0.85:
       │       Logs to spoof_detection_logs; raises HTTP 400 ("Liveness check failed")
       └── Facenet / DeepFace extracts 128-dimensional embedding vector
       ▼
4. pgvector Cosine Search:
       SELECT user_id, (embedding <-> :vector) AS distance
       FROM face_embeddings
       WHERE org_id = :org_id AND is_active = TRUE
       ORDER BY distance ASC LIMIT 1;
       
       distance = result.distance
       If distance > 0.40:
           Raises HTTP 401 ("Facial identity could not be verified")
       If result.user_id != current_user.id:
           Raises HTTP 403 ("Biometric mismatch: Face matches another employee")
       ▼
5. Attendance Log Record:
       INSERT INTO attendance_logs (
           user_id, org_id, shift_id, timestamp, status, 
           verification_method, confidence_score, liveness_score, location
       ) VALUES (
           current_user.id, current_user.org_id, active_shift.id, NOW(), 
           'present', 'biometric', 1.0 - distance, liveness_score, location
       );
       ▼
6. Background Tasks:
       ├── If BLOCKCHAIN_ENABLED: Enqueues Web3 smart contract anchoring transaction
       └── Pushes real-time clock-in notification event to active WebSocket sessions
       ▼
7. Response:
       RETURN HTTP 200 OK {
           "status": "success",
           "message": "Clock-in successful",
           "timestamp": "2026-11-16T08:30:00Z",
           "confidence": 0.94
       }
```

---

## 5. Graceful Shutdown Sequence

When the server receives a `SIGTERM` or `SIGINT` signal:
1. Uvicorn stops accepting new incoming TCP connections.
2. Active HTTP requests in flight are allowed to complete up to the graceful timeout window.
3. Execution resumes in `backend/main.py:38` inside `lifespan`:
   ```python
   logger.info("Shutting down application...")
   ```
4. SQLAlchemy connection pool (`engine.dispose()`) terminates active pool connections to PostgreSQL.
5. In-process caches and background task workers flush pending queues and terminate cleanly.
