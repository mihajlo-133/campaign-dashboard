---
phase: 03-dashboard-views
plan: "01"
subsystem: qa-data-model
tags: [qa-engine, pydantic, models, tdd, view-04]
status: complete
completed: "2026-04-04"
duration_minutes: 8
tasks_completed: 2
files_changed: 3
requires:
  - "02-02: QA engine with broken_count and issues_by_variable"
provides:
  - "BrokenLeadDetail model for drill-down detail capture"
  - "CampaignQAResult.broken_leads field populated per QA run"
affects:
  - "03-02: Campaign detail view will consume broken_leads"
tech_stack_added: []
tech_stack_patterns:
  - "Pydantic v2 model extension with optional list field (default=[])"
  - "TDD: RED-GREEN-REFACTOR across two commits"
key_files_created: []
key_files_modified:
  - prospeqt-email-qa/app/models/qa.py
  - prospeqt-email-qa/app/services/qa_engine.py
  - prospeqt-email-qa/tests/test_qa_engine.py
decisions:
  - "BrokenLeadDetail captures email, lead_status (raw int), and broken_vars dict with actual values (empty string, None, or 'NO')"
  - "broken_leads defaults to empty list — backward compatible with existing CampaignQAResult consumers"
  - "broken_vars dict stores {varName: currentValue} pairs for each broken variable in the lead"
requirements_satisfied: [VIEW-04]
---

# Phase 03 Plan 01: BrokenLeadDetail Model for Campaign Drill-Down Summary

Extended the QA data model to capture per-lead broken variable detail (BrokenLeadDetail + CampaignQAResult.broken_leads), enabling the campaign drill-down view (VIEW-04) to display specific broken leads with their email, status, and which variables are bad.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Add BrokenLeadDetail model + CampaignQAResult.broken_leads field | 4343e6c | app/models/qa.py, tests/test_qa_engine.py |
| 2 | Update run_campaign_qa to populate broken_leads | ed5b424 | app/services/qa_engine.py, tests/test_qa_engine.py |

## What Was Built

**BrokenLeadDetail** (new Pydantic model in `app/models/qa.py`):
```python
class BrokenLeadDetail(BaseModel):
    email: str
    lead_status: int          # Raw integer status from Instantly API
    broken_vars: dict[str, str | None]  # {varName: currentValue}
```

**CampaignQAResult extension**: Added `broken_leads: list[BrokenLeadDetail] = []` field after `last_checked`. Backward compatible — defaults to empty list.

**qa_engine.py update**: The `run_campaign_qa` loop now builds `broken_lead_details` alongside the existing `broken_lead_ids` set. For each broken lead, a `BrokenLeadDetail` is appended with the lead's email, status, and a dict of `{varName: currentValue}` for every broken variable.

## Verification

```
$ cd prospeqt-email-qa && .venv/bin/python -m pytest tests/ -x -q
88 passed, 6 warnings in 1.29s
```

All 88 tests pass. 6 new tests added (3 model tests + 3 integration tests):
- `test_broken_lead_detail_model` — field access and None value storage
- `test_campaign_qa_result_broken_leads_default` — backward compat empty list
- `test_campaign_qa_result_broken_leads_populated` — populated field roundtrip
- `test_run_campaign_qa_broken_leads_captured` — 2 broken leads from fixture
- `test_run_campaign_qa_broken_leads_detail_values` — correct email, status, broken_vars
- `test_run_campaign_qa_broken_leads_empty_when_clean` — empty list for clean campaigns

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all fields are fully wired. broken_leads is populated with real data from the QA engine loop.

## Self-Check: PASSED

Files confirmed:
- `prospeqt-email-qa/app/models/qa.py` — contains `class BrokenLeadDetail` and `broken_leads: list[BrokenLeadDetail] = []`
- `prospeqt-email-qa/app/services/qa_engine.py` — contains `from app.models.qa import BrokenLeadDetail`, `broken_lead_details: list[BrokenLeadDetail] = []`, `broken_lead_details.append(BrokenLeadDetail(`, `broken_leads=broken_lead_details`
- `prospeqt-email-qa/tests/test_qa_engine.py` — contains all 6 new test functions

Commits confirmed:
- 4343e6c — Task 1 (model + model tests)
- ed5b424 — Task 2 (engine update + integration tests)
