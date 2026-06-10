#!/usr/bin/env python
"""
Try every possible way to authenticate to Xert calendar endpoints.
Focus: OAuth cookies, laravel_token cookie, and session from oauth flow.
"""
import requests
import json
import os
from datetime import date, timedelta

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_path):
    for line in open(env_path):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

EMAIL    = os.environ.get('XERT_EMAIL', '')
PASSWORD = os.environ.get('XERT_PASSWORD', '')
BASE     = "https://www.xertonline.com"

start = (date.today() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00.000Z")
end   = (date.today() + timedelta(days=28)).strftime("%Y-%m-%dT23:59:59.000Z")
CAL   = f"{BASE}/calendar/events?start={start}&end={end}&includeDuplicates=true"
XHR   = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}

def test(label, session_or_none, extra_headers={}):
    s = session_or_none or requests.Session()
    hdrs = {**XHR, **extra_headers}
    r = s.get(CAL, headers=hdrs, timeout=10)
    ct = r.headers.get("content-type", "")
    ok = r.status_code == 200 and "json" in ct
    print(f"{'✓' if ok else '✗'} [{r.status_code}] {label}")
    if ok:
        data = r.json()
        print(f"   → {len(data)} items!")
        if data:
            print(f"   → Keys: {list(data[0].keys())[:8]}")
            for item in data[:3]:
                print(f"   · {item.get('name','?')} — {str(item.get('start') or item.get('date',''))[:10]}")
    elif r.status_code not in (401, 404):
        print(f"   → {r.text[:80]}")
    return ok

# ── Method 1: OAuth with session (captures any cookies set) ──────
print("=== Method 1: OAuth via session object ===")
s1 = requests.Session()
auth_r = s1.post(f"{BASE}/oauth/token", data={
    "grant_type": "password", "username": EMAIL, "password": PASSWORD,
    "client_id": "xert_public", "client_secret": "xert_public",
})
token = auth_r.json().get("access_token")
print(f"Token: {token[:20]}...")
print(f"OAuth response cookies: {dict(auth_r.cookies)}")
print(f"Session cookies after OAuth: {dict(s1.cookies)}")
if test("Session cookies from OAuth (no Bearer)", s1): exit()
if test("Session cookies + Bearer", s1, {"Authorization": f"Bearer {token}"}): exit()

# ── Method 2: laravel_token cookie (Laravel SPA auth) ────────────
print("\n=== Method 2: laravel_token cookie ===")
s2 = requests.Session()
s2.cookies.set("laravel_token", token, domain="www.xertonline.com")
if test("laravel_token cookie + XHR", s2): exit()
if test("laravel_token cookie + Bearer + XHR", s2, {"Authorization": f"Bearer {token}"}): exit()

# ── Method 3: Hit main site first to get XSRF token ──────────────
print("\n=== Method 3: XSRF token flow ===")
s3 = requests.Session()
s3.get(f"{BASE}/", timeout=10)  # Get initial cookies
xsrf = s3.cookies.get("XSRF-TOKEN") or s3.cookies.get("xsrf-token")
print(f"XSRF token: {xsrf[:20] if xsrf else 'None'}")
s3.headers.update({"X-XSRF-TOKEN": xsrf or ""})
# Now do OAuth
s3.post(f"{BASE}/oauth/token", data={
    "grant_type": "password", "username": EMAIL, "password": PASSWORD,
    "client_id": "xert_public", "client_secret": "xert_public",
})
print(f"Cookies after main+oauth: {list(s3.cookies.keys())}")
if test("XSRF + OAuth session", s3): exit()
if test("XSRF + OAuth session + Bearer", s3, {"Authorization": f"Bearer {token}"}): exit()

# ── Method 4: POST to /login via AJAX ────────────────────────────
print("\n=== Method 4: AJAX login POST ===")
s4 = requests.Session()
# Try posting to login as JSON
login_r = s4.post(f"{BASE}/login",
    json={"email": EMAIL, "password": PASSWORD},
    headers={"Accept": "application/json", "Content-Type": "application/json"},
    timeout=10)
print(f"Login POST (JSON): {login_r.status_code} — {login_r.text[:100]}")
print(f"Cookies: {list(s4.cookies.keys())}")
if test("After JSON login POST", s4): exit()

# ── Method 5: Try alternative login URLs ─────────────────────────
print("\n=== Method 5: Alternative login URLs ===")
s5 = requests.Session()
for login_path in ["/auth/login", "/user/login", "/account/login", "/sign-in", "/signin"]:
    r = s5.post(f"{BASE}{login_path}",
        data={"email": EMAIL, "password": PASSWORD, "username": EMAIL},
        headers={"Accept": "application/json"},
        timeout=8)
    if r.status_code not in (404, 405):
        print(f"  [{r.status_code}] {login_path} — {r.text[:80]}")
        if r.status_code in (200, 302):
            if test(f"After {login_path}", s5): exit()

print("\n=== No method worked — Xert requires real browser session ===")
print("Recommendation: Use Playwright for headless browser auth")
print("OR: Show planner with template data until Xert API is accessible")
