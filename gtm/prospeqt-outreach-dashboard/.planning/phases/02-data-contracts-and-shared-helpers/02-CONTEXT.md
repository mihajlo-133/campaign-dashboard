# Phase 2: Data Contracts and Shared Helpers - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Every data boundary in the codebase has an explicit, documented contract (TypedDict) and duplicated fetcher logic is extracted into shared helpers. No new features, no platform changes, no frontend work.

</domain>

<decisions>
## Implementation Decisions

### Contract Format
- **D-01:** Use Python stdlib `TypedDict` classes to define data contracts: `ClientData`, `CampaignData`, `DailyData` (and any others needed for sub-structures).
- **D-02:** TypedDict definitions go in server.py in a new "Data contracts" section between the current "Constants" section and "Config layer" section. This becomes the single location where any developer (or Claude Code) can see every required and optional key.
- **D-03:** Use `typing.NotRequired` (Python 3.11+) or `total=False` on a separate TypedDict for optional keys (e.g., `in_progress` is None for EmailBison, `daily` is empty for EmailBison).

### Helper Extraction
- **D-04:** Extract `_calc_rates(sent, replies, avg_sent, avg_replies, bounced, bounce_sent)` — the identical rate calculation pattern used by both Instantly and EmailBison fetchers. Returns `(reply_rate_today, reply_rate_7d, bounce_rate)`.
- **D-05:** Extract `_build_client_data(**kwargs)` — assembles the `ClientData` dict from fetcher-provided values, including calling `_trend()` for trend indicators. Both fetchers call this instead of manually building the return dict.
- **D-06:** Leave 7-day average calculation platform-specific. Instantly uses daily array (filter out today, average remaining). EmailBison uses stats endpoint (subtract today, divide by 6). The API shapes differ enough that forcing unification would add abstraction without value.
- **D-07:** Leave campaign iteration and per-campaign dict building platform-specific. Field population differs (Instantly has first_touch, followups, total_leads, per-campaign not_contacted; EmailBison zeros these out).

### Contract Enforcement
- **D-08:** Documentation only — no runtime validation in production code. The TypedDict classes ARE the contract. Tests verify fetcher outputs match the contract.
- **D-09:** Add test(s) that verify both `fetch_instantly_data` and `fetch_emailbison_data` return dicts containing all `ClientData.__required_keys__`. This catches drift without production overhead.

### Claude's Discretion
- Exact TypedDict field names and whether to use `Required`/`NotRequired` vs `total=False` pattern
- Whether to create one TypedDict or split into required base + optional extension
- Placement of new helpers within the existing section structure (likely in "Helpers" section 8)
- Whether `_build_client_data` uses keyword-only args or a simpler signature

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase
- `server.py` lines 509-690 — Instantly fetcher (`fetch_instantly_data`) with current return structure
- `server.py` lines 700-874 — EmailBison fetcher (`fetch_emailbison_data`) with current return structure
- `server.py` lines 881-947 — Helpers section: `_trend()`, `_pool_days_remaining()`, `_classify_client()` (consumers of fetcher data)
- `server.py` lines 1098-1121 — `get_all_data()` and `/api/data` endpoint (frontend consumer)
- `tests/test_api_fetchers.py` — Existing monkeypatch-based fetcher tests (must continue passing)
- `tests/test_classification.py` — Classification tests that consume fetcher output shapes

### Project Rules
- `.claude/rules/dashboard-no-deps.md` — Stdlib-only constraint (TypedDict from `typing` is stdlib, OK)
- `.claude/rules/dashboard-dev.md` — Section map, test patterns, development conventions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_trend(today, avg_7d)` (lines 881-890): Already extracted shared helper for trend indicators — pattern to follow
- `_safe_num(val)` (lines 310-323): Shared numeric coercion for API garbage — already shared
- `_pool_days_remaining(data, client_name)` (lines 893-899): Consumes fetcher data — contract consumer

### Established Patterns
- Both fetchers return nearly identical top-level dict structures (15+ shared keys)
- Rate calculation is duplicated identically: `(numerator / denominator * 100) if denominator > 0 else 0.0`
- Trend calculation uses 3 identical calls to `_trend()` in both fetchers
- Return dict manually assembled in both fetchers with same key names
- Monkeypatch-based testing: `_http_get` and `_http_post` are patched, not the fetcher functions themselves

### Integration Points
- `_fetch_client()` calls the fetcher functions and adds `status`, `kpi`, `thresholds`, `fetched_at` to the result
- `_classify_client()` reads only ~7 keys from the fetcher dict: `active_campaigns`, `total_campaigns`, `sent_today`, `reply_rate_today`, `bounce_rate`, `not_contacted`, `avg_sent_7d`
- Frontend (`dashboard.html`) reads the full `/api/data` response including all fetcher keys plus the keys added by `_fetch_client`

</code_context>

<specifics>
## Specific Ideas

- TypedDict preview shown during discussion was approved as the direction — `ClientData` with nested `CampaignData` list
- `_calc_rates` returns a tuple `(reply_rate_today, reply_rate_7d, bounce_rate)` — caller destructures
- `_build_client_data` uses keyword-only args for clarity (matches TypedDict fields)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-data-contracts-and-shared-helpers*
*Context gathered: 2026-04-03*
