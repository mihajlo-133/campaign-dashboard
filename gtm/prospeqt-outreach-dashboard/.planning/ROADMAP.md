# Roadmap: Prospeqt Outreach Dashboard

## Overview

This is a brownfield refactor of a 28-hour-old codebase that already has critical runtime bugs. The journey goes: fix what's broken first (Phases 1), make the architecture navigable for Claude Code (Phases 2-3), make the system production-reliable (Phase 4), build new admin features on the clean foundation (Phase 5), add observability and test hygiene (Phase 6), polish the frontend (Phase 7), and finalize documentation so any new session can orient instantly (Phase 8).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Critical Bug Fixes** - Restore admin panel functionality and fix race conditions / unbounded threads (completed 2026-04-03)
- [ ] **Phase 2: Data Contracts and Shared Helpers** - Explicit interfaces between all major components and DRY fetcher logic
- [ ] **Phase 3: Platform Adapter and State Encapsulation** - Adapter pattern dispatch and global mutable state in a manager class
- [ ] **Phase 4: Production Resilience** - Stale-while-revalidate, retry/backoff, and config schema versioning
- [ ] **Phase 5: Admin Panel** - Full CRUD for clients, KPI targets, and alert thresholds via the admin UI
- [ ] **Phase 6: Structured Logging and Lazy Templates** - Full traceback logging, timestamps, and test-safe template loading
- [ ] **Phase 7: Frontend Polish** - In-place metric updates, loading skeleton, stale data indicator
- [ ] **Phase 8: Documentation Finalization** - CLAUDE.md section line ranges and per-section docstrings

## Phase Details

### Phase 1: Critical Bug Fixes
**Goal**: The admin panel works end-to-end and the background refresh is race-condition-free with bounded concurrency
**Depends on**: Nothing (first phase)
**Requirements**: BUG-01, BUG-02, BUG-03, BUG-04
**Success Criteria** (what must be TRUE):
  1. Navigating to /admin/login, entering the correct password, and submitting redirects to the admin panel without a 500 error
  2. All admin API routes (/admin/ping, /admin/ping-log, /admin/config GET and POST) return valid JSON responses instead of crashing with NameError
  3. Running the dashboard for 30+ minutes with many campaigns does not produce stale not_contacted values caused by backfill outlasting the cache TTL
  4. The ThreadPoolExecutor for per-campaign backfill never spawns more than 10 concurrent threads regardless of how many campaigns are active
**Plans**: 2 plans
Plans:
- [x] 01-01-PLAN.md — Implement admin auth functions (_check_admin_auth, _make_token) + regression tests
- [x] 01-02-PLAN.md — Fix backfill race condition with generation counter + bound threads to ThreadPoolExecutor

### Phase 2: Data Contracts and Shared Helpers
**Goal**: Every data boundary in the codebase has an explicit, documented contract and duplicated fetcher logic is extracted into shared helpers
**Depends on**: Phase 1
**Requirements**: ARCH-01, ARCH-02
**Success Criteria** (what must be TRUE):
  1. A developer (or Claude Code in a new session) can read a single location to see every required and optional key that a fetcher must return
  2. The rate_calc, 7-day average, and campaign grouping logic exists in exactly one place and is called by both the Instantly and EmailBison fetchers
  3. All existing tests pass without modification after the helper extraction
**Plans**: TBD

### Phase 3: Platform Adapter and State Encapsulation
**Goal**: Platform dispatch is table-driven (not if/elif) and all global mutable state is managed through a single class
**Depends on**: Phase 2
**Requirements**: ARCH-03, ARCH-04
**Success Criteria** (what must be TRUE):
  1. Adding a hypothetical third email platform requires adding one entry to a dispatch dict, not editing an if/elif chain
  2. All cache reads, cache writes, config access, and step-cache operations go through a single StateManager class with no naked global variable access outside it
  3. All existing tests pass without modification after the encapsulation
**Plans**: TBD

### Phase 4: Production Resilience
**Goal**: The dashboard serves last-known-good data during API outages and automatically retries on rate limits
**Depends on**: Phase 3
**Requirements**: RES-01, RES-02, RES-03
**Success Criteria** (what must be TRUE):
  1. When an API call fails, the client card still shows the last successfully fetched data with a visible "stale" indicator rather than an error state
  2. When an API returns 429, the fetch automatically retries up to 3 times with exponential backoff before giving up
  3. The config file includes a version field, and loading a config without the field applies defaults for any new fields rather than crashing
**Plans**: TBD

### Phase 5: Admin Panel
**Goal**: Team members can manage the full client roster and all monitoring thresholds through the admin UI without touching code or environment variables
**Depends on**: Phase 1
**Requirements**: ADMIN-01, ADMIN-02, ADMIN-03, ADMIN-04, ADMIN-05
**Success Criteria** (what must be TRUE):
  1. A team member can visit /admin/login, enter the admin password, and access the admin panel in a browser session that persists across page reloads
  2. A team member can change the KPI targets (sent/day, pool target, opps/day, reply rate) for any individual client and see them reflected immediately in health classification
  3. A team member can add a brand-new client with name, platform, API key source, and KPI targets, and the client appears on the dashboard within one cache cycle
  4. A team member can remove an existing client and it disappears from the dashboard after the next cache cycle
  5. A team member can edit alert thresholds (reply rate, bounce rate, pool days warn/red boundaries) either globally or per individual client
**Plans**: TBD
**UI hint**: yes

### Phase 6: Structured Logging and Lazy Templates
**Goal**: Production errors produce full tracebacks with context, and test imports no longer touch the filesystem
**Depends on**: Phase 3
**Requirements**: ARCH-05, ARCH-06
**Success Criteria** (what must be TRUE):
  1. When a fetcher raises an exception in production, the Render log shows the full traceback, the client name, and a timestamp — not a swallowed error
  2. Importing server.py in a test environment (with no templates/ directory present) does not raise a FileNotFoundError
  3. The stdlib logging module is used throughout — no bare print() calls for error/warning conditions
**Plans**: TBD

### Phase 7: Frontend Polish
**Goal**: Dashboard refreshes feel seamless — metrics update in place without visible flicker, scroll position is preserved, and stale data is clearly flagged
**Depends on**: Phase 4, Phase 6
**Requirements**: FE-01, FE-02, FE-03
**Success Criteria** (what must be TRUE):
  1. Triggering a data refresh (auto or manual) updates metric values in-place without collapsing any expanded campaign rows or resetting scroll position
  2. On the first page load, a skeleton loading state is visible before data arrives instead of an empty or broken layout
  3. When the dashboard is serving stale data (after an API error), each affected client card shows a visible indicator (e.g., a badge or muted color) without disrupting the normal health color classification
**Plans**: TBD
**UI hint**: yes

### Phase 8: Documentation Finalization
**Goal**: CLAUDE.md accurately reflects post-refactor line ranges and every major section has a docstring that explains its contract
**Depends on**: Phase 7
**Requirements**: ARCH-07, ARCH-08
**Success Criteria** (what must be TRUE):
  1. The section map in CLAUDE.md lists accurate line ranges that match the actual post-refactor server.py
  2. Every major section in server.py has a docstring that states what it takes as input, what it returns, and what it depends on
  3. A new Claude Code session starting from CLAUDE.md can identify any function's location and contract without running grep
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Critical Bug Fixes | 2/2 | Complete   | 2026-04-03 |
| 2. Data Contracts and Shared Helpers | 0/TBD | Not started | - |
| 3. Platform Adapter and State Encapsulation | 0/TBD | Not started | - |
| 4. Production Resilience | 0/TBD | Not started | - |
| 5. Admin Panel | 0/TBD | Not started | - |
| 6. Structured Logging and Lazy Templates | 0/TBD | Not started | - |
| 7. Frontend Polish | 0/TBD | Not started | - |
| 8. Documentation Finalization | 0/TBD | Not started | - |
