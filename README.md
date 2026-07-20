# Plataforma de clases — v2

Rebuild from zero of the classroom platform (marionomics.com).

- **v1 is archived** on the [`v1-archive`](https://github.com/marionomics/school-app/tree/v1-archive) branch (tag: `v1-final`).
- v2 planning and design docs live in `planning/` and `docs/` as they are created.

Status: planning phase.

## Deployment (Railway)

Build/start commands are defined in `railway.json` and `nixpacks.toml` at the repo root. The backend serves the built frontend (`frontend/dist`) directly, with an SPA fallback so client-side routes work on refresh; `/api/*` routes are never swallowed by the fallback.

Environment variables to set in the Railway dashboard:

- `DATABASE_URL` — auto-provided by the Railway Postgres plugin
- `GOOGLE_CLIENT_ID` — from Google Cloud Console
- `TEACHER_EMAIL` — email that gets the teacher role on first login
- `CORS_ORIGINS` — `https://<railway-domain>`

After deploying, add the Railway domain to the Google OAuth authorized origins.
