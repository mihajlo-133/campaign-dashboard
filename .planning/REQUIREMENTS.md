# Requirements: Email QA Dashboard

**Defined:** 2026-04-04
**Core Value:** No campaign launches with broken personalization variables.

## User Persona

**GTM Engineer** — builds campaigns in Clay, pushes lead data with variables into Instantly campaigns, and is responsible for launch readiness. Needs to verify that every lead's variables are complete and correct before hitting "go."

**User Journey:**
1. Engineer finishes a Clay table, pushes 500 leads into an Instantly campaign
2. Opens the QA dashboard to check if all variables landed correctly
3. Sees the campaign (maybe in "drafted" status), triggers a check
4. Dashboard shows issue summary: "Campaign X — 12 leads have broken `{{cityName}}`, 3 leads have broken `{{companyRevenue}}`"
5. Engineer drills down to see which specific leads are broken
6. Goes back to Clay/Instantly to fix the data, re-pushes
7. Runs the check again — all green, safe to launch

## v1 Requirements

### API Integration

- [ ] **API-01**: System fetches all campaigns from configured Instantly workspaces via v2 API
- [ ] **API-02**: System filters campaigns by status — only active (status=1) and draft (status=0) campaigns are shown; paused (status=2) and completed (status=3) are excluded
- [ ] **API-03**: System extracts sequence copy from inline `campaign.sequences[].steps[].variants[].body` and `.subject` fields (no separate API call needed)
- [ ] **API-04**: System fetches all leads from filtered campaigns via POST `/api/v2/leads/list` endpoint with cursor pagination
- [ ] **API-05**: System filters leads to active-only using lead `status` field (status=1 is active; exclude status=3 completed, status=-1 bounced/error)
- [ ] **API-06**: System reads lead variables from `lead.payload` dict (key-value pairs attached to each lead)
- [ ] **API-07**: System respects Instantly rate limits (100 req/sec, 6000 req/min per workspace) with per-workspace throttling

### QA Engine

- [ ] **QA-01**: System extracts all `{{variableName}}` patterns from campaign sequence copy, excluding `{{RANDOM | ...}}` spin syntax and `{{accountSignature}}` (system variable)
- [ ] **QA-02**: System matches extracted copy variables against `lead.payload` keys (case-sensitive)
- [ ] **QA-03**: System flags leads where a copy-referenced variable is empty string
- [ ] **QA-04**: System flags leads where a copy-referenced variable is null/missing
- [ ] **QA-05**: System flags leads where a copy-referenced variable has the value "NO" (sentinel value from enrichment tools)
- [ ] **QA-06**: System produces a per-campaign issue summary: count of broken leads grouped by variable name

### Dashboard Views

- [ ] **VIEW-01**: All-workspaces overview — top-level entry point showing health status across all workspaces
- [ ] **VIEW-02**: Workspace-level rollup — shows all campaigns in a workspace with their QA status
- [ ] **VIEW-03**: Campaign-level summary — shows per-variable breakdown of broken lead counts
- [ ] **VIEW-04**: Drill-down to per-lead issue list — shows which specific leads have broken variables (email + broken variable names + current values)
- [ ] **VIEW-05**: "Last checked" timestamp displayed per campaign to confirm data freshness
- [ ] **VIEW-06**: Severity badges — visual distinction for campaigns with many broken leads vs few (e.g., color-coded thresholds)
- [ ] **VIEW-07**: Three-level navigation: all workspaces → workspace → campaign → lead list

### Operations

- [ ] **OPS-01**: Manual "run check" trigger at all-workspaces level
- [ ] **OPS-02**: Manual "run check" trigger at per-workspace level
- [ ] **OPS-03**: Manual "run check" trigger at per-campaign level
- [ ] **OPS-04**: Background polling discovers new campaigns and runs QA checks at configurable interval
- [ ] **OPS-05**: Background poller is resilient — wraps exceptions, continues running, logs errors
- [ ] **OPS-06**: Dashboard shows last-refresh timestamp from background poller (visible to users)

### Admin & Access

- [ ] **ADM-01**: Admin panel to add new Instantly workspaces by providing workspace name + API key
- [ ] **ADM-02**: Admin panel to remove existing workspaces
- [ ] **ADM-03**: Admin panel protected by simple password authentication
- [ ] **ADM-04**: QA viewing is open access — no login required to see results
- [x] **ADM-05**: API keys stored server-side with file-based persistence (survives app restarts, supports runtime add/remove)

### UX & Visual Design

- [ ] **UX-01**: Dashboard has polished, professional visual design (luxury aesthetic)
- [ ] **UX-02**: UI is optimized for scanning hundreds/thousands of leads — clear data hierarchy, fast comprehension
- [ ] **UX-03**: Mobile-responsive layout (desktop-first, but usable on tablet/phone)
- [ ] **UX-04**: Visual QA validated with Playwright screenshots at multiple viewports before shipping
- [ ] **UX-05**: UX design expert agent consulted during frontend phases for evidence-based design review

### Infrastructure

- [x] **INF-01**: Modular codebase — routes, API clients, QA logic, templates in separate modules
- [x] **INF-02**: Deployable to Render as a standard Python web app
- [x] **INF-03**: No hardcoded API keys in source code
- [x] **INF-04**: Project pushed to GitHub as its own repository (or directory)

## v2 Requirements

### Alerting

- **ALRT-01**: Slack webhook notification when new QA issues are detected during background poll
- **ALRT-02**: Configurable alert thresholds (e.g., only alert when >N leads are broken)

### Export

- **EXP-01**: CSV export of broken leads per campaign (email, broken variables, current values)

### Advanced Operations

- **AOPS-01**: Configurable poll interval per workspace (high-priority clients checked more often)
- **AOPS-02**: Variable discovery view — full variable inventory per campaign
- **AOPS-03**: Bulk actions from dashboard (pause campaigns, etc.)

### Platform Expansion

- **PLAT-01**: EmailBison integration
- **PLAT-02**: Smartlead integration

## Out of Scope

| Feature | Reason |
|---------|--------|
| Write-back to Instantly (edit lead variables) | Scope explosion, bidirectional API complexity, risk of corrupting live data |
| User accounts / individual logins | Disproportionate complexity for 2-4 person team; simple admin password sufficient |
| Real-time pre-upload validation | Different product surface — dashboard validates what's in Instantly, not what's about to be uploaded |
| Email deliverability metrics | Different concern; already handled by Prospeqt outreach dashboard |
| Historical QA run logs | Storage/indexing complexity for low daily value; last-check timestamp sufficient for v1 |
| AI-powered automatic lead fixing | Enrichment quality/cost/responsibility concerns — flag issues, let team decide corrections |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| API-01 | Phase 1 | Pending |
| API-02 | Phase 1 | Pending |
| API-03 | Phase 1 | Pending |
| API-04 | Phase 1 | Pending |
| API-05 | Phase 1 | Pending |
| API-06 | Phase 1 | Pending |
| API-07 | Phase 1 | Pending |
| QA-01 | Phase 2 | Pending |
| QA-02 | Phase 2 | Pending |
| QA-03 | Phase 2 | Pending |
| QA-04 | Phase 2 | Pending |
| QA-05 | Phase 2 | Pending |
| QA-06 | Phase 2 | Pending |
| VIEW-01 | Phase 3 | Pending |
| VIEW-02 | Phase 3 | Pending |
| VIEW-03 | Phase 3 | Pending |
| VIEW-04 | Phase 3 | Pending |
| VIEW-05 | Phase 3 | Pending |
| VIEW-06 | Phase 3 | Pending |
| VIEW-07 | Phase 3 | Pending |
| OPS-01 | Phase 2 | Pending |
| OPS-02 | Phase 2 | Pending |
| OPS-03 | Phase 2 | Pending |
| OPS-04 | Phase 2 | Pending |
| OPS-05 | Phase 2 | Pending |
| OPS-06 | Phase 2 | Pending |
| ADM-01 | Phase 1 | Pending |
| ADM-02 | Phase 1 | Pending |
| ADM-03 | Phase 1 | Pending |
| ADM-04 | Phase 1 | Pending |
| ADM-05 | Phase 1 | Complete |
| UX-01 | Phase 4 | Pending |
| UX-02 | Phase 3 | Pending |
| UX-03 | Phase 3 | Pending |
| UX-04 | Phase 4 | Pending |
| UX-05 | Phase 4 | Pending |
| INF-01 | Phase 1 | Complete |
| INF-02 | Phase 1 | Complete |
| INF-03 | Phase 1 | Complete |
| INF-04 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 40 total
- Mapped to phases: 40
- Unmapped: 0

---
*Requirements defined: 2026-04-04*
*Last updated: 2026-04-04 — all 40 requirements mapped to phases 1-4*
