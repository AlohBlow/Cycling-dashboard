"""
Generates coaching notes using the Claude API, with template fallback.
"""

import logging
import os
import anthropic
from datetime import date, datetime, timedelta, timezone

_SGT = timezone(timedelta(hours=8))

def _today_sgt():
    return datetime.now(_SGT).date()

log = logging.getLogger(__name__)

RACE_DATE = date(2026, 8, 21)   # Tour de Bintan Stage 1 (primary target Stage 3 = Aug 23)


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



def _generate_via_claude(api_key, ctl, atl, tsb_raw, xert_status, hrv_list, activities,
                         xss_remaining_today, strava_latest, today, days_to_race,
                         iv_fitness=None, tomorrow_session=None, wellness=None,
                         today_recovery_title=None, today_rec_tier=None, current_phase=None):
    """Build a structured 5-block prompt and call Claude Haiku for a personalised coaching note."""
    from math import exp

    xs = xert_status or {}
    w  = wellness or {}

    # ── Most recent meaningful activity ──────────────────────────────────────
    _TRIVIAL = {'shop', 'walk', 'stroll', 'errand', 'commute', 'groceries'}
    def _meaningful(act):
        name  = (act.get('name') or '').lower()
        xss   = act.get('xss') or 0
        sport = (act.get('sport_type') or '').lower()
        if any(t in name for t in _TRIVIAL) and xss < 15: return False
        if 'walk' in sport and xss < 20: return False
        return True
    meaningful = [a for a in activities if _meaningful(a)]
    recent = (meaningful or activities or [None])[0]

    # ── HRV ──────────────────────────────────────────────────────────────────
    hrv_vals = [v.get('hrv') for v in (hrv_list or []) if v.get('hrv')]
    hrv_trend = ' → '.join(str(v) for v in hrv_vals[-3:]) if hrv_vals else 'no data'
    hrv_latest = hrv_vals[-1] if hrv_vals else None
    hrv_avg = round(sum(hrv_vals) / len(hrv_vals), 1) if hrv_vals else None
    if hrv_latest and hrv_avg:
        hrv_pct = round((hrv_latest - hrv_avg) / hrv_avg * 100)
        hrv_signal = ('elevated' if hrv_pct > 8 else 'suppressed' if hrv_pct < -8 else 'balanced')
    else:
        hrv_pct = None
        hrv_signal = 'unknown'

    # ── CTL trend (2 weeks ago) ───────────────────────────────────────────────
    ctl_2w_ago = None
    if iv_fitness and len(iv_fitness) >= 14:
        entry = iv_fitness[-14]
        ctl_2w_ago = round(entry.get('ctl') or 0, 1)
    ctl_trend = (f"up from {ctl_2w_ago} two weeks ago" if ctl_2w_ago and ctl > ctl_2w_ago
                 else f"down from {ctl_2w_ago} two weeks ago" if ctl_2w_ago and ctl < ctl_2w_ago
                 else "flat over two weeks")

    # ── Projected race day TSB (assuming standard taper) ─────────────────────
    proj_ctl = round(ctl * exp(-days_to_race / 42), 1)
    proj_atl = round(atl * exp(-days_to_race / 7), 1)
    proj_tsb_rest = round(proj_ctl - proj_atl, 0)
    # Blend: taper means some load continues, so result is between rest and now
    proj_tsb_taper = round(proj_tsb_rest * 0.7 + tsb_raw * 0.3 + 3, 0)
    projected_tsb_range = f"+{int(proj_tsb_taper - 2)} to +{int(proj_tsb_taper + 5)}"

    # ── Strava Riduck: last session details ──────────────────────────────────
    sl = strava_latest if (strava_latest and strava_latest.get('has_riduck')) else {}
    p15s = None
    # Scan all recent activities for best 15-sec power this block
    # (strava_latest only has the most recent — best proxy available)
    if sl:
        # Not stored at top level but available in raw riduck if passed separately
        pass

    # ── Build structured prompt ───────────────────────────────────────────────
    lines = [
        f"You are a data-driven cycling coach writing a daily coaching note for James Loh.",
        f"James is a competitive cyclist preparing for Tour de Bintan 2026 (3-stage race, Aug 21-23).",
        f"Stage 1: 15km ITT Thu Aug 21 · Stage 2: 140km rolling Fri Aug 22 · Stage 3: 110km hilly Sat Aug 23 (PRIMARY TARGET — attack and win).",
        f"Today: {today.strftime('%A %d %B %Y')}  |  Days to Stage 1: {days_to_race}  |  Days to Stage 3 (primary): {days_to_race + 2}",
        f"",
        f"=== TRAINING DATA ===",
        f"",
        f"CTL (fitness base): {ctl}  [{ctl_trend}]",
        f"ATL (fatigue): {atl}",
        f"TSB (form): {tsb_raw:+.1f}",
        f"Projected race-day TSB (if taper executes): {projected_tsb_range}",
    ]

    if hrv_latest:
        lines += [
            f"",
            f"HRV today: {hrv_latest}ms  |  7-day avg: {hrv_avg}ms  |  Signal: {hrv_signal} ({hrv_pct:+d}% vs avg)",
            f"HRV trend (3 days): {hrv_trend}",
        ]

    tr = w.get('training_readiness')
    if tr is not None:
        lines.append(f"Garmin Training Readiness: {tr}/100")

    if xs:
        xtp = xs.get('tp')
        xltp = xs.get('ltp')
        xhie = xs.get('hie')
        xpp  = xs.get('pp')
        lines += [
            f"",
            f"Xert TP (threshold power): {round(xtp) if xtp else '—'}W  LTP: {round(xltp) if xltp else '—'}W",
            f"Xert HIE: {round(xhie, 1) if xhie else '—'}kJ  PP: {round(xpp) if xpp else '—'}W",
            f"Xert training status: {xs.get('status_label', '—')}",
        ]
        if xs.get('wotd_name'):
            lines.append(f"Xert WOTD: {xs['wotd_name']} — {xs.get('wotd_description', '')[:120]}")
        if xss_remaining_today:
            lines.append(f"XSS target remaining today: {xss_remaining_today:.0f}")

    # Determine whether the most recent activity is today's completed session
    today_completed = recent and recent.get('date', '')[:10] == today.isoformat()

    if recent:
        rdate = recent.get('date', '')[:10]
        rname = recent.get('name', 'Activity')
        rxss  = recent.get('xss') or '—'
        rdist = recent.get('distance_km') or '—'
        rdur  = recent.get('duration_str') or '—'
        session_label = f"TODAY COMPLETED ✅ ({rdate})" if today_completed else f"MOST RECENT SESSION ({rdate})"
        lines += [
            f"",
            f"{session_label}: {rname}",
            f"  XSS: {rxss}  Distance: {rdist} km  Duration: {rdur}",
        ]

    if sl:
        riduck_label = "RIDUCK ANALYSIS — today's completed ride" if today_completed else "RIDUCK ANALYSIS (most recent ride)"
        lines += [
            f"",
            f"{riduck_label}:",
            f"  Energy: Fat {sl.get('fat_pct') or '—'}%  Carb {sl.get('carb_pct') or '—'}%",
            f"  Recovery needed: {sl.get('recovery_hrs') or '—'}h",
        ]
        if sl.get('awc_pct') is not None:
            lines.append(f"  AWC discharge: {sl['awc_pct']}%  Anaerobic matches: {sl.get('matches') or '—'}")
        if sl.get('p20m_watts'):
            xtp_val = xs.get('tp') or 1
            p20_pct = sl['p20m_watts'] / xtp_val * 100 if xtp_val else 0
            lines.append(f"  20-min peak power: {sl['p20m_watts']}W ({round(p20_pct)}% of TP)")
        pz = sl.get('power_zones') or []
        if pz:
            pz_str = '  '.join(f"{z['zone']}:{z['pct']}%" for z in pz)
            lines.append(f"  Power zones: {pz_str}")
        if sl.get('p5m_watts'):
            lines.append(f"  5-min peak power: {sl['p5m_watts']}W")

    hydration = w.get('hydration_ml')
    hydration_target = w.get('hydration_target_ml')
    if hydration and hydration_target:
        lines += [
            f"",
            f"WELLNESS:",
            f"  Hydration: {hydration}ml logged vs {hydration_target}ml target",
        ]
    elif hydration:
        lines += [f"", f"WELLNESS:", f"  Hydration: {hydration}ml logged"]

    if tomorrow_session:
        ts = tomorrow_session
        lines += [
            f"",
            f"TOMORROW'S PLANNED SESSION: {ts.get('name', '—')}",
            f"  Target XSS: {ts.get('xss', '—')}  Duration: {ts.get('time_str', '—')}",
        ]

    # ── Instructions ─────────────────────────────────────────────────────────
    # Protocol parameters — absolute, never to be substituted by Claude's defaults
    _protocol_params = (
        "RECOVERY PROTOCOL — MANDATORY SEQUENCE AND PARAMETERS:\n"
        "  Step 1: Dry sauna 80–90°C × N rounds (NEVER describe this as 40°C — 40°C is a steam room, not a sauna)\n"
        "  Step 2: 13–14°C pool 3–5 min BETWEEN each sauna round (inter-round cool-down only)\n"
        "  Step 3: 4°C cold shock 30–60 sec legs only — AFTER the FINAL round only, never between rounds\n"
        "  Step 4: Magnesium pool at end\n"
        "RULES: Never place 4°C cold shock before 13–14°C pool. "
        "Never describe sauna temperature as 40°C. "
        "4°C ≠ 13°C. 30 sec ≠ 3 min. Steam room ≠ dry sauna."
    )
    _rec_line = (
        f"MANDATORY: The dashboard has prescribed '{today_recovery_title}' for tonight. "
        f"You MUST reference this protocol by name and include sauna/cold-plunge steps if it calls for them. "
        f"Do NOT say 'skip sauna', 'no sauna', or 'save heat stress'. "
        f"{_protocol_params}"
    ) if today_recovery_title else _protocol_params

    block3_instruction = (
        f"Block 3 — TODAY'S STATUS & EVENING PROTOCOL\n"
        f"Today's ride is ALREADY COMPLETED (see TODAY COMPLETED above) — do NOT prescribe another ride.\n"
        f"Comment briefly on how the completed session went (XSS, effort level, power zones).\n"
        f"Prescribe tonight's recovery: nutrition, hydration, sleep target, and the sauna/cold-plunge protocol below.\n"
        f"{_rec_line}\n"
        f"If hydration is low, flag it urgently."
    ) if today_completed else (
        f"Block 3 — TODAY'S PRESCRIPTION\n"
        f"Give specific, actionable targets: power ceiling, HR ceiling, cadence, XSS target.\n"
        f"If recovery day: strict ceilings. If hard day: peak targets from Xert TP + WOTD.\n"
        f"Add a stop condition (e.g. 'abort if HR exceeds Xbpm for more than 90s').\n"
        f"{_rec_line}\n"
        f"If hydration is low, add an urgent hydration note."
    )

    lines += [
        f"",
        f"=== COACHING NOTE INSTRUCTIONS ===",
        f"",
        f"Write exactly 5 labelled blocks. Each block is short — max 4 sentences. Total note under 350 words.",
        f"Use specific numbers from the data above. No generic advice. No fluff.",
        f"",
        f"Block 1 — STATUS SYNTHESIS",
        f"Combine HRV signal, TSB, and CTL trend into one clear sentence about readiness.",
        f"If HRV suppressed but TSB fresh → explain the conflict and which to trust.",
        f"State CTL trend and days to race.",
        f"",
        f"Block 2 — SESSION INSIGHT",
        f"Comment on the most recent ride's power zones, AWC use, and recovery hours.",
        f"Compare 20-min power to TP percentage. Flag anything unusual.",
        f"Note Xert training status and breakthrough proximity.",
        f"",
        block3_instruction,
        f"",
        f"Block 4 — TOMORROW PREVIEW",
        f"State when today's recovery hours clear (last session start + recovery_hrs).",
        f"Give power/HR ceiling if easy day, or pre-depletion strategy if hard day.",
        f"State trade-off: any extra effort today directly debits tomorrow's session quality.",
        f"",
        f"Block 5 — RACE TRAJECTORY",
        f"One-line traffic light: 🟢 On track / 🟡 Monitor / 🔴 Flag.",
        f"State CTL trend, projected race-day TSB, and the #1 priority for this week.",
        f"Current training phase: {current_phase or 'Build'}.",
        f"IMPORTANT: Only prescribe work that matches this phase. "
        f"Durability Block = long sustained efforts, ZERO interval or high/peak XSS work. "
        f"Rebuild = threshold only. Taper = volume reduction. "
        f"Do NOT prescribe VO2 intervals, 5×2min blocks, or anaerobic work unless the phase explicitly calls for it.",
    ]

    prompt = '\n'.join(lines)

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1200,
        system=(
            "You are a terse, data-driven cycling coach. "
            "Write exactly 5 blocks as instructed. "
            "Start your response IMMEDIATELY with 'Block 1 —' — no title, no header, no separator line before it. "
            "Block 5 (RACE TRAJECTORY) is the most critical — always complete it fully before stopping. "
            "End every block with a complete sentence. Never cut off mid-sentence."
        ),
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    # Strip any preamble lines the model adds before Block 1 (title, date header, dashes)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip().lower()
        if stripped.startswith('block 1') or stripped.startswith('**block 1'):
            text = '\n'.join(lines[i:]).strip()
            break
    # Safety: if response ends mid-sentence, truncate at last complete sentence
    if text and text[-1] not in '.!?»"\'':
        last = max(text.rfind('. '), text.rfind('! '), text.rfind('? '))
        if last > len(text) // 2:
            text = text[:last + 1]
    return text


def generate_coaching_note(
    ctl,
    atl,
    tsb_raw,
    xert_status,
    hrv_list,
    activities,
    xss_remaining_today=None,
    strava_latest=None,
    iv_fitness=None,
    tomorrow_session=None,
    wellness=None,
    today_recovery_title=None,
    today_rec_tier=None,
    current_phase=None,
):
    """
    Generate a data-driven coaching note via Claude API, falling back to templates.

    Returns:
        String: The generated 5-block coaching note (~300 words)
    """

    today = _today_sgt()
    yesterday = today - timedelta(days=1)
    days_to_race = max(0, (RACE_DATE - today).days)

    # ── Claude API ────────────────────────────────────────────────────────────
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            note = _generate_via_claude(
                api_key, ctl, atl, tsb_raw, xert_status, hrv_list, activities,
                xss_remaining_today, strava_latest, today, days_to_race,
                iv_fitness=iv_fitness, tomorrow_session=tomorrow_session, wellness=wellness,
                today_recovery_title=today_recovery_title, today_rec_tier=today_rec_tier,
                current_phase=current_phase,
            )
            if note:
                log.info(f"Claude coaching note generated ({len(note.split())} words)")
                return note
        except Exception as e:
            log.warning(f"Claude API call failed, falling back to template: {e}")
    # ── Template fallback ─────────────────────────────────────────────────────

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

    p4 = f"You're in the {phase}. With {days_to_race} days to Tour de Bintan Stage 1, your CTL of {ctl:.1f} and ATL of {atl:.1f} show consistent work. Stay consistent, recover when needed, and trust your preparation."

    paragraphs.append(p4)

    # Combine and verify length
    note = " ".join(paragraphs)
    word_count = len(note.split())

    log.info(f"Generated coaching note ({word_count} words)")
    return note
