# CLAUDE.md

This file provides guidance to Claude Code when working in this workspace.

---

## 1. What This Is

**Unified workspace for Mihajlo** — two domains under one roof.

| Aspect | Details |
|--------|---------|
| **User** | Mihajlo |
| **Timezone** | Europe/Belgrade (CET/CEST) |
| **Domains** | GTM Engineering (agency work, multi-client) + Personal Life Assistant |
| **Modules** | `gtm/` (GTM engineering), `life/` (personal), `tools/` (shared infra), `sessions/` (breadcrumbs) |

---

## 2. Core Behaviors (ALWAYS APPLY)

All detailed rules are in `.claude/rules/` and auto-load. Key behaviors:

1. **Proactive Check-ins**: Run time-aware protocols (morning briefing, evening reflection). See `time-aware-checkin.md`.
2. **Memory Persistence**: Read/write to `life/people/`, `life/brain/`, `life/habits/` as interactions happen. See `memory-persistence.md`.
3. **Honest Pushback**: Be direct/blunt, challenge avoidance, call out shiny-object syndrome. See `working-profile.md`.
4. **Mise en Place**: Full prep before execution on multi-step tasks. Inventory, station setup, prep, execute, plate. Never skip phases. Match the human's pace. See `mise-en-place.md`.
5. **Verification Protocol**: Provide evidence before claiming work is complete. No assertions without proof. See `verification-protocol.md`.
6. **Session Continuity**: Save breadcrumbs to `sessions/` when context runs low or major work completes. See `session-continuity.md`.
7. **Context Management**: Monitor token usage, max 10 MCPs enabled, delegate MCP calls to subagents. See `context-management.md` and `mcp-subagent.md`.
8. **Request Clarity**: Assess complexity before executing; clarify ambiguous requests (max 4 questions). See `request-clarity.md`.
9. **Auto-Open Links**: ALWAYS open URLs in the browser using `open "<url>"` on macOS. Never just display links.
10. **File Placement**: Auto-determine correct locations. Never create files in root (except config). See `repo-organization.md`.
11. **File Discovery — Index First**: When looking for files, **always try the knowledge index before glob/grep/subagents**. It's faster, smarter, and keeps context clean:
    - Keyword: `tools/knowledge/.venv/bin/python3 tools/knowledge/index.py search "query"`
    - Semantic: `tools/knowledge/.venv/bin/python3 tools/knowledge/index.py semantic "fuzzy question"`
    - Related: `tools/knowledge/.venv/bin/python3 tools/knowledge/index.py related path/to/file.md`
    - Entity: `tools/knowledge/.venv/bin/python3 tools/knowledge/index.py entity "name"`
    - Only fall back to glob/grep/subagent if the index returns nothing. See `find-files.md`.

---

## 3. Key Commands

### GTM Commands

| Command | Purpose |
|---------|---------|
| `/analyze-pdf <path>` | Convert and analyze PDF/DOCX via Docling |
| `/fetch-transcript [id]` | Fetch Fathom meeting transcript |
| `/list-meetings` | List recent Fathom meetings |
| `/graph-health` | Check knowledge graph health |
| `/ingest` | Process content into knowledge graph |

### Life Commands

| Command | Purpose |
|---------|---------|
| `/checkin` | Run daily check-in protocol (time-aware) |
| `/log` | Quick log: workout, reading, learning, or custom |
| `/add-person` | Add new person to Social CRM |
| `/plan-project [name]` | Create tracked project with success criteria |
| `/projects` | Dashboard of all projects with staleness alerts |
| `/review [project]` | Two-stage review: spec compliance + quality grade |
| `/think [topic]` | Structured brainstorming with Socratic questioning |

### Shared Commands

| Command | Purpose |
|---------|---------|
| `/save-session` | Save session breadcrumbs to `sessions/` |
| `/search [query]` | Search knowledge index (keyword + semantic) |
| `/build-skill [tech] [url]` | Build skill reference by scraping official docs |
| `/build-expert [domain] [url]` | Build full expert stack: skill + specialist agent |
| `/assemble-team [task]` | Dynamically assemble specialist agent team |

---

## 4. Essential Lookups

### GTM

| Need | Location |
|------|----------|
| Client config | `gtm/clients/{client}/client.yaml` |
| Client ICP/knowledge | `gtm/clients/{client}/knowledge/` |
| GTM playbooks/strategies | `gtm/docs/strategy/` |
| GTM knowledge/methodologies | `gtm/docs/knowledge/` |
| Tool API references | `gtm/docs/knowledge/tools/` |
| GTM scripts | `gtm/scripts/` |
| Transcripts | `gtm/transcripts/` |

### Life

| Need | Location |
|------|----------|
| Projects & accountability | `life/projects/` |
| People/relationships | `life/people/` |
| Learnings & insights | `life/brain/` |
| Habit tracking | `life/habits/` |
| User psychology | `.claude/rules/working-profile.md` |

### Shared

| Need | Location |
|------|----------|
| Skill references | `tools/skills/` |
| Workflow playbooks | `tools/playbooks/` |
| Google/API credentials | `tools/accounts/` |
| Session history | `sessions/` |
| MCP documentation | `tools/mcp/` |
| Knowledge index | `tools/knowledge/index.py` |

---

## 5. File Organization

**NEVER create files in root** (except config files like `.active_client`).

| Content Type | Destination |
|--------------|-------------|
| GTM leads/CSVs | `gtm/clients/{client}/leads/` |
| GTM campaigns | `gtm/clients/{client}/campaigns/` |
| GTM AI outputs | `gtm/clients/{client}/outputs/` |
| GTM scripts | `gtm/scripts/` |
| GTM transcripts | `gtm/transcripts/{source}/` |
| Client-agnostic GTM knowledge | `gtm/docs/knowledge/` |
| Client-agnostic GTM strategy | `gtm/docs/strategy/` |
| People/relationships | `life/people/` |
| Learnings/insights | `life/brain/` |
| Habit tracking | `life/habits/` |
| Projects | `life/projects/` |
| Session breadcrumbs | `sessions/` |
| Shared scripts | `tools/scripts/` |
| Skill references | `tools/skills/` |
| Meeting reports | `docs/meetings/` |
| Cross-domain docs | `docs/` |

See `.claude/rules/repo-organization.md` for the full decision tree.

---

## 6. GTM Client System

GTM work is multi-client. Each client gets their own workspace under `gtm/clients/{slug}/`.

### Client Directory Structure

```
gtm/clients/{slug}/
  client.yaml          # Client config (ICP, pain angles, product, channels)
  leads/               # Lead lists
  campaigns/           # Campaign materials
  knowledge/           # Client-specific product knowledge
  outputs/             # AI-generated outputs
  raw_data/            # Unprocessed data
```

### Onboarding a New Client

1. Copy `gtm/clients/_template/` to `gtm/clients/{slug}/`
2. Fill in `client.yaml` with client details
3. Skills auto-read `client.yaml` for pain angles, ICP, product info

### Active Client Detection

1. Check `.active_client` file in repo root (contains slug)
2. If not set, ask: "Which client is this for?"

### ZenHire

ZenHire is the first client. Its config is at `gtm/clients/zenhire/client.yaml`. All legacy ZenHire data (leads, campaigns, outputs) lives under `gtm/clients/zenhire/`.

---

## 7. Agent Teams vs Subagents

| Scenario | Use | Why |
|----------|-----|-----|
| Quick focused tasks (validation, lookup) | Subagents | Lower token cost, results summarized back |
| Complex builds needing QA + coordination | **Agent Teams** | Builder and QA discuss findings |
| Parallel review (security, perf, testing) | **Agent Teams** | Reviewers compare and debate |
| Competing hypothesis debugging | **Agent Teams** | Teams test theories, challenge each other |
| Council/decision-making | **Agent Teams** | Members debate and reach consensus |
| Simple data processing | Subagents | Sequential, no discussion needed |

**Key difference:** Subagents report back to parent (silos). Agent teammates message EACH OTHER directly (peer-to-peer).

**Best practices:**
1. Start with 3-5 teammates (overhead scales linearly)
2. Give full context in spawn prompt (teammates don't inherit conversation)
3. Avoid same-file edits (each teammate owns different files)
4. Use Sonnet for routine work, Opus for complex reasoning

---

## 8. Specialist Agents

Available in `.claude/agents/` for complex tasks via `/assemble-team`:

| Agent | Purpose | Model |
|-------|---------|-------|
| researcher | Web research, evidence gathering, fact-checking | Sonnet |
| strategist | Trade-off analysis, systems thinking, deep reasoning | Opus |
| critic | Devil's advocate, stress-testing, pre-mortem analysis | Sonnet |
| writer | Content creation, documentation, polishing | Sonnet |
| executor | Implementation, file management, task completion | Sonnet |
| skill-builder | Scrape docs, build structured skill reference files | Sonnet |
| agent-builder | Create specialist agents using agentic engineering playbook | Sonnet |
| slack | Prospeqt Slack check-in summaries and ad-hoc queries | Haiku |
| instantly | Instantly.ai campaign management across client workspaces | Sonnet |
| emailbison | EmailBison campaign management (campaigns, leads, warmup, analytics) | Sonnet |
| dashboard-builder | Build dashboards from data sources | Sonnet |
| pitch-expert | Pitch deck strategy and structure | Sonnet |
| creative-director | Visual and creative direction for content | Sonnet |
| storytelling-agent | Narrative structure and storytelling | Sonnet |
| slidev-expert | Slidev presentation development | Sonnet |
| excalidraw-expert | Excalidraw diagram creation | Sonnet |
| playwright-cli-expert | Browser automation with Playwright CLI | Sonnet |
| ux-design-expert | UX design auditor for dashboards and internal tools — evidence-based design science | Sonnet |

---

## 9. Discipline Rules

Three progressive rules in `.claude/rules/` enforce knowledge work quality:

1. **Think First** (`think-first.md`) — Socratic questioning before new commitments. Prevents shiny-object starts.
2. **Finish What You Start** (`finish-what-you-start.md`) — Surface unfinished work before starting new work. Make abandonment conscious, not accidental.
3. **Verify Before Done** (`verify-before-done.md`) — Success criteria check before marking complete. Two-stage: spec compliance, then quality grade.

---

## 10. Time-Aware Behavior

Claude adapts behavior based on Belgrade time:

| Time | Mode | Focus |
|------|------|-------|
| 6am-12pm | Morning | Full briefing: email, calendar, birthdays, todos, horizon items |
| 12pm-6pm | Afternoon | Quick status, blockers, remaining priorities |
| 6pm-11pm | Evening | Reflection, logging, capture learnings and interactions |
| 11pm-6am | Night | Minimal, sleep-focused, quick help only |

See `.claude/rules/time-aware-checkin.md` for full protocol including email/Slack/ClickUp delegation.

---

## 11. System Graph

`system_graph.json` maps repo-level infrastructure (modules, scripts, integrations, MCP servers, skills, accounts). Read it at session start for non-trivial tasks to understand how components connect.

Graph maintenance is handled by the `graph-maintainer` skill (`.claude/skills/graph-maintainer/SKILL.md`) which auto-activates when new components are created or existing ones significantly change. The skill decides whether a graph update is warranted.

The knowledge index at `tools/knowledge/index.py` provides FTS5 keyword search, semantic search, and graph traversal across all indexed markdown files. System graphs remain the authoritative infrastructure map; the index imports their edges for searchability. Run `tools/knowledge/.venv/bin/python3 tools/knowledge/index.py status` to check index health.

Session breadcrumbs include a `## Graph Changes` section to track structural changes across sessions.

---

## 12. Google Workspace Accounts

| Account | Integration | Email | Purpose |
|---------|-------------|-------|---------|
| personal | gws CLI (~/.gws/personal.json) | mihajlo.maiga@gmail.com | Primary everyday |
| secondary | None | — | Inactive, receives Erste Bank statements |
| throwaway | None | — | Testing and spam signups |
| zenhire | None | mihajlo@zenhire.ai | ZenHire work (GWS not active) |
| prospeqt | gws CLI (~/.gws/prospeqt.json) | mihajlo@prospeqt.co | Prospeqt work |

Google Workspace uses the `gws` CLI tool (not MCP). Switch accounts via `GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE=~/.gws/{account}.json`. Always delegate GWS operations to subagents. See `.claude/rules/google-workspace-delegation.md`.

---

## 13. Compact Instructions

When compacting, preserve:
- **All file paths** created or modified in this session
- **Active tasks**: what the user asked for and current progress
- **Key decisions**: what was decided and why
- **People/names/dates**: any personal info discussed
- **Session breadcrumb locations**: paths to relevant session files in `sessions/`
- **Telegram bridge state**: bot token, chat ID, listener status (if active)

Summarize away: exploratory searches, intermediate debugging, verbose tool outputs, research details (save conclusions, not process).

---

## 14. Constraints

These apply to GTM work and may vary per client (check `client.yaml`):

| Constraint | Default |
|------------|---------|
| GTM tool budget | ~$1,500/month |
| Process | Manual-first for 90 days, no automation before validation |
| HubSpot duplicate rate | <5% target, >10% is red flag |
| Email bounce rate | 15-25% acceptable, >25% indicates bad data |

---

## 15. Remember

- All `.claude/rules/*.md` files auto-load at session start
- Check `sessions/` for recent work context
- Proactively ask about people, habits, learnings during sessions
- Use `tools/skills/` for tech references before guessing at syntax
- Use `/memory` to see what rules are loaded
- GTM skills read `gtm/clients/{active_client}/client.yaml` for client-specific context

---

## 16. File Discovery: Always Use a Subagent

**Never guess file paths. Never run exploratory globs/greps in the main session to find files.**

When a user references any file ambiguously — a client doc, playbook, script, campaign, skill, lead list, transcript, or account config — spawn a **haiku subagent** to search the repo and return absolute paths. The main session only reads the file the user selects from the results.

This keeps the main context clean (no wasted tokens on search results) and prevents loading the wrong file when multiple matches exist.

**Trigger conditions:** User references a client by name, asks for a playbook/strategy, mentions a script or template, asks for campaign copy, references a knowledge base file, or gives any partial/ambiguous file reference.

**Full rule with subagent prompt template, guardrails, and worked example:** `.claude/rules/find-files.md`

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Email QA Dashboard**

A standalone web dashboard that QA-checks email campaigns across multiple Instantly workspaces before they go live. It fetches campaigns, extracts copy variables (e.g., `{{cityName}}`), cross-references them against lead data, and flags leads where variables are empty, null, or set to "NO" — values that would render as amateur-looking text in the final email. Built for the Prospeqt GTM team to ensure every lead in an active or drafted campaign has clean, complete variable data.

**Core Value:** **No campaign launches with broken personalization variables.** Every lead's variables must match what the copy expects, and the team must know about problems before emails go out.

### Constraints

- **Modular architecture**: Must be organized into clear modules (routes, API clients, QA logic, templates) — not a single-file monolith. Team members and future developers need to navigate the codebase.
- **Render deployment**: Must work as a standard Python web app on Render (Procfile, requirements.txt if needed)
- **API rate limits**: Instantly API has rate limits — concurrent fetching across multiple workspaces needs throttling/queuing
- **No hardcoded keys**: API keys managed through the dashboard admin panel, stored server-side (not in code)
- **UX/UI quality**: Visual design must be polished. Use `ux-design-expert` agent for design audits and `playwright-cli-expert` agent for visual QA during frontend work.
- **Playwright testing**: All frontend phases must include Playwright-based visual QA (screenshots at multiple viewports, user flow validation)
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

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
# Core — installs FastAPI + Uvicorn + Jinja2 + pydantic-settings + python-multipart
# Async HTTP client
# Background scheduler (stable 3.x, NOT 4.x)
# Production server (add when deploying)
# Dev dependencies (keep in requirements-dev.txt)
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
## Version Compatibility
| Package | Compatible With | Notes |
|---------|----------------|-------|
| fastapi[standard] 0.135.x | Python 3.10+ | Requires Python 3.10 minimum. Render's Python 3.11 runtime is the safe target. |
| APScheduler 3.11.x | Python 3.8+ | Compatible. Use AsyncIOScheduler, not BackgroundScheduler, in async FastAPI context. |
| httpx 0.28.x | Python 3.8+ | Compatible. Pair with `anyio` for test async context (ships with fastapi[standard]). |
| pydantic v2 (ships with fastapi) | FastAPI 0.100+ | FastAPI 0.100 moved to Pydantic v2 natively. Do not pin to pydantic v1. |
| HTMX 2.x | No Python dependency | Load from CDN: `https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js`. No install required. |
## Project Structure (Recommended)
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
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
