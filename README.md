# Plataforma de clases — v2

Rebuild from zero of the classroom platform (marionomics.com).

- **v1 is archived** on the [`v1-archive`](https://github.com/marionomics/school-app/tree/v1-archive) branch (tag: `v1-final`).
- v2 planning and design docs live in `planning/` and `docs/` as they are created.

**Status:** Phase 0 (Cimientos) code complete — not yet deployed. Railway config (`railway.json`, `nixpacks.toml`) and CI are in place; the actual Railway project creation, env vars, and Google OAuth domain setup are a manual step (see Deployment below).

## Development Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Initialize database
alembic upgrade head

# Run server
uvicorn app.main:app --reload
```

The backend listens on `http://localhost:8000` by default.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs on `http://localhost:5173`.

### Seed Local Data

To populate a **fresh** development database with test users, a class, and enrollments (the script has no duplicate-safety check, so only run it against an empty DB — delete `school_v2.db` and re-run `alembic upgrade head` first if you've already used the app):

```bash
cd backend
rm -f school_v2.db && alembic upgrade head
python seed.py
```

This creates:
- 1 teacher (hola@marionomics.com)
- 3 students (alumno{1,2,3}@example.com)
- 1 class (Microeconomía) with all students enrolled

The class code is printed to stdout and can be used to test the invite-link flow.

## Deployment (Railway)

Build/start commands are defined in `railway.json` and `nixpacks.toml` at the repo root. The backend serves the built frontend (`frontend/dist`) directly, with an SPA fallback so client-side routes work on refresh; `/api/*` routes are never swallowed by the fallback.

Environment variables to set in the Railway dashboard:

- `DATABASE_URL` — auto-provided by the Railway Postgres plugin
- `GOOGLE_CLIENT_ID` — from Google Cloud Console
- `TEACHER_EMAIL` — email that gets the teacher role on first login
- `CORS_ORIGINS` — `https://<railway-domain>`

After deploying, add the Railway domain to the Google OAuth authorized origins.
