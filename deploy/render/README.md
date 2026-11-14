# Render free-tier evaluation

This build runs the existing frontend, backend, and reverse proxy in **one free Render web service**, using Dockerfile.render. It does **not** change existing project services.

## Limitations
- The service has **ephemeral local storage**. SQLite, configuration, video renders, and credentials saved through the UI may be lost whenever it restarts or redeploys. Do not rely on it to store valuable media or configure long-term social OAuth credentials.
- Heavy FFmpeg/Whisper/AI operations may exceed free instance CPU/RAM limits. A successful /health response is not proof that a video render will succeed.
- Publishing, unattended campaigns, and real provider calls are not validated by deployment alone.
- Free-tier usage and Render quotas must be checked on your billing page before relying on it. Never upgrade a plan without approval.

## Render service settings
- Repository: AdminKJG/KJGSPL_AI-Content-Studio
- Branch: deploy/render-free-evaluation
- Runtime: Docker
- Dockerfile: ./Dockerfile.render
- Plan: free
- Autodeploy: disabled during evaluation
- Health check: /health
- STUDIO_PUBLIC_ORIGIN: exact https://<service>.onrender.com URL
- STUDIO_API_TOKEN: randomly generated high-entropy token, stored **only** as Render secret environment variable.
- STUDIO_SECURE_COOKIES: true

## Acceptance checks
1. Build succeeds; /health returns JSON with status=ok.
2. /login is available. Incorrect login is rejected.
3. Authenticated UI, APIs, media, and WebSockets work through the single HTTPS origin.
4. Small test render completes, download works, and video can be opened.
5. Persistence is tested separately before calling this production-ready.

Production requires persistent encrypted storage, backups, resource sizing, and a security review. Refer to root DEPLOYMENT.md.
