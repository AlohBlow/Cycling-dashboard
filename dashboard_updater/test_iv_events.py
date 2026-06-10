#!/usr/bin/env python
"""Check what Intervals.icu /events actually returns for the next 4 weeks."""
import requests
import json
import os
from datetime import date, timedelta

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_path):
    for line in open(env_path):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

ATHLETE_ID = os.environ.get('INTERVALS_ATHLETE_ID', 'i95383')
API_KEY    = os.environ.get('INTERVALS_API_KEY', '')
BASE       = "https://intervals.icu/api/v1"

auth = ("API_KEY", API_KEY)
today  = date.today()
oldest = today.isoformat()
newest = (today + timedelta(weeks=4)).isoformat()

print(f"Fetching events: {oldest} → {newest}\n")

r = requests.get(f"{BASE}/athlete/{ATHLETE_ID}/events",
                 auth=auth,
                 params={"oldest": oldest, "newest": newest})
print(f"Status: {r.status_code}")
if r.status_code != 200:
    print(r.text)
    exit()

events = r.json()
print(f"Total events: {len(events)}\n")

if events:
    print("=== ALL KEYS in first event ===")
    print(json.dumps(list(events[0].keys()), indent=2))
    print()

    print(f"=== ALL {len(events)} EVENTS ===")
    for ev in events:
        name  = ev.get('name') or ev.get('description') or '(no name)'
        d     = (ev.get('start_date_local') or ev.get('date') or '')[:10]
        etype = ev.get('type') or ev.get('category') or '?'
        load  = ev.get('load') or ev.get('icu_training_load') or 0
        dur   = ev.get('moving_time') or ev.get('duration') or 0
        src   = ev.get('source') or '?'
        print(f"  {d}  [{etype:10s}]  {name[:45]:45s}  load={load}  dur={dur}s  src={src}")

    print()
    print("=== FULL FIRST EVENT (raw) ===")
    print(json.dumps(events[0], indent=2, default=str))
else:
    print("No events found for this period.")
    print("\nTrying broader range (past 30 days + 60 days future)...")
    oldest2 = (today - timedelta(days=30)).isoformat()
    newest2 = (today + timedelta(days=60)).isoformat()
    r2 = requests.get(f"{BASE}/athlete/{ATHLETE_ID}/events",
                      auth=auth,
                      params={"oldest": oldest2, "newest": newest2})
    ev2 = r2.json()
    print(f"Broader search found: {len(ev2)} events")
    for ev in ev2[:10]:
        name = ev.get('name') or ev.get('description') or '(no name)'
        d    = (ev.get('start_date_local') or ev.get('date') or '')[:10]
        print(f"  {d}  {name[:50]}")
