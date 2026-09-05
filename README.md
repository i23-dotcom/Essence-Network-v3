# Essence Network v6 — Production Studio

Essence Network online television production/control platform.

## Included

- 6 Essence channels
- Browser master-control studio
- Program/On-Air monitor and Preview monitor
- Upload media directly from the studio
- Assign uploaded video to any channel
- Channel playlist/queue
- TAKE TO AIR control
- Lower-third graphics
- Ticker graphics
- Essence logo watermark
- Visual frame control
- Audio volume and mute controls
- Automatic FFmpeg playout/watchdog
- HLS output per channel
- Cloudflare Stream live-input provisioning
- GitHub + Render Docker deployment
- Persistent Render media/state storage

The online studio is designed as the control plane. For commercial 24/7 broadcast, continuous encoder/pllayout workloads should run on dedicated media compute while Render hosts the web/control plane.
