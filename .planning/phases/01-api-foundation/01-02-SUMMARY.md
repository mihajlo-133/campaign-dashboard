---
phase: 01-api-foundation
plan: 02
subsystem: api
tags: [instantly, httpx, respx, pydantic, async, pagination, rate-limiting]

# Dependency graph
requires:
  - phase: 01-01
    provides: workspace.get_api_key, settings.request_timeout, test fixtures (campaign_response.json, leads_response.json), conftest.py

provides:
  - "app/api/instantly.py: async list_campaigns (GET, cursor pagination, status 0+1 filter)"
  - "app/api/instantly.py: async fetch_all_leads (POST, cursor pagination, status=1 filter)"
  - "app/api/instantly.py: extract_copy_from_campaign (inline variant extraction)"
  - "app/api/instantly.py: _get_semaphore (Semaphore(5) per workspace)"
  - "app/models/instantly.py: Campaign, Lead, CampaignSequence, CampaignStep, CampaignVariant Pydantic models"
  - "tests/test_instantly.py: 9 passing tests covering all client behaviors"

affects: [02-qa-engine, 03-dashboard-views]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cursor pagination: loop on next_starting_after cursor, break when None"
    - "Per-workspace Semaphore(5) stored in module-level dict for rate limiting"
    - "respx.mock for httpx transport-level mocking in async tests"
    - "TDD: RED (failing import) -> fix pagination logic -> GREEN (all 9 pass)"

key-files:
  created:
    - prospeqt-email-qa/app/api/instantly.py
    - prospeqt-email-qa/app/models/instantly.py
    - prospeqt-email-qa/tests/test_instantly.py
  modified: []

key-decisions:
  - "Cursor is the sole pagination termination signal — do not use item count < limit (last pages can be partial)"
  - "Lead variables live in lead['payload'] dict (not custom_variables) — verified against live API 2026-04-04"
  - "Campaign copy is inline in sequences response — no extra API call needed (per API-03)"
  - "Semaphore(5) per workspace stored at module level in _semaphores dict for cross-request reuse"

patterns-established:
  - "Pagination pattern: while True loop, break on not cursor, sleep(0.1) between pages"
  - "Rate limiting: async with _get_semaphore(workspace_name) wraps each HTTP call"
  - "Status filtering applied after collection (not as API param) for predictable behavior"

requirements-completed: [API-01, API-02, API-03, API-04, API-05, API-06, API-07]

# Metrics
duration: 6min
completed: 2026-04-04
---

# Phase 01 Plan 02: Instantly API Client Summary

**Async Instantly v2 API client with cursor pagination (campaigns GET, leads POST), status filtering (draft+active only), inline copy extraction, and per-workspace Semaphore(5) rate limiting — all verified by 9 passing respx-mocked tests**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-04T11:47:00Z
- **Completed:** 2026-04-04T11:53:04Z
- **Tasks:** 1 (TDD)
- **Files modified:** 3

## Accomplishments

- Pydantic v2 models for Campaign, Lead, and inline sequence structure
- list_campaigns: GET with cursor pagination, filters to status 0 (draft) and 1 (active) only
- fetch_all_leads: POST /leads/list with cursor pagination, filters to status=1 active leads only
- extract_copy_from_campaign: flat list of {subject, body} from inline sequences.steps.variants
- Per-workspace Semaphore(5) prevents concurrent request flooding across async callers
- 9 test functions covering pagination, filtering, copy extraction, rate limiting, error handling

## Task Commits

TDD phases (RED → GREEN):

1. **RED: Failing tests** - `0ddee8a` (test: 8 test functions, all failing on ImportError)
2. **GREEN: Implementation** - `a4fd419` (feat: models + API client, all 9 tests pass)

**Plan metadata:** (this commit)

## Files Created/Modified

- `prospeqt-email-qa/app/api/instantly.py` - Async API client: list_campaigns, fetch_all_leads, extract_copy_from_campaign, _get_semaphore
- `prospeqt-email-qa/app/models/instantly.py` - Pydantic v2 models: Campaign, Lead, CampaignVariant, CampaignStep, CampaignSequence
- `prospeqt-email-qa/tests/test_instantly.py` - 9 tests using respx mocks

## Decisions Made

- **Cursor is the sole termination signal**: Initial implementation used `len(items) < 100` as secondary break condition — this caused the pagination test to fail (page 2 had 1 item, not 100). Reverted to cursor-only. The Instantly API signals "no more pages" via null cursor, not partial pages.
- **Lead payload field confirmed**: `lead["payload"]` dict is the correct field for lead variables. Added comment `# Lead variables are in lead["payload"] — verified 2026-04-04`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pagination termination condition**
- **Found during:** Task 1 (GREEN phase — first test run)
- **Issue:** Initial implementation broke pagination on last page with `len(items) < 100` — test had a page2 with 1 item (< limit of 100), so the loop stopped after page1 and missed page2's items
- **Fix:** Removed `len(items) < 100` condition. Loop terminates only when `next_starting_after` is None/falsy. This is correct per Instantly API contract — null cursor means end of results.
- **Files modified:** `prospeqt-email-qa/app/api/instantly.py`
- **Verification:** `test_list_campaigns_returns_all_pages` and `test_fetch_all_leads_pagination` both pass
- **Committed in:** `a4fd419` (same commit as implementation)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in initial pagination logic)
**Impact on plan:** Essential fix — incorrect termination would cause missed campaigns/leads on any workspace with a partial final page.

## Issues Encountered

None beyond the auto-fixed pagination bug above.

## Known Stubs

None — all functions fully implemented and verified.

## Next Phase Readiness

- API client ready for Phase 02 (QA engine) to call list_campaigns + fetch_all_leads
- extract_copy_from_campaign ready for variable parsing layer
- Models ready to be used as type hints in downstream services
- All 9 tests pass — regression coverage in place for future changes

---
*Phase: 01-api-foundation*
*Completed: 2026-04-04*
