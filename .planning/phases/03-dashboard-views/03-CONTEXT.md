# Phase 3: Dashboard Views - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the dashboard views that let GTM engineers navigate from all-workspaces overview to per-lead issue detail. Four pages: overview (all workspaces), workspace detail (campaigns), campaign detail (variable breakdown + broken leads). No new backend logic — consume QA engine results from Phase 2's cache.

</domain>

<decisions>
## Implementation Decisions

### Navigation architecture
- **D-01:** Separate pages per drill-down level with distinct URLs: `/` (overview), `/ws/{name}` (workspace), `/ws/{name}/campaign/{id}` (campaign detail)
- **D-02:** Text breadcrumb trail at top of each page: "All Workspaces > Enavra > Campaign A" — click any segment to jump back
- **D-03:** All campaigns shown on workspace page (active + draft) with status badges — no hiding of clean campaigns by default

### Overview page (/)
- **D-04:** Workspace cards only — no global summary header/aggregation
- **D-05:** All workspace cards same size and layout regardless of health status — clean workspaces get green badge, not collapsed/minimized
- **D-06:** Each card shows: workspace name, broken lead count, campaign count, last-checked timestamp
- **D-07:** "Scan All" button lives in the topbar, always visible on every page

### Health visualization
- **D-08:** Traffic light dot (green/yellow/red) based on PERCENTAGE of broken leads, not raw count — 30 broken out of 300 is critical, 30 out of 5000 is a rounding error
- **D-09:** Thresholds: Green <2%, Yellow 2-10%, Red >10%
- **D-10:** Same percentage-based traffic light logic at every level (workspace cards, campaign rows)

### Campaign page layout
- **D-11:** Variable summary block on top ("cityName — 12 leads broken"), broken lead table below
- **D-12:** Campaign page also gets per-variable breakdown with counts

### Broken leads table
- **D-13:** Columns: email address, broken variables with current values (e.g. "cityName: [empty], niche: NO"), lead status (active/contacted/bounced)
- **D-14:** No "all payload variables" column — focus on broken vars only
- **D-15:** Paginated table, 25 leads per page — classic pagination with page numbers

### Scan trigger UX
- **D-16:** Global "Scan All" in topbar + per-workspace scan on workspace page + per-campaign scan on campaign page — buttons at every level
- **D-17:** Button becomes spinner + disabled during scan. Page data refreshes via HTMX when scan completes
- **D-18:** Freshness indicator on all pages: timestamp + color (green <5min, yellow 5-15min, gray >15min) — carried from Phase 2 D-21

### Claude's Discretion
- HTMX partial update strategy (full page swap vs targeted div replacement)
- Exact CSS styling within the existing design system (base.html variables)
- Responsive/mobile behavior
- Empty state displays (no campaigns, no broken leads)
- Error state displays (workspace API errors from D-14)
- Exact pagination component implementation

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing codebase (Phase 1 + 2 output)
- `prospeqt-email-qa/app/templates/base.html` — Design system: CSS variables, topbar, toast, Inter font, HTMX loaded
- `prospeqt-email-qa/app/templates/dashboard.html` — Current placeholder to replace
- `prospeqt-email-qa/app/routes/dashboard.py` — Current route at `/` to extend
- `prospeqt-email-qa/app/services/cache.py` — QACache with get_cache().get_all() returning GlobalQAResult
- `prospeqt-email-qa/app/services/poller.py` — trigger_qa_all(), trigger_qa_workspace(), trigger_qa_campaign()
- `prospeqt-email-qa/app/models/qa.py` — CampaignQAResult, WorkspaceQAResult, GlobalQAResult models
- `prospeqt-email-qa/app/services/qa_engine.py` — run_campaign_qa(), run_workspace_qa()
- `prospeqt-email-qa/app/models/instantly.py` — Lead, Campaign models with status enums

### Planning artifacts
- `.planning/PROJECT.md` — Project vision, core value
- `.planning/REQUIREMENTS.md` — VIEW-01 through VIEW-07, UX-02, UX-03
- `.planning/ROADMAP.md` — Phase 3 success criteria
- `.planning/phases/01-api-foundation/01-CONTEXT.md` — D-04 stack, D-05 admin gear icon, D-14 error badges
- `.planning/phases/02-qa-engine-background/02-CONTEXT.md` — D-08 result shape, D-17-D-21 scan triggers and freshness

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `base.html`: Full design system with CSS custom properties (--bg, --bg-el, --tx1, --tx2, --green, --amber, --red, --sh), topbar with gear icon, toast system, HTMX 2.0.4 loaded from CDN
- `dashboard.py`: FastAPI router with Jinja2 templates — extend with new routes
- `admin.html`/`login.html`: Reference for form patterns and modal dialogs within the design system
- QACache singleton: `get_cache()` returns thread-safe cache with `get_all()`, `get_workspace()`, `get_campaign()` methods

### Established Patterns
- Jinja2 template inheritance from `base.html` — all pages use `{% extends "base.html" %}`
- CSS-in-template via `{% block extra_styles %}` — no external CSS files
- JS-in-template via `{% block extra_scripts %}` — no build pipeline
- FastAPI routes return `TemplateResponse` with context dict

### Integration Points
- New routes in `dashboard.py`: `/ws/{name}`, `/ws/{name}/campaign/{id}`
- HTMX endpoints for partial updates: scan trigger → refresh data sections
- Cache reads: `get_cache().get_all()` for overview, `.get_workspace(name)` for workspace page
- Trigger calls: `trigger_qa_all()`, `trigger_qa_workspace(name)`, `trigger_qa_campaign(ws, id)` from poller module

</code_context>

<specifics>
## Specific Ideas

- Percentage-based health is the key UX insight: 30 broken/300 total = critical (10%), 30 broken/5000 total = noise (0.6%). The traffic light must reflect this ratio, not raw counts.
- Show both the percentage AND raw count on cards/rows: "3.2% (12/375)" so users understand the ratio and the magnitude
- Breadcrumb trail is essential for the separate-pages approach — no dead ends per success criteria #5
- Variable summary block on campaign page should visually call out which variables are worst (most broken leads)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-dashboard-views*
*Context gathered: 2026-04-04*
