# Essence Network v6 — Production Studio

This version replaces the basic channel list with a real browser-based master-control workspace.

## GitHub

Upload the **contents of this folder** to the repository root. `Dockerfile` must be at the root.

## Render

- Runtime / Language: **Docker**
- Build Command: **empty**
- Docker Command: **empty** (Render uses the Dockerfile CMD)
- Health check: `/api/health`
- Persistent disk: `/var/data`
- `ESSENCE_DATA_DIR=/var/data`
- `ESSENCE_AUTO_START=1`
- `ESSENCE_AUTO_CLOUDFLARE=1`
- Set `ESSENCE_ADMIN_EMAIL`, `ESSENCE_ADMIN_PASSWORD`, `ESSENCE_SESSION_SECRET`.
- For online distribution, set `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`.

Render uses the Dockerfile CMD when no Docker Command is specified.

## Studio workflow

1. Open `/studio.html` and sign in.
2. Select one of the six channels.
3. Upload a video from **MEDIA SOURCES**.
4. Click **ADD TO CHANNEL**.
5. Click **PREVIEW** to load it into the preview monitor.
6. Click **TAKE TO AIR** to make it the channel's current source.
7. Use **GRAPHICS** for lower thirds and ticker text.
8. Use **VISUAL** for the Essence watermark / frame behavior.
9. Use **AUDIO** for volume and mute.
10. The **PROGRAM / ON AIR** monitor shows the channel's actual HLS output.

The selected channel's playlist is persisted under the Render disk. A channel can be assigned different media independently.

## Online live input

If Cloudflare Stream credentials are configured, use **Live Inputs → PROVISION 6 LIVE INPUTS**. Cloudflare provides RTMPS/SRT ingest and HLS/DASH playback.

## Production note

This is a real online master-control/playout application, but six simultaneous software encoders are CPU intensive. For a commercial 24/7 network, put the continuous media engines on dedicated media compute and keep Render as the control plane/public application. Render persistent disks are single-instance storage and have deployment limitations.
