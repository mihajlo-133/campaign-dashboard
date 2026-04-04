---
phase: 02-qa-engine-background
plan: 02
subsystem: cache-and-poller
tags: [cache, background-polling, apscheduler, asyncio, fire-and-forget, deduplication]
dependency_graph:
  requires:
    - 02-01 (QA engine — run_workspace_qa, run_campaign_qa, QA models)
    - app/api/instantly.py (list_campaigns)
    - app/services/workspace.py (list_workspaces, get_api_key)
  provides:
    - app/services/cache.py (QACache, get_cache)
    - app/services/poller.py (discovery_poll, trigger_qa_all, trigger_qa_workspace, trigger_qa_campaign)
    - app/main.py (lifespan wiring — scheduler registration + initial discovery)
  affects:
    - Phase 03 dashboard routes (will read from get_cache().get_all() and get_workspace())
tech_stack:
  added: []
  patterns:
    - asyncio.Lock for in-memory cache protection
    - asyncio.create_task for fire-and-forget background jobs
    - asyncio.gather(return_exceptions=True) for error-isolated parallel workspace discovery
    - APScheduler AsyncIOScheduler interval job registered in FastAPI lifespan
    - Module-level _running_scans dict for deduplication of concurrent QA scans
key_files:
  created:
    - prospeqt-email-qa/app/services/cache.py
    - prospeqt-email-qa/app/services/poller.py
    - prospeqt-email-qa/tests/test_cache.py
    - prospeqt-email-qa/tests/test_poller.py
  modified:
    - prospeqt-email-qa/app/main.py
decisions:
  - "_running_scans is a module-level dict (not an instance variable) — tasks survive across trigger calls, enabling deduplication across different request contexts"
  - "discovery_poll uses asyncio.gather(return_exceptions=True) as the primary error isolation mechanism — _discover_workspace also catches internally so exceptions are always logged before being discarded by gather"
  - "QACache._workspace_campaigns and _workspace_results are separate namespaces — discovery (phase 2) and QA results (manual trigger) are distinct data sources with different lifecycles"
  - "_prune_done_scans called at start of every trigger — prevents unbounded dict growth and re-enables triggering after a scan completes"
  - "lifespan calls await discovery_poll() on startup — dashboard has cached campaign data immediately without waiting for first scheduler interval"
metrics:
  duration: 3 minutes
  completed: 2026-04-04T13:12:25Z
  tasks_completed: 2
  files_created: 4
  files_modified: 1
---

# Phase 02 Plan 02: Cache + Background Poller Summary

**One-liner:** In-memory QACache with asyncio.Lock + background discovery poller using APScheduler interval jobs + fire-and-forget manual QA triggers with concurrent scan deduplication.

## What Was Built

### Task 1 — QACache module (TDD)

`app/services/cache.py` implements an in-memory result store with two namespaces:

- `_workspace_results`: full QA results per workspace (stored by manual triggers)
- `_workspace_campaigns`: campaign lists per workspace (stored by discovery poll)

Both namespaces share a single `asyncio.Lock`. Per-workspace error tracking is cleared automatically when a successful result is stored. `get_all()` aggregates across all workspaces into a `GlobalQAResult`.

`get_cache()` returns the module-level singleton used by poller and (in Phase 3) by dashboard routes.

10 unit tests: set/get, aggregation, error tracking, campaign storage, singleton identity.

### Task 2 — Poller + lifespan wiring (TDD)

`app/services/poller.py` provides:

**Discovery polling:**
- `discovery_poll()`: runs `_discover_workspace()` for all workspaces in parallel via `asyncio.gather(return_exceptions=True)`. Per-workspace failures are caught inside `_discover_workspace` and stored as cache errors — they cannot propagate to cancel other workspace discoveries. Updates `last_refresh` timestamp after all workspaces complete.

**Manual QA triggers:**
- `trigger_qa_all()`: creates background tasks for all workspaces, returns `{status: started, workspaces_triggered: N}` immediately
- `trigger_qa_workspace()`: creates background task for one workspace, deduplicates via `_running_scans`
- `trigger_qa_campaign()`: creates background task for one campaign, deduplicates via `_running_scans`

**Deduplication:**
- `_running_scans` dict maps `task_key -> asyncio.Task`
- `_prune_done_scans()` removes completed tasks at the start of every trigger call
- Second trigger for the same scope while first is running returns `{status: already_running}`

**app/main.py lifespan updated:**
- Imports `discovery_poll` from poller
- Registers `discovery_poll` as APScheduler interval job (interval from `QA_POLL_INTERVAL_SECONDS` env var, default 300s)
- Calls `await discovery_poll()` immediately on startup

9 unit tests covering discovery, error isolation, fire-and-forget returns, deduplication, and cleanup.

## Verification Evidence

```
82 passed, 6 warnings in 0.98s
```

Test breakdown:
- 63 existing Phase 1 tests: all pass
- 10 new cache tests: all pass
- 9 new poller tests: all pass

```
$ grep -c "def test_" tests/test_poller.py
9
$ grep -c "def test_" tests/test_cache.py
10
$ grep "discovery_poll" app/main.py
from app.services.poller import discovery_poll
        discovery_poll,
        id="discovery_poll",
    await discovery_poll()
$ grep "QA_POLL_INTERVAL_SECONDS" app/main.py
    poll_interval = int(os.getenv("QA_POLL_INTERVAL_SECONDS", "300"))
```

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1 — QACache + tests | f96176b | cache.py, test_cache.py |
| Task 2 — Poller + lifespan + tests | ff825fb | poller.py, main.py, test_poller.py |

## Deviations from Plan

None — plan executed exactly as written.

The `test_trigger_cleanup_done_tasks` test required adding `await asyncio.sleep(0.05)` after the second trigger to allow the newly created background task time to execute before the assertion. This was a test timing detail, not a deviation from the implementation specification.

## Known Stubs

None. All functions return real data from the cache. Phase 3 dashboard routes will read from `get_cache().get_all()` and `get_workspace()` — both are fully implemented.

## Self-Check: PASSED
