# Single service: FastAPI serves the built frontend from frontend/dist.
#
# Why a Dockerfile instead of Nixpacks: Nixpacks' image installs only the 466
# packages in our lockfile that carry no os/cpu constraint, silently skipping
# every platform-gated native binary (rolldown, tailwind oxide, lightningcss).
# `npm ci --include=optional` does not override it. A stock node image installs
# all 473 for linux-x64, which is what CI has always done.

# ---- stage 1: build the frontend ----
FROM node:22-bookworm-slim AS frontend

WORKDIR /build

# Copy manifests first so the dependency layer caches independently of source.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ---- stage 2: runtime ----
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/

# app/main.py resolves FRONTEND_DIST as <repo root>/frontend/dist, and it
# computes that three parents up from backend/app/main.py — so this must land
# at /app/frontend/dist to match the layout the code expects.
COPY --from=frontend /build/dist frontend/dist

CMD ["sh", "-c", "cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
