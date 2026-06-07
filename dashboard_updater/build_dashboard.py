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

# Add dashboard_updater to path so imports work correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jinja2 import Environment, FileSystemLoader
import intervals_client as iv
import xert_client as xr
from config import XERT_EMAIL
from data_builder import build_context
from coaching_note_generator import generate_coaching_note

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
    if XERT_EMAIL:
        log.info('Fetching Xert data...')
        try:
            xert_status = xr.get_athlete_status()
            log.info(f"  Xert TP={xert_status.get('tp')} status={xert_status.get('status_label')}")
        except Exception as e:
            log.warning(f'Xert error (skipping): {e}')
    else:
        log.info('Xert: no credentials configured — skipping')

    return data, xert_status


def build():
    log.info(f'Build started — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    api_data, xert_status = _fetch()

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
