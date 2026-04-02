# Requirements: Prospeqt Outreach Dashboard

**Defined:** 2026-04-02
**Core Value:** At a glance, any Prospeqt team member can see which clients are healthy and which need immediate attention.

## v1 Requirements

### Critical Bugs

- [ ] **BUG-01**: Admin authentication works end-to-end (login, session token, route protection)
- [ ] **BUG-02**: All admin API routes respond without NameError (ping, ping-log, config GET/POST)
- [ ] **BUG-03**: Background backfill does not cause stale not_contacted counts when backfill exceeds cache TTL
- [ ] **BUG-04**: Thread spawning is bounded (max 10 concurrent threads per fetch, regardless of campaign count)

### Architecture

- [ ] **ARCH-01**: Data contract is explicitly documented — every fetcher returns a dict with defined required/optional keys
- [ ] **ARCH-02**: Duplicated logic between Instantly and EmailBison fetchers is extracted into shared helpers (rate calc, 7d average, campaign grouping)
- [ ] **ARCH-03**: Platform dispatch uses adapter pattern (dict mapping platform → fetch function) instead of if/elif
- [ ] **ARCH-04**: Global mutable state is encapsulated in a state manager class (cache, config, step cache)
- [ ] **ARCH-05**: Templates load lazily (not at import time) so tests don't touch filesystem on import
- [ ] **ARCH-06**: Structured logging via stdlib logging module — full tracebacks on errors, timestamps, client context
- [ ] **ARCH-07**: Codebase section banners updated in CLAUDE.md with current line ranges after refactor
- [ ] **ARCH-08**: Each module/section has a docstring explaining its contract (what it takes, what it returns, what it depends on)

### Admin Panel

- [ ] **ADMIN-01**: Team member can log in to admin panel with password and receive a session token
- [ ] **ADMIN-02**: Team member can edit KPI targets (sent/day, pool target, opps/day, reply rate) per client
- [ ] **ADMIN-03**: Team member can add a new client (name, platform, API key source, KPI targets)
- [ ] **ADMIN-04**: Team member can remove a client from the dashboard
- [ ] **ADMIN-05**: Team member can edit alert thresholds (reply rate warn/red, bounce rate warn/red, pool days warn/red) per client and globally

### Resilience

- [ ] **RES-01**: When an API call fails, last good data is preserved with a "stale" indicator instead of hard error
- [ ] **RES-02**: API calls retry with exponential backoff on 429 rate limit responses (max 3 retries)
- [ ] **RES-03**: Config schema includes version field with forward migration path for new fields

### Frontend

- [ ] **FE-01**: Dashboard refresh updates metrics in-place without full DOM rebuild (preserves scroll position and expand state)
- [ ] **FE-02**: Visual polish: loading skeleton during initial fetch, smooth transitions on metric updates
- [ ] **FE-03**: Stale data indicator shown on client cards when serving cached data after API error

## v2 Requirements

### Observability

- **OBS-01**: Audit log for admin config changes (who, what, when)
- **OBS-02**: Slack/email alerts when a client transitions to RED status
- **OBS-03**: Historical metric data with persistent storage for trend analysis

### Features

- **FEAT-01**: Reply categorization (positive/neutral/negative/OOO)
- **FEAT-02**: CSV export of dashboard data
- **FEAT-03**: Per-campaign drill-down with step-level analytics
- **FEAT-04**: Sending account health monitoring
- **FEAT-05**: 7-day sparkline charts per client

### Scale

- **SCALE-01**: Multi-user admin with role-based access
- **SCALE-02**: Client-facing read-only view with per-client auth
- **SCALE-03**: Support for 3+ email platforms (Lemlist, Woodpecker, etc.)

## Out of Scope

| Feature | Reason |
|---------|--------|
| External Python dependencies | Stdlib-only constraint for zero-setup Render deploy |
| Full frontend redesign | Current table layout works; minor polish only |
| Client self-service access | Internal tool for Prospeqt team only |
| Real-time websocket updates | 5-min polling is sufficient for campaign monitoring |
| Database/persistent storage | No historical data needs in v1 |
| Mobile-native app | Responsive web is sufficient |
| Build tools (webpack, vite) | Vanilla HTML/CSS/JS keeps deployment simple |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BUG-01 | Phase 1 | Pending |
| BUG-02 | Phase 1 | Pending |
| BUG-03 | Phase 1 | Pending |
| BUG-04 | Phase 1 | Pending |
| ARCH-01 | Phase 2 | Pending |
| ARCH-02 | Phase 2 | Pending |
| ARCH-03 | Phase 3 | Pending |
| ARCH-04 | Phase 3 | Pending |
| RES-01 | Phase 4 | Pending |
| RES-02 | Phase 4 | Pending |
| RES-03 | Phase 4 | Pending |
| ADMIN-01 | Phase 5 | Pending |
| ADMIN-02 | Phase 5 | Pending |
| ADMIN-03 | Phase 5 | Pending |
| ADMIN-04 | Phase 5 | Pending |
| ADMIN-05 | Phase 5 | Pending |
| ARCH-05 | Phase 6 | Pending |
| ARCH-06 | Phase 6 | Pending |
| FE-01 | Phase 7 | Pending |
| FE-02 | Phase 7 | Pending |
| FE-03 | Phase 7 | Pending |
| ARCH-07 | Phase 8 | Pending |
| ARCH-08 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-02*
*Last updated: 2026-04-02 after roadmap creation — all 23 requirements mapped*
