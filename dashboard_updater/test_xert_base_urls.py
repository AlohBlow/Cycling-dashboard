#!/usr/bin/env python
"""
Test different Xert API base URL structures
"""
import requests
import sys
sys.path.insert(0, '.')
from config import XERT_EMAIL, XERT_PASSWORD

print("=" * 70)
print("XERT API BASE URL DISCOVERY TEST")
print("=" * 70)

_AUTH_URL = "https://www.xertonline.com/oauth/token"

# Get token first
print(f"\n1. Authenticating...")
try:
    r = requests.post(_AUTH_URL, data={
        "grant_type": "password",
        "username": XERT_EMAIL,
        "password": XERT_PASSWORD,
        "client_id": "xert_public",
        "client_secret": "xert_public",
    })
    if r.status_code != 200:
        print(f"   ✗ Auth failed: {r.status_code}")
        sys.exit(1)

    access_token = r.json().get("access_token")
    print(f"   ✓ Authenticated")
    headers = {"Authorization": f"Bearer {access_token}"}
except Exception as e:
    print(f"   ✗ Exception: {e}")
    sys.exit(1)

# Try different base URL patterns
base_urls = [
    "https://www.xertonline.com/api/v1",
    "https://www.xertonline.com/api/v2",
    "https://www.xertonline.com/api",
    "https://xertonline.com/api/v1",
    "https://api.xertonline.com/v1",
    "https://api.xertonline.com",
    "https://xert.com/api/v1",
    "https://app.xertonline.com/api/v1",
]

endpoints_to_try = ["/athlete", "/signature", "/user", "/workouts"]

print(f"\n2. Testing different base URLs:")
print("-" * 70)

for base_url in base_urls:
    for endpoint in endpoints_to_try:
        try:
            url = f"{base_url}{endpoint}"
            r = requests.get(url, headers=headers, timeout=3)

            status_icon = "✓" if r.status_code == 200 else "✗"
            print(f"   {status_icon} {url:60} → {r.status_code}")

            if r.status_code == 200:
                try:
                    data = r.json()
                    if isinstance(data, dict) and "tp" in str(data).lower():
                        print(f"      ^^ FOUND TP DATA! ^^")
                except:
                    pass
        except Exception as e:
            print(f"   ✗ {url:60} → Error")

print("\n" + "=" * 70)
