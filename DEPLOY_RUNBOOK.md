# Netlify Deploy Runbook — Cycling Dashboard

## Credentials
- Site ID: `bda3603b-775e-4d11-9b4f-a6f09d987e00`
- Token: in `outputs/.claude/settings.local.json` → `NETLIFY_TOKEN`
- Live URL: `https://cycling-dashboard-jl.netlify.app`

## Fast Deploy Process (3 steps, ~5 tool calls)

### Step 1 — Create deploy + get required SHAs
```javascript
// Run in javascript_tool on any tab
const r = await fetch('https://api.netlify.com/api/v1/sites/<SITE_ID>/deploys', {
  method: 'POST',
  headers: { 'Authorization': 'Bearer <TOKEN>', 'Content-Type': 'application/json' },
  body: JSON.stringify({
    files: {
      '/index.html': '<SHA1_of_dashboard_html>',
      '/upload.html': '<SHA1_of_upload_html>'
    }
  })
});
const j = await r.json();
window._deployId = j.id;
```
Get SHA1s: **do NOT use bash sha1sum** — Windows files have CRLF line endings but bash reads them as LF, giving a wrong hash. Use the browser SHA1 after FileReader loads the actual file bytes (see Step 2 verification below).

### Step 2 — Upload files via file_upload tool (NOT hex encoding)
1. Create hidden file inputs in the browser:
```javascript
['_fi1','_fi2'].forEach(id => {
  const el = document.createElement('input');
  el.type='file'; el.id=id; el.style.display='none';
  document.body.appendChild(el);
});
```
2. Use `find` to locate refs, then `file_upload` for each file
3. Read and PUT:
```javascript
const file = document.getElementById('_fi1').files[0];
const buf = await file.arrayBuffer();
await fetch(`https://api.netlify.com/api/v1/deploys/${deployId}/files/index.html`, {
  method: 'PUT',
  headers: { 'Authorization': 'Bearer <TOKEN>', 'Content-Type': 'application/octet-stream' },
  body: buf
});
```

### Step 3 — Poll until ready
```javascript
const r = await fetch(`https://api.netlify.com/api/v1/deploys/${deployId}`,
  { headers: { 'Authorization': 'Bearer <TOKEN>' } });
const j = await r.json();
j.state; // 'ready' = done
```

---

## Why NOT hex encoding

The previous approach (hex-encode file → inject via javascript_tool parameter) is **unreliable**:
- Passing 36,000-char strings through javascript_tool introduces content corruption
- Specifically: chunk[2] gains 70 extra characters; other chunks have silent byte errors
- SHA1 mismatch results; deploy fails silently

The file_upload → FileReader → fetch PUT approach:
- Zero encoding: native binary, no character mangling
- SHA1 verified server-side by Netlify (response includes sha field)
- ~5 tool calls total vs. 40+ for hex approach
- Works for any file size up to browser memory limit

---

## File locations
- Dashboard: `Cycling Training/cycling-dashboard.html` (34,413 bytes)
- Upload page: outputs folder → `upload.html` (5,443 bytes)
