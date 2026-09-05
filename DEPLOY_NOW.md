# Essence Network v5 — Operational Deploy

## Render
- Runtime: Docker
- Build Command: leave empty
- Start Command / Docker Command: leave empty (Dockerfile CMD starts `python server.py`)
- Plan: paid/starter or higher for continuous operation
- Persistent disk: `/var/data`
- `ESSENCE_DATA_DIR=/var/data`
- `ESSENCE_AUTO_START=1`
- `ESSENCE_AUTO_CLOUDFLARE=1`

## Required secrets
Set these in Render Environment: `ESSENCE_ADMIN_EMAIL`, `ESSENCE_ADMIN_PASSWORD`, `ESSENCE_SESSION_SECRET`.
For real Cloudflare live distribution also set `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` (Cloudflare API token needs Stream Write).

## What happens on deploy
1. The web control room starts.
2. All six channels automatically start a continuous demo playout.
3. If Cloudflare credentials are present, six Live Inputs are automatically provisioned.
4. Each channel's encoded program is sent to its Cloudflare RTMPS input and also retained as local HLS.
5. The public site plays the channel HLS URL.

For real programming, replace the demo asset with licensed media or connect a real encoder/live production source.
