# Essence Network V3

Production CMS starter for Essence Network: HLS channels, TV Guide/EPG, VOD, News and authenticated admin management.

## What changed from V2.1
- Real Node/Express API
- SQLite database
- JWT admin login
- Shared server-side content (not browser localStorage)
- CRUD for channels, programmes, videos and news
- File upload endpoint
- Public API endpoint for the website
- Health endpoint for monitoring
- Environment-based secrets

## Run locally
1. Install Node.js 20+.
2. Copy `.env.example` to `.env`.
3. Set a strong `JWT_SECRET`, `ADMIN_EMAIL` and `ADMIN_PASSWORD`.
4. Run `npm install`.
5. Run `npm run init-admin`.
6. Run `npm start`.
7. Open `http://localhost:3000`.

## GitHub Pages note
GitHub Pages can host the static frontend, but it cannot run the Node/SQLite API. For production, deploy this whole application to a Node-capable host (or split `public/` to GitHub Pages and the `/api` server to a backend host), then point the frontend API base URL at the backend.

## Security
- Never commit `.env`.
- Change the admin password before deployment.
- Use HTTPS in production.
- Restrict CORS to your actual frontend domain.
- Use licensed HLS/VOD media only.
- Add rate limiting, password hashing with a slow password KDF (e.g. Argon2/bcrypt), backups and audit logs before high-scale public launch.

## Streaming
Replace demo HLS URLs with an Essence-owned/licensed `.m3u8` stream. A production broadcast pipeline can be OBS/encoder → ingest → transcoder/origin → CDN → this CMS/player.


## Deployment troubleshooting — `db.prepare is not a function`

This release uses `better-sqlite3`, and `server/db.js` exports the actual Database instance. If a deployment still reports `db.prepare is not a function`, the host is running a different or older commit.

After replacing the repository contents, redeploy from the new commit and confirm `/api/health` reports version `3.0.1`. Do not mix old `src/server/*` files with this root-level `server/*` layout.

Render: Build `npm install`, Start `npm start`, Node 20+, and set `JWT_SECRET`.
