# Campaign Dashboard

Real-time multi-client email campaign performance monitor for Instantly and EmailBison.

## Deploy on Render

1. Push this directory to a GitHub repo
2. In Render, create a new Web Service and connect the repo
3. Set Environment to **Docker**
4. Add the environment variables listed below
5. Deploy — Render injects `PORT` automatically; the server binds to `0.0.0.0`

## Environment Variables

Set these in Render's Environment panel (Dashboard > Service > Environment):

| Variable | Platform | Client |
|----------|----------|--------|
| `INSTANTLY_KEY_MYPLACE` | Instantly | MyPlace |
| `INSTANTLY_KEY_SWISHFUNDING` | Instantly | SwishFunding |
| `INSTANTLY_KEY_SMARTMATCHAPP` | Instantly | SmartMatchApp |
| `INSTANTLY_KEY_HEYREACH` | Instantly | HeyReach |
| `INSTANTLY_KEY_KAYSE` | Instantly | Kayse |
| `INSTANTLY_KEY_PROSPERLY` | Instantly | Prosperly |
| `EMAILBISON_KEY_RANKZERO` | EmailBison | RankZero |
| `EMAILBISON_KEY_SWISHFUNDING` | EmailBison | SwishFunding (EB) |

`PORT` is set automatically by Render — do not set it manually.

Clients with a missing env var will appear in the dashboard with "No API key" instead of live data.

## Deploying New Commits

The source code lives at `gtm/scripts/client_dashboard.py` in the main workspace repo.
The deployment repo is `mihajlo-133/campaign-dashboard` on GitHub.

### Quick deploy workflow

```bash
# 1. Copy updated source to deploy repo
cp gtm/scripts/client_dashboard.py /tmp/campaign-dashboard-new/client_dashboard.py

# 2. Commit and push
cd /tmp/campaign-dashboard-new
git add client_dashboard.py && git commit -m "Description of changes" && git push origin main

# 3. Trigger cache-cleared deploy via Render API
curl -s -X POST "https://api.render.com/v1/services/srv-d73efrfdiees73erakqg/deploys" \
  -H "Authorization: Bearer $(grep -oP '```\n\K[^`]+' tools/accounts/render/api_key.md)" \
  -H "Content-Type: application/json" \
  -d '{"clearCache": "clear"}'

# 4. Monitor deploy status
RENDER_API_KEY=<key> render deploys list srv-d73efrfdiees73erakqg -o json --confirm
```

### Important notes

- **Always use `clearCache: "clear"`** in the deploy API call. Without it, Docker layer caching may serve stale code.
- The deploy hook URL (`/deploy/srv-...?key=...`) does NOT support cache clearing — use the REST API instead.
- If a deploy gets stuck in `update_in_progress`, cancel it via API then re-deploy:
  ```bash
  curl -s -X POST "https://api.render.com/v1/services/srv-d73efrfdiees73erakqg/deploys/<deploy-id>/cancel" \
    -H "Authorization: Bearer <api-key>"
  ```
- The code auto-detects Render vs local: when `PORT` env var is set, it binds to `0.0.0.0` and reads API keys from env vars. Locally it binds to `127.0.0.1` and reads keys from files.
- Render API key stored at: `tools/accounts/render/api_key.md`
- UptimeRobot keeps the service warm (5-min pings). API key: `tools/accounts/render/api_key.md`

## Local Development

```bash
# Reads API keys from tools/accounts/ markdown files
python client_dashboard.py --no-prefetch

# Or with env vars (same as Render)
INSTANTLY_KEY_MYPLACE=your_key_here python client_dashboard.py
```
