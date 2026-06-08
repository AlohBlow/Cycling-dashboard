import requests
from datetime import date, timedelta
from config import INTERVALS_ATHLETE_ID, INTERVALS_API_KEY, INTERVALS_BASE_URL


def _auth():
    return ("API_KEY", INTERVALS_API_KEY)


def _get(path, params=None):
    r = requests.get(f"{INTERVALS_BASE_URL}{path}", auth=_auth(), params=params)
    r.raise_for_status()
    return r.json()


# ── HRV ──────────────────────────────────────────────────────────────────────

def get_hrv_7d():
    """
    Returns last 7 days of wellness with HRV fields.
    Each entry: {id (date str), hrv, hrvSdnn, restingHR, ...}
    """
    oldest = (date.today() - timedelta(days=7)).isoformat()
    rows = _get(f"/athlete/{INTERVALS_ATHLETE_ID}/wellness", {"oldest": oldest})
    return [
        {
            "date": r.get("id"),
            "hrv": r.get("hrv"),           # rMSSD
            "hrv_sdnn": r.get("hrvSDNN"),  # API uses camelCase: hrvSDNN
        }
        for r in rows
        if r.get("hrv") is not None
    ]


# ── FITNESS (CTL / ATL / Form) ────────────────────────────────────────────────

def get_fitness_14w():
    """
    Returns daily CTL, ATL, Form (TSB) for the last 14 weeks.
    Uses the /athlete/{id}/activities?oldest=... endpoint which returns
    fitness data per day via the `ctl`/`atl` fields, or falls back to
    the wellness endpoint which carries fitness values.

    Intervals.icu exposes fitness via the /athlete/{id}/wellness endpoint
    (ctl, atl, form fields) — wellness doubles as the fitness log.
    """
    oldest = (date.today() - timedelta(weeks=14)).isoformat()
    rows = _get(f"/athlete/{INTERVALS_ATHLETE_ID}/wellness", {"oldest": oldest})
    result = []
    for r in rows:
        ctl = r.get("ctl")
        atl = r.get("atl")
        form = r.get("form")
        if ctl is not None or atl is not None:
            result.append({
                "date": r.get("id"),
                "ctl": ctl,
                "atl": atl,
                "form": form,
            })
    return result


# ── ACTIVITIES ────────────────────────────────────────────────────────────────

def get_recent_activities(limit=10):
    """
    Returns the last `limit` activities with:
    name, date, distance_km, duration_sec, xss (if available), sport_type.
    """
    # Fetch more than `limit` days to guarantee we get `limit` activities
    # Fetch 60 days to capture recent activities across all sport types
    oldest = (date.today() - timedelta(days=60)).isoformat()
    rows = _get(f"/athlete/{INTERVALS_ATHLETE_ID}/activities", {"oldest": oldest})
    # Exclude bare Strava stubs that have no detail fields
    rows = [r for r in rows if not (r.get("source") == "STRAVA" and not r.get("name"))]
    # Sort by date descending (newest first) then take limit
    rows = sorted(rows, key=lambda r: r.get("start_date_local", ""), reverse=True)[:limit]
    result = []
    for r in rows:
        dist_m = r.get("distance") or 0
        result.append({
            "name": r.get("name"),
            "date": r.get("start_date_local", ""),   # full ISO string, truncated in data_builder
            "distance_km": round(dist_m / 1000, 1) if dist_m else None,
            "duration_sec": r.get("moving_time"),
            "xss": r.get("icu_training_load"),
            "intensity": r.get("icu_intensity"),
            "sport_type": r.get("type"),
        })
    return result


# ── WELLNESS (weight / resting HR) ───────────────────────────────────────────

def get_latest_wellness():
    """
    Returns the most recent wellness entry that has weight and/or restingHR.
    """
    oldest = (date.today() - timedelta(days=14)).isoformat()
    rows = _get(f"/athlete/{INTERVALS_ATHLETE_ID}/wellness", {"oldest": oldest})
    # Walk backwards to find the most recent entry with useful values
    for r in reversed(rows):
        weight = r.get("weight")
        resting_hr = r.get("restingHR")
        if weight or resting_hr:
            return {
                "date": r.get("id"),
                "weight_kg": weight,
                "resting_hr": resting_hr,
                "sleep_secs": r.get("sleepSecs"),
                "sleep_score": r.get("sleepScore"),
                "hrv": r.get("hrv"),
                "sport_info": r.get("sportInfo", []),  # contains eFTP per sport type
            }
    return {}
