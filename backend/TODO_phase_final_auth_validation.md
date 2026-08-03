# VisionCore v2.0 — Authentication Subsystem Phase Final Validation Plan

## Information Gathered
- **Validation Script**: `runtime_validation_auth_final.py` — 9 phases covering environment, login, users/me, refresh, logout, Redis failure, restart, reload, regression
- **Test Credentials**: 33 accounts across SuperAdmin, OrgAdmin, OrgEmployee, OrgHR, OrgIntern, OrgManager, OrgViewer — all password `Vision@123`
- **Server**: Runs on `127.0.0.1:8000` via `uvicorn main:app`
- **Endpoints**:
  - `POST /api/v1/auth/login` — form-based `username` + `password`
  - `POST /api/v1/auth/refresh` — JSON body `{"refresh_token": "..."}`
  - `POST /api/v1/auth/logout` — Bearer token auth
  - `GET /api/v1/users/me` — Bearer token auth
  - `GET /health` — Health check

## Infrastructure Confirmed
1. ✅ SECRET_KEY no longer auto-generates (config.py `SECRET_KEY: str = ""` with validator)
2. ✅ SECRET_KEY fails fast when missing or < 32 chars (validator raises `ValueError`)
3. ✅ `security.py` uses lazy Redis (`_redis_client = None`, `_get_redis()`)
4. ✅ `rate_limit.py` uses lazy Redis
5. ✅ `cache.py` uses lazy Redis
6. ✅ Redis connections have `socket_connect_timeout=2` and `socket_timeout=2`
7. ✅ JWT encode/decode diagnostic scripts pass (verified in `security.py`)

## Plan: Runtime Validation Execution Steps

### Step 1: Check server status
- Verify FastAPI server is running on port 8000
- Check `.env` has SECRET_KEY, POSTGRES_PASSWORD configured

### Step 2: Run Phase 1 — Environment Validation
- Health check
- SECRET_KEY length >= 32
- JWT algorithm = HS256
- Token lifetimes correct

### Step 3: Run Phase 2 — Login Validation
- POST /api/v1/auth/login with `sa_val@test.local` / `Vision@123`
- Verify HTTP 200, access_token, refresh_token, token_type=bearer
- Decode JWT and verify sub, exp, iat, jti, type, remaining lifetime

### Step 4: Run Phase 3 — Current User
- GET /api/v1/users/me with token
- Verify correct user returned, no auth errors

### Step 5: Run Phase 4 — Refresh Token
- POST /api/v1/auth/refresh with refresh token
- Verify new tokens issued

### Step 6: Run Phase 5 — Logout
- POST /api/v1/auth/logout
- Verify token blacklisted
- GET /users/me returns 401/403

### Step 7: Run Phase 6 — Redis Failure
- Attempt to verify graceful degradation
- Note: Manual Redis stop may be needed

### Step 8: Run Phase 7 — Server Restart
- Verify login works after restart
- Verify /users/me works

### Step 9: Run Phase 8 — Reload
- Verify login works after reload

### Step 10: Run Phase 9 — Regression
- Test org, RBAC, subscription endpoints

### Step 11: Generate Reports
- Runtime Validation Report
- JWT Validation Report
- Authentication Lifecycle Report
- Regression Report
- Freeze Recommendation

## Dependent Files
- `runtime_validation_auth_final.py` — The script to execute
- `app/core/config.py` — Settings validation
- `app/core/security.py` — JWT, blacklist, Redis
- `app/routers/auth.py` — Auth endpoints
- `app/routers/users.py` — Users endpoints
- `app/api/deps.py` — Dependencies (token validation)

## Followup Steps
1. Ensure server is running before executing validation
2. Execute validation script
3. If failures occur, identify root cause and apply minimal fix
4. Re-run all phases after any fix
5. Generate and save all reports

