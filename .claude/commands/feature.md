# /feature Command

Orchestrate a dashboard feature from intake to ship. Guides through 5 phases: intake, spec, build, QA, ship.

**Usage:** `/feature [description]`

## Instructions

### Phase 1 — INTAKE (main session)

1. **Read context:**
   - Read relevant sections of `gtm/prospeqt-outreach-dashboard/server.py`
   - Read the template file(s) likely affected
   - Check `gtm/prospeqt-outreach-dashboard/docs/BACKLOG.md` for related items

2. **Clarify with 2-3 questions:**
   - What problem does this solve for the AE (account executive)?
   - What does "done" look like? (specific, testable criteria)
   - Any constraints? (e.g., must not change existing card layout)

3. **Write feature brief:**
   ```
   ## Feature: [Name]
   **Problem:** [What AE pain this solves]
   **Solution:** [How it works]
   **Success criteria:**
   - [ ] [Criterion 1 — specific, verifiable]
   - [ ] [Criterion 2]
   **Affected files:** [server.py sections, template files]
   **Size:** Small / Medium / Large
   ```

4. **Present to user for approval.** Do not proceed until approved.

### Phase 2 — SPEC (size-gated)

Determine size based on these criteria:

| Size | Criteria | Action |
|------|----------|--------|
| **Small** | 1-2 server.py sections, <50 lines, no new endpoints, no schema change | Write implementation notes inline. Skip spec agents. Go to Phase 3. |
| **Medium** | 3+ sections, schema changes, new UI component | Spawn spec team (see below) |
| **Large** | New page, new API integration, architecture change | Spawn spec team + require explicit user review of spec |

**User override:** If user says "skip spec" or "just build it" — go straight to Phase 3.

**Spawning the spec team:**

Use agent team (peer-to-peer, NOT subagents):
- `prospeqt-spec-architect` — reads code, writes spec to `docs/specs/{feature-name}.md`
- `prospeqt-spec-reviewer` — verifies spec against actual code, challenges gaps

Wait for them to converge. Present approved spec to user for final sign-off (Large features only).

### Phase 3 — BUILD

Spawn the build team (peer-to-peer agent team, NOT subagents):
- `prospeqt-dashboard-builder` — implements in server.py + templates + tests
- `prospeqt-dashboard-reviewer` — reviews against spec, checks mobile/errors/stdlib/tests

Provide them with:
- The approved spec (or inline brief for Small features)
- The specific success criteria from Phase 1
- Any user feedback from Phase 2

Wait for them to converge and report completion.

### Phase 4 — QA

1. **Run tests:**
   ```bash
   cd gtm/prospeqt-outreach-dashboard && python -m pytest tests/ -v
   ```
   - All tests must pass
   - If failures: read output, fix, re-run
   - **3 strikes rule:** If 3 fix attempts fail, escalate to user

2. **Take screenshots:**
   ```bash
   cd gtm/prospeqt-outreach-dashboard && make qa
   ```
   This starts the mock server and captures Playwright screenshots at 3 viewports:
   - Desktop: 1440×900
   - Tablet: 768×1024
   - Mobile: 375×812

3. **Present screenshots to user** at all 3 viewports

4. **If user flags issues:** Fix inline, re-screenshot, re-present

### Phase 5 — SHIP

1. **Summarize all changes:**
   - Files modified and why
   - New tests added
   - Any decisions made during build

2. **Show final screenshots** at all 3 viewports

3. **User approves → commit:**
   - Descriptive commit message referencing the feature
   - Push to remote

## Notes

- The `/feature` command is the standard entry point for all dashboard work
- Small features skip Phase 2 entirely — intake → build → QA → ship
- Always check BACKLOG.md — the feature might already be described there
- If the feature touches classification logic (`_classify_client`), flag it as high-risk and add extra test coverage
