#!/usr/bin/env python
"""
Deep Xert API endpoint discovery - focusing on calendar and workout data
"""
import requests
import sys
sys.path.insert(0, '.')
from config import XERT_EMAIL, XERT_PASSWORD

_AUTH_URL = "https://www.xertonline.com/oauth/token"

print("=" * 70)
print("XERT DEEP API DISCOVERY")
print("=" * 70)

# Authenticate
r = requests.post(_AUTH_URL, data={
    "grant_type": "password",
    "username": XERT_EMAIL,
    "password": XERT_PASSWORD,
    "client_id": "xert_public",
    "client_secret": "xert_public",
})
token = r.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}
print(f"\n✓ Authenticated\n")

# Also try with content-type header
headers_json = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# Try multiple base URLs with Xert-specific paths
tests = [
    # Xert app URLs (from browser network inspection patterns)
    ("https://www.xertonline.com/api/v1/athlete", headers),
    ("https://www.xertonline.com/api/v1/athletes/me", headers),
    ("https://www.xertonline.com/api/v2/athlete", headers),
    ("https://www.xertonline.com/api/v2/athlete/me", headers),

    # Xert uses "xata" for their advisor
    ("https://www.xertonline.com/api/v1/xata", headers),
    ("https://www.xertonline.com/api/v1/xata/athlete", headers),

    # Try without /api/ prefix
    ("https://www.xertonline.com/v1/athlete", headers),
    ("https://www.xertonline.com/v2/athlete", headers),

    # Try different domain patterns
    ("https://www.xertonline.com/api/v1/fitness", headers),
    ("https://www.xertonline.com/api/v1/power-curve", headers),
    ("https://www.xertonline.com/api/v1/training-load", headers),

    # Calendar/planner specific
    ("https://www.xertonline.com/api/v1/calendar", headers),
    ("https://www.xertonline.com/api/v1/events", headers),
    ("https://www.xertonline.com/api/v1/planned-workouts", headers),
    ("https://www.xertonline.com/api/v1/recommendations", headers),

    # Try with username in URL
    (f"https://www.xertonline.com/api/v1/athletes/{XERT_EMAIL}", headers),
    (f"https://www.xertonline.com/api/v1/user/{XERT_EMAIL}", headers),

    # Try the root API
    ("https://www.xertonline.com/api/v1", headers),
    ("https://www.xertonline.com/api", headers),
]

print(f"Testing {len(tests)} endpoints...\n")
for url, hdrs in tests:
    try:
        r = requests.get(url, headers=hdrs, timeout=5)
        icon = "✓" if r.status_code == 200 else "✗"
        print(f"{icon} {url}")
        print(f"  → Status: {r.status_code}")
        if r.status_code == 200:
            try:
                data = r.json()
                print(f"  → Data keys: {list(data.keys())[:8]}")
            except:
                print(f"  → Response: {r.text[:100]}")
        elif r.status_code not in [404]:
            print(f"  → Body: {r.text[:100]}")
    except Exception as e:
        print(f"✗ {url}")
        print(f"  → Error: {str(e)[:60]}")
    print()

print("=" * 70)
print("TIP: Check your browser's Network tab in Xert app to find real endpoints")
print("=" * 70)
