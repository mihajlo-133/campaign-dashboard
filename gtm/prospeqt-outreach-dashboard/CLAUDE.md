# Prospeqt Outreach Dashboard

Campaign monitoring dashboard for Prospeqt's cold email agency. Shows real-time performance across all client workspaces.

## What This Is

- 9 clients across **Instantly v2** (7) and **EmailBison** (2)
- Replaces the Daily Vitals Slack bot (stale data, no drill-down, inaccurate)
- Deployed to Render, accessed by Prospeqt AEs to monitor campaign health

## Architecture

**stdlib-only Python HTTP server** — single file, no pip dependencies.

```
server.py              # All Python — API fetchers, cache, classification, HTTP handler
templates/
  dashboard.html       # Main UI — client cards, metrics, auto-refresh
  admin.html           # Config panel — thresholds, KPI targets
  login.html           # Admin login page
tests/
  fixtures/            # Mock API responses (JSON)
  test_*.py            # pytest test files
qa/
  screenshots/         # Playwright viewport screenshots
  screenshot.py        # QA automation script
docs/
  BACKLOG.md           # Feature backlog (P1/P2/P3)
  specs/               # Feature specs from /feature workflow
```

## Key Patterns

- **Templates loaded at import time** — `_load_template()` reads once, stored as module constants. Changes require server restart.
- **ThreadPoolExecutor** for parallel API fetches across all clients
- **5-min cache TTL** — background refresh thread keeps data warm
- **Mock mode** (`--mock`) serves deterministic data from `tests/fixtures/mock_api_data.json` for QA
- **Classification** (`_classify_client`) drives card health colors: green/amber/red based on configurable thresholds

## The Stdlib Constraint

server.py uses ONLY Python stdlib. No `requests`, no `flask`, no pip packages. This enables single-file deployment to Render with zero setup. See `.claude/rules/dashboard-no-deps.md`.

## Development

| Task | Command |
|------|---------|
| Run locally | `python server.py --port 8060` |
| Run with mock data | `python server.py --mock` |
| Run tests | `make test` or `python -m pytest tests/ -v` |
| QA screenshots | `make qa` |
| New feature | `/feature [description]` |

## server.py Sections

Code is organized into comment-bannered sections. New code goes in the correct section — see `.claude/rules/dashboard-dev.md` for the full map.

1. Constants — PORT, CACHE_TTL, KPI_TARGETS, thresholds
2. Config layer — load/save/resolve runtime config
3. Client registry — CLIENTS dict (name → platform + key_path)
4. API key reader — parse keys from markdown files
5. HTTP helpers — _http_get, _http_post, pagination
6. Instantly fetcher — all Instantly v2 API logic
7. EmailBison fetcher — all EmailBison API logic
8. Helpers — _trend, _pool_days_remaining, _classify_client
9. Cache & background refresh — TTL cache, background thread, mock mode
10. HTML template loading — read from templates/ directory
11. HTTP handler & admin auth — Handler class, admin routes, ping tracking
12. Main — argparse, server startup

## Key Paths

| Need | Path |
|------|------|
| Feature backlog | `docs/BACKLOG.md` |
| Feature specs | `docs/specs/` |
| Test fixtures | `tests/fixtures/` |
| QA screenshots | `qa/screenshots/` |
| Dashboard spec | `gtm/docs/strategy/client_dashboard_spec.md` |
| UX requirements | `gtm/docs/strategy/client_dashboard_ux_requirements.md` |
| Dev conventions | `.claude/rules/dashboard-dev.md` |
| Stdlib constraint | `.claude/rules/dashboard-no-deps.md` |

## Clients

| Client | Platform | Status |
|--------|----------|--------|
| MyPlace | Instantly | Active |
| SwishFunding | Instantly | Active |
| SmartMatchApp | Instantly | Active |
| HeyReach | Instantly | Active |
| Kayse | Instantly | Active |
| Prosperly | Instantly | No API Key |
| Enavra | Instantly | Active |
| RankZero | EmailBison | Active |
| SwishFunding (EB) | EmailBison | Active |

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Prospeqt Outreach Dashboard**

A real-time campaign monitoring dashboard for the Prospeqt team. It aggregates outbound email campaign metrics from Instantly and EmailBison across 9+ clients, classifies client health (green/amber/red), and surfaces alerts when campaigns need attention. Deployed on Render, accessed by internal Prospeqt team members.

**Core Value:** At a glance, any Prospeqt team member can see which clients are healthy and which need immediate attention — without logging into multiple platforms.

### Constraints

- **Stdlib-only**: Python standard library only in production code (no pip packages). This enables single-file deploy to Render with zero requirements.txt.
- **Render deployment**: Must work with `python server.py` on Render. Config via environment variables.
- **No build tools**: Frontend is vanilla HTML/CSS/JS. No bundlers, transpilers, or framework dependencies.
- **Timeline**: Complete refactor this week across a few sessions.
- **Backward compatible**: Existing Render deployment must continue working. No breaking changes to the `/api/data` contract that the frontend consumes.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
