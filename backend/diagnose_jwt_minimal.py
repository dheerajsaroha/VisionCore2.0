#!/usr/bin/env python3
"""Minimal JWT diagnostic — no Redis, no DB, no TestClient."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')
import logging
logging.basicConfig(level=logging.WARNING)

import json
from datetime import datetime, timezone, timedelta
import calendar

# Test python-jose directly WITHOUT importing our security module
# (which has module-level Redis connection that causes hangs)

from jose import jwt as jose_jwt, JWTError, ExpiredSignatureError

SECRET_KEY = "test-secret-key-that-is-at-least-32-chars-long!!"
ALGORITHM = "HS256"

print("=" * 70)
print("MINIMAL JWT EXPIRATION DIAGNOSTIC")
print("=" * 70)

# 1. Create token with timezone-aware datetime (like security.py does)
print("\n[1] TOKEN WITH timezone-aware datetime (security.py method)")
print("-" * 50)

now_aware = datetime.now(timezone.utc)
exp_aware = now_aware + timedelta(minutes=60)
print(f"  now: {now_aware.isoformat()}  (tzinfo={now_aware.tzinfo})")
print(f"  exp: {exp_aware.isoformat()}  (tzinfo={exp_aware.tzinfo})")
print(f"  exp.timestamp(): {exp_aware.timestamp()}")
print(f"  time.time():     {__import__('time').time()}")

payload_aware = {
    "exp": exp_aware,
    "sub": "42",
    "type": "access",
    "jti": "test-jti",
    "iat": now_aware,
}
token_aware = jose_jwt.encode(payload_aware, SECRET_KEY, algorithm=ALGORITHM)

# Decode without validation
raw = jose_jwt.get_unverified_claims(token_aware)
print(f"  JWT 'exp' value: {raw.get('exp')} (type={type(raw.get('exp')).__name__})")
print(f"  JWT 'iat' value: {raw.get('iat')} (type={type(raw.get('iat')).__name__})")

# Decode WITH validation
try:
    decoded = jose_jwt.decode(token_aware, SECRET_KEY, algorithms=[ALGORITHM])
    print(f"  ✅ DECODE SUCCESS: sub={decoded.get('sub')} type={decoded.get('type')}")
except ExpiredSignatureError as e:
    print(f"  ❌ EXPIRED SIGNATURE: {e}")
    print(f"  🔥 THIS IS THE BUG!")
except Exception as e:
    print(f"  ❌ OTHER ERROR: {type(e).__name__}: {e}")

# 2. Create token with NAIVE datetime (old method)
print("\n[2] TOKEN WITH NAIVE datetime (legacy method)")
print("-" * 50)

now_naive = datetime.utcnow()
exp_naive = now_naive + timedelta(minutes=60)
print(f"  now: {now_naive.isoformat()}  (tzinfo={now_naive.tzinfo})")
print(f"  exp: {exp_naive.isoformat()}  (tzinfo={exp_naive.tzinfo})")

payload_naive = {
    "exp": exp_naive,
    "sub": "42",
    "type": "access",
    "jti": "test-jti-2",
    "iat": now_naive,
}
token_naive = jose_jwt.encode(payload_naive, SECRET_KEY, algorithm=ALGORITHM)

raw2 = jose_jwt.get_unverified_claims(token_naive)
print(f"  JWT 'exp' value: {raw2.get('exp')} (type={type(raw2.get('exp')).__name__})")

try:
    decoded2 = jose_jwt.decode(token_naive, SECRET_KEY, algorithms=[ALGORITHM])
    print(f"  ✅ DECODE SUCCESS: sub={decoded2.get('sub')}")
except ExpiredSignatureError as e:
    print(f"  ❌ EXPIRED SIGNATURE: {e}")
except Exception as e:
    print(f"  ❌ OTHER ERROR: {type(e).__name__}: {e}")

# 3. Create token with INTEGER timestamp (most reliable)
print("\n[3] TOKEN WITH INTEGER timestamp")
print("-" * 50)

now_ts = int(__import__('time').time())
exp_ts = now_ts + 3600  # +1 hour
print(f"  now_ts: {now_ts}  =  {datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat()}")
print(f"  exp_ts: {exp_ts}  =  {datetime.fromtimestamp(exp_ts, tz=timezone.utc).isoformat()}")

payload_int = {
    "exp": exp_ts,
    "sub": "42",
    "type": "access",
    "jti": "test-jti-3",
    "iat": now_ts,
}
token_int = jose_jwt.encode(payload_int, SECRET_KEY, algorithm=ALGORITHM)

try:
    decoded3 = jose_jwt.decode(token_int, SECRET_KEY, algorithms=[ALGORITHM])
    print(f"  ✅ DECODE SUCCESS: sub={decoded3.get('sub')}")
except ExpiredSignatureError as e:
    print(f"  ❌ EXPIRED SIGNATURE: {e}")
except Exception as e:
    print(f"  ❌ OTHER ERROR: {type(e).__name__}: {e}")

# 4. Check python-jose version
print("\n[4] JOSE LIBRARY INFO")
print("-" * 50)
try:
    import jose
    print(f"  jose path: {jose.__file__}")
    # Try to get version
    try:
        from jose.constants import __version__
        print(f"  jose version: {__version__}")
    except:
        pass
except Exception as e:
    print(f"  Error: {e}")

# Check the encode source to understand datetime handling
print("\n[5] JOSE ENCODE SOURCE (datetime handling)")
print("-" * 50)
try:
    import inspect
    from jose import jwt as jose_module
    source = inspect.getsource(jose_module.encode)
    # Find the datetime handling lines
    for line in source.split('\n'):
        if 'datetime' in line or 'exp' in line.lower() or 'timestamp' in line:
            print(f"  {line.strip()}")
except Exception as e:
    print(f"  Could not inspect: {e}")

# Try to find the claims processing
try:
    source2 = inspect.getsource(jose_module)
    for line in source2.split('\n'):
        if 'exp' in line.lower() and ('check' in line.lower() or 'process' in line.lower() or 'datetime' in line):
            print(f"  {line.strip()}")
except:
    pass

print("\n" + "=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)

