# Essence Network — Real Online Broadcast Operation v4

This package is the production-oriented online layer for Essence Network. It provides a public six-channel TV site, protected Master Control, FFmpeg playout, HLS output, media upload, watchdog restart, and optional Cloudflare Stream Live Input provisioning.

## Important architecture

- **GitHub:** source control and deployment source.
- **Render:** public control/application service and persistent station storage.
- **FFmpeg:** program playout/encoding engine.
- **Cloudflare Stream (optional but recommended for public live delivery):** live ingest and global playback/CDN.
- **Real cameras/live sources:** feed an encoder/OBS into Cloudflare Stream using RTMPS or SRT.

Render is the control/application layer; it is not a Ugandan RF transmitter.

## Deploy

1. Create a GitHub repository and upload this folder.
2. In Render, connect the GitHub repository and deploy the included `render.yaml` Blueprint.
3. Set `ESSENCE_ADMIN_EMAIL`, `ESSENCE_ADMIN_PASSWORD`, and keep the generated session secret.
4. Deploy. Open the Render URL for the public TV site and `/studio.html` for Master Control.
5. For a real global live operation, add Cloudflare Stream credentials and provision six Live Inputs from the Studio.

Render web services must listen on the `PORT` environment variable and bind to `0.0.0.0`; this package does so.

## Cloudflare live operation

Cloudflare Stream Live Inputs accept RTMPS or SRT. After provisioning, use the channel's returned ingest credentials in OBS/FFmpeg/hardware encoders. Configure the resulting HLS manifest URL as `ESSENCE_<CHANNEL_ID>_HLS_URL` if you want the public site to use that Cloudflare feed instead of local HLS.

For a true 24/7 channel, replace the bundled demo with licensed programming and connect a reliable encoder/playout source. Use redundant ingest/encoding for broadcast continuity.

## Security

Do not leave the default admin password. Set strong secrets in Render. Control endpoints and uploads require a signed session. Before opening the Studio to a large operations team, add individual accounts, roles, audit logs, rate limiting and a managed database.
