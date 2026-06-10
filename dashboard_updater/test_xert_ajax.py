#!/usr/bin/env python
"""
Test Xert calendar endpoint with AJAX headers.
The SPA returns HTML for browser requests but JSON for XHR requests.
"""
import requests
import json
import os
from datetime import date, timedelta

# Load .env
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

# Get OAuth token (also sets session cookie)
auth_r = requests.post(f"{BASE}/oauth/token", data={
    "grant_type":    "password",
    "username":      EMAIL,
    "password":      PASSWORD,
    "client_id":     "xert_public",
    "client_secret": "xert_public",
})
token_data = auth_r.json()
token = token_data.get("access_token")
print(f"Token: {token[:20]}...")

# Build date range
start = (date.today() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00.000Z")
end   = (date.today() + timedelta(days=28)).strftime("%Y-%m-%dT23:59:59.000Z")
cal_url = f"{BASE}/calendar/events?start={start}&end={end}&includeDuplicates=true"

print(f"\nTesting: {cal_url[:80]}...\n")

header_sets = [
    ("Bearer + XHR header", {
        "Authorization":    f"Bearer {token}",
        "X-Requested-With": "XMLHttpRequest",
        "Accept":           "application/json",
    }),
    ("Bearer + XHR + Referer", {
        "Authorization":    f"Bearer {token}",
        "X-Requested-With": "XMLHttpRequest",
        "Accept":           "application/json",
        "Referer":          f"{BASE}/my-fitness",
        "Origin":           BASE,
    }),
    ("XHR only (no Bearer)", {
        "X-Requested-With": "XMLHttpRequest",
        "Accept":           "application/json",
    }),
    ("Bearer only (no XHR)", {
        "Authorization":    f"Bearer {token}",
        "Accept":           "application/json",
    }),
]

for label, headers in header_sets:
    r = requests.get(cal_url, headers=headers, timeout=10)
    content_type = r.headers.get("content-type", "")
    is_json = "json" in content_type
    icon = "✓" if (r.status_code == 200 and is_json) else "~" if r.status_code == 200 else "✗"
    print(f"{icon} [{r.status_code}] {label}")
    print(f"   Content-Type: {content_type}")
    if r.status_code == 200 and is_json:
        data = r.json()
        print(f"   ✓✓ JSON DATA! {len(data)} items")
        if data:
            print(f"   Keys: {list(data[0].keys())[:10]}")
            for item in data[:3]:
                name = item.get('name') or item.get('title') or item.get('workout_name') or '?'
                d    = item.get('date') or item.get('start') or item.get('startTime') or '?'
                print(f"   · '{name}' — {str(d)[:10]}")
        break
    elif r.status_code == 200:
        print(f"   HTML response: {r.text[:100]}")
    else:
        print(f"   Body: {r.text[:100]}")
    print()

# Also try the athlete fitness endpoint used in browser
print("\n--- Fitness / Status Endpoints ---")
fitness_urls = [
    f"{BASE}/xata/fitness",
    f"{BASE}/xata/athlete",
    f"{BASE}/xata/status",
    f"{BASE}/xata/recommendations",
    f"{BASE}/xata/calendar",
]
xhr_headers = {
    "Authorization":    f"Bearer {token}",
    "X-Requested-With": "XMLHttpRequest",
    "Accept":           "application/json",
    "Referer":          f"{BASE}/my-fitness",
}
for url in fitness_urls:
    r = requests.get(url, headers=xhr_headers, timeout=8)
    ct = r.headers.get("content-type", "")
    icon = "✓" if (r.status_code == 200 and "json" in ct) else "~" if r.status_code == 200 else "✗"
    print(f"{icon} [{r.status_code}] {url}  ({ct[:30]})")
    if "json" in ct and r.status_code == 200:
        print(f"   → {list(r.json().keys())[:8]}")
