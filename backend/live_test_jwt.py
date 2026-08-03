#!/usr/bin/env python3
"""
JWT Root Cause Test - Diagnoses the expiring JWT issue.
Bypasses all import hangs by:
1. Starting a uvicorn server in subprocess
2. Using curl to test actual HTTP round-trip
3. Testing with known-good credentials
"""
import sys, os, subprocess, time, json, urllib.request, urllib.error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

POSTGRES_PASSWORD = "postgres"
LOGIN_URL = "http://127.0.0.1:8765/api/v1/auth/login"
ME_URL = "http://127.0.0.1:8765/api/v1/users/me"
HEALTH_URL = "http://127.0.0.1:8765/health"

def http_post(url, data, headers=None):
    """Make POST request."""
    req = urllib.request.Request(url, data=data.encode(), headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return 0, str(e)

def http_get(url, headers=None):
    """Make GET request."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return 0, str(e)

# Step 1: Start the server
print("=" * 70)
print("JWT ROOT CAUSE DIAGNOSTIC — LIVE HTTP TEST")
print("=" * 70)

print("\n[1] Starting uvicorn server on port 8765...")
server_proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8765"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    cwd=BASE_DIR,
    env={**os.environ, "POSTGRES_PASSWORD": POSTGRES_PASSWORD}
)

# Wait for server to be ready
import socket
for attempt in range(30):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 8765))
        s.close()
        print(f"  ✅ Server ready after {attempt+1}s")
        break
    except:
        time.sleep(1)
else:
    print("  ❌ Server failed to start within 30s")
    server_proc.terminate()
    sys.exit(1)

try:
    # Step 2: Health check
    print("\n[2] Health check...")
    status, body = http_get(HEALTH_URL)
    print(f"  GET /health → {status}")
    if status == 200:
        data = json.loads(body)
        print(f"    status={data.get('status')}, version={data.get('version')}")
    else:
        print(f"    body={body[:200]}")

    # Step 3: Login as SuperAdmin
    print("\n[3] Login as SuperAdmin...")
    test_emails = [
        "sa_sub_val@test.local",
        "sa_val@test.local",
        "sa@test.local",
    ]
    
    token = None
    for email in test_emails:
        form_data = f"username={urllib.parse.quote(email)}&password=Vision%40123"
        status, body = http_post(LOGIN_URL, form_data, 
                                 {"Content-Type": "application/x-www-form-urlencoded"})
        print(f"  POST /auth/login ({email}) → {status}")
        if status == 200:
            data = json.loads(body)
            token = data.get("access_token")
            print(f"    ✅ LOGIN SUCCESS")
            print(f"    token_type: {data.get('token_type')}")
            print(f"    access_token[:50]: {token[:50] if token else 'NONE'}...")
            break
        else:
            print(f"    body: {body[:200]}")
    
    if not token:
        # Try direct DB login
        print("\n  Trying to find working credentials from DB...")
        # Check db
        import subprocess
        result = subprocess.run(
            ["PGPASSWORD=" + POSTGRES_PASSWORD, "psql", "-h", "localhost", "-U", "postgres",
             "-d", "attendance_db", "-c", 
             """SELECT u.email, u.hashed_password FROM users u 
                JOIN roles r ON r.id = u.role_id 
                WHERE r.name IN ('SuperAdmin') AND u.is_deleted = 0 LIMIT 5"""],
            capture_output=True, text=True,
            env={"PGPASSWORD": POSTGRES_PASSWORD, "PATH": os.environ.get("PATH", "")}
        )
        print(f"    DB users output: {result.stdout[:500]}")
        print(f"    DB users stderr: {result.stderr[:500]}")
    
    if token:
        # Step 4: Call /users/me IMMEDIATELY
        print("\n[4] GET /users/me (immediate after login)...")
        status, body = http_get(ME_URL, {"Authorization": f"Bearer {token}"})
        print(f"  GET /users/me → {status}")
        if status == 200:
            data = json.loads(body)
            print(f"    ✅ SUCCESS: id={data.get('id')}, email={data.get('email')}")
        else:
            print(f"    ❌ FAILED: body={body[:500]}")
            
            # Try to decode token to verify validity
            import base64
            parts = token.split('.')
            if len(parts) == 3:
                # Decode payload
                padded = parts[1] + '=' * (4 - len(parts[1]) % 4)
                try:
                    payload_bytes = base64.urlsafe_b64decode(padded)
                    payload = json.loads(payload_bytes)
                    print(f"\n    JWT Payload: {json.dumps(payload, indent=6)}")
                    
                    exp_ts = payload.get('exp', 0)
                    now_ts = time.time()
                    print(f"    exp timestamp: {exp_ts}")
                    print(f"    now timestamp: {now_ts}")
                    print(f"    expiration remaining: {(exp_ts - now_ts)/60:.1f} minutes")
                    print(f"    token expired? {exp_ts < now_ts}")
                except Exception as e:
                    print(f"    Could not decode payload: {e}")
    
    # Step 5: Test with /health to confirm server is fine
    print("\n[5] Re-testing health...")
    status, body = http_get(HEALTH_URL)
    print(f"  GET /health → {status}")

    # Step 6: Show server logs
    print("\n[6] Last 20 lines of server stderr:")
    time.sleep(0.5)
    stderr_output = server_proc.stderr.read().decode(errors='replace')
    for line in stderr_output.split('\n')[-30:]:
        if line.strip():
            print(f"  | {line}")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

finally:
    print("\n[7] Shutting down server...")
    server_proc.terminate()
    try:
        server_proc.wait(timeout=5)
    except:
        server_proc.kill()
    print("  Done")

print("\n" + "=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)
