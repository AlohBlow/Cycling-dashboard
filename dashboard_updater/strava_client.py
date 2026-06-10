"""
Strava API client — OAuth2 refresh-token flow.
Fetches recent cycling activities and parses Riduck AI summaries
embedded in activity descriptions for power zones, anaerobic work,
peak power, and recovery metrics.
"""

import re
import requests
import logging
import time
from datetime import date, timedelta
from config import STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN

log = logging.getLogger(__name__)

_AUTH_URL    = "https://www.strava.com/oauth/token"
_BASE_URL    = "https://www.strava.com/api/v3"
_token_cache = {}


# ── OAuth ─────────────────────────────────────────────────────────────────────

def _get_access_token():
    if _token_cache.get("access_token"):
        return _token_cache["access_token"]
    r = requests.post(_AUTH_URL, data={
        "client_id":     STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "refresh_token": STRAVA_REFRESH_TOKEN,
        "grant_type":    "refresh_token",
    }, timeout=15)
    r.raise_for_status()
    data = r.json()
    _token_cache["access_token"] = data["access_token"]
    log.info(f"Strava token refreshed, expires {data.get('expires_at')}")
    return data["access_token"]


def _get(path, params=None):
    headers = {"Authorization": f"Bearer {_get_access_token()}"}
    r = requests.get(f"{_BASE_URL}{path}", headers=headers, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


# ── Riduck description parser ─────────────────────────────────────────────────

def _parse_riduck(desc):
    """
    Parse Riduck AI summary from Strava activity description.
    Returns dict with power zones, peak power, anaerobic metrics, recovery time.
    """
    if not desc or ("Riduck" not in desc and "ⓧⓔⓡⓣ" not in desc):
        return None

    out = {}

    # XSS totals: ✅ 131𝗑𝗌𝗌  🔵 116  🟡 11.3  🔴 3.5
    m = re.search(r'[✅❎]\s*([\d.]+)𝗑𝗌𝗌\s+🔵\s*([\d.]+)\s+🟡\s*([\d.]+)\s+🔴\s*([\d.]+)', desc)
    if m:
        out['xss_total'] = float(m.group(1))
        out['xss_low']   = float(m.group(2))
        out['xss_high']  = float(m.group(3))
        out['xss_peak']  = float(m.group(4))

    # Recovery time: ✨ Recovery time 37 hour
    m = re.search(r'Recovery time\s+(\d+)\s+hour', desc)
    if m:
        out['recovery_hours'] = int(m.group(1))

    # Peak power durations
    peak = {}
    for dur, key in [('15sec', 'p15s'), ('1min', 'p1m'), ('5min', 'p5m'),
                     ('10min', 'p10m'), ('20min', 'p20m'), ('40min', 'p40m'), ('1hour', 'p1h')]:
        m = re.search(rf'⚡\s*{dur}\s+(\d+)w\s+\((\d+)%\)', desc)
        if m:
            peak[key] = {'watts': int(m.group(1)), 'pct': int(m.group(2))}
    if peak:
        out['peak_power'] = peak

    # Power zones: ⚪ 1zone 28% (+9%)
    pz = {}
    for z in range(1, 8):
        m = re.search(rf'{z}zone\s+(\d+)%', desc)
        if m:
            pz[f'z{z}'] = int(m.group(1))
    if pz:
        out['power_zones'] = pz

    # HR zones — search only within HR zone section
    hz = {}
    hr_section = desc[desc.find('Heartrate zone'):] if 'Heartrate zone' in desc else ''
    for z in range(1, 6):
        m = re.search(rf'{z}zone\s+(\d+)%', hr_section)
        if m:
            hz[f'z{z}'] = int(m.group(1))
    if hz:
        out['hr_zones'] = hz

    # Anaerobic
    m = re.search(r'Matches\s+([\d.]+)', desc)
    if m:
        out['matches'] = float(m.group(1))
    m = re.search(r'AWC energy\s+([\d.]+)kJ', desc)
    if m:
        out['awc_energy_kj'] = float(m.group(1))
    m = re.search(r'Maximum discharge\s+([\d.]+)%', desc)
    if m:
        out['awc_discharge_pct'] = float(m.group(1))

    # Energy metabolism
    m = re.search(r'Fat\s+([\d.]+)%', desc)
    if m:
        out['fat_pct'] = float(m.group(1))
    m = re.search(r'Carb\s+([\d.]+)%', desc)
    if m:
        out['carb_pct'] = float(m.group(1))

    # Riduck training status
    m = re.search(r'Fitness\s+(\d+),\s*Fatigue\s+(\d+),\s*Balance\s+(-?\d+)', desc)
    if m:
        out['riduck_fitness'] = int(m.group(1))
        out['riduck_fatigue'] = int(m.group(2))
        out['riduck_balance'] = int(m.group(3))

    return out if out else None


# ── Public API ────────────────────────────────────────────────────────────────

_CYCLING_TYPES = {'Ride', 'VirtualRide', 'GravelRide', 'MountainBikeRide', 'EBikeRide'}
_SKIP_NAMES    = {'shop', 'walk', 'stroll', 'errand', 'commute'}


def get_recent_activities(days=14, limit=10):
    """
    Fetch recent cycling activities from Strava, parse Riduck summaries.
    Returns list of enriched activity dicts.
    """
    after_date = date.today() - timedelta(days=days)
    after = int(time.mktime(after_date.timetuple()))

    activities = _get("/athlete/activities", {
        "after":    after,
        "per_page": limit * 3,
    })

    result = []
    for act in activities:
        sport = act.get('sport_type') or act.get('type', '')
        name  = (act.get('name') or '').lower()

        if sport not in _CYCLING_TYPES:
            continue
        if any(k in name for k in _SKIP_NAMES) and act.get('moving_time', 0) < 1800:
            continue

        # Fetch full detail for description (list endpoint omits it)
        try:
            detail = _get(f"/activities/{act['id']}")
            desc = detail.get('description') or ''
        except Exception:
            desc = ''

        riduck = _parse_riduck(desc)

        dur_sec = act.get('moving_time') or 0
        h, m    = dur_sec // 3600, (dur_sec % 3600) // 60
        dur_str = f"{h}h {m:02d}m" if h else f"{m}m"
        dist_km = round((act.get('distance') or 0) / 1000, 1)

        entry = {
            'id':           str(act.get('id')),
            'name':         act.get('name'),
            'date':         (act.get('start_date_local') or '')[:10],
            'sport_type':   sport,
            'duration_sec': dur_sec,
            'duration_str': dur_str,
            'distance_km':  dist_km,
            'elevation_m':  round(act.get('total_elevation_gain') or 0),
            'avg_hr':       act.get('average_heartrate'),
            'max_hr':       act.get('max_heartrate'),
            'avg_watts':    act.get('average_watts'),
            'calories':     act.get('calories'),
            'relative_effort': act.get('suffer_score'),
            'kudos':        act.get('kudos_count', 0),
            'pr_count':     act.get('pr_count', 0),
            'riduck':       riduck,
        }

        if riduck:
            entry['xss']           = riduck.get('xss_total')
            entry['xss_low']       = riduck.get('xss_low')
            entry['xss_high']      = riduck.get('xss_high')
            entry['xss_peak']      = riduck.get('xss_peak')
            entry['matches']       = riduck.get('matches')
            entry['awc_energy_kj'] = riduck.get('awc_energy_kj')
            entry['awc_pct']       = riduck.get('awc_discharge_pct')
            entry['recovery_hrs']  = riduck.get('recovery_hours')
            entry['p5m_watts']     = (riduck.get('peak_power') or {}).get('p5m', {}).get('watts')
            entry['p20m_watts']    = (riduck.get('peak_power') or {}).get('p20m', {}).get('watts')
            entry['p20m_pct']      = (riduck.get('peak_power') or {}).get('p20m', {}).get('pct')
            entry['fat_pct']       = riduck.get('fat_pct')
            entry['carb_pct']      = riduck.get('carb_pct')
            entry['power_zones']   = riduck.get('power_zones')
            entry['hr_zones']      = riduck.get('hr_zones')

        result.append(entry)
        if len(result) >= limit:
            break

    log.info(f"Strava: {len(result)} cycling activities fetched")
    return result
