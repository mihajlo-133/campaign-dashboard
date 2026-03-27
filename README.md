# Campaign Dashboard

Real-time multi-client email campaign performance monitor for Instantly and EmailBison.

## Deploy on Render

1. Create a new Web Service from this repo
2. Set environment to Docker
3. Add these environment variables:

| Variable | Platform |
|----------|----------|
| `INSTANTLY_MYPLACE` | Instantly |
| `INSTANTLY_SWISHFUNDING` | Instantly |
| `INSTANTLY_SMARTMATCHAPP` | Instantly |
| `INSTANTLY_HEYREACH` | Instantly |
| `INSTANTLY_KAYSE` | Instantly |
| `INSTANTLY_PROSPERLY` | Instantly |
| `INSTANTLY_ENAVRA` | Instantly |
| `EMAILBISON_RANKZERO` | EmailBison |
| `EMAILBISON_SWISHFUNDING` | EmailBison |

Port is auto-detected from Render's `$PORT` env var.
