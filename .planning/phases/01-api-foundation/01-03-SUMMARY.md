---
phase: "01"
plan: "03"
subsystem: "admin-panel"
tags: [fastapi, jinja2, htmx, admin, auth, templates, integration-tests]
dependency_graph:
  requires: ["01-01"]
  provides: ["admin-panel-routes", "html-templates", "admin-integration-tests"]
  affects: ["02-01"]
tech_stack:
  added: []
  patterns: ["Starlette 1.0 TemplateResponse API (request as first arg)", "POST-redirect-GET pattern for form submissions", "httponly cookie auth with path scoping"]
key_files:
  created:
    - prospeqt-email-qa/app/routes/admin.py
    - prospeqt-email-qa/app/routes/dashboard.py
    - prospeqt-email-qa/app/templates/base.html
    - prospeqt-email-qa/app/templates/login.html
    - prospeqt-email-qa/app/templates/admin.html
    - prospeqt-email-qa/app/templates/dashboard.html
    - prospeqt-email-qa/tests/test_admin.py
    - prospeqt-email-qa/tests/test_routes.py
  modified:
    - prospeqt-email-qa/app/main.py
decisions:
  - "Use POST /admin/workspaces/{name}/delete (not HTTP DELETE) for browser form compatibility"
  - "TemplateResponse uses Starlette 1.0 API: request as first positional arg, context as keyword arg"
  - "Admin cookie scoped to path=/admin with httponly and samesite=lax"
  - "2-field add workspace form (name + api_key only, no platform field — per D-07)"
metrics:
  duration: "~6 minutes"
  completed_date: "2026-04-04"
  tasks_completed: 3
  files_created: 8
  files_modified: 1
---

# Phase 01 Plan 03: Admin Panel, Templates, and Integration Tests Summary

**One-liner:** Password-protected admin panel with workspace CRUD via FastAPI routes, Jinja2 templates matching the UI-SPEC design contract, and 12 passing integration tests.

## What Was Built

### Admin Routes (`app/routes/admin.py`)
- 6 routes with `/admin` prefix: login GET/POST, panel GET, workspaces POST (add), workspaces/{name}/delete POST, logout GET
- `require_admin` dependency guards GET /admin, POST /admin/workspaces, POST /admin/workspaces/{name}/delete
- Password verification via `check_password()` + `create_session_token()` for session cookie
- httponly cookie (`admin_session`) with `path=/admin` and `samesite=lax`
- 2-field workspace form: `workspace_name` + `api_key` only (no platform field — per D-07)
- POST-redirect-GET pattern for all form submissions

### Dashboard Routes (`app/routes/dashboard.py`)
- `GET /` — renders dashboard.html, no auth required (per ADM-04)
- `GET /health` — returns `{"status": "ok"}`, no auth required

### HTML Templates
- `base.html`: Inter font via Google Fonts, HTMX 2.0.4 CDN, full CSS custom property set from UI-SPEC, 64px topbar with gear icon (aria-label="Admin settings"), `showToast()` JS function with success/error variants
- `login.html`: "Admin Access" heading, password field, "Sign In" button, inline error with `var(--red)`, centered card with `var(--sh-md)`
- `admin.html`: "Workspace Admin" heading, 2-field add form (Workspace Name + API Key), workspace table with Connected dot status, confirm() remove dialog, sign out link, empty state text, JS field validation to disable Add button until both fields filled
- `dashboard.html`: placeholder extending base.html

### Integration Tests (12 total, all passing)
- `test_admin.py`: 9 tests — login renders, correct/wrong password, auth required, panel with auth, add workspace (2-field), remove workspace, logout, dashboard open access
- `test_routes.py`: 3 tests — health check JSON, dashboard HTML content-type, 404 for unknown routes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TemplateResponse API for Starlette 1.0 / Python 3.14**
- **Found during:** Task 3 (running tests)
- **Issue:** Starlette 1.0's `Jinja2Templates.TemplateResponse` changed its signature — `request` is now the first positional argument, not inside the context dict. Passing `{"request": request, ...}` as context caused a `TypeError: cannot use 'tuple' as a dict key` in Jinja2's LRU cache (because `Request` objects are unhashable in Python 3.14).
- **Fix:** Updated all `TemplateResponse` calls in `admin.py` and `dashboard.py` to use new API: `templates.TemplateResponse(request, "template.html", context={...})`
- **Files modified:** `app/routes/admin.py`, `app/routes/dashboard.py`
- **Commit:** 37ceaf2

## Known Stubs

- `dashboard.html` contains placeholder text "QA results will appear here after Phase 2 and Phase 3 are complete." — intentional stub, resolved in Phase 3.
- Workspace status is hardcoded to "Connected" for all workspaces — API health checking is not implemented until Phase 2.

## Self-Check: PASSED

All 8 created files confirmed present. All 3 task commits verified:
- b413269: feat(01-03): add admin and dashboard routes, wire into FastAPI app
- d7f3954: feat(01-03): create HTML templates per UI-SPEC design contract
- 37ceaf2: feat(01-03): add integration tests and fix TemplateResponse API for Starlette 1.0

Test suite: 12/12 passing.
