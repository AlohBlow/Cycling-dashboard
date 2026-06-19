"""
Xert API client — two auth methods:
  1. OAuth Bearer token → /oauth/training_info, /oauth/activity, /oauth/workout
  2. Web session (username + XSRF-TOKEN) → /calendar/events (planned + completed)
"""

import requests
import time
import logging
from datetime import date, datetime, timedelta
from urllib.parse import unquote
from config import XERT_EMAIL, XERT_PASSWORD

log = logging.getLogger(__name__)

_BASE          = "https://www.xertonline.com"
_AUTH_URL      = f"{_BASE}/oauth/token"
_CLIENT_ID     = "xert_public"
_CLIENT_SECRET = "xert_public"

_token_cache   = {}
_session_cache = {"session": None}


# ── OAuth Bearer token ────────────────────────────────────────────────────────

def _get_token():
    if _token_cache.get("access_token"):
        return _token_cache["access_token"]
    r = requests.post(_AUTH_URL, data={
        "grant_type":    "password",
        "username":      XERT_EMAIL,
        "password":      XERT_PASSWORD,
        "client_id":     _CLIENT_ID,
        "client_secret": _CLIENT_SECRET,
    }, timeout=15)
    r.raise_for_status()
    _token_cache.update(r.json())
    return _token_cache["access_token"]


def _oauth_get(path, params=None):
    headers = {"Authorization": f"Bearer {_get_token()}"}
    r = requests.get(f"{_BASE}/oauth{path}", headers=headers, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


# ── Web session (for /calendar/events) ───────────────────────────────────────

def _get_web_session():
    """Login via Laravel web session and return authenticated requests.Session."""
    if _session_cache["session"]:
        return _session_cache["session"]

    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
        "Accept":     "application/json",
        "Origin":     _BASE,
        "Referer":    _BASE + "/",
    })

    # Step 1: Get XSRF-TOKEN from root page
    s.get(_BASE + "/", timeout=10)
    xsrf = unquote(s.cookies.get("XSRF-TOKEN", ""))

    # Step 2: POST login with username (not email) + XSRF token
    r = s.post(
        f"{_BASE}/auth/login",
        json={"username": XERT_EMAIL, "password": XERT_PASSWORD},
        headers={
            "X-XSRF-TOKEN":     xsrf,
            "Content-Type":     "application/json",
            "Accept":           "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=15,
    )
    if r.status_code not in (200, 204):
        raise RuntimeError(f"Xert web login failed: {r.status_code} {r.text[:100]}")

    log.info("Xert web session established")
    _session_cache["session"] = s
    return s


def _web_get(path, params=None):
    s = _get_web_session()
    r = s.get(f"{_BASE}{path}", params=params, headers={
        "Accept":           "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer":          f"{_BASE}/my-fitness",
    }, timeout=15)
    r.raise_for_status()
    return r.json()


# ── Athlete status & fitness signature ───────────────────────────────────────

def get_athlete_status():
    """
    Returns current Xert fitness signature + training status from /oauth/training_info.
    Fields: tp, ltp, hie, pp, status_label, tl_*, xss_today, wotd_*
    """
    data = _oauth_get("/training_info")

    sig  = data.get("signature", {})
    tl   = data.get("tl", {})
    wotd = data.get("wotd", {})
    target_xss = data.get("targetXSS", {})
    raw_status = data.get("status", "")

    status_css_map = {
        "Very fresh": "blue", "Fresh": "green", "Optimal": "green",
        "Tired": "yellow", "Very tired": "red", "Detraining": "grey",
    }
    status_css = next((v for k, v in status_css_map.items() if k.lower() in raw_status.lower()), "grey")

    return {
        "tp":  sig.get("ftp"),
        "ltp": sig.get("ltp"),
        "hie": sig.get("hie"),
        "pp":  sig.get("pp"),
        "status_label": raw_status,
        "status_css":   status_css,
        "tl_low":   tl.get("low"),
        "tl_high":  tl.get("high"),
        "tl_peak":  tl.get("peak"),
        "tl_total": tl.get("total"),
        "xss_today":       target_xss.get("total"),
        "xss_recommended": target_xss.get("total"),
        "wotd_name":        wotd.get("name"),
        "wotd_description": wotd.get("description"),
        "wotd_type":        wotd.get("type"),
        "wotd_difficulty":  wotd.get("difficulty"),
        "wotd_url":         wotd.get("url"),
        "source": data.get("source"),
    }


# ── Calendar events (planned + completed) ────────────────────────────────────

def get_calendar_events(days_back=7, days_forward=28):
    """
    Fetch all calendar events (activities + planned workouts) from Xert web.
    Returns list of dicts with standardised fields.
    exerciseType == 'Activity' → completed; anything else → planned/forecast
    """
    start = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00.000Z")
    end   = (date.today() + timedelta(days=days_forward)).strftime("%Y-%m-%dT23:59:59.000Z")

    events = _web_get("/calendar/events", {
        "start": start,
        "end":   end,
        "includeDuplicates": "true",
    })

    result = []
    for ev in (events if isinstance(events, list) else []):
        # Local date — start_date_local is stored as local time despite "Z" suffix
        local_dt = ev.get("start_date_local", "")
        date_str = local_dt[:10] if local_dt else ""

        exercise_type = ev.get("exerciseType", "")
        today_str = date.today().isoformat()

        # ALL events have exerciseType="Activity" — use date + matched_activity to distinguish
        # matched_activity="forecast" → completed (real activity matched to a forecast slot)
        # matched_activity=None + future date → planned/forecast (not yet done)
        matched = ev.get("matched_activity")
        if date_str < today_str:
            is_completed = True   # past date = definitely completed
        elif date_str == today_str:
            is_completed = matched is not None  # today: completed only if matched
        else:
            is_completed = False  # future date = planned

        # XSS: actual field is populated for both completed and some planned events.
        # placeholder_xss_details.xss is a fallback for planned events that lack direct xss.
        xss = ev.get("xss") or 0
        ph_xss = (ev.get("placeholder_xss_details") or {}).get("xss") or 0
        if not xss:
            xss = ph_xss  # use placeholder if direct xss is missing

        # Duration: 'duration' field in seconds (timer time)
        dur_sec = ev.get("duration") or 0

        # Distance in km
        dist_km = ev.get("distance") or 0

        # XSS breakdown — from actual fields for completed, placeholder for planned
        ph = ev.get("placeholder_xss_details") or {}
        xss_low  = ev.get("xlss") or ph.get("xlss")
        xss_high = ev.get("xhss") or ph.get("xhss")
        xss_peak = ev.get("xpss") or ph.get("xpss")

        result.append({
            "date":         date_str,
            "name":         ev.get("name", "").strip(),
            "type":         ev.get("type", ""),           # Cycling, Walking, Running
            "exercise_type": exercise_type,               # Activity / Forecast / Workout
            "completed":    is_completed,
            "xss":          round(xss, 1) if xss else 0,
            "xss_low":      round(xss_low, 1) if xss_low is not None else None,
            "xss_high":     round(xss_high, 1) if xss_high is not None else None,
            "xss_peak":     round(xss_peak, 1) if xss_peak is not None else None,
            "distance_km":  round(dist_km, 1) if dist_km else None,
            "duration_sec": int(dur_sec) if dur_sec else None,
            "avg_hr":       ev.get("avg_heart_rate"),
            "max_hr":       ev.get("max_heart_rate"),
            "avg_power":    ev.get("avg_power"),
            "max_power":    ev.get("max_power"),
            "focus":        ev.get("focus") or ev.get("fa"),
            "specificity":  ev.get("spr"),
            "breakthrough": bool(ev.get("br")),
            "path":         ev.get("path"),
        })

    log.info(f"Xert calendar: {len(result)} events "
             f"({sum(1 for e in result if e['completed'])} completed, "
             f"{sum(1 for e in result if not e['completed'])} planned)")
    return result


# ── OAuth activity list (fallback) ────────────────────────────────────────────

def get_recent_activities(days=60, limit=50):
    """
    Returns recent Xert activities via OAuth /oauth/activity endpoint.
    Fallback if web session fails.
    """
    now   = int(time.time())
    since = int((datetime.now() - timedelta(days=days)).timestamp())
    data  = _oauth_get("/activity", {"from": since, "to": now})
    activities = data.get("activities", []) if isinstance(data, dict) else data

    result = []
    for act in activities[:limit]:
        start_raw = act.get("start_date", {})
        start_str = start_raw.get("date", "") if isinstance(start_raw, dict) else str(start_raw)
        date_str  = start_str[:10]
        result.append({
            "name":              act.get("name"),
            "date":              date_str,
            "start_date_local":  date_str,
            "sport_type":        act.get("activity_type"),
            "type":              act.get("activity_type"),
            "xss":               0,
            "distance_km":       None,
            "duration_sec":      None,
            "completed":         True,
        })
    return result


# ── Workouts library ──────────────────────────────────────────────────────────

def get_workouts():
    data = _oauth_get("/workout")
    workouts = data.get("workouts", []) if isinstance(data, dict) else data
    return [{"name": w.get("name"), "path": w.get("path"),
             "description": w.get("description")} for w in workouts]
