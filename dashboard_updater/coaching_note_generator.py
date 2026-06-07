"""
Generates coaching notes using Claude API based on live training data.
"""

import logging
from datetime import date, datetime, timedelta

from anthropic import Anthropic

log = logging.getLogger(__name__)

RACE_DATE = date(2026, 6, 28)


def _format_hrv_trend(hrv_list):
    """Extract last 3 days of HRV data and format as a trend string."""
    if not hrv_list:
        return "No HRV data available"

    # Get last 3 readings
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
    Generate a coaching note using Claude API.

    Args:
        ctl: Chronic Training Load (float)
        atl: Acute Training Load (float)
        tsb_raw: Training Stress Balance = CTL - ATL (float)
        xert_status: Dict with Xert data (tp, status_label, status_css, etc.)
        hrv_list: List of dicts with HRV data (each with 'date' and 'hrv')
        activities: List of dicts with activity data
        xss_remaining_today: Float, XSS remaining for today (optional)

    Returns:
        String: The generated coaching note (4 paragraphs, <300 words)
    """

    today = date.today()
    yesterday = today - timedelta(days=1)
    days_to_race = max(0, (RACE_DATE - today).days)

    # Get yesterday's and today's activities
    yesterday_act = _get_activity_by_date(activities, yesterday)
    today_act = _get_activity_by_date(activities, today)

    # Format HRV trend
    hrv_trend = _format_hrv_trend(hrv_list)

    # Xert status
    xert_label = xert_status.get("status_label", "Active") if xert_status else "Not configured"
    xert_tp = xert_status.get("tp", "—") if xert_status else "—"
    xert_color = xert_status.get("status_css", "muted") if xert_status else "muted"

    # Build the prompt for Claude
    prompt = f"""You are a professional cycling coach. Based on the athlete's current training metrics, write a concise 4-paragraph coaching note.

ATHLETE METRICS (Today: {today.strftime("%Y-%m-%d")}):
- CTL (Chronic Training Load): {ctl}
- ATL (Acute Training Load): {atl}
- TSB (Training Stress Balance): {tsb_raw}
- Xert Training Status: {xert_label} (color: {xert_color}, TP: {xert_tp})
- HRV Trend (last 3 days): {hrv_trend}

RECENT ACTIVITIES:
- Yesterday ({yesterday.strftime("%Y-%m-%d")}): {yesterday_act.get('name', 'No activity recorded') if yesterday_act else 'No activity recorded'}{f" ({yesterday_act.get('xss', 0):.0f} XSS, {yesterday_act.get('distance_km', '—')} km)" if yesterday_act else ""}
- Today ({today.strftime("%Y-%m-%d")}): {today_act.get('name', 'No activity recorded') if today_act else 'No activity recorded'}{f" ({today_act.get('xss', 0):.0f} XSS, {today_act.get('distance_km', '—')} km)" if today_act else ""}

RACE COUNTDOWN: {days_to_race} days until race ({RACE_DATE.strftime("%B %d")})
XSS Remaining Today: {xss_remaining_today if xss_remaining_today else "Not available"}

WRITE A COACHING NOTE with these 4 paragraphs:
1. Yesterday's Execution: Comment on yesterday's activity quality, intensity, and how it aligns with the athlete's TSB/recovery state.
2. Current Recovery Status: Assess current CTL, ATL, TSB, HRV status, and what the athlete's body is telling us about readiness.
3. Today's Priority: Prescribe what today should look like (intensity, focus, or rest) based on TSB, HRV, and race countdown.
4. Race Build Context: Situate this moment in the larger race prep—how many weeks out, what phase are we in, what's the strategic focus?

Style guidelines:
- Be specific and data-driven; reference the actual numbers
- Direct and concise; no fluff or over-explanation
- Use active voice; speak as the coach directly
- Keep it under 300 words total
- No section headers; just 4 flowing paragraphs"""

    log.info("Generating coaching note via Claude API...")

    try:
        client = Anthropic()
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=512,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        coaching_note = message.content[0].text
        log.info("Coaching note generated successfully")
        return coaching_note

    except Exception as e:
        log.error(f"Failed to generate coaching note: {e}")
        return None
