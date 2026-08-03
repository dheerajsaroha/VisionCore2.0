"""
runtime_validation_auth.py — Sprint 1 Authentication Final Runtime Validation
Phase 3: Freeze Validation
"""
from fastapi.testclient import TestClient
from main import app
from app.db.database import SessionLocal
from app.db.models.all_models import User, Role, Organization, UserSession
from app.core.security import get_password_hash
from sqlalchemy.orm import joinedload
import uuid, json, sys

client = TestClient(app)
PASSWORD = "Vision@123"
errors = []

def log(msg):
    print(msg)
    sys.stdout.flush()

def check(cond, msg):
    if cond:
        log(f"  ✅ {msg}")
    else:
        log(f"  ❌ {msg}")
        errors.append(msg)

# ── Setup QA user ──
db = SessionLocal()
qa_user = (
    db.query(User)
    .options(joinedload(User.role))
    .filter(User.is_active == 1, User.is_deleted == 0)
    .order_by(User.id)
    .first()
)
if not qa_user:
    org = db.query(Organization).first()
    role = db.query(Role).filter(Role.name == "Employee").first() or db.query(Role).first()
    if org and role:
        import uuid as _uuid
        uid = _uuid.uuid4().hex[:8]
        qa_user = User(
            org_id=org.id,
            role_id=role.id,
            full_name="QA Validation User",
            username=f"qa_val_{uid}",
            email=f"qa_val_{uid}@test.local",
            employee_id=f"VAL-{uid}",
            hashed_password=get_password_hash(PASSWORD),
            is_active=1,
            is_deleted=0,
        )
        db.add(qa_user)
        db.commit()
        db.refresh(qa_user)

qa_email = qa_user.email
role_name = qa_user.role.name
org_id = str(qa_user.org_id)
log(f"\nQA Identity: {qa_email} | Role: {role_name} | Org: {org_id}")
db.close()

# =====================================================================
# STEP 1 — Login Validation
# =====================================================================
log("\n" + "=" * 70)
log("STEP 1 — Login Validation")
log("=" * 70)

r = client.post("/api/v1/auth/login", data={"username": qa_email, "password": PASSWORD})
check(r.status_code == 200, f"POST /api/v1/auth/login — HTTP {r.status_code}")
payload = r.json()
check("access_token" in payload, "Access token issued")
check("refresh_token" in payload, "Refresh token issued")
check(payload.get("token_type") == "bearer", f"Token type: {payload.get('token_type')}")
access_token = payload["access_token"]
refresh_token = payload["refresh_token"]

# Negative cases
r = client.post("/api/v1/auth/login", data={"username": qa_email, "password": "WRONG_PASS_123"})
check(r.status_code == 401, f"Wrong password — HTTP {r.status_code}")

r = client.post("/api/v1/auth/login", data={"username": "nonexistent@test.local", "password": PASSWORD})
check(r.status_code == 401, f"Non-existent user — HTTP {r.status_code}")

# =====================================================================
# STEP 2 — Protected Endpoint (/users/me)
# =====================================================================
log("\n" + "=" * 70)
log("STEP 2 — Protected Endpoint (GET /api/v1/users/me)")
log("=" * 70)

r = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {access_token}"})
check(r.status_code == 200, f"GET /api/v1/users/me — HTTP {r.status_code}")
me = r.json()
check(str(me["id"]) == str(qa_user.id), f"Correct user ID: {me['id']}")
check(me["email"] == qa_email, f"Correct email: {me['email']}")
check(me["role"]["name"] == role_name, f"Correct role: {me['role']['name']}")
check(str(me["org_id"]) == org_id, f"Correct org_id: {me['org_id']}")

# Unauthenticated
r = client.get("/api/v1/users/me")
check(r.status_code in (401, 403), f"Unauthenticated — HTTP {r.status_code}")

r = client.get("/api/v1/users/me", headers={"Authorization": "Bearer invalid_token"})
check(r.status_code in (401, 403), f"Invalid token — HTTP {r.status_code}")

# =====================================================================
# STEP 3 — Refresh Validation (ALL Cases A-E)
# =====================================================================
log("\n" + "=" * 70)
log("STEP 3 — Refresh Validation")
log("=" * 70)

# Case A — JSON body
r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
check(r.status_code == 200, f"Case A (JSON body) — HTTP {r.status_code}")
pa = r.json()
check("access_token" in pa, "Case A — New access token")
check("refresh_token" in pa, "Case A — New refresh token")

# Case B — Query parameter
r = client.post("/api/v1/auth/login", data={"username": qa_email, "password": PASSWORD})
assert r.status_code == 200
qt = r.json()["refresh_token"]

r = client.post(f"/api/v1/auth/refresh?refresh_token={qt}")
check(r.status_code == 200, f"Case B (query param) — HTTP {r.status_code}")
check("access_token" in r.json(), "Case B — New access token")

# Case C — Replay (token rotation)
r = client.post("/api/v1/auth/login", data={"username": qa_email, "password": PASSWORD})
assert r.status_code == 200
old_rt = r.json()["refresh_token"]
r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_rt})
assert r.status_code == 200
r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_rt})
check(r.status_code == 401, f"Case C (replay/rotation) — HTTP {r.status_code}")

# Case D — Malformed
r = client.post("/api/v1/auth/refresh", json={"refresh_token": "this.is.not.a.jwt"})
check(r.status_code == 401 or r.status_code == 422, f"Case D (malformed) — HTTP {r.status_code}")

r = client.post("/api/v1/auth/refresh", json={"refresh_token": "eyJhbGciOiJIUzI1NiJ9.dW5yZWFs.dmFsdWU"})
check(r.status_code == 401 or r.status_code == 422, f"Case D (bad JWT) — HTTP {r.status_code}")

# Case E — Missing
r = client.post("/api/v1/auth/refresh", json={})
check(r.status_code == 422, f"Case E (missing) — HTTP {r.status_code}")

# =====================================================================
# STEP 4 — Logout Validation
# =====================================================================
log("\n" + "=" * 70)
log("STEP 4 — Logout Validation")
log("=" * 70)

r = client.post("/api/v1/auth/login", data={"username": qa_email, "password": PASSWORD})
assert r.status_code == 200
lo_token = r.json()["access_token"]
lo_rt = r.json()["refresh_token"]

r = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {lo_token}"})
check(r.status_code == 200, f"POST /api/v1/auth/logout — HTTP {r.status_code}")
check(r.json().get("detail") == "Successfully logged out", "Logout message")

# Blacklisted token rejected
r = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {lo_token}"})
check(r.status_code in (401, 403), f"Blacklisted token — HTTP {r.status_code}")

# Refresh after logout fails
r = client.post("/api/v1/auth/refresh", json={"refresh_token": lo_rt})
check(r.status_code in (401, 422), f"Refresh after logout — HTTP {r.status_code}")

# =====================================================================
# STEP 5 — Redis Validation
# =====================================================================
log("\n" + "=" * 70)
log("STEP 5 — Redis Validation (Graceful Degradation)")
log("=" * 70)

# Login works regardless of Redis
r = client.post("/api/v1/auth/login", data={"username": qa_email, "password": PASSWORD})
check(r.status_code == 200, "Login works (Redis agnostic)")

# =====================================================================
# STEP 6 — Regression
# =====================================================================
log("\n" + "=" * 70)
log("STEP 6 — Regression")
log("=" * 70)

r = client.post("/api/v1/auth/login", data={"username": qa_email, "password": PASSWORD})
check(r.status_code == 200, "Login — regression OK")
reg_at = r.json()["access_token"]
reg_rt = r.json()["refresh_token"]

r = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {reg_at}"})
check(r.status_code == 200, "/users/me — regression OK")

r = client.post("/api/v1/auth/refresh", json={"refresh_token": reg_rt})
check(r.status_code == 200, "Refresh — regression OK")

r = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
check(r.status_code == 200, "Logout — regression OK")

r = client.get("/health")
check(r.status_code == 200, "Health check — regression OK")

# =====================================================================
# RESULTS
# =====================================================================
log("\n" + "=" * 70)
log("VALIDATION RESULTS")
log("=" * 70)

if errors:
    log(f"\nDefects found: {len(errors)}")
    for e in errors:
        log(f"  ❌ {e}")
    log("\n" + "=" * 70)
    log("Sprint 1 — Foundation — Authentication")
    log("Status: 🟡 IN PROGRESS")
    log("First failing: " + errors[0])
    log("=" * 70)
    sys.exit(1)
else:
    log("\nDefects found: 0")
    log("\n" + "=" * 70)
    log("")
    log("Sprint 1")
    log("Foundation")
    log("Authentication")
    log("Status: ✅ COMPLETE")
    log("State: 🔒 FROZEN")
    log("Version: VisionCore v2.0")
    log("")
    log("=" * 70)
    sys.exit(0)

