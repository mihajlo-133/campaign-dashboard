# Phase 2: QA Engine + Background - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the QA engine (variable extraction, lead flagging) and background polling infrastructure. By the end of this phase, the system continuously checks all active campaigns for broken variables and makes results available in-memory. No dashboard views yet — that's Phase 3.

</domain>

<decisions>
## Implementation Decisions

### Variable matching
- **D-01:** Case-sensitive exact match between copy variables and lead.payload keys (verified against live API — `companyName` in copy matches `companyName` in payload exactly)
- **D-02:** Exclude `{{RANDOM | ...}}` spin syntax from variable extraction (regex must handle the pipe-separated options inside double braces)
- **D-03:** Exclude `{{accountSignature}}` from variable extraction (system variable, not a lead variable)
- **D-04:** No other exclusions — just RANDOM and accountSignature

### Bad value detection
- **D-05:** Three values flagged as broken: empty string (`""`), null/missing (key absent from payload), and literal string `"NO"`
- **D-06:** No other bad values (no "N/A", no "n/a" — just those three)
- **D-07:** Not configurable per workspace in v1 — hardcoded detection rules

### QA result shape
- **D-08:** Results structured per-campaign: `{campaign_id, campaign_name, total_leads, broken_count, issues_by_variable: {varName: count}, last_checked}`
- **D-09:** Results rolled up per-workspace: aggregate broken count across campaigns
- **D-10:** Results rolled up across all workspaces: total broken leads, total campaigns checked
- **D-11:** Three levels of scanning: all workspaces → per workspace → per campaign

### Background poller
- **D-12:** Poll every 5 minutes (configurable via env var)
- **D-13:** Poller does discovery only — checks for new/changed campaigns, does NOT run full QA automatically
- **D-14:** Full QA runs only on manual trigger (user clicks "Run QA" button)
- **D-15:** Poller must be resilient — one workspace error doesn't stop others
- **D-16:** Poller updates a last-refresh timestamp visible in the UI

### Manual check UX
- **D-17:** "QA Scan All" button triggers full QA across all workspaces simultaneously
- **D-18:** Per-workspace and per-campaign scan buttons also available
- **D-19:** User must get clear feedback during scan — loading state, progress indication, error reporting (no silent timeouts)
- **D-20:** Concurrency must be managed carefully — rate limits per workspace (semaphore from Phase 1 API client)
- **D-21:** Freshness indicator: timestamp + color coding (green <5min, yellow 5-15min, gray >15min)

### Claude's Discretion
- QA result data structure implementation (Pydantic models vs plain dicts)
- Cache implementation (in-memory dict, TTL, etc.)
- Loading UX approach (progressive HTMX updates vs full-page loading vs background+badge)
- APScheduler configuration details
- Error aggregation strategy

</decisions>

<specifics>
## Specific Ideas

- Variable regex must handle `{{RANDOM | opt1 | opt2 | ... }}` — the pipe-separated content inside RANDOM braces should NOT be treated as variable names
- Real data shows variables like `companyName`, `firstName`, `case_study_name`, `approval_year`, `niche`, `loan_amount`, `funding_need`, `sendingAccountName` — all camelCase or snake_case
- The existing `extract_copy_from_campaign()` function in `app/api/instantly.py` already extracts subject+body from campaign sequences — QA engine should consume its output
- Concurrency is critical: "QA Scan All" across 6 workspaces × N campaigns per workspace = potentially hundreds of API calls. Must respect per-workspace rate limits (semaphore of 5 in instantly.py)

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing codebase (Phase 1 output)
- `prospeqt-email-qa/app/api/instantly.py` — Async API client with list_campaigns, fetch_all_leads, extract_copy_from_campaign
- `prospeqt-email-qa/app/models/instantly.py` — Pydantic models for Campaign, Lead, CampaignVariant etc.
- `prospeqt-email-qa/app/services/workspace.py` — Workspace registry (list_workspaces, get_api_key)
- `prospeqt-email-qa/app/main.py` — FastAPI app with lifespan
- `prospeqt-email-qa/tests/fixtures/campaign_response.json` — Real API response shape
- `prospeqt-email-qa/tests/fixtures/leads_response.json` — Real API response shape

### Planning artifacts
- `.planning/PROJECT.md` — Project vision, API data shapes (verified live)
- `.planning/REQUIREMENTS.md` — QA-01 through QA-06, OPS-01 through OPS-06
- `.planning/ROADMAP.md` — Phase 2 success criteria
- `.planning/phases/01-api-foundation/01-CONTEXT.md` — Phase 1 decisions (D-04 stack, D-09 env vars, D-14 error badges, D-15 caching discretion)
- `.planning/research/PITFALLS.md` — API rate limits, background thread pitfalls

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/api/instantly.py`: `list_campaigns()`, `fetch_all_leads()`, `extract_copy_from_campaign()` — the QA engine should call these
- `app/models/instantly.py`: `Lead`, `Campaign`, `CampaignVariant` models — QA results can extend these
- `app/services/workspace.py`: `list_workspaces()`, `get_api_key()` — QA engine iterates over workspaces using these
- Per-workspace semaphore pattern in `instantly.py` — already handles rate limiting

### Established Patterns
- Async/await throughout (FastAPI + httpx)
- Layer-based module structure: `app/api/`, `app/services/`, `app/routes/`, `app/models/`
- Tests use `respx` for mocking httpx, `pytest-asyncio` for async tests
- Fixtures in `tests/fixtures/` with real API response shapes

### Integration Points
- QA engine goes in `app/services/qa_engine.py` (new)
- Background poller goes in `app/services/poller.py` (new)
- Cache goes in `app/services/cache.py` (new)
- QA engine needs routes in Phase 3 — for now it's callable functions only
- APScheduler integrates via FastAPI lifespan in `app/main.py`

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-qa-engine-background*
*Context gathered: 2026-04-04*
