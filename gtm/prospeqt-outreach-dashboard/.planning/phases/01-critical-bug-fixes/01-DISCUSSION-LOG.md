# Phase 1: Critical Bug Fixes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-02
**Phase:** 01-critical-bug-fixes
**Areas discussed:** Admin auth design, Backfill race fix, Thread bounding, Test strategy, Data accuracy

---

## Admin Authentication

| Option | Description | Selected |
|--------|-------------|----------|
| Simple HMAC token | HMAC-SHA256 of password + timestamp, httpOnly cookie, 8-hour expiry | |
| Random session token | Random token on login, server-side dict storage | |
| You decide | Claude picks simplest approach | |

**User's choice:** "There is no need to have admin auth, this is an internal tool, we just have to have a password we share internally"
**Notes:** User explicitly rejected session/user-account approaches. Simple shared password is the requirement.

### Follow-up: Password Persistence

| Option | Description | Selected |
|--------|-------------|----------|
| Cookie for 8 hours | Enter password once, httpOnly cookie keeps you in | ✓ |
| Every page load | No cookies, password form every visit | |

**User's choice:** Cookie for 8 hours
**Notes:** Convenience over maximum simplicity — don't want to re-enter on every page refresh.

---

## Backfill Race Condition

| Option | Description | Selected |
|--------|-------------|----------|
| Generation counter | Each fetch increments generation; backfill checks before writing | ✓ |
| Timestamp guard | Backfill records cache timestamp, checks before writing | |
| You decide | Claude picks simplest approach | |

**User's choice:** Generation counter (Recommended)
**Notes:** None

---

## Thread Bounding

| Option | Description | Selected |
|--------|-------------|----------|
| One global pool | Single ThreadPoolExecutor(max_workers=10), natural backpressure | ✓ |
| Per-refresh pool | New pool per cycle, each capped at 10 | |

**User's choice:** One global pool (Recommended)
**Notes:** None

---

## Test Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Focused regression tests | Admin routes, backfill generation, thread bounds. ~5-8 tests | ✓ |
| Minimal smoke tests | Admin routes return 200/401, existing tests pass. ~2-3 tests | |
| You decide | Claude decides based on severity | |

**User's choice:** Focused regression tests (Recommended)
**Notes:** None

---

## Data Accuracy

| Option | Description | Selected |
|--------|-------------|----------|
| Known wrong numbers | Specific metrics don't match Instantly UI | |
| Verify before shipping | Manual audit step before closing Phase 1 | |
| Both | Discrepancies seen AND need systematic check | |

**User's initial choice:** Known wrong numbers
**Follow-up:** User checked and determined "It actually seems to be correct now, even though I thought it was not."

| Option | Description | Selected |
|--------|-------------|----------|
| Add audit step | Spot-check 2-3 clients vs Instantly UI before closing Phase 1 | |
| Skip for now | Data looks correct, focus on the 4 bugs | ✓ |

**User's choice:** Skip for now
**Notes:** Data accuracy concern resolved by manual inspection during the discussion.

---

## Claude's Discretion

- Cookie name, HMAC secret derivation, exact token format
- Generation counter storage mechanism
- Test fixture design for admin auth

## Deferred Ideas

- Data accuracy audit — revisit if discrepancies surface
- Reply categorization — v2 scope
