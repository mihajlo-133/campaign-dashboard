---
phase: 02-qa-engine-background
plan: 01
subsystem: testing
tags: [qa-engine, pydantic, regex, variable-extraction, instantly-api, tdd, asyncio, respx]

requires:
  - phase: 01-api-foundation
    provides: extract_copy_from_campaign, fetch_all_leads, list_campaigns, Lead/Campaign Pydantic models

provides:
  - extract_variables(): extracts {{varName}} placeholders from copy, excludes RANDOM spin and accountSignature
  - is_broken_value(): detects None/empty/"NO" sentinel values
  - check_lead(): case-sensitive payload check returning broken variable names
  - run_campaign_qa(): async per-campaign QA runner returning CampaignQAResult
  - run_workspace_qa(): async workspace-level aggregator with per-campaign error isolation
  - CampaignQAResult, WorkspaceQAResult, GlobalQAResult Pydantic models

affects:
  - 02-02-PLAN (background scheduler consumes run_workspace_qa)
  - 03-routes-templates (API routes expose QA results from these models)

tech-stack:
  added: []
  patterns:
    - TDD with RED/GREEN cycle for pure logic and async runners
    - respx for httpx mocking in async pytest tests
    - Frozenset for system variable exclusion list
    - Error isolation pattern in workspace QA runner (continue on campaign failure)

key-files:
  created:
    - prospeqt-email-qa/app/models/qa.py
    - prospeqt-email-qa/app/services/qa_engine.py
    - prospeqt-email-qa/tests/test_qa_engine.py
    - prospeqt-email-qa/tests/fixtures/qa_campaign_fixture.json
  modified: []

key-decisions:
  - "Pipe character (|) in raw match is the RANDOM spin exclusion signal — simpler and more reliable than checking identifier prefix"
  - "broken_lead_ids uses set for deduplication — distinct broken lead count, not per-variable-per-lead count"
  - "workspace QA runner continues past per-campaign exceptions (error isolation) — one bad campaign doesn't block others"

patterns-established:
  - "extract_variables() strips whitespace from raw match before checking exclusion rules"
  - "check_lead() uses payload.get(var_name) which returns None for missing keys — unified None/missing handling"
  - "run_campaign_qa() and run_workspace_qa() import from app.api.instantly at call site to avoid circular imports"

requirements-completed: [QA-01, QA-02, QA-03, QA-04, QA-05, QA-06]

duration: 3min
completed: 2026-04-04
---

# Phase 02 Plan 01: QA Engine Core Summary

**Regex-based variable extractor, sentinel-aware bad value detector, and async per-campaign/workspace QA runners with 35 TDD tests — all pure logic, no I/O stubs**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-04T13:03:26Z
- **Completed:** 2026-04-04T13:06:19Z
- **Tasks:** 2 (both TDD tasks implemented in one GREEN pass)
- **Files modified:** 4

## Accomplishments

- `extract_variables()` correctly parses `{{varName}}`, strips whitespace from `{{ spacedVar }}`, excludes `{{RANDOM | opt1 | opt2}}` spin syntax (pipe detection) and `{{accountSignature}}` system variable
- `is_broken_value()` flags exactly `None`, `""`, and `"NO"` as broken; case-sensitive — `"no"` and `"N/A"` pass through
- `run_campaign_qa()` returns `CampaignQAResult` with distinct `broken_count` (set deduplication) and per-variable issue counts
- `run_workspace_qa()` aggregates campaigns with error isolation — single campaign failure logs and continues, others unaffected
- 35 new tests pass; full suite 63/63 passed (28 existing Phase 1 + 35 new QA engine tests)

## Task Commits

1. **Tasks 1 + 2: QA engine core (models, extraction, runners, tests)** - `c9ab062` (feat)

**Plan metadata:** TBD (docs commit)

## Files Created/Modified

- `prospeqt-email-qa/app/models/qa.py` — CampaignQAResult, WorkspaceQAResult, GlobalQAResult Pydantic models
- `prospeqt-email-qa/app/services/qa_engine.py` — extract_variables, is_broken_value, check_lead, run_campaign_qa, run_workspace_qa
- `prospeqt-email-qa/tests/test_qa_engine.py` — 35 unit tests covering all QA-01 through QA-06 requirements
- `prospeqt-email-qa/tests/fixtures/qa_campaign_fixture.json` — Campaign fixture with RANDOM spin, accountSignature, spacedVar, and 3 leads (1 clean, 1 empty cityName, 1 NO firstName)

## Decisions Made

- Pipe character (`|`) in raw `{{...}}` match is the RANDOM spin exclusion signal — simpler than checking for `RANDOM` prefix and handles any spin syntax
- `broken_lead_ids` is a `set[str]` for deduplication — `broken_count` reflects distinct leads with issues, not total issue occurrences
- `run_workspace_qa()` continues past per-campaign exceptions — logs the error and proceeds, one broken campaign doesn't abort the workspace QA

## Deviations from Plan

None - plan executed exactly as written. Both TDD tasks were implemented in a single RED→GREEN pass since all functions share the same files (qa_engine.py and test_qa_engine.py).

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- QA engine core complete — `run_workspace_qa()` is the entry point for the background scheduler (Plan 02-02)
- All three result models (`CampaignQAResult`, `WorkspaceQAResult`, `GlobalQAResult`) are ready for API route consumption (Phase 03)
- No blockers — the STATE.md concern about `{{ variableName }}` with spaces is confirmed resolved (test_extract_variables_with_spaces passes)

## Self-Check

Files exist:
- prospeqt-email-qa/app/models/qa.py ✓
- prospeqt-email-qa/app/services/qa_engine.py ✓
- prospeqt-email-qa/tests/test_qa_engine.py ✓
- prospeqt-email-qa/tests/fixtures/qa_campaign_fixture.json ✓

Commit c9ab062 exists ✓ (verified via git log)

---
*Phase: 02-qa-engine-background*
*Completed: 2026-04-04*
