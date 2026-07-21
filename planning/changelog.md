# Changelog

## 2026-07-20
- **Fase 0 (Cimientos) complete**: Monorepo scaffold, Google auth, onboarding, class management with schedules/dates/weights, join codes, invite links, Railway deployment with PostgreSQL, and local seed script.
- All 12 Phase 0 tasks shipped and tested.
- Backend: 24 passing tests. Frontend: clean build.
- Seed script (`python backend/seed.py`) populates dev DB with teacher, 3 students, and sample class.
- Not yet live (Railway deployment is manual) and not yet manually QA'd end-to-end on a phone (login → onboarding → create class → invite → join) — both require real Google OAuth credentials, which no agent in this build had access to. These are the next manual steps for Mario before Fase 1 starts.

## 2026-07-19
- v1 archivada por completo: branch `v1-archive`, tag `v1-final` en GitHub. Deployment de Railway ya dado de baja.
- `main` limpiado para el rebuild desde cero.
- Docs de planeación de v1 preservados localmente en `planning/archive-v1/` (no publicados).
- Diseño de v2 aprobado: spec en `docs/superpowers/specs/2026-07-19-v2-platform-rebuild-design.md`.
- Carpeta `planning/` creada (roadmap, bugs, changelog, future).
- CLAUDE.md reescrito para la v2.
