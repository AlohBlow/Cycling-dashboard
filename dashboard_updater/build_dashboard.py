"""
Fetches live data, renders the Jinja2 template, writes index.html.
Run directly:  python build_dashboard.py
Or via:        scheduler.py  (twice daily)
"""

import logging
import sys
import os
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
import intervals_client as iv
import xert_client as xr
from config import XERT_EMAIL
from data_builder import build_context
from coaching_note_generator import generate_coaching_note
from planner_builder import build_planner

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

PROJECT_ROOT   = Path(__file__).parent.parent
TEMPLATE_FILE  = 'cycling-dashboard-template.html'
OUTPUT_FILE    = PROJECT_ROOT / 'index.html'


def _fetch():
    data = {'fitness': [], 'wellness': {}, 'activities': [], 'hrv': []}

    log.info('Fetching Intervals.icu data...')
    try:
        data['fitness']    = iv.get_fitness_14w()
        data['wellness']   = iv.get_latest_wellness()
        data['activities'] = iv.get_recent_activities(limit=10)
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

    return data, xert_status


def build():
    log.info(f'Build started — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    api_data, xert_status = _fetch()

    # Build training planner — Xert calendar (planned + completed) + Intervals.icu fallback
    log.info('Building training planner...')
    xert_cal = api_data.get('xert_calendar', [])
    planned  = [e for e in xert_cal if not e.get('completed')]
    completed_xert = [e for e in xert_cal if e.get('completed')]
    # Use Xert completed events merged with Intervals.icu (for XSS/duration accuracy)
    # Intervals.icu is the activity source of truth; Xert calendar adds planned events
    try:
        planner_ctx = build_planner(
            iv_events=planned,                     # Xert planned/forecast events
            iv_activities=api_data['activities'],  # Intervals.icu completed (has XSS + duration)
            weeks=3,
        )
        log.info(f"  Planner: {len(planner_ctx.get('planner_weeks', []))} weeks")
    except Exception as e:
        log.warning(f'Planner build error: {e}')
        planner_ctx = {'planner_weeks': [], 'active_week_index': 0}

    ctx = build_context(
        iv_fitness    = api_data['fitness'],
        iv_wellness   = api_data['wellness'],
        iv_activities = api_data['activities'],
        iv_hrv        = api_data['hrv'],
        xert_status   = xert_status,
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
        activities=api_data['activities'],
        xss_remaining_today=xss_remaining,
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
