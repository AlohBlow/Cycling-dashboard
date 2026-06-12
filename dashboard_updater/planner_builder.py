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

RACE_DATE = date(2026, 6, 28)


def _xss_badge_class(xss):
    if not xss or xss == 0: return 'xss-rest'
    if xss < 50:  return 'xss-rest'
    if xss < 100: return 'xss-easy'
    if xss < 150: return 'xss-mod'
    return 'xss-mega'


def _recovery_protocol(session_name, xss):
    """Return (icon_text, title, detail) for per-day recovery based on session intensity."""
    name_l = (session_name or '').lower()
    is_high = xss >= 100 or any(k in name_l for k in ('irrt', 'race', 'ccp', 'faber', 'crazies'))
    is_rest  = xss == 0 or any(k in name_l for k in ('rest', 'travel', 'walk'))
    if is_rest:
        return '😴', 'Full rest', 'Light stretching only'
    elif is_high:
        return '🔥', 'Dry 80–90°C', '4°C shock · 1–2 min'
    else:
        return '🧖', 'Steam 40–45°C', '14°C standard'


def _week_range_str(monday):
    """Returns e.g. 'Jun 7–13'"""
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        return f"{_MON_S[monday.month]} {monday.day}–{sunday.day}"
    return f"{_MON_S[monday.month]} {monday.day} – {_MON_S[sunday.month]} {sunday.day}"


def _get_monday(d):
    """Return the Monday of the week containing date d."""
    return d - timedelta(days=d.weekday())


def build_planner(iv_events, iv_activities, weeks=3, strava_activities=None):
    """
    Build a list of week dicts for the training planner.

    Args:
        iv_events: List of planned events from Intervals.icu
        iv_activities: List of recent completed activities
        weeks: Number of weeks to show (default 3)
        strava_activities: Optional list of Strava activities with Riduck XSS breakdown

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

    # Build a lookup of completed activities by date
    completed_by_date = {}
    for act in (iv_activities or []):
        act_date = act.get('date', '')[:10]
        if act_date:
            if act_date not in completed_by_date:
                completed_by_date[act_date] = []
            completed_by_date[act_date].append(act)

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
        days_to_race = (RACE_DATE - week_monday).days
        is_past_week = week_sunday < today
        if is_past_week:
            week_label = f"Last Week — {_week_range_str(week_monday)}"
        elif days_to_race <= 7:
            week_label = f"Race Week — {_week_range_str(week_monday)}"
        elif days_to_race <= 14:
            week_label = f"Taper Week — {_week_range_str(week_monday)}"
        else:
            week_label = f"Race Build Week {w + 1} — {_week_range_str(week_monday)}"

        # Build days for this week (Mon–Sun)
        days = []
        week_xss_total = 0

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
                # Sum XSS from ALL activities this day
                xss = sum(_act_xss(a) for a in completed)
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

            week_xss_total += xss or 0

            # Determine CSS class for day card
            day_classes = ['cal-day']
            if day_date == today:
                day_classes.append('today')
            elif day_date < today and completed_flag:
                day_classes.append('completed')
            elif day_date < today and not completed_flag:
                day_classes.append('past')

            # XSS breakdown from Strava/Riduck (completed sessions only)
            strava_act = strava_by_date.get(date_str) if completed_flag else None
            riduck = (strava_act.get('riduck') or {}) if strava_act else {}
            xss_low  = round(riduck.get('xss_low')  or 0)
            xss_high = round(riduck.get('xss_high') or 0)
            xss_peak = round(riduck.get('xss_peak') or 0)

            days.append({
                'date':           date_str,
                'day_num':        day_date.day,
                'dow':            dow,
                'session_name':   session_name,
                'plan_name':      plan_name,
                'time_str':       time_str,
                'xss':            round(xss) if xss else 0,
                'xss_class':      _xss_badge_class(xss),
                'xss_low':        xss_low,
                'xss_high':       xss_high,
                'xss_peak':       xss_peak,
                'completed':      completed_flag,
                'is_today':       day_date == today,
                'is_past':        day_date < today,
                'day_class':      ' '.join(day_classes),
                # rec_icon/title/detail assigned in post-pass below
                'rec_icon':       None,
                'rec_title':      None,
                'rec_detail':     None,
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
                d['rec_icon'], d['rec_title'], d['rec_detail'] = '😴', 'Full rest', 'Light stretching only'
            elif i in recovery_indices:
                d['rec_icon'], d['rec_title'], d['rec_detail'] = _recovery_protocol(d['session_name'], d['xss'])
            else:
                d['rec_icon'], d['rec_title'], d['rec_detail'] = None, None, None

        # Week 1 (index 1) = this week = active tab
        is_this_week = (week_monday == this_monday)

        planner_weeks.append({
            'week_id':      f"week{w + 1}",
            'week_label':   week_label,
            'tab_label':    f"{'Last Wk' if w==0 else 'This Wk' if w==1 else 'Next Wk'} · {_week_range_str(week_monday)}",
            'week_xss':     round(week_xss_total),
            'days':         days,
            'is_active':    is_this_week,
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

    return {
        'planner_weeks':     planner_weeks,
        'active_week_index': active_week_index,
        'tomorrow_session':  tomorrow_session,
    }
