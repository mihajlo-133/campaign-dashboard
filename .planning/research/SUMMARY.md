# Project Research Summary

**Project:** Email QA Dashboard — Instantly.ai Campaign Variable Validation
**Domain:** Multi-workspace email campaign QA dashboard (Python web app)
**Researched:** 2026-04-04
**Confidence:** HIGH

## Executive Summary

This is a pre-send QA tool for cold email campaigns: it scans all active leads in all active Instantly.ai campaigns and flags leads where personalization variables referenced in the copy are empty, null, or set to the "NO" sentinel value used by Apollo and other enrichment tools. No direct competitor exists — Instantly's native preview is manual and per-lead, while marketing email QA tools (Litmus) don't understand cold email variable patterns. The right approach is a modular Python web app: FastAPI + Jinja2 templates for the presentation layer, httpx for async Instantly API calls, APScheduler for background polling, and an in-memory TTL cache so dashboards reads never block on API. The app is read-mostly — it never writes to Instantly — which keeps the access model simple (open read, password-gated admin).

The biggest risks are not architectural — they're API integration details. Instantly v2 deviates from REST conventions in three ways that will silently break a naive implementation: (1) campaign copy is not in the campaigns list response, it requires a separate API call per campaign to fetch sequence steps; (2) the leads list endpoint is a POST, not a GET; (3) lead status is not a simple boolean — filtering active-only leads requires knowing which integer status codes correspond to terminal states (bounced, unsubscribed, completed). Getting these wrong produces a QA tool that either reports 0 issues (false negatives from missing copy data or wrong variable casing) or floods users with noise (unflagged inactive leads).

Mitigation is straightforward: build the Instantly API client first, test it against real API responses before writing any QA logic, and pin all status code mappings as documented constants. The QA engine should be pure functions with no I/O — it takes data structures in, returns issue reports out — so it can be fully unit-tested before any HTTP integration. Background polling should be designed for resilience from day one: a thread that silently dies leaves stale data with no visible error, and a refresh loop with no per-workspace throttling will hit rate limits immediately on a "run all" trigger with 6 workspaces.

## Key Findings

### Recommended Stack

FastAPI is the correct framework for this project. The dashboard polls 6 workspaces concurrently on a schedule — async is not optional, it's the architecture. FastAPI's async-native design, auto-generated docs, and pydantic-settings integration make it substantially better than Flask for this use case. Jinja2 SSR (server-side rendering) + HTMX for partial page updates is the right presentation approach: the dashboard is read-mostly with no complex client state, so a React SPA would add build pipeline and deployment complexity with zero user value. APScheduler 3.x (NOT 4.x, which is pre-release alpha as of April 2026) handles background polling cleanly via AsyncIOScheduler integrated with FastAPI's lifespan events.

**Core technologies:**
- **FastAPI 0.135.3** — web framework and API layer — async-native, handles concurrent workspace polling without blocking
- **Uvicorn 0.43.0** — ASGI server — FastAPI's recommended server, auto-detected by Render
- **httpx 0.28.1** — async HTTP client for Instantly API — async-native, supports connection pools and retries
- **APScheduler 3.11.2** — background polling scheduler — stable 3.x; do NOT use 4.x (pre-release alpha, breaking changes likely)
- **Jinja2** — server-side HTML rendering — ships with fastapi[standard], zero extra config
- **HTMX 2.x** — partial page updates via CDN — no install, handles "run check" button DOM updates without custom JS
- **pydantic-settings** — type-safe config from env vars — ships with fastapi[standard], reads Render env vars automatically

### Expected Features

The feature dependency graph has a clear critical path: variable extraction from copy → lead completeness check → campaign-level issue summary → workspace rollup → all-workspaces overview. Nothing above this line works without everything below it. The most important non-obvious feature is "NO" value detection — Instantly enrichment tools write the literal string "NO" as a placeholder for missing data, so checking only null/empty produces false negatives on the most common real-world failure mode.

**Must have (table stakes):**
- Variable extraction from campaign copy — regex over all sequence step variants (subject + body)
- Lead completeness check (empty, null, "NO" detection) — cross-reference against per-lead custom_variables
- Active campaign + active lead filtering — filter noise from paused, bounced, unsubscribed leads
- Campaign-level issue summary (broken lead count per variable) — actionable at-a-glance view
- Workspace-level rollup + all-workspaces overview — entry point for multi-client agency context
- Manual "run check" trigger — forces cache refresh on demand
- Background polling with configurable interval — keeps data current without manual action
- Admin panel (password-protected workspace API key management) — without this, workspaces are hardcoded
- "Last checked" timestamp per campaign — confirms data freshness, distinguishes "clean" from "not yet checked"

**Should have (competitive):**
- Drill-down to per-lead issue list with CSV export — "which leads specifically need fixing"
- Slack webhook alert on new QA failures — proactive notification vs requiring the team to check the dashboard
- Issue severity classification — highlight campaigns with >N broken leads to prioritize effort
- Variable discovery view — shows the full variable inventory per campaign (useful for onboarding)

**Defer (v2+):**
- EmailBison / Smartlead integration — validate the concept on Instantly first
- Historical QA run log / diff between runs — significant storage and indexing complexity for low daily value
- Write-back to Instantly — turns a read-only QA tool into a campaign management tool; different product, different risk surface
- User accounts / individual logins — massive auth complexity for a 2-4 person team; simple admin password is sufficient

### Architecture Approach

The architecture separates into four distinct layers with unidirectional dependencies: presentation (Jinja2 templates) → routes (FastAPI, one Blueprint per concern) → services (qa_engine, poller, auth — pure business logic) → data (instantly_client, in-memory cache, workspace JSON store). The qa_engine is the most important component to get right: it must be a pure function module with no I/O, so it can be fully unit-tested against fixture data before any API integration. The background poller and manual check trigger share the same qa_engine.run_check() call — no duplication, same logic both paths.

**Major components:**
1. **instantly_client.py** — all Instantly v2 HTTP calls (campaigns list, sequence steps, leads list paginated); dumb HTTP wrapper with no business logic; rate limiting lives here
2. **qa_engine.py** — variable extraction (regex over copy text) + lead cross-reference + issue report building; pure functions, no I/O, fully unit-testable
3. **cache.py** — thread-safe in-memory TTL cache; dashboard reads always come from here, never directly from Instantly API
4. **poller.py** — APScheduler background job that populates the cache on schedule; resilience wrapper required around the entire loop body
5. **workspace_store.py** — JSON persistence for workspace registry (name, API key); admin panel writes here; poller reads here
6. **routes/qa.py + routes/admin.py** — FastAPI routers; contain zero business logic; call service functions and render templates

### Critical Pitfalls

1. **Campaign copy is not in the campaigns list response** — Copy lives in sequence steps, requiring a separate GET per campaign after fetching the list. Fetching campaign list and finding no variables to parse is the silent failure mode. Fix: after fetching campaigns, call `GET /campaigns/{id}` for each, parse variables from ALL variants of ALL steps (subject + body). Address in Phase 1.

2. **Variable name case-sensitivity produces false negatives** — Lead data uses keys exactly as uploaded; copy uses `{{variableName}}` as written. `cityname` (lead key) and `{{cityName}}` (copy) are the same variable but won't match without normalization. Fix: normalize all variable names to lowercase for comparison; store canonical → original mapping for display. Address in Phase 2 (QA engine).

3. **Rate limit collapse on concurrent workspace fetch** — Instantly enforces 100 req/sec per workspace. A "run all" trigger on 6 workspaces fires 180+ API calls simultaneously, causing cascading 429s that look like data failures. Fix: per-workspace semaphores (max 5-10 concurrent requests), stagger workspace groups on "run all", respect `Retry-After` headers. Address in Phase 1 (API client).

4. **Background thread silent death** — Python's threading.Thread does not propagate exceptions to the main thread. A single malformed API response kills the refresh loop; dashboard serves stale data with no visible error. Fix: wrap entire loop body in `try/except Exception` with logging and `continue`; add last-successful-refresh timestamp to cached data; surface a staleness banner when data is >2× TTL old. Address in Phase 2 (background task design).

5. **API keys in plaintext / accessible without auth** — Admin panel stores client Instantly API keys. If keys land in a committed JSON file or admin routes lack proper auth, all 6 client workspaces are exposed. Fix: store keys as Render environment variables; never in code or committed files; admin password comparison via `hmac.compare_digest`; test that unauthenticated requests to `/admin/*` return 401. Address in Phase 1 (security foundation).

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: API Foundation + Security Baseline

**Rationale:** Everything else depends on a correct Instantly v2 API client and a secure admin panel. The three most common API integration mistakes (copy not in list response, leads endpoint is POST, cursor-based pagination) must be solved before any QA logic is built on top. Security (API key storage, admin auth) must be designed in from day one — retrofitting is costly and risky.

**Delivers:** Working Instantly API client (campaigns, sequence steps, paginated leads), workspace registry with admin panel (add/remove workspaces, password-protected), API key storage in Render env vars, active campaign + active lead filtering with correct status code mapping.

**Addresses:** Variable extraction foundation, workspace management, open-read / admin-gated access model.

**Avoids:** Copy-not-in-list-response (Pitfall 4), lead status filtering noise (Pitfall 3), API keys in git (Pitfall 6), rate limit collapse (Pitfall 1 — throttling layer goes in the client).

### Phase 2: QA Engine + Background Infrastructure

**Rationale:** With a correct API client in place, the QA engine can be built as pure functions tested against fixtures. Background polling and cache must be designed for resilience here — the silent thread death problem and large-campaign timeout problem require architectural decisions (fire-and-forget job pattern, per-workspace semaphore) that are expensive to retrofit.

**Delivers:** Variable extraction regex with normalization (lowercase, multi-variant parsing), lead completeness check with "NO" detection, campaign-level issue summary, thread-safe in-memory TTL cache, APScheduler background poller with resilience wrapper (try/except, last-refresh timestamp), manual "run check" trigger using fire-and-forget pattern.

**Uses:** APScheduler 3.11.2 AsyncIOScheduler, httpx AsyncClient with semaphore, FastAPI lifespan for scheduler startup/shutdown.

**Implements:** qa_engine.py (pure functions), cache.py, poller.py.

**Avoids:** Variable casing mismatch (Pitfall 2 — normalization in qa_engine), background thread silent death (Pitfall 5), QA run timeouts (Pitfall 7 — fire-and-forget from the start).

### Phase 3: Dashboard Views + Workspace Rollup

**Rationale:** With QA engine and cache working, the presentation layer can be built against fixture data. All three display levels (all-workspaces, per-workspace, per-campaign) are straightforward template rendering — cache reads only. HTMX handles the "run check" button without custom JS.

**Delivers:** All-workspaces overview page, workspace drill-down page, campaign drill-down with per-variable issue counts, "last checked" timestamp display, "not yet checked" vs "0 issues" distinction, HTMX-wired "run check" button with loading state.

**Uses:** FastAPI + Jinja2 templates, HTMX 2.x from CDN, mobile-first CSS.

**Implements:** routes/qa.py, templates/dashboard.html, templates/workspace.html, templates/campaign.html.

### Phase 4: Drill-Down, Export + Alerting

**Rationale:** Once the team is using the core dashboard daily, Phase 4 adds the features that make it actionable: drill down to which specific leads need fixing and export them, plus proactive Slack alerts so the team doesn't have to remember to check the dashboard.

**Delivers:** Per-lead issue list view (email + broken variables), CSV export of broken leads, Slack webhook alert on new QA failures (configurable threshold), issue severity classification (highlight campaigns with >N broken leads).

**Addresses:** Drill-down differentiator, CSV export, Slack alert, severity classification from FEATURES.md.

### Phase Ordering Rationale

- Phase 1 before Phase 2: qa_engine needs a real API client to validate against; the API shape (copy in sequence steps, POST leads endpoint, cursor pagination) must be understood before the parser is built.
- Phase 2 before Phase 3: templates are pointless if the cache is not populated correctly; all display logic reads from cache, so cache must be correct first.
- Phase 3 before Phase 4: drill-down and export build on the campaign-level summary view; alerts build on the polling loop. Both require Phase 3's infrastructure.
- Security baseline in Phase 1: admin auth and API key storage must not be deferred — they're harder to add correctly after the routes are built and the system is in use.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** Instantly v2 API lead status code mapping — official docs describe status categories but the exact integer codes for "active" vs terminal states need validation against live API responses. Recommend inspecting real lead objects before finalizing the filter logic.
- **Phase 2:** Variable regex edge cases — Instantly templates may use `{{ variableName }}` with whitespace inside braces; HTML-encoded email bodies may wrap variables in `&lt;` entities. Regex pattern needs testing against real campaign copy samples before finalizing.

Phases with standard patterns (skip research-phase):
- **Phase 3:** FastAPI + Jinja2 + HTMX is well-documented with official examples; no research needed.
- **Phase 4:** Slack webhook integration is a one-liner; CSV export is stdlib. Both are standard patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Verified against PyPI (confirmed versions), official FastAPI docs, Render deployment docs. APScheduler 4.x alpha warning confirmed from author's GitHub issue. |
| Features | HIGH (core), MEDIUM (alerting) | Core QA features verified against Instantly API docs and PROJECT.md. Slack alerting pattern from DQOps docs — MEDIUM confidence. |
| Architecture | HIGH | Based on Instantly v2 official API docs + existing Prospeqt dashboard codebase as primary reference. Flask Blueprint + service layer is an established pattern. |
| Pitfalls | HIGH (API specifics), MEDIUM (background task patterns) | API pitfalls from official Instantly docs (HIGH). Background task resilience patterns from community sources (MEDIUM). |

**Overall confidence:** HIGH

### Gaps to Address

- **Instantly lead status integer codes:** Official docs describe status categories semantically but the exact integer values mapping to "active" vs "bounced/unsubscribed/completed" are not confirmed in research. Validate by fetching 10 leads from a real campaign and inspecting the raw `status` field before finalizing the filter in Phase 1.
- **Render persistent disk on free tier:** ARCHITECTURE.md notes that Render's free tier has no persistent disk, requiring env-var bootstrap for workspace JSON. Validate the exact Render environment variable update pattern (manual vs Render Deploy API) before committing to the admin panel implementation.
- **Variable syntax variants in the wild:** Research identified `{{variableName}}` as the standard pattern and `{{ variableName }}` (with spaces) as a possible variant. Confirm against 5+ real campaign copy samples during Phase 2 qa_engine development.

## Sources

### Primary (HIGH confidence)
- [Instantly API v2 official docs](https://developer.instantly.ai) — rate limits, lead list endpoint (POST), campaign endpoint, cursor pagination
- [Instantly API v2 Changelog](https://feedback.instantly.ai/changelog/instantly-api-v2-is-officially-here) — v1 deprecated Jan 2026
- [FastAPI PyPI](https://pypi.org/project/fastapi/) — version 0.135.3 confirmed
- [APScheduler PyPI](https://pypi.org/project/APScheduler/) — v3.11.2 stable, v4 pre-release alpha confirmed
- [httpx PyPI](https://pypi.org/project/httpx/) — version 0.28.1 confirmed
- [FastAPI official docs](https://fastapi.tiangolo.com) — templates, testing, background tasks
- [APScheduler author GitHub issue](https://github.com/agronholm/apscheduler/issues/465) — "do NOT use 4.x in production" author statement
- Existing `gtm/prospeqt-outreach-dashboard/server.py` — observed Instantly integration patterns

### Secondary (MEDIUM confidence)
- [Render FastAPI deployment article](https://render.com/articles/fastapi-deployment-options) — ASGI auto-detection, env var secrets
- [Flask Blueprints DigitalOcean guide](https://www.digitalocean.com/community/tutorials/how-to-structure-a-large-flask-application-with-flask-blueprints-and-flask-sqlalchemy) — modular Flask architecture patterns
- [DQOps Slack integration docs](https://dqops.com/docs/integrations/slack/configuring-slack-notifications/) — Slack webhook pattern for data quality alerting
- [Python Threading — Real Python](https://realpython.com/intro-to-python-threading/) — thread safety patterns
- [Instantly blog: Cold Email Subject Line QA](https://instantly.ai/blog/cold-email-subject-line-checklist-pre-send-qa-for-sales-teams/) — confirms "broken variables" as known problem
- [Instantly blog: AI-Powered Personalization](https://instantly.ai/blog/ai-powered-cold-email-personalization-safe-patterns-prompt-examples-workflow-for-founders/) — variable syntax, fallback values, manual preview workflow

### Tertiary (LOW confidence)
- WebSearch: FastAPI vs Flask 2025, HTMX+Jinja2 SSR patterns — multiple corroborating community sources, not a single authoritative reference

---
*Research completed: 2026-04-04*
*Ready for roadmap: yes*
