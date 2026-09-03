# ESSENCE NETWORK — PROJECT DOCUMENT
## Version 3.0 — Production CMS + API Foundation
Date: 3 September 2026

### Objective
Move Essence Network from a browser-only prototype to a shared, server-backed digital TV platform.

### V3 completed
- Node.js/Express API
- SQLite database schema
- JWT-authenticated admin dashboard
- Channels CRUD with HLS URLs
- Programme/EPG CRUD
- VOD CRUD
- News CRUD
- Upload endpoint foundation
- Public content API
- Health endpoint
- Environment configuration
- Public responsive website
- HLS playback using hls.js with native fallback

### Architecture
Browser → Express API → SQLite
Browser → HLS CDN/origin for live video
Admin → JWT login → protected CRUD API

### Deployment model
GitHub stores source code. GitHub Pages may host the static frontend, but the API/database require a Node-capable backend. For the simplest V3 deployment, deploy the complete repository to a Node hosting service. For a split deployment, host `/public` separately and configure an API base URL.

### Production hardening still required
- Argon2/bcrypt password hashing instead of the prototype SHA-256 helper
- Rate limiting and login protection
- HTTPS
- Strict CORS
- Database backups
- Audit logs
- Role-based permissions
- CDN/media storage
- Real EPG scheduling rules/time zones
- Stream health monitoring
- Automated deployments

### Roadmap
V1 UI → V2 HLS → V2.1 browser CMS → **V3 shared production CMS foundation** → V4 Android APK → V5 Android TV/Google TV → V6 OTT platform.
