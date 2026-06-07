#!/usr/bin/env python
"""
Comprehensive Xert API endpoint discovery test
"""
import requests
import sys
sys.path.insert(0, '.')
from config import XERT_EMAIL, XERT_PASSWORD

print("=" * 70)
print("XERT API ENDPOINT DISCOVERY TEST")
print("=" * 70)

_AUTH_URL = "https://www.xertonline.com/oauth/token"
_BASE_URL = "https://www.xertonline.com/api/v1"

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

# List of endpoints to test
endpoints = [
    "/athlete",
    "/athletes",
    "/user",
    "/users",
    "/profile",
    "/me",
    "/account",
    "/status",
    "/signature",
    "/workouts",
    "/activities",
    "/training-status",
]

print(f"\n2. Testing endpoints at {_BASE_URL}:")
print("-" * 70)

for endpoint in endpoints:
    try:
        url = f"{_BASE_URL}{endpoint}"
        r = requests.get(url, headers=headers, timeout=5)

        status_icon = "✓" if r.status_code < 400 else "✗"
        print(f"   {status_icon} {endpoint:30} → {r.status_code}", end="")

        if r.status_code == 200:
            # Show what data we got
            try:
                data = r.json()
                if isinstance(data, dict):
                    keys = list(data.keys())[:5]
                    print(f"  | Keys: {keys}")
                elif isinstance(data, list):
                    print(f"  | List with {len(data)} items")
                else:
                    print(f"  | Type: {type(data).__name__}")
            except:
                print(f"  | (Not JSON)")
        else:
            print()
    except Exception as e:
        print(f"   ✗ {endpoint:30} → Exception: {str(e)[:40]}")

print("\n" + "=" * 70)
print("Note: Look for endpoints with status 200 that contain TP, HIE, PP data")
print("=" * 70)
