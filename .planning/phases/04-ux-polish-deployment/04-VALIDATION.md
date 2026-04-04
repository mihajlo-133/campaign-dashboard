---
phase: 4
slug: ux-polish-deployment
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio + Playwright CLI |
| **Config file** | `prospeqt-email-qa/tests/conftest.py` |
| **Quick run command** | `cd prospeqt-email-qa && .venv/bin/python -m pytest tests/ -x -q` |
| **Full suite command** | `cd prospeqt-email-qa && .venv/bin/python -m pytest tests/ -v` |
| **Estimated runtime** | ~8 seconds (unit/integration) + ~15 seconds (Playwright E2E) |

---

## Sampling Rate

- **After every task commit:** Run `cd prospeqt-email-qa && .venv/bin/python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd prospeqt-email-qa && .venv/bin/python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 8 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | UX-01 | visual | Playwright screenshots at 3 viewports + ux-design-expert review | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | UX-01 | unit | `python -m pytest tests/ -x -q` (no regressions) | ✅ | ⬜ pending |
| 04-02-01 | 02 | 2 | UX-04 | e2e | Playwright screenshot + interaction flow test | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | UX-04 | visual | ux-design-expert agent review of screenshots | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 3 | UX-05 | integration | `curl -s <render-url>/health` returns 200 | ❌ W0 | ⬜ pending |
| 04-03-02 | 03 | 3 | UX-05 | smoke | Playwright screenshot of live Render deployment | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Playwright E2E test file — stubs for viewport screenshots and interaction flow
- [ ] QA screenshot script — captures 3 viewports programmatically

*Existing test infrastructure (pytest + conftest.py) covers all unit/integration requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Luxury aesthetic passes UX expert review | UX-01 | Subjective visual quality | ux-design-expert agent reviews Playwright screenshots and flags issues |
| Scan interaction flow works end-to-end | UX-04 | Browser interaction with HTMX | Playwright clicks scan, verifies spinner, waits for swap, confirms results |
| Live Render URL accessible to team | UX-05 | External service availability | curl the Render URL, verify 200 response and HTML content |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 8s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
