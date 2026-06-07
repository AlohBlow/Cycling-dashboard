#!/usr/bin/env python
"""
Simple Xert API test - helps debug connection issues
"""
import requests
import sys
sys.path.insert(0, '.')
from config import XERT_EMAIL, XERT_PASSWORD

print("=" * 60)
print("XERT API TEST")
print("=" * 60)

print(f"\n1. Credentials:")
print(f"   Email: {XERT_EMAIL}")
print(f"   Password: {'*' * len(XERT_PASSWORD)}")

_AUTH_URL = "https://www.xertonline.com/oauth/token"
_BASE_URL = "https://www.xertonline.com/api/v1"

# Test 1: Get OAuth token
print(f"\n2. Getting OAuth token from {_AUTH_URL}...")
try:
    r = requests.post(_AUTH_URL, data={
        "grant_type": "password",
        "username": XERT_EMAIL,
        "password": XERT_PASSWORD,
        "client_id": "xert_public",
        "client_secret": "xert_public",
    })
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        token_data = r.json()
        access_token = token_data.get("access_token")
        print(f"   ✓ Got token: {access_token[:20]}...")

        # Test 2: Get athlete data
        print(f"\n3. Fetching athlete data from {_BASE_URL}/athlete...")
        headers = {"Authorization": f"Bearer {access_token}"}
        r2 = requests.get(f"{_BASE_URL}/athlete", headers=headers)
        print(f"   Status: {r2.status_code}")
        if r2.status_code == 200:
            data = r2.json()
            print(f"   ✓ Got athlete data:")
            print(f"     - TP: {data.get('tp')}")
            print(f"     - HIE: {data.get('hie')}")
            print(f"     - PP: {data.get('pp')}")
            print(f"     - Status: {data.get('status') or data.get('trainingStatus')}")
        else:
            print(f"   ✗ Error: {r2.status_code}")
            print(f"     Response: {r2.text}")
    else:
        print(f"   ✗ Failed to get token")
        print(f"     Response: {r.text}")
except Exception as e:
    print(f"   ✗ Exception: {e}")

print("\n" + "=" * 60)
