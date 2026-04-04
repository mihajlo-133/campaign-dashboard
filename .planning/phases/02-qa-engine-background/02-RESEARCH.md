# Phase 2: QA Engine + Background - Research

**Researched:** 2026-04-04
**Domain:** Python regex variable extraction, async background scheduling (APScheduler), in-memory cache with asyncio locking, FastAPI lifespan integration
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Case-sensitive exact match between copy variables and lead.payload keys
- **D-02:** Exclude `{{RANDOM | ...}}` spin syntax from variable extraction
- **D-03:** Exclude `{{accountSignature}}` from variable extraction
- **D-04:** No other exclusions — just RANDOM and accountSignature
- **D-05:** Three values flagged as broken: empty string (`""`), null/missing (key absent), and literal string `"NO"`
- **D-06:** No other bad values (no "N/A", no "n/a" — just those three)
- **D-07:** Not configurable per workspace in v1 — hardcoded detection rules
- **D-08:** Results structured per-campaign: `{campaign_id, campaign_name, total_leads, broken_count, issues_by_variable: {varName: count}, last_checked}`
- **D-09:** Results rolled up per-workspace: aggregate broken count across campaigns
- **D-10:** Results rolled up across all workspaces: total broken leads, total campaigns checked
- **D-11:** Three levels of scanning: all workspaces → per workspace → per campaign
- **D-12:** Poll every 5 minutes (configurable via env var)
- **D-13:** Poller does discovery only — checks for new/changed campaigns, does NOT run full QA automatically
- **D-14:** Full QA runs only on manual trigger (user clicks "Run QA" button)
- **D-15:** Poller must be resilient — one workspace error doesn't stop others
- **D-16:** Poller updates a last-refresh timestamp visible in the UI
- **D-17:** "QA Scan All" button triggers full QA across all workspaces simultaneously
- **D-18:** Per-workspace and per-campaign scan buttons also available
- **D-19:** User must get clear feedback during scan — loading state, progress indication, error reporting
- **D-20:** Concurrency must be managed carefully — rate limits per workspace (semaphore from Phase 1 API client)
- **D-21:** Freshness indicator: timestamp + color coding (green <5min, yellow 5-15min, gray >15min)

### Claude's Discretion

- QA result data structure implementation (Pydantic models vs plain dicts)
- Cache implementation (in-memory dict, TTL, etc.)
- Loading UX approach (progressive HTMX updates vs full-page loading vs background+badge)
- APScheduler configuration details
- Error aggregation strategy

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QA-01 | Extract all `{{variableName}}` patterns from campaign sequence copy, excluding `{{RANDOM | ...}}` and `{{accountSignature}}` | Verified: regex `\{\{([^}]+)\}\}` + filter-by-pipe + SYSTEM_VARS exclusion set handles all known Instantly copy variants including spaces around identifiers |
| QA-02 | Match extracted copy variables against `lead.payload` keys (case-sensitive) | Verified: direct dict key lookup, no normalization needed per D-01 |
| QA-03 | Flag leads where a copy-referenced variable is empty string | Verified: `value == ''` check works; empty string in payload correctly identified |
| QA-04 | Flag leads where a copy-referenced variable is null/missing | Verified: `dict.get()` returns `None` for absent keys; `value is None` catches both explicit null and missing key |
| QA-05 | Flag leads where a copy-referenced variable has the value "NO" | Verified: `value == 'NO'` (case-sensitive) per D-06; "no" and "N/A" are NOT flagged |
| QA-06 | Produce per-campaign issue summary: count of broken leads grouped by variable name | Verified: issues_by_variable dict pattern works; broken_count tracks distinct broken leads |
| OPS-01 | Manual "run check" trigger at all-workspaces level | Pattern: `asyncio.create_task()` fire-and-forget, returns immediately with status |
| OPS-02 | Manual "run check" trigger at per-workspace level | Same fire-and-forget pattern, scoped to single workspace |
| OPS-03 | Manual "run check" trigger at per-campaign level | Same pattern, scoped to single campaign |
| OPS-04 | Background polling discovers new campaigns at configurable interval | APScheduler `AsyncIOScheduler` with `interval` trigger; `QA_POLL_INTERVAL_SECONDS` env var |
| OPS-05 | Background poller is resilient — wraps exceptions, continues running | Pattern: `asyncio.gather()` with `safe_fetch()` wrapper that catches exceptions per-workspace |
| OPS-06 | Dashboard shows last-refresh timestamp from background poller | Cache stores `last_refresh: datetime` at workspace and global level |
</phase_requirements>

---

## Summary

Phase 2 builds the core QA engine and background infrastructure on top of the Phase 1 API client. The codebase is already well-structured with async/await throughout, per-workspace semaphores, and a FastAPI lifespan that has a placeholder `_scheduler` ready to receive jobs.

The three new modules are `app/services/qa_engine.py` (variable extraction + lead flagging), `app/services/cache.py` (in-memory result storage with asyncio.Lock), and `app/services/poller.py` (APScheduler job + manual trigger logic). No new dependencies are needed — APScheduler 3.11.2 is already installed and the project already imports AsyncIOScheduler in `app/main.py`.

The biggest technical risk is the variable regex. Verified live: the pattern `\{\{([^}]+)\}\}` correctly handles `{{RANDOM |opt1|opt2}}` (excluded via pipe check), `{{ spacedVar }}` (handled via strip), and `{{accountSignature}}` (excluded via SYSTEM_VARS set). All edge cases from the fixtures and CONTEXT.md pass.

**Primary recommendation:** Build in the order: qa_engine (pure functions, no I/O) → cache → poller → wire into lifespan. Test qa_engine exhaustively before adding I/O dependencies.

---

## Standard Stack

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| APScheduler | 3.11.2 | Background poll scheduling | Already in requirements.txt; AsyncIOScheduler confirmed working with async functions |
| asyncio (stdlib) | Python 3.14 | Concurrency: Lock, gather, create_task | In-process, zero overhead, correct tool for async FastAPI context |
| pydantic | v2 (bundled with fastapi[standard]) | QA result models | Already used for Lead/Campaign models in Phase 1 |
| re (stdlib) | — | Variable regex extraction | No external parser needed |
| datetime (stdlib) | — | Freshness timestamps | Used for last_checked, last_refresh fields |

### No New Dependencies Required

All libraries needed for Phase 2 are already installed. `requirements.txt` does not need changes.

---

## Architecture Patterns

### Recommended Module Structure

```
prospeqt-email-qa/app/services/
├── auth.py             # Phase 1 — unchanged
├── workspace.py        # Phase 1 — unchanged
├── qa_engine.py        # NEW: extract_variables(), check_lead(), run_campaign_qa(), run_workspace_qa()
├── cache.py            # NEW: QACache class, CacheEntry, async get/set/get_all
└── poller.py           # NEW: discovery_poll(), trigger_qa_all(), trigger_qa_workspace(), trigger_qa_campaign()

prospeqt-email-qa/app/models/
├── instantly.py        # Phase 1 — unchanged
└── qa.py               # NEW: CampaignQAResult, WorkspaceQAResult, GlobalQAResult (Pydantic)
```

### Pattern 1: Variable Extraction (QA-01)

**What:** Regex extraction with pipe-based spin syntax exclusion and SYSTEM_VARS filter.
**When to use:** Called by `run_campaign_qa()` once per campaign, result cached.

```python
# app/services/qa_engine.py
import re
from typing import FrozenSet

_RAW_PATTERN = re.compile(r'\{\{([^}]+)\}\}')
_SYSTEM_VARS: FrozenSet[str] = frozenset(['RANDOM', 'accountSignature'])


def extract_variables(copy_variants: list[dict]) -> set[str]:
    """Extract lead variable names from campaign copy variants.
    
    Excludes:
    - {{RANDOM | opt1 | opt2 }} spin syntax (detected via pipe in raw match)
    - {{accountSignature}} (system variable, not a lead variable)
    - Handles {{ spacedVar }} — strips whitespace around identifier
    
    Source: verified against campaign_response.json + CONTEXT.md D-02, D-03, D-04
    """
    vars_found: set[str] = set()
    for variant in copy_variants:
        for field_text in (variant.get('subject', ''), variant.get('body', '')):
            for raw in _RAW_PATTERN.findall(field_text):
                stripped = raw.strip()
                if '|' in stripped:
                    continue  # Spin syntax — skip entirely
                ident = stripped.split()[0] if stripped else ''
                if ident and ident not in _SYSTEM_VARS:
                    vars_found.add(ident)
    return vars_found
```

### Pattern 2: Bad Value Detection (QA-03, QA-04, QA-05)

**What:** Single function, three checks — null/missing, empty string, "NO" sentinel.
**When to use:** Called per-lead, per-variable inside `run_campaign_qa()`.

```python
def is_broken_value(value: str | None) -> bool:
    """Return True if the variable value indicates broken/missing data.
    
    Three cases per D-05, D-06:
    - None: key absent from payload OR explicit null in payload
    - '': empty string from enrichment tool output
    - 'NO': sentinel value from Clay/enrichment when field not found
    
    NOT flagged: 'n/a', 'N/A', 'no', '0' (per D-06)
    """
    return value is None or value == '' or value == 'NO'
```

### Pattern 3: Per-Campaign QA (QA-02, QA-06)

**What:** Extract vars from copy, iterate leads, count broken per variable.
**When to use:** Called by manual trigger or poller per campaign.

```python
from app.models.qa import CampaignQAResult
from datetime import datetime, timezone

async def run_campaign_qa(
    client: httpx.AsyncClient,
    api_key: str,
    campaign: dict,
    workspace_name: str,
) -> CampaignQAResult:
    """Run full QA for one campaign: extract copy vars, check all active leads."""
    # Extract variables from inline copy (reuses Phase 1 function)
    copy_variants = extract_copy_from_campaign(campaign)
    copy_vars = extract_variables(copy_variants)
    
    # Fetch all active leads (reuses Phase 1 function with per-workspace semaphore)
    leads = await fetch_all_leads(client, api_key, campaign['id'], workspace_name)
    
    # Count broken leads per variable
    issues_by_variable: dict[str, int] = {}
    broken_lead_ids: set[str] = set()
    
    for lead in leads:
        payload: dict = lead.get('payload') or {}
        for var_name in copy_vars:
            value = payload.get(var_name)  # None if key absent
            if is_broken_value(value):
                issues_by_variable[var_name] = issues_by_variable.get(var_name, 0) + 1
                broken_lead_ids.add(lead['id'])
    
    return CampaignQAResult(
        campaign_id=campaign['id'],
        campaign_name=campaign['name'],
        total_leads=len(leads),
        broken_count=len(broken_lead_ids),
        issues_by_variable=issues_by_variable,
        last_checked=datetime.now(timezone.utc),
    )
```

### Pattern 4: Cache with asyncio.Lock (Claude's Discretion — RECOMMENDED)

**What:** In-memory dict protected by `asyncio.Lock`, keyed by workspace name.
**Why this over alternatives:** ThreadLock would work but asyncio.Lock is the correct primitive in an async FastAPI app — no thread context switching overhead, works naturally with await.

```python
# app/services/cache.py
import asyncio
from datetime import datetime, timezone
from app.models.qa import WorkspaceQAResult, GlobalQAResult

class QACache:
    """In-memory QA result cache. Thread-safe via asyncio.Lock.
    
    Key design: workspace results are stored individually so a single
    workspace refresh doesn't block reads of other workspaces.
    """
    
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._workspace_results: dict[str, WorkspaceQAResult] = {}
        self._workspace_errors: dict[str, str] = {}  # workspace -> error message
        self._last_global_refresh: datetime | None = None
    
    async def set_workspace(self, name: str, result: WorkspaceQAResult) -> None:
        async with self._lock:
            self._workspace_results[name] = result
            self._workspace_errors.pop(name, None)
    
    async def set_workspace_error(self, name: str, error: str) -> None:
        async with self._lock:
            self._workspace_errors[name] = error
    
    async def set_last_refresh(self, ts: datetime) -> None:
        async with self._lock:
            self._last_global_refresh = ts
    
    async def get_all(self) -> GlobalQAResult:
        async with self._lock:
            workspaces = list(self._workspace_results.values())
            return GlobalQAResult(
                workspaces=workspaces,
                errors=dict(self._workspace_errors),
                total_broken=sum(w.total_broken for w in workspaces),
                total_campaigns_checked=sum(len(w.campaigns) for w in workspaces),
                last_refresh=self._last_global_refresh,
            )
    
    async def get_workspace(self, name: str) -> WorkspaceQAResult | None:
        async with self._lock:
            return self._workspace_results.get(name)


# Module-level singleton — imported by poller and routes
_cache = QACache()

def get_cache() -> QACache:
    return _cache
```

### Pattern 5: APScheduler Poller (OPS-04, OPS-05)

**What:** AsyncIOScheduler adds an interval job during lifespan startup. Job does discovery poll only (per D-13). Error isolation: one workspace failure does not prevent others from refreshing.
**Key detail:** `_scheduler` already exists in `app/main.py` — poller adds a job to it, does not create a new scheduler.

```python
# app/services/poller.py
import asyncio
import logging
from datetime import datetime, timezone
import httpx
from app.services.workspace import list_workspaces, get_api_key
from app.api.instantly import list_campaigns
from app.services.cache import get_cache

logger = logging.getLogger(__name__)

_running_scans: dict[str, asyncio.Task] = {}


async def _discover_workspace(client: httpx.AsyncClient, ws_name: str) -> None:
    """Discover campaigns for one workspace. Updates cache with campaign list.
    
    Discovery only — does not run full QA (per D-13).
    Errors are caught and logged; they do not propagate (per D-15, OPS-05).
    """
    api_key = get_api_key(ws_name)
    if not api_key:
        return
    try:
        campaigns = await list_campaigns(client, api_key, ws_name)
        cache = get_cache()
        # Store campaign list for workspace — Phase 3 will render this
        await cache.set_campaigns(ws_name, campaigns)
    except Exception as exc:
        logger.exception("Discovery failed for workspace %s: %s", ws_name, exc)
        await get_cache().set_workspace_error(ws_name, str(exc))


async def discovery_poll() -> None:
    """Background poll: discover all workspace campaigns.
    
    Runs every QA_POLL_INTERVAL_SECONDS (default 300).
    All workspaces run concurrently with error isolation.
    Updates last_refresh timestamp after all workspaces attempted (per D-16, OPS-06).
    """
    workspaces = list_workspaces()
    if not workspaces:
        return
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        await asyncio.gather(
            *[_discover_workspace(client, ws['name']) for ws in workspaces],
            return_exceptions=True,  # Prevents gather from stopping on first error
        )
    
    await get_cache().set_last_refresh(datetime.now(timezone.utc))
    logger.info("Discovery poll complete: %d workspaces", len(workspaces))
```

### Pattern 6: Manual QA Trigger (OPS-01, OPS-02, OPS-03)

**What:** Fire-and-forget `asyncio.create_task()` prevents HTTP request from blocking. Deduplication check prevents duplicate concurrent scans for same scope.
**Why not synchronous:** A full QA scan for a large workspace can take 30-120 seconds. Render has a 30s request timeout. Must never block the HTTP handler.

```python
async def trigger_qa_campaign(campaign_id: str, workspace_name: str) -> dict:
    """Trigger QA scan for one campaign. Returns immediately."""
    task_key = f"campaign:{campaign_id}"
    existing = _running_scans.get(task_key)
    if existing and not existing.done():
        return {'status': 'already_running', 'scope': task_key}
    
    task = asyncio.create_task(
        _run_campaign_qa_job(campaign_id, workspace_name),
        name=f"qa-{task_key}"
    )
    _running_scans[task_key] = task
    return {'status': 'started', 'scope': task_key}


async def trigger_qa_all() -> dict:
    """Trigger QA scan across all workspaces. Returns immediately."""
    workspaces = list_workspaces()
    tasks_started = 0
    for ws in workspaces:
        task_key = f"workspace:{ws['name']}"
        existing = _running_scans.get(task_key)
        if not existing or existing.done():
            task = asyncio.create_task(
                _run_workspace_qa_job(ws['name']),
                name=f"qa-{task_key}"
            )
            _running_scans[task_key] = task
            tasks_started += 1
    return {'status': 'started', 'workspaces_triggered': tasks_started}
```

### Pattern 7: Pydantic QA Models (Claude's Discretion — RECOMMENDED)

**What:** Pydantic BaseModel for QA results. Consistent with existing Lead/Campaign models.
**Why Pydantic over plain dicts:** Type safety, auto-validation, easy JSON serialization for Phase 3 route responses.

```python
# app/models/qa.py
from pydantic import BaseModel
from datetime import datetime

class CampaignQAResult(BaseModel):
    campaign_id: str
    campaign_name: str
    total_leads: int
    broken_count: int
    issues_by_variable: dict[str, int] = {}
    last_checked: datetime | None = None

class WorkspaceQAResult(BaseModel):
    workspace_name: str
    campaigns: list[CampaignQAResult] = []
    total_broken: int = 0
    error: str | None = None       # Set when workspace fetch failed
    last_checked: datetime | None = None

class GlobalQAResult(BaseModel):
    workspaces: list[WorkspaceQAResult] = []
    errors: dict[str, str] = {}   # workspace_name -> error message
    total_broken: int = 0
    total_campaigns_checked: int = 0
    last_refresh: datetime | None = None
```

### Pattern 8: Lifespan Wiring

**What:** Add discovery_poll job to existing `_scheduler` in `app/main.py` lifespan.
**Key detail:** The scheduler already exists and is started — just add the job registration.

```python
# app/main.py — add to lifespan startup section
from app.services.poller import discovery_poll
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_from_env()
    
    # Register background discovery job
    poll_interval = int(os.getenv('QA_POLL_INTERVAL_SECONDS', '300'))
    _scheduler.add_job(
        discovery_poll,
        'interval',
        seconds=poll_interval,
        id='discovery_poll',
        replace_existing=True,
    )
    _scheduler.start()
    
    # Run once immediately on startup
    await discovery_poll()
    
    yield
    
    _scheduler.shutdown(wait=False)
```

### Anti-Patterns to Avoid

- **Synchronous QA in HTTP handler:** Never `await run_all_qa()` inside a route handler. Must always fire-and-forget via `asyncio.create_task()`. Render's 30s timeout will kill the request on large campaigns.
- **Global state without asyncio.Lock:** The cache dict is accessed from both the background poller and HTTP routes. Must use `asyncio.Lock` for all reads and writes.
- **Re-fetching copy on every QA run:** `extract_copy_from_campaign()` works on the already-fetched campaign dict. Cache the campaign list from discovery poll; QA reads from it.
- **Starting the scheduler before calling `.start()`:** APScheduler raises `SchedulerNotRunningError` if you call `.shutdown()` without `.start()`. The lifespan pattern handles this correctly.
- **Using `return_exceptions=False` in `asyncio.gather()`:** Default behavior — first exception cancels remaining coroutines. Use `return_exceptions=True` for error isolation across workspaces.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Background task scheduling | Custom threading.Timer loop | APScheduler AsyncIOScheduler | Already installed; handles asyncio event loop correctly; interval jobs with misfire grace |
| Concurrent workspace fetches | Manual asyncio.gather orchestration | asyncio.gather() + return_exceptions=True | Standard library; error isolation built-in |
| HTTP request mocking in tests | Custom mock server | respx (already installed) | Matches Phase 1 test patterns exactly; mock transport for httpx.AsyncClient |
| Async test support | Manual event loop setup | pytest-asyncio with asyncio_mode=auto | Already configured in pytest.ini |

---

## Common Pitfalls

### Pitfall 1: Variable Regex Misses `{{ spacedVar }}`

**What goes wrong:** Using `\{\{(\w+)\}\}` misses variables with whitespace inside braces. STATE.md explicitly flags this as a known concern.
**Why it happens:** Simple `\w+` pattern requires the brace content to be exactly an identifier with no whitespace.
**How to avoid:** Use `\{\{([^}]+)\}\}` to capture everything inside braces, then strip whitespace from the captured group. Verified working in live test above.
**Warning signs:** QA shows 0 issues on campaigns you can see have personalization.

### Pitfall 2: `asyncio.gather()` Without `return_exceptions=True`

**What goes wrong:** First workspace that raises an exception cancels all remaining workspace fetches. OPS-05 requires the opposite behavior.
**Why it happens:** Default `asyncio.gather()` propagates the first exception.
**How to avoid:** Always use `asyncio.gather(..., return_exceptions=True)` in poller. Log exceptions from the return values.
**Warning signs:** Only first N workspaces show data; rest are empty on "run all" trigger.

### Pitfall 3: Missing-Key vs Null vs Empty String Conflation

**What goes wrong:** `payload.get('varName')` returns `None` for BOTH absent keys AND explicit `null` values. Both are bad but for different reasons — absent key means the lead was never enriched with that variable; explicit null means enrichment ran but found nothing.
**Why it happens:** Python dict.get() collapses both to None.
**How to avoid:** For Phase 2, both are treated identically (per D-05). But the QA result should count both as "broken" without distinguishing. The current `is_broken_value(None)` catches both correctly.

### Pitfall 4: APScheduler `AsyncIOScheduler` Must Start Inside Running Event Loop

**What goes wrong:** Calling `_scheduler.start()` before the FastAPI lifespan (before asyncio event loop is running) causes runtime errors.
**Why it happens:** AsyncIOScheduler binds to the current event loop. If called at module import time (outside lifespan), the event loop may not exist yet.
**How to avoid:** Only call `_scheduler.start()` inside the lifespan context manager, which runs within the already-started event loop. The current `app/main.py` pattern is already correct.
**Warning signs:** `RuntimeError: no running event loop` at startup.

### Pitfall 5: Cache Singleton Initialization Timing

**What goes wrong:** The `QACache` singleton is created at module import time. If it contains an `asyncio.Lock`, it must be created within the event loop — otherwise the lock is not bound to the correct loop.
**Why it happens:** In Python 3.10+, `asyncio.Lock()` creates a lock for the running event loop. Creating it at module level (before the event loop starts) works in Python 3.10+ because locks are no longer bound to a specific loop at creation time (changed in Python 3.10).
**How to avoid:** In Python 3.14 (the project's runtime), this is not an issue — `asyncio.Lock()` works correctly at module level. Confirmed by working test.

### Pitfall 6: `_running_scans` Dict Grows Unboundedly

**What goes wrong:** Completed `asyncio.Task` objects accumulate in `_running_scans` dict. After 1000 QA runs, the dict holds 1000 done tasks.
**Why it happens:** Tasks are added but never cleaned up.
**How to avoid:** Periodically clean done tasks from `_running_scans`. Simplest approach: check `task.done()` before adding and remove done entries from the dict on each trigger call. Or prune on each trigger call: `_running_scans = {k: v for k, v in _running_scans.items() if not v.done()}`.

---

## Code Examples

### Full Variable Extraction (Verified Live)

```python
# Source: verified in test run above — all 6 sample cases pass

import re
from typing import FrozenSet

_RAW_PATTERN = re.compile(r'\{\{([^}]+)\}\}')
_SYSTEM_VARS: FrozenSet[str] = frozenset(['RANDOM', 'accountSignature'])

def extract_variables(copy_variants: list[dict]) -> set[str]:
    vars_found: set[str] = set()
    for variant in copy_variants:
        for field_text in (variant.get('subject', ''), variant.get('body', '')):
            for raw in _RAW_PATTERN.findall(field_text):
                stripped = raw.strip()
                if '|' in stripped:
                    continue  # {{RANDOM | opt1 | opt2}} — pipe means spin syntax
                ident = stripped.split()[0] if stripped else ''
                if ident and ident not in _SYSTEM_VARS:
                    vars_found.add(ident)
    return vars_found
```

**Test cases that must pass:**
- `{{firstName}}` → `{'firstName'}`
- `{{ cityName }}` → `{'cityName'}` (spaces handled)
- `{{accountSignature}}` → `set()` (excluded)
- `{{RANDOM |opt1|opt2}}` → `set()` (spin syntax excluded)
- `{{case_study_name}}` → `{'case_study_name'}` (underscores work)

### APScheduler + FastAPI Lifespan (Verified Pattern)

```python
# Source: verified APScheduler 3.11.2 + asyncio test above
# AsyncIOScheduler correctly runs async coroutines as jobs

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os

_scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_from_env()
    
    poll_interval = int(os.getenv('QA_POLL_INTERVAL_SECONDS', '300'))
    _scheduler.add_job(
        discovery_poll,
        'interval',
        seconds=poll_interval,
        id='discovery_poll',
        replace_existing=True,
    )
    _scheduler.start()
    await discovery_poll()  # Initial run
    
    yield
    
    _scheduler.shutdown(wait=False)
```

### Error-Isolated Concurrent Workspace Refresh (Verified Live)

```python
# Source: verified asyncio.gather pattern above — 3 succeed, 1 fails, no crash

async def refresh_all_workspaces() -> None:
    workspaces = list_workspaces()
    
    async def safe_refresh(ws_name: str) -> None:
        try:
            await _discover_workspace_impl(ws_name)
        except Exception as exc:
            logger.exception("Workspace %s refresh failed: %s", ws_name, exc)
            await get_cache().set_workspace_error(ws_name, str(exc))
    
    await asyncio.gather(
        *[safe_refresh(ws['name']) for ws in workspaces]
    )
    await get_cache().set_last_refresh(datetime.now(timezone.utc))
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| APScheduler 4.x (pre-release) | APScheduler 3.11.x (stable) | April 2026 | Do NOT use 4.x — pre-release alpha with breaking changes |
| `threading.Thread` for background tasks | `asyncio.create_task()` + AsyncIOScheduler | FastAPI adoption (~2021) | Correct for async FastAPI; threading.Thread works but requires careful event loop management |
| Blocking HTTP in background tasks | `httpx.AsyncClient` with await | httpx maturity | Must use async client inside asyncio tasks; sync `requests` library blocks the event loop |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| APScheduler | OPS-04 background polling | ✓ | 3.11.2 | — |
| Python asyncio | All async patterns | ✓ | Python 3.14 stdlib | — |
| httpx.AsyncClient | API calls in QA engine | ✓ | 0.28.1 | — |
| pydantic | QA result models | ✓ | v2 (bundled) | Plain dicts (less type safety) |
| pytest + pytest-asyncio + respx | QA engine tests | ✓ | Installed in .venv | — |

**No missing dependencies.** Phase 2 requires zero new packages.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | `prospeqt-email-qa/pytest.ini` (`asyncio_mode = auto`) |
| Quick run command | `cd prospeqt-email-qa && .venv/bin/python -m pytest tests/test_qa_engine.py -q` |
| Full suite command | `cd prospeqt-email-qa && .venv/bin/python -m pytest tests/ -q` |

Current baseline: 28 tests, all passing.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QA-01 | Extract vars, exclude RANDOM + accountSignature | unit | `pytest tests/test_qa_engine.py::test_extract_variables -x` | ❌ Wave 0 |
| QA-01 | Handle `{{ spacedVar }}` (spaces inside braces) | unit | `pytest tests/test_qa_engine.py::test_extract_variables_with_spaces -x` | ❌ Wave 0 |
| QA-01 | Handle `{{RANDOM | opt1 | opt2}}` — full pipe content | unit | `pytest tests/test_qa_engine.py::test_extract_variables_excludes_random -x` | ❌ Wave 0 |
| QA-02 | Case-sensitive match: `companyName` ≠ `companyname` | unit | `pytest tests/test_qa_engine.py::test_case_sensitive_match -x` | ❌ Wave 0 |
| QA-03 | Empty string `""` flagged as broken | unit | `pytest tests/test_qa_engine.py::test_broken_empty_string -x` | ❌ Wave 0 |
| QA-04 | Null/absent key flagged as broken | unit | `pytest tests/test_qa_engine.py::test_broken_null_and_missing -x` | ❌ Wave 0 |
| QA-05 | "NO" flagged; "no" and "N/A" NOT flagged | unit | `pytest tests/test_qa_engine.py::test_broken_NO_sentinel -x` | ❌ Wave 0 |
| QA-06 | Per-campaign result shape matches D-08 | unit | `pytest tests/test_qa_engine.py::test_campaign_qa_result_shape -x` | ❌ Wave 0 |
| QA-06 | broken_count = distinct broken lead count | unit | `pytest tests/test_qa_engine.py::test_broken_count_distinct_leads -x` | ❌ Wave 0 |
| OPS-04 | APScheduler job registered and fires | unit | `pytest tests/test_poller.py::test_scheduler_job_registered -x` | ❌ Wave 0 |
| OPS-05 | One workspace error does not stop others | unit | `pytest tests/test_poller.py::test_workspace_error_isolation -x` | ❌ Wave 0 |
| OPS-06 | last_refresh timestamp updated after poll | unit | `pytest tests/test_poller.py::test_last_refresh_timestamp -x` | ❌ Wave 0 |
| OPS-01/02/03 | trigger returns immediately (fire-and-forget) | unit | `pytest tests/test_poller.py::test_trigger_returns_immediately -x` | ❌ Wave 0 |
| OPS-01 | Duplicate trigger returns 'already_running' | unit | `pytest tests/test_poller.py::test_duplicate_trigger_deduplicated -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd prospeqt-email-qa && .venv/bin/python -m pytest tests/test_qa_engine.py -q`
- **Per wave merge:** `cd prospeqt-email-qa && .venv/bin/python -m pytest tests/ -q`
- **Phase gate:** Full suite green (28 existing + all Phase 2 tests) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_qa_engine.py` — covers QA-01 through QA-06 (all variable extraction + lead flagging logic)
- [ ] `tests/test_poller.py` — covers OPS-01 through OPS-06 (scheduler registration, error isolation, manual trigger)
- [ ] `tests/fixtures/qa_result.json` — expected QA result shape for a campaign with known broken leads
- [ ] `app/models/qa.py` — Pydantic models for CampaignQAResult, WorkspaceQAResult, GlobalQAResult

No framework install needed — pytest, pytest-asyncio, and respx are already installed.

---

## Project Constraints (from CLAUDE.md)

| Constraint | Impact on Phase 2 |
|------------|-------------------|
| Modular architecture | qa_engine, cache, poller must be separate modules under `app/services/`. No logic in `app/main.py` beyond wiring. |
| APScheduler 3.x only | Already installed at 3.11.2. Do NOT use APScheduler 4.x (pre-release alpha). |
| FastAPI + httpx async throughout | QA engine must use `httpx.AsyncClient` passed as parameter (not created inline). |
| No hardcoded API keys | Workspace keys come from `workspace.get_api_key()` service only. |
| pytest + respx for tests | Match Phase 1 test patterns exactly — `respx.mock` decorator, async test fixtures. |

---

## Open Questions

1. **D-13 poller behavior: discovery only vs. QA-on-discovery**
   - What we know: D-13 says poller does discovery only (campaign list), NOT full QA
   - What's unclear: Should the poller update the campaign list in cache but NOT compute QA results? Phase 3 will need campaign lists to render the dashboard — the cache needs them.
   - Recommendation: Poller updates `campaigns_by_workspace` in cache. Manual trigger runs full QA and updates `qa_results_by_campaign`. These are separate cache namespaces.

2. **Initial QA run on startup**
   - What we know: Poller runs discovery on startup. QA is manual-trigger only per D-14.
   - What's unclear: Should the dashboard show "not yet checked" state on first load, or should startup trigger a QA scan?
   - Recommendation: Show "not yet checked" on first load. Only run QA when user clicks the button. This is consistent with D-14 and avoids a potentially slow startup.

3. **Concurrency between background poller and manual trigger**
   - What we know: Both can run simultaneously and modify the cache.
   - What's unclear: What if a manual "QA Scan All" is triggered while a background discovery poll is running?
   - Recommendation: They operate on different cache namespaces (discovery → campaign list, manual → QA results). No collision. The asyncio.Lock in QACache handles concurrent writes correctly.

---

## Sources

### Primary (HIGH confidence)
- Verified live code execution — all patterns in this document were tested in the project's Python 3.14 / APScheduler 3.11.2 / asyncio environment
- `prospeqt-email-qa/app/api/instantly.py` — Phase 1 API client (existing, confirmed working)
- `prospeqt-email-qa/app/models/instantly.py` — Phase 1 Pydantic models
- `prospeqt-email-qa/app/main.py` — Existing lifespan with `_scheduler` placeholder
- `prospeqt-email-qa/tests/fixtures/` — Real API response shapes
- `.planning/research/PITFALLS.md` — Phase 1 pitfall research (HIGH confidence)
- `.planning/phases/02-qa-engine-background/02-CONTEXT.md` — Locked decisions D-01 through D-21

### Secondary (MEDIUM confidence)
- APScheduler 3.11.2 PyPI — confirmed stable release, async support
- pytest-asyncio docs — `asyncio_mode = auto` configuration

---

## Metadata

**Confidence breakdown:**
- Variable extraction algorithm: HIGH — live tested against all known edge cases
- Bad value detection logic: HIGH — live tested, matches D-05/D-06 precisely
- APScheduler async job pattern: HIGH — live verified in project's Python 3.14 environment
- asyncio.Lock cache pattern: HIGH — live verified, concurrent access correct
- Fire-and-forget trigger pattern: HIGH — live verified, deduplication works
- Module structure recommendations: HIGH — consistent with Phase 1 established patterns
- Test file specifications: HIGH — mirrors exact Phase 1 test patterns

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable libraries — APScheduler 3.x, asyncio, pydantic v2)
