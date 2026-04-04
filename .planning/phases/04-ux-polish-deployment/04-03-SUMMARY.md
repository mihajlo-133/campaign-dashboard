---
phase: "04"
plan: "03"
subsystem: deployment
tags: [render, github, deployment, production]
status: partial
created: 2026-04-04
completed: pending-task-2

dependency_graph:
  requires: [04-01, 04-02]
  provides: [github-repo, render-service, production-url]
  affects: [live-deployment, team-access]

tech_stack:
  added: []
  patterns:
    - Render free tier with Python runtime (not Docker)
    - GitHub repo as deployment source with auto-deploy on push
    - Health check at /health endpoint

key_files:
  created:
    - prospeqt-email-qa/.gitignore (updated for deployment)
  modified: []

decisions:
  - "GitHub repo created as public (mihajlo-133/prospeqt-email-qa) — no secrets in code, all keys via env vars"
  - "Render service created via REST API with serviceDetails.plan + region structure (not top-level plan field)"
  - "New service ID srv-d78k971r0fns738metu0 — NOT the old campaign-dashboard srv-d73efrfdiees73erakqg"
  - "Deploy triggered with clearCache: clear per D-09 proven pattern"
  - ".playwright-cli/ session files excluded from git (dev artifacts)"

metrics:
  duration_minutes: 5
  completed_date: 2026-04-04
  tasks_completed: 1
  files_changed: 1
---

# Phase 4 Plan 3: GitHub + Render Deployment Summary

New GitHub repo created and pushed, new Render service deployed via API at https://prospeqt-email-qa.onrender.com. Health check returns `{"status":"ok"}`. Awaiting human step: set 9 env vars in Render dashboard (workspace API keys, ADMIN_PASSWORD, SECRET_KEY).

## What Was Done

### Task 1: Create GitHub repo and push code, create Render service via API

**GitHub repo:**

- Repo: https://github.com/mihajlo-133/prospeqt-email-qa
- Visibility: PUBLIC
- Branch: main
- 47 files committed (all app code, no .env, no .venv, no .playwright-cli session files)
- .gitignore updated with: `qa/screenshots/*.png`, `.playwright-cli/`

**Render service:**

- Service ID: `srv-d78k971r0fns738metu0` (new — NOT the old srv-d73efrfdiees73erakqg)
- URL: https://prospeqt-email-qa.onrender.com
- Dashboard: https://dashboard.render.com/web/srv-d78k971r0fns738metu0
- Region: Frankfurt
- Plan: free
- Runtime: Python 3.11
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
- Health check path: `/health`
- Auto-deploy: yes (on push to main)

**Deploy status:** `live` — initial deploy completed successfully.

### Task 2: Set workspace API keys in Render dashboard

**Status: PENDING — awaiting human action**

9 env vars must be set manually in Render Dashboard → prospeqt-email-qa → Environment:

| Env Var | Source |
|---------|--------|
| WORKSPACE_MYPLACE_API_KEY | tools/prospeqt-automation/.env → INSTANTLY_MYPLACE |
| WORKSPACE_SWISHFUNDING_API_KEY | tools/prospeqt-automation/.env → INSTANTLY_SWISHFUNDING |
| WORKSPACE_SMARTMATCHAPP_API_KEY | tools/prospeqt-automation/.env → INSTANTLY_SMARTMATCHAPP |
| WORKSPACE_KAYSE_API_KEY | tools/prospeqt-automation/.env → INSTANTLY_KAYSE |
| WORKSPACE_PROSPERLY_API_KEY | tools/prospeqt-automation/.env → INSTANTLY_PROSPERLY |
| WORKSPACE_HEYREACH_API_KEY | tools/prospeqt-automation/.env → INSTANTLY_HEYREACH |
| ADMIN_PASSWORD | Set a secure password |
| SECRET_KEY | Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| QA_POLL_INTERVAL_SECONDS | 300 |

## Verification

```
gh repo view mihajlo-133/prospeqt-email-qa --json url,visibility -q '{url:.url,visibility:.visibility}'
{"url":"https://github.com/mihajlo-133/prospeqt-email-qa","visibility":"PUBLIC"}

curl -s https://prospeqt-email-qa.onrender.com/health
{"status":"ok"}

Render deploy status: live
```

## Commits

| Hash | Message |
|------|---------|
| 68b7f00 | chore(04-03): update prospeqt-email-qa .gitignore for deployment |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Render API payload structure requires serviceDetails wrapper**
- **Found during:** Task 1 (Render service creation)
- **Issue:** Plan showed `type`, `plan`, `region`, `runtime` as top-level keys in the Render API POST body. Render API v1 requires these to be inside `serviceDetails` with `envSpecificDetails` for non-static non-Docker services.
- **Fix:** Restructured payload with `serviceDetails: { plan, region, runtime, buildCommand, startCommand, healthCheckPath, envSpecificDetails: {...} }`
- **Files modified:** None (API call only)

**2. [Rule 1 - Bug] .playwright-cli/ session files included in initial git add**
- **Found during:** Task 1 (git status check before commit)
- **Issue:** `git add .` picked up `.playwright-cli/*.yml` session files — dev artifacts that should not be deployed.
- **Fix:** Added `.playwright-cli/` to .gitignore before committing, removed from staging with `git rm --cached`
- **Files modified:** `.gitignore`

## Self-Check: PASSED

- GitHub repo `mihajlo-133/prospeqt-email-qa` exists and is PUBLIC
- Render service ID `srv-d78k971r0fns738metu0` differs from old `srv-d73efrfdiees73erakqg`
- `curl https://prospeqt-email-qa.onrender.com/health` → `{"status":"ok"}`
- Commit 68b7f00 exists in main repo
