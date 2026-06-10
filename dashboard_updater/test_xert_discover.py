#!/usr/bin/env python
"""
Discover Xert's real API endpoints by scanning their JS bundle.
Also try token-as-cookie and other auth variations.
"""
import requests
import re
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

# Get token
auth_r = requests.post(f"{BASE}/oauth/token", data={
    "grant_type": "password", "username": EMAIL, "password": PASSWORD,
    "client_id": "xert_public", "client_secret": "xert_public",
})
token = auth_r.json().get("access_token")
print(f"Token: {token[:20]}...\n")

# ── 1. Try token as cookie / URL param ───────────────────────────
start = (date.today() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00.000Z")
end   = (date.today() + timedelta(days=28)).strftime("%Y-%m-%dT23:59:59.000Z")

print("=== Auth variations ===")
tests = [
    ("Token as URL param",
     f"{BASE}/calendar/events?token={token}&start={start}&end={end}",
     {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}, {}),
    ("Token as cookie",
     f"{BASE}/calendar/events?start={start}&end={end}",
     {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
     {"token": token}),
    ("access_token cookie",
     f"{BASE}/calendar/events?start={start}&end={end}",
     {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
     {"access_token": token}),
]
for label, url, hdrs, cookies in tests:
    r = requests.get(url[:100]+"...", headers=hdrs, cookies=cookies, timeout=8) if len(url)>100 else requests.get(url, headers=hdrs, cookies=cookies, timeout=8)
    ct = r.headers.get("content-type","")
    icon = "✓" if "json" in ct and r.status_code==200 else "~" if r.status_code==200 else "✗"
    print(f"{icon} [{r.status_code}] {label}: {r.text[:80]}")

# ── 2. Scan JS bundle for API endpoints ──────────────────────────
print("\n=== Scanning Xert JS for API endpoints ===")
# Get the main page to find JS bundle URL
home = requests.get(f"{BASE}/my-fitness", timeout=10)
js_files = re.findall(r'src="(/[^"]+\.js[^"]*)"', home.text)
print(f"Found {len(js_files)} JS files: {js_files[:5]}")

api_patterns = set()
for js_url in js_files[:5]:  # Check first 5
    full_url = BASE + js_url if js_url.startswith('/') else js_url
    print(f"\nFetching: {full_url[:80]}")
    try:
        r = requests.get(full_url, timeout=15)
        content = r.text
        # Find API endpoint patterns
        matches = re.findall(r'["\`](/(?:api|calendar|xata|fitness|athlete|workout|activity)[^"\`\s?]{3,50})', content)
        for m in matches:
            api_patterns.add(m)
    except Exception as e:
        print(f"  Error: {e}")

print(f"\n=== API paths found in JS ({len(api_patterns)} unique) ===")
sorted_paths = sorted(api_patterns)
for p in sorted_paths[:60]:
    print(f"  {p}")

# ── 3. Try common Xert API patterns with Bearer ───────────────────
print("\n=== Testing discovered patterns ===")
xhr_bearer = {
    "Authorization": f"Bearer {token}",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
}
candidate_paths = [
    "/api/workouts",
    "/api/calendar",
    "/api/athlete/fitness",
    "/api/athlete/status",
    "/api/planned",
    "/api/events",
    "/workouts",
    "/activities",
    "/athlete/fitness",
]
for path in candidate_paths:
    try:
        r = requests.get(f"{BASE}{path}", headers=xhr_bearer, timeout=6)
        ct = r.headers.get("content-type","")
        if r.status_code != 404:
            icon = "✓" if "json" in ct and r.status_code==200 else "~"
            print(f"{icon} [{r.status_code}] {path} ({ct[:25]}): {r.text[:80]}")
    except:
        pass
