#!/usr/bin/env python
"""Quick test of official Xert /oauth/ API endpoints."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xert_client as xr
import json

print("=== Xert Official API Test ===\n")

print("[1] Training Info (fitness signature + WOTD)...")
status = xr.get_athlete_status()
print(f"  TP  (Threshold Power):  {status.get('tp')}")
print(f"  LTP (Lower Threshold):  {status.get('ltp')}")
print(f"  HIE (High Intensity E): {status.get('hie')}")
print(f"  PP  (Peak Power):       {status.get('pp')}")
print(f"  Status: {status.get('status_label')}  [{status.get('status_css')}]")
print(f"  TL total: {status.get('tl_total')}")
print(f"  Target XSS: {status.get('xss_today')}")
print(f"  WOTD: {status.get('wotd_name')} ({status.get('wotd_type')})")
print(f"  WOTD desc: {str(status.get('wotd_description',''))[:80]}")
print()

print("[2] Recent activities...")
acts = xr.get_recent_activities(days=30, limit=5)
for a in acts:
    print(f"  {a['date']}  {a['name'][:40]}  [{a.get('type','')}]")
print()

print("[3] User workouts...")
try:
    wkts = xr.get_workouts()
    print(f"  {len(wkts)} workouts in library")
    for w in wkts[:3]:
        print(f"  · {w['name']}")
except Exception as e:
    print(f"  Error: {e}")
