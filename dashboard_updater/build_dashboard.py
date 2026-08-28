"""
Fetches live data, renders the Jinja2 template, writes index.html.
Run directly:  python build_dashboard.py
Or via:        scheduler.py  (twice daily)
"""

import json
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
import intervals_client as iv
import xert_client as xr
import strava_client as sc
from config import XERT_EMAIL, STRAVA_CLIENT_ID
from data_builder import build_context
from coaching_note_generator import generate_coaching_note
from planner_builder import build_planner

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

PROJECT_ROOT   = Path(__file__).parent.parent
_EXCLUSIONS_FILE = Path(__file__).parent / 'excluded_activities.json'


def _load_exclusions():
    """Load activity exclusion list from JSON config. Returns (set_of_ids, set_of_dates)."""
    try:
        data = json.loads(_EXCLUSIONS_FILE.read_text())
        return set(str(i) for i in data.get('activity_ids', [])), \
               set(data.get('dates', []))
    except Exception:
        return set(), set()


def _apply_exclusions(activities, excluded_ids, excluded_dates):
    """Remove activities matching excluded IDs or dates from the list."""
    out = []
    for a in activities:
        aid = str(a.get('id') or a.get('activity_id') or '')
        d   = (a.get('date') or '')[:10]
        if aid in excluded_ids or d in excluded_dates:
            log.info(f"  Excluded activity: {a.get('name', '?')} ({d}, id={aid})")
            continue
        out.append(a)
    return out
TEMPLATE_FILE  = 'cycling-dashboard-template.html'
OUTPUT_FILE    = PROJECT_ROOT / 'index.html'


def _fetch():
    data = {'fitness': [], 'wellness': {}, 'activities': [], 'hrv': []}

    log.info('Fetching Intervals.icu data...')
    try:
        data['fitness']    = iv.get_fitness_14w()
        data['wellness']   = iv.get_latest_wellness()
        data['activities'] = iv.get_recent_activities(limit=20)
        data['hrv']        = iv.get_hrv_7d()
        log.info(f"  fitness: {len(data['fitness'])} days | "
                 f"activities: {len(data['activities'])} | "
                 f"hrv: {len(data['hrv'])} days")
    except Exception as e:
        log.error(f'Intervals.icu error: {e}')

    xert_status = None
    data['xert_calendar'] = []
    if XERT_EMAIL:
        log.info('Fetching Xert data...')
        try:
            xert_status = xr.get_athlete_status()
            log.info(f"  Xert TP={xert_status.get('tp')} status={xert_status.get('status_label')}")
        except Exception as e:
            log.warning(f'Xert status error (skipping): {e}')
        try:
            xert_events = xr.get_calendar_events(days_back=14, days_forward=28)
            log.info(f"  Xert calendar: {len(xert_events)} events")
            data['xert_calendar'] = xert_events
        except Exception as e:
            log.warning(f'Xert calendar error (skipping): {e}')
            # Fallback to OAuth activity list
            try:
                xert_acts = xr.get_recent_activities(days=60, limit=50)
                data['xert_calendar'] = xert_acts
            except Exception as e2:
                log.warning(f'Xert activities fallback error: {e2}')
    else:
        log.info('Xert: no credentials configured — skipping')

    data['strava_activities'] = []
    if STRAVA_CLIENT_ID:
        log.info('Fetching Strava data...')
        try:
            strava_acts = sc.get_recent_activities(days=14, limit=7)
            data['strava_activities'] = strava_acts
            log.info(f"  Strava: {len(strava_acts)} activities")
        except Exception as e:
            log.warning(f'Strava error (skipping): {e}')
    else:
        log.info('Strava: no credentials configured — skipping')

    return data, xert_status


def build():
    log.info(f'Build started — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    api_data, xert_status = _fetch()

    # Apply activity exclusion list
    excl_ids, excl_dates = _load_exclusions()
    if excl_ids or excl_dates:
        log.info(f'Exclusion list: {len(excl_ids)} IDs, {len(excl_dates)} dates')
        api_data['activities']        = _apply_exclusions(api_data['activities'],        excl_ids, excl_dates)
        api_data['strava_activities'] = _apply_exclusions(api_data['strava_activities'], excl_ids, excl_dates)
        api_data['xert_calendar']     = _apply_exclusions(api_data['xert_calendar'],     excl_ids, excl_dates)

    # Build training planner — Xert calendar (planned + completed) + Intervals.icu fallback
    log.info('Building training planner...')
    xert_cal = api_data.get('xert_calendar', [])
    _planned_raw = [e for e in xert_cal if not e.get('completed')]
    completed_xert = [e for e in xert_cal if e.get('completed')]

    # Per-date dedup: when a date has both auto-Forecast and explicit Workout events,
    # prefer Workout (Forecast events are auto-generated load targets, not actual sessions).
    from collections import defaultdict
    _pbd: dict = defaultdict(list)
    for e in _planned_raw:
        _pbd[(e.get('date') or '')[:10]].append(e)
    planned = []
    for d_evs in _pbd.values():
        has_workout = any(
            (e.get('exercise_type') or '').lower() not in ('forecast', '')
            for e in d_evs
        )
        for e in d_evs:
            if has_workout and (e.get('exercise_type') or '').lower() == 'forecast':
                continue  # skip auto-Forecast when explicit Workout exists
            planned.append(e)
    log.info(f"  Planned events after Forecast dedup: {len(planned)} "
             f"(was {len(_planned_raw)}, dropped {len(_planned_raw)-len(planned)} Forecast)")
    # Log per-date XSS for verification
    import itertools
    for d, evs in itertools.groupby(sorted(planned, key=lambda e: (e.get('date') or '')[:10]),
                                    key=lambda e: (e.get('date') or '')[:10]):
        _evs = list(evs)
        log.info(f"    planned {d}: {[(ev.get('name','?'), ev.get('exercise_type','?'), ev.get('xss',0)) for ev in _evs]}")

    # Supplement IV activities with Xert completed events not yet synced to IV.
    # Deduplicate by (date, name) AND by XSS similarity — Garmin and Xert often name
    # the same ride differently (e.g. "All The Small Things" vs "Lucy in the Sky").
    iv_keys = {(a.get('date', '')[:10], (a.get('name') or '').strip().lower())
               for a in api_data['activities']}
    # Build per-date XSS index for same-ride detection
    iv_xss_by_date: dict[str, list[float]] = {}
    for a in api_data['activities']:
        d = a.get('date', '')[:10]
        if d:
            iv_xss_by_date.setdefault(d, []).append(float(a.get('xss') or 0))

    extras = []
    for ev in completed_xert:
        ev_date = (ev.get('date') or '')[:10]
        ev_name = (ev.get('name') or 'Activity').strip().lower()
        if not ev_date:
            continue
        if (ev_date, ev_name) in iv_keys:
            continue
        ev_xss = float(ev.get('xss') or 0)
        # Skip if IV already has a same-name activity for this date (handled above).
        # XSS-similarity dedup: only apply when exactly ONE IV activity exists on the date —
        # multiple same-day activities legitimately share similar XSS (e.g. 3 back-to-back
        # Zwift races all scoring ~25 XSS each). Collapsing them loses real activities.
        same_date_xss = iv_xss_by_date.get(ev_date, [])
        if ev_xss > 0 and len(same_date_xss) == 1 and any(
            abs(x - ev_xss) / max(x, ev_xss) < 0.15  # tighter: 15% tolerance, single-activity days only
            for x in same_date_xss if x > 0
        ):
            continue
        extras.append({
            'name':         ev.get('name', 'Activity'),
            'date':         ev_date + 'T00:00:00',
            'xss':          ev_xss,
            'duration_sec': ev.get('duration_sec') or 0,
            'distance_km':  ev.get('distance_km'),
            'sport_type':   ev.get('type', 'Ride'),
            'intensity':    None,
        })
        iv_keys.add((ev_date, ev_name))
        iv_xss_by_date.setdefault(ev_date, []).append(ev_xss)
    if extras:
        combined = api_data['activities'] + extras
        combined.sort(key=lambda a: a.get('date', ''), reverse=True)
        api_data['activities'] = combined[:20]  # keep top 20 newest

    # Use Xert completed events merged with Intervals.icu (for XSS/duration accuracy)
    # Intervals.icu is the activity source of truth; Xert calendar adds planned events
    try:
        planner_ctx = build_planner(
            iv_events=planned,                      # Xert planned/forecast events
            iv_activities=api_data['activities'],   # Intervals.icu completed (has XSS + duration)
            weeks=3,
            strava_activities=api_data.get('strava_activities', []),
            xert_completed=completed_xert,          # Xert completed — fallback for IV sync lag
        )
        log.info(f"  Planner: {len(planner_ctx.get('planner_weeks', []))} weeks")
    except Exception as e:
        log.warning(f'Planner build error: {e}')
        planner_ctx = {'planner_weeks': [], 'active_week_index': 0}

    ctx = build_context(
        iv_fitness        = api_data['fitness'],
        iv_wellness       = api_data['wellness'],
        iv_activities     = api_data['activities'],
        iv_hrv            = api_data['hrv'],
        xert_status       = xert_status,
        xert_calendar     = api_data.get('xert_calendar', []),
        strava_activities = api_data.get('strava_activities', []),
    )

    # Generate coaching note
    log.info('Generating coaching note...')
    cur_fitness = api_data['fitness'][-1] if api_data['fitness'] else {}
    ctl = round(cur_fitness.get('ctl') or 0, 1)
    atl = round(cur_fitness.get('atl') or 0, 1)
    tsb_raw = round(ctl - atl, 1)

    # Get XSS remaining (Xert API returns xss_today)
    xss_remaining = xert_status.get('xss_today') if xert_status else None

    coaching_note = generate_coaching_note(
        ctl=ctl,
        atl=atl,
        tsb_raw=tsb_raw,
        xert_status=xert_status,
        hrv_list=api_data['hrv'],
        activities=ctx['activities'],  # enriched with Xert XSS
        xss_remaining_today=xss_remaining,
        strava_latest=ctx.get('strava_latest'),
        iv_fitness=api_data['fitness'],
        tomorrow_session=planner_ctx.get('tomorrow_session'),
        wellness=api_data['wellness'],
        today_recovery_title=planner_ctx.get('today_recovery_title'),
        today_rec_tier=planner_ctx.get('today_rec_tier'),
        current_phase=planner_ctx.get('current_phase'),
    )

    if coaching_note:
        ctx['coaching_note'] = coaching_note
    else:
        log.warning('Coaching note generation failed; using empty placeholder')
        ctx['coaching_note'] = ''

    # Merge planner context
    ctx.update(planner_ctx)

    env = Environment(
        loader=FileSystemLoader(str(PROJECT_ROOT)),
        autoescape=False,
    )
    tmpl = env.get_template(TEMPLATE_FILE)
    html = tmpl.render(**ctx)

    OUTPUT_FILE.write_text(html, encoding='utf-8')
    log.info(f'Saved → {OUTPUT_FILE}')
    log.info('Build complete.')


if __name__ == '__main__':
    build()
