#!/usr/bin/env python
"""Inspect all 46 Xert calendar events to find planned/forecast ones."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xert_client as xr
from datetime import date, timedelta
from urllib.parse import unquote
import requests

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

# Login
s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Origin": BASE})
s.get(BASE + "/", timeout=10)
xsrf = unquote(s.cookies.get("XSRF-TOKEN", ""))
r = s.post(f"{BASE}/auth/login", json={"username": EMAIL, "password": PASSWORD},
           headers={"X-XSRF-TOKEN": xsrf, "Content-Type": "application/json",
                    "Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}, timeout=15)
print(f"Login: {r.status_code}")

start = (date.today() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00.000Z")
end   = (date.today() + timedelta(days=28)).strftime("%Y-%m-%dT23:59:59.000Z")
cal = s.get(f"{BASE}/calendar/events", params={"start": start, "end": end, "includeDuplicates": "true"},
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest",
                     "Referer": f"{BASE}/my-fitness"}, timeout=15)

events = cal.json()
print(f"\nTotal events: {len(events)}\n")

# Show summary of all events
print(f"{'DATE':<12} {'EXERCISE_TYPE':<20} {'NAME':<35} {'XSS':>6} {'COMPLETED'}")
print("-" * 85)
today = date.today().isoformat()
for ev in events:
    local_dt  = ev.get("start_date_local", "")
    date_str  = local_dt[:10] if local_dt else "?"
    etype     = ev.get("exerciseType", "?")
    name      = (ev.get("name") or "").strip()[:34]
    xss       = ev.get("xss") or 0
    completed = etype == "Activity"
    marker    = "✅" if completed else "📅"
    future    = " ← FUTURE" if date_str > today else ""
    print(f"{date_str:<12} {etype:<20} {name:<35} {xss:>6.1f}  {marker}{future}")

# Show distinct exerciseType values
etypes = set(ev.get("exerciseType") for ev in events)
print(f"\nDistinct exerciseType values: {etypes}")

# Show a future/non-Activity event in full detail
future_events = [ev for ev in events if (ev.get("start_date_local","")[:10] or "") > today]
planned_events = [ev for ev in events if ev.get("exerciseType") != "Activity"]

print(f"\nFuture events (date > today): {len(future_events)}")
print(f"Non-Activity events: {len(planned_events)}")

if future_events:
    print(f"\nFirst future event keys: {list(future_events[0].keys())[:15]}")
    print(f"First future event:")
    # Show key fields only
    fe = future_events[0]
    for k in ['name', 'start_date_local', 'exerciseType', 'xss', 'type', 'distance',
              'duration', 'matched_activity', 'placeholder_xss_details']:
        print(f"  {k}: {fe.get(k)}")

# Save full list for inspection
with open("xert_all_events.json", "w") as f:
    json.dump([{
        "date": (ev.get("start_date_local","")[:10]),
        "name": ev.get("name","").strip(),
        "exerciseType": ev.get("exerciseType"),
        "xss": ev.get("xss") or 0,
        "type": ev.get("type"),
        "matched_activity": ev.get("matched_activity"),
        "placeholder_xss_details": ev.get("placeholder_xss_details"),
    } for ev in events], f, indent=2, default=str)
print("\nFull summary saved to xert_all_events.json")
