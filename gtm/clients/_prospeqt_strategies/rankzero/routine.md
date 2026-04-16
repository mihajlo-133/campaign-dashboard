---
title: "Rank Zero — Weekly Report Routine"
type: reference
tags: [rankzero, routine, automation, emailbison, weekly-report]
status: active
created: 2026-04-16
---

# Rank Zero — Weekly Report Routine

## Purpose

Every Wednesday at 15:30 Belgrade time, generate a client-facing HTML
outreach report (MTD / WTD / Week-before with 3 smooth line charts) from
EmailBison data and send it to Mihajlo via Telegram (`@claude_code_386_bot`,
chat `8052848572`) for review.

Built as a **Claude Routine** (cloud-hosted) so the report fires even when
the local Mac is off. Dry-run phase — delivery is to Mihajlo personally
until the format is locked; client delivery is a future upgrade.

## Components

| Artifact | Path |
|---|---|
| Generator script | `gtm/scripts/rankzero_weekly_report.py` |
| SVG chart builder (inline) | same file — `build_svg_chart()` |
| Output directory (local runs) | `outputs/rankzero/reports/weekly_YYYYMMDD.html` |
| Routine spec | this file |

## Schedule

- **Cron:** `30 13 * * 3` (Wednesday 13:30 UTC = 15:30 Belgrade CEST)
  - ⚠️ When Belgrade shifts to CET (late Oct → late Mar), this becomes 14:30 Belgrade. Update to `30 14 * * 3` at DST transitions, or use the routine UI's timezone-aware scheduling if available.

## Routine prompt (paste into the routine config)

```
You are running the Rank Zero weekly outreach report.

Execute:
  python3 gtm/scripts/rankzero_weekly_report.py --send --no-write

The script fetches EmailBison data for three windows (MTD / WTD / week before),
renders an HTML report with three smooth-line dual-axis charts, and sends both
a text summary and the HTML document to Telegram chat TELEGRAM_CHAT_ID via
TELEGRAM_BOT_TOKEN.

Expected output: "[OK] Sent report to Telegram chat ..." followed by window totals.

If the script exits non-zero:
  1. Read the stderr output
  2. Report the failure reason (EmailBison auth? Telegram token? rate limit?)
  3. Do NOT retry automatically — let Mihajlo investigate manually
```

## Environment variables (set these in the routine config, NOT in the repo)

| Variable | Value | Notes |
|---|---|---|
| `EMAILBISON_RANKZERO` | `<api_key>` | Currently in `tools/prospeqt-automation/.env` — copy this value |
| `TELEGRAM_BOT_TOKEN` | `8535535192:AAH0zkGZwz30X-kVI9Xy21WxvtZocCSWnlQ` | `@claude_code_386_bot` — from `tools/accounts/telegram.md` |
| `TELEGRAM_CHAT_ID` | `8052848572` | Mihajlo's personal chat (`@maigaa133`) |

**Do NOT commit any of these to the repo.** They are set in the Claude Routines
environment configuration UI only. The bot token values are already tracked in
`tools/accounts/telegram.md` for operational reference — treat that file as
sensitive and do NOT publish the repo without scrubbing it.

## Setup steps (one-time)

### On your laptop (now)
Commit the script to the repo:
```
git add gtm/scripts/rankzero_weekly_report.py gtm/clients/_prospeqt_strategies/rankzero/routine.md
git commit -m "Add Rank Zero weekly report routine"
git push
```

### In the Claude.ai Routines UI
1. Go to https://claude.ai/code/routines
2. Click **New routine**
3. **Name:** `Rank Zero — Weekly Report`
4. **Repo:** connect to the `claude-code` repo (GitHub connection required)
5. **Schedule:** Wednesday 15:30 Belgrade → cron `30 13 * * 3` (UTC)
6. **Environment variables:** add the three vars from the table above
7. **Prompt:** paste the block from `## Routine prompt` above
8. Save

### First-run verification
1. Click **Run now** in the routine UI
2. Check Telegram (`@claude_code_386_bot`) within ~30 seconds for the text summary + HTML attachment
3. If nothing arrives, check the routine run log for errors
4. Common failures:
   - **401 from EmailBison** → wrong/rotated API key
   - **Telegram "not-ok"** → wrong token or chat ID; also: bot must be initiated by you at least once (send `/start` to `@claude_code_386_bot` from your `@maigaa133` account)
   - **No chart data** → check the `line-area-chart-stats` endpoint is returning data for the window

## When to expand delivery

Once you've reviewed 2–3 weekly reports and the format + narrative is locked,
consider adding one of:
- **Email delivery to the client** — re-add the SMTP sender, send the HTML to Johannes/Niels at rankzero.io
- **Second Telegram chat** — add a Prospeqt team group chat ID, send the summary there too for Balsa/Petar visibility
- **Slack delivery** — add a Slack MCP send alongside the Telegram message

Update this doc's "Dry-run phase" note above when delivery expands.

## Upgrade paths (not doing now)

- **Add Claude commentary block** — have Claude write 1-2 sentences of exec
  summary based on the numbers before sending. Requires the routine prompt to
  generate HTML first, then inject commentary, then email.
- **Historical tracking** — commit each week's generated HTML back to the repo
  on a `reports/` branch so trends are queryable via git log.
- **Slack delivery** — add a Slack MCP send alongside email.

## Reference

- `gtm/scripts/rankzero_weekly_report.py` — generator + SMTP sender
- `gtm/transcripts/fireflies/rankzero_handover_20260407.md` — Petar's handover
  defining the report format (MTD / last week / week before)
- `sessions/Session_20260407_170000_prospeqt_unified_shipped_phases_1_to_5.md`
  — origin of `EMAILBISON_RANKZERO` env var
