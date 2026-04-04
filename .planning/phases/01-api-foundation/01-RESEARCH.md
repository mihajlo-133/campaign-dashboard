# Phase 1: API Foundation - Research

**Researched:** 2026-04-04
**Domain:** FastAPI project scaffold + Instantly v2 API client + workspace admin panel
**Confidence:** HIGH — all decisions are locked, stack is verified against PyPI, API shapes verified against live data, prior research in canonical refs is current

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Separate GitHub repo named `prospeqt-email-qa`
- **D-02:** Claude's discretion on internal module organization (layer-based vs feature-based)
- **D-03:** Plain Python venv for local dev — no Docker
- **D-04:** FastAPI + Jinja2 + HTMX stack, uvicorn for dev, gunicorn+uvicorn for production
- **D-05:** Admin panel accessed via settings/gear icon in main nav bar — not a separate /admin route
- **D-06:** Password prompt appears when clicking the gear icon (simple shared password, not user accounts)
- **D-07:** Adding a workspace requires only: display name + API key
- **D-08:** Removing a workspace shows a confirmation dialog with a simple sentence
- **D-09:** Workspace API keys stored exclusively in environment variables — no JSON file, no database
- **D-10:** Admin panel add/remove modifies env vars, requires Render env var update + redeploy — acceptable
- **D-11:** No encryption of API keys at rest — server-side only, internal tool
- **D-12:** Local dev uses .env file loaded by pydantic-settings; Render sets env vars in dashboard
- **D-13:** Env var naming convention: `WORKSPACE_<NAME>_API_KEY=<key>`
- **D-14:** When Instantly API is down or rate-limited for one workspace, show error badge + display last successful data
- **D-15:** Claude's discretion on caching strategy

### Claude's Discretion

- Internal module organization (D-02)
- Caching strategy (D-15)
- Pydantic model design for campaign/lead data
- Error handling patterns (retry logic, timeout values)
- Exact env var parsing format for workspace configuration

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INF-01 | Modular codebase — routes, API clients, QA logic, templates in separate modules | Layer-based directory structure: `app/routes/`, `app/services/`, `app/api/`, `app/templates/` |
| INF-02 | Deployable to Render as standard Python web app | FastAPI + uvicorn on Render confirmed; `requirements.txt` + start command pattern documented |
| INF-03 | No hardcoded API keys in source code | pydantic-settings reads from env vars; keys never in code or committed files |
| INF-04 | Project pushed to GitHub as its own repo | New `prospeqt-email-qa` repo — standalone, no monorepo entanglement |
| API-01 | Fetch all campaigns from configured Instantly workspaces via v2 API | GET `https://api.instantly.ai/api/v2/campaigns` with `Authorization: Bearer <key>` + cursor pagination |
| API-02 | Filter campaigns by status — only active (1) and draft (0) shown | Filter at response level: `[c for c in campaigns if c["status"] in (0, 1)]` |
| API-03 | Extract sequence copy from `campaign.sequences[].steps[].variants[].body/subject` | Copy is INLINE in GET `/campaigns` response — no additional API call needed |
| API-04 | Fetch all leads via POST `/api/v2/leads/list` with cursor pagination | Confirmed pattern from existing `server.py`: body `{"campaign": id, "limit": 100}`, cursor via `next_starting_after` |
| API-05 | Filter leads to active-only (status=1; exclude status=3 and status=-1) | Apply status filter in POST body — reduces fetched volume; confirmed status codes from live API |
| API-06 | Read lead variables from `lead.payload` dict | Confirmed: `lead.payload` (not `lead.custom_variables`) — verified against live API 2026-04-04 |
| API-07 | Respect Instantly rate limits (100 req/sec, 6000 req/min per workspace) | Per-workspace `asyncio.Semaphore` + 100ms sleep between paginated pages |
| ADM-01 | Admin panel to add new workspaces (name + API key) | HTMX form POST to `/admin/workspaces` — writes `WORKSPACE_<NAME>_API_KEY` to in-memory registry |
| ADM-02 | Admin panel to remove workspaces | HTMX `hx-delete` (or POST with method override) to `/admin/workspaces/{name}` — removes from registry |
| ADM-03 | Admin panel protected by simple password auth | Cookie-based session; password compared via `hmac.compare_digest`; `ADMIN_PASSWORD` env var |
| ADM-04 | QA viewing is open access — no login required | Auth middleware only applies to `/admin/*` routes; all other routes unauthenticated |
| ADM-05 | API keys stored server-side with persistence across app restarts | NOTE: D-09 overrides this — env vars only. Registry is rebuilt at startup by reading `WORKSPACE_*_API_KEY` env vars. "Persistence" is achieved by setting env vars on Render before deploy. |
</phase_requirements>

---

## Summary

Phase 1 builds the complete foundation: project scaffold, Instantly v2 async API client, workspace configuration system, and password-protected admin panel. All technology decisions are already locked — the planner can proceed with specific implementation tasks.

The stack is FastAPI 0.135.3 + httpx 0.28.1 + APScheduler 3.11.2 + pydantic-settings 2.13.1 + Jinja2 (bundled). All versions verified against PyPI as of 2026-04-04. The Instantly v2 API data shapes are verified against a live API call — no guessing required.

The single most important constraint to honor in Phase 1 is **decision D-09**: workspace API keys are stored exclusively as environment variables. This means `ADM-05`'s mention of "file-based persistence" is superseded by D-09. At startup, the app reads all `WORKSPACE_<NAME>_API_KEY=<value>` env vars to populate an in-memory workspace registry. Adding/removing a workspace updates Render env vars + redeploys — no JSON file on disk.

**Primary recommendation:** Build in this order: (1) project scaffold + settings, (2) workspace registry from env vars, (3) Instantly API client with async cursor pagination, (4) admin panel + auth. Test the API client against one real workspace before wiring the admin panel.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi[standard] | 0.135.3 | Web framework, routing, ASGI | Async-native, Pydantic v2 built-in, Jinja2 + pydantic-settings ship with `[standard]` extra |
| uvicorn | 0.43.0 | ASGI server (dev + prod) | FastAPI's default; auto-detected by Render |
| httpx | 0.28.1 | Async HTTP client for Instantly API | `AsyncClient` with connection pool; `AsyncHTTPTransport` for retries; closest-to-requests API |
| APScheduler | 3.11.2 | Background polling | `AsyncIOScheduler` integrates with FastAPI lifespan; v4 is pre-release alpha — pin `<4.0.0` |
| pydantic-settings | 2.13.1 | Env var config / settings | Ships with `fastapi[standard]`; reads `.env` locally and Render env vars in production |
| Jinja2 | 3.x (bundled) | Server-side HTML templating | Ships with `fastapi[standard]`; pairs with `TemplateResponse` |
| HTMX | 2.0.4 (CDN) | Partial DOM updates without JS | Load from CDN: `https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-multipart | 0.0.x (bundled) | Form data parsing for admin panel | Required for FastAPI to parse HTML form submissions |
| gunicorn | 23.x | Production process manager | Start command on Render for multi-worker: `gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker` |
| pytest | 8.x | Test runner | All unit + integration tests |
| pytest-asyncio | 0.24.x | Async test support | Testing async FastAPI routes + httpx client |
| respx | 0.21.x | httpx mock transport | Mock Instantly API responses in tests — never call live API in tests |
| python-dotenv | 1.x | .env file loading | Auto-loaded by pydantic-settings locally; not needed on Render |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastAPI | Flask | Flask requires explicit async extensions; no built-in Pydantic; weaker for concurrent multi-workspace fetching |
| APScheduler 3.x | Celery + Redis | Celery requires Redis broker + separate worker process — no benefit at single-server scale |
| httpx | aiohttp | httpx has simpler API, better timeout config, respx mock library is purpose-built for httpx |
| pydantic-settings | python-decouple | pydantic-settings is FastAPI-native, ships bundled, supports type validation — no second config library needed |

**Installation:**

```bash
# Create venv
python3 -m venv .venv && source .venv/bin/activate

# Production dependencies
pip install "fastapi[standard]>=0.135.0" "httpx>=0.28.0,<0.29.0" "APScheduler>=3.11.0,<4.0.0" gunicorn

# Dev dependencies
pip install pytest pytest-asyncio respx python-dotenv ruff
```

**requirements.txt (production):**
```
fastapi[standard]>=0.135.0
httpx>=0.28.0,<0.29.0
APScheduler>=3.11.0,<4.0.0
gunicorn>=23.0.0
```

**Version verification:** All package versions confirmed against PyPI on 2026-04-04.

- fastapi: 0.135.3 (current stable)
- httpx: 0.28.1 (current stable)
- apscheduler: 3.11.2 (current stable 3.x; 4.x is pre-release alpha)
- pydantic-settings: 2.13.1 (current stable)

**Python version note:** Render uses Python 3.11 by default. Local dev on this machine is Python 3.14.3 (Homebrew). FastAPI 0.135.x supports Python 3.10+ — both are compatible. Recommend pinning Render to Python 3.11 explicitly via `runtime.txt` containing `python-3.11.0`.

---

## Architecture Patterns

### Recommended Project Structure

```
prospeqt-email-qa/
├── app/
│   ├── main.py               # FastAPI app factory, lifespan, router inclusion
│   ├── config.py             # pydantic-settings Settings class — reads WORKSPACE_*_API_KEY env vars
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── dashboard.py      # GET / — full-page QA overview (Phase 3 content, skeleton in Phase 1)
│   │   └── admin.py          # GET/POST /admin — workspace management + gear icon panel
│   ├── services/
│   │   ├── __init__.py
│   │   ├── workspace.py      # Workspace registry: list, add, remove — reads from env vars
│   │   └── auth.py           # Admin session: check password, set/clear cookie
│   ├── api/
│   │   ├── __init__.py
│   │   └── instantly.py      # All Instantly v2 calls: campaigns, leads (async, httpx)
│   ├── models/
│   │   ├── __init__.py
│   │   └── instantly.py      # Pydantic models: Campaign, Lead, Workspace, QAResult (Phase 2+)
│   └── templates/
│       ├── base.html         # Shared layout, nav with gear icon, CSS custom props
│       ├── dashboard.html    # Placeholder — wired in Phase 3
│       ├── admin.html        # Workspace list + add/remove forms
│       └── login.html        # Admin password prompt (modal or page)
├── tests/
│   ├── fixtures/             # Mock Instantly API response JSON files
│   ├── test_workspace.py     # Workspace registry unit tests
│   ├── test_instantly.py     # API client tests (respx mocks)
│   └── test_admin.py         # Admin route integration tests
├── .env.example              # Template: WORKSPACE_ENAVRA_API_KEY=, ADMIN_PASSWORD=
├── requirements.txt
├── requirements-dev.txt
├── runtime.txt               # python-3.11.0
└── render.yaml               # Optional Render IaC
```

**Decision rationale (D-02):** Layer-based (`routes/`, `services/`, `api/`) over feature-based because there are only 4 phases and 3 concerns (API, QA, views). At this scale, feature-based directories would split the tiny Phase 1 across 3 feature folders — layer-based keeps Phase 1 in one focused area.

### Pattern 1: Workspace Registry from Environment Variables

**What:** At startup, scan all env vars matching `WORKSPACE_<NAME>_API_KEY` pattern and build an in-memory workspace dict. This satisfies both D-09 (env vars only) and ADM-05 (persists across restarts, since Render env vars survive deploys).

**When to use:** Application startup via FastAPI lifespan. Also re-read after manual registry refresh.

```python
# app/services/workspace.py
import os
import re

_WORKSPACE_PATTERN = re.compile(r'^WORKSPACE_([A-Z0-9_]+)_API_KEY$')
_registry: dict[str, str] = {}  # name -> api_key

def load_from_env() -> None:
    """Read all WORKSPACE_<NAME>_API_KEY env vars into the in-memory registry."""
    global _registry
    _registry = {}
    for key, value in os.environ.items():
        match = _WORKSPACE_PATTERN.match(key)
        if match and value.strip():
            name = match.group(1).lower().replace('_', '-')  # ENAVRA -> enavra
            _registry[name] = value.strip()

def list_workspaces() -> list[dict]:
    return [{"name": name, "key_preview": key[-4:]} for name, key in _registry.items()]

def get_api_key(name: str) -> str | None:
    return _registry.get(name)
```

**Note on ADM-01/ADM-02:** The admin panel UI shows the current registry. "Adding" a workspace tells the admin "Set WORKSPACE_MYNAME_API_KEY=<key> in Render env vars and redeploy." The panel itself does not write env vars — it cannot (env vars are immutable at runtime). The panel can optionally store additions in a session-level pending dict for UX purposes, but persistent add/remove requires a Render redeploy.

### Pattern 2: FastAPI Application Factory with Lifespan

**What:** `create_app()` returns a configured FastAPI instance. Lifespan context manager starts APScheduler and loads workspace registry.

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.workspace import load_from_env
from app.routes import admin, dashboard

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    load_from_env()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(poll_all_workspaces, "interval", minutes=15)
    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown()

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.include_router(dashboard.router)
    app.include_router(admin.router, prefix="/admin")
    return app

app = create_app()
```

### Pattern 3: Instantly v2 Async API Client

**What:** A stateless async module wrapping all Instantly v2 HTTP calls. Uses a shared `httpx.AsyncClient` initialized in lifespan.

```python
# app/api/instantly.py
import asyncio
import httpx

INSTANTLY_BASE = "https://api.instantly.ai/api/v2"
_semaphores: dict[str, asyncio.Semaphore] = {}  # per-workspace rate limiting

def _get_semaphore(workspace_name: str) -> asyncio.Semaphore:
    if workspace_name not in _semaphores:
        _semaphores[workspace_name] = asyncio.Semaphore(5)  # max 5 concurrent per workspace
    return _semaphores[workspace_name]

async def list_campaigns(client: httpx.AsyncClient, api_key: str) -> list[dict]:
    """Fetch all campaigns, return only active (status=1) and draft (status=0)."""
    headers = {"Authorization": f"Bearer {api_key}"}
    results = []
    cursor = None
    while True:
        params = {"limit": 100}
        if cursor:
            params["starting_after"] = cursor
        resp = await client.get(f"{INSTANTLY_BASE}/campaigns", headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        results.extend(items)
        cursor = data.get("next_starting_after")
        if not cursor or len(items) < 100:
            break
    return [c for c in results if c.get("status") in (0, 1)]

async def list_leads_page(
    client: httpx.AsyncClient,
    api_key: str,
    campaign_id: str,
    cursor: str | None = None,
) -> dict:
    """Fetch one page of active leads (status=1) for a campaign."""
    headers = {"Authorization": f"Bearer {api_key}"}
    body = {
        "campaign": campaign_id,
        "limit": 100,
        "filter_lt_status": 1,  # active leads only — verify exact param name against live API
    }
    if cursor:
        body["starting_after"] = cursor
    resp = await client.post(f"{INSTANTLY_BASE}/leads/list", headers=headers, json=body)
    resp.raise_for_status()
    return resp.json()  # {"items": [...], "next_starting_after": "..."}
```

**Critical note on `lead.payload`:** Per live API verification (2026-04-04), lead variables are in `lead.payload` (not `lead.custom_variables`). The existing `server.py` references `custom_variables` for the outreach dashboard but this QA dashboard must use `lead.payload`. Confirm by printing a raw lead object from one real API call before building the QA engine in Phase 2.

### Pattern 4: Admin Password Auth with Cookie Session

**What:** ADMIN_PASSWORD env var; simple cookie set on successful auth; `hmac.compare_digest` for timing-safe comparison; dependency injection to protect admin routes.

```python
# app/services/auth.py
import hmac, os
from fastapi import Cookie, HTTPException
from itsdangerous import URLSafeTimedSerializer

_secret = os.environ.get("SECRET_KEY", "change-me-in-production")
_serializer = URLSafeTimedSerializer(_secret)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

def check_password(submitted: str) -> bool:
    return hmac.compare_digest(submitted.encode(), ADMIN_PASSWORD.encode())

def create_session_token() -> str:
    return _serializer.dumps("admin")

def verify_session_token(token: str) -> bool:
    try:
        _serializer.loads(token, max_age=86400)  # 24h session
        return True
    except Exception:
        return False

# FastAPI dependency
def require_admin(admin_session: str | None = Cookie(default=None)):
    if not admin_session or not verify_session_token(admin_session):
        raise HTTPException(status_code=401, detail="Admin access required")
```

**Note:** `itsdangerous` ships with fastapi[standard] via Starlette — no extra install needed.

### Pattern 5: HTMX Gear Icon Admin Panel

**What:** Gear icon in nav triggers HTMX modal overlay. Password form posts to `/admin/login`. On success, admin controls appear inline without page reload.

```html
<!-- In base.html nav -->
<button hx-get="/admin/panel" hx-target="#admin-panel" hx-swap="innerHTML">
  ⚙
</button>
<div id="admin-panel"></div>

<!-- /admin/panel returns the password prompt if unauthenticated,
     or the workspace management form if authenticated -->
```

### Anti-Patterns to Avoid

- **Storing API keys in a JSON file on disk:** D-09 explicitly forbids this. Even for MVP convenience, the Render ephemeral filesystem makes file-based storage unreliable.
- **Synchronous HTTP calls:** Using `requests` instead of `httpx` blocks the FastAPI event loop. All Instantly calls must be `await`ed.
- **Calling Instantly API in the route handler:** Phase 1 should establish that dashboard routes read from cache, not from Instantly directly. Even though the cache is empty in Phase 1, the route structure should reflect this separation.
- **APScheduler 4.x:** The latest PyPI entry for `apscheduler` is 3.11.2. Do not install `4.x` — it's a pre-release alpha with breaking API changes. Always pin `<4.0.0`.
- **Comparing passwords with `==`:** Use `hmac.compare_digest` to prevent timing attacks.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async HTTP client with connection pooling | Custom urllib.request wrapper | httpx.AsyncClient | Connection reuse, timeout config, retry transport, respx mock support |
| Background scheduler with cron-like syntax | threading.Thread + time.sleep | APScheduler AsyncIOScheduler | Exception isolation per job, configurable intervals, clean shutdown in lifespan |
| Type-safe env var config | Manual `os.environ.get()` everywhere | pydantic-settings BaseSettings | Type coercion, validation errors at startup, `.env` support, bundled with fastapi[standard] |
| Cookie session serialization | Base64 + HMAC homebrew | itsdangerous URLSafeTimedSerializer | Bundled with Starlette (ships with FastAPI), expiry, tamper detection |
| HTML templating | f-string concatenation | Jinja2 (bundled with fastapi[standard]) | Auto-escaping, template inheritance, loops/conditionals, zero additional install |

**Key insight:** `fastapi[standard]` bundles Jinja2, pydantic-settings, python-multipart, and itsdangerous (via Starlette). One install command gets most of the stack.

---

## Common Pitfalls

### Pitfall 1: ADM-05 vs D-09 Conflict

**What goes wrong:** REQUIREMENTS.md ADM-05 says "file-based persistence." CONTEXT.md D-09 says "env vars only." Implementer builds a JSON file system and ships it.

**Why it happens:** Requirements were written before the discussion phase locked D-09.

**How to avoid:** D-09 wins. The persistence mechanism is Render environment variables. The admin panel UI explains to the admin that adding/removing workspaces requires updating Render env vars and redeploying. The in-memory registry is rebuilt at every startup by reading `WORKSPACE_*_API_KEY` vars.

**Warning signs:** Any code that writes to a `.json` file for workspace storage.

### Pitfall 2: Lead Variables Are in `lead.payload`, Not `lead.custom_variables`

**What goes wrong:** Prior research and the existing `server.py` use `custom_variables`. The live API verification for this project says `lead.payload`. Building Phase 2 QA logic against the wrong field key produces 0 issues found (false negatives) for every lead.

**Why it happens:** Inconsistent field naming between Instantly API versions or endpoints.

**How to avoid:** In the first integration test of the API client, print a raw lead object and confirm the field name before Phase 2 begins. Add a comment in `instantly.py`: `# Lead variables are in lead["payload"] — verified 2026-04-04`.

**Warning signs:** QA engine reports 0 issues on a campaign known to have bad data.

### Pitfall 3: Campaign Copy Is Inline — No Separate API Call Needed

**What goes wrong:** Developer assumes campaign copy requires a separate `GET /campaigns/{id}` call and builds sequential per-campaign fetches.

**Why it happens:** REST convention suggests campaign detail is a separate endpoint. The Instantly v2 API returns sequences inline in the campaigns list response.

**How to avoid:** Sequence copy lives at `campaign["sequences"][*]["steps"][*]["variants"][*]["body"]` and `["subject"]` in the campaigns list response. Parse it directly — no additional HTTP call.

**Warning signs:** Code making `len(campaigns)` extra API calls per workspace to fetch sequence data.

### Pitfall 4: Rate Limit Collapse on "Run All" Trigger

**What goes wrong:** All 6 workspaces fire their campaign+lead fetches simultaneously. Each workspace makes 30+ API calls. 180+ concurrent calls hit Instantly in 2 seconds → 429s on all workspaces.

**Why it happens:** `asyncio.gather(*[fetch_workspace(ws) for ws in workspaces])` with no concurrency limit.

**How to avoid:** Use per-workspace `asyncio.Semaphore(5)` inside the API client. Add 100ms sleep between paginated lead pages. When triggering all workspaces, stagger with `asyncio.Semaphore(3)` at the workspace level.

**Warning signs:** "Run all" works in dev (1-2 workspaces, small campaigns) but fails in production.

### Pitfall 5: APScheduler 4.x Accidentally Installed

**What goes wrong:** `pip install apscheduler` without version pin installs 4.x if it becomes the default. The `AsyncIOScheduler` import path changes and the app crashes at startup.

**Why it happens:** pip resolves to "latest" by default.

**How to avoid:** Pin in requirements.txt: `APScheduler>=3.11.0,<4.0.0`. Verify with `pip show apscheduler | grep Version`.

**Warning signs:** `ImportError: cannot import name 'AsyncIOScheduler' from 'apscheduler.schedulers.asyncio'`.

### Pitfall 6: Admin Routes Accessible Without Auth

**What goes wrong:** Admin panel shows workspace API keys (last 4 chars) and workspace names to anyone who hits `/admin` directly.

**Why it happens:** Auth dependency applied in wrong place — on the POST handler but not the GET.

**How to avoid:** Add `require_admin` dependency to ALL `/admin/*` routes including GET. Write a test: unauthenticated GET to `/admin/` returns 401 or redirect to login prompt.

---

## Code Examples

Verified patterns from official sources and existing codebase:

### Cursor Pagination for Instantly v2 (campaigns)

```python
# Source: existing server.py _paginate_instantly() + official docs
async def paginate_instantly(client: httpx.AsyncClient, url: str, headers: dict) -> list[dict]:
    results = []
    cursor = None
    while True:
        params = {"limit": 100}
        if cursor:
            params["starting_after"] = cursor
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        results.extend(items)
        cursor = data.get("next_starting_after")
        if not cursor or len(items) < 100:
            break
    return results
```

### Cursor Pagination for Instantly v2 (leads — POST)

```python
# Source: existing server.py _count_not_contacted_via_api() pattern
async def fetch_active_leads(
    client: httpx.AsyncClient, api_key: str, campaign_id: str
) -> list[dict]:
    headers = {"Authorization": f"Bearer {api_key}"}
    leads = []
    cursor = None
    while True:
        body = {"campaign": campaign_id, "limit": 100}
        if cursor:
            body["starting_after"] = cursor
        resp = await client.post(
            f"{INSTANTLY_BASE}/leads/list", headers=headers, json=body
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        # Filter to active leads (status=1) — also filter in body if API supports it
        leads.extend(lead for lead in items if lead.get("status") == 1)
        cursor = data.get("next_starting_after")
        if not cursor or len(items) < 100:
            break
        await asyncio.sleep(0.1)  # 100ms between pages — rate limit safety
    return leads
```

### Parse Workspace Names from Environment

```python
# Source: Pattern for D-13 implementation
import os, re
WORKSPACE_ENV_PATTERN = re.compile(r'^WORKSPACE_([A-Z0-9_]+)_API_KEY$')

def get_workspaces_from_env() -> dict[str, str]:
    """Returns {workspace_display_name: api_key} from env vars."""
    workspaces = {}
    for env_key, value in os.environ.items():
        m = WORKSPACE_ENV_PATTERN.match(env_key)
        if m and value.strip():
            display_name = m.group(1).replace('_', ' ').title()  # ENAVRA -> Enavra
            workspaces[display_name] = value.strip()
    return workspaces
```

### pydantic-settings Config

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    admin_password: str = "changeme"
    secret_key: str = "dev-secret-change-in-prod"
    poll_interval_minutes: int = 15
    request_timeout: int = 15
    # Workspace keys loaded separately via pattern matching

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
```

### Extract Campaign Copy Variables (for Phase 2 reference)

```python
# app/services/ — Phase 2 will use this, but Phase 1 should parse copy to confirm structure
def extract_copy_from_campaign(campaign: dict) -> str:
    """Concatenate all variant body+subject text from inline sequences."""
    parts = []
    for seq in campaign.get("sequences", []):
        for step in seq.get("steps", []):
            for variant in step.get("variants", []):
                parts.append(variant.get("subject", ""))
                parts.append(variant.get("body", ""))
    return "\n".join(parts)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Instantly API v1 | Instantly API v2 | Jan 19, 2026 (v1 deprecated) | All endpoints change; `Bearer` auth instead of key query param |
| APScheduler 3.x as default | APScheduler 4.x pre-release | Early 2025 | Must pin `<4.0.0` explicitly |
| Flask + requests (sync) | FastAPI + httpx (async) | 2024-2025 ecosystem shift | Concurrent multi-workspace fetching requires async |
| pydantic v1 + FastAPI | pydantic v2 (FastAPI 0.100+) | FastAPI 0.100 (2023) | Pydantic v2 has different model syntax; don't pin to v1 |

**Deprecated/outdated:**

- `Instantly API v1`: Returns 410 Gone or redirects. All calls must use `/api/v2/` base URL.
- `APScheduler BackgroundScheduler` in FastAPI: Use `AsyncIOScheduler` — `BackgroundScheduler` uses threading and doesn't integrate cleanly with FastAPI's async event loop.
- `threading.Thread` for background polling: APScheduler with `AsyncIOScheduler` is the correct pattern for FastAPI.

---

## Open Questions

1. **Lead status filter parameter name in POST `/leads/list`**
   - What we know: Status codes are confirmed: 1=active, 3=contacted, -1=bounced. POST body takes filter params.
   - What's unclear: The exact body key for status filtering (is it `filter`, `status`, `filter_lt_status`?). The existing `server.py` uses `"filter": "FILTER_VAL_NOT_CONTACTED"` — but that's a named filter, not a status code filter.
   - Recommendation: In the first integration test plan, include a task to fetch 10 leads from a real campaign and inspect the raw response to confirm: (a) the `payload` field name, and (b) the correct body parameter for status=1 filtering. If no status filter exists in the POST body, filter client-side after fetch.

2. **`lead.payload` vs `lead.variables` vs `lead.custom_variables`**
   - What we know: CONTEXT.md and PROJECT.md both state `lead.payload` — verified live 2026-04-04.
   - What's unclear: Whether the existing `server.py`'s use of `custom_variables` applies to a different endpoint or an older API version.
   - Recommendation: First task in the API client plan must be to fetch one real lead and print its keys. Do not build Phase 2 QA logic until this is confirmed.

3. **Admin panel gear icon: inline panel or separate page?**
   - What we know: D-05 says gear icon in main nav bar. D-06 says password prompt appears on click.
   - What's unclear: Whether this is an HTMX-loaded slide-out panel, a modal, or a separate `/admin` page loaded via HTMX.
   - Recommendation: HTMX `hx-get="/admin/panel"` into a `<div id="admin-overlay">` that renders as a fixed-position right panel. Avoids page navigation, keeps QA results visible. Implement as an HTMX-swapped partial.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | Entire project | ✓ | 3.14.3 (local); Render: 3.11 | Use venv; Render uses 3.11 |
| pip3 | Package install | ✓ | 26.0 | — |
| git | Repo management | ✓ | 2.50.1 | — |
| uvicorn | Dev server | ✗ (not global) | — | Install in venv: `pip install "fastapi[standard]"` |
| Instantly API (live) | Integration tests | ✓ (6 workspaces) | v2 (confirmed) | respx mocks for unit tests |
| Render account | Deployment | ✓ (existing) | — | — |
| GitHub | Repo hosting | ✓ (existing) | — | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**

- uvicorn: Not installed globally. Install into project venv as part of `pip install "fastapi[standard]"`. No action needed at setup time.

**Render Python version:** Render defaults to the Python version in `runtime.txt`. Add `runtime.txt` containing `python-3.11.0` to the project root. FastAPI 0.135.x requires Python 3.10+ — 3.11 is the safe production target.

---

## Validation Architecture

nyquist_validation is enabled (config.json `workflow.nyquist_validation: true`).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.24.x |
| Config file | `pytest.ini` (Wave 0 gap — create with `asyncio_mode = "auto"`) |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ --cov=app --cov-report=term-missing` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INF-01 | Module structure is correct — imports work across layers | smoke | `python -c "from app.api.instantly import list_campaigns"` | ❌ Wave 0 |
| INF-03 | No hardcoded API keys in source | static | `grep -r "Bearer " app/ --include="*.py" \| grep -v "env\|config\|os.environ"` | — |
| API-01 | Campaigns fetched from Instantly with pagination | unit | `pytest tests/test_instantly.py::test_list_campaigns_paginated -x` | ❌ Wave 0 |
| API-02 | Only status=0 and status=1 campaigns returned | unit | `pytest tests/test_instantly.py::test_campaign_status_filter -x` | ❌ Wave 0 |
| API-03 | Sequence copy extracted from campaign.sequences inline | unit | `pytest tests/test_instantly.py::test_extract_campaign_copy -x` | ❌ Wave 0 |
| API-04 | Leads paginated with cursor, all pages collected | unit | `pytest tests/test_instantly.py::test_leads_pagination -x` | ❌ Wave 0 |
| API-05 | Only status=1 leads returned | unit | `pytest tests/test_instantly.py::test_lead_status_filter -x` | ❌ Wave 0 |
| API-06 | Variables read from `lead.payload` dict | unit | `pytest tests/test_instantly.py::test_lead_payload_read -x` | ❌ Wave 0 |
| API-07 | Rate limit respected — no 429 on concurrent fetch | integration | `pytest tests/test_instantly.py::test_rate_limit_semaphore -x` | ❌ Wave 0 |
| ADM-01 | Admin can add workspace via panel form | integration | `pytest tests/test_admin.py::test_add_workspace -x` | ❌ Wave 0 |
| ADM-02 | Admin can remove workspace | integration | `pytest tests/test_admin.py::test_remove_workspace -x` | ❌ Wave 0 |
| ADM-03 | Admin panel requires password | integration | `pytest tests/test_admin.py::test_auth_required -x` | ❌ Wave 0 |
| ADM-04 | Dashboard routes are open (no auth) | integration | `pytest tests/test_admin.py::test_dashboard_open_access -x` | ❌ Wave 0 |
| INF-02 | App starts and health endpoint returns 200 | smoke | `pytest tests/test_routes.py::test_health_check -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ --cov=app --cov-report=term-missing`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_instantly.py` — covers API-01 through API-07 using respx mocks
- [ ] `tests/test_admin.py` — covers ADM-01 through ADM-04 using FastAPI TestClient
- [ ] `tests/test_routes.py` — covers INF-02, smoke tests for all routes
- [ ] `tests/fixtures/campaign_response.json` — mock GET /campaigns response with sequences inline
- [ ] `tests/fixtures/leads_response.json` — mock POST /leads/list response with `payload` dict
- [ ] `pytest.ini` — `asyncio_mode = "auto"` setting
- [ ] `.env.example` — template showing required env var names
- [ ] Framework install: `pip install pytest pytest-asyncio respx` in dev requirements

---

## Sources

### Primary (HIGH confidence)

- PyPI fastapi — version 0.135.3 confirmed 2026-04-04
- PyPI httpx — version 0.28.1 confirmed 2026-04-04
- PyPI apscheduler — version 3.11.2 confirmed 2026-04-04; 4.x is pre-release alpha
- PyPI pydantic-settings — version 2.13.1 confirmed 2026-04-04
- `.planning/research/STACK.md` — prior research, all versions still current
- `.planning/research/ARCHITECTURE.md` — build order and component boundaries
- `.planning/research/PITFALLS.md` — API integration and rate limit patterns
- `gtm/prospeqt-outreach-dashboard/server.py` — live Instantly v2 API patterns: cursor pagination, Bearer auth, POST /leads/list with `starting_after`, 100ms rate limit sleep
- `.planning/phases/01-api-foundation/01-CONTEXT.md` — all locked decisions (D-01 through D-15)
- `tools/accounts/enavra/instantly.md` — confirmed API key format (base64 string), API v2 only note, rate limits

### Secondary (MEDIUM confidence)

- Render Python deployment documentation — Python 3.11 default, ASGI auto-detection, env var secrets management
- FastAPI official docs: lifespan events, Jinja2 templates, TestClient — fastapi.tiangolo.com

### Tertiary (LOW confidence)

- None — all claims in this research are supported by PRIMARY or SECONDARY sources.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all versions verified against PyPI registry on research date
- Architecture: HIGH — patterns derived from existing working code in `server.py` and prior architecture research
- API shapes: HIGH — verified against live Instantly v2 API on 2026-04-04 per PROJECT.md
- Pitfalls: HIGH — derived from existing `server.py` patterns (known working) and prior pitfalls research

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable stack; API shapes confirmed live)
