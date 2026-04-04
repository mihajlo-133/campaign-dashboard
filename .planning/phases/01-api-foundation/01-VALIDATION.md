---
phase: 1
slug: api-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.24.x |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | INF-01 | structure | `test -d app/` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | API-01 | integration | `pytest tests/test_instantly.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | API-02 | unit | `pytest tests/test_instantly.py -k filter` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | API-04 | integration | `pytest tests/test_instantly.py -k pagination` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | API-07 | unit | `pytest tests/test_instantly.py -k rate_limit` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ADM-01 | integration | `pytest tests/test_admin.py -k add_workspace` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ADM-03 | integration | `pytest tests/test_admin.py -k auth` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — shared fixtures, async client factory
- [ ] `tests/fixtures/` — mock Instantly API responses (campaigns, leads)
- [ ] `requirements-dev.txt` — pytest, pytest-asyncio, respx
- [ ] pytest framework installed and configured

*Planner will refine task IDs and exact test file paths.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Admin panel visual layout | ADM-01, ADM-02 | UI visual check | Playwright screenshot at 1440x900 |
| Gear icon nav placement | ADM-04 | Visual position | Playwright screenshot showing nav bar |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
