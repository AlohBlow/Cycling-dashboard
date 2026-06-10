#!/usr/bin/env python
"""Test Xert authentication and discover working calendar endpoints."""
import requests
import json
import sys
import os
from datetime import date, timedelta

# Load .env manually
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_path):
    for line in open(env_path):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

XERT_EMAIL    = os.environ.get('XERT_EMAIL', '')
XERT_PASSWORD = os.environ.get('XERT_PASSWORD', '')

print("=" * 60)
print("XERT AUTH TEST")
print("=" * 60)
print(f"Email: {XERT_EMAIL}")
print(f"Password: {'*' * len(XERT_PASSWORD)}")
print()

if not XERT_EMAIL or not XERT_PASSWORD:
    print("ERROR: XERT_EMAIL or XERT_PASSWORD not set in .env")
    sys.exit(1)

# ── Step 1: Authenticate ──────────────────────────────────────────
_AUTH_URL = "https://www.xertonline.com/oauth/token"
print(f"Authenticating at: {_AUTH_URL}")

r = requests.post(_AUTH_URL, data={
    "grant_type": "password",
    "username": XERT_EMAIL,
    "password": XERT_PASSWORD,
    "client_id":     "xert_public",
    "client_secret": "xert_public",
})

print(f"Auth status: {r.status_code}")
print(f"Auth response: {r.text[:500]}")
print()

token_data = r.json()
token = token_data.get("access_token")

if not token:
    print("ERROR: No access_token in response. Check username/password.")
    sys.exit(1)

print(f"✓ Token: {token[:30]}...")
print()

# ── Step 2: Test Calendar Endpoints ──────────────────────────────
headers_bearer = {"Authorization": f"Bearer {token}"}

start = (date.today() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00.000Z")
end   = (date.today() + timedelta(days=21)).strftime("%Y-%m-%dT23:59:59.000Z")

print("Testing calendar endpoints with Bearer token:")
print("-" * 60)

urls = [
    f"https://www.xertonline.com/calendar/events?start={start}&end={end}&includeDuplicates=true",
    f"https://www.xertonline.com/calendar/events?start={start}&end={end}",
    f"https://www.xertonline.com/calendarSummary/Weekly?theDate={date.today().isoformat()}",
    f"https://www.xertonline.com/api/v1/athlete",
    f"https://www.xertonline.com/api/v1/activities?limit=5",
    f"https://www.xertonline.com/api/v1/workouts?limit=5",
]

for url in urls:
    try:
        resp = requests.get(url, headers=headers_bearer, timeout=8, allow_redirects=True)
        icon = "✓" if resp.status_code == 200 else "✗"
        short_url = url[:70] + "..." if len(url) > 70 else url
        print(f"\n{icon} [{resp.status_code}] {short_url}")
        if resp.status_code == 200:
            try:
                data = resp.json()
                if isinstance(data, list):
                    print(f"   → {len(data)} items")
                    if data:
                        print(f"   → Keys: {list(data[0].keys())[:8]}")
                        # Show first item summary
                        first = data[0]
                        name = first.get('name') or first.get('title') or first.get('workout_name') or '?'
                        d    = first.get('date') or first.get('start') or first.get('startTime') or '?'
                        print(f"   → First: '{name}' on {str(d)[:10]}")
                elif isinstance(data, dict):
                    print(f"   → Dict keys: {list(data.keys())[:10]}")
            except:
                print(f"   → Non-JSON: {resp.text[:120]}")
        elif resp.status_code in (301, 302):
            print(f"   → Redirect → {resp.headers.get('Location','?')}")
        else:
            print(f"   → Body: {resp.text[:150]}")
    except Exception as e:
        print(f"\n✗ [ERR] {url[:60]}")
        print(f"   → {e}")

print()
print("=" * 60)
print("Done.")
