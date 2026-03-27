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

## Local Development

```bash
INSTANTLY_KEY_MYPLACE=your_key_here python client_dashboard.py
# or use a .env file (not committed) and source it first
```
