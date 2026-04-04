# Pitfalls Research

**Domain:** Email QA Dashboard — Multi-workspace API integration, template variable parsing, background task management
**Researched:** 2026-04-04
**Confidence:** HIGH (API specifics from official docs + MEDIUM for background task patterns from community sources)

---

## Critical Pitfalls

### Pitfall 1: Rate Limit Collapse When Fetching All Workspaces Concurrently

**What goes wrong:**
The Instantly API v2 enforces a **workspace-scoped** rate limit of 100 req/sec and 6,000 req/min. The key insight: this limit is per workspace (API key), not global. With 6 workspaces each running concurrent requests, you could hit 600 req/sec combined — and if multiple clients share one Instantly org, the limit collapses to a single workspace budget. A ThreadPoolExecutor with no per-workspace throttle hammers every workspace simultaneously at startup or on a "run check all" trigger, causing cascading 429s that look like data fetch failures rather than rate limit issues.

**Why it happens:**
Developers treat concurrent fetching as "each workspace gets its own pool" and forget that QA scans require multiple sequential API calls per workspace: list campaigns → list sequence steps → list leads (paginated) → fetch lead variables. A single workspace QA scan for 3 campaigns with 500 leads each = 30+ API calls. 6 workspaces × 30 calls = 180 calls fired simultaneously on a "run all" trigger.

**How to avoid:**
- Introduce per-workspace semaphores (`asyncio.Semaphore` or a `threading.Semaphore`) to cap concurrent requests at 5-10 per workspace.
- Add a 100ms sleep between paginated pages (the existing outreach dashboard does this — keep the pattern).
- On "run all" trigger, stagger workspace fetches rather than firing all at once: chunk workspaces into groups of 2-3, add 500ms delay between groups.
- Cache the workspace-level campaign+copy data separately from the lead-level data. Copy rarely changes; leads do. Don't re-fetch copy on every QA run.
- Respect `Retry-After` headers on 429 responses — exponential backoff with jitter, not fixed sleep.

**Warning signs:**
- QA results show partial data (some workspaces populated, others empty) on "run all"
- 429 errors appear in logs within 2-3 seconds of triggering a full scan
- Fetch time spikes from ~5s to 60s+ on concurrent runs

**Phase to address:** Phase 1 (API integration foundation) — design the throttling layer before building the QA logic on top.

---

### Pitfall 2: Variable Name Case-Sensitivity and Normalization Mismatch

**What goes wrong:**
The Instantly API returns lead custom variables as a JSON object where the key is the variable name exactly as entered when uploading leads. Campaign copy uses `{{variableName}}` syntax. These two sources are not guaranteed to match in case: a lead uploaded with key `cityname` won't be flagged as missing when the copy uses `{{cityName}}`. Worse, the same variable may be spelled `{{City_Name}}` in one campaign and `{{cityName}}` in another, creating false negatives — the QA system reports clean when data is actually broken.

**Why it happens:**
Lead data and campaign copy are authored independently. Sales ops uploads leads with one casing; copywriters use another. Instantly itself does not enforce variable name consistency.

**How to avoid:**
- Normalize all variable names to lowercase for comparison (both parsed from copy and fetched from lead data). Store the canonical → original mapping for display purposes.
- At parse time, build a `variable_index`: `{ "cityname": ["{{cityName}}", "{{CityName}}"] }` showing all copy variants that resolve to the same normalized key.
- Flag campaigns where the same semantic variable has multiple spellings across steps — this is a data hygiene issue to surface to the team, not just a lead-level issue.
- Test the regex against Instantly's actual copy format: `{{variableName}}` with optional whitespace inside braces (`{{ variableName }}` appears in some templates).

**Warning signs:**
- QA shows 0 issues on a campaign you know has bad data
- Different campaigns for the same workspace show different variable names for what appears to be the same field
- Manual spot-check of a lead shows a field the QA dashboard missed

**Phase to address:** Phase 2 (variable parsing engine) — the normalization logic must be defined before the cross-reference logic is built.

---

### Pitfall 3: Fetching Leads Without Filtering Status Correctly

**What goes wrong:**
The Instantly API `/leads/list` endpoint returns all leads including bounced, unsubscribed, and completed leads. Without proper status filtering, the QA dashboard flags issues on leads that will never receive an email — creating noise that erodes trust in the tool. More critically, you may miss active leads who have bad data because the lead count appears large but is dominated by non-active leads.

**Why it happens:**
The lead status codes in Instantly v2 are not named intuitively. "Active" is not a single status value — it's the absence of terminal statuses. Developers fetch all leads and assume they can filter client-side, but with large campaigns (10k+ leads), fetching all pages just to discard 80% is extremely slow and burns API quota.

**How to avoid:**
- Filter by status server-side at fetch time using the `status` filter parameter. Based on Instantly v2 docs, use `interest_status` and lead status filters rather than fetching all and filtering.
- Explicitly exclude statuses: bounced, unsubscribed, completed (sent all steps), invalid email.
- Document the exact Instantly status codes used, as they can change across API versions. Add a constant or config file mapping status names to API codes so changes are localized.
- When status codes are ambiguous, fetch a small sample (10 leads), inspect the raw `status` field values, and document what was observed.

**Warning signs:**
- Lead counts seem much larger than expected for "active" campaigns
- QA runs take 3-5x longer than expected
- Users report "these leads already replied — why are they flagged?"

**Phase to address:** Phase 1 (API integration) — status filtering must be in the leads fetcher from the start. Retrofitting filters into paginated fetchers is painful.

---

### Pitfall 4: Campaign Copy Lives Inside Sequence Steps, Not at Campaign Level

**What goes wrong:**
The Instantly API campaign object does not include copy (subject, body) in the campaigns list endpoint response. Campaign copy is nested inside sequence steps, and sequences have variants. Fetching campaign copy requires a separate API call per campaign (get campaign detail → sequences → steps → variants). Developers who paginate the campaign list and assume the list response includes body text will find no variables to parse and ship a QA tool that silently reports 0 issues.

**Why it happens:**
The campaign list endpoint is optimized for listing (name, status, metrics) — not for reading copy. The API design separates campaign metadata from sequence content. This is consistent with REST patterns but surprises developers expecting copy in the list response.

**How to avoid:**
- After fetching the campaign list, make a separate `GET /campaigns/{id}` call for each active/draft campaign to retrieve sequence data.
- Parse variables from all fields: `sequences[0].steps[].variants[].subject` AND `sequences[0].steps[].variants[].body`. Subject lines also use `{{variables}}`.
- Cache the copy-level data aggressively (15-30 min TTL) since copy changes rarely. Use the campaign's `updated_at` timestamp to invalidate cache selectively.
- Account for A/B variants: each step can have multiple variants with different body text. Parse variables from all variants, union them.

**Warning signs:**
- Parsed variable list is empty for campaigns you know are personalized
- Subject line variables are missed but body variables are caught (parsing only body)
- QA runs seem fast (suspiciously fast = not making the right API calls)

**Phase to address:** Phase 1 (API integration) — requires understanding the API response shape before building the parser.

---

### Pitfall 5: Background Refresh Thread Silently Dying

**What goes wrong:**
A background polling thread that refreshes workspace data every N minutes can silently die if it encounters an unhandled exception. Python's `threading.Thread` does not propagate exceptions to the main thread — the thread terminates, the dashboard continues serving stale cached data, and no one notices until a user wonders why the data hasn't updated in hours.

**Why it happens:**
The pattern `thread.daemon = True; thread.start()` is simple and widely used. But daemon threads die on any unhandled exception. If a single API call raises an unexpected error shape (e.g., Instantly returns HTML instead of JSON during an outage), the exception propagates up, kills the thread, and takes the entire refresh loop with it.

**How to avoid:**
- Wrap the entire background loop body in a `try/except Exception` with a catch-all that logs the error and `continues` the loop rather than re-raising.
- Add a "last successful refresh" timestamp to the cached data. Serve a banner or visual indicator when data is more than 2× the TTL old.
- Add a health check endpoint (`/health`) that reports last refresh time for each workspace. Render can ping this and alert.
- Use `threading.excepthook` (Python 3.8+) to capture thread exceptions globally and log them.
- Test thread death explicitly: inject a malformed API response into one workspace's fetcher and verify the other workspaces keep refreshing.

**Warning signs:**
- Data "freezes" — all timestamps show the same time hours ago
- No error logs despite data staleness
- Dashboard appears healthy (no errors shown) but data is old

**Phase to address:** Phase 2 (background task architecture) — thread resilience must be designed in, not added as a patch.

---

### Pitfall 6: API Keys Stored in Plain Text Without Access Control

**What goes wrong:**
The admin panel accepts API keys and stores them server-side. If keys are stored in a plain JSON file without filesystem restrictions, or if the admin panel is accessible without authentication due to a middleware bug, all 6 client API keys are exposed. A misconfigured Render deployment (public git repo, leaked config) leaks all client Instantly workspaces to anyone with the URL.

**Why it happens:**
Password-protecting the admin panel is implemented, but the password check is done at the route handler level. If the request doesn't hit the expected handler (e.g., direct file path access, misconfigured routing), the check is bypassed. Also, the API key file is often accessible via the same HTTP server process if the file path is under the web root.

**How to avoid:**
- Store API keys in environment variables on Render, not in a JSON file on disk. The admin panel updates Render environment variables via the Render API, not local files.
- If disk storage is used (simpler for MVP), ensure the storage file is outside the web-accessible directory and the HTTP handler explicitly rejects direct file requests.
- The admin password must be hashed (bcrypt or at minimum HMAC-SHA256) — never compared as plaintext.
- Never expose the raw API key in admin panel responses (show last 4 chars only, like credit cards).
- Add a test: verify that unauthenticated requests to `/admin/*` routes return 401 or redirect to login. This must be a CI check.

**Warning signs:**
- Admin routes accessible without the password in testing
- API keys visible in browser developer tools network tab
- Config file committed to git by accident

**Phase to address:** Phase 1 (admin panel + auth foundation) — security must not be deferred to a later phase.

---

### Pitfall 7: Large Lead Counts Making QA Runs Timeout

**What goes wrong:**
A campaign with 50,000 leads requires 500 paginated API calls (at 100 leads per page) just to fetch the lead list, plus one variable validation per lead. At 100ms per API call, that is 50 seconds of blocking I/O for a single campaign. With a web request timeout of 30 seconds (Render default), a "run QA" button triggers a timeout before results return. Users assume the tool is broken.

**Why it happens:**
The QA run is triggered synchronously in the request handler. The handler doesn't return until the QA is complete. Small campaigns during development (100-500 leads) feel fast. Production campaigns are 10-100× larger.

**How to avoid:**
- Never run QA synchronously in the HTTP request handler. Use the fire-and-forget pattern: handler starts a background job, returns immediately with `{ "status": "running", "job_id": "..." }`. Frontend polls `/status/{job_id}` until complete.
- Store QA results in the cache keyed by workspace+campaign+timestamp. The "run check" button triggers a cache refresh, not a blocking fetch.
- For the initial MVP, make the "run check" trigger a background refresh and show the user the last-computed results with a "refreshing..." indicator. This is simpler than a full job queue.
- Set an explicit per-workspace lead fetch budget (e.g., max 10,000 leads per campaign for QA). Display a warning if a campaign exceeds this and only QA the first N leads.

**Warning signs:**
- "Run check" button works in dev but hangs in production
- Render logs show `H12 - Request timeout` errors
- Users refresh the page thinking it crashed

**Phase to address:** Phase 2 (QA execution engine) — the async/background job pattern must be established before QA runs are wired to the UI.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Parse variables with a simple regex `\{\{(\w+)\}\}` | Fast to implement | Misses variables with spaces, nested paths, special chars in Instantly templates | MVP only — upgrade in Phase 2 |
| Store API keys in a local JSON file | No Render API integration needed | File lost on Render redeploy (ephemeral filesystem), keys must be re-entered | Never — use env vars from day one |
| Fetch all leads regardless of status and filter client-side | Simpler fetch code | Burns API quota, slow for large campaigns | Never — filter server-side |
| Single global background refresh (all workspaces together) | One thread to manage | One slow workspace blocks all others; rate limits compound | MVP only — replace with per-workspace refresh scheduling |
| Synchronous QA run triggered by HTTP request | Simplest code path | Times out on large campaigns in production | Never — async from the start |
| Cache QA results indefinitely until manual refresh | Avoids re-fetching | Stale data masks newly-introduced variable issues | Never — add TTL even if generous (2-4 hours) |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Instantly v2 API | Using API v1 endpoints (deprecated Jan 2026) | All calls must use `/api/v2/` base. v1 endpoints return 410 or redirect. |
| Instantly leads endpoint | GET request to list leads | List leads is a POST endpoint in v2 — a REST deviation due to complex filter parameters |
| Instantly campaign copy | Assuming copy is in the campaign list response | Copy lives in sequence steps; requires a separate GET per campaign |
| Instantly pagination | Using `page` / `offset` parameters | v2 uses cursor-based pagination via `next_starting_after` field from previous response |
| Instantly lead variables | Assuming flat key-value in lead response | Custom variables are nested in a `variables` or `custom_variables` sub-object; field name must be verified against real API response |
| Instantly rate limit | Treating limit as per-key | Limit is per workspace, shared across all API keys for that workspace |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching all leads to count active ones | Slow QA runs; API quota exhaustion | Use status filter at API level, not client-side | At 5,000+ leads per campaign |
| Per-lead API calls to fetch variables | 1 API call per lead = catastrophic | Fetch variables in bulk within the lead list endpoint (check if `include_variables` param exists) | At 100+ leads |
| Re-fetching campaign copy on every QA run | 6 workspaces × N campaigns × 2 API calls = dozens of calls per refresh | Cache copy with long TTL (30 min), invalidate only on `updated_at` change | At 3+ workspaces with 5+ campaigns each |
| Parsing variables from HTML-encoded email body | Misses variables wrapped in `&lt;` encoding | Decode HTML entities before regex parsing | Any campaign with HTML formatting |
| Storing QA results in memory only | Results lost on server restart or Render redeploy | Write QA results to disk or return as on-demand computation | First Render restart in production |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing API keys as plaintext in a JSON config file committed to git | All client Instantly workspaces compromised | Use Render environment variables; add `*.json` with keys to `.gitignore`; audit git history |
| Admin password stored/compared as plaintext | Brute force or memory leak exposes password | Hash with HMAC-SHA256 or bcrypt; use `hmac.compare_digest` for timing-safe comparison |
| Exposing raw API keys in admin panel responses | Keys visible to anyone with dev tools | Mask keys in responses (show last 4 chars only); never echo keys back from the server |
| No rate limiting on the admin login endpoint | Password brute-force | Add a simple exponential backoff: lock out IP for 60s after 5 failed attempts |
| Render ephemeral filesystem for key storage | Keys wiped on every deploy, requiring re-configuration | Store keys as Render environment variables; admin panel updates env vars via Render Deploy API |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing "0 issues" when QA hasn't run yet | Users trust stale (absent) results | Show "not checked yet" state distinct from "0 issues found" |
| No indication QA is running | Users click "run check" multiple times, triggering duplicate jobs | Show spinner with "Checking..." and disable the button during a run |
| Displaying broken variable names without context | "cityName is empty for 47 leads" — which campaign? | Always show: workspace → campaign → variable → lead count hierarchy |
| Listing every affected lead with full details | Overwhelming — 5,000 rows of lead emails | Summarize at variable level (N leads affected); drill down on demand |
| No distinction between "NO" and empty/null | "NO" is semantically different from empty — it's a data entry pattern for "not found" | Surface "NO" values separately from truly empty values; they require different remediation |

---

## "Looks Done But Isn't" Checklist

- [ ] **Variable parser:** Does it handle variables in email subject lines, not just body? Subject `{{firstName}}` broken is as bad as body.
- [ ] **Lead status filter:** Verified that bounced/unsubscribed/completed leads are excluded — not just assumed to be excluded.
- [ ] **Multi-variant parsing:** Does the parser extract variables from all A/B variants, or just the first? Instant supports multiple variants per step.
- [ ] **Rate limit handling:** Does the fetcher handle 429 with retry-after backoff, or does it crash the workspace fetch and mark it as failed?
- [ ] **Background thread health:** Is there a visible indicator showing when data was last successfully refreshed per workspace?
- [ ] **Admin auth bypass:** Tested that accessing `/admin/api-keys` directly (without the login session) returns 401, not the page.
- [ ] **Empty campaign handling:** Does the QA logic handle campaigns with 0 leads gracefully (no division-by-zero, no crash)?
- [ ] **Workspace with no active campaigns:** Does the dashboard render cleanly when a workspace exists but has no active/draft campaigns?
- [ ] **"NO" value detection:** Is "NO" (the string) explicitly checked, or only `null`/empty string? This is the primary real-world bad data pattern.
- [ ] **Large campaign performance:** Tested against a campaign with 5,000+ leads, not just the 50-lead dev fixture.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| API keys stored in git history | HIGH | Rotate all 6 Instantly API keys immediately; use `git filter-repo` to scrub history; audit for any downstream exposure |
| Background thread silently died, stale data for 12h | LOW | Restart server; add thread health check + exception wrapper before next deploy |
| Rate limit collapse on first production run | MEDIUM | Add per-workspace semaphore + stagger delay; redeploy; validate with a staged "run all" test |
| Variable mismatch causing 0 issues reported (false negative) | MEDIUM | Audit 5 campaigns manually against API responses; fix normalization logic; add test fixtures for known-bad cases |
| QA run timeouts on large campaigns | MEDIUM | Switch to fire-and-forget background job; requires frontend polling change + job status endpoint |
| Render ephemeral FS wiped API keys | LOW | Re-enter keys via admin panel; move to env vars before it happens again |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Rate limit collapse on concurrent fetch | Phase 1: API client foundation | Load test: trigger "run all" for all 6 workspaces; confirm no 429s in logs |
| Variable case-sensitivity mismatch | Phase 2: Variable parser | Unit test: known variable name pairs with different casing report as same variable |
| Lead status filtering wrong | Phase 1: API client foundation | Integration test: verify lead count matches Instantly UI "active leads" count |
| Copy lives in sequence steps, not campaign list | Phase 1: API client foundation | Test against real campaign; confirm variables are extracted from copy |
| Background thread silent death | Phase 2: Background task engine | Test: inject exception in one workspace fetcher; verify others continue and last-refresh timestamp updates |
| API keys in plaintext / accessible without auth | Phase 1: Admin panel + auth | Security test: unauthenticated GET to admin routes returns 401; API keys not in git |
| QA run timeout on large campaigns | Phase 2: QA execution engine | Load test against campaign with 5,000+ leads; response time < 500ms (job accepted) |

---

## Sources

- [Instantly API v2 Rate Limit Documentation](https://developer.instantly.ai/getting-started/rate-limit) — official, HIGH confidence
- [Instantly API v2 Lead List Endpoint](https://developer.instantly.ai/api/v2/lead/listleads) — official, HIGH confidence
- [Instantly API v2 Campaign Endpoint](https://developer.instantly.ai/api/v2/campaign) — official, HIGH confidence
- [Instantly API v2 Changelog](https://feedback.instantly.ai/changelog/instantly-api-v2-is-officially-here) — official, HIGH confidence
- [Email Personalization Pitfalls — Customer.io](https://customer.io/learn/personalization/personalization-fallbacks) — MEDIUM confidence
- [Python Threading Safety — Real Python](https://realpython.com/intro-to-python-threading/) — HIGH confidence (stable stdlib patterns)
- [API Key Security Best Practices — GitGuardian](https://blog.gitguardian.com/secrets-api-management/) — MEDIUM confidence
- Existing `gtm/prospeqt-outreach-dashboard/server.py` — observed patterns, HIGH confidence (primary reference for existing Instantly integration approach)

---
*Pitfalls research for: Email QA Dashboard — Instantly multi-workspace variable validation*
*Researched: 2026-04-04*
