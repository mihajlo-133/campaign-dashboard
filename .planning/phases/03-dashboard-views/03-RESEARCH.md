# Phase 3: Dashboard Views — Research

**Researched:** 2026-04-04
**Domain:** FastAPI + Jinja2 + HTMX dashboard views, server-side rendered data drill-down
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Navigation architecture:**
- D-01: Separate pages per drill-down level with distinct URLs: `/` (overview), `/ws/{name}` (workspace), `/ws/{name}/campaign/{id}` (campaign detail)
- D-02: Text breadcrumb trail at top of each page: "All Workspaces > Enavra > Campaign A" — click any segment to jump back
- D-03: All campaigns shown on workspace page (active + draft) — no hiding of clean campaigns by default

**Overview page (/):**
- D-04: Workspace cards only — no global summary header/aggregation
- D-05: All workspace cards same size and layout — clean workspaces get green badge, not collapsed
- D-06: Each card shows: workspace name, broken lead count, campaign count, last-checked timestamp
- D-07: "Scan All" button lives in the topbar, always visible on every page

**Health visualization:**
- D-08: Traffic light dot (green/yellow/red) based on PERCENTAGE of broken leads — not raw count
- D-09: Thresholds: Green <2%, Yellow 2-10%, Red >10%
- D-10: Same percentage-based traffic light logic at every level (workspace cards, campaign rows)

**Campaign page layout:**
- D-11: Variable summary block on top ("cityName — 12 leads broken"), broken lead table below
- D-12: Campaign page also gets per-variable breakdown with counts

**Broken leads table:**
- D-13: Columns: email address, broken variables with current values (e.g. "cityName: [empty], niche: NO"), lead status (active/contacted/bounced)
- D-14: No "all payload variables" column — focus on broken vars only
- D-15: Paginated table, 25 leads per page — classic pagination with page numbers

**Scan trigger UX:**
- D-16: Global "Scan All" in topbar + per-workspace scan on workspace page + per-campaign scan on campaign page
- D-17: Button becomes spinner + disabled during scan. Page data refreshes via HTMX when scan completes
- D-18: Freshness indicator on all pages: timestamp + color (green <5min, yellow 5-15min, gray >15min)

### Claude's Discretion

- HTMX partial update strategy (full page swap vs targeted div replacement)
- Exact CSS styling within the existing design system (base.html variables)
- Responsive/mobile behavior
- Empty state displays (no campaigns, no broken leads)
- Error state displays (workspace API errors)
- Exact pagination component implementation

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VIEW-01 | All-workspaces overview — top-level entry point showing health status across all workspaces | Served by `/` route reading `get_cache().get_all()` → WorkspaceCard grid |
| VIEW-02 | Workspace-level rollup — shows all campaigns in a workspace with their QA status | Served by `/ws/{name}` route reading `get_cache().get_workspace(name)` → CampaignRow table |
| VIEW-03 | Campaign-level summary — shows per-variable breakdown of broken lead counts | Served by `/ws/{name}/campaign/{id}` route reading `issues_by_variable` from `CampaignQAResult` |
| VIEW-04 | Drill-down to per-lead issue list — shows which specific leads have broken variables | **REQUIRES MODEL EXTENSION**: `CampaignQAResult` currently stores only `broken_count` and `issues_by_variable`. Per-lead broken detail (email + var name + current value) is not stored. Planner must add a `broken_leads` list to the model and update `run_campaign_qa` to populate it. |
| VIEW-05 | "Last checked" timestamp displayed per campaign to confirm data freshness | `CampaignQAResult.last_checked` is already populated; route passes it to template; freshness color logic per D-18 |
| VIEW-06 | Severity badges — visual distinction for campaigns with many broken leads vs few | Traffic light dot using `broken_count / total_leads` percentage per D-08/D-09 |
| VIEW-07 | Three-level navigation: all workspaces → workspace → campaign → lead list | Breadcrumb component + URL structure D-01/D-02 |
| UX-02 | UI optimized for scanning hundreds/thousands of leads — clear data hierarchy, fast comprehension | Campaign table columns with truncated variable names + counts; pagination at 25/page |
| UX-03 | Mobile-responsive layout (desktop-first, but usable on tablet/phone) | CSS grid breakpoints per UI-SPEC: 3-col / 2-col / 1-col |

</phase_requirements>

---

## Summary

Phase 3 is a pure frontend rendering phase. All data is already computed by Phase 2 (QA engine + cache). The work is: (1) extend the data model to store per-lead broken detail for VIEW-04, (2) add three new routes consuming the cache, (3) write three new Jinja2 templates following the UI-SPEC design contract, and (4) wire HTMX scan triggers with partial page refreshes.

**The single most important discovery:** `CampaignQAResult` does not store per-lead broken detail. It tracks `broken_count` (integer) and `issues_by_variable` (dict of var → count), but not the list of broken leads with their email addresses and per-variable values. VIEW-04 requires this data. The planner must include a task to add a `broken_leads` list field to `CampaignQAResult` (and a new `BrokenLeadDetail` model) and update `run_campaign_qa` to populate it.

**Primary recommendation:** Treat this as two work streams — (1) model extension + QA engine update to capture per-lead detail, and (2) route + template build for all three views. Stream 1 is the prerequisite for VIEW-04 but not for VIEW-01, VIEW-02, VIEW-03 which can be built against the existing model.

---

## Standard Stack

### Core (Already Installed — No New Dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.135.3 | Route handlers, TemplateResponse | Established in Phase 1 |
| Jinja2 | 3.x (bundled) | Template rendering, inheritance from base.html | Established in Phase 1 |
| HTMX | 2.0.4 (CDN) | Partial page updates for scan triggers and pagination | Already loaded in base.html |
| Pydantic v2 | bundled with fastapi | Model extension for BrokenLeadDetail | Already in use |

**No new packages are required.** Phase 3 introduces zero new dependencies.

### New Model Required

A `BrokenLeadDetail` model must be added to `app/models/qa.py`:

```python
class BrokenLeadDetail(BaseModel):
    """Per-lead broken variable detail for drill-down view (VIEW-04)."""
    email: str
    lead_status: int          # Raw integer status from Instantly API
    broken_vars: dict[str, str | None]  # {varName: currentValue}
```

And `CampaignQAResult` must gain a new field:

```python
class CampaignQAResult(BaseModel):
    # ... existing fields ...
    broken_leads: list[BrokenLeadDetail] = []  # Per-lead detail for VIEW-04
```

---

## Architecture Patterns

### Recommended Project Structure (additions to existing)

```
prospeqt-email-qa/
├── app/
│   ├── models/
│   │   └── qa.py                  # ADD: BrokenLeadDetail, extend CampaignQAResult
│   ├── routes/
│   │   └── dashboard.py           # ADD: /ws/{name}, /ws/{name}/campaign/{id}, scan API routes
│   ├── services/
│   │   ├── qa_engine.py           # UPDATE: populate broken_leads in run_campaign_qa
│   │   └── cache.py               # No changes needed
│   └── templates/
│       ├── base.html              # UPDATE: add Scan All button to topbar
│       ├── dashboard.html         # REPLACE: overview page (workspace card grid)
│       ├── workspace.html         # NEW: workspace detail page
│       └── campaign.html          # NEW: campaign detail page with variable summary + broken leads table
├── tests/
│   ├── test_qa_engine.py          # UPDATE: add tests for broken_leads population
│   └── test_routes.py             # UPDATE: add tests for new routes
```

### Pattern 1: Route → Cache Read → TemplateResponse

All three new routes follow the same pattern: read from cache, compute display values (percentages, freshness), pass to template.

```python
# Source: established pattern from Phase 1 dashboard.py
@router.get("/ws/{ws_name}", response_class=HTMLResponse)
async def workspace_detail(request: Request, ws_name: str):
    result = await get_cache().get_workspace(ws_name)
    if result is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return templates.TemplateResponse(request, "workspace.html", {
        "workspace": result,
        "breadcrumbs": [("All Workspaces", "/"), (ws_name, None)],
    })
```

### Pattern 2: HTMX Scan Trigger → Partial HTML Response

Scan buttons POST to API endpoints that trigger background QA and return partial HTML fragments. HTMX swaps the fragment into the DOM.

```python
@router.post("/api/scan/ws/{ws_name}", response_class=HTMLResponse)
async def scan_workspace(request: Request, ws_name: str):
    await trigger_qa_workspace(ws_name)
    # Poll briefly (scan is async — may not be done)
    # Return current state as partial HTML fragment
    result = await get_cache().get_workspace(ws_name)
    return templates.TemplateResponse(request, "_partials/campaign_table.html", {
        "workspace": result
    })
```

The UI-SPEC defines this contract: scan endpoint returns outerHTML of the target element, HTMX replaces it.

**Note on async scan timing:** Scan triggers are fire-and-forget (the background task may still be running when the response is returned). Options:
1. Return current cached state immediately (simple, may show stale data)
2. Wait up to N seconds for the scan to complete before responding (better UX, adds latency)

Option 1 is simpler and matches the existing polling model. The freshness indicator communicates data age to the user. Recommend option 1 for the planner.

### Pattern 3: Pagination via HTMX Query Params

Pagination links use `hx-get="?page=N"` to load page N of broken leads without full page reload. The route reads `page: int = 1` as a query param and slices the broken leads list.

```python
@router.get("/ws/{ws_name}/campaign/{campaign_id}", response_class=HTMLResponse)
async def campaign_detail(request: Request, ws_name: str, campaign_id: str, page: int = 1):
    result = await get_cache().get_workspace(ws_name)
    campaign = next((c for c in result.campaigns if c.campaign_id == campaign_id), None)
    
    page_size = 25
    total_pages = max(1, math.ceil(len(campaign.broken_leads) / page_size))
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    page_leads = campaign.broken_leads[start:start + page_size]
    
    return templates.TemplateResponse(request, "campaign.html", {
        "campaign": campaign,
        "page_leads": page_leads,
        "page": page,
        "total_pages": total_pages,
    })
```

### Pattern 4: Health Percentage Computation (Template Filter or Route Logic)

The traffic light color depends on `broken_count / total_leads`. This can be computed in the route and passed to the template, or as a Jinja2 filter. Route-side computation is simpler (no filter registration needed):

```python
def health_class(broken: int, total: int) -> str:
    """Return CSS modifier class for traffic light dot."""
    if total == 0:
        return "gray"
    pct = broken / total
    if pct < 0.02:
        return "green"
    elif pct <= 0.10:
        return "yellow"
    return "red"
```

Pass as a utility function or inline it in the template with Jinja2 arithmetic.

### Pattern 5: Freshness Display

Freshness computation from a `datetime | None` to display text and CSS class:

```python
from datetime import datetime, timezone

def freshness_class(ts: datetime | None) -> str:
    if ts is None:
        return "gray"
    age_seconds = (datetime.now(timezone.utc) - ts).total_seconds()
    if age_seconds < 300:
        return "green"
    elif age_seconds < 900:
        return "amber"
    return "gray"
```

### Anti-Patterns to Avoid

- **Re-fetching Instantly API in route handlers:** Routes must only read from cache. Never call Instantly directly from a route — that defeats the entire caching architecture from Phase 2.
- **Storing per-lead broken detail in a separate cache namespace:** Keep it in `CampaignQAResult.broken_leads` — one model, one namespace, one serialization path.
- **Mutable default argument in Pydantic model:** `broken_leads: list[BrokenLeadDetail] = []` is fine in Pydantic v2 (it uses `default_factory` internally). Do not add `field(default_factory=list)` — Pydantic v2 handles this automatically.
- **Using asyncio.sleep() as a polling mechanism in scan routes:** Scan routes return immediately. Don't try to wait for scan completion in the HTTP request cycle.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTMX response format | Custom JS polling mechanism | HTMX `hx-post` + `hx-swap` | HTMX is already loaded; 3 lines of HTML attributes vs hundreds of lines of JS |
| Template inheritance | Copy-paste base.html into each template | `{% extends "base.html" %}` | Already established pattern; `{% block content %}` is the only override needed |
| Pagination offset math | Custom pagination library | Route-level slice `leads[start:end]` + `math.ceil` | Simple enough inline; no library adds value at this scale |
| Health color thresholds | CSS custom properties with dynamic values | Python function → CSS class string → static CSS rules | Dynamic CSS is brittle; mapping to pre-defined classes (`.health-dot--green`) is the established pattern |
| Toast notifications | Custom notification system | Existing `showToast()` from base.html | Already implemented; call `showToast(message, type)` from HTMX after-request events |

---

## Critical Gap: Per-Lead Broken Detail Not Stored

**This is the primary planning blocker for VIEW-04.**

**Current state:** `run_campaign_qa` in `qa_engine.py` iterates leads, calls `check_lead(payload, copy_vars)`, adds to `broken_lead_ids` set, and increments `issues_by_variable` counts. After the loop completes, **the per-lead detail (email, lead status, which variables were broken, what their values were) is not stored**. Only counts survive.

**Required state:** `CampaignQAResult.broken_leads` must be a list of `BrokenLeadDetail` objects, each with:
- `email: str`
- `lead_status: int` (raw Instantly status integer)
- `broken_vars: dict[str, str | None]` — maps variable name to its current value (empty string, None, or "NO")

**Impact on `run_campaign_qa`:** The loop body must be extended to capture per-lead detail when a lead has broken variables:

```python
broken_lead_details: list[BrokenLeadDetail] = []

for lead in leads:
    payload = lead.get("payload") or {}
    broken_vars_set = check_lead(payload, copy_vars)
    if broken_vars_set:
        broken_lead_ids.add(lead.get("id", lead.get("email", "")))
        for var_name in broken_vars_set:
            issues_by_variable[var_name] = issues_by_variable.get(var_name, 0) + 1
        # NEW: capture per-lead detail for VIEW-04
        broken_lead_details.append(BrokenLeadDetail(
            email=lead.get("email", ""),
            lead_status=lead.get("status", 0),
            broken_vars={v: payload.get(v) for v in broken_vars_set},
        ))

return CampaignQAResult(
    # ... existing fields ...
    broken_leads=broken_lead_details,  # NEW
)
```

**Memory consideration:** For a campaign with 5000 leads and 10% broken (500 leads), storing per-lead detail is ~50KB of strings — completely acceptable for an in-memory cache.

---

## Common Pitfalls

### Pitfall 1: Campaign Lookup by ID Across Workspace Cache

**What goes wrong:** The route `/ws/{name}/campaign/{id}` must find the correct `CampaignQAResult` from `WorkspaceQAResult.campaigns`. If the workspace has never been QA-scanned (only discovered by the discovery poll), `get_cache().get_workspace(name)` returns `None` and the campaign detail page 404s.

**Why it happens:** There are two separate cache namespaces: `_workspace_campaigns` (campaign lists from discovery poll) and `_workspace_results` (QA results from scan). The workspace detail page needs QA results, not just discovery data.

**How to avoid:** Check for `None` workspace result and render an appropriate "not yet scanned" state with a Scan button rather than a hard 404.

**Warning signs:** `/ws/{name}/campaign/{id}` returns 404 for valid workspaces that have never been manually scanned.

### Pitfall 2: HTMX Target ID Mismatch

**What goes wrong:** Scan button posts to `/api/scan/ws/{name}`, HTMX targets `#campaign-table`, but the partial response does not include an element with that ID or renders a different element structure.

**Why it happens:** The `hx-target` attribute on the button and the `id` attribute in the partial template must match exactly. If the partial template is rendered inside a wrapping element that includes the ID, but `hx-swap="outerHTML"` replaces the outer element, the ID disappears after the first swap.

**How to avoid:** Use `hx-swap="innerHTML"` to replace the contents of the target (keeping the ID), not `outerHTML` (which replaces the element including its ID). Or ensure the partial template always renders its outer element with the same ID. The UI-SPEC specifies `outerHTML` — so the partial HTML fragment returned by the server MUST include the target element's ID as the root element.

**Warning signs:** First scan works, second scan does nothing (element not found).

### Pitfall 3: Scan Returns Stale Data

**What goes wrong:** User clicks "Scan Workspace." HTMX gets a response immediately (fire-and-forget), but the background task hasn't finished yet. The refreshed partial shows the same (or no) data.

**Why it happens:** `trigger_qa_workspace()` returns immediately. The QA job runs asynchronously. The route reads from cache before the job completes.

**How to avoid:** One of two approaches:
1. After triggering, add a brief `await asyncio.sleep(0.5)` then read cache. This improves perceived responsiveness for small workspaces.
2. Return the triggered state with a freshness indicator showing "Scanning…" and let the user manually refresh when done.

Option 2 is the safer choice — never assume scan duration. The UI-SPEC's D-17 (button spinner) covers the scanning state feedback.

### Pitfall 4: Template Context Key Collisions

**What goes wrong:** Route passes `workspace` to the template, but Jinja2 `{% extends "base.html" %}` block also passes a variable named `request`. FastAPI's `TemplateResponse` requires `request` as the first positional argument (Phase 1 learned decision: "TemplateResponse uses Starlette 1.0 API: request as first arg, not inside context dict").

**How to avoid:** Pass `request` as the first argument, not inside the context dict. Double-check that no context key shadows reserved Jinja2 names.

### Pitfall 5: Missing `total_leads` for Percentage Calculation

**What goes wrong:** A workspace has been QA-scanned but the campaign's `total_leads` is 0 (no leads yet, or all filtered out). Dividing `broken_count / total_leads` raises ZeroDivisionError.

**How to avoid:** Always guard with `if total_leads > 0` before computing percentage. Render gray "no data" state when `total_leads == 0`.

### Pitfall 6: Lead Status Display (Integer to Label)

**What goes wrong:** Broken leads table shows raw integer status (`1`, `-1`, `3`) instead of human-readable labels ("Active", "Bounced", "Completed").

**Why it happens:** `BrokenLeadDetail.lead_status` is an integer. Template must convert it.

**How to avoid:** Define a mapping in the route context or as a Jinja2 filter:
```python
LEAD_STATUS_LABELS = {1: "Active", 2: "Paused", 3: "Completed", -1: "Bounced"}
```
Pass as template context or register as a Jinja2 global. Note: only status=1 (Active) leads are fetched per API-05, but bounced/completed leads may appear in cached results if the status changed after the scan.

---

## Code Examples

### Verified Patterns from Existing Codebase

#### TemplateResponse (Phase 1 established pattern)
```python
# Source: app/routes/dashboard.py — Starlette 1.0 API
return templates.TemplateResponse(request, "template.html", {"key": value})
# NOT: templates.TemplateResponse("template.html", {"request": request, "key": value})
```

#### Jinja2 Template Inheritance
```html
{# Source: app/templates/admin.html — established pattern #}
{% extends "base.html" %}
{% block title %}Page Title{% endblock %}
{% block extra_styles %}<style>/* page-specific CSS */</style>{% endblock %}
{% block content %}
  <!-- page content here -->
{% endblock %}
{% block extra_scripts %}<script>/* page-specific JS */</script>{% endblock %}
```

#### HTMX Scan Trigger
```html
{# Per UI-SPEC HTMX Interaction Contract #}
<button
  hx-post="/api/scan/ws/{{ workspace.workspace_name }}"
  hx-target="#campaign-table"
  hx-swap="outerHTML"
  hx-indicator="#scan-spinner">
  <span id="scan-spinner" class="htmx-indicator">
    <!-- spinner SVG -->
  </span>
  Scan Workspace
</button>
```

#### Traffic Light Dot (UI-SPEC component)
```html
<span class="health-dot health-dot--{{ health_class }}"></span>
```

```css
.health-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.health-dot--green { background: var(--green); }
.health-dot--yellow { background: var(--amber); }
.health-dot--red { background: var(--red); }
.health-dot--gray { background: var(--tx3); }
```

#### Variable Mini-Bar (UI-SPEC variable summary block)
```html
{% for var_name, count in campaign.issues_by_variable|dictsort(by='value', reverse=True) %}
<div class="var-row">
  <span class="var-name">{{ var_name }}</span>
  <span class="var-count">{{ count }} leads broken</span>
  <div class="var-bar-bg">
    <div class="var-bar-fill" style="width: {{ (count / campaign.total_leads * 100)|round(1) }}%"></div>
  </div>
</div>
{% endfor %}
```

#### Pagination Links with HTMX
```html
{# Target: #broken-leads-table, swap: outerHTML — per UI-SPEC #}
<div class="pagination" id="pagination">
  {% if page > 1 %}
  <a hx-get="?page={{ page - 1 }}" hx-target="#broken-leads-table" hx-swap="outerHTML">←</a>
  {% endif %}
  {% for p in range(1, total_pages + 1) %}
  <a hx-get="?page={{ p }}" hx-target="#broken-leads-table" hx-swap="outerHTML"
     class="{% if p == page %}active{% endif %}">{{ p }}</a>
  {% endfor %}
  {% if page < total_pages %}
  <a hx-get="?page={{ page + 1 }}" hx-target="#broken-leads-table" hx-swap="outerHTML">→</a>
  {% endif %}
</div>
```

---

## Scan API Endpoints — Required New Routes

The UI-SPEC specifies three scan endpoints that don't exist yet. The planner must create these:

| Method | Path | Action | HTMX Target |
|--------|------|--------|-------------|
| POST | `/api/scan/all` | `trigger_qa_all()` then return workspace grid partial | `#workspace-grid` |
| POST | `/api/scan/ws/{ws_name}` | `trigger_qa_workspace(ws_name)` then return campaign table partial | `#campaign-table` |
| POST | `/api/scan/ws/{ws_name}/campaign/{campaign_id}` | `trigger_qa_campaign(campaign_id, campaign, ws_name)` then return results partial | `#campaign-results` |

These can be added to `dashboard.py` or extracted to a new `app/routes/scan.py`.

**Challenge with scan API for campaign:** `trigger_qa_campaign(campaign_id, campaign, ws_name)` requires a `campaign` dict, not just the ID. The route must look up the campaign dict from the cache (either `get_workspace` result or `get_campaigns` discovery result).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pytest.ini` (check for `asyncio_mode = "auto"`) |
| Quick run command | `cd prospeqt-email-qa && pytest tests/test_routes.py tests/test_qa_engine.py -x -q` |
| Full suite command | `cd prospeqt-email-qa && pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VIEW-01 | GET `/` returns HTML with workspace cards | integration | `pytest tests/test_routes.py::test_overview_page -x` | ❌ Wave 0 |
| VIEW-02 | GET `/ws/{name}` returns campaign rows | integration | `pytest tests/test_routes.py::test_workspace_page -x` | ❌ Wave 0 |
| VIEW-03 | Campaign page shows variable breakdown | integration | `pytest tests/test_routes.py::test_campaign_page_variable_summary -x` | ❌ Wave 0 |
| VIEW-04 | Campaign page shows per-lead broken details | integration | `pytest tests/test_routes.py::test_campaign_page_broken_leads -x` | ❌ Wave 0 |
| VIEW-05 | Last-checked timestamp appears on page | integration | `pytest tests/test_routes.py::test_freshness_timestamp -x` | ❌ Wave 0 |
| VIEW-06 | Traffic light dot color matches threshold | unit | `pytest tests/test_routes.py::test_health_class_thresholds -x` | ❌ Wave 0 |
| VIEW-07 | Breadcrumb trail navigates three levels | integration | `pytest tests/test_routes.py::test_breadcrumb_navigation -x` | ❌ Wave 0 |
| UX-02 | Broken leads table shows email + broken vars | integration | Covered by VIEW-04 test | ❌ Wave 0 |
| UX-03 | Template includes responsive breakpoints | unit/smoke | `pytest tests/test_routes.py::test_mobile_meta_tag -x` | ❌ Wave 0 |
| MODEL | BrokenLeadDetail stored in run_campaign_qa | unit | `pytest tests/test_qa_engine.py::test_broken_leads_captured -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd prospeqt-email-qa && pytest tests/test_qa_engine.py tests/test_routes.py -x -q`
- **Per wave merge:** `cd prospeqt-email-qa && pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_routes.py` — extend with tests for new VIEW-01 through VIEW-07 routes (file exists, needs new test functions)
- [ ] `tests/test_qa_engine.py` — add test for `broken_leads` field population (file exists, needs new test function)
- [ ] Fixtures: `tests/fixtures/` — add mock `WorkspaceQAResult` with `broken_leads` populated for route tests

---

## Environment Availability

Step 2.6: SKIPPED (no new external dependencies — all required packages installed in Phase 1/2; no new services, runtimes, or CLIs needed for Phase 3).

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Template `request` in context dict | `request` as first positional arg to TemplateResponse | Starlette 1.0 (applied Phase 1) | Route code must use positional arg pattern |
| APScheduler 4.x | APScheduler 3.11.2 | Locked at Phase 0 | Do not import from `apscheduler.schedulers.background` — use `AsyncIOScheduler` only |

---

## Open Questions

1. **Campaign lookup for scan endpoint**
   - What we know: `trigger_qa_campaign(campaign_id, campaign, ws_name)` needs a `campaign` dict
   - What's unclear: Where does the scan route get the campaign dict? Options: (a) look up from `get_cache().get_workspace(ws_name).campaigns`, (b) look up from `get_cache().get_campaigns(ws_name)` discovery cache
   - Recommendation: Use `get_cache().get_workspace(ws_name).campaigns` first (has QA result shape); fall back to `get_cache().get_campaigns(ws_name)` (discovery shape). Both are campaign dicts from the Instantly API.

2. **Scan response: wait or return stale?**
   - What we know: Scan is fire-and-forget. Returning immediately may show stale data.
   - What's unclear: Is a brief `asyncio.sleep(1.0)` before reading cache acceptable?
   - Recommendation: Add `await asyncio.sleep(0.5)` after triggering scan before reading cache and returning partial. Cap at 0.5s to avoid request timeouts. Document this as a best-effort freshness improvement.

3. **Breadcrumb for campaign page: campaign name or ID?**
   - What we know: URL uses campaign ID (`/ws/{name}/campaign/{id}`). Breadcrumb should show campaign name.
   - What's unclear: Is campaign name always available in `CampaignQAResult.campaign_name`? Yes — it is populated by `run_campaign_qa` from `campaign["name"]`.
   - Recommendation: Use `CampaignQAResult.campaign_name` for the breadcrumb text.

---

## Sources

### Primary (HIGH confidence)
- Codebase: `prospeqt-email-qa/app/models/qa.py` — confirmed `CampaignQAResult` schema and missing `broken_leads` field
- Codebase: `prospeqt-email-qa/app/services/qa_engine.py` — confirmed `run_campaign_qa` loop structure; per-lead detail not currently stored
- Codebase: `prospeqt-email-qa/app/services/cache.py` — confirmed `QACache` API: `get_all()`, `get_workspace(name)`
- Codebase: `prospeqt-email-qa/app/services/poller.py` — confirmed trigger functions: `trigger_qa_all()`, `trigger_qa_workspace()`, `trigger_qa_campaign()`
- Codebase: `prospeqt-email-qa/app/templates/base.html` — confirmed CSS variables, HTMX CDN, toast system
- Codebase: `prospeqt-email-qa/app/routes/dashboard.py` — confirmed TemplateResponse pattern
- `.planning/phases/03-dashboard-views/03-CONTEXT.md` — locked decisions D-01 through D-18
- `.planning/phases/03-dashboard-views/03-UI-SPEC.md` — component specs, HTMX interaction contract, copywriting contract
- `.planning/REQUIREMENTS.md` — VIEW-01 through VIEW-07, UX-02, UX-03

### Secondary (MEDIUM confidence)
- FastAPI official docs: TemplateResponse Starlette 1.0 API (verified in Phase 1 STATE.md decision log)
- HTMX 2.x docs: `hx-swap="outerHTML"` behavior for scan triggers (verified in UI-SPEC)

---

## Metadata

**Confidence breakdown:**
- Model extension gap (VIEW-04): HIGH — confirmed by direct inspection of `qa.py` and `qa_engine.py`
- Route patterns: HIGH — established by Phase 1, directly readable in codebase
- HTMX patterns: HIGH — UI-SPEC specifies exact contracts; HTMX 2.x already loaded
- Template patterns: HIGH — base.html and existing templates confirm the inheritance model

**Research date:** 2026-04-04
**Valid until:** Stable indefinitely (no external API dependencies; pure frontend rendering phase)
