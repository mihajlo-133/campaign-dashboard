---
phase: 03-dashboard-views
plan: "02"
subsystem: dashboard-views
tags: [dashboard, htmx, jinja2, routes, templates, responsive, health-dots]
status: complete
completed: "2026-04-04"
duration_minutes: 5
tasks_completed: 2
files_changed: 5
requires:
  - "03-01: BrokenLeadDetail model and CampaignQAResult.broken_leads"
  - "02-02: QA engine with broken_count and issues_by_variable"
provides:
  - "Overview page (/) with workspace card grid and health dots"
  - "Workspace detail page (/ws/{name}) with campaign table and breadcrumb"
  - "Scan All button in topbar (base.html) triggering POST /api/scan/all"
  - "Scan endpoints: POST /api/scan/all and POST /api/scan/ws/{ws_name}"
  - "Utility functions: health_class, health_pct, freshness_class, freshness_text"
affects:
  - "03-03: Campaign detail view will link from workspace table rows"
tech_stack_added: []
tech_stack_patterns:
  - "HTMX hx-post with hx-target and hx-swap for partial DOM updates"
  - "Jinja2 template inheritance with base.html providing shared CSS components"
  - "Health dot traffic light: green <2%, yellow 2-10%, red >10% broken/total ratio"
  - "Freshness indicator: green <5min, amber 5-15min, gray >15min since last scan"
  - "Responsive CSS grid: 3-col (1024px+), 2-col (tablet), 1-col (mobile)"
key_files_created:
  - prospeqt-email-qa/app/templates/workspace.html
key_files_modified:
  - prospeqt-email-qa/app/templates/base.html
  - prospeqt-email-qa/app/templates/dashboard.html
  - prospeqt-email-qa/app/routes/dashboard.py
  - prospeqt-email-qa/tests/test_routes.py
decisions:
  - "dashboard.py scan endpoints return full-page template (not partial fragment) — HTMX targets the correct element by ID, keeping templates simple"
  - "workspace_detail returns not_scanned=True when cache miss — avoids 404 for valid workspaces not yet scanned"
  - "Scan All button targets #workspace-grid for HTMX swap — consistent with the id used in dashboard.html"
requirements_satisfied: [VIEW-01, VIEW-02, VIEW-05, VIEW-06, VIEW-07, UX-02, UX-03]
---

# Phase 03 Plan 02: Overview and Workspace Detail Views Summary

Built the all-workspaces overview page and workspace campaign-table detail page with HTMX scan triggers, health traffic-light dots, freshness indicators, breadcrumb navigation, and responsive grid layout.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Add Scan All button to base.html topbar + utility functions + scan routes to dashboard.py | b77636b | app/templates/base.html, app/routes/dashboard.py |
| 2 | Build dashboard.html overview template and workspace.html detail template with tests | e19cda6 | app/templates/dashboard.html, app/templates/workspace.html, tests/test_routes.py |

## What Was Built

**base.html additions:**
- Scan All button in topbar with HTMX `hx-post="/api/scan/all"` targeting `#workspace-grid`
- CSS components: `.scan-btn-primary`, `.scan-btn-secondary`, `.health-dot` (green/yellow/red/gray), `.breadcrumb-bar`, `.status-badge` (active/draft), `.freshness`, `.page-shell`
- HTMX `htmx:responseError` handler showing toast on failed scan requests

**dashboard.py additions:**
- `health_class(broken, total)`: Returns "green" (<2%), "yellow" (2-10%), "red" (>10%), "gray" (no data)
- `health_pct(broken, total)`: Returns formatted percentage string
- `freshness_class(ts)`: Returns "green" (<5min), "amber" (5-15min), "gray" (>15min or None)
- `freshness_text(ts)`: Returns human-readable string ("Just now", "3 min ago", "2h ago", "Never scanned")
- `total_leads_for_workspace(ws)`: Sums total_leads across campaigns
- `GET /`: Overview with workspace cards built from `get_cache().get_all()`
- `GET /ws/{ws_name}`: Campaign table built from `get_cache().get_workspace(ws_name)`; returns not_scanned=True on cache miss
- `POST /api/scan/all`: Calls `trigger_qa_all()`, returns refreshed workspace grid HTML
- `POST /api/scan/ws/{ws_name}`: Calls `trigger_qa_workspace(ws_name)`, returns refreshed campaign table HTML

**dashboard.html (overview):**
- Workspace card grid with 3-col/2-col/1-col responsive breakpoints (1024px, 768px)
- Each card: health dot, workspace name, broken percentage, campaign count, freshness indicator, per-workspace Scan button
- Empty state: "No workspaces configured" with link to /admin

**workspace.html (new):**
- Breadcrumb: "All Workspaces > {ws_name}" with clickable "All Workspaces" link
- Workspace-level summary row: health dot + broken leads / campaign count
- Campaign table: Name (with health dot + link), Status badge, Broken Leads count, Variables Affected, Last Checked, Scan button per row
- Not-scanned state: prompt to click "Scan Workspace"
- Empty campaigns state: "No campaigns found" message
- Responsive: hides Variables column on tablet, stacks rows on mobile

## Verification

```
$ cd prospeqt-email-qa && .venv/bin/python -m pytest tests/ -x -q
97 passed, 6 warnings in 0.92s
```

97 tests pass (9 new route tests added). Zero failures.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all template variables are wired to real cache data. The workspace page renders campaign data from `get_cache().get_workspace()` which is populated by the QA engine. The `not_scanned=True` state is intentional UX for workspaces with no scan yet — it is not a stub.

## Self-Check: PASSED

Files confirmed present:
- `prospeqt-email-qa/app/templates/base.html` — contains "Scan All", `hx-post="/api/scan/all"`, `.scan-btn-primary`, `.health-dot`, `.breadcrumb-bar`, `.status-badge--active`
- `prospeqt-email-qa/app/routes/dashboard.py` — contains `def health_class(`, `def freshness_class(`, `async def workspace_detail(`, `async def scan_all(`, `async def scan_workspace(`, `get_cache().get_all()`
- `prospeqt-email-qa/app/templates/dashboard.html` — contains `id="workspace-grid"`, `health-dot--{{ ws.health }}`, `No workspaces configured`, `ws.freshness_txt`
- `prospeqt-email-qa/app/templates/workspace.html` — contains `id="campaign-table"`, `breadcrumb-bar`, `All Workspaces`, `Scan Workspace`, `No campaigns found`
- `prospeqt-email-qa/tests/test_routes.py` — contains `def test_overview_page_has_workspace_grid`, `def test_workspace_page_returns_html`, `def test_health_class_thresholds`

Commits confirmed: b77636b (Task 1), e19cda6 (Task 2)
