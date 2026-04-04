# Roadmap: Email QA Dashboard

## Overview

Four phases from scaffold to ship. Phase 1 builds the Instantly API client and admin panel — the foundation everything else depends on. Phase 2 adds the QA engine and background polling infrastructure, tested against fixtures before connecting to real data. Phase 3 renders the dashboard views that GTM engineers actually use: workspace overview → workspace drill-down → campaign summary → per-lead issue list. Phase 4 polishes the UX to the required luxury standard, adds Playwright visual QA, and ships to Render.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: API Foundation** - Instantly v2 client, workspace admin panel, project scaffold (completed 2026-04-04)
- [ ] **Phase 2: QA Engine + Background** - Variable extraction, lead flagging, cache, background poller
- [ ] **Phase 3: Dashboard Views** - All-workspaces, workspace, campaign, and per-lead UI
- [ ] **Phase 4: UX Polish + Deployment** - Visual design, Playwright QA, Render deployment

## Phase Details

### Phase 1: API Foundation
**Goal**: The app can connect to configured Instantly workspaces, authenticate as admin, and return structured campaign + lead data
**Depends on**: Nothing (first phase)
**Requirements**: INF-01, INF-02, INF-03, INF-04, API-01, API-02, API-03, API-04, API-05, API-06, API-07, ADM-01, ADM-02, ADM-03, ADM-04, ADM-05
**Success Criteria** (what must be TRUE):
  1. Admin can add a new Instantly workspace (name + API key) via password-protected panel and the key persists across app restarts
  2. Admin can remove a workspace from the panel and it no longer appears in any data fetch
  3. App fetches campaigns from all configured workspaces, filtering to status=0 (draft) and status=1 (active) only
  4. App fetches all active leads (status=1) from a campaign using cursor pagination with no leads missed
  5. Lead variables are read from `lead.payload` dict and sequence copy is parsed from inline `campaign.sequences[].steps[].variants[].body/subject`
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Project scaffold, config, workspace registry, test infrastructure
- [x] 01-02-PLAN.md — Instantly v2 async API client with pagination, filtering, rate limiting
- [x] 01-03-PLAN.md — Admin panel routes, auth, templates (UI-SPEC), integration tests

### Phase 2: QA Engine + Background
**Goal**: The system continuously checks all active campaigns for broken variables and makes results available in-memory with no API blocking
**Depends on**: Phase 1
**Requirements**: QA-01, QA-02, QA-03, QA-04, QA-05, QA-06, OPS-01, OPS-02, OPS-03, OPS-04, OPS-05, OPS-06
**Success Criteria** (what must be TRUE):
  1. QA engine extracts `{{variableName}}` patterns from copy, excluding `{{RANDOM | ...}}` spin syntax and `{{accountSignature}}`
  2. QA engine flags leads where any copy-referenced variable is empty, null, or the string "NO" — producing a per-variable broken lead count per campaign
  3. Background poller runs on schedule, populates the in-memory cache, survives individual API errors without dying, and updates a last-refresh timestamp
  4. Manual "run check" at all-workspaces, workspace, and campaign level triggers an immediate cache refresh and returns within a reasonable time
  5. When background poller encounters an error on one workspace, other workspaces continue refreshing normally
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md — QA models, variable extraction, lead flagging, per-campaign/workspace QA runner (TDD)
- [ ] 02-02-PLAN.md — Cache layer, background poller, manual triggers, lifespan wiring

### Phase 3: Dashboard Views
**Goal**: GTM engineers can navigate from all-workspaces overview to per-lead issue detail and understand exactly which leads need fixing
**Depends on**: Phase 2
**Requirements**: VIEW-01, VIEW-02, VIEW-03, VIEW-04, VIEW-05, VIEW-06, VIEW-07, UX-02, UX-03
**Success Criteria** (what must be TRUE):
  1. Engineer can open the dashboard and see all workspaces at a glance with health status badges (green/yellow/red based on broken lead counts)
  2. Engineer can click into a workspace and see all campaigns with their QA status, variable issue counts, and last-checked timestamp
  3. Engineer can click into a campaign and see a per-variable breakdown: "cityName — 12 leads broken"
  4. Engineer can drill into a campaign and see which specific leads are broken: email address + which variables are broken + current values
  5. Navigation flows naturally from all-workspaces → workspace → campaign → lead list with no dead ends
**Plans**: TBD
**UI hint**: yes

### Phase 4: UX Polish + Deployment
**Goal**: The dashboard is visually polished, Playwright-validated at three viewports, and deployed to Render with all 6 existing workspaces pre-configured
**Depends on**: Phase 3
**Requirements**: UX-01, UX-04, UX-05
**Success Criteria** (what must be TRUE):
  1. Dashboard passes a UX design expert review: clear data hierarchy, luxury aesthetic, scannable at a glance — no critical design issues outstanding
  2. Playwright screenshots at desktop (1440x900), tablet (768x1024), and mobile (375x812) show no broken layouts or overflowing elements
  3. All 6 Prospeqt client workspaces are configured and the dashboard is live at a Render URL accessible to the team
  4. Manual "run check" user flow completes successfully in a Playwright end-to-end test (click trigger → loading state → results update)
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. API Foundation | 3/3 | Complete   | 2026-04-04 |
| 2. QA Engine + Background | 1/2 | In Progress|  |
| 3. Dashboard Views | 0/TBD | Not started | - |
| 4. UX Polish + Deployment | 0/TBD | Not started | - |
