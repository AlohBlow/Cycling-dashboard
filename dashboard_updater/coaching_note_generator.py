"""
Generates coaching notes based on live training data (template-based, no API required).
"""

import logging
from datetime import date, datetime, timedelta, timezone

_SGT = timezone(timedelta(hours=8))

def _today_sgt():
    return datetime.now(_SGT).date()

log = logging.getLogger(__name__)

RACE_DATE = date(2026, 6, 28)


def _format_hrv_trend(hrv_list):
    """Extract last 3 days of HRV data and format as a trend string."""
    if not hrv_list:
        return "No HRV data available"

    recent = hrv_list[-3:] if len(hrv_list) >= 3 else hrv_list
    trend_str = " → ".join(str(entry.get("hrv", "—")) for entry in recent)
    return trend_str


def _get_activity_by_date(activities, target_date):
    """Find an activity from the list that occurred on the target date."""
    if not activities:
        return None

    for act in activities:
        act_date_str = act.get("date", "")
        if act_date_str.startswith(target_date.strftime("%Y-%m-%d")):
            return act

    return None


def _assess_tsb(tsb):
    """Assess training readiness based on TSB value."""
    if tsb is None:
        return "maintain current load"
    if tsb < -30:
        return "risk of overtraining — prioritize recovery"
    if tsb < -10:
        return "optimal for intensity work"
    if tsb < 0:
        return "slightly fatigued — moderate effort today"
    if tsb < 15:
        return "fresh — good for tempo or threshold"
    return "very fresh — ready for hard efforts"


def _assess_hrv(hrv_list):
    """Assess recovery status from HRV data."""
    if not hrv_list:
        return "No HRV data available"

    vals = [v['hrv'] for v in hrv_list if v.get('hrv')]
    if not vals:
        return "HRV data incomplete"

    latest = vals[-1]
    avg = sum(vals) / len(vals) if vals else 0

    if latest > avg * 1.1:
        return "elevated — excellent recovery status"
    if latest < avg * 0.9:
        return "suppressed — still recovering"
    return "stable — normal recovery"


def generate_coaching_note(
    ctl,
    atl,
    tsb_raw,
    xert_status,
    hrv_list,
    activities,
    xss_remaining_today=None,
):
    """
    Generate a data-driven coaching note using template logic.

    Args:
        ctl: Chronic Training Load (float)
        atl: Acute Training Load (float)
        tsb_raw: Training Stress Balance = CTL - ATL (float)
        xert_status: Dict with Xert data (may be None if API unavailable)
        hrv_list: List of dicts with HRV data
        activities: List of dicts with activity data
        xss_remaining_today: Float, XSS remaining for today (optional)

    Returns:
        String: The generated coaching note (4 paragraphs, <300 words)
    """

    today = _today_sgt()
    yesterday = today - timedelta(days=1)
    days_to_race = max(0, (RACE_DATE - today).days)

    # Filter to meaningful training activities only (exclude trivial/errands)
    _TRIVIAL = {'shop', 'walk', 'stroll', 'errand', 'commute', 'groceries'}
    def _is_meaningful(act):
        name = (act.get('name') or '').lower()
        xss  = act.get('xss') or 0
        sport = (act.get('sport_type') or act.get('type') or '').lower()
        if any(t in name for t in _TRIVIAL) and xss < 15:
            return False
        if 'walk' in sport and xss < 20:
            return False
        return True

    meaningful = [a for a in activities if _is_meaningful(a)]
    all_acts = meaningful if meaningful else activities  # fallback to all if nothing meaningful

    # Get most recent activities (activities list is newest-first)
    yesterday_act = _get_activity_by_date(all_acts, yesterday)
    today_act = _get_activity_by_date(all_acts, today)
    # Fallback: if no exact date match, use the most recent meaningful activity
    most_recent_act = all_acts[0] if all_acts else None
    most_recent_date = most_recent_act.get('date', '')[:10] if most_recent_act else 'unknown'
    log.info(f"  today_act: {today_act.get('name') if today_act else 'None'} | yesterday_act: {yesterday_act.get('name') if yesterday_act else 'None'} | most_recent: {most_recent_act.get('name') if most_recent_act else 'None'} ({most_recent_date})")

    # Format data
    hrv_trend = _format_hrv_trend(hrv_list)
    hrv_status = _assess_hrv(hrv_list)
    tsb_status = _assess_tsb(tsb_raw)

    # Build note
    paragraphs = []

    # Paragraph 1: Most recent activity execution
    ref_act = today_act or yesterday_act or most_recent_act
    if ref_act:
        act_name = ref_act.get('name', 'Activity')
        xss = ref_act.get('xss') or 0
        dist = ref_act.get('distance_km', '—')
        act_date = ref_act.get('date', '')[:10]
        xss_str = f"{xss:.0f} XSS" if isinstance(xss, (int, float)) else "—"
        dist_str = f"{dist} km" if dist else "—"
        p1 = f"Your most recent logged session — {act_name} ({xss_str}, {dist_str}) on {act_date} — reflects a {atl:.1f} ATL. CTL is at {ctl:.1f}, indicating a solid fitness base built through consistent work."
    else:
        p1 = f"No recent activities logged in Intervals.icu. With CTL at {ctl:.1f} and ATL at {atl:.1f}, your fitness base is solid — make sure your sessions are syncing correctly."

    paragraphs.append(p1)

    # Paragraph 2: Current Recovery Status
    p2 = f"Today's TSB is {tsb_raw:+.1f} ({tsb_status}). HRV trend shows {hrv_status}. Your body needs attention to both training stress (ATL) and fitness base (CTL) — this balance is critical {days_to_race} days from race day."
    paragraphs.append(p2)

    # Paragraph 3: Today's Priority
    if tsb_raw < -20:
        priority = "Focus on quality over quantity. One hard effort if you feel sharp; otherwise, easy/recovery pace."
    elif tsb_raw < 0:
        priority = "Push intensity today if HRV allows. You're in the sweet spot for threshold or VO₂ work."
    else:
        priority = "Build aerobic base with steady effort. Save hard intervals for when TSB is lower."

    xss_note = f" Target {xss_remaining_today:.0f} XSS if available." if xss_remaining_today else ""
    p3 = f"{priority}{xss_note} Listen to your body — fatigue perception matters as much as metrics."

    paragraphs.append(p3)

    # Paragraph 4: Race Build Context
    weeks_out = days_to_race // 7
    if weeks_out > 4:
        phase = "base-building phase — keep pushing fitness"
    elif weeks_out > 2:
        phase = "final build — intensity work is critical"
    else:
        phase = "taper window approaching — quality over volume"

    p4 = f"You're in the {phase}. With {days_to_race} days to June 28, your CTL of {ctl:.1f} and ATL of {atl:.1f} show consistent work. Stay consistent, recover when needed, and trust your preparation."

    paragraphs.append(p4)

    # Combine and verify length
    note = " ".join(paragraphs)
    word_count = len(note.split())

    log.info(f"Generated coaching note ({word_count} words)")
    return note
