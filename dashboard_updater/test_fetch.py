"""
Run from dashboard_updater/:
    python test_fetch.py

Prints raw results from every fetch function so you can inspect the shapes
before wiring them into the HTML template.
"""

import json
import sys

sys.path.insert(0, ".")   # make sure local imports work when run from any cwd


def pp(label, data):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print('='*60)
    print(json.dumps(data, indent=2, default=str))


# ── Intervals.icu ─────────────────────────────────────────────────────────────
print("\n" + "▓"*60)
print("  INTERVALS.ICU")
print("▓"*60)

try:
    import intervals_client as iv

    pp("HRV — last 7 days", iv.get_hrv_7d())
    pp("Fitness (CTL/ATL/Form) — last 14 weeks", iv.get_fitness_14w())
    pp("Recent activities (last 10)", iv.get_recent_activities(limit=10))
    pp("Latest wellness (weight + resting HR)", iv.get_latest_wellness())

except Exception as e:
    print(f"\n[INTERVALS ERROR] {type(e).__name__}: {e}")
    import traceback; traceback.print_exc()


# ── Xert ──────────────────────────────────────────────────────────────────────
print("\n" + "▓"*60)
print("  XERT")
print("▓"*60)

try:
    from config import XERT_EMAIL
    if not XERT_EMAIL:
        print("\n  [SKIPPED] XERT_EMAIL not set in config.py")
    else:
        import xert_client as xr
        pp("Athlete status (signature / form / XSS)", xr.get_athlete_status())
        pp("Recent workouts (last 5)", xr.get_recent_workouts(limit=5))

except Exception as e:
    print(f"\n[XERT ERROR] {type(e).__name__}: {e}")
    import traceback; traceback.print_exc()

print("\n" + "▓"*60)
print("  DONE")
print("▓"*60 + "\n")
