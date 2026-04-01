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
