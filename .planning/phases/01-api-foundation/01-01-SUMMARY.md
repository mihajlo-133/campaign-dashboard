---
phase: "01-api-foundation"
plan: "01"
subsystem: "project-scaffold"
tags: [fastapi, pydantic-settings, workspace-registry, pytest, auth]
dependency_graph:
  requires: []
  provides:
    - prospeqt-email-qa app scaffold
    - workspace registry (load_from_env, list/get/add/remove)
    - pydantic-settings config
    - auth service (hmac + itsdangerous session tokens)
    - pytest infrastructure with fixtures
  affects:
    - "01-02 (Instantly API client) — imports from app.services.workspace"
    - "01-03 (Admin panel) — imports from app.services.auth, app.services.workspace"
tech_stack:
  added:
    - fastapi[standard]>=0.135.0
    - httpx>=0.28.0,<0.29.0
    - APScheduler>=3.11.0,<4.0.0
    - gunicorn>=23.0.0
    - itsdangerous>=2.1.0
    - pytest>=8.0.0
    - pytest-asyncio>=0.24.0
    - respx>=0.21.0
    - ruff
  patterns:
    - FastAPI app factory with lifespan (create_app pattern)
    - pydantic-settings BaseSettings for env var config
    - Module-level registry dict for workspace state
    - hmac.compare_digest + itsdangerous URLSafeTimedSerializer for session auth
    - autouse pytest fixture for registry isolation between tests
key_files:
  created:
    - prospeqt-email-qa/app/main.py
    - prospeqt-email-qa/app/config.py
    - prospeqt-email-qa/app/services/workspace.py
    - prospeqt-email-qa/app/services/auth.py
    - prospeqt-email-qa/tests/conftest.py
    - prospeqt-email-qa/tests/test_workspace.py
    - prospeqt-email-qa/tests/fixtures/campaign_response.json
    - prospeqt-email-qa/tests/fixtures/leads_response.json
    - prospeqt-email-qa/requirements.txt
    - prospeqt-email-qa/requirements-dev.txt
    - prospeqt-email-qa/Procfile
    - prospeqt-email-qa/runtime.txt
    - prospeqt-email-qa/.env.example
    - prospeqt-email-qa/.gitignore
    - prospeqt-email-qa/pytest.ini
  modified: []
decisions:
  - "itsdangerous added to requirements.txt (not bundled with fastapi[standard]) — required for auth session tokens"
  - "autouse reset_registry fixture ensures test isolation for workspace registry (module-level state)"
  - "add_workspace tests use monkeypatch.setenv before calling add_workspace to ensure os.environ cleanup on teardown"
metrics:
  duration_seconds: 259
  completed_date: "2026-04-04"
  tasks_completed: 2
  tasks_total: 2
  files_created: 22
  files_modified: 0
---

# Phase 01 Plan 01: Project Scaffold — Summary

FastAPI project scaffold with modular directory structure, pydantic-settings config, workspace registry from env vars, admin auth service, and full pytest infrastructure with verified Instantly API fixtures.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create project directory, install dependencies, scaffold all modules | 200f5e3 | 17 files created |
| 2 | Create test fixtures and conftest with workspace + app fixtures | 729b0ba | 5 files created |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Missing Dependency] Added itsdangerous to requirements.txt**
- **Found during:** Task 1
- **Issue:** `app/services/auth.py` imports `itsdangerous.URLSafeTimedSerializer` but `itsdangerous` is not bundled with `fastapi[standard]` — it's a separate package
- **Fix:** Added `itsdangerous>=2.1.0` to `requirements.txt` and installed it in the venv
- **Files modified:** `prospeqt-email-qa/requirements.txt`
- **Commit:** 200f5e3

**2. [Rule 1 - Bug] Fixed test isolation failure in workspace tests**
- **Found during:** Task 2
- **Issue:** `test_add_workspace_adds_to_registry` calls `add_workspace("newclient", "new-key")` which writes `WORKSPACE_NEWCLIENT_API_KEY` directly to `os.environ`. This env var persisted into `test_env_pattern_ignores_non_workspace_vars`, causing it to find 3 workspaces instead of 2.
- **Fix:** Added `autouse=True` fixture `reset_registry` to clear `_registry` before/after each test. In `test_add_workspace_adds_to_registry`, used `monkeypatch.setenv("WORKSPACE_NEWCLIENT_API_KEY", "")` before calling `add_workspace` so monkeypatch tracks and undoes the env var on teardown.
- **Files modified:** `prospeqt-email-qa/tests/test_workspace.py`
- **Commit:** 729b0ba

## Verification Results

```
$ cd prospeqt-email-qa && .venv/bin/python -c "from app.main import app; print('App imports OK')"
App imports OK

$ cat Procfile
web: gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT

$ WORKSPACE_TEST_API_KEY=abc123 .venv/bin/python -c "from app.services.workspace import load_from_env, list_workspaces; load_from_env(); print(list_workspaces())"
[{'name': 'test', 'key_preview': '...c123'}]

$ .venv/bin/pytest tests/ -v
7 passed in 0.01s
```

## Self-Check: PASSED

All created files verified to exist. Commit hashes 200f5e3 and 729b0ba confirmed in git log.
