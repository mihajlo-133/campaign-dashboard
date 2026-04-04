# Feature Research

**Domain:** Email campaign personalization QA / variable validation dashboard
**Researched:** 2026-04-04
**Confidence:** HIGH (core QA/validation features), MEDIUM (alerting/analytics patterns)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Variable extraction from campaign copy | Core purpose — detect `{{variableName}}` patterns in sequences | LOW | Regex over sequence step bodies; Instantly sequences stored as step arrays |
| Lead variable completeness check | Core purpose — flag leads where copy-referenced variables are empty, null, or "NO" | MEDIUM | Must cross-ref campaign variables against per-lead `custom_variables` object |
| Campaign-level issue summary | Users need "which campaigns have problems and how many" at a glance | LOW | Aggregate count of broken leads per campaign |
| Workspace-level rollup | Multiple workspaces managed centrally; users need "is workspace X clean?" | LOW | Roll up campaign summaries per API key / workspace |
| All-workspaces overview | Top-level entry point — "any issues anywhere right now?" | LOW | Roll up workspace summaries |
| Active/draft campaign filter | Completed/paused campaigns are irrelevant for pre-send QA | LOW | Instantly API v2 supports campaign status filter enum |
| Active lead filter | Bounced/unsubscribed leads are irrelevant; only active leads need clean variables | MEDIUM | `lt_interest_status` field on lead object encodes status; filter logic non-trivial |
| Per-variable breakdown | "Which variable is broken for how many leads in this campaign?" | LOW | Group flagged leads by which variable is missing |
| Manual "run check" trigger | Users want to force a refresh on demand, not wait for polling | LOW | Button at workspace and campaign level |
| Background polling / auto-refresh | Dashboard should stay current without manual action | MEDIUM | Background thread with configurable interval |
| Admin panel for workspace management | Add/remove API keys without code changes | MEDIUM | Password-protected; store keys server-side not in code |
| Open viewing (no login for QA results) | Low-friction access for the full team to check status | LOW | Admin actions are gated; read views are open |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Drill-down from workspace → campaign → lead list | See exactly which leads need fixing without leaving the dashboard | MEDIUM | Three-level navigation; lead list view shows email + which variable is broken |
| "Last checked" timestamp per campaign | Confirms freshness — users know whether the data is stale | LOW | Store check timestamp alongside cached results |
| Issue severity classification | Distinguish 1 broken lead vs 500 broken leads; help prioritize effort | LOW | Count-based: flag campaigns with >N broken leads differently |
| Variable discovery (what variables does this campaign actually use?) | Shows team the full variable inventory per campaign — useful for onboarding | LOW | Byproduct of the extraction step; display alongside issue count |
| Slack alert on QA failure | Proactive notification — team doesn't have to remember to check the dashboard | MEDIUM | Webhook post when new issues are detected on poll; configurable threshold |
| Exportable issue report (CSV) | Hand off a clean list of lead emails + broken variables to whoever fixes the data | LOW | Filter flagged leads → CSV download |
| "NO" value detection as well as null/empty | Instantly uses literal "NO" as a placeholder for missing data from enrichment tools | LOW | This is the core insight from the PROJECT.md — most QA tools miss this |
| Multi-workspace isolation | Each workspace's data is scoped to its API key — no cross-contamination | LOW | Important for agency context where each workspace = one client |
| Configurable poll interval per workspace | High-priority clients can be checked more frequently | LOW | Admin panel config value |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Write-back to Instantly (edit lead variables from dashboard) | "Wouldn't it be great to fix leads directly?" | Scope explosion, bidirectional API complexity, risk of corrupting live campaign data, auth surface area triples | View-only MVP — export a CSV of broken leads, fix them in the source and re-upload |
| User accounts / individual logins | Multi-person team, audit trail | Massive complexity for a small team; JWT, password hashing, session management, password reset flows | Single admin password for config, open read access for viewing. Simple and sufficient for a 2-4 person team. |
| Bulk campaign actions (pause, archive, move) | "Since you can see everything, let me act on it too" | Turns a read-only QA tool into a campaign management tool — different product, different risk surface | Dedicated Instantly UI for campaign actions |
| Real-time variable validation (pre-upload) | "Check my CSV before I upload it to Instantly" | Upload-time validation is a different product surface, not a dashboard | The dashboard validates what's already in Instantly; use a separate CSV linter for pre-upload |
| Email deliverability metrics (open rate, bounce rate) | Dashboard is visible, might as well add more data | Scope and purpose drift; the Prospeqt outreach dashboard already handles deliverability metrics | Keep this dashboard focused on one thing: variable completeness before send |
| Historical QA run logs (all runs, diffs between runs) | "Show me when issues were introduced" | Storage, indexing, diff logic — significant complexity for low daily value | Last-check timestamp + current state is sufficient; Slack alert captures when issues first appeared |
| EmailBison / Smartlead integration in v1 | "We use multiple platforms" | API shape is different; variable syntax may differ; doubles scope | Instantly-only for v1. Validate the concept, then extend. |
| Automatic lead fixing (AI-powered enrichment) | "If you know it's broken, just fix it" | Enrichment quality, cost, responsibility — this is a separate enrichment product | Flag the issue; let the team decide what data is correct |

---

## Feature Dependencies

```
[All-workspaces overview]
    └──requires──> [Workspace-level rollup]
                       └──requires──> [Campaign-level issue summary]
                                          └──requires──> [Variable extraction from copy]
                                          └──requires──> [Lead variable completeness check]
                                                             └──requires──> [Active lead filter]

[Drill-down workspace → campaign → lead list]
    └──requires──> [Campaign-level issue summary]
    └──requires──> [Per-variable breakdown]

[Manual "run check" trigger]
    └──requires──> [Background polling / auto-refresh] (shares the same check function)

[Slack alert on QA failure]
    └──requires──> [Background polling / auto-refresh]
    └──enhances──> [Issue severity classification]

[Exportable issue report (CSV)]
    └──requires──> [Per-variable breakdown]
    └──requires──> [Drill-down to lead list]

[Configurable poll interval per workspace]
    └──requires──> [Admin panel for workspace management]

["Last checked" timestamp per campaign]
    └──requires──> [Background polling / auto-refresh]

["NO" value detection]
    └──enhances──> [Lead variable completeness check] (adds a third failure condition alongside empty/null)
```

### Dependency Notes

- **Campaign-level issue summary requires both extraction and completeness check:** The summary is meaningless without first knowing what variables the copy expects AND what each lead's variables contain.
- **Slack alert requires polling:** Alerts fire on the polling loop when a clean campaign becomes broken — not on manual checks. Manual checks are for human review.
- **Active lead filter requires care:** Instantly's `lt_interest_status` int encodes many states. Must map correctly to "active" vs excluded. This is the most likely place for subtle bugs — worth explicit test coverage.
- **Write-back conflicts with open viewing:** If write-back were added, open access would become a security hole. Keeping the tool read-only preserves the simple access model.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept.

- [ ] Variable extraction from campaign copy — foundational; nothing else works without it
- [ ] Lead variable completeness check (empty, null, "NO" detection) — the core QA function
- [ ] Active/draft campaign filter — avoid noise from irrelevant campaigns
- [ ] Active lead filter — avoid noise from excluded leads
- [ ] Campaign-level issue summary (broken lead count per variable) — actionable view
- [ ] Workspace-level rollup — agency context requires multi-workspace view
- [ ] All-workspaces overview — entry point for the team
- [ ] Manual "run check" trigger — lets users force a refresh on demand
- [ ] Background polling with configurable interval — keeps data fresh automatically
- [ ] Admin panel for workspace API key management (password-protected) — without this, workspaces are hardcoded
- [ ] Open viewing, admin-gated configuration — the correct access model for this team
- [ ] "Last checked" timestamp per campaign — confirms data freshness

### Add After Validation (v1.x)

Features to add once core is working and team is using it daily.

- [ ] Drill-down to per-lead issue list with export CSV — trigger: team reports they find the campaign summary useful but need to know which leads specifically
- [ ] Slack webhook alert on new QA failures — trigger: team reports they're not checking the dashboard proactively
- [ ] Issue severity classification (highlight campaigns with >N broken leads) — trigger: workspace volume grows, visual priority triage needed
- [ ] Configurable poll interval per workspace — trigger: some workspaces are higher priority than others

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] EmailBison / Smartlead integration — trigger: Instantly is no longer the only platform in use
- [ ] Historical QA run log / diff between runs — trigger: team wants to track data quality over time
- [ ] Variable discovery view (full variable inventory per campaign) — nice to have; low urgency
- [ ] White-label / multi-team support — trigger: tool gets used by more than one agency

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Variable extraction from copy | HIGH | LOW | P1 |
| Lead completeness check (empty/null/"NO") | HIGH | MEDIUM | P1 |
| Campaign-level issue summary | HIGH | LOW | P1 |
| Workspace rollup + all-workspaces view | HIGH | LOW | P1 |
| Active campaign / active lead filter | HIGH | MEDIUM | P1 |
| Manual run check trigger | MEDIUM | LOW | P1 |
| Background polling | MEDIUM | MEDIUM | P1 |
| Admin panel (workspace management) | HIGH | MEDIUM | P1 |
| "Last checked" timestamp | MEDIUM | LOW | P1 |
| Drill-down to per-lead issue list | HIGH | MEDIUM | P2 |
| CSV export of broken leads | MEDIUM | LOW | P2 |
| Slack webhook alert | MEDIUM | MEDIUM | P2 |
| Severity classification | LOW | LOW | P2 |
| Configurable poll interval | LOW | LOW | P2 |
| Variable discovery view | LOW | LOW | P3 |
| Historical QA log | LOW | HIGH | P3 |
| EmailBison integration | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

No direct competitors exist as standalone tools. Closest analogues:

| Feature | Instantly built-in | Litmus / Email QA tools | Our Approach |
|---------|-------------------|-------------------------|--------------|
| Variable validation | Preview mode (manual, per-lead) | Marketing email render preview — no cold email personalization | Automated bulk check across all leads in all active campaigns |
| Missing field detection | None (fallback values soften the problem but don't flag it) | Generic "merge tag" warnings for marketing templates | Explicit "NO" detection + null/empty; cross-ref against actual copy variables |
| Multi-workspace view | Separate workspace logins required | Single account | Unified API-key-per-workspace model with cross-workspace rollup |
| Lead data quality dashboard | None | HubSpot Data Quality Command Center (CRM-level) | Campaign-scoped: only checks leads in campaigns, only checks variables used in copy |
| Alerting | None native for variable issues | Post-send error reports | Pre-send proactive alerting via Slack webhook |
| Admin access control | Full workspace login | Role-based user management | Simple admin password for config, open read for viewing |

**Key differentiator vs Instantly built-in:** Instantly's preview mode is per-lead and manual. Our tool checks every active lead in bulk automatically and presents a summary requiring zero per-lead inspection.

**Key differentiator vs marketing QA tools (Litmus):** Those tools check rendering and marketing email syntax — they don't understand cold email `{{variableName}}` patterns from Instantly, don't understand the "NO" sentinel value pattern, and don't work against Instantly API data.

---

## Sources

- [Instantly.ai Blog: Cold Email Subject Line Checklist: Pre-Send QA for Sales Teams](https://instantly.ai/blog/cold-email-subject-line-checklist-pre-send-qa-for-sales-teams/) — confirms "broken variables" as a known problem
- [Instantly.ai Blog: AI-Powered Cold Email Personalization](https://instantly.ai/blog/ai-powered-cold-email-personalization-safe-patterns-prompt-examples-workflow-for-founders/) — confirms variable syntax, fallback values, manual preview workflow
- [Instantly API v2: Add leads in bulk](https://developer.instantly.ai/api/v2/lead/bulkaddleads) — confirmed `custom_variables` object structure (string/number/boolean/null values)
- [Instantly API v2: List campaigns](https://developer.instantly.ai/api/v2/campaign/listcampaign) — confirms campaign status enum filter
- [DQOps: Configuring Slack notifications for data quality](https://dqops.com/docs/integrations/slack/configuring-slack-notifications/) — Slack webhook pattern for data quality alerting
- [Litmus: Email Testing and QA](https://www.litmus.com/blog/email-testing-and-qa) — marketing email QA scope comparison
- PROJECT.md: confirmed "NO" sentinel value as third failure condition alongside empty/null

---

*Feature research for: Email QA Dashboard — Instantly.ai campaign personalization variable validation*
*Researched: 2026-04-04*
