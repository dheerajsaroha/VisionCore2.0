# JWT Expiration Bug — Root Cause Fix

## ✅ Step 1: Fix `app/core/security.py` — LAZY REDIS (DONE)
**Root Cause #1:** Module-level `redis_client = redis_async.from_url(...)` was executed at import time. When Redis is not running, the async connection attempt hung indefinitely because no socket timeout was configured. This caused:
- `import app.core.security` to hang (>10s timeout)
- Any diagnostic script importing from security to fail
- `get_current_user` in `deps.py` to hang on `is_token_blacklisted()` call

**Fix:** Replaced module-level `redis_client` with lazy `_get_redis()` function that:
- Delays Redis connection creation until first `blacklist_token()` or `is_token_blacklisted()` call
- Adds `socket_connect_timeout=2` and `socket_timeout=2` so failures are fast (2s vs ∞)
- Existing try/except wrappers already handle Redis failures gracefully by logging warnings and returning `False`

**Verification:** `import app.core.security` now completes in 0.31s (vs ∞ before).

## Step 2: Fix `app/core/config.py` — SECRET_KEY CONSISTENCY (PENDING)
**Root Cause #2:** Auto-generated SECRET_KEY via `secrets.token_urlsafe(48)` changes on every process restart. Token signed by server A cannot be decoded by server B. Set `SECRET_KEY` in `.env` to a stable value.

## Step 3: Full Auth Flow Verification (PENDING)
Needs server restart + login test.

