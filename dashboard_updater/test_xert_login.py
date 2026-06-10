#!/usr/bin/env python
"""
Xert login via /auth/login with proper CSRF token.
Discovery: /auth/login exists and returns 419 (CSRF mismatch) - we just need correct CSRF.
"""
import requests
import json
import re
import os
from urllib.parse import unquote
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

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"})

# ── Step 1: GET / to receive XSRF-TOKEN cookie ────────────────────
print("[1] Getting XSRF token from root...")
r = s.get(BASE + "/", timeout=10)
print(f"    Status: {r.status_code}  Cookies: {list(s.cookies.keys())}")

xsrf_cookie = s.cookies.get("XSRF-TOKEN")
if xsrf_cookie:
    xsrf_decoded = unquote(xsrf_cookie)
    print(f"    XSRF-TOKEN (decoded): {xsrf_decoded[:40]}...")
else:
    print("    No XSRF-TOKEN yet")
    xsrf_decoded = ""

# Also try getting the login page to find any hidden _token field
print("\n[2] GET /auth/login for hidden _token field...")
r2 = s.get(BASE + "/auth/login", timeout=10)
print(f"    Status: {r2.status_code}  Cookies: {list(s.cookies.keys())}")

# Refresh XSRF after hitting login page
xsrf_cookie = s.cookies.get("XSRF-TOKEN")
if xsrf_cookie:
    xsrf_decoded = unquote(xsrf_cookie)
    print(f"    XSRF-TOKEN (decoded): {xsrf_decoded[:40]}...")

# Try to find hidden _token in HTML
hidden_token = None
if r2.status_code == 200:
    match = re.search(r'name="_token"[^>]*value="([^"]+)"', r2.text)
    if not match:
        match = re.search(r'value="([^"]+)"[^>]*name="_token"', r2.text)
    if match:
        hidden_token = match.group(1)
        print(f"    Hidden _token: {hidden_token[:40]}...")
    else:
        print(f"    No hidden _token in form. Page snippet: {r2.text[:200]}")

# ── Step 2: POST to /auth/login with CSRF ─────────────────────────
print("\n[3] POST to /auth/login...")

csrf_to_use = hidden_token or xsrf_decoded
print(f"    Using CSRF: {csrf_to_use[:40] if csrf_to_use else 'NONE'}...")

login_data = {
    "email":    EMAIL,
    "password": PASSWORD,
    "_token":   csrf_to_use,
}

r3 = s.post(
    BASE + "/auth/login",
    data=login_data,
    headers={
        "Referer":         BASE + "/auth/login",
        "X-XSRF-TOKEN":   xsrf_decoded,
        "Accept":          "application/json, text/html, */*",
        "Content-Type":    "application/x-www-form-urlencoded",
    },
    timeout=10,
    allow_redirects=True,
)
print(f"    Status: {r3.status_code}  Final URL: {r3.url}")
print(f"    Cookies: {list(s.cookies.keys())}")
print(f"    Response: {r3.text[:200]}")

# ── Step 3: Test calendar if login succeeded ──────────────────────
print("\n[4] Testing calendar endpoint with session...")
r4 = s.get(CAL, headers={
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
    "Referer": BASE + "/my-fitness",
}, timeout=10)

ct = r4.headers.get("content-type", "")
print(f"    Status: {r4.status_code}  Content-Type: {ct}")

if r4.status_code == 200 and "json" in ct:
    data = r4.json()
    print(f"\n    ✓✓✓ SUCCESS! {len(data)} calendar events!")
    print(f"    Keys: {list(data[0].keys())[:10] if data else 'empty'}")
    for item in data[:5]:
        name = item.get('name') or item.get('workout_name') or item.get('title') or '?'
        d    = item.get('date') or item.get('start') or item.get('startTime') or '?'
        xss  = item.get('xss') or item.get('strain') or item.get('load') or 0
        print(f"    · {str(d)[:10]}  {name[:45]}  xss={xss}")
    print("\n    Saving full first event to xert_event_sample.json...")
    if data:
        with open("xert_event_sample.json", "w") as f:
            json.dump(data[0], f, indent=2, default=str)
elif r4.status_code == 200:
    print(f"    Still HTML (not logged in): {r4.text[:150]}")
else:
    print(f"    Body: {r4.text[:150]}")

# ── Step 4: Also get fitness/status data ─────────────────────────
print("\n[5] Trying athlete fitness endpoints with logged-in session...")
fitness_paths = [
    "/xata", "/xata/", "/xata/athlete", "/xata/fitness",
    "/athlete/fitness", "/fitness/data", "/my-fitness/data",
    "/api/fitness", "/api/athlete",
]
for path in fitness_paths:
    try:
        r5 = s.get(BASE + path, headers={"Accept":"application/json","X-Requested-With":"XMLHttpRequest"}, timeout=6)
        ct5 = r5.headers.get("content-type","")
        if r5.status_code != 404:
            icon = "✓" if "json" in ct5 and r5.status_code==200 else "~"
            print(f"    {icon} [{r5.status_code}] {path}  ({ct5[:30]})")
            if "json" in ct5 and r5.status_code == 200:
                print(f"       Keys: {list(r5.json().keys())[:8]}")
    except: pass
