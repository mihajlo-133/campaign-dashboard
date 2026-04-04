# Phase 4: UX Polish + Deployment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** 04-ux-polish-deployment
**Areas discussed:** Visual polish scope, Playwright QA strategy, Render deployment config, UX expert review process

---

## Visual Polish Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Refine current system | Keep existing palette/layout. Improve spacing, typography, hover states, transitions, consistency. | ✓ |
| Elevate to premium | Current palette + refined typography scale, whitespace, transitions, hover lifts, data hierarchy contrast. | |
| Full aesthetic overhaul | New palette, custom fonts, reimagined cards, branded feel. Significantly more work. | |

**User's choice:** Refine current system
**Notes:** Don't reinvent, tighten what's there.

| Option | Description | Selected |
|--------|-------------|----------|
| No dark mode | Light theme only. Internal tool, keep it simple. | ✓ |
| Dark mode via system preference | Auto-detect prefers-color-scheme, swap CSS variables. | |
| Dark mode with toggle | User switch, persisted in localStorage. | |

**User's choice:** No dark mode

| Option | Description | Selected |
|--------|-------------|----------|
| No specifics — just make it polished | Trust UX expert agent to identify and fix issues. | ✓ |
| I have specific things I want improved | User describes pet peeves. | |

**User's choice:** No specifics — full discretion to Claude and UX expert agent.

---

## Playwright QA Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| qa/ directory in project root | qa/screenshot.py, qa/screenshots/. Matches CLAUDE.md convention. | |
| tests/e2e/ directory | Alongside existing unit tests. | |

**User's choice:** Doesn't matter — Claude's discretion.

| Option | Description | Selected |
|--------|-------------|----------|
| Manual human review | Screenshots generated, team eyeballs them. | |
| UX expert agent review | ux-design-expert agent reviews and flags issues. | ✓ |
| Both | Agent reviews first, human does final sign-off. | |

**User's choice:** UX expert agent review only.

| Option | Description | Selected |
|--------|-------------|----------|
| Screenshots only | 3 viewports, static. Run check flow tested via pytest. | |
| Screenshots + interaction flow | Also clicks scan, verifies spinner, waits for HTMX swap, confirms update. | ✓ |

**User's choice:** Screenshots plus full interaction flow.

---

## Render Deployment Config

| Option | Description | Selected |
|--------|-------------|----------|
| New Render service | Separate service and URL. Old dashboard stays. | ✓ |
| Replace existing service | Repoint old service to new app. | |
| New service, deprecate old later | Stand up new, verify, then decide on old. | |

**User's choice:** New Render service. Do not touch old dashboard.
**Notes:** Prior session breadcrumbs document the proven deployment pattern (env vars, dual-mode, clearCache, etc.)

| Option | Description | Selected |
|--------|-------------|----------|
| Free tier | Spins down after 15min, ~30s cold start. Acceptable for internal tool. | ✓ |
| Paid tier | Always-on, no cold starts. | |

**User's choice:** Free tier. Uptime bot to keep it warm is out of scope for this phase.

---

## UX Expert Review Process

| Option | Description | Selected |
|--------|-------------|----------|
| Audit first, then fix | Run UX expert on current state, use findings to drive polish. | |
| Fix first, then audit | Polish based on Claude's judgment, then UX expert as quality gate. | |
| Sandwich — audit, fix, audit | Initial audit, fix, final audit. Two audits, one fix cycle. | |

**User's choice:** UX expert runs after every piece of frontend work — not just once. Continuous gate.

| Option | Description | Selected |
|--------|-------------|----------|
| Max 2 iterations | Cap at 2 fix rounds per deliverable. | |
| Until no critical issues | Keep iterating until zero critical issues. | |
| Claude's discretion | Stop when diminishing returns — cosmetic, not structural. | ✓ |

**User's choice:** Claude's discretion on when to stop iterating.

---

## Claude's Discretion

- Playwright test directory structure
- Specific visual polish improvements (typography, spacing, shadows, transitions)
- Number of UX expert review iterations per deliverable
- GitHub repo setup for Render
- Exact Render service configuration

## Deferred Ideas

- Uptime bot setup (UptimeRobot) — separate task after deployment
- Custom domain for new Render service
- Deprecating old campaign-dashboard Render service
