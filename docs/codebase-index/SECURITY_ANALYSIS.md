# Security Architecture & Risk Analysis

> **Phase 9 — Security Architecture & Vulnerability Analysis**  
> **Scope:** Authentication security, cryptographic guarantees, tenant isolation, biometric privacy, and empirical vulnerability assessment.

---

## 1. Authentication & Session Security Architecture

VisionCore 2.0 implements a hybrid authentication model designed to mitigate cross-site scripting (XSS) and token theft:

```
┌────────────────────────────────────────────────────────┐
│ Client Browser                                         │
│  ├── In-Memory Memory Store: Short-Lived Access Token  │
│  │   (Lifespan: 60 minutes, ALGORITHM: HS256)          │
│  └── Browser Cookie Jar: HttpOnly Refresh Cookie       │
│      (Name: visioncore_refresh, SameSite: Lax, Secure) │
└────────────────────────────────────────────────────────┘
```

### 1.1 Dual-Token Lifecycle & Rotation
- **Access Token:** Short-lived (60 minutes). Contains claims: `sub` (user_id), `org_id`, `role`, `type="access"`, and `jti` (unique session UUID). Kept strictly in client memory to prevent exfiltration via XSS.
- **Refresh Cookie:** Stored in an `HttpOnly`, `SameSite=Lax` cookie (`Secure=True` in staging and production). Never accessible to JavaScript.
- **Refresh Token Rotation:** Every call to `POST /api/v1/auth/refresh` issues a new access token and invalidates the previous refresh token by issuing a new session token, preventing replay attacks.

### 1.2 Database Session Binding (`user_sessions`)
Unlike stateless JWT implementations, VisionCore 2.0 verifies the token's `jti` claim against the `user_sessions` table on **every authenticated request** (`app/api/deps.py:86-100`):
```python
active_session = db.query(UserSession).filter(
    UserSession.user_id == user_id,
    UserSession.jti == session_jti,
    UserSession.is_active == True,
).first()
if not active_session:
    raise HTTPException(status_code=401, detail="Session has been revoked")
```
- **Security Impact:** Instant revocation. Calling `/api/v1/auth/logout` or resetting a password immediately revokes the JWT across all nodes, even when Redis is down.

---

## 2. Multi-Tenant Isolation & Access Control

### 2.1 Row-Level Multi-Tenancy Enforcement
- **Universal `org_id` Scope:** Over 200 database models explicitly declare an `org_id` foreign key.
- **Context Injection:** `TenantContext` middleware binds the authenticated organization ID to the thread-local execution context.
- **Regression Verification:** Tested via `test_tenant_security_regression.py` to ensure user A cannot query or mutate records belonging to organization B.

### 2.2 Enterprise Adaptive Access Control (EAAC)
- **Granular Permissions:** Every endpoint checks fine-grained permissions formatted as `module.action` (e.g. `attendance.corrections`, `payroll.approve`).
- **Dynamic Role Elevation:** Changes to dynamic roles require dual authorization records (`role_approvals`) and maintain immutable history in `role_assignment_history`.

---

## 3. Biometric Data Protection & Privacy

1. **Vector Storage:** Facial images are transformed into 128-dimensional mathematical embedding vectors. The raw bitmap is not retained in primary database tables.
2. **AES-256 Symmetric Encryption:** Supported via `app/core/biometric_crypto.py` to encrypt vector representations before disk persistence.
3. **Strict Anti-Spoofing & Liveness:** `LIVENESS_CHECK_ENABLED=True` and `LIVENESS_STRICT_MODE=True` enforce texture analysis, frequency screening, and eye-aspect ratio checks to reject printed photos, video replays, and mask attacks.
4. **Upload Ceilings:** `MAX_BIOMETRIC_IMAGE_BYTES = 10 * 1024 * 1024` (10 MB) prevents memory exhaustion and decompression bomb attacks.

---

## 4. Confirmed Vulnerabilities & Potential Security Risks

### 4.1 Contradictory `Permissions-Policy` in Nginx Configuration
- **Severity:** High (Functional & Deployment Blocker)
- **Evidence:**
  - In `backend/main.py:65`:
    ```python
    response.headers["Permissions-Policy"] = "geolocation=(self), camera=(self), microphone=(self)"
    ```
  - In `deploy/nginx.conf:15`:
    ```nginx
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
    ```
- **Impact:** An empty allowlist (`camera=()`) in Nginx explicitly denies camera access to **all** origins, including the application itself. If deployed behind this Nginx configuration, browser webcam capture for face recognition will fail immediately.
- **Remediation:** Align `deploy/nginx.conf` with `backend/main.py` by updating the header to:
  ```nginx
  add_header Permissions-Policy "geolocation=(self), microphone=(self), camera=(self)" always;
  ```

### 4.2 Hardcoded Fallback Credentials in Container Manifests
- **Severity:** Medium (Operational Risk)
- **Evidence:**
  - `deploy/docker-compose.yml:49`:
    `SECRET_KEY: ${SECRET_KEY:-lSybLY2ZIQTa4NZ26tQVo00SfYJputFLm4MusMLobHg}`
  - `infrastructure/docker-compose.yml:8`:
    `POSTGRES_PASSWORD: SecretPassword123`
  - `infrastructure/docker-compose.yml:99`:
    `JWT_SECRET=SuperSecretKeyAtLeast32CharsLongMustBeComplex!`
- **Impact:** If operators deploy using default `.env` files without overriding these variables, default predictable secrets are used in production.
- **Remediation:** Remove default values from `docker-compose.yml` and require explicit environment variable definitions; fail container launch if variables are missing.

### 4.3 Accumulation of Sensitive Artifacts in Repository Tree
- **Severity:** Low (Repository Hygiene & Data Exposure)
- **Evidence:** 516 PDF files exist under `backend/app_data/uploads/` containing test offer letters and employee payslips generated during test runs.
- **Remediation:** Add `backend/app_data/uploads/` to `.gitignore` and delete generated test PDF files from git tracking.

---

## 5. Rate Limiting, DDoS & Brute-Force Defense

- **Global Ingress Rate Limiting:** Enforced via `app/core/rate_limit.py` using a Redis token bucket (100 requests / 60 seconds per IP).
- **Authentication Endpoint Ceilings:** Strict limits applied to sensitive routes:
  - `POST /api/v1/auth/login`: 5 attempts / minute per IP.
  - `POST /api/v1/auth/forgot-password`: 3 requests / hour per account (`PASSWORD_RESET_ACCOUNT_HOURLY_LIMIT=3`).
  - `POST /api/v1/auth/reset-password`: 5 attempts maximum per OTP code (`PASSWORD_RESET_OTP_MAX_ATTEMPTS=5`).
- **Local Fallback:** When Redis is unavailable, an in-memory sliding window counter prevents service disruption while maintaining local IP rate capping.

---

## 6. Audit Logging & Immutable Ledgers

- **System Audit Logs:** Administrative actions (role changes, user modifications, approval overrides) are recorded in `audit_logs` and `security_event_logs`.
- **Blockchain Anchoring:** When `BLOCKCHAIN_ENABLED=True`, SHA-256 hashes of critical attendance records are submitted via `web3.py` to an EVM smart contract (`AttendanceAudit`), ensuring tamper-proof verification.
