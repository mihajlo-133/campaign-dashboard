# Phase 4: UX Polish + Deployment — Research

**Researched:** 2026-04-04
**Domain:** CSS/UX polish, Playwright visual QA, Render deployment
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Refine current design system — do not overhaul. Improve spacing, typography weight, hover states, transitions (200-300ms eases), and consistency across all 6 templates (base, login, admin, dashboard, workspace, campaign).
- **D-02:** No dark mode. Light theme only. Internal tool, keep it simple.
- **D-03:** UX expert agent and Claude have full discretion on specific visual improvements.
- **D-04:** Playwright test directory structure is Claude's discretion.
- **D-05:** Screenshots validated by the `ux-design-expert` agent — no manual human review step required.
- **D-06:** Playwright tests include static screenshots at 3 viewports (1440x900, 768x1024, 375x812) AND full interaction flow: click scan button → verify loading spinner appears → wait for HTMX swap → confirm results update.
- **D-07:** NEW Render service — do NOT deploy to `srv-d73efrfdiees73erakqg` (campaign-dashboard). Old monolithic dashboard stays untouched.
- **D-08:** Render free tier. Uptime bot out of scope for this phase.
- **D-09:** Proven deployment pattern: API keys as env vars, auto-detect Render via PORT env var, bind 0.0.0.0 on Render / 127.0.0.1 locally, public GitHub repo, always deploy with `clearCache: "clear"` via Render REST API.
- **D-10:** 6 workspace API keys set manually in Render dashboard UI. No keys in code or render.yaml.
- **D-11:** Render API key at `tools/accounts/render/api_key.md`.
- **D-12:** `ux-design-expert` agent runs as post-implementation gate after every piece of frontend work — not just once at end.
- **D-13:** UX expert agent takes Playwright screenshots, checks all 3 viewports, clicks through the UI.
- **D-14:** Claude decides when to stop iterating on UX feedback — stop when fixes hit diminishing returns (cosmetic, not structural).

### Claude's Discretion

- Playwright test directory structure (D-04)
- Specific visual polish improvements — typography, spacing, shadows, transitions (D-03)
- Number of UX expert review iterations per deliverable (D-14)
- GitHub repo setup for the new Render service (new repo vs monorepo subfolder deploy)
- Exact Render service configuration (region, instance type within free tier)
- Health check endpoint design

### Deferred Ideas (OUT OF SCOPE)

- Uptime bot setup (e.g., UptimeRobot) to keep free tier warm
- Custom domain for the new Render service
- Deprecating/removing the old `campaign-dashboard` Render service

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-01 | Dashboard has polished, professional visual design (luxury aesthetic) | CSS design token audit of base.html; UX expert agent protocol established; specific improvement areas identified |
| UX-04 | Visual QA validated with Playwright screenshots at multiple viewports before shipping | Playwright CLI v1.59 confirmed installed; screenshot + resize commands documented; 3-viewport protocol defined |
| UX-05 | UX design expert agent consulted during frontend phases for evidence-based design review | Agent file at `.claude/agents/ux-design-expert.md` confirmed; audit protocol and deliverable format documented |

</phase_requirements>

---

## Summary

Phase 4 is a refinement-and-ship phase: polish the existing design system, validate visually with Playwright and the UX expert agent, then deploy a new Render service for the email QA dashboard. No new features. No architecture changes.

The existing codebase is well-structured for this phase. `base.html` already has a solid CSS custom property system (`--bg`, `--tx1`, `--blue`, etc.), Inter font, and responsive breakpoints at 767px and 1023px. The templates inherit cleanly from `base.html`, so improvements to the design tokens propagate to all 6 templates automatically. The Procfile already uses gunicorn + uvicorn worker — it's Render-ready.

The deployment story is clear from prior sessions. The pattern is proven: new GitHub repo (public, no secrets), Render service created via API with `clearCache: "clear"` on every deploy, API keys as env vars matching the `WORKSPACE_<NAME>_API_KEY` pattern already coded in `workspace.py`. The only action needed is creating the new Render service and setting 6 env vars manually in the Render dashboard.

**Primary recommendation:** Run UX expert audit first to get a scored improvement list, apply CSS fixes in `base.html` and page-specific stylesheets, validate with Playwright screenshots at 3 viewports, then create the GitHub repo + Render service and set env vars.

---

## Standard Stack

All tools are already in use — this phase adds no new dependencies.

### Core (already in requirements.txt)

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| FastAPI | >=0.135.0 | Web framework | Installed |
| Jinja2 | bundled with FastAPI | Template rendering | Installed |
| HTMX | 2.0.4 (CDN) | Partial page updates | In use |
| Inter | Google Fonts (CDN) | Typography | In use |
| gunicorn + uvicorn | >=23.0.0 | ASGI server for Render | Installed |

### Dev/QA (already in requirements-dev.txt)

| Tool | Version | Purpose | Status |
|------|---------|---------|--------|
| pytest | >=8.0.0 | Test runner | Installed |
| playwright-cli | 1.59.0-alpha (npm global) | Browser screenshots + interaction testing | Confirmed installed |
| ruff | latest | Linting | Installed |

### External Services

| Service | Purpose | Status |
|---------|---------|--------|
| GitHub (public repo) | Source for Render auto-deploy | Needs new repo for email-qa project |
| Render free tier | Production hosting | Needs new service (NOT srv-d73efrfdiees73erakqg) |

**No new packages to install for this phase.**

---

## Architecture Patterns

### Existing Project Structure

```
prospeqt-email-qa/
├── app/
│   ├── main.py              # FastAPI app factory, lifespan, scheduler
│   ├── config.py            # Settings via pydantic-settings
│   ├── templates/
│   │   ├── base.html        # CSS design system — all CSS vars here
│   │   ├── dashboard.html   # Overview page (workspace grid)
│   │   ├── workspace.html   # Workspace detail (campaign table)
│   │   ├── campaign.html    # Campaign detail (variable summary + broken leads)
│   │   ├── admin.html       # Admin panel (workspace management)
│   │   └── login.html       # Admin login
│   ├── routes/
│   ├── services/
│   │   └── workspace.py     # Reads WORKSPACE_*_API_KEY env vars
│   ├── models/
│   └── api/
├── tests/                   # pytest unit/integration tests
├── Procfile                 # gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
├── requirements.txt
├── requirements-dev.txt
├── runtime.txt              # python-3.11.0
└── pytest.ini               # asyncio_mode = auto
```

### Pattern 1: CSS Token Refinement (Design System Polish)

**What:** All visual improvements flow through CSS custom properties in `base.html`. Page templates inherit via `{% extends "base.html" %}` — changing a token updates all 6 templates.

**Existing tokens to refine:**
```css
/* Source: prospeqt-email-qa/app/templates/base.html */
:root {
  --bg: #f5f5f7;           /* Page background */
  --bg-el: #ffffff;        /* Card/element background */
  --bg-hov: #f0f0f2;       /* Hover state */
  --bd: #e0e0e4;           /* Default border */
  --bd-s: #d0d0d4;         /* Strong border (hover) */
  --tx1: #1a1a1a;          /* Primary text */
  --tx2: #6b6b6b;          /* Secondary text */
  --tx3: #8a8a8e;          /* Muted text */
  --blue: #2756f7;         /* Primary action */
  --blue-h: #1679fa;       /* Primary action hover */
  --green: #1a8a3e;        /* Success/clean */
  --amber: #b87a00;        /* Warning */
  --red: #c33939;          /* Error/broken */
  --sh: 0 1px 3px rgba(0,0,0,0.04), 0 2px 8px rgba(0,0,0,0.04);
  --sh-md: 0 4px 12px rgba(0,0,0,0.08);
}
```

**Typical refinement targets (from UX expert audit protocol):**
- Typography weight: confirm heading/body/meta weight progression creates clear hierarchy
- Shadow depth: `--sh` and `--sh-md` — may need `--sh-lg` for modals or elevated states
- Transition consistency: currently buttons use `0.15s`, base pattern should be `200-300ms ease` per D-01
- Spacing: verify 8px grid adherence across card padding, gap values, page-shell padding
- Hover states: ensure all interactive elements (table rows, cards, nav items) have `--bg-hov` applied
- Border radius: `8px` on cards, `12px` on section cards (admin) — ensure consistency

### Pattern 2: Playwright Visual QA Protocol

**What:** `playwright-cli` (already installed globally at v1.59.0-alpha) takes screenshots and tests interaction flows. The `playwright-cli-expert` agent handles all browser operations.

**Viewport resize then screenshot pattern:**
```bash
# Source: playwright-cli-expert agent + existing prospeqt dashboard QA pattern

# Session start
playwright-cli open http://localhost:8000

# Desktop viewport
playwright-cli resize 1440 900
playwright-cli screenshot --filename=desktop.png

# Tablet viewport  
playwright-cli resize 768 1024
playwright-cli screenshot --filename=tablet.png

# Mobile viewport
playwright-cli resize 375 812
playwright-cli screenshot --filename=mobile.png
```

**Interaction flow test for scan button (D-06):**
```bash
# 1. Snapshot to get scan button ref
playwright-cli snapshot
# 2. Click scan button (ref from snapshot)
playwright-cli click <scan-btn-ref>
# 3. Snapshot to verify loading spinner appeared
playwright-cli snapshot
# 4. Wait for HTMX swap to complete
playwright-cli snapshot  # Re-snapshot after update
# 5. Confirm results updated (workspace-grid content changed)
```

**QA output directory (Claude's discretion per D-04):**
```
prospeqt-email-qa/
└── qa/
    └── screenshots/
        ├── desktop-overview.png
        ├── tablet-overview.png
        ├── mobile-overview.png
        ├── desktop-workspace.png
        └── ... (per page, per viewport)
```

### Pattern 3: Render Deployment

**What:** Create a new Render service pointing to a new GitHub repo containing only the `prospeqt-email-qa/` directory contents.

**Render service creation via API:**
```bash
# Source: Session_20260328_170000_dashboard_redesign_render_deploy.md
# Render API key: rnd_plQzm24wpxndHKJ7scpVQs7EbwdH (tools/accounts/render/api_key.md)

curl -X POST "https://api.render.com/v1/services" \
  -H "Authorization: Bearer rnd_plQzm24wpxndHKJ7scpVQs7EbwdH" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "web_service",
    "name": "prospeqt-email-qa",
    "repo": "https://github.com/mihajlo-133/<new-repo>",
    "branch": "main",
    "plan": "free",
    "region": "frankfurt",
    "buildCommand": "pip install -r requirements.txt",
    "startCommand": "gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT",
    "envVars": [
      {"key": "PYTHON_VERSION", "value": "3.11.0"},
      {"key": "QA_POLL_INTERVAL_SECONDS", "value": "300"}
    ]
  }'
```

**Deploy with cache clearing (mandatory per D-09):**
```bash
# Source: Session_20260328_170000_dashboard_redesign_render_deploy.md
# CRITICAL: Docker layer caching caused stale code bugs in prior deploys

curl -s -X POST "https://api.render.com/v1/services/<new-service-id>/deploys" \
  -H "Authorization: Bearer rnd_plQzm24wpxndHKJ7scpVQs7EbwdH" \
  -H "Content-Type: application/json" \
  -d '{"clearCache": "clear"}'
```

**Workspace env var naming (matches workspace.py WORKSPACE_ENV_PATTERN):**
```
WORKSPACE_MYPLACE_API_KEY=<key>
WORKSPACE_SWISHFUNDING_API_KEY=<key>
WORKSPACE_SMARTMATCHAPP_API_KEY=<key>
WORKSPACE_KAYSE_API_KEY=<key>
WORKSPACE_PROSPERLY_API_KEY=<key>
WORKSPACE_HEYREACH_API_KEY=<key>
```

Note: The existing `.env` uses `INSTANTLY_*` naming (for the OLD monolithic dashboard). The email-QA app uses `WORKSPACE_*_API_KEY` pattern (enforced by `workspace.py` regex `^WORKSPACE_([A-Z0-9_]+)_API_KEY$`). These are different apps with different env var schemes.

**Render auto-detect pattern (already in `workspace.py` / `main.py`):**
- `load_from_env()` called in lifespan — reads all `WORKSPACE_*_API_KEY` env vars at startup
- `Procfile` already binds `0.0.0.0:$PORT` — Render-ready
- `runtime.txt` already specifies `python-3.11.0`

**GitHub repo options (Claude's discretion):**
- **Option A (recommended):** New GitHub repo `mihajlo-133/prospeqt-email-qa` containing `prospeqt-email-qa/` contents at root. Clean, dedicated repo for this service.
- **Option B:** Render root directory config pointing to `prospeqt-email-qa/` subfolder of monorepo. More complex Render setup.

Option A is preferred — matches pattern from prior deployments and avoids monorepo root-dir config.

### Pattern 4: UX Expert Agent Integration

**What:** The `ux-design-expert` agent (`.claude/agents/ux-design-expert.md`) performs evidence-based code audits across 8 dimensions and produces scored reports with specific CSS fixes.

**When to trigger (D-12):** After every frontend deliverable, not just at end.
**Protocol:** Agent reads template HTML/CSS, evaluates 8 dimensions (cognitive load, IA, visual hierarchy, dataviz, interaction, mobile, accessibility, consistency), produces Top 5 Highest-Impact Fixes with CSS snippets.
**Iteration stop rule (D-14):** Stop when remaining issues are cosmetic (shadow shade, pixel-level spacing) rather than structural (hierarchy, touch target sizes, contrast).

### Anti-Patterns to Avoid

- **Overriding base.html tokens with inline styles:** CSS custom properties cascade. Adding `style="color: red"` bypasses the design system. Always use `var(--red)`.
- **Starting new Render service pointing at old service ID:** Per D-07, the existing `srv-d73efrfdiees73erakqg` must NOT be touched. Deploying to it would overwrite the team's live outreach dashboard.
- **Using deploy hook URL for cache busting:** The Render deploy hook (`https://api.render.com/deploy/...`) does NOT support `clearCache`. Must use the REST API (`POST /v1/services/{id}/deploys` with body `{"clearCache": "clear"}`).
- **Hardcoding API keys anywhere in source:** Keys go in Render env vars only (D-10). workspace.py already enforces this via env var reading.
- **Playwright screenshots without resize:** `playwright-cli screenshot` captures current viewport. Must call `playwright-cli resize W H` before each screenshot.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSS design tokens | New token system | Extend existing `:root` vars in `base.html` | System already exists, propagates to all 6 templates |
| Browser screenshots | Custom Playwright script | `playwright-cli-expert` agent | Agent handles session management, resize, file output |
| UX review criteria | Manual checklist | `ux-design-expert` agent | Agent has 4 skill files of HCI/design science, produces scored reports |
| Render deployment | Deploy script from scratch | Render REST API with proven curl pattern | Pattern verified across 2 prior sessions, `clearCache` essential |
| Port detection | Complex env detection | `PORT` env var presence check (already in Procfile) | Procfile already handles this correctly |

**Key insight:** All tooling for this phase exists and is proven. The work is CSS refinement + running agents + one Render API call.

---

## Common Pitfalls

### Pitfall 1: Docker Layer Cache Stale Code

**What goes wrong:** Render caches Docker layers aggressively. A `COPY requirements.txt .` layer hash can match even when source files changed, causing old code to be served despite showing "deploy successful."

**Why it happens:** Docker build caching is content-hash based. Minor changes can resolve to the same layer hash.

**How to avoid:** Always use `clearCache: "clear"` in the Render deploy API call body. This forces a full rebuild. The deploy hook URL does NOT support this — must use the REST API.

**Warning signs:** Deploy shows "live" but changes aren't reflected in the running app.

### Pitfall 2: Wrong Render Service Targeted

**What goes wrong:** Accidentally deploying to `srv-d73efrfdiees73erakqg` (the old outreach dashboard) instead of the new email-QA service.

**Why it happens:** Both use the same Render API key. Easy to copy the old service ID.

**How to avoid:** The new service ID won't be known until service creation. Save it immediately. Never reuse `srv-d73efrfdiees73erakqg`.

**Warning signs:** Post-deploy URL is `campaign-dashboard-0zra.onrender.com` — that's the wrong service.

### Pitfall 3: WORKSPACE_* vs INSTANTLY_* Key Confusion

**What goes wrong:** Setting `INSTANTLY_MYPLACE` env vars on Render instead of `WORKSPACE_MYPLACE_API_KEY`. Dashboard starts with 0 workspaces configured.

**Why it happens:** The old monolithic dashboard (client_dashboard.py) uses `INSTANTLY_*` naming. The email-QA app uses `WORKSPACE_*_API_KEY` naming. Both are in the same Render account.

**How to avoid:** The regex in `workspace.py` is `^WORKSPACE_([A-Z0-9_]+)_API_KEY$`. Env var names must match exactly. Test by checking the admin panel after first deploy — should show 6 workspaces.

**Warning signs:** Admin panel shows "No workspaces configured" after deploy, despite keys being set.

### Pitfall 4: HTMX Scan Flow Not Tested End-to-End

**What goes wrong:** Screenshots show a static page. The Playwright test doesn't verify that clicking "Scan All" triggers the loading spinner and updates the workspace grid.

**Why it happens:** Static screenshots only validate layout — they miss HTMX interaction behavior.

**How to avoid:** Per D-06, the test must include: click scan → verify `htmx-indicator` spinner is visible → wait for HTMX swap → confirm `#workspace-grid` content updated. The `playwright-cli` tool's snapshot mechanism handles this: snapshot after click shows the DOM mid-request.

**Warning signs:** All screenshots pass UX review but the "run check" flow isn't tested.

### Pitfall 5: Render Free Tier Cold Start on First QA

**What goes wrong:** Playwright test fails because Render cold starts take ~30 seconds, causing connection timeout during the interaction flow test.

**Why it happens:** Render free tier spins down after 15 minutes. First request wakes the dyno.

**How to avoid:** Before running Playwright end-to-end tests against production, ping the URL first and wait for a 200 response. Add a retry/wait in the test flow.

**Warning signs:** Playwright times out on first `playwright-cli open <render-url>`.

---

## Code Examples

### Health Check Endpoint (recommended addition)

Render needs a health check URL to determine if the service is up.

```python
# Source: FastAPI docs + Render deployment best practice
# Add to app/routes/dashboard.py or app/main.py

@router.get("/health")
async def health():
    return {"status": "ok"}
```

Configure in Render service settings: health check path = `/health`.

### Transition Consistency (CSS refinement example)

Current buttons use `transition: background 0.15s` — too fast (150ms). Per D-01, use 200-300ms eases.

```css
/* Source: base.html — update these transitions */
.scan-btn-primary {
  transition: background 0.2s ease;  /* was 0.15s */
}
.scan-btn-secondary {
  transition: background 0.2s ease, border-color 0.2s ease;  /* was 0.15s */
}
.ws-card {
  transition: box-shadow 0.2s ease;  /* was 0.15s */
}
.gear-btn {
  transition: background 0.2s ease, border-color 0.2s ease;  /* was 0.15s */
}
```

### HTMX Loading State (verify spinner coverage)

The scan button already has an `htmx-indicator` spinner. Confirm the HTMX attributes are correct so the loading state is visible:

```html
<!-- Source: base.html — existing pattern, verify it works -->
<button class="scan-btn-primary"
        hx-post="/api/scan/all"
        hx-target="#workspace-grid"
        hx-swap="outerHTML"
        hx-indicator=".scan-all-spinner">
  <span class="scan-all-spinner htmx-indicator">
    <svg class="spin-icon">...</svg>
  </span>
  <span class="scan-btn-label">Scan All</span>
</button>
```

The `hx-indicator` attribute points to `.scan-all-spinner`. The `.htmx-indicator` class hides it by default and shows it during HTMX requests. This is the element the Playwright test must confirm is visible after clicking the button.

### Playwright Interaction Flow Test

```bash
# Source: playwright-cli-expert agent pattern + base.html HTMX setup

# 1. Start session
playwright-cli open http://localhost:8000

# 2. Resize to desktop
playwright-cli resize 1440 900

# 3. Take baseline screenshot
playwright-cli screenshot --filename=qa/screenshots/desktop-overview-before-scan.png

# 4. Snapshot to get scan button ref
playwright-cli snapshot
# Read .playwright-cli/latest.yml, find "Scan All" button ref (e.g., e42)

# 5. Click scan button
playwright-cli click e42

# 6. Snapshot IMMEDIATELY after click — spinner should be visible
playwright-cli snapshot
# Read snapshot — verify scan-all-spinner is visible (htmx-request class applied)

# 7. Snapshot after HTMX swap completes
playwright-cli snapshot
# Verify #workspace-grid content updated

# 8. Screenshot of post-scan state
playwright-cli screenshot --filename=qa/screenshots/desktop-overview-after-scan.png

# 9. Close session
playwright-cli close
```

---

## State of the Art

| Old Pattern | Current Pattern | Impact |
|------------|----------------|--------|
| Deploying via Render deploy hook | REST API with `clearCache: "clear"` | Eliminates stale code from Docker layer caching |
| Reading API keys from local markdown files | Env vars on Render | No secrets in source code |
| Manual visual QA | Playwright + UX expert agent | Evidence-based, reproducible |
| Single-file monolith | Modular FastAPI app | Navigable codebase, clean template inheritance |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| playwright-cli | Playwright QA screenshots and interaction tests | ✓ | 1.59.0-alpha | — |
| Python 3.11 | App runtime (runtime.txt) | ✓ | 3.11.x | — |
| gunicorn | Render Procfile | ✓ | >=23.0.0 (requirements.txt) | — |
| Render API key | Service creation + deploys | ✓ | `rnd_plQzm24wpxndHKJ7scpVQs7EbwdH` (tools/accounts/render/api_key.md) | — |
| GitHub account | Public repo for Render auto-deploy | ✓ | mihajlo-133 (prior deploys confirmed) | — |
| Workspace API keys | Render env var configuration | ✓ | In `tools/prospeqt-automation/.env` (INSTANTLY_* naming, need conversion to WORKSPACE_*_API_KEY) | — |
| ux-design-expert agent | UX audit | ✓ | `.claude/agents/ux-design-expert.md` | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

**Key note on API keys:** The `tools/prospeqt-automation/.env` has all 6 workspace keys under `INSTANTLY_*` naming. For Render, they must be set as `WORKSPACE_<NAME>_API_KEY`. The conversion is: `INSTANTLY_MYPLACE` → `WORKSPACE_MYPLACE_API_KEY`. The 6 workspaces are: MYPLACE, SWISHFUNDING, SMARTMATCHAPP, KAYSE, PROSPERLY, HEYREACH.

---

## Validation Architecture

> nyquist_validation is enabled (not explicitly set to false in config.json).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.24.x |
| Config file | `prospeqt-email-qa/pytest.ini` — `asyncio_mode = auto` |
| Quick run command | `cd prospeqt-email-qa && python -m pytest tests/ -x -q` |
| Full suite command | `cd prospeqt-email-qa && python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-01 | Polished luxury aesthetic — no critical design issues | Manual-only (UX expert agent audit) | Run `ux-design-expert` agent against templates | N/A — agent-based |
| UX-04 | Playwright screenshots at 3 viewports show no broken layouts | Visual QA (playwright-cli) | `playwright-cli screenshot` at 3 viewports + validated by UX expert agent | ❌ Wave 0 — create `prospeqt-email-qa/qa/` |
| UX-05 | UX design expert agent consulted as quality gate | Process check | Confirmed via UX expert agent audit report output | N/A — process |

**Note on UX-01/UX-05:** These requirements are validated by the `ux-design-expert` agent, not pytest. The agent reads template source code, evaluates 8 dimensions, and produces a scored report. Success criteria = no critical issues outstanding (grade B or above on all structural dimensions).

**Note on UX-04:** The Playwright interaction flow (scan → loading → results update) is a manual test via `playwright-cli` commands, not a pytest test. Screenshots are reviewed by the UX expert agent.

### Sampling Rate

- **Per task commit:** `cd prospeqt-email-qa && python -m pytest tests/ -x -q` (existing suite — regression check)
- **Per wave merge:** `cd prospeqt-email-qa && python -m pytest tests/ -v`
- **Phase gate:** Full suite green + UX expert agent audit grade B+ + Playwright screenshots at 3 viewports pass before marking phase complete

### Wave 0 Gaps

- [ ] `prospeqt-email-qa/qa/screenshots/` — directory for Playwright output screenshots (create in Wave 0)
- [ ] `prospeqt-email-qa/qa/` — QA directory for Playwright workflow docs and screenshots

*(Existing test infrastructure in `tests/` covers all backend requirements. No new pytest files needed for this phase — UX validation is agent-based + visual.)*

---

## Deployment Workflow (Canonical Reference)

Based on verified patterns from two prior sessions:

### Step 1: Create new GitHub repo

New repo: `mihajlo-133/prospeqt-email-qa` (public)

Contents at repo root = contents of `prospeqt-email-qa/` directory:
- `app/`
- `tests/`
- `Procfile`
- `requirements.txt`
- `requirements-dev.txt`
- `runtime.txt`
- `pytest.ini`

### Step 2: Create Render service via API

```bash
curl -X POST "https://api.render.com/v1/services" \
  -H "Authorization: Bearer rnd_plQzm24wpxndHKJ7scpVQs7EbwdH" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "web_service",
    "name": "prospeqt-email-qa",
    "ownerId": "tea-d73ebos2kvos73aaeajg",
    "repo": "https://github.com/mihajlo-133/prospeqt-email-qa",
    "branch": "main",
    "plan": "free",
    "region": "frankfurt",
    "buildCommand": "pip install -r requirements.txt",
    "startCommand": "gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT",
    "healthCheckPath": "/health"
  }'
```

Save the returned service ID.

### Step 3: Set env vars manually in Render dashboard

Navigate to Render dashboard → new service → Environment → add:

```
WORKSPACE_MYPLACE_API_KEY      = <from tools/prospeqt-automation/.env INSTANTLY_MYPLACE>
WORKSPACE_SWISHFUNDING_API_KEY = <from tools/prospeqt-automation/.env INSTANTLY_SWISHFUNDING>
WORKSPACE_SMARTMATCHAPP_API_KEY = <from tools/prospeqt-automation/.env INSTANTLY_SMARTMATCHAPP>
WORKSPACE_KAYSE_API_KEY        = <from tools/prospeqt-automation/.env INSTANTLY_KAYSE>
WORKSPACE_PROSPERLY_API_KEY    = <from tools/prospeqt-automation/.env INSTANTLY_PROSPERLY>
WORKSPACE_HEYREACH_API_KEY     = <from tools/prospeqt-automation/.env INSTANTLY_HEYREACH>
QA_POLL_INTERVAL_SECONDS       = 300
ADMIN_PASSWORD                 = <set a secure password>
```

### Step 4: Deploy with cache clearing

```bash
curl -s -X POST "https://api.render.com/v1/services/<new-service-id>/deploys" \
  -H "Authorization: Bearer rnd_plQzm24wpxndHKJ7scpVQs7EbwdH" \
  -H "Content-Type: application/json" \
  -d '{"clearCache": "clear"}'
```

### Step 5: Verify

1. Wait for deploy to complete (poll `/v1/services/<id>/deploys`)
2. Open production URL in browser
3. Verify admin panel shows 6 workspaces
4. Run Playwright end-to-end test against production URL

---

## Open Questions

1. **Admin password for production deployment**
   - What we know: Admin panel requires `ADMIN_PASSWORD` env var (from Phase 1 decisions)
   - What's unclear: No password specified yet for the production Render service
   - Recommendation: Generate a secure password during the Render env var setup step. Note it securely.

2. **GitHub repo naming: new vs subfolder deploy**
   - What we know: Prior deploys all used dedicated repos (campaign-dashboard had its own repo)
   - What's unclear: Whether Render subfolder deploy (root directory config) would work cleanly
   - Recommendation: New dedicated repo `mihajlo-133/prospeqt-email-qa` — cleaner, proven pattern

3. **ADMIN_PASSWORD env var name confirmation**
   - What we know: Admin auth uses `itsdangerous` with session tokens (Phase 1 decision)
   - What's unclear: Exact env var name used in `app/config.py` for the admin password
   - Recommendation: Check `app/config.py` and `app/routes/admin.py` during implementation to confirm exact env var name before setting it in Render

---

## Project Constraints (from CLAUDE.md)

- **Modular architecture required:** Not a single-file monolith (already satisfied by Phase 1-3 work)
- **Render deployment:** Must work as standard Python web app with Procfile (already satisfied)
- **No hardcoded keys:** API keys via env vars only (already satisfied; confirmed by workspace.py pattern)
- **UX/UI quality:** Use `ux-design-expert` agent for design audits (D-12/D-13)
- **Playwright testing:** All frontend phases must include Playwright visual QA at multiple viewports (D-06)
- **No dark mode:** Light theme only (D-02)
- **GSD workflow:** Changes go through GSD execute-phase, not direct repo edits

---

## Sources

### Primary (HIGH confidence)

- `prospeqt-email-qa/app/templates/base.html` — Confirmed CSS design token system, existing breakpoints, transition values
- `prospeqt-email-qa/Procfile` — Confirmed gunicorn + uvicorn binding pattern for Render
- `prospeqt-email-qa/app/services/workspace.py` — Confirmed `WORKSPACE_*_API_KEY` env var pattern and regex
- `prospeqt-email-qa/runtime.txt` — Confirmed Python 3.11.0
- `.claude/agents/ux-design-expert.md` — Confirmed agent protocol, 8-dimension audit, deliverable format
- `.claude/agents/playwright-cli-expert.md` — Confirmed playwright-cli command set, screenshot workflow, resize → screenshot pattern
- `tools/accounts/render/api_key.md` — Confirmed Render API key, existing service ID (to NOT reuse)

### Secondary (MEDIUM confidence)

- `sessions/Session_20260328_170000_dashboard_redesign_render_deploy.md` — clearCache requirement, deploy hook limitation, env var naming fix, Render owner ID `tea-d73ebos2kvos73aaeajg`
- `sessions/Session_20260327_211200_dashboard_render_deploy_responsive.md` — Initial deploy pattern, GitHub public repo pattern, Frankfurt region

### Tertiary (LOW confidence)

None — all findings directly verified from project files and session breadcrumbs.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all packages confirmed installed and in requirements.txt
- Architecture: HIGH — codebase fully read, template inheritance confirmed, workspace.py env var regex confirmed
- Pitfalls: HIGH — clearCache issue and env var naming issue documented from actual prior session failures
- Playwright QA: HIGH — playwright-cli confirmed installed at v1.59.0, agent confirmed available
- Render deployment: HIGH — exact API key, owner ID, pattern all from verified session breadcrumbs

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable tech, 30-day window; Render API and playwright-cli are stable)
