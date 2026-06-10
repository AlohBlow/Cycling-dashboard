#!/usr/bin/env python
"""
Test Xert web session login to access /calendar/events with cookies.
Xert's web app uses Laravel session auth, not Bearer token, for these endpoints.
"""
import requests
import json
import os
import re
from datetime import date, timedelta

# Load .env manually
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_path):
    for line in open(env_path):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

EMAIL    = os.environ.get('XERT_EMAIL', '')
PASSWORD = os.environ.get('XERT_PASSWORD', '')

BASE = "https://www.xertonline.com"
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
})

print("=" * 60)
print("XERT SESSION LOGIN TEST")
print("=" * 60)

# ── Step 1: Get login page (for CSRF token) ───────────────────────
print("\n[1] Fetching login page for CSRF token...")
r = session.get(f"{BASE}/login", timeout=10)
print(f"    Status: {r.status_code}")

# Extract CSRF token from HTML
csrf = None
match = re.search(r'_token["\s]+value="([^"]+)"', r.text)
if not match:
    match = re.search(r'csrf[_-]token["\s]+content="([^"]+)"', r.text, re.IGNORECASE)
if not match:
    match = re.search(r'"_token":"([^"]+)"', r.text)
if match:
    csrf = match.group(1)
    print(f"    CSRF token: {csrf[:20]}...")
else:
    print("    No CSRF token found — trying without it")
    print(f"    Login page snippet: {r.text[:300]}")

# ── Step 2: POST login credentials ───────────────────────────────
print("\n[2] Posting login credentials...")
login_data = {
    "email": EMAIL,
    "password": PASSWORD,
}
if csrf:
    login_data["_token"] = csrf

r2 = session.post(
    f"{BASE}/login",
    data=login_data,
    headers={"Referer": f"{BASE}/login", "Content-Type": "application/x-www-form-urlencoded"},
    timeout=10,
    allow_redirects=True,
)
print(f"    Status: {r2.status_code}")
print(f"    Final URL: {r2.url}")
print(f"    Cookies: {dict(session.cookies)}")

# Check if we're still on login page (failed) or got redirected (success)
if "/login" in r2.url or r2.status_code == 422:
    print("    ✗ Login failed — still on login page")
    print(f"    Response snippet: {r2.text[:300]}")
else:
    print("    ✓ Login appears successful!")

# ── Step 3: Also try OAuth token + inject as cookie ──────────────
print("\n[3] Also getting OAuth Bearer token...")
auth_r = requests.post(f"{BASE}/oauth/token", data={
    "grant_type": "password",
    "username": EMAIL,
    "password": PASSWORD,
    "client_id": "xert_public",
    "client_secret": "xert_public",
})
token = auth_r.json().get("access_token")
print(f"    Token: {token[:20] if token else 'NONE'}...")

# ── Step 4: Test calendar endpoint with session cookies ───────────
start = (date.today() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00.000Z")
end   = (date.today() + timedelta(days=21)).strftime("%Y-%m-%dT23:59:59.000Z")
cal_url = f"{BASE}/calendar/events?start={start}&end={end}&includeDuplicates=true"

print(f"\n[4] Testing calendar endpoint with session cookies...")
print(f"    URL: {cal_url[:80]}...")

# Try with session cookies only
r3 = session.get(cal_url, headers={"Accept": "application/json"}, timeout=10)
print(f"    [Session only] Status: {r3.status_code}")
if r3.status_code == 200:
    try:
        data = r3.json()
        print(f"    ✓ JSON! {len(data)} items")
        if data:
            print(f"    Keys: {list(data[0].keys())[:10]}")
            print(f"    First: {json.dumps(data[0], default=str)[:300]}")
    except:
        print(f"    Still HTML: {r3.text[:200]}")

# Try with session cookies + Bearer token header
print(f"\n[5] Testing with session cookies + Bearer token header...")
r4 = session.get(cal_url, headers={
    "Accept": "application/json",
    "Authorization": f"Bearer {token}",
}, timeout=10)
print(f"    [Session + Bearer] Status: {r4.status_code}")
if r4.status_code == 200:
    try:
        data = r4.json()
        print(f"    ✓ JSON! {len(data)} items")
        if data:
            print(f"    Keys: {list(data[0].keys())[:10]}")
            print(f"    First item name: {data[0].get('name') or data[0].get('title') or data[0].get('workout_name')}")
    except:
        print(f"    Still HTML: {r4.text[:200]}")

# ── Step 5: Try athlete fitness data via session ───────────────────
print(f"\n[6] Testing fitness/athlete endpoints with session...")
for path in ["/my-fitness", "/fitness", "/athlete", "/dashboard"]:
    r5 = session.get(f"{BASE}{path}", headers={"Accept": "application/json"}, timeout=8)
    icon = "✓" if r5.status_code == 200 else "✗"
    is_json = "json" in r5.headers.get("content-type", "")
    print(f"    {icon} [{r5.status_code}] {path} {'(JSON)' if is_json else '(HTML)'}")

print("\n" + "=" * 60)
print("Done.")
