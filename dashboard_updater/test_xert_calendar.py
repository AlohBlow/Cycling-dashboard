#!/usr/bin/env python
"""Test Xert calendar endpoints discovered from browser network tab"""
import requests
import json
import sys
from datetime import date, timedelta
sys.path.insert(0, '.')
from config import XERT_EMAIL, XERT_PASSWORD

_AUTH_URL = "https://www.xertonline.com/oauth/token"
_BASE = "https://www.xertonline.com"

print("=" * 70)
print("XERT CALENDAR API TEST")
print("=" * 70)

# Authenticate
r = requests.post(_AUTH_URL, data={
    "grant_type": "password",
    "username": XERT_EMAIL,
    "password": XERT_PASSWORD,
    "client_id": "xert_public",
    "client_secret": "xert_public",
})
token_data = r.json()
token = token_data.get("access_token")
print(f"\n✓ Authenticated: {token[:20]}...\n")

headers = {"Authorization": f"Bearer {token}"}

# Date range: last 30 days to next 30 days
start = (date.today() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00.000Z")
end   = (date.today() + timedelta(days=30)).strftime("%Y-%m-%dT23:59:59.000Z")

tests = [
    # Calendar events (what we saw in browser)
    f"{_BASE}/calendar/events?start={start}&end={end}&includeDuplicates=true",
    f"{_BASE}/calendar/events?start={start}&end={end}",

    # Calendar summary
    f"{_BASE}/calendarSummary/Weekly/theDate={date.today().isoformat()}",
    f"{_BASE}/calendarSummary/Weekly?theDate={date.today().isoformat()}",

    # Try with athlete-specific paths
    f"{_BASE}/calendar/events",
    f"{_BASE}/calendar",

    # Fitness signature - different base
    f"{_BASE}/fitness",
    f"{_BASE}/athlete",
    f"{_BASE}/profile",
]

print("Testing endpoints with Bearer token:\n")
for url in tests:
    try:
        r = requests.get(url, headers=headers, timeout=5)
        icon = "✓" if r.status_code == 200 else "✗"
        print(f"{icon} [{r.status_code}] {url[:80]}")
        if r.status_code == 200:
            try:
                data = r.json()
                if isinstance(data, list):
                    print(f"   → List of {len(data)} items")
                    if data:
                        print(f"   → First item keys: {list(data[0].keys())[:6]}")
                elif isinstance(data, dict):
                    print(f"   → Dict keys: {list(data.keys())[:8]}")
            except:
                print(f"   → Response: {r.text[:100]}")
        elif r.status_code == 401:
            print(f"   → Auth required (try cookies instead of Bearer)")
        elif r.status_code == 302:
            print(f"   → Redirect to: {r.headers.get('Location', '?')}")
    except Exception as e:
        print(f"✗ [ERR] {url[:80]}")
        print(f"   → {str(e)[:60]}")
    print()

print("=" * 70)
