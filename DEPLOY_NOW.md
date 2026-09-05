# Deploy Essence Network now

## GitHub

```bash
git init
git add .
git commit -m "Essence Network online broadcast v4"
git branch -M main
git remote add origin YOUR_GITHUB_REPO_URL
git push -u origin main
```

## Render

Connect the GitHub repo in Render and use the included Blueprint. Set these secrets:

- `ESSENCE_ADMIN_EMAIL`
- `ESSENCE_ADMIN_PASSWORD`
- `CLOUDFLARE_ACCOUNT_ID` (when using Stream)
- `CLOUDFLARE_API_TOKEN` (Stream Write permission)

The service health endpoint is `/api/health`.

## Test

- Public TV: `/`
- Studio: `/studio.html`
- Login: `/login.html`
- Health: `/api/health`

The initial six channels can be started from Studio. They use the bundled demo media as a 24/7 loop until real licensed station media is uploaded.
