# Phase 3: Dashboard Views - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** 03-dashboard-views
**Areas discussed:** Drill-down layout, Health visualization, Broken leads detail, Scan trigger UX

---

## Drill-down Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Single page with drill-down | Everything on one page, HTMX swaps sections inline | |
| Separate pages per level | Each level is its own URL: /, /ws/{name}, /ws/{name}/campaign/{id} | ✓ |
| Hybrid: overview + HTMX panels | Overview always visible, HTMX loads details below | |

**User's choice:** Separate pages per level
**Notes:** Clean URLs, bookmarkable, browser back works

| Option | Description | Selected |
|--------|-------------|----------|
| Summary header + workspace cards | Global aggregation header above cards | |
| Workspace cards only | Just cards, no global summary | ✓ |
| You decide | Claude's discretion | |

**User's choice:** Workspace cards only

| Option | Description | Selected |
|--------|-------------|----------|
| Same size, green badge | All cards same layout, green check for clean | ✓ |
| Collapsed/muted when clean | Clean workspaces shown as compact one-liners | |
| You decide | Claude's discretion | |

**User's choice:** Same size, green badge

| Option | Description | Selected |
|--------|-------------|----------|
| Text breadcrumb trail | "All Workspaces > Enavra > Campaign A" at top | ✓ |
| Just a back arrow | Single ← Back link | |
| You decide | Claude's discretion | |

**User's choice:** Text breadcrumb trail

| Option | Description | Selected |
|--------|-------------|----------|
| All campaigns with status badges | Show every active/draft campaign | ✓ |
| Only campaigns with issues | Hide clean campaigns by default | |
| You decide | Claude's discretion | |

**User's choice:** All campaigns with status badges

| Option | Description | Selected |
|--------|-------------|----------|
| Name + broken count + campaign count + last checked | Full context at a glance | ✓ |
| Name + broken count + health badge only | Minimal card info | |
| You decide | Claude's discretion | |

**User's choice:** Name + broken count + campaign count + last checked

| Option | Description | Selected |
|--------|-------------|----------|
| Variable summary on top, lead table below | Summary block then scrollable table | ✓ |
| Side by side | Sidebar + main content | |
| You decide | Claude's discretion | |

**User's choice:** Variable summary on top, lead table below

---

## Health Visualization

| Option | Description | Selected |
|--------|-------------|----------|
| Traffic light dot (green/yellow/red) | Simple colored dot based on thresholds | ✓ (modified) |
| Color-coded broken count | Number itself is colored | |
| Background tint on card | Entire card gets subtle tint | |
| You decide | Claude's discretion | |

**User's choice:** Traffic light dot — but based on PERCENTAGE not raw count. "If I have 30 broken its critical if I have 300 leads but its a rounding error if I have 5000 leads."

| Option | Description | Selected |
|--------|-------------|----------|
| Green <1%, Yellow 1-5%, Red >5% | Tight thresholds | |
| Green <2%, Yellow 2-10%, Red >10% | More relaxed | ✓ |
| Green 0%, Yellow >0 and <5%, Red >=5% | Strictest — any broken = yellow | |
| You decide | Claude's discretion | |

**User's choice:** Green <2%, Yellow 2-10%, Red >10%

| Option | Description | Selected |
|--------|-------------|----------|
| Same percentage logic | Consistent thresholds at all levels | ✓ |
| Raw count at campaign level | Show "12/200" with colors | |

**User's choice:** Same percentage logic at all levels

---

## Broken Leads Detail

| Option | Description | Selected |
|--------|-------------|----------|
| Email address | Lead's email | ✓ |
| Broken variables + current values | Which vars broken and current content | ✓ |
| Lead status | Active/contacted/bounced | ✓ |
| All payload variables | Every variable, not just broken | |

**User's choice:** Email, broken vars + values, lead status (not all payload)

| Option | Description | Selected |
|--------|-------------|----------|
| Paginated table (25 per page) | Classic pagination | ✓ |
| Show all, browser scrolls | Render everything | |
| You decide | Claude's discretion | |

**User's choice:** Paginated table, 25 per page

---

## Scan Trigger UX

| Option | Description | Selected |
|--------|-------------|----------|
| In the topbar, always visible | Global action next to gear icon | ✓ |
| On the overview page only | Contextual per page | |
| Both: topbar + contextual | Most discoverable | |

**User's choice:** Topbar, always visible

| Option | Description | Selected |
|--------|-------------|----------|
| Button becomes spinner + disable | Simple, clear loading state | ✓ |
| Toast notification with progress | Fire-and-forget with toast updates | |
| You decide | Claude's discretion | |

**User's choice:** Button becomes spinner + disabled during scan

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, scan buttons at every level | Overview + workspace + campaign | ✓ |
| Only global scan in topbar | One button for everything | |
| You decide | Claude's discretion | |

**User's choice:** Scan buttons at every level

---

## Claude's Discretion

- HTMX partial update strategy
- Exact CSS styling
- Responsive/mobile behavior
- Empty state displays
- Error state displays
- Pagination component implementation

## Deferred Ideas

None — discussion stayed within phase scope
