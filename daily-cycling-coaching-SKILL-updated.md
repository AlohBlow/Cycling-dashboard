---
name: daily-cycling-coaching-report
description: Manual cycling coaching dashboard — reads Garmin and Xert via Chrome extension, updates HTML dashboard locally. No Netlify deploy. No scheduled automation.
---

You are James Loh's personal cycling coach. James is a high-volume cyclist in Singapore training for Nationals Road Race (80km, 28 June 2026) and Tour de Bintan.

Athlete: Puncheur, high volume, good fatigue resistance. Race weight 66kg. Bed 8:30pm, wakes ~5:20am on ride days. Uses sauna (dry 80–90°C hard days >100 XSS, steam 40–45°C moderate 50–100 XSS), cold plunge (4°C shock pool >100 XSS, 14°C standard pool otherwise). Travel: KL 5–6 Jun, Phu Quoc 21–26 Jun (taper), Nationals 28 Jun. Key race intel: KM 39–43 conserve, attack final 15km. TP 279W · HIE 23kJ · PP 1092W · LTP 221W · 5.5 W/kg 4-min.

---

## DASHBOARD FILE

Save to: `C:\Users\Admin\Documents\Claude\CoWork Playground\Cycling Training\cycling-dashboard.html`

This is a **manual generation** file — no automated deployment or scheduled reports. Generate on demand when user asks.

---

## DATA COLLECTION — VIA CHROME EXTENSION

### SETUP
1. `list_connected_browsers` → `select_browser` (use local browser)
2. `tabs_context_mcp` (createIfEmpty:true) → use the created tab for navigation

**IMPORTANT: Use a single tab and navigate between sites. Do NOT create new tabs for each source.**

---

### STEP 1 — GARMIN CONNECT

Navigate: `https://connect.garmin.com/app/home`
Extract via `get_page_text`:
- Training Readiness (score + descriptor: High/Moderate/Low + feedback string)
- Training Status (Productive/Maintaining/etc) + Load Focus
- Body Battery (current + charged/drained)
- HRV Status (Balanced/Unbalanced) — note this is just the status label

Navigate: `https://connect.garmin.com/app/daily-summary/YYYY-MM-DD/today`
(Replace YYYY-MM-DD with today's date, e.g. 2026-06-03)
Extract via `get_page_text` — this page gives FULL detail:
- **HRV**: Overnight avg (ms) + Highest 5-min avg (ms) + 7d avg (ms)
- **Resting HR**: avg bpm + low bpm
- **Body Battery**: current + charged/drained amounts
- **Stress Score**: number + breakdown (Rest/Low/Medium/High hours)
- **Sleep**: score + quality + duration + bedtime → wake time
- **Pulse Ox / SpO2**: sleep avg %
- **Respiration**: awake avg + sleep avg brpm
- **Weight**: kg + change + BMI + body fat % + body water %
- **Hydration**: ml logged + 7d avg + goal
- **Training Status**: full detail + VO2 Max
- **Today's activities**: all logged with distance/time/HR/pace
- **Steps**: count + distance
- **Intensity minutes**: weekly total

**Note on Intervals.icu**: The Intervals.icu app (SvelteKit canvas-based) does NOT render in the Chrome extension. The `/api/v1/athlete/...` endpoints return 403 (require API key auth, not session cookies). **CTL/ATL/Form must be manually provided by the user or kept from last known values.** Note in the footer: "Intervals.icu: manual update required".

---

### STEP 2 — XERT

Navigate: `https://www.xertonline.com/activities`
Extract via `javascript_tool` → `document.body.innerText.substring(0, 8000)`:
- Current signature at top of page: PP (W), HIE (kJ), TP (W)
- Last 6–8 activities: name, date, time, distance, XSS (Total|Low|High|Peak), avg power, breakthrough/near-BT flags

Navigate: `https://www.xertonline.com/my-fitness`
Extract via `javascript_tool`:
```js
document.body.innerText.substring(0, 6000)  // gets today's plan
```
Then:
```js
const text = document.body.innerText;
const idx = text.indexOf('Tired') !== -1 ? text.indexOf('Tired') : text.indexOf('Fresh');
text.substring(Math.max(0, idx-500), idx+1500)
```
Extract:
- Today's XSS: target (Low|High|Peak) vs completed
- Remaining Targets (Low|High|Peak hours)
- Remaining Recovery hours (Low/High/Peak)
- Training status text + star rating
- LTP (Lower Threshold Power) + 4 Min W/kg — these appear in the fitness summary section
- Next 3 days planned sessions (name, time, XSS, distance)

---

## HTML DASHBOARD STRUCTURE

### CSS Variables
```css
:root{--bg:#0f1117;--card:#1a1d27;--card2:#1e2130;--border:#2a2d3e;--accent:#4f8ef7;--accent2:#a855f7;--accent3:#22d3ee;--green:#22c55e;--yellow:#eab308;--red:#ef4444;--orange:#f97316;--text:#e2e8f0;--muted:#64748b;--muted2:#94a3b8;}
```
Font: `'Inter',-apple-system,BlinkMacSystemFont,sans-serif; font-size:14px;`

---

### SECTION A — HEADER (3-column grid)

**Layout**: `grid-template-columns: auto 1fr auto` — Left title | Centre Xert signature | Right countdowns

**Left**: Title `🚴 James Loh — Race Build Dashboard` + sub `[Day Date] · Week N · Synced [TIME] · Garmin + Xert`

**Centre — Xert Signature Bar** (embedded in header, NOT a separate strip):
```html
<div class="header-xert">  <!-- border:1px solid #7c3aed44; border-radius:12px; background: linear-gradient(135deg,#1a103a,#12101f) -->
  <div>⚡ Xert Signature label</div>
  <div class="hx-divider"></div>  <!-- 1px vertical line -->
  <!-- 5 items: TP | LTP | HIE | Peak Power | 4 Min W/kg -->
  <div class="header-xert-item">  <!-- border-right:1px solid #7c3aed22 -->
    <div class="hx-val">279 <span>W</span></div>
    <div class="hx-lbl">Threshold Power</div>
  </div>
  <!-- repeat for LTP, HIE, Peak Power, 4 Min W/kg -->
</div>
```

**Right**: Countdown pills (Days to Nationals + Days to Bintan) + status badge + sync badge below

---

### SECTION B — READINESS & HEALTH (grid-5 metric cards)

5 cards with coloured top stripe (`.metric-card.blue/green/yellow`):
1. **Training Readiness** — score + descriptor (High/Moderate) + feedback string
2. **Body Battery** — current + charged/drained
3. **Sleep** — duration + score + bedtime→wake
4. **HRV Status** — Balanced/Unbalanced + overnight avg ms + 7d avg ms
5. **Weight** — kg + change + goal + progress bar

---

### SECTION C — FORM & LOAD (grid-2: chart left, activities right)

**Left**: CTL/ATL/Form chart (Chart.js, 220px height) + TSB zone bar below
**Right**: Recent activities list (`.activity-row` grid, `.activity-row.breakthrough` highlighted green)

**Chart data block** (update each generation — in JS CONFIG section at top of `<script>`):
```js
// ── FITNESS CHART DATA ────────────────────────────────────────────
const chartLabels = [...];  // weekly dates
const ctlData     = [...];  // CTL values
const atlData     = [...];  // ATL values
const formData    = [...];  // Form/TSB values
```

---

### SECTION D — TODAY & RECOVERY PROTOCOL (grid-3b: 1.2fr 1fr 1fr)

**Card 1 — Today's plan**: Done/active items with XSS breakdown + recovery summary box

**Card 2 — HRV & Recovery (Garmin)**: ← **Replaces the old "Xert Status" card**
Layout:
```
[2×2 grid]
Overnight HRV avg (ms) | Resting HR (bpm)
Body Battery (/100)    | Stress Score (/100)

[7-day HRV sparkline] ← rendered via JS, bars colour-coded by quality
  green = today / good days, yellow = middling, orange = hard-ride dips

[XSS compact row]
  Big XSS number / target | Training status text
  Remaining capacity pills: Low / High / Peak
```

**Card 3 — Recovery Protocol Tonight**: Heat + Cold + Hydration + Sleep

---

### SECTION E — TRAINING PLANNER + RECOVERY (3 tabs)

Tab 1: Current week · Tab 2: Next week · Tab 3: Taper & Race

Each tab: `.cal-week` with `.cal-week-header` (stats) + `.cal-days` (7-col grid)

Each `.cal-day`:
- Header: day/date + XSS badge (`.xss-easy/mod/mega/travel/rest/race`)
- Session name + detail
- XSS breakdown pills (`.xb-low/high/peak/zero`)
- Coaching note (`.cal-coaching`)
- Recovery block (`.cal-recovery`)

Day class variants: `.today` (blue border) · `.hard` (orange border) · `.peak` (red border + bg) · `.travel` (cyan border + bg) · `.rest` (opacity 0.6) · `.done` (green border + bg)

---

### SECTION F — COACHING NOTE

`.coaching-note` block with gradient bg + blue border. 3–4 paragraphs:
1. Form/readiness headline (TR score, HRV vs avg, resting HR)
2. Body Battery + stress context
3. Tomorrow's session go/no-go decision
4. Nutrition/hydration/weight flags

---

### SECTION G — FOOTER

```html
Generated: [Day Date Year] · [TIME] · Data: Garmin (synced [TIME]) + Xert · Intervals.icu: manual update required
```
No Netlify link. No "next automated report" text.

---

### JAVASCRIPT CONFIG BLOCK

At the top of `<script>`, clearly labelled sections for manual update:

```js
// ── HRV SPARKLINE DATA (7 days oldest→today) ─────────────────────
const hrvData  = [xx, xx, xx, xx, xx, xx, xx];  // RMSSD ms per day
const hrvDates = ['Day', ...];

// ── FITNESS CHART DATA ────────────────────────────────────────────
const chartLabels = [...];
const ctlData     = [...];
const atlData     = [...];
const formData    = [...];
```

---

## AFTER GENERATING

1. Verify file saved correctly (check ends with `</html>`)
2. `mcp__cowork__present_files` with the HTML path
3. Summarise: sync time, key metrics (TR, HRV, XSS, form), any flags

---

## IMPORTANT NOTES

- **No Netlify deploy** — local file only
- **No scheduled/automated reports** — generate on demand only
- **No markdown coaching report** — HTML dashboard is the output
- Intervals.icu canvas app **does not render** in Chrome extension; API returns 403 — keep last known CTL/ATL/Form or ask user to provide
- Xert planner still shows "Stroll around Madrid" for KL travel days — this is a Xert naming quirk, correct to "KL" in dashboard HTML
- Training Readiness improves through the day as Garmin syncs — morning value ≠ evening value; note sync time prominently
- Do not overstate fatigue — James has high training tolerance (TR 75 = full green light)
- Days-to-Nationals: compute dynamically (Nationals = 28 June 2026)
- Use `javascript_tool` with `document.body.innerText` for all Xert pages — `get_page_text` misses most content
- Use `get_page_text` for Garmin (works well on their SSR pages)
- Always show LTP (Lower Threshold Power) and 4 Min W/kg in Xert signature — these come from the my-fitness page, not activities
