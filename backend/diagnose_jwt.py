#!/usr/bin/env python3
"""Diagnose JWT expiration bug — no server startup required."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')
import logging
logging.basicConfig(level=logging.WARNING)

from datetime import datetime, timezone, timedelta
import json

# Load settings FIRST
from app.core.config import settings

print("=" * 70)
print("JWT EXPIRATION DIAGNOSTIC")
print("=" * 70)

# 1. Check system clock
print("\n[1] SYSTEM CLOCK")
print("-" * 50)
utcnow_naive = datetime.utcnow()
utcnow_aware = datetime.now(timezone.utc)
now_ts = __import__('time').time()
print(f"  datetime.utcnow():          {utcnow_naive}  (naive)")
print(f"  datetime.now(timezone.utc): {utcnow_aware}  (aware)")
print(f"  time.time():                {now_ts}")
print(f"  time.timezone:              {__import__('time').timezone}  (local offset seconds)")
print(f"  time.tzname:                {__import__('time').tzname}")

# 2. Check settings
print("\n[2] SETTINGS")
print("-" * 50)
print(f"  SECRET_KEY:                {settings.SECRET_KEY[:20]}... (len={len(settings.SECRET_KEY)})")
print(f"  ALGORITHM:                 {settings.ALGORITHM}")
print(f"  ACCESS_TOKEN_EXPIRE_MINUTES: {settings.ACCESS_TOKEN_EXPIRE_MINUTES}")
print(f"  REFRESH_TOKEN_EXPIRE_DAYS: {settings.REFRESH_TOKEN_EXPIRE_DAYS}")

# 3. Create a token and inspect
print("\n[3] TOKEN CREATION")
print("-" * 50)
from app.core.security import create_access_token

token = create_access_token(
    subject="42",
    expires_delta=timedelta(minutes=60),
    session_jti="test-jti-12345"
)
print(f"  Token created at:  {datetime.now(timezone.utc).isoformat()}")
print(f"  Token (first 80):  {token[:80]}...")

# 4. Decode WITHOUT validation to inspect payload
print("\n[4] DECODE WITHOUT VALIDATION (raw payload)")
print("-" * 50)
from jose import jwt as jose_jwt, JWTError

# Decode with options={"verify_signature": False} to skip all validation
raw_payload = jose_jwt.get_unverified_claims(token)
raw_header = jose_jwt.get_unverified_header(token)

print(f"  Header:  {json.dumps(raw_header, indent=4)}")
print(f"  Payload: {json.dumps(raw_payload, indent=4, default=str)}")

# Parse timestamps
exp_ts = raw_payload.get("exp", 0)
iat_ts = raw_payload.get("iat", 0)
sub = raw_payload.get("sub")
jti = raw_payload.get("jti")
token_type = raw_payload.get("type")

exp_dt_aware = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
iat_dt_aware = datetime.fromtimestamp(iat_ts, tz=timezone.utc)
now_dt_aware = datetime.now(timezone.utc)

print(f"\n  sub:          {sub}")
print(f"  type:         {token_type}")
print(f"  jti:          {jti}")
print(f"  iat:          {iat_ts}  =  {iat_dt_aware.isoformat()}")
print(f"  exp:          {exp_ts}  =  {exp_dt_aware.isoformat()}")
print(f"  now (UTC):    {now_ts}  =  {now_dt_aware.isoformat()}")
print(f"  remaining:    {exp_ts - now_ts:.1f} seconds  ({(exp_ts - now_ts)/60:.1f} minutes)")
print(f"  already expired? {exp_ts < now_ts}")

# 5. Try decode WITH validation
print("\n[5] DECODE WITH VALIDATION")
print("-" * 50)

try:
    decoded = jose_jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM]
    )
    print(f"  ✅ Decode SUCCESS: {json.dumps(decoded, indent=4, default=str)}")
except Exception as e:
    print(f"  ❌ Decode FAILED: {type(e).__name__}: {e}")

# 6. Check with explicit options
print("\n[6] DECODE WITH EXPLICIT OPTIONS")
print("-" * 50)

try:
    decoded2 = jose_jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        options={"verify_exp": True, "verify_iat": True}
    )
    print(f"  ✅ With verify_exp=True: SUCCESS")
except Exception as e:
    print(f"  ❌ With verify_exp=True: {type(e).__name__}: {e}")

# 7. Check if leeway helps
print("\n[7] DECODE WITH LEEWAY")
print("-" * 50)
try:
    decoded3 = jose_jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        options={"verify_exp": True, "verify_iat": True},
        leeway=300  # 5 minutes leeway
    )
    print(f"  ✅ With leeway=300: SUCCESS")
except Exception as e:
    print(f"  ❌ With leeway=300: {type(e).__name__}: {e}")

# 8. Create a token with naive datetime (legacy approach)
print("\n[8] NAIVE DATETIME TOKEN")
print("-" * 50)
from jose import jwt as jose_jwt
import uuid

# Simulate legacy naive approach
now_naive = datetime.utcnow()  # This is naive
exp_naive = now_naive + timedelta(minutes=60)

to_encode = {
    "exp": exp_naive,
    "sub": "42",
    "type": "access",
    "jti": str(uuid.uuid4()),
    "iat": now_naive,
}
naive_token = jose_jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
print(f"  naive now: {now_naive} (naive={now_naive.tzinfo is None})")
print(f"  naive exp:  {exp_naive} (naive={exp_naive.tzinfo is None})")

# Decode naive token
try:
    decoded_n = jose_jwt.decode(
        naive_token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM]
    )
    print(f"  ✅ Naive token decode: SUCCESS")
except Exception as e:
    print(f"  ❌ Naive token decode: {type(e).__name__}: {e}")

# 9. Check python-jose version
print("\n[9] JOSE LIBRARY VERSION")
print("-" * 50)
try:
    import jose
    print(f"  jose version: {jose.__version__}")
except:
    print(f"  jose package found, but __version__ not available")

# 10. Check the actual jose encode/decode behavior for exp
print("\n[10] JOSE ENCODE/DECODE 'exp' BEHAVIOR")
print("-" * 50)

# Test: what does jose do with an aware datetime in exp?
aware_dt = datetime.now(timezone.utc) + timedelta(hours=1)
naive_dt = datetime.utcnow() + timedelta(hours=1)

print(f"  aware exp: {aware_dt} -> timestamp: {aware_dt.timestamp()}")
print(f"  naive exp: {naive_dt} -> would-be timestamp: {naive_dt.timestamp()}")

# Encode with aware, decode and check what exp comes back
test_payload = {"exp": aware_dt, "sub": "test"}
test_token = jose_jwt.encode(test_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
test_decoded = jose_jwt.get_unverified_claims(test_token)
print(f"  aware exp after round-trip: {test_decoded.get('exp')}")
print(f"  current timestamp: {datetime.now(timezone.utc).timestamp()}")

# Encode with naive, decode and check  
test_payload2 = {"exp": naive_dt, "sub": "test"}
test_token2 = jose_jwt.encode(test_payload2, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
test_decoded2 = jose_jwt.get_unverified_claims(test_token2)
print(f"  naive exp after round-trip: {test_decoded2.get('exp')}")

print("\n" + "=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)

