# Stack Research

**Domain:** Modular Python web dashboard — REST API data fetching, background polling, server-side rendering
**Researched:** 2026-04-04
**Confidence:** HIGH (verified against PyPI, official docs, Render documentation)

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| FastAPI | 0.135.3 | Web framework / API layer | Async-native (matches httpx + APScheduler), auto-generates OpenAPI docs, Pydantic integration built-in, Render has native ASGI support. Benchmarks at 15-20k req/s vs Flask's 2-3k. For a dashboard doing concurrent API polling across 6 workspaces, async is not optional — it's the architecture. |
| Uvicorn | 0.43.0 | ASGI server | FastAPI's recommended server. Render detects and configures it automatically. Single-worker for MVP, Gunicorn+UvicornWorker for multi-core scale. |
| Jinja2 | 3.x (bundled with fastapi[standard]) | Server-side HTML rendering | Render full HTML pages, not JSON. Dashboard is a read-mostly display tool — no React SPA needed. Jinja2 ships with FastAPI's standard install, zero additional config. |
| HTMX | 2.x (CDN, no install) | Partial page updates without JS | Manual "run check" triggers and per-campaign refresh need DOM updates without a full page reload. HTMX handles this with HTML attributes — no custom JS. Pairs with FastAPI+Jinja2 as a documented pattern in 2025. |
| httpx | 0.28.1 | Async HTTP client for Instantly API | Async-native, supports connection pools, retries via AsyncHTTPTransport, timeout config. Direct replacement for `requests` in async context. Use `AsyncClient` with a shared client instance across the app lifespan. |
| APScheduler | 3.11.2 | Background polling scheduler | Stable production release (v4 is pre-release alpha, do not use in prod). AsyncIOScheduler integrates cleanly with FastAPI's lifespan events. Runs interval jobs for workspace polling without a separate Celery/Redis stack. |
| pydantic-settings | 2.x (bundled with fastapi[standard]) | Environment-based config / API key storage | Type-safe config from env vars and .env files. API keys stored as env vars on Render (not in code). Zero-friction on Render: set env vars in dashboard, pydantic-settings reads them automatically. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-multipart | 0.0.x (bundled with fastapi[standard]) | Form data parsing | Admin panel password submission uses HTML forms, not JSON bodies. Required for FastAPI to parse form fields. |
| gunicorn | 23.x | Production process manager | Add when deploying to Render with multiple workers. Start command: `gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker`. For MVP single-worker, plain `uvicorn` suffices. |
| pytest | 8.x | Test runner | Unit tests for QA logic (variable parsing, flag detection), integration tests for API routes. Standard choice, no alternatives needed. |
| pytest-asyncio | 0.24.x | Async test support | Required for testing async FastAPI routes and the httpx async client calls. Add `asyncio_mode = "auto"` to pytest.ini. |
| respx | 0.21.x | httpx request mocking | Mock Instantly API responses in tests. Works as a drop-in mock transport for httpx.AsyncClient. Do not call live APIs in tests. |
| python-dotenv | 1.x | .env file loading for local dev | Loaded automatically by pydantic-settings when running locally. Not needed on Render (env vars set directly). |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uvicorn (dev mode) | Hot-reload during development | `uvicorn app.main:app --reload` — auto-restarts on file changes. Never use `--reload` in production. |
| pytest-cov | Coverage reporting | `pytest --cov=app` — target >80% coverage on QA logic module specifically. |
| ruff | Linting + formatting | Replaces flake8+black+isort. Single tool, fast, opinionated. Add to pre-commit or CI. |

## Installation

```bash
# Core — installs FastAPI + Uvicorn + Jinja2 + pydantic-settings + python-multipart
pip install "fastapi[standard]"

# Async HTTP client
pip install httpx==0.28.1

# Background scheduler (stable 3.x, NOT 4.x)
pip install "APScheduler>=3.11,<4.0"

# Production server (add when deploying)
pip install gunicorn

# Dev dependencies (keep in requirements-dev.txt)
pip install pytest pytest-asyncio pytest-cov respx python-dotenv ruff
```

**requirements.txt (production):**
```
fastapi[standard]>=0.135.0
httpx>=0.28.0,<0.29.0
APScheduler>=3.11.0,<4.0.0
gunicorn>=23.0.0
```

**Render start command:**
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
Or with multi-worker:
```
gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| FastAPI | Flask | If team is already Flask-heavy and no async needs exist. Flask is simpler to onboard but requires explicit async extensions (Flask-Async) and has no built-in data validation. For this project's concurrent multi-workspace polling, async is necessary — Flask would fight you. |
| FastAPI | Django | If you need a full ORM, admin panel, auth system, and migrations out of the box. Django is heavyweight for a dashboard that stores nothing in a database. |
| APScheduler 3.x | Celery + Redis | If jobs are CPU-bound, distributed, or need persistence across restarts. For periodic API polling (lightweight, single-process), Celery adds a Redis dependency, worker process, and ops overhead with no benefit at this scale. |
| APScheduler 3.x | APScheduler 4.x | When v4 reaches stable. v4 is alpha as of April 2026 — breaking changes likely. Pin to `<4.0.0`. |
| httpx | aiohttp | httpx has a closer-to-requests API, better timeout config, and simpler retry setup. aiohttp is fine but adds no value over httpx for this use case. |
| Jinja2 + HTMX | React / Vue SPA | If you need complex client-side state, real-time websocket updates, or a design team building in component libraries. For a QA dashboard read by ops/GTM team, SSR is simpler to maintain and faster to ship. |
| pydantic-settings | python-decouple / dynaconf | pydantic-settings is the FastAPI-native solution, ships in the standard install, supports type validation. No reason to add a second config library. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| APScheduler 4.x | Pre-release alpha as of April 2026. Author warns: "may change in a backwards incompatible fashion without any migration pathway." | APScheduler 3.11.2 — stable, widely used, asyncio support via AsyncIOScheduler |
| Celery | Requires Redis broker, separate worker process, separate monitoring. Zero benefit at single-server scale with lightweight polling jobs. | APScheduler 3.x in-process background scheduler |
| SQLite / SQLAlchemy | This dashboard has no persistent data storage requirement. API keys go in env vars. QA results are computed on-demand from live Instantly API data. Adding a DB layer is premature. | In-memory dict cache with TTL; revisit when persistence is explicitly required |
| requests (sync) | Blocks the event loop when called from async FastAPI routes. Makes concurrent multi-workspace fetching sequential. | httpx.AsyncClient with async/await |
| Flask-based dashboards (Dash, Streamlit) | Streamlit/Dash are for data science notebooks, not team-facing web apps with admin panels, custom routing, and access control. They fight you when you need standard web patterns. | FastAPI + Jinja2 + HTMX |
| React / Next.js frontend | Over-engineered for a QA results display page. Adds build pipeline, npm dependency management, CORS config, and a separate deployment. | Jinja2 templates + HTMX for interactivity |
| Docker (MVP) | Render handles Python ASGI apps natively without Docker. Docker adds Dockerfile maintenance and slower builds for no benefit on Render's managed platform. | Native Render Python environment with requirements.txt |

## Stack Patterns by Variant

**For the background polling loop:**
Use `AsyncIOScheduler` (APScheduler 3.x) started in FastAPI's `lifespan` async context manager. This ensures the scheduler starts after app startup and shuts down cleanly:
```python
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(poll_all_workspaces, "interval", minutes=15)
    scheduler.start()
    yield
    scheduler.shutdown()
```

**For manual "run check" triggers (HTMX):**
HTMX posts to a FastAPI endpoint that triggers the check and returns an HTML fragment, which HTMX swaps into the page. No page reload, no JavaScript:
```html
<button hx-post="/check/workspace/{{workspace_id}}" hx-target="#results-{{workspace_id}}" hx-swap="innerHTML">
  Run Check
</button>
```

**For concurrent multi-workspace API fetching:**
Use `asyncio.gather()` with the shared `httpx.AsyncClient`. Rate-limit with a semaphore to stay within Instantly API limits:
```python
sem = asyncio.Semaphore(3)  # max 3 concurrent workspace fetches
async with sem:
    results = await fetch_workspace(client, workspace_id)
```

**For Render secret management:**
Store all Instantly API keys as Render Environment Variables (Settings > Environment). Load via pydantic-settings from `os.environ`. Never write keys to disk or commit them.

## Version Compatibility

| Package | Compatible With | Notes |
|---------|----------------|-------|
| fastapi[standard] 0.135.x | Python 3.10+ | Requires Python 3.10 minimum. Render's Python 3.11 runtime is the safe target. |
| APScheduler 3.11.x | Python 3.8+ | Compatible. Use AsyncIOScheduler, not BackgroundScheduler, in async FastAPI context. |
| httpx 0.28.x | Python 3.8+ | Compatible. Pair with `anyio` for test async context (ships with fastapi[standard]). |
| pydantic v2 (ships with fastapi) | FastAPI 0.100+ | FastAPI 0.100 moved to Pydantic v2 natively. Do not pin to pydantic v1. |
| HTMX 2.x | No Python dependency | Load from CDN: `https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js`. No install required. |

## Project Structure (Recommended)

```
app/
  main.py           # FastAPI app, lifespan, router inclusion
  config.py         # pydantic-settings Settings class
  routes/
    dashboard.py    # GET / — full dashboard HTML
    checks.py       # POST /check/* — trigger QA run, return HTML fragment
    admin.py        # GET/POST /admin — workspace management
  services/
    instantly.py    # httpx async client wrapper for Instantly v2 API
    qa.py           # Variable extraction and flag logic (pure functions)
    poller.py       # APScheduler job: poll all workspaces
  templates/
    base.html
    dashboard.html
    partials/       # HTMX fragment templates
      campaign_results.html
      workspace_results.html
  static/           # CSS, any JS beyond HTMX CDN
tests/
  test_qa.py        # Unit tests for variable parsing and flag detection
  test_routes.py    # Integration tests via TestClient
  fixtures/         # Mock Instantly API responses as JSON
requirements.txt
requirements-dev.txt
render.yaml         # Optional: Render IaC config
```

## Sources

- [FastAPI PyPI](https://pypi.org/project/fastapi/) — confirmed version 0.135.3 (April 1, 2026)
- [uvicorn PyPI](https://pypi.org/project/uvicorn/) — confirmed version 0.43.0
- [httpx PyPI](https://pypi.org/project/httpx/) — confirmed version 0.28.1
- [APScheduler PyPI](https://pypi.org/project/APScheduler/) — confirmed 3.11.2 stable, 4.x is pre-release alpha
- [FastAPI deployment on Render](https://render.com/articles/fastapi-deployment-options) — ASGI auto-detection, Uvicorn config, env var secrets (MEDIUM confidence — Render article, not official Render docs)
- [FastAPI Background Tasks docs](https://fastapi.tiangolo.com/tutorial/background-tasks/) — recommended patterns for background work
- [FastAPI Templates docs](https://fastapi.tiangolo.com/advanced/templates/) — Jinja2 integration (HIGH confidence — official docs)
- [FastAPI Testing docs](https://fastapi.tiangolo.com/tutorial/testing/) — TestClient + pytest patterns (HIGH confidence — official docs)
- [APScheduler 4.x alpha warning](https://github.com/agronholm/apscheduler/issues/465) — "do NOT use this release in production" (HIGH confidence — author statement)
- WebSearch: FastAPI vs Flask 2025, HTMX+Jinja2 SSR patterns, httpx rate limiting — (MEDIUM confidence — multiple corroborating sources)

---
*Stack research for: Modular Python web dashboard — Email QA Dashboard*
*Researched: 2026-04-04*
