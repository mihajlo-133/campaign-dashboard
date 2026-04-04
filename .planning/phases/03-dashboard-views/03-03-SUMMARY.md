---
phase: 03-dashboard-views
plan: "03"
subsystem: dashboard-views
tags: [dashboard, htmx, jinja2, routes, templates, pagination, breadcrumb, campaign-detail]
status: complete
completed: "2026-04-04"
duration_minutes: 6
tasks_completed: 2
files_changed: 3
requires:
  - "03-01: BrokenLeadDetail model and CampaignQAResult.broken_leads"
  - "03-02: Overview + workspace pages, utility functions, base.html CSS"
provides:
  - "Campaign detail page (/ws/{ws_name}/campaign/{campaign_id}) with variable summary and broken leads table"
  - "POST /api/scan/ws/{ws_name}/campaign/{campaign_id} per-campaign scan endpoint"
  - "PAGE_SIZE=25 HTMX pagination with #broken-leads-table targeting"
  - "Three-level breadcrumb: All Workspaces > {workspace} > {campaign}"
  - "format_var_value: None -> [missing], empty -> [empty], NO -> NO display"
affects:
  - "04-admin: campaign drill-down links from workspace table rows are now live"
tech_stack_added: []
tech_stack_patterns:
  - "HTMX hx-get pagination targeting inner div (#broken-leads-table outerHTML swap) vs full-page targets"
  - "Campaign scan endpoint calls campaign_detail() handler directly — avoids duplicating template render logic"
  - "Variable bar width computed as percentage of total_leads in Python, passed to template as float"
key_files_created:
  - prospeqt-email-qa/app/templates/campaign.html
key_files_modified:
  - prospeqt-email-qa/app/routes/dashboard.py
  - prospeqt-email-qa/tests/test_routes.py
decisions:
  - "scan_campaign endpoint calls campaign_detail() handler directly — avoids duplicating template render logic"
  - "Variable bar pct computed per campaign.total_leads — shows proportion of total leads affected, not proportion of broken leads"
  - "HTMX pagination targets #broken-leads-table (not #campaign-results) — allows page flip without losing variable summary block"
requirements-completed: [VIEW-03, VIEW-04, VIEW-05, VIEW-07, UX-02]
duration: 6min
completed: "2026-04-04"
---

# Phase 03 Plan 03: Campaign Detail Page with Variable Summary and Broken Leads Table

**Campaign drill-down page with per-variable bar chart, paginated broken leads table (25/page), HTMX scan trigger, and three-level breadcrumb via FastAPI/Jinja2/HTMX**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-04T15:18:00Z
- **Completed:** 2026-04-04T15:21:02Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Campaign detail page renders variable breakdown with count and visual percentage bars
- Broken leads table shows email, broken variable names with display values ([empty]/[missing]/NO), and lead status
- HTMX pagination at 25 leads per page targeting `#broken-leads-table` for partial DOM swap
- Three-level breadcrumb: All Workspaces (clickable) > {workspace} (clickable) > {campaign name}
- Scan Campaign button wired with HTMX POST to `/api/scan/ws/{ws_name}/campaign/{campaign_id}`
- Clean "All clear" state and "Not yet scanned" empty state handled
- 7 new route tests covering breadcrumb, data rendering, clean state, scan endpoint

## Task Commits

Each task was committed atomically:

1. **Task 1: Add campaign detail route and campaign scan endpoint** - `db564b6` (feat)
2. **Task 2: Create campaign.html template and add route tests** - `bc46ef6` (feat)

## Files Created/Modified

- `prospeqt-email-qa/app/routes/dashboard.py` - Added `campaign_detail`, `scan_campaign`, `PAGE_SIZE=25`, `format_var_value`; imported `trigger_qa_campaign`
- `prospeqt-email-qa/app/templates/campaign.html` - Full campaign detail template with variable summary, broken leads table, pagination, breadcrumb, HTMX wiring
- `prospeqt-email-qa/tests/test_routes.py` - 7 new tests for campaign routes (104 total, all pass)

## Decisions Made

- `scan_campaign` endpoint calls `campaign_detail()` handler directly rather than re-implementing template render — avoids code duplication, ensures scan result and GET result are rendered identically
- Variable bar percentage computed as `count / campaign.total_leads * 100` (proportion of total leads affected), not proportion of broken leads — gives more informative visual signal
- HTMX pagination targets `#broken-leads-table` (not `#campaign-results`) — allows flipping pages without clearing the variable summary block above

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all template variables are wired to real data from `CampaignQAResult`. The `not_scanned=True` state is intentional UX for campaigns not yet in the QA cache — not a stub.

## Verification

```
$ cd prospeqt-email-qa && .venv/bin/python -m pytest tests/ -x -q
104 passed, 6 warnings in 1.04s
```

104 tests pass. 7 new campaign route tests added:
- `test_campaign_page_returns_html` — breadcrumb + status 200
- `test_campaign_page_has_results_container` — `#campaign-results` present
- `test_campaign_page_not_scanned_state` — "Not yet scanned" for unknown campaign
- `test_campaign_page_with_data` — variable summary + broken leads with `[empty]` display value
- `test_campaign_page_clean_state` — "All clear" when broken_count=0
- `test_breadcrumb_three_levels` — all three clickable breadcrumb segments
- `test_scan_campaign_endpoint` — POST to `/api/scan/ws/{name}/campaign/{id}` returns HTML

## Self-Check: PASSED

Files confirmed:
- `prospeqt-email-qa/app/routes/dashboard.py` — contains `async def campaign_detail(`, `async def scan_campaign(`, `PAGE_SIZE = 25`, `trigger_qa_campaign`, `def format_var_value(`, `"[missing]"`, `"[empty]"`, `math.ceil(total_broken_count / PAGE_SIZE)`
- `prospeqt-email-qa/app/templates/campaign.html` — contains `id="campaign-results"`, `id="broken-leads-table"`, `Variable Issues`, `Broken Leads`, `All clear`, `Scan Campaign`, `broken-var-value`, `pagination`, `hx-get`, `breadcrumb-bar`
- `prospeqt-email-qa/tests/test_routes.py` — contains `def test_campaign_page_with_data`, `def test_campaign_page_clean_state`, `def test_breadcrumb_three_levels`

Commits confirmed:
- `db564b6` — Task 1 (campaign detail route + scan endpoint)
- `bc46ef6` — Task 2 (campaign.html template + tests)

---
*Phase: 03-dashboard-views*
*Completed: 2026-04-04*
