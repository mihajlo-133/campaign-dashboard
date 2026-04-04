---
phase: 3
slug: dashboard-views
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | `gtm/prospeqt-outreach-dashboard/tests/conftest.py` |
| **Quick run command** | `cd gtm/prospeqt-outreach-dashboard && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd gtm/prospeqt-outreach-dashboard && python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd gtm/prospeqt-outreach-dashboard && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd gtm/prospeqt-outreach-dashboard && python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | VIEW-04 | unit | `python -m pytest tests/test_models.py -k broken_lead` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | VIEW-04 | unit | `python -m pytest tests/test_qa_engine.py -k broken_leads` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | VIEW-01 | integration | `python -m pytest tests/test_routes.py -k workspace_overview` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | VIEW-02, VIEW-03 | integration | `python -m pytest tests/test_routes.py -k campaign_detail` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 2 | VIEW-04 | integration | `python -m pytest tests/test_routes.py -k lead_detail` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 2 | VIEW-05, VIEW-06 | integration | `python -m pytest tests/test_routes.py -k navigation` | ❌ W0 | ⬜ pending |
| 03-03-02 | 03 | 2 | UX-02, UX-03 | visual | Playwright QA screenshots | ❌ W0 | ⬜ pending |
| 03-03-03 | 03 | 2 | VIEW-07 | integration | `python -m pytest tests/test_routes.py -k scan_trigger` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_models.py` — stubs for BrokenLeadDetail model validation
- [ ] `tests/test_qa_engine.py` — stubs for broken_leads population in run_campaign_qa
- [ ] `tests/test_routes.py` — stubs for all three new route handlers
- [ ] `tests/conftest.py` — shared fixtures (mock cache data, mock QA results with broken_leads)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Health badges render green/yellow/red | UX-02 | Visual color correctness | Take Playwright screenshot at 1440x900, verify badge colors match UI-SPEC hex values |
| HTMX scan refresh updates DOM correctly | VIEW-07 | Browser interaction | Trigger scan via button, verify partial swap replaces campaign row without full reload |
| Mobile responsive layout | UX-03 | Visual breakpoint behavior | Playwright screenshots at 375x812 and 768x1024, verify layout shifts per UI-SPEC |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
