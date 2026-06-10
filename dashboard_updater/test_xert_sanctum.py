#!/usr/bin/env python
"""
Xert SPA login via Laravel Sanctum CSRF cookie flow.
The correct sequence is:
  1. GET /sanctum/csrf-cookie  → sets XSRF-TOKEN cookie
  2. POST /auth/login          → establish session (using X-XSRF-TOKEN header)
  3. GET /calendar/events      → get planned workouts (XHR + session)
"""
import requests
import json
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

s = requests.Session()
s.headers.update({
    "User-Agent":  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
    "Accept":      "application/json",
    "Referer":     BASE + "/",
    "Origin":      BASE,
})

# ── Step 1: Sanctum CSRF cookie ───────────────────────────────────
print("[1] GET /sanctum/csrf-cookie ...")
r1 = s.get(f"{BASE}/sanctum/csrf-cookie", timeout=10)
print(f"    Status: {r1.status_code}")
print(f"    Cookies: {list(s.cookies.keys())}")

xsrf = s.cookies.get("XSRF-TOKEN")
if xsrf:
    xsrf_decoded = unquote(xsrf)
    print(f"    XSRF-TOKEN: {xsrf_decoded[:40]}...")
else:
    print("    No XSRF-TOKEN — trying root page instead")
    r0 = s.get(BASE + "/", timeout=10)
    xsrf = s.cookies.get("XSRF-TOKEN", "")
    xsrf_decoded = unquote(xsrf) if xsrf else ""
    print(f"    After root: cookies={list(s.cookies.keys())}")

# ── Step 2: POST /auth/login ──────────────────────────────────────
print(f"\n[2] Trying multiple credential field combinations ...")
combos = [
    {"username": EMAIL, "password": PASSWORD},
    {"email":    EMAIL, "password": PASSWORD},
    {"username": EMAIL, "password": PASSWORD, "remember": False},
    {"login":    EMAIL, "password": PASSWORD},
]
login_r = None
for creds in combos:
    r = s.post(
        f"{BASE}/auth/login",
        json=creds,
        headers={
            "X-XSRF-TOKEN":     xsrf_decoded,
            "Content-Type":     "application/json",
            "Accept":           "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer":          BASE + "/",
        },
        timeout=10,
    )
    print(f"    [{r.status_code}] {list(creds.keys())[0]}={EMAIL!r} → {r.text[:80]}")
    if r.status_code in (200, 204):
        login_r = r
        print(f"    ✓ Login SUCCESS with fields: {list(creds.keys())}")
        print(f"    Cookies: {list(s.cookies.keys())}")
        break
    login_r = r

# ── Step 4: Test calendar endpoint ───────────────────────────────
print(f"\n[3] Testing /calendar/events ...")
start = (date.today() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00.000Z")
end   = (date.today() + timedelta(days=28)).strftime("%Y-%m-%dT23:59:59.000Z")
cal_url = f"{BASE}/calendar/events?start={start}&end={end}&includeDuplicates=true"

r3 = s.get(cal_url, headers={
    "Accept":           "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Referer":          BASE + "/my-fitness",
}, timeout=10)

ct = r3.headers.get("content-type", "")
print(f"    Status: {r3.status_code}  Content-Type: {ct}")

if r3.status_code == 200 and "json" in ct:
    data = r3.json()
    print(f"\n    ✓✓✓ SUCCESS! {len(data)} calendar events!")
    if data:
        print(f"    Keys: {list(data[0].keys())[:10]}")
        for item in data[:5]:
            name = item.get('name') or item.get('title') or item.get('workout_name') or '?'
            d    = item.get('start') or item.get('date') or item.get('startTime') or '?'
            print(f"    · {str(d)[:10]}  {name[:50]}")
        with open("xert_calendar_sample.json", "w") as f:
            json.dump(data[:3], f, indent=2, default=str)
        print("    Saved sample to xert_calendar_sample.json")
else:
    print(f"    Response: {r3.text[:200]}")

# ── Step 5: Also try /my-fitness page to check login state ────────
print(f"\n[4] Checking login state via /my-fitness ...")
r4 = s.get(f"{BASE}/my-fitness", headers={"Accept": "text/html"}, timeout=10)
logged_in = "logout" in r4.text.lower() or "my-fitness" in r4.url
print(f"    Status: {r4.status_code}  Appears logged in: {logged_in}")
if not logged_in:
    print(f"    Page title snippet: {r4.text[r4.text.find('<title'):r4.text.find('<title')+60]}")
