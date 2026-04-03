---
phase: 01-critical-bug-fixes
plan: 02
subsystem: cache-threading
tags: [bug-fix, threading, race-condition, backfill, tdd]
dependency_graph:
  requires: [01-01]
  provides: [backfill-generation-counter, thread-pool-bounding]
  affects: [server.py:_backfill_nc, server.py:_fetch_client, server.py:_background_refresh_loop, server.py:do_POST]
tech_stack:
  added: [concurrent.futures.ThreadPoolExecutor]
  patterns: [generation-counter, pool-submit-instead-of-raw-threads]
key_files:
  created: [tests/test_backfill_threading.py]
  modified: [server.py]
decisions:
  - Generation counter merged into existing _cache_lock block to prevent two-lock acquisition
  - pool.submit called outside _cache_lock (gen captured inside lock, submit outside)
  - startup pre-fetch in main() intentionally left as raw threads (sequential startup, not production path)
metrics:
  duration_minutes: 8
  completed_date: "2026-04-03T09:05:38Z"
  tasks_completed: 1
  files_changed: 2
requirements_closed: [BUG-03, BUG-04]
---

# Phase 01 Plan 02: Backfill Race Condition + Thread Pool Bounding Summary

**One-liner:** Generation counter prevents stale backfill overwrites; ThreadPoolExecutor(max_workers=10) replaces all raw threading.Thread() calls in fetch/backfill/refresh paths.

## What Was Built

### Backfill Race Condition Fix (BUG-03)

Added `_cache_generation = {}` — a monotonic integer counter per client. Every time `_fetch_client` writes fresh data to the cache, it increments that client's generation and captures the new value (`gen`). When `_backfill_nc` completes its slow leads/list API work, it checks `_cache_generation.get(client_name, 0) != generation` before writing. If a newer fetch occurred while backfill was running, the stale results are discarded silently.

The generation check is merged into the existing `with _cache_lock:` block — a single lock acquisition does both the staleness check and the cache update atomically.

### Thread Pool Bounding (BUG-04)

Added `_backfill_pool = ThreadPoolExecutor(max_workers=10)` as a module-level global. Three call sites converted from raw `threading.Thread` to `_backfill_pool.submit`:

| Location | Before | After |
|---|---|---|
| `_fetch_client` backfill launch | `threading.Thread(...).start()` | `_backfill_pool.submit(_backfill_nc, ..., gen)` |
| `_background_refresh_loop` per-client refresh | `threading.Thread(...).start()` per client | `_backfill_pool.submit(_fetch_client, name)` |
| `do_POST /api/refresh` manual refresh | `threading.Thread(...).start()` per client | `_backfill_pool.submit(_fetch_client, name)` |

Remaining `threading.Thread` uses:
- `_worker` helpers inside `_paginate_instantly` and `fetch_emailbison_data` — within-fetch parallelism for a single API call sequence; acceptable
- `start_background_refresh` — creates the single daemon thread that runs `_background_refresh_loop`; required startup pattern
- `main()` startup pre-fetch — sequential startup, not the production path

### Regression Tests

`tests/test_backfill_threading.py` — 8 tests across 2 classes:

- `TestGenerationCounter` (4 tests): stale discard, fresh write, signature check, dict exists
- `TestThreadPoolBounding` (4 tests): pool exists with max_workers=10, no threading.Thread in _fetch_client, _background_refresh_loop, or do_POST

## Tasks Completed

| Task | Name | Commit | Files |
|---|---|---|---|
| 1 | Add generation counter + ThreadPoolExecutor pool | d33f126 | server.py, tests/test_backfill_threading.py |

## Test Results

```
77 passed in 0.05s
```

All 69 pre-existing tests continue to pass. 8 new regression tests added.

## Verification Evidence

```
$ grep -n "_backfill_pool.submit" server.py
1053:            _backfill_pool.submit(_backfill_nc, client_name, nc_backfill, nc_api_key, gen)
1070:                futures.append(_backfill_pool.submit(_fetch_client, name))
1229:                _backfill_pool.submit(_fetch_client, name)

$ grep -n "_cache_generation" server.py
958:_cache_generation = {}   # {client_name: int} — monotonic generation counter...
990:        current_gen = _cache_generation.get(client_name, 0)
1048:            _cache_generation[client_name] = _cache_generation.get(client_name, 0) + 1
1049:            gen = _cache_generation[client_name]
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- [x] `server.py` modified and committed (d33f126)
- [x] `tests/test_backfill_threading.py` created and committed (d33f126)
- [x] All 77 tests pass
- [x] `_cache_generation` dict exists at line 958
- [x] `_backfill_pool = ThreadPoolExecutor(max_workers=10)` at line 962
- [x] `_backfill_nc` signature includes `generation: int`
- [x] 3 `_backfill_pool.submit` call sites confirmed
- [x] No `threading.Thread` in _fetch_client, _background_refresh_loop, or do_POST refresh handler
