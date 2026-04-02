# Phase 1: Critical Bug Fixes - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the 4 critical bugs that block production use: broken admin panel (6 undefined functions), backfill race condition (stale not_contacted), and unbounded thread spawning. No new features, no refactoring beyond what's needed to fix the bugs.

</domain>

<decisions>
## Implementation Decisions

### Admin Authentication
- **D-01:** No user accounts or roles. Single shared password for the internal team. Password set via environment variable (existing `ADMIN_PASSWORD` pattern).
- **D-02:** After entering the correct password, set an httpOnly cookie valid for 8 hours. No re-authentication on page refresh within that window.
- **D-03:** Implement the 6 missing functions (`_check_admin_auth`, `_make_token`, and any others referenced but undefined) using HMAC-SHA256 of the password to generate the cookie token. Stdlib only (hashlib + hmac).

### Backfill Race Condition
- **D-04:** Use a generation counter to prevent stale backfill writes. Each `_fetch_client` call increments a per-client generation number. The backfill thread captures the generation at spawn time and checks it matches before writing results to cache. If generation has advanced (meaning a newer fetch happened), discard the backfill results silently.

### Thread Bounding
- **D-05:** One global `ThreadPoolExecutor(max_workers=10)` shared across all refresh cycles for backfill work. Replace the current `threading.Thread()` spawning pattern (line 1039-1044) with pool submissions. Natural backpressure — if pool is busy, new backfills queue rather than spawning unbounded threads.

### Test Strategy
- **D-06:** Focused regression tests (~5-8 new tests): admin routes return 200/401 (no NameError), backfill respects generation counter (stale writes discarded), thread pool stays bounded. Existing classification tests must continue passing.

### Data Accuracy
- **D-07:** Data accuracy confirmed as correct by manual inspection. No audit step needed in Phase 1. Will investigate if discrepancies surface later.

### Claude's Discretion
- Cookie name, HMAC secret derivation, and exact token format
- Generation counter storage mechanism (dict vs attribute on cache)
- Specific test fixture design for admin auth tests

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase
- `server.py` lines 1155-1215 — Admin HTTP handler routes (where NameError occurs)
- `server.py` lines 969-1001 — `_backfill_nc` function (race condition location)
- `server.py` lines 1003-1050 — `_fetch_client` function (thread spawning location)
- `server.py` lines 953-967 — Cache globals and `_should_refresh` (cache TTL logic)

### Project Rules
- `.claude/rules/dashboard-no-deps.md` — Stdlib-only constraint (no pip packages)
- `.claude/rules/dashboard-dev.md` — Development conventions, section map, test patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_cache_lock` (threading.Lock): Already used for cache synchronization — backfill fix should use this same lock
- `_cache_data`, `_cache_ts` dicts: Existing cache storage pattern — generation counter fits alongside these
- Cookie pattern at line 1203: `admin_token={token}; Max-Age=28800; Path=/; HttpOnly; SameSite=Strict` — already scaffolded, just needs the token generation function
- `hashlib` and `hmac` already imported or available in stdlib

### Established Patterns
- All cache mutations happen inside `with _cache_lock:` blocks
- Background work uses daemon threads (`daemon=True`)
- HTTP handler is a single `Handler` class with `do_GET`/`do_POST` methods
- Config read via `get_config()` with lock protection

### Integration Points
- Admin routes in `do_GET` (lines 1159, 1173, 1209) and `do_POST` — these call the undefined functions
- `_fetch_client` (line 1038-1044) — where backfill threads spawn, needs pool replacement
- `_background_refresh_loop` (line 1055) — orchestrates refresh cycle, no changes needed if pool is global

</code_context>

<specifics>
## Specific Ideas

- Internal tool — security model is "shared password among teammates," not enterprise auth
- Data accuracy was checked manually and confirmed correct as of today — no systematic audit needed

</specifics>

<deferred>
## Deferred Ideas

- Data accuracy audit (systematic comparison of dashboard vs Instantly UI) — revisit if discrepancies surface
- Reply categorization (positive/neutral/negative) — v2 scope

</deferred>

---

*Phase: 01-critical-bug-fixes*
*Context gathered: 2026-04-02*
