# Phase 2: QA Engine + Background - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-04-04
**Phase:** 02-qa-engine-background
**Areas discussed:** Variable matching, QA result shape, Background poller, Manual check UX

---

## Variable Matching

| Option | Description | Selected |
|--------|-------------|----------|
| Case-sensitive (exact) | {{firstName}} must match exactly | ✓ |
| Case-insensitive | {{FirstName}} matches firstname | |
| You decide | Whatever's safest | |

**User's choice:** Case-sensitive — verified against live API that variables match exactly (camelCase)

| Option | Description | Selected |
|--------|-------------|----------|
| Just those two | Only RANDOM and accountSignature | ✓ |
| All system vars | Also exclude email, first_name, etc. | |
| Let me list them | Specific exclusions | |

**User's choice:** Just RANDOM and accountSignature

---

## QA Result Shape

**User's choice:** Three-level scanning (all → workspace → campaign). "QA Scan All" button for full cross-workspace scan. Concurrency management is critical.

| Option | Description | Selected |
|--------|-------------|----------|
| Just those three | Empty, null, "NO" | ✓ |
| Add 'N/A' | Also flag N/A variants | |
| Configurable | Admin-set per workspace | |

**User's choice:** Just those three — empty string, null/missing, literal "NO"

---

## Background Poller

| Option | Description | Selected |
|--------|-------------|----------|
| Every 5 minutes | Quick discovery, moderate load | ✓ |
| Every 15 minutes | Lower load | |
| Configurable | Default 5min, env var | |
| You decide | Balance freshness/limits | |

**User's choice:** Every 5 minutes, plus manual refresh button
**Notes:** User emphasized both auto-poll AND manual trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Full QA on all | Complete QA every cycle | |
| Discovery only | Just check for new campaigns | ✓ |
| Smart diff | Full QA first, then changes only | |

**User's choice:** Discovery only — full QA only on manual trigger

---

## Manual Check UX

**User's choice:** Claude's discretion on loading approach, but two things are critical:
1. UX feedback — user must know it's working, not timing out or erroring
2. Reliability — all API calls and polling must complete reliably

| Option | Description | Selected |
|--------|-------------|----------|
| Timestamp only | "Last checked: 3 min ago" | |
| Timestamp + color | Green/yellow/gray based on age | ✓ |
| You decide | Whatever works | |

**User's choice:** Timestamp + color coding for freshness

---

## Claude's Discretion

- Loading UX approach (progressive/full-page/background)
- Cache implementation
- QA result data structure
- APScheduler config details

## Deferred Ideas

None
