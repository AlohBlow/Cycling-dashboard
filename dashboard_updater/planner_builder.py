"""
Builds the dynamic training planner context from Intervals.icu events API.
Fetches planned workouts, matches with actual activities, highlights today.
"""

import logging
from datetime import date, datetime, timedelta, timezone

_SGT = timezone(timedelta(hours=8))

def _today_sgt():
    return datetime.now(_SGT).date()

log = logging.getLogger(__name__)

_DOW_S = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
_MON_S = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',
          7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}

RACE_DATE = date(2026, 8, 21)

# Phase config: (start_date, end_date_inclusive, label)
# Weeks not matched fall back to a generic label.
PHASE_CONFIG = [
    (date(2026, 6, 29), date(2026, 7,  5), "Recovery Week"),
    (date(2026, 7,  6), date(2026, 7, 12), "Rebuild Week 1"),
    (date(2026, 7, 13), date(2026, 7, 19), "Rebuild Week 2"),
    (date(2026, 7, 20), date(2026, 7, 23), "Durability Block ⚡"),
    (date(2026, 7, 24), date(2026, 7, 28), "Birthday Rest 🎂"),
    (date(2026, 7, 29), date(2026, 8,  4), "Bintan Build"),
    (date(2026, 8,  5), date(2026, 8, 11), "Peak Week"),
    (date(2026, 8, 12), date(2026, 8, 20), "Taper"),
    (date(2026, 8, 21), date(2026, 8, 23), "🏁 Tour de Bintan"),
]

def _phase_label(week_monday: date, week_sunday: date) -> str | None:
    """Return phase name if this week overlaps a configured phase, else None."""
    for start, end, label in PHASE_CONFIG:
        if week_monday <= end and week_sunday >= start:
            return label
    return None


def _xss_badge_class(xss):
    if not xss or xss == 0: return 'xss-rest'
    if xss < 50:  return 'xss-rest'
    if xss < 100: return 'xss-easy'
    if xss < 150: return 'xss-mod'
    return 'xss-mega'


def _recovery_protocol(session_name, xss, is_breakthrough=False, xss_peak=0, awc_pct=None):
    """
    Return (icon, title, blocks, protocol_tier) where blocks is a list of (icon, line) pairs.
    protocol_tier: 'breakthrough' | 'hard' | 'moderate' | 'recovery' | 'rest'
    """
    name_l = (session_name or '').lower()
    is_rest = xss == 0 or any(k in name_l for k in ('rest', 'travel', 'walk'))

    # Breakthrough: Xert BT flag OR AWC discharged >85% OR any meaningful peak XSS
    is_bt_session = (
        is_breakthrough
        or (awc_pct is not None and awc_pct >= 85)
        or (xss_peak is not None and xss_peak > 5)
    )

    if is_rest:
        return '😴', 'Rest Day', [
            ('🧖', 'Steam only — or skip entirely if fatigued'),
            ('💊', 'Magnesium pool 10min if available'),
        ], 'rest'

    if is_bt_session:
        return '🏅', 'BREAKTHROUGH — Full Dry Sauna Protocol', [
            ('🔥', 'Dry sauna 80–90°C · 12 min × 3'),
            ('🌊', '13–14°C pool · 3–5 min between rounds'),
            ('❄️', '4°C cold shock · 30–60 sec legs only · ×3'),
            ('💊', 'Magnesium pool · 10 min extended'),
        ], 'breakthrough'

    if xss >= 150:
        return '🔥', 'Heavy Day — Dry Sauna Protocol', [
            ('🔥', 'Dry sauna 80–90°C · 12 min × 2'),
            ('🌊', '13–14°C pool between rounds'),
            ('❄️', '4°C cold shock · legs only · ×2'),
            ('💊', 'Magnesium pool · 8 min'),
        ], 'hard'

    if xss >= 80:
        return '🔥', 'Moderate Day Protocol', [
            ('🔥', 'Dry sauna 80–90°C · 12 min × 2  OR  Steam 40–45°C · 15 min × 2'),
            ('🌊', '13–14°C pool between rounds'),
            ('❄️', '4°C cold shock · ×1–2'),
            ('💊', 'Magnesium pool · 8 min'),
        ], 'moderate'

    # Recovery / Z2 (XSS < 80)
    return '🧖', 'Recovery — Steam Protocol', [
        ('🧖', 'Steam 40–45°C · 15 min × 2'),
        ('🌊', '13–14°C pool between rounds'),
        ('💊', 'Magnesium pool · 8 min'),
    ], 'recovery'


def _estimate_xss_breakdown(session_name, xss):
    """Estimate low/high/peak XSS split for planned sessions (no Riduck data available)."""
    if not xss:
        return 0, 0, 0
    name_l = (session_name or '').lower()
    # Pure low-intensity: Z1-Z2 only
    if any(k in name_l for k in ('low intensity', 'recovery', 'cruise', 'lit',
                                  'back to blue', 'endurance', 'z2', 'zone 2')):
        low, high, peak = 1.00, 0.00, 0.00
    # Max-intensity: Crazies/Faber/pure race events
    elif any(k in name_l for k in ('crazies', 'faber')):
        low, high, peak = 0.25, 0.40, 0.35
    # SMART structured intervals
    elif 'smart' in name_l:
        low, high, peak = 0.35, 0.40, 0.25
    # CCP / threshold
    elif any(k in name_l for k in ('ccp', 'threshold', 'sweetspot')):
        low, high, peak = 0.40, 0.45, 0.15
    # IRRT / group ride with race efforts — actual data shows ~70-90% low
    elif any(k in name_l for k in ('irrt', 'ir sat', 'ir tue', 'ir thu', 'race effort')):
        low, high, peak = 0.70, 0.20, 0.10
    # Pure race (standalone event)
    elif 'race' in name_l:
        low, high, peak = 0.30, 0.40, 0.30
    elif xss >= 120:
        low, high, peak = 0.35, 0.45, 0.20
    elif xss >= 70:
        low, high, peak = 0.55, 0.38, 0.07
    else:
        low, high, peak = 0.80, 0.18, 0.02
    return round(xss * low), round(xss * high), round(xss * peak)


def _week_range_str(monday):
    """Returns e.g. 'Jun 7–13'"""
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        return f"{_MON_S[monday.month]} {monday.day}–{sunday.day}"
    return f"{_MON_S[monday.month]} {monday.day} – {_MON_S[sunday.month]} {sunday.day}"


def _get_monday(d):
    """Return the Monday of the week containing date d."""
    return d - timedelta(days=d.weekday())


def build_planner(iv_events, iv_activities, weeks=3, strava_activities=None, xert_completed=None):
    """
    Build a list of week dicts for the training planner.

    Args:
        iv_events: List of planned events from Intervals.icu
        iv_activities: List of recent completed activities
        weeks: Number of weeks to show (default 3)
        strava_activities: Optional list of Strava activities with Riduck XSS breakdown
        xert_completed: Xert completed events — used as fallback when IV hasn't synced yet

    Returns:
        dict with:
          - planner_weeks: list of week dicts
          - active_week_index: 0-based index of current week
    """
    today = _today_sgt()

    # Build Strava/Riduck XSS breakdown lookup by date
    strava_by_date = {}
    for act in (strava_activities or []):
        d = act.get('date', '')[:10]
        if d and not strava_by_date.get(d):  # keep first (most recent) per date
            strava_by_date[d] = act

    # Build a lookup of completed activities by date from Intervals.icu
    completed_by_date = {}
    for act in (iv_activities or []):
        act_date = act.get('date', '')[:10]
        if act_date:
            if act_date not in completed_by_date:
                completed_by_date[act_date] = []
            completed_by_date[act_date].append(act)

    # Supplement with Xert completed events for dates IV hasn't synced yet
    for ev in (xert_completed or []):
        ev_date = (ev.get('date') or '')[:10]
        if ev_date and ev_date not in completed_by_date:
            completed_by_date[ev_date] = [{
                'name':         ev.get('name', 'Activity'),
                'date':         ev_date,
                'xss':          ev.get('xss') or 0,
                'duration_sec': ev.get('duration_sec') or 0,
                'distance_km':  ev.get('distance_km'),
                'sport_type':   ev.get('type', 'Ride'),
                '_source':      'xert',
            }]

    # Build a lookup of planned events by date
    events_by_date = {}
    for ev in (iv_events or []):
        ev_date = (ev.get('start_date_local') or ev.get('date') or '')[:10]
        if ev_date:
            if ev_date not in events_by_date:
                events_by_date[ev_date] = []
            events_by_date[ev_date].append(ev)

    # Determine starting Monday (race week is week 0, work backwards)
    race_monday = _get_monday(RACE_DATE)

    # Start from PREVIOUS Monday so last week's completed sessions are visible
    this_monday = _get_monday(today)
    start_monday = this_monday - timedelta(weeks=1)

    # Generate weeks: last week (completed) + this week (active) + next week(s)
    planner_weeks = []
    active_week_index = 1  # This week is the second tab

    for w in range(weeks):
        week_monday = start_monday + timedelta(weeks=w)
        week_sunday = week_monday + timedelta(days=6)
        week_num = (week_monday - _get_monday(RACE_DATE - timedelta(weeks=3))).days // 7 + 1

        # Determine week label
        is_past_week = week_sunday < today
        phase = _phase_label(week_monday, week_sunday)
        if is_past_week:
            week_label = f"Last Week — {_week_range_str(week_monday)}"
        elif phase:
            week_label = f"{phase} — {_week_range_str(week_monday)}"
        else:
            week_label = f"Race Build Week {w + 1} — {_week_range_str(week_monday)}"

        # Build days for this week (Mon–Sun)
        days = []

        for d in range(7):
            day_date = week_monday + timedelta(days=d)
            date_str = day_date.strftime('%Y-%m-%d')
            dow = _DOW_S[d]  # MON, TUE, ... SUN

            # Get planned events for this day
            planned = events_by_date.get(date_str, [])

            # Get completed activities for this day
            completed = completed_by_date.get(date_str, [])

            # Build session name
            if completed:
                # Pick primary activity = highest XSS (most significant session)
                _SKIP = {'shop', 'walk', 'stroll', 'errand', 'commute'}
                def _act_xss(a): return a.get('xss') or 0
                def _is_trivial(a):
                    n = (a.get('name') or '').lower()
                    return any(t in n for t in _SKIP) and _act_xss(a) < 15
                meaningful = [a for a in completed if not _is_trivial(a)]
                display_list = meaningful if meaningful else completed
                # Sort by XSS descending, pick highest
                act = sorted(display_list, key=_act_xss, reverse=True)[0]

                session_name = act.get('name', 'Activity')
                # Use primary XSS when it dominates (≥3x next-highest = Garmin sub-segment detection).
                # Otherwise sum all activities (e.g. separate AM + PM sessions both matter).
                if len(completed) > 1:
                    xss_vals = sorted([_act_xss(a) for a in completed], reverse=True)
                    if xss_vals[1] > 0 and xss_vals[0] / xss_vals[1] >= 3:
                        xss = _act_xss(act)  # primary session only
                    else:
                        xss = sum(_act_xss(a) for a in completed)
                else:
                    xss = _act_xss(act)
                dist = act.get('distance_km')
                dur_sec = act.get('duration_sec') or 0
                dur_h = dur_sec // 3600
                dur_m = (dur_sec % 3600) // 60
                dur_str = f"{dur_h}h {dur_m:02d}m" if dur_h else f"{dur_m}m"
                dist_str = f" · {dist} km" if dist else ""
                # Show count if multiple sessions
                extra = f" +{len(completed)-1} more" if len(completed) > 1 else ""
                time_str = f"{dur_str}{dist_str}{extra}"
                completed_flag = True
                plan_name = planned[0].get('name', '') if planned else ''
            elif planned:
                # Show planned session
                ev = planned[0]
                session_name = ev.get('name') or ev.get('description') or 'Training'
                # XSS from Xert calendar event (already resolved from placeholder_xss_details)
                xss = ev.get('xss') or ev.get('load_target') or ev.get('icu_training_load') or 0
                # Duration: Xert events use duration_sec key
                dur_sec = ev.get('duration_sec') or ev.get('moving_time') or ev.get('duration') or 0
                dist_km = ev.get('distance_km')
                dur_h = dur_sec // 3600
                dur_m = (dur_sec % 3600) // 60
                dur_str = f"{dur_h}h {dur_m:02d}m" if dur_sec else ""
                dist_str = f" · {dist_km} km" if dist_km else ""
                time_str = f"{dur_str}{dist_str}" if dur_sec else "Planned"
                completed_flag = False
                plan_name = session_name
            else:
                # No data — show rest day or placeholder
                session_name = "Rest Day" if day_date < today else "—"
                xss = 0
                time_str = ""
                completed_flag = False
                plan_name = ""

            # Determine CSS class for day card
            day_classes = ['cal-day']
            if day_date == today:
                day_classes.append('today')
            elif day_date < today and completed_flag:
                day_classes.append('completed')
            elif day_date < today and not completed_flag:
                day_classes.append('past')

            # XSS breakdown priority:
            # 1. Xert event's own xlss/xhss/xpss (most authoritative — direct from Xert)
            # 2. Strava/Riduck for completed rides (independent validation)
            # 3. Estimate as last resort
            xss_low = xss_high = xss_peak = 0
            xss_breakdown_estimated = False

            # Try Xert breakdown first (works for both completed and planned)
            # Pick highest-XSS cycling event per date to avoid matching walks/errands
            _CYCLING_TYPES = {'cycling', 'ride', 'virtualride', 'ebikeride'}
            xert_src = None
            if completed_flag:
                candidates = [
                    e for e in (xert_completed or [])
                    if e.get('date', '')[:10] == date_str
                    and (e.get('type') or '').lower() in _CYCLING_TYPES
                    and e.get('xss_low') is not None
                ]
                if candidates:
                    xert_src = sorted(candidates, key=lambda e: e.get('xss') or 0, reverse=True)[0]
            else:
                candidates = [
                    e for e in events_by_date.get(date_str, [])
                    if (e.get('type') or '').lower() in _CYCLING_TYPES
                    and e.get('xss_low') is not None
                ]
                if not candidates:  # fall back to any planned event with breakdown
                    candidates = [e for e in events_by_date.get(date_str, []) if e.get('xss_low') is not None]
                if candidates:
                    xert_src = sorted(candidates, key=lambda e: e.get('xss') or 0, reverse=True)[0]

            _CYCLING = {'cycling', 'ride', 'virtualride', 'ebikeride', 'cycling'}

            hr_derived = False  # True when activity has no power meter data
            is_breakthrough = False
            awc_pct = None

            if xert_src and xert_src.get('xss_low') is not None:
                xss_low  = round(xert_src.get('xss_low') or 0)
                xss_high = round(xert_src.get('xss_high') or 0)
                xss_peak = round(xert_src.get('xss_peak') or 0)
                is_breakthrough = bool(xert_src.get('breakthrough'))
            elif completed_flag:
                # Fall back to Riduck for completed rides
                strava_act = strava_by_date.get(date_str)
                riduck = (strava_act.get('riduck') or {}) if strava_act else {}
                awc_pct = riduck.get('awc_pct') or strava_act.get('awc_pct') if strava_act else None
                rdl = riduck.get('xss_low')
                rdh = riduck.get('xss_high')
                rdp = riduck.get('xss_peak')
                if rdl is not None or rdh is not None or rdp is not None:
                    xss_low  = round(rdl or 0)
                    xss_high = round(rdh or 0)
                    xss_peak = round(rdp or 0)
                else:
                    # No power breakdown available — check if HR-derived
                    # An IV activity with no intensity/power field = HR-only XSS
                    primary_act = completed_by_date.get(date_str, [{}])[0]
                    has_power = bool(primary_act.get('intensity') or primary_act.get('avg_power'))
                    if not has_power:
                        hr_derived = True
                        xss_low, xss_high, xss_peak = (xss or 0), 0, 0
                    else:
                        xss_low, xss_high, xss_peak = _estimate_xss_breakdown(session_name, xss)
                    xss_breakdown_estimated = True
            elif xss:
                xss_low, xss_high, xss_peak = _estimate_xss_breakdown(session_name, xss)
                xss_breakdown_estimated = True

            # Normalize breakdown to always sum exactly to the day's xss.
            # Xert's xlss/xhss/xpss can reference a different total than IV's xss —
            # scaling prevents weekly sums overflowing vs the total.
            if xss:
                breakdown_sum = xss_low + xss_high + xss_peak
                if breakdown_sum > 0 and breakdown_sum != xss:
                    factor = xss / breakdown_sum
                    xss_low  = round(xss_low  * factor)
                    xss_high = round(xss_high * factor)
                    xss_peak = max(0, xss - xss_low - xss_high)

            days.append({
                'date':                   date_str,
                'day_num':                day_date.day,
                'dow':                    dow,
                'session_name':           session_name,
                'plan_name':              plan_name,
                'time_str':               time_str,
                'xss':                    round(xss) if xss else 0,
                'xss_class':              _xss_badge_class(xss),
                'xss_low':                xss_low,
                'xss_high':               xss_high,
                'xss_peak':               xss_peak,
                'xss_breakdown_estimated': xss_breakdown_estimated,
                'hr_derived':             hr_derived,
                'is_breakthrough':        is_breakthrough,
                'awc_pct':               awc_pct,
                'completed':              completed_flag,
                'is_today':               day_date == today,
                'is_past':                day_date < today,
                'day_class':              ' '.join(day_classes),
                # rec_icon/title/rec_blocks assigned in post-pass below
                'rec_icon':   None,
                'rec_title':  None,
                'rec_blocks': [],
            })

        # ── Recovery protocol: max 3 sessions per week, hardest days ─────────
        # Sort non-rest days by XSS descending; assign active recovery to top 3.
        # Rest days always get the rest protocol; other days get no recovery card.
        active_days = sorted(
            [(i, d['xss']) for i, d in enumerate(days) if d['xss'] > 0],
            key=lambda x: x[1], reverse=True
        )
        recovery_indices = {i for i, _ in active_days[:3]}
        for i, d in enumerate(days):
            if d['xss'] == 0:
                d['rec_icon'], d['rec_title'], d['rec_blocks'], d['rec_tier'] = _recovery_protocol('rest', 0)
            elif i in recovery_indices:
                d['rec_icon'], d['rec_title'], d['rec_blocks'], d['rec_tier'] = _recovery_protocol(
                    d['session_name'], d['xss'],
                    is_breakthrough=d.get('is_breakthrough', False),
                    xss_peak=d.get('xss_peak', 0),
                    awc_pct=d.get('awc_pct'),
                )
            else:
                d['rec_tier'] = None
            # else: no recovery card (rec_icon stays None)

        # ── Weekly XSS breakdown totals ───────────────────────────────────────
        # Derive total from components (normalized per-day) so they always sum correctly.
        week_xss_low  = sum(d['xss_low']  for d in days)
        week_xss_high = sum(d['xss_high'] for d in days)
        week_xss_peak = sum(d['xss_peak'] for d in days)
        week_xss_total = week_xss_low + week_xss_high + week_xss_peak
        week_has_hr_derived = any(d.get('hr_derived') for d in days)

        # Week 1 (index 1) = this week = active tab
        is_this_week = (week_monday == this_monday)

        planner_weeks.append({
            'week_id':        f"week{w + 1}",
            'week_label':     week_label,
            'tab_label':      f"{'Last Wk' if w==0 else 'This Wk' if w==1 else 'Next Wk'} · {_week_range_str(week_monday)}",
            'week_xss':           round(week_xss_total),
            'week_xss_low':       round(week_xss_low),
            'week_xss_high':      round(week_xss_high),
            'week_xss_peak':      round(week_xss_peak),
            'week_has_hr_derived': week_has_hr_derived,
            'days':               days,
            'is_active':          is_this_week,
        })

    # Find tomorrow's planned session for Today card
    tomorrow = today + timedelta(days=1)
    tomorrow_str = tomorrow.strftime('%Y-%m-%d')
    tomorrow_plan = events_by_date.get(tomorrow_str, [])
    tomorrow_session = None
    if tomorrow_plan:
        ev = tomorrow_plan[0]
        tomorrow_session = {
            'name':     ev.get('name') or 'Training',
            'xss':      round(ev.get('xss') or 0),
            'distance': ev.get('distance_km'),
            'time_str': '',
        }
        dur = ev.get('duration_sec') or 0
        if dur:
            h, m = dur // 3600, (dur % 3600) // 60
            tomorrow_session['time_str'] = f"{h}h {m:02d}m"

    # Extract today's recovery protocol for coaching note context
    today_recovery_title = None
    today_rec_tier = None
    for week in planner_weeks:
        for d in week['days']:
            if d.get('is_today'):
                today_recovery_title = d.get('rec_title')
                today_rec_tier = d.get('rec_tier')
                break

    return {
        'planner_weeks':        planner_weeks,
        'active_week_index':    active_week_index,
        'tomorrow_session':     tomorrow_session,
        'today_recovery_title': today_recovery_title,
        'today_rec_tier':       today_rec_tier,
    }
