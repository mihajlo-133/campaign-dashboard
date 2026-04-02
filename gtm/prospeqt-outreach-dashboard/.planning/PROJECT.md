# Prospeqt Outreach Dashboard

## What This Is

A real-time campaign monitoring dashboard for the Prospeqt team. It aggregates outbound email campaign metrics from Instantly and EmailBison across 9+ clients, classifies client health (green/amber/red), and surfaces alerts when campaigns need attention. Deployed on Render, accessed by internal Prospeqt team members.

## Core Value

At a glance, any Prospeqt team member can see which clients are healthy and which need immediate attention — without logging into multiple platforms.

## Requirements

### Validated

- ✓ Multi-client campaign monitoring across Instantly and EmailBison — existing
- ✓ Health classification (green/amber/red) based on configurable thresholds — existing
- ✓ Real-time metrics: sent today, reply rate, bounce rate, opportunities — existing
- ✓ Per-campaign drill-down with expand/collapse rows — existing
- ✓ Lead pool runway tracking (not_contacted counts) — existing
- ✓ Background data refresh with 5-minute TTL cache — existing
- ✓ Dark/light theme toggle — existing
- ✓ Mock mode for QA screenshots — existing
- ✓ Responsive table layout (desktop + mobile) — existing
- ✓ Render deployment with env var configuration — existing

### Active

- [ ] Fix broken admin authentication (6 undefined functions crash at runtime)
- [ ] Fix race condition in background backfill (stale not_contacted when backfill > cache TTL)
- [ ] Bound thread spawning (prevent 1000+ threads with many campaigns)
- [ ] Modular codebase architecture optimized for AI agent (Claude Code) navigability
- [ ] Explicit data contracts between fetchers, classifier, cache, and frontend
- [ ] Admin panel: edit KPI targets per client
- [ ] Admin panel: add/remove clients from the dashboard
- [ ] Admin panel: edit alert thresholds (green/amber/red) per client
- [ ] Platform adapter pattern for clean multi-platform extension
- [ ] Stale-while-revalidate: preserve last good data during API errors
- [ ] Structured logging for production debugging on Render
- [ ] Retry/backoff for API rate limits (429s during concurrent startup)
- [ ] Frontend minor polish: targeted DOM updates (no full re-render on refresh), preserve expand state

### Out of Scope

- Client-facing access / multi-tenant auth — no client self-service planned
- Audit logging for admin config changes — not needed with small team
- Historical data persistence / database — no storage layer planned
- Webhook-based real-time updates — polling is sufficient
- Slack/email alerts on RED status — team checks dashboard directly
- External Python dependencies (pip packages) — stdlib-only for zero-setup Render deploy
- Full frontend redesign — current table layout works, minor polish only
- New platforms beyond Instantly + EmailBison — not planned for next 3 months
- CSV export — not requested
- Reply categorization (positive/neutral/negative) — future consideration

## Context

- **Codebase age**: 28 hours old (as of 2026-04-02), 11 commits, 2 major rewrites already
- **Architecture**: Single server.py (1,299 lines) + dashboard.html (906 lines) + admin.html + login.html
- **Deployment**: Render.com via GitHub, env vars for API keys and config
- **Test suite**: 3 test files (~700 lines), fixtures-based, good classification coverage
- **Known critical bugs**: Admin panel completely broken (NameError on all /admin routes), backfill race condition, unbounded thread spawning
- **Technical debt**: Duplicated logic across Instantly/EmailBison fetchers, 13+ global mutable state variables, no data model classes, errors swallow tracebacks
- **Primary developer**: Claude Code (AI agent) — codebase must be optimized for LLM navigability
- **Team access**: Internal Prospeqt team members (AEs, ops)

## Constraints

- **Stdlib-only**: Python standard library only in production code (no pip packages). This enables single-file deploy to Render with zero requirements.txt.
- **Render deployment**: Must work with `python server.py` on Render. Config via environment variables.
- **No build tools**: Frontend is vanilla HTML/CSS/JS. No bundlers, transpilers, or framework dependencies.
- **Timeline**: Complete refactor this week across a few sessions.
- **Backward compatible**: Existing Render deployment must continue working. No breaking changes to the `/api/data` contract that the frontend consumes.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Stdlib-only Python | Zero-setup Render deploy, no dependency drift, proven in production | ✓ Good |
| Optimize for AI agent navigability | Claude Code is primary developer — locality of behavior, explicit contracts, greppable naming | — Pending |
| Keep table layout, minor polish only | Current layout works for the team. Full redesign not justified. | — Pending |
| Modular file split when server.py > ~1,800 lines | Below pain threshold now at 1,299. Section banners work. Split at natural growth point. | — Pending |
| Platform adapter pattern (dict dispatch first) | Only 2 platforms now. Full class adapters when platform #3 arrives. | — Pending |
| Fix critical bugs before structural refactor | Broken admin, race conditions, and unbounded threads are ship-blocking | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-02 after initialization*
