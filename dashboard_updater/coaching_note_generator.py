"""
Generates coaching notes based on live training data (template-based, no API required).
"""

import logging
from datetime import date, datetime, timedelta

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

    today = date.today()
    yesterday = today - timedelta(days=1)
    days_to_race = max(0, (RACE_DATE - today).days)

    # Get activities
    yesterday_act = _get_activity_by_date(activities, yesterday)
    today_act = _get_activity_by_date(activities, today)

    # Format data
    hrv_trend = _format_hrv_trend(hrv_list)
    hrv_status = _assess_hrv(hrv_list)
    tsb_status = _assess_tsb(tsb_raw)

    # Build note
    paragraphs = []

    # Paragraph 1: Yesterday's Execution
    if yesterday_act:
        act_name = yesterday_act.get('name', 'Activity')
        xss = yesterday_act.get('xss', 0)
        dist = yesterday_act.get('distance_km', '—')
        p1 = f"Yesterday's {act_name} ({xss:.0f} XSS, {dist} km) fits your current {atl:.1f} ATL load. You're accumulating fatigue — CTL sitting at {ctl:.1f} suggests you're building fitness while managing acute stress."
    else:
        p1 = f"You skipped yesterday, which is wise with ATL at {atl:.1f}. Your CTL sits at {ctl:.1f}, so recovery days are valuable in this build phase."

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
