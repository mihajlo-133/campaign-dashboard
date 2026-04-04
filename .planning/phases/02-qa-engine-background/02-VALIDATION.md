---
phase: 2
slug: qa-engine-background
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.24.x |
| **Config file** | `prospeqt-email-qa/pytest.ini` |
| **Quick run command** | `cd prospeqt-email-qa && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd prospeqt-email-qa && python -m pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd prospeqt-email-qa && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd prospeqt-email-qa && python -m pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | QA-01 | unit | `pytest tests/test_qa_engine.py -k extract_variables` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | QA-02 | unit | `pytest tests/test_qa_engine.py -k spin_syntax` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | QA-03 | unit | `pytest tests/test_qa_engine.py -k account_signature` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 1 | QA-04 | unit | `pytest tests/test_qa_engine.py -k bad_value` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 1 | QA-05 | unit | `pytest tests/test_qa_engine.py -k broken_count` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | OPS-01 | unit | `pytest tests/test_poller.py -k schedule` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | OPS-02 | unit | `pytest tests/test_poller.py -k error_isolation` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 1 | OPS-03 | unit | `pytest tests/test_cache.py -k ttl` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | QA-06 | integration | `pytest tests/test_qa_integration.py -k manual_trigger` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 2 | OPS-04 | integration | `pytest tests/test_qa_integration.py -k workspace_scan` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `prospeqt-email-qa/tests/test_qa_engine.py` — stubs for QA-01 through QA-06
- [ ] `prospeqt-email-qa/tests/test_poller.py` — stubs for OPS-01 through OPS-03
- [ ] `prospeqt-email-qa/tests/test_cache.py` — stubs for OPS-03
- [ ] `prospeqt-email-qa/tests/test_qa_integration.py` — stubs for QA-06, OPS-04
- [ ] `prospeqt-email-qa/tests/fixtures/campaign_with_variables.json` — mock campaign with various variable patterns
- [ ] `prospeqt-email-qa/tests/fixtures/leads_with_broken_vars.json` — mock leads with empty/null/"NO" values

*Existing infrastructure (pytest, respx, conftest.py) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Freshness indicator color coding | OPS-05 | Visual/CSS behavior | Inspect timestamp display after cache update |
| Loading state UX during scan | OPS-06 | Visual/UX behavior | Trigger manual scan, observe loading indicators |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
