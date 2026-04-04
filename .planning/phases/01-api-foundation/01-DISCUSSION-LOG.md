# Phase 1: API Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** 01-api-foundation
**Areas discussed:** Project structure, Admin panel UX, API key storage, Data contracts

---

## Project Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Feature-based | Group by feature: app/admin/, app/qa/, app/dashboard/ | |
| Layer-based | Group by layer: app/routes/, app/services/, app/templates/ | |
| You decide | Whatever makes sense for a FastAPI dashboard at this scale | ✓ |

**User's choice:** You decide — Claude has discretion on internal module organization.
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| New root directory | email-qa-dashboard/ at repo root | |
| Under gtm/ | gtm/email-qa-dashboard/ — grouped with other GTM tools | |
| Separate repo | Its own GitHub repo, deployed independently | ✓ |

**User's choice:** Separate repo
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| email-qa-dashboard | Descriptive, clear purpose | |
| instantly-qa | Short, platform-specific | |
| prospeqt-email-qa | Branded to Prospeqt | ✓ |

**User's choice:** prospeqt-email-qa
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Plain venv | Simple: python -m venv, pip install, uvicorn | ✓ |
| Docker Compose | Containerized dev environment | |
| You decide | Whatever's simplest | |

**User's choice:** Plain venv
**Notes:** None

---

## Admin Panel UX

| Option | Description | Selected |
|--------|-------------|----------|
| Separate /admin route | Dedicated page at /admin with its own login gate | |
| Settings icon in nav | Gear icon in the main dashboard nav, password prompt on click | ✓ |
| You decide | Whatever feels natural | |

**User's choice:** Settings icon in nav
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Name + API key | Just a display name and the Instantly API key | ✓ |
| Name + key + config | Also set poll interval, alert thresholds, etc. | |
| Minimal for MVP | Name + API key only | |

**User's choice:** Name + API key
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Confirm dialog | "Are you sure?" with workspace name shown | ✓ |
| Instant remove | Click remove, it's gone immediately | |
| You decide | Whatever protects against accidental removal | |

**User's choice:** Confirm dialog with a simple sentence
**Notes:** User specified "confirm dialog with a simple sentence"

---

## API Key Storage

| Option | Description | Selected |
|--------|-------------|----------|
| JSON file | workspaces.json on disk — simple, readable, gitignored | |
| Environment vars | All keys in env vars — Render-native | ✓ |
| SQLite | Small database file | |
| You decide | Whatever works for Render + runtime add/remove | |

**User's choice:** Environment vars
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| No encryption | Keys stored as plaintext — server-side only | ✓ |
| Basic encryption | Encrypt with an app secret | |
| You decide | Whatever's appropriate for internal tool | |

**User's choice:** No encryption
**Notes:** None

**Follow-up: Persistence tension**

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid (Recommended) | Bootstrap from env vars + JSON file for runtime additions | |
| Env vars only | Accept that adding requires Render redeploy | ✓ |
| JSON file only | All keys in JSON on persistent disk | |
| You decide | Best admin experience | |

**User's choice:** Env vars only — accepts that workspace changes need Render dashboard update + redeploy
**Notes:** None

---

## Data Contracts

| Option | Description | Selected |
|--------|-------------|----------|
| Error badge | Show workspace with error badge + last successful data | ✓ |
| Hide workspace | Temporarily hide until API recovers | |
| You decide | Whatever communicates clearly | |

**User's choice:** Error badge
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory dict | Simple dict keyed by workspace+campaign | |
| TTL cache | In-memory with automatic expiry | |
| You decide | Whatever balances freshness with API load | ✓ |

**User's choice:** You decide — Claude's discretion on caching strategy
**Notes:** None

---

## Claude's Discretion

- Internal module organization (layer-based vs feature-based)
- Caching strategy (dict vs TTL cache vs other)
- Pydantic model design
- Error handling patterns

## Deferred Ideas

None — discussion stayed within phase scope
