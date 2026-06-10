"""
Transforms raw API responses into the flat dict that Jinja2 renders into the dashboard.
"""

import json
from datetime import date, datetime, timedelta

_MON = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',
        7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
_MON_LONG = {1:'January',2:'February',3:'March',4:'April',5:'May',6:'June',
             7:'July',8:'August',9:'September',10:'October',11:'November',12:'December'}
_DOW_S = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
_DOW_L = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']


def _dur(secs):
    if not secs: return '—'
    h, rem = divmod(int(secs), 3600)
    m = rem // 60
    return f'{h}h {m:02d}m' if h else f'{m}m'


def _fmt_date(iso):
    """'2026-04-03T06:00' → 'Fri 3 Apr'"""
    if not iso: return ''
    d = datetime.strptime(iso[:10], '%Y-%m-%d')
    return f"{_DOW_S[d.weekday()]} {d.day} {_MON[d.month]}"


def _xss_class(xss):
    x = xss or 0
    if x < 30:  return 'xss-rest'
    if x < 80:  return 'xss-easy'
    if x < 150: return 'xss-mod'
    return 'xss-mega'


def _sport_icon(t):
    return {
        'Ride': '🚴', 'VirtualRide': '🚴', 'EBikeRide': '🚴',
        'Run': '🏃', 'VirtualRun': '🏃',
        'Walk': '🚶',
        'Swim': '🏊',
        'WeightTraining': '🏋️', 'Workout': '🏋️',
    }.get(t or '', '⚡')


def _tsb_info(tsb):
    """Returns (tsb_str, zone_name, css_var_name)"""
    if tsb is None:
        return '—', '—', 'muted'
    v = round(tsb, 1)
    s = f'+{v}' if v >= 0 else str(v)
    if v < -30: return s, 'High Risk',   'red'
    if v < -10: return s, 'Optimal',     'green'
    if v <   0: return s, 'Moderate',    'yellow'
    if v <  15: return s, 'Fresh',       'accent'
    return          s, 'Transition',  'yellow'


def _hrv_info(hrv_list):
    """Returns (today_val, avg_val, status_str, css_color, badge_class, badge_text)"""
    vals = [v['hrv'] for v in hrv_list if v.get('hrv')]
    if not vals:
        return '—', '—', 'No Data', 'muted', 'med', 'No HRV data'
    avg = sum(vals) / len(vals)
    latest = vals[-1]
    avg_r = round(avg, 1)
    if latest > avg * 1.08:
        return latest, avg_r, 'Elevated',   'green',   'good',     'Above 7d Average ↑'
    if latest < avg * 0.88:
        return latest, avg_r, 'Suppressed', 'orange',  'med',      'Below 7d Average ↓'
    return latest, avg_r, 'Balanced',   'accent2', 'balanced', 'In Range ↔'


def build_context(iv_fitness, iv_wellness, iv_activities, iv_hrv, xert_status,
                  xert_calendar=None, strava_activities=None):
    today = date.today()
    race_date = date(2026, 6, 28)
    days_to_race = max(0, (race_date - today).days)

    # ── Fitness (CTL / ATL / TSB) ────────────────────────────────────────────
    cur = iv_fitness[-1] if iv_fitness else {}
    ctl = round(cur.get('ctl') or 0, 1)
    atl = round(cur.get('atl') or 0, 1)
    tsb_raw = round(ctl - atl, 1)
    tsb_str, tsb_zone, tsb_color = _tsb_info(tsb_raw)

    # ── Chart: last 14 data points ───────────────────────────────────────────
    rows14 = iv_fitness[-14:] if len(iv_fitness) >= 14 else iv_fitness
    chart_labels, chart_ctl, chart_atl, chart_tsb = [], [], [], []
    for r in rows14:
        d = datetime.strptime(r['date'], '%Y-%m-%d')
        chart_labels.append(f"{_MON[d.month]} {d.day}")
        c = round(r['ctl'], 1) if r.get('ctl') is not None else None
        a = round(r['atl'], 1) if r.get('atl') is not None else None
        chart_ctl.append(c)
        chart_atl.append(a)
        chart_tsb.append(round((c or 0) - (a or 0), 1))

    # ── Wellness ─────────────────────────────────────────────────────────────
    w = iv_wellness or {}
    sleep_secs = w.get('sleep_secs') or 0
    sh, sm = divmod(int(sleep_secs), 3600)
    sm //= 60
    sleep_str    = f'{sh}h {sm:02d}m' if sleep_secs else '—'
    sleep_score  = w.get('sleep_score')
    sleep_badge  = f"{int(sleep_score)} Sleep Score" if sleep_score else 'Score unavailable'
    resting_hr   = w.get('resting_hr', '—')
    weight       = w.get('weight_kg')
    weight_disp  = f"{weight:.1f}" if weight else '—'

    # eFTP fallback if Xert not configured
    sport_info = (w.get('sport_info') or [{}])[0] if isinstance(w.get('sport_info'), list) else {}
    eftp = round(sport_info.get('eftp') or 0) or None

    # ── HRV ──────────────────────────────────────────────────────────────────
    hrv_today, hrv_avg, hrv_status, hrv_color, hrv_badge_cls, hrv_badge_txt = _hrv_info(iv_hrv)

    # ── Build Xert XSS lookup by date (use Xert as source of truth for XSS) ──
    xert_xss_by_date = {}
    for ev in (xert_calendar or []):
        if not ev.get('completed'):
            continue
        d = ev.get('date', '')[:10]
        xss = ev.get('xss') or 0
        if d and xss:
            # Sum multiple completed events per day
            xert_xss_by_date[d] = xert_xss_by_date.get(d, 0) + xss

    # ── Activities ───────────────────────────────────────────────────────────
    yesterday = today - timedelta(days=1)
    act_rows = []
    for a in iv_activities:
        act_date = a.get('date', '')[:10]
        # Use Xert XSS for this date if available (more accurate than Intervals.icu)
        xert_day_xss = xert_xss_by_date.get(act_date)
        iv_xss = a.get('xss') or 0
        # Only use Xert XSS for cycling activities; walks/runs keep IV value
        sport = (a.get('sport_type') or '').lower()
        is_cycling = 'ride' in sport or sport == 'cycling'
        if xert_day_xss and is_cycling:
            xss_v = round(xert_day_xss)
        else:
            xss_v = round(iv_xss) if iv_xss else 0
        act_rows.append({
            'icon':          _sport_icon(a.get('sport_type')),
            'name':          a.get('name') or 'Activity',
            'date':          a.get('date', ''),
            'date_str':      _fmt_date(a.get('date', '')),
            'sport_type':    a.get('sport_type', ''),
            'duration_str':  _dur(a.get('duration_sec')),
            'distance_km':   a.get('distance_km'),
            'distance_str':  f"{a.get('distance_km')} km" if a.get('distance_km') else '—',
            'xss':           xss_v,
            'xss_class':     _xss_class(xss_v),
            'row_class':     '',
            'is_today':      act_date == today.isoformat(),
            'is_yesterday':  act_date == yesterday.isoformat(),
        })

    # ── Xert ─────────────────────────────────────────────────────────────────
    xs = xert_status or {}
    xtp_raw  = xs.get('tp')
    xtp  = round(xtp_raw) if isinstance(xtp_raw, (int, float)) else (eftp or '—')
    xhie_raw = xs.get('hie')
    # API returns HIE already in kJ
    xhie = round(xhie_raw, 1) if isinstance(xhie_raw, (int, float)) else '—'
    xpp_raw = xs.get('pp')
    xpp  = round(xpp_raw) if isinstance(xpp_raw, (int, float)) else '—'
    xsl  = xs.get('status_label') or ('Active' if xs else 'Not configured')
    xsc  = xs.get('status_css')   or 'muted'
    # WOTD
    xwotd_name = xs.get('wotd_name')
    xwotd_desc = xs.get('wotd_description') or ''
    xwotd_type = xs.get('wotd_type') or ''
    xtarget_xss = xs.get('xss_today')

    # ── Generated dates ───────────────────────────────────────────────────────
    dow = today.weekday()
    gen_short = f"{_DOW_S[dow]} {today.day} {_MON[today.month]} {today.year}"
    gen_long  = f"{_DOW_L[dow]} {today.day} {_MON_LONG[today.month]} {today.year}"
    tmrw = today + timedelta(days=1)
    next_rpt  = f"{_DOW_L[tmrw.weekday()]} {tmrw.day} {_MON_LONG[tmrw.month]} {tmrw.year}"
    tomorrow_short = f"{_DOW_S[tmrw.weekday()].upper()} {tmrw.day} {_MON[tmrw.month].upper()}"

    return {
        # Meta
        'generated_date_short': gen_short,
        'generated_date_long':  gen_long,
        'next_report_date':     next_rpt,
        'tomorrow_date_short':  tomorrow_short,

        # Countdown
        'days_to_nationals': days_to_race,

        # Form & Load
        'ctl':       ctl,
        'atl':       atl,
        'tsb_str':   tsb_str,
        'tsb_zone':  tsb_zone,
        'tsb_color': tsb_color,

        # Chart (JSON-safe for inline JS)
        'chart_labels_json': json.dumps(chart_labels),
        'chart_ctl_json':    json.dumps(chart_ctl),
        'chart_atl_json':    json.dumps(chart_atl),
        'chart_tsb_json':    json.dumps(chart_tsb),

        # Wellness
        'weight_display': weight_disp,
        'resting_hr':     resting_hr,
        'sleep_duration': sleep_str,
        'sleep_badge':    sleep_badge,

        # HRV
        'hrv_today':     hrv_today,
        'hrv_7d_avg':    hrv_avg,
        'hrv_status':    hrv_status,
        'hrv_color':     hrv_color,
        'hrv_badge_cls': hrv_badge_cls,
        'hrv_badge_txt': hrv_badge_txt,

        # Xert
        'xert_tp':           xtp,
        'xert_hie':          xhie,
        'xert_pp':           xpp,
        'xert_status_label': xsl,
        'xert_status_color': xsc,
        'xert_wotd_name':    xwotd_name,
        'xert_wotd_desc':    xwotd_desc,
        'xert_wotd_type':    xwotd_type,
        'xert_target_xss':   xtarget_xss,

        # Activities (list of dicts)
        'activities': act_rows,
    }
