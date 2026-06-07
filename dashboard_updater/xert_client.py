"""
Xert API client.

Auth: Xert uses OAuth2 password-grant tokens.
Base URL: https://www.xertonline.com/oauth/token  (auth)
          https://www.xertonline.com/api/v1       (data)

Key endpoints used:
  GET /athlete           → signature (TP, HIE, PP), training status, XSS today
  GET /workouts?limit=N  → recent workouts
"""

import requests
from config import XERT_EMAIL, XERT_PASSWORD

_AUTH_URL = "https://www.xertonline.com/oauth/token"
_BASE_URL = "https://www.xertonline.com/api/v1"
_CLIENT_ID = "xert_public"           # Xert's public OAuth client
_CLIENT_SECRET = "xert_public"

_token_cache = {}


def _get_token():
    if _token_cache.get("access_token"):
        return _token_cache["access_token"]
    r = requests.post(_AUTH_URL, data={
        "grant_type": "password",
        "username": XERT_EMAIL,
        "password": XERT_PASSWORD,
        "client_id": _CLIENT_ID,
        "client_secret": _CLIENT_SECRET,
    })
    r.raise_for_status()
    _token_cache.update(r.json())
    return _token_cache["access_token"]


def _headers():
    return {"Authorization": f"Bearer {_get_token()}"}


def _get(path, params=None):
    r = requests.get(f"{_BASE_URL}{path}", headers=_headers(), params=params)
    r.raise_for_status()
    return r.json()


# ── Athlete status ────────────────────────────────────────────────────────────

def get_athlete_status():
    """
    Returns current Xert athlete data including:
    - Fitness Signature: tp (threshold power), hie, pp
    - form (training status label + colour)
    - xss_today (XSS accumulated so far today)
    - xss_7d (rolling 7-day XSS total)
    - focus / specificity
    - recommended daily XSS (from Xert's XATA)
    """
    data = _get("/athlete")
    athlete = data.get("athlete", data)   # some API versions nest under "athlete"

    # Training status mapping (Xert colour codes → human labels)
    status_map = {
        "blue":   ("Fresh", "blue"),
        "green":  ("Optimal", "green"),
        "yellow": ("Tired", "yellow"),
        "red":    ("Very Tired", "red"),
        "grey":   ("Transition", "grey"),
    }

    raw_status = athlete.get("status") or athlete.get("trainingStatus") or {}
    status_color = raw_status.get("color") if isinstance(raw_status, dict) else raw_status
    status_label, status_css = status_map.get(status_color, (status_color, "grey"))

    return {
        # Fitness Signature
        "tp": athlete.get("tp"),
        "hie": athlete.get("hie"),
        "pp": athlete.get("pp"),
        # Training Form
        "status_color": status_color,
        "status_label": status_label,
        "status_css": status_css,
        # XSS
        "xss_today": athlete.get("xssToday") or athlete.get("xss_today"),
        "xss_7d": athlete.get("xss7Days") or athlete.get("xss_7days"),
        "xss_recommended": athlete.get("xssRecommended") or athlete.get("recommended_xss"),
        # Focus & Specificity
        "focus": athlete.get("focus"),
        "specificity": athlete.get("specificity") or athlete.get("specificityRating"),
        # Power metrics
        "watts_per_kg": athlete.get("wattsPerKilogram") or athlete.get("watts_per_kg"),
        "lower_tp": athlete.get("lowerTP") or athlete.get("lower_tp"),
    }


# ── Recent workouts ───────────────────────────────────────────────────────────

def get_recent_workouts(limit=5):
    """Returns recent Xert workouts with XSS, focus, duration."""
    data = _get("/workouts", {"limit": limit})
    workouts = data if isinstance(data, list) else data.get("workouts", [])
    result = []
    for w in workouts:
        result.append({
            "name": w.get("name"),
            "date": (w.get("startTime") or "")[:10],
            "xss": w.get("xss"),
            "focus": w.get("focus"),
            "duration_sec": w.get("duration"),
            "status": w.get("status"),   # "breakthrough", "maximal", etc.
        })
    return result
