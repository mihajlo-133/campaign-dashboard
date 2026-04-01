# Prospeqt Outreach Dashboard — Development Conventions

## Applies To

All work inside `gtm/prospeqt-outreach-dashboard/`.

## server.py Section Map

server.py is organized into logical sections delimited by comment banners. New code goes in the correct section — never append to the bottom.

| # | Section | Line Range (approx) | What Belongs Here |
|---|---------|---------------------|-------------------|
| 1 | Constants | Top | PORT, CACHE_TTL, REQUEST_TIMEOUT, KPI_TARGETS, alert thresholds, factory defaults |
| 2 | Config layer | After constants | load_config, save_config, get_config, get_client_kpi, get_client_thresholds, validate_config |
| 3 | Client registry | After config | CLIENTS dict mapping name → platform + key_path |
| 4 | API key reader | After registry | read_api_key — parses markdown files for fenced code blocks |
| 5 | HTTP helpers | After key reader | _http_get, _http_post, _count_not_contacted, _paginate_instantly |
| 6 | Instantly fetcher | After HTTP helpers | _get_step_analytics, fetch_instantly_data — all Instantly v2 API logic |
| 7 | EmailBison fetcher | After Instantly | _eb_parse_events_timeseries, fetch_emailbison_data — all EmailBison API logic |
| 8 | Helpers | After EmailBison | _trend, _pool_days_remaining, _classify_client — pure logic, no I/O |
| 9 | Cache & background refresh | After helpers | _cache_lock, _should_refresh, _backfill_nc, _fetch_client, _background_refresh_loop, get_all_data, mock mode |
| 10 | HTML template loading | After cache | _load_template, DASHBOARD_HTML, LOGIN_HTML, ADMIN_HTML constants |
| 11 | HTTP handler & admin auth | After templates | Handler class (do_GET, do_POST), admin auth helpers, ping tracking |
| 12 | Main | Bottom | main() with argparse, server startup |

## Template Conventions

- **Vanilla JS only** — no frameworks, no build tools
- CSS in `<style>` tags, JS in `<script>` tags
- **Mobile-first CSS** — base styles for 375px, then `@media (min-width: ...)` for larger
- **CSS custom properties** for theming: `var(--bg)`, `var(--fg)`, `var(--surface)`, `var(--border)`, etc.
- Templates are in `templates/` — `dashboard.html`, `admin.html`, `login.html`
- Templates are loaded once at import time as module constants — changes require server restart

## Testing

- **Framework:** pytest
- **Fixtures:** `tests/fixtures/` — mock API responses as JSON files
- **Never hit real APIs** in tests — always use fixtures or mocked responses
- **Classification tests are highest priority** — `_classify_client` drives the entire dashboard health display
- Config validation tests verify threshold bounds and type safety
- API fetcher tests verify response parsing handles edge cases (empty, malformed, rate-limited)

## QA Protocol

- **Always use `--mock` mode** for QA screenshots — deterministic data, no API dependency
- **Playwright screenshots at 3 viewports** before shipping any visual change:
  - Desktop: 1440×900
  - Tablet: 768×1024
  - Mobile: 375×812
- QA script: `qa/screenshot.py` (or `make qa`)
- Screenshots land in `qa/screenshots/`

## Agent Teams

When spawning build or spec teams for this dashboard, always use **peer-to-peer agent teams** per `agent-team-protocol.md`. Never use independent subagents that report back. Agents message each other by name via SendMessage.

## Stdlib Constraint

See `dashboard-no-deps.md` — server.py uses ONLY Python stdlib. No exceptions.
