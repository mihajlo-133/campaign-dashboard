# Email QA Dashboard

## What This Is

A standalone web dashboard that QA-checks email campaigns across multiple Instantly workspaces before they go live. It fetches campaigns, extracts copy variables (e.g., `{{cityName}}`), cross-references them against lead data, and flags leads where variables are empty, null, or set to "NO" — values that would render as amateur-looking text in the final email. Built for the Prospeqt GTM team to ensure every lead in an active or drafted campaign has clean, complete variable data.

## Core Value

**No campaign launches with broken personalization variables.** Every lead's variables must match what the copy expects, and the team must know about problems before emails go out.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Fetch all campaigns from configured Instantly workspaces via API
- [ ] Filter campaigns by status (active, drafted) — ignore completed/paused
- [ ] Extract all copy/sequence text from filtered campaigns
- [ ] Parse `{{variableName}}` patterns from campaign copy
- [ ] Fetch all leads from filtered campaigns
- [ ] Filter to active leads only (exclude unsubscribed, bounced, etc.)
- [ ] Fetch all custom variables for active leads
- [ ] Match lead variables against copy variables — identify which lead fields correspond to which copy placeholders
- [ ] Flag leads where a copy-referenced variable is empty, null, or "NO"
- [ ] Display QA results at three levels: all workspaces, per workspace, per campaign
- [ ] Show issue summary: count of broken leads per variable per campaign
- [ ] Admin panel to add/remove Instantly workspaces by API key (password-protected)
- [ ] Open access for viewing QA results (no login required)
- [ ] Background polling to discover new campaigns periodically
- [ ] Manual "run check" trigger at all/workspace/campaign level

### Out of Scope

- Writing back to Instantly (editing lead variables, removing leads) — MVP is view-only
- Slack notifications on QA failures — future goal, not v1
- Bulk actions on campaigns from the dashboard — future
- EmailBison integration — Instantly only for v1
- User accounts/individual logins — simple admin password is sufficient

## Context

- **Existing infra**: 6 Instantly workspaces with API keys stored in `tools/accounts/{client}/instantly.md` (enavra, heyreach-client, kayse, myplace, smartmatchapp, swishfunding)
- **Existing dashboard**: The Prospeqt outreach dashboard (`gtm/prospeqt-outreach-dashboard/`) uses a single-file stdlib-only pattern. This project deliberately chooses a modular architecture for maintainability and extensibility.
- **Deployment target**: GitHub repo → Render (or similar), accessible to team via URL
- **Instantly API**: v2 REST API, authentication via API key. Rate limits apply.
- **Variable format**: Instantly uses `{{variableName}}` syntax in campaign copy. Also uses `{{RANDOM | opt1 | opt2}}` spin syntax (exclude from QA). `{{accountSignature}}` is a system variable (exclude from QA).
- **API data shapes (verified live 2026-04-04)**:
  - Campaign statuses: `0`=draft, `1`=active, `2`=paused, `3`=completed
  - Lead statuses: `1`=active, `3`=contacted/completed, `-1`=bounced/error
  - Sequence copy is inline: `campaign.sequences[].steps[].variants[].body` and `.subject`
  - Lead variables are in `lead.payload` dict (not a separate field)
  - Leads endpoint: POST `/api/v2/leads/list` with cursor pagination
  - Campaigns endpoint: GET `/api/v2/campaigns`
- **Team size**: Small Prospeqt GTM team (2-4 people)
- **User profile**: GTM engineers managing multiple clients, pushing hundreds/thousands of leads into campaigns. They need to quickly verify variable completeness at scale — speed and clarity in the UI are critical.
- **Visual design priority**: UX/UI quality is a first-class concern, not an afterthought. The dashboard must feel polished and professional — luxury aesthetic, clear data hierarchy, scannable at a glance.
- **Frontend QA**: Playwright CLI is available for visual regression testing and user flow validation. Use it during frontend phases.
- **UX expert agent**: The `ux-design-expert` agent should be utilized during frontend/UI phases for evidence-based design review.
- **Future direction**: Background monitoring with Slack alerts when issues detected, bulk campaign actions, possibly more email platforms

## Constraints

- **Modular architecture**: Must be organized into clear modules (routes, API clients, QA logic, templates) — not a single-file monolith. Team members and future developers need to navigate the codebase.
- **Render deployment**: Must work as a standard Python web app on Render (Procfile, requirements.txt if needed)
- **API rate limits**: Instantly API has rate limits — concurrent fetching across multiple workspaces needs throttling/queuing
- **No hardcoded keys**: API keys managed through the dashboard admin panel, stored server-side (not in code)
- **UX/UI quality**: Visual design must be polished. Use `ux-design-expert` agent for design audits and `playwright-cli-expert` agent for visual QA during frontend work.
- **Playwright testing**: All frontend phases must include Playwright-based visual QA (screenshots at multiple viewports, user flow validation)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Standalone project (not added to outreach dashboard) | Different purpose, different architecture needs, cleaner separation | -- Pending |
| Modular architecture over single-file | Extensibility for Slack, bulk actions, new platforms; navigability for team | -- Pending |
| Open viewing + admin-only workspace management | Low friction for QA checks, controlled access for configuration | -- Pending |
| View-only MVP (no write-back to Instantly) | Reduce risk, ship faster, validate the QA concept first | -- Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-04 — Phase 3 (Dashboard Views) complete. Full drill-down navigation: all-workspaces overview → workspace detail → campaign detail with per-variable breakdown and broken leads table. BrokenLeadDetail model, 3 new routes, 3 templates, HTMX pagination. 104 tests passing.*
