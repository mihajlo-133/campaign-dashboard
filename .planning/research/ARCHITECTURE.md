# Architecture Research

**Domain:** Multi-workspace email campaign QA dashboard (Python web app)
**Researched:** 2026-04-04
**Confidence:** HIGH — Based on Instantly v2 API docs, existing Prospeqt dashboard codebase, and established Flask/modular Python patterns.

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          PRESENTATION LAYER                              │
│  ┌────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐ │
│  │ dashboard.html │  │   admin.html     │  │     login.html           │ │
│  │ (QA results)   │  │ (workspace mgmt) │  │   (admin gate)           │ │
│  └───────┬────────┘  └────────┬─────────┘  └──────────────────────────┘ │
├──────────┼─────────────────────┼────────────────────────────────────────┤
│                          ROUTE LAYER                                     │
│  ┌────────────────────┐   ┌────────────────────┐                        │
│  │  routes/qa.py      │   │  routes/admin.py   │                        │
│  │  GET /             │   │  GET  /admin       │                        │
│  │  GET /ws/<slug>    │   │  POST /admin/ws    │                        │
│  │  GET /ws/<slug>/   │   │  DELETE /admin/ws  │                        │
│  │      campaign/<id> │   │  POST /admin/check │                        │
│  │  POST /api/check   │   │  POST /login       │                        │
│  └──────────┬─────────┘   └────────┬───────────┘                        │
├─────────────┼──────────────────────┼────────────────────────────────────┤
│                          SERVICE LAYER                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │ qa_engine.py │  │  poller.py   │  │workspace_svc │  │  auth.py    │  │
│  │ (core logic) │  │ (background) │  │  .py         │  │ (sessions)  │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────────────┘  │
├─────────┼─────────────────┼─────────────────┼──────────────────────────┤
│                          DATA LAYER                                      │
│  ┌──────────────────┐  ┌──────────────┐  ┌─────────────────────────┐    │
│  │ instantly_client │  │  cache.py    │  │  workspace_store.py     │    │
│  │      .py         │  │ (in-memory)  │  │  (JSON file on disk)    │    │
│  └──────────────────┘  └──────────────┘  └─────────────────────────┘    │
├──────────────────────────────────────────────────────────────────────────┤
│                          EXTERNAL                                        │
│  ┌───────────────────────────────────────────┐                           │
│  │         Instantly v2 REST API             │                           │
│  │  api.instantly.ai/api/v2 (Bearer token)  │                           │
│  └───────────────────────────────────────────┘                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `routes/qa.py` | Serve QA views (all/workspace/campaign) and trigger manual checks | Flask Blueprint, renders Jinja2 templates |
| `routes/admin.py` | Workspace CRUD, manual poll trigger, admin login | Flask Blueprint, password check middleware |
| `services/qa_engine.py` | Parse `{{variable}}` patterns from copy, cross-reference against lead data, build issue report | Pure Python — no I/O, fully testable |
| `services/poller.py` | Background thread polling Instantly API on schedule | `threading.Thread` + `time.sleep` loop (or APScheduler) |
| `services/workspace_svc.py` | Business logic for workspace add/remove/list | Thin orchestrator between routes and storage |
| `services/auth.py` | Admin session management, password check | Flask session + `hmac.compare_digest` |
| `api/instantly_client.py` | All Instantly v2 API calls — campaigns, leads, sequences | `urllib.request` (stdlib) or `requests` (acceptable dep) |
| `cache.py` | In-memory TTL cache for QA results per workspace | Thread-safe dict with timestamp |
| `workspace_store.py` | Persist workspace configs (name, API key) to JSON file | Read/write `workspaces.json` with file lock |
| `templates/` | Jinja2 HTML templates | dashboard.html, admin.html, login.html |

---

## Recommended Project Structure

```
email-qa-dashboard/
├── app.py                    # Flask app factory, register blueprints, start poller
├── config.py                 # Config class — reads env vars, sets defaults
├── Procfile                  # web: gunicorn app:create_app()
├── requirements.txt          # flask, gunicorn (+ pytest, playwright for dev)
├── workspaces.json           # Persisted workspace registry (gitignored if keys present)
│
├── routes/
│   ├── __init__.py
│   ├── qa.py                 # Blueprint: dashboard views + manual check trigger
│   └── admin.py              # Blueprint: workspace management + login
│
├── services/
│   ├── __init__.py
│   ├── qa_engine.py          # Variable extraction, lead cross-reference, issue report
│   ├── poller.py             # Background poll loop
│   ├── workspace_svc.py      # Add/remove/list workspaces
│   └── auth.py               # Admin session helpers
│
├── api/
│   ├── __init__.py
│   └── instantly_client.py   # All Instantly v2 HTTP calls (campaigns, leads, steps)
│
├── cache.py                  # In-memory TTL cache (thread-safe)
├── workspace_store.py        # JSON persistence for workspace registry
│
├── templates/
│   ├── base.html             # Shared layout, nav, CSS variables
│   ├── dashboard.html        # All-workspace QA overview
│   ├── workspace.html        # Per-workspace drill-down
│   ├── campaign.html         # Per-campaign lead-level issues
│   ├── admin.html            # Workspace management panel
│   └── login.html            # Admin login page
│
├── static/
│   └── app.css               # Mobile-first CSS (no framework)
│
└── tests/
    ├── fixtures/             # Mock Instantly API response JSON files
    ├── test_qa_engine.py     # Unit tests for variable parsing + matching
    ├── test_instantly_client.py  # API client tests (monkeypatched HTTP)
    ├── test_routes.py        # Route tests with Flask test client
    └── test_cache.py         # Cache TTL + thread safety tests
```

### Structure Rationale

- **`routes/`:** One Blueprint per user-facing concern (viewing vs. managing). Routes own request parsing and template rendering only — no business logic.
- **`services/`:** Business logic lives here, isolated from HTTP. `qa_engine.py` can be tested with pure Python inputs, no Flask, no HTTP.
- **`api/`:** All Instantly v2 HTTP calls in one module. When Instantly changes an endpoint, one file changes. When EmailBison support is added in v2, it gets its own module here.
- **`cache.py` + `workspace_store.py`:** Two distinct persistence concerns separated. Cache is volatile and in-memory. Workspace registry is durable and on-disk.
- **`workspaces.json`:** Admin panel writes API keys here. On Render, this should be a mounted disk or env-var bootstrap. Keys never in code.

---

## Architectural Patterns

### Pattern 1: Flask Application Factory

**What:** `create_app()` function returns a configured Flask app instead of a module-level `app = Flask(...)`.
**When to use:** Always for non-trivial Flask apps. Required for testing (create a fresh app per test).
**Trade-offs:** Adds one level of indirection. Worth it for testability and config isolation.

**Example:**
```python
# app.py
def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(config or "config.ProductionConfig")

    from routes.qa import qa_bp
    from routes.admin import admin_bp
    app.register_blueprint(qa_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    from services.poller import start_poller
    start_poller(app)

    return app
```

### Pattern 2: Service Layer Separating Logic from Routes

**What:** Routes call service functions. Services contain all business logic. Routes contain zero logic.
**When to use:** Whenever the same logic could be triggered from multiple places (HTTP route AND background poller).
**Trade-offs:** More files; worth it because `qa_engine.run_check(workspace_id)` can be called from both a manual POST and the background loop without duplication.

**Example:**
```python
# routes/qa.py
@qa_bp.post("/api/check/<workspace_id>")
def trigger_check(workspace_id):
    result = qa_engine.run_check(workspace_id)  # service call
    cache.set(workspace_id, result)
    return jsonify(result)

# services/poller.py
def _poll_loop():
    while True:
        for ws in workspace_store.list_all():
            result = qa_engine.run_check(ws["id"])  # same service call
            cache.set(ws["id"], result)
        time.sleep(POLL_INTERVAL)
```

### Pattern 3: Thread-Safe In-Memory Cache with TTL

**What:** A dict protected by a `threading.Lock`, where each entry carries a timestamp. Entries are considered stale after TTL seconds. A background thread keeps the cache warm; reads never block on API calls.
**When to use:** When you need sub-second reads for a UI while data freshness of 5-15 minutes is acceptable.
**Trade-offs:** Cache is lost on process restart (Render restart resets it). First read after restart triggers a synchronous fetch. Acceptable for this use case.

**Example:**
```python
# cache.py
import threading, time

_lock = threading.Lock()
_store: dict = {}
TTL = 600  # 10 minutes

def get(key):
    with _lock:
        entry = _store.get(key)
        if entry and (time.time() - entry["ts"]) < TTL:
            return entry["data"]
    return None

def set(key, data):
    with _lock:
        _store[key] = {"data": data, "ts": time.time()}
```

### Pattern 4: Pure Function QA Engine

**What:** `qa_engine.py` exports a single function `run_check(campaigns, leads_by_campaign)` that takes data structures as input and returns an issue report. No HTTP, no file I/O inside.
**When to use:** Whenever the core logic needs to be unit-testable without mocking infrastructure.
**Trade-offs:** The caller (route or poller) must fetch the data first, then pass it in. Slightly more code in the orchestration layer.

**Example:**
```python
# services/qa_engine.py
import re

VAR_PATTERN = re.compile(r'\{\{(\w+)\}')

def extract_variables(copy_text: str) -> set[str]:
    """Return all {{variable}} names found in campaign copy."""
    return set(VAR_PATTERN.findall(copy_text))

def check_leads(leads: list[dict], required_vars: set[str]) -> list[dict]:
    """Return leads with issues: missing/null/NO variables."""
    issues = []
    for lead in leads:
        custom = lead.get("custom_variables") or {}
        broken = [
            v for v in required_vars
            if not custom.get(v) or custom[v] in ("", "NO", None)
        ]
        if broken:
            issues.append({"email": lead["email"], "broken_vars": broken})
    return issues
```

---

## Data Flow

### QA Check Flow (Manual Trigger)

```
User clicks "Run Check" on dashboard
    ↓
POST /api/check/<workspace_id>          (routes/qa.py)
    ↓
workspace_store.get(workspace_id)       → API key, name
    ↓
instantly_client.list_campaigns(key)    → campaigns list (active + drafted)
    ↓ (for each campaign)
instantly_client.get_sequence_steps(key, campaign_id)  → copy text
    ↓
qa_engine.extract_variables(copy_text)  → set of {{var}} names
    ↓
instantly_client.list_leads(key, campaign_id, active_only=True) → lead list
    ↓
qa_engine.check_leads(leads, required_vars)  → issues list
    ↓
cache.set(workspace_id, result)         → stored for dashboard read
    ↓
HTTP 200 + JSON summary                 (routes/qa.py returns)
    ↓
Dashboard JS refreshes view
```

### Background Poll Flow

```
poller thread wakes (every N minutes)
    ↓
workspace_store.list_all()              → all registered workspaces
    ↓ (for each workspace, rate-limited)
[same fetch + QA steps as above]
    ↓
cache.set(workspace_id, result)
    ↓
thread sleeps until next interval
```

### Admin Workspace Registration

```
Admin POST /admin/ws  { name, api_key }
    ↓
auth.require_admin()                    → 403 if no valid session
    ↓
instantly_client.validate_key(api_key)  → test call to /api/v2/campaigns
    ↓ success
workspace_store.add(name, api_key)      → write to workspaces.json
    ↓
Redirect to /admin
```

### Key Data Flows

1. **Variable extraction:** Copy text (string) → regex scan → set of variable names. Runs in-process, no I/O.
2. **Lead variable check:** Lead list (from Instantly API) + required variable set → per-lead issue list. Pure function, no I/O.
3. **Cache reads:** All dashboard renders read from in-memory cache. API is never called in the request path after initial warmup.
4. **Workspace registry:** Admin panel reads/writes `workspaces.json`. Background poller reads it at each poll cycle to discover new workspaces.

---

## Build Order

Dependencies flow from bottom to top. Build in this order:

| Step | Module | Depends On | Why First |
|------|--------|------------|-----------|
| 1 | `workspace_store.py` | Nothing | Everything else needs to read workspace configs |
| 2 | `api/instantly_client.py` | `workspace_store.py` | Core data source — test against real API early |
| 3 | `services/qa_engine.py` | Nothing (pure functions) | Can be built and fully tested before any HTTP |
| 4 | `cache.py` | Nothing | Simple, tested in isolation |
| 5 | `services/auth.py` | Flask session | Needed before admin routes |
| 6 | `routes/qa.py` | All of the above | Wires display layer to cache + QA engine |
| 7 | `routes/admin.py` | `auth.py`, `workspace_store.py` | Admin CRUD + login |
| 8 | `templates/` | Routes | HTML rendered by routes |
| 9 | `services/poller.py` | `instantly_client.py`, `qa_engine.py`, `cache.py` | Background loop — integrate after core flow works |
| 10 | `app.py` | All blueprints, poller | Final wiring |

**Critical path:** `workspace_store → instantly_client → qa_engine → routes → templates → poller`

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 6 workspaces (current) | In-memory cache, threading.Thread poller, workspaces.json — all fine |
| 20-50 workspaces | Add ThreadPoolExecutor in poller for parallel workspace fetches. Rate-limit per API key. In-memory cache still fine. |
| 50+ workspaces | Consider Redis for cache (shared across Render instances). SQLite for workspace registry. APScheduler with job queue. |

### Scaling Priorities

1. **First bottleneck:** Instantly API rate limits when polling many campaigns per workspace. Fix: add per-workspace request throttling (token bucket or simple sleep) inside `instantly_client.py`.
2. **Second bottleneck:** Memory pressure from caching large lead lists. Fix: cache only the QA result summary (issue counts per variable), not the raw lead data.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Instantly v2 API | `urllib.request` HTTP calls, Bearer token auth | Rate limits exist — backoff required. Pagination via `starting_after` cursor. Leads endpoint is POST, not GET. |
| Render (deployment) | `Procfile` + `gunicorn app:create_app()` | `workspaces.json` needs a Render persistent disk or env-var bootstrap for API keys to survive deploys. |
| File system | Read/write `workspaces.json` | On Render free tier there is no persistent disk — use env var `WORKSPACES_JSON` to bootstrap from environment, then cache in memory. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `routes` ↔ `services` | Direct function calls | Routes import service functions. Services never import from routes. |
| `services/poller` ↔ `services/qa_engine` | Direct function calls | Poller calls `qa_engine.run_check()` — same as routes do. No duplication. |
| `services` ↔ `api/` | Direct function calls | Services call `instantly_client.*`. Client is a dumb HTTP wrapper with no business logic. |
| `cache` ↔ `routes` | Direct function calls | Routes read from cache on every GET. Never directly from Instantly API. |
| `workspace_store` ↔ `poller` | Direct function calls | Poller calls `workspace_store.list_all()` at start of each poll cycle. Picks up newly added workspaces automatically. |

---

## Anti-Patterns

### Anti-Pattern 1: Business Logic in Routes

**What people do:** Put variable parsing and lead-matching logic directly inside the route handler function.
**Why it's wrong:** Background poller cannot reuse route code. Logic cannot be unit-tested without an HTTP client. Flask test client required for every QA logic test.
**Do this instead:** All QA logic lives in `services/qa_engine.py`. Routes call `qa_engine.run_check(...)` and return the result.

### Anti-Pattern 2: Calling Instantly API in Every Dashboard Request

**What people do:** Fetch campaigns and leads from Instantly on every HTTP GET to the dashboard.
**Why it's wrong:** Dashboard becomes slow (seconds per page load), hammers Instantly rate limits, fails when Instantly is down.
**Do this instead:** Background poller populates the cache. Dashboard reads from cache synchronously. Cache miss triggers an async refresh, returns stale or loading state.

### Anti-Pattern 3: Storing API Keys in Code or Config Files Committed to Git

**What people do:** Add `ENAVRA_KEY = "abc123"` in `config.py` or `workspaces.json` in a public repo.
**Why it's wrong:** Keys leaked in git history, accessible to anyone with repo access.
**Do this instead:** Admin panel writes keys to `workspaces.json` on the server's filesystem (or Render env var). `workspaces.json` is `.gitignore`d. Existing keys in `tools/accounts/*/instantly.md` are NOT read at deploy time — admin panel is the runtime source of truth.

### Anti-Pattern 4: Single Monolith Module

**What people do:** Copy the existing `server.py` monolith pattern from the Prospeqt outreach dashboard.
**Why it's wrong (for this project):** The outreach dashboard is intentionally stdlib-only for zero-dependency single-file deployment. This project accepts Flask as a dependency and has more distinct subsystems (QA engine, admin, background poller). A monolith makes QA engine testing, route isolation, and future platform additions harder.
**Do this instead:** Use the modular structure above. The stdlib constraint does NOT apply to this project.

### Anti-Pattern 5: Fetching All Leads Into Memory for Large Campaigns

**What people do:** Paginate through all leads for a large campaign, hold the full list in memory, then run QA.
**Why it's wrong:** A campaign with 50,000 leads would consume significant memory and take minutes to fetch.
**Do this instead:** Stream-process leads in pages. As each page arrives from Instantly, run `qa_engine.check_leads(page, required_vars)`, accumulate only the issues (not the full lead list), discard the raw page. Cache the issue summary, not the raw data.

---

## Sources

- Instantly v2 API documentation: [developer.instantly.ai](https://developer.instantly.ai)
- Instantly v2 campaign and lead endpoints: [developer.instantly.ai/api/v2/campaign](https://developer.instantly.ai/api/v2/campaign), [developer.instantly.ai/api/v2/lead/listleads](https://developer.instantly.ai/api/v2/lead/listleads)
- Flask Blueprints modular architecture: [flask.palletsprojects.com/en/stable/blueprints/](https://flask.palletsprojects.com/en/stable/blueprints/)
- Flask application factory + service layer: [DigitalOcean Flask Blueprints guide](https://www.digitalocean.com/community/tutorials/how-to-structure-a-large-flask-application-with-flask-blueprints-and-flask-sqlalchemy), [Architecture Patterns with Python — O'Reilly](https://www.oreilly.com/library/view/architecture-patterns-with/9781492052197/ch04.html)
- APScheduler for background tasks: [apscheduler.readthedocs.io](https://apscheduler.readthedocs.io/en/3.x/userguide.html)
- Existing Prospeqt outreach dashboard for pattern reference: `gtm/prospeqt-outreach-dashboard/server.py`

---
*Architecture research for: Email QA Dashboard — modular Python web dashboard*
*Researched: 2026-04-04*
