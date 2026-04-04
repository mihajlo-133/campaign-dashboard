---
phase: 01-api-foundation
verified: 2026-04-04T12:03:06Z
status: gaps_found
score: 16/17 must-haves verified
gaps:
  - truth: "ADM-05: API keys stored with file-based persistence that survives app restarts"
    status: partial
    reason: "Workspace registry reads from env vars at startup (survives restarts if env is set at deploy time), but workspaces added at runtime via add_workspace() are stored only in os.environ for the current process — they are lost on restart. No file-based persistence layer (JSON, SQLite, etc.) exists."
    artifacts:
      - path: "prospeqt-email-qa/app/services/workspace.py"
        issue: "add_workspace() writes to os.environ only — not to any persistent file. Dynamically-added workspaces disappear on restart."
    missing:
      - "File-based persistence for runtime add/remove (e.g., write to .workspaces.json, load at startup alongside env vars)"
      - "load_from_env() should also load from persistence file, or add_workspace() should write to a file"
human_verification:
  - test: "Visual QA of admin panel templates"
    expected: "Login page, admin workspace table, and nav gear icon render correctly in browser with correct spacing, colors, and interactions"
    why_human: "Template rendering requires a running server and browser — cannot verify visual quality programmatically"
  - test: "End-to-end admin workflow"
    expected: "Admin can log in, add a workspace via the form, see it in the table, and remove it — full browser interaction"
    why_human: "Full form submission flow with redirects and cookie persistence requires a running server"
---

# Phase 01: API Foundation Verification Report

**Phase Goal:** The app can connect to configured Instantly workspaces, authenticate as admin, and return structured campaign + lead data
**Verified:** 2026-04-04T12:03:06Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Project directory exists with modular structure (app/routes, app/services, app/api, app/models, app/templates) | VERIFIED | All 5 subdirectories confirmed: `ls prospeqt-email-qa/app/` shows api, services, routes, models, templates |
| 2 | App can start and read workspace config from WORKSPACE_*_API_KEY environment variables | VERIFIED | `WORKSPACE_TEST_API_KEY=abc123 python -c "from app.services.workspace import load_from_env, list_workspaces; load_from_env(); print(list_workspaces())"` returns `[{'name': 'test', 'key_preview': '...c123'}]` |
| 3 | No API keys are hardcoded in any source file | VERIFIED | Grep for hardcoded Bearer tokens in app/ returns nothing; all auth flows through env vars and settings |
| 4 | Test framework is installed and all tests pass | VERIFIED | `pytest tests/ -v` exits 0 with 28 passed, 0 failures |
| 5 | Workspace registry loads from env vars at startup and exposes list/get/add/remove | VERIFIED | `workspace.py` implements all 5 operations; `load_from_env()` called in lifespan; `list_workspaces()`, `get_api_key()`, `add_workspace()`, `remove_workspace()` all implemented |
| 6 | API client fetches all campaigns (GET) with cursor pagination, status 0+1 filter | VERIFIED | `instantly.py` line 61: `[c for c in all_campaigns if c.get("status") in (0, 1)]`; pagination loop runs until `next_starting_after` is None; test `test_list_campaigns_returns_all_pages` passes |
| 7 | Only draft (status=0) and active (status=1) campaigns returned | VERIFIED | Line 61 in instantly.py filters by `status in (0, 1)`; `test_campaign_status_filter` passes |
| 8 | Sequence copy extracted from inline campaign.sequences[].steps[].variants[].body/subject — no extra API call | VERIFIED | `extract_copy_from_campaign()` iterates sequences/steps/variants inline; `test_extract_campaign_copy` passes |
| 9 | All active leads (status=1) fetched via POST /leads/list with cursor pagination | VERIFIED | `fetch_all_leads()` uses POST with body `{"campaign": ..., "limit": 100}`, pagination via `starting_after` in body; line 101: `[lead for lead in all_leads if lead.get("status") == 1]` |
| 10 | Lead variables read from lead.payload dict | VERIFIED | Comment in code: `# Lead variables are in lead["payload"] — verified 2026-04-04`; `test_lead_payload_read` passes; fixture has `"payload"` key |
| 11 | Per-workspace rate limiting prevents 429 errors | VERIFIED | `_get_semaphore()` returns `asyncio.Semaphore(5)` per workspace; `test_rate_limit_semaphore` passes |
| 12 | Admin can add a new workspace by entering name + API key in a form | VERIFIED | POST `/admin/workspaces` accepts `workspace_name` + `api_key` form fields; `test_add_workspace` passes |
| 13 | Admin can remove a workspace and it disappears from the list | VERIFIED | POST `/admin/workspaces/{name}/delete` calls `remove_workspace(name)`; `test_remove_workspace` passes |
| 14 | Admin panel is password-protected — unauthenticated access redirects to 401 | VERIFIED | `require_admin` dependency on GET /admin, POST /admin/workspaces, POST /admin/workspaces/{name}/delete (4 occurrences); `test_admin_panel_requires_auth` passes |
| 15 | Dashboard routes are open access — no login required | VERIFIED | `dashboard.py` routes have no auth dependency; `test_dashboard_open_access` passes |
| 16 | Gear icon in nav bar links to admin panel | VERIFIED | `base.html` contains `<a href="/admin" class="gear-btn" aria-label="Admin settings">` with inline gear SVG |
| 17 | ADM-05: API keys stored with file-based persistence that survives app restarts | PARTIAL | Env-var-based workspaces survive restarts if set at deploy time, but dynamically added workspaces (via admin form) are lost on restart — no file write in `add_workspace()` |

**Score:** 16/17 truths verified (1 partial)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `prospeqt-email-qa/app/main.py` | FastAPI app factory with lifespan | VERIFIED | `create_app()` factory, lifespan calls `load_from_env()`, includes both routers |
| `prospeqt-email-qa/app/config.py` | Settings class reading env vars via pydantic-settings | VERIFIED | `class Settings(BaseSettings)` with all required fields |
| `prospeqt-email-qa/app/services/workspace.py` | Workspace registry: load_from_env, list_workspaces, get_api_key, add_workspace, remove_workspace | VERIFIED | All 5 functions present and tested |
| `prospeqt-email-qa/app/services/auth.py` | check_password, create_session_token, verify_session_token, require_admin | VERIFIED | All 4 functions present using hmac + itsdangerous |
| `prospeqt-email-qa/app/api/instantly.py` | Async Instantly v2 API client: list_campaigns, fetch_all_leads, extract_copy_from_campaign | VERIFIED | All 3 functions present with pagination, filtering, rate limiting |
| `prospeqt-email-qa/app/models/instantly.py` | Pydantic models: Campaign, Lead, Workspace | VERIFIED | Campaign, Lead, LeadPayload, CampaignVariant, CampaignStep, CampaignSequence |
| `prospeqt-email-qa/app/routes/admin.py` | Admin routes with require_admin dependency | VERIFIED | 6 routes; require_admin on 3 protected endpoints |
| `prospeqt-email-qa/app/routes/dashboard.py` | Dashboard routes: GET / (placeholder), GET /health | VERIFIED | Both routes present, no auth dependency |
| `prospeqt-email-qa/app/templates/base.html` | Base template with nav bar, gear icon, CSS custom properties, HTMX script | VERIFIED | All CSS vars, HTMX 2.0.4, gear icon with aria-label, showToast JS function |
| `prospeqt-email-qa/app/templates/login.html` | Admin login page per UI-SPEC | VERIFIED | "Admin Access" heading, password field, "Sign In" button, error display |
| `prospeqt-email-qa/app/templates/admin.html` | Admin panel with workspace list table and add form per UI-SPEC | VERIFIED | "Workspace Admin" heading, 2-field form (name + API key, no Platform field per D-07), workspace table with remove confirm dialog |
| `prospeqt-email-qa/app/templates/dashboard.html` | Dashboard placeholder | VERIFIED | Extends base.html, placeholder content |
| `prospeqt-email-qa/tests/conftest.py` | Shared pytest fixtures for TestClient and mock workspaces | VERIFIED | mock_env, app_client, campaign_response, leads_response fixtures |
| `prospeqt-email-qa/tests/fixtures/campaign_response.json` | Mock Instantly campaigns API response with inline sequences | VERIFIED | 4 campaigns with statuses 0/1/2/3, sequences with steps.variants containing subject+body |
| `prospeqt-email-qa/tests/fixtures/leads_response.json` | Mock Instantly leads API response with payload dict | VERIFIED | 4 leads with statuses 1/1/-1/3, each with `payload` dict |
| `prospeqt-email-qa/tests/test_instantly.py` | API client tests using respx mocks | VERIFIED | 9 test functions covering pagination, filtering, copy extraction, rate limiting, error handling |
| `prospeqt-email-qa/tests/test_admin.py` | Integration tests for admin auth, add/remove workspace | VERIFIED | 9 test functions for full admin auth flow |
| `prospeqt-email-qa/tests/test_workspace.py` | Unit tests for workspace registry | VERIFIED | 7 test functions |
| `prospeqt-email-qa/tests/test_routes.py` | Smoke tests for routes | VERIFIED | 3 test functions |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/main.py` | `app/services/workspace.py` | `load_from_env()` in lifespan | VERIFIED | Line 9: `from app.services.workspace import load_from_env`; line 21: `load_from_env()` in lifespan |
| `app/config.py` | environment variables | `class Settings(BaseSettings)` | VERIFIED | `class Settings(BaseSettings)` with `model_config = {"env_file": ".env"}` |
| `app/api/instantly.py` | `https://api.instantly.ai/api/v2` | httpx.AsyncClient with Bearer auth | VERIFIED | `INSTANTLY_BASE = "https://api.instantly.ai/api/v2"`; auth header `{"Authorization": f"Bearer {api_key}"}` |
| `app/api/instantly.py` | `app/services/workspace.py` | `get_api_key` import pattern | VERIFIED | API client receives api_key parameter; callers use workspace registry to supply it |
| `app/routes/admin.py` | `app/services/auth.py` | `require_admin` dependency, `check_password` | VERIFIED | Lines 7: `from app.services.auth import check_password, create_session_token, require_admin` |
| `app/routes/admin.py` | `app/services/workspace.py` | `add_workspace`, `remove_workspace`, `list_workspaces` | VERIFIED | Line 8: `from app.services.workspace import add_workspace, list_workspaces, remove_workspace` |
| `app/main.py` | `app/routes/admin.py` | `app.include_router(admin.router)` | VERIFIED | Line 49: `application.include_router(admin.router)` |
| `app/main.py` | `app/routes/dashboard.py` | `app.include_router(dashboard.router)` | VERIFIED | Line 48: `application.include_router(dashboard.router)` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `app/api/instantly.py::list_campaigns` | `all_campaigns` | httpx GET to `api.instantly.ai/api/v2/campaigns` with real Bearer auth | Yes — real API call with cursor pagination | FLOWING |
| `app/api/instantly.py::fetch_all_leads` | `all_leads` | httpx POST to `api.instantly.ai/api/v2/leads/list` | Yes — real API call with cursor pagination | FLOWING |
| `app/routes/admin.py::admin_panel` | `workspaces` | `list_workspaces()` → `_registry` dict populated by `load_from_env()` | Yes — reads from env vars at startup | FLOWING |
| `app/templates/dashboard.html` | none | Placeholder template — no dynamic data in Phase 1 | N/A — intentional placeholder for Phase 3 | EXPECTED PLACEHOLDER |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 28 tests pass | `pytest tests/ -v` | 28 passed, 0 failed, 6 warnings (deprecation only) in 0.54s | PASS |
| App imports cleanly | `python -c "from app.main import app; ..."` | "All imports OK" | PASS |
| Workspace registry loads from env | `WORKSPACE_TEST_API_KEY=abc123 python -c "..."` | `[{'name': 'test', 'key_preview': '...c123'}]` | PASS |
| No hardcoded API keys | grep for Bearer tokens in app/ | "NO HARDCODED KEYS FOUND" | PASS |
| Templates pass UI-SPEC checks | Python template assertion script | "All template checks passed" | PASS |
| Admin routes count | Python route inspection | 6 admin routes, 2 dashboard routes | PASS |
| Semaphore limit | `_get_semaphore('test')._value` | 5 | PASS |
| Campaign filter present | `grep "status in (0, 1)"` | Line 61 confirmed | PASS |
| Lead filter present | `grep "== 1"` | Line 101 confirmed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| INF-01 | 01-01 | Modular codebase — routes, API clients, QA logic, templates in separate modules | SATISFIED | All 5 module directories exist and import correctly |
| INF-02 | 01-01 | Deployable to Render as a standard Python web app | SATISFIED | `Procfile` with gunicorn + uvicorn worker; `runtime.txt: python-3.11.0`; no non-stdlib build requirements |
| INF-03 | 01-01 | No hardcoded API keys in source code | SATISFIED | Grep finds zero hardcoded keys in app/ |
| INF-04 | 01-01 | Project pushed to GitHub as its own repository/directory | NEEDS HUMAN | Requires checking actual GitHub state — cannot verify programmatically from within the repo |
| API-01 | 01-02 | System fetches all campaigns from configured Instantly workspaces via v2 API | SATISFIED | `list_campaigns()` with Bearer auth, GET endpoint, cursor pagination |
| API-02 | 01-02 | System filters campaigns by status — only active (status=1) and draft (status=0) | SATISFIED | Line 61: `[c for c in all_campaigns if c.get("status") in (0, 1)]` |
| API-03 | 01-02 | System extracts sequence copy from inline campaign.sequences[].steps[].variants[] | SATISFIED | `extract_copy_from_campaign()` iterates inline — no extra API call |
| API-04 | 01-02 | System fetches all leads from filtered campaigns via POST /api/v2/leads/list | SATISFIED | `fetch_all_leads()` uses POST with cursor pagination |
| API-05 | 01-02 | System filters leads to active-only (status=1) | SATISFIED | Line 101: `[lead for lead in all_leads if lead.get("status") == 1]` |
| API-06 | 01-02 | System reads lead variables from lead.payload dict | SATISFIED | Comment confirmed: `# Lead variables are in lead["payload"]`; models use `payload: dict` |
| API-07 | 01-02 | System respects Instantly rate limits with per-workspace throttling | SATISFIED | `asyncio.Semaphore(5)` per workspace; `await asyncio.sleep(0.1)` between pages |
| ADM-01 | 01-03 | Admin panel to add new Instantly workspaces | SATISFIED | POST /admin/workspaces with 2-field form |
| ADM-02 | 01-03 | Admin panel to remove existing workspaces | SATISFIED | POST /admin/workspaces/{name}/delete |
| ADM-03 | 01-03 | Admin panel protected by simple password authentication | SATISFIED | `require_admin` dependency on all admin write routes; hmac-based password check |
| ADM-04 | 01-03 | QA viewing is open access — no login required | SATISFIED | Dashboard routes have zero auth dependencies |
| ADM-05 | 01-01 | API keys stored server-side with file-based persistence (survives app restarts, supports runtime add/remove) | PARTIAL | Env-var workspaces persist across Render deploys; dynamically added workspaces (runtime add) are lost on app restart — `add_workspace()` writes only to `os.environ` for the current process, no file |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/templates/dashboard.html` | N/A | Placeholder content — intentional per Phase 1 design | Info | No impact — placeholder is expected and documented in plan |
| None | — | No TODO/FIXME/HACK comments in source | — | Clean |
| None | — | No empty return stubs in production code | — | Clean |
| None | — | No hardcoded credentials | — | Clean |

### Human Verification Required

#### 1. Template Visual Rendering

**Test:** Start the app with `uvicorn app.main:app`, open `http://localhost:8000/admin/login` in a browser
**Expected:** Login card is centered, 360px wide, with correct Inter font, blue "Sign In" button, and proper spacing per UI-SPEC Component 2
**Why human:** CSS rendering and visual quality cannot be verified programmatically

#### 2. INF-04 GitHub Push

**Test:** Check `https://github.com/` for the `prospeqt-email-qa` repository or directory
**Expected:** Project is accessible as a GitHub repository or subdirectory in an existing repo
**Why human:** Cannot verify external GitHub state from within the local repo

#### 3. End-to-End Admin Workflow

**Test:** Start app, log in, add a workspace via the form, verify it appears in the table, click Remove and confirm
**Expected:** Full workflow completes without errors; workspace appears/disappears correctly; confirm dialog shows with correct text
**Why human:** Cookie-based session auth through a real browser, form interactions, and redirect handling need a running server

### Gaps Summary

**1 gap blocks full ADM-05 compliance:**

ADM-05 requires "file-based persistence (survives app restarts, supports runtime add/remove)." The current implementation uses env vars exclusively:

- Workspaces configured via environment variables (e.g., `WORKSPACE_ENAVRA_API_KEY=...`) DO survive restarts because they are set at the deployment level (Render env vars).
- Workspaces added at runtime via the admin panel form call `add_workspace()`, which writes to `os.environ` for the current process only. If the server restarts, these dynamically-added workspaces are gone.

The plan's `must_haves.truths` for ADM-05 only says "loads from env vars at startup and exposes list/get/add/remove operations," which IS satisfied. However, REQUIREMENTS.md says "file-based persistence (survives app restarts)" — the stricter definition is not met.

**Practical impact:** For the immediate use case (GTM engineers adding workspaces via the admin panel), any workspace added through the UI would be lost on the next deploy or restart. The workaround is to set env vars at the Render dashboard level, but that bypasses the admin UI entirely.

**Fix:** `add_workspace()` should also write to a JSON file (e.g., `workspaces.json`), and `load_from_env()` should be augmented (or a separate `load_from_file()` called in lifespan) to merge env-var workspaces with file-persisted ones.

---

_Verified: 2026-04-04T12:03:06Z_
_Verifier: Claude (gsd-verifier)_
