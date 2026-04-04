# Phase 1: API Foundation - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the FastAPI project scaffold, Instantly v2 API client, workspace admin panel, and data fetching infrastructure. By the end of this phase, the app can connect to configured Instantly workspaces, authenticate as admin, and return structured campaign + lead data. No QA logic or dashboard views yet.

</domain>

<decisions>
## Implementation Decisions

### Project structure
- **D-01:** Separate GitHub repo named `prospeqt-email-qa`
- **D-02:** Claude's discretion on internal module organization (layer-based vs feature-based — choose what's best for a FastAPI dashboard at this scale)
- **D-03:** Plain Python venv for local dev — no Docker
- **D-04:** FastAPI + Jinja2 + HTMX stack (from research), uvicorn for dev, gunicorn+uvicorn for production

### Admin panel UX
- **D-05:** Admin panel accessed via settings/gear icon in the main nav bar — not a separate /admin route
- **D-06:** Password prompt appears when clicking the gear icon (simple shared password, not user accounts)
- **D-07:** Adding a workspace requires only: display name + API key
- **D-08:** Removing a workspace shows a confirmation dialog with a simple sentence (e.g., "Remove [workspace name]? This will stop monitoring its campaigns.")

### API key storage
- **D-09:** Workspace API keys stored exclusively in environment variables — no JSON file, no database
- **D-10:** Admin panel add/remove workspace modifies env vars which requires updating Render env vars and redeploying — this is acceptable for the team
- **D-11:** No encryption of API keys at rest — server-side only, internal tool
- **D-12:** For local development, use .env file loaded by pydantic-settings. For Render, set env vars in the Render dashboard.
- **D-13:** Env var naming convention: workspace keys stored as structured env vars (e.g., `WORKSPACE_<NAME>_API_KEY=<key>`)

### Data contracts
- **D-14:** When Instantly API is down or rate-limited for one workspace, show an error badge on that workspace + display last successful data. Other workspaces continue normally.
- **D-15:** Claude's discretion on caching strategy — choose what balances freshness with API load

### Claude's Discretion
- Internal module organization (D-02)
- Caching strategy (D-15)
- Pydantic model design for campaign/lead data
- Error handling patterns (retry logic, timeout values)
- Exact env var parsing format for workspace configuration

</decisions>

<specifics>
## Specific Ideas

- Repo is standalone (`prospeqt-email-qa`) deployed independently to Render, not part of the main claude-code monorepo
- Instantly API data shapes verified against live API (2026-04-04):
  - Campaign statuses: 0=draft, 1=active, 2=paused, 3=completed
  - Lead statuses: 1=active, 3=contacted, -1=bounced
  - Copy is inline: `campaign.sequences[].steps[].variants[].body/subject`
  - Lead variables in `lead.payload` dict
  - Campaigns: GET `/api/v2/campaigns`
  - Leads: POST `/api/v2/leads/list` with cursor pagination
  - Rate limits: 100 req/sec, 6000 req/min per workspace
- Admin panel is a gear icon in nav, not a separate page — keeps it accessible but not prominent
- 6 existing workspaces to bootstrap: enavra, heyreach-client, kayse, myplace, smartmatchapp, swishfunding

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Instantly API
- `.planning/research/STACK.md` — Technology stack recommendations, versions, and project structure
- `.planning/research/ARCHITECTURE.md` — System architecture, component boundaries, data flow
- `.planning/research/PITFALLS.md` — API integration pitfalls, rate limiting, lead status codes
- `.planning/research/FEATURES.md` — Feature landscape, dependencies, MVP definition

### Project configuration
- `.planning/PROJECT.md` — Project vision, constraints, API data shapes (verified live)
- `.planning/REQUIREMENTS.md` — v1 requirements with requirement IDs (API-01 through API-07, ADM-01 through ADM-05, INF-01 through INF-04)
- `.planning/ROADMAP.md` — Phase 1 success criteria and requirement mapping

### Existing API key files (for bootstrapping workspace list)
- `tools/accounts/enavra/instantly.md` — Enavra API key
- `tools/accounts/kayse/instantly.md` — Kayse API key
- `tools/accounts/myplace/instantly.md` — MyPlace API key
- `tools/accounts/smartmatchapp/instantly.md` — SmartMatchApp API key
- `tools/accounts/swishfunding/instantly.md` — SwishFunding API key
- `tools/accounts/heyreach-client/instantly.md` — HeyReach Client API key

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Existing Prospeqt outreach dashboard (`gtm/prospeqt-outreach-dashboard/server.py`) — reference for Instantly API v2 patterns, but this project uses a different architecture (modular FastAPI vs single-file stdlib)
- API key files in `tools/accounts/*/instantly.md` — keys to bootstrap initial workspaces into env vars

### Established Patterns
- Instantly v2 API uses Bearer token auth: `Authorization: Bearer <key>`
- Campaign list is GET, lead list is POST with JSON body
- Lead pagination uses cursor-based approach (not offset)
- Rate limits are per-workspace (100 req/sec)

### Integration Points
- This is a standalone project — no integration with existing codebase
- Will be deployed as its own Render service
- Workspace API keys sourced from existing `tools/accounts/` files for initial setup

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-api-foundation*
*Context gathered: 2026-04-04*
