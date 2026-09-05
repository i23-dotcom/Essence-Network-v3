# Essence Network v4 — GitHub/Render fix

IMPORTANT: The contents of this folder must be uploaded to the ROOT of the GitHub repository.

The GitHub repository root must show:
- Dockerfile
- render.yaml
- server.py
- config/
- web/
- media/

Do NOT upload the parent folder itself as a nested directory. Render must be able to see `Dockerfile` at the repository root.

In Render, use Docker runtime / Dockerfile deployment. Do not use Node.js.

If Render still runs `npm install`, the service is configured as a Node service or has the wrong Root Directory. Clear the Root Directory (leave blank) and redeploy.
