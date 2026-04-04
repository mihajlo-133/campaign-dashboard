# Phase 4: UX Polish + Deployment - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Visual polish of the existing dashboard UI, Playwright-based QA validation at three viewports with interaction flow testing, and production deployment to Render with all 6 Prospeqt workspaces pre-configured. No new features — refinement and shipping of what's built.

</domain>

<decisions>
## Implementation Decisions

### Visual polish scope
- **D-01:** Refine the current design system — do not overhaul. Improve spacing, typography weight, hover states, transitions (200-300ms eases), and consistency across all 6 templates (base, login, admin, dashboard, workspace, campaign).
- **D-02:** No dark mode. Light theme only. Internal tool, keep it simple.
- **D-03:** UX expert agent and Claude have full discretion on specific visual improvements. No user-specified pet peeves — just make it polished.

### Playwright QA strategy
- **D-04:** Directory structure for Playwright tests/screenshots is Claude's discretion.
- **D-05:** Screenshots validated by the `ux-design-expert` agent — no manual human review step required.
- **D-06:** Playwright tests include both static screenshots at 3 viewports (1440x900, 768x1024, 375x812) AND full interaction flow: click scan button → verify loading spinner appears → wait for HTMX swap → confirm results update.

### Render deployment
- **D-07:** New Render service — do NOT deploy to the existing `campaign-dashboard` service (srv-d73efrfdiees73erakqg). The old monolithic dashboard stays untouched.
- **D-08:** Render free tier. An uptime bot will keep it warm (out of scope for this phase).
- **D-09:** Follow the proven deployment pattern from prior sessions:
  - API keys as env vars (naming: `WORKSPACE_<NAME>_API_KEY=<key>`, matching Phase 1 D-13)
  - Auto-detect Render vs local via `PORT` env var presence
  - Bind `0.0.0.0` on Render, `127.0.0.1` locally
  - Public GitHub repo (no secrets in code), auto-deploy on push
  - Always deploy with `clearCache: "clear"` via Render REST API (Docker layer caching caused stale code in prior deploys)
- **D-10:** 6 Prospeqt workspace API keys set manually in Render dashboard UI. No keys in code or render.yaml.
- **D-11:** Render API key and deploy tooling already available at `tools/accounts/render/api_key.md`.

### UX expert review process
- **D-12:** The `ux-design-expert` agent runs as a post-implementation gate after every piece of frontend work — not just once at the end.
- **D-13:** UX expert agent takes Playwright screenshots, checks all 3 viewports, and clicks through the UI to verify everything works as planned.
- **D-14:** Claude decides when to stop iterating on UX expert feedback — stop when fixes hit diminishing returns (cosmetic, not structural).

### Claude's Discretion
- Playwright test directory structure (D-04)
- Specific visual polish improvements — typography, spacing, shadows, transitions (D-03)
- Number of UX expert review iterations per deliverable (D-14)
- GitHub repo setup for the new Render service (new repo vs monorepo subfolder deploy)
- Exact Render service configuration (region, instance type within free tier)
- Health check endpoint design

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior deployment sessions (deployment patterns and lessons learned)
- `sessions/Session_20260328_170000_dashboard_redesign_render_deploy.md` — Render dual-mode API keys, cache busting, env var naming, deploy workflow
- `sessions/Session_20260327_211200_dashboard_render_deploy_responsive.md` — Initial Render deployment, GitHub repo setup, cold start behavior, mobile responsive fixes

### Render account config
- `tools/accounts/render/api_key.md` — Render API key, existing service ID (for reference, NOT for reuse), deploy hook pattern

### Existing codebase (what's being polished)
- `prospeqt-email-qa/app/templates/base.html` — Design system CSS variables, shared layout, existing breakpoints
- `prospeqt-email-qa/app/templates/dashboard.html` — Overview page template
- `prospeqt-email-qa/app/templates/workspace.html` — Workspace detail template
- `prospeqt-email-qa/app/templates/campaign.html` — Campaign detail template
- `prospeqt-email-qa/Procfile` — Existing gunicorn+uvicorn config for Render

### Prior phase decisions
- `.planning/phases/01-api-foundation/01-CONTEXT.md` — D-09/D-12/D-13: env var API key storage pattern, D-05/D-06: admin panel UX
- `.planning/phases/03-dashboard-views/03-CONTEXT.md` — D-08/D-09/D-10: health badge thresholds, D-16/D-17/D-18: scan trigger UX

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- CSS custom properties in `base.html`: `--bg`, `--bg-el`, `--tx1`, `--tx2`, `--blue`, `--green`, `--amber`, `--red`, `--sh`, `--sh-md`
- Responsive breakpoints already at 767px and 1023px in base.html, dashboard.html, workspace.html
- Procfile already configured for gunicorn+uvicorn
- Health class/freshness utility functions in `dashboard.py`

### Established Patterns
- Jinja2 template inheritance from `base.html`
- HTMX for partial page updates (scan triggers, pagination)
- CSS-only responsive design (no JS breakpoint detection)
- Vanilla JS only — no frameworks

### Integration Points
- `app/main.py` — FastAPI app entry point (uvicorn serves this)
- `app/services/workspace.py` — Workspace registry reads from env vars (already Render-compatible)
- All 6 templates extend `base.html` — CSS changes propagate through inheritance

</code_context>

<specifics>
## Specific Ideas

- Prior Render deploys used `clearCache: "clear"` via REST API — mandatory for this deploy too (Docker layer caching caused stale code bugs)
- Free tier spins down after 15min inactivity with ~30s cold start — uptime bot planned but out of scope
- The old dashboard at `campaign-dashboard-0zra.onrender.com` stays live and untouched

</specifics>

<deferred>
## Deferred Ideas

- Uptime bot setup (e.g., UptimeRobot) to keep free tier warm — separate task after deployment
- Custom domain for the new Render service
- Deprecating/removing the old `campaign-dashboard` Render service

</deferred>

---

*Phase: 04-ux-polish-deployment*
*Context gathered: 2026-04-04*
