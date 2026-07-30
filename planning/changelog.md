# Changelog

## 2026-07-29
- **Fase 1 (El Feed) complete**: las 12 tareas del plan shipped.
- Backend: modelos `Post`/`Like`/`Attachment`/`PointsLedger` con migración; servicio de puntos como único escritor del ledger append-only; storage R2 con URLs presignadas; creación de posts con atribución automática de clase; feed global con paginación keyset; thread (3 niveles); toggle de like; borrado suave con revocación; endpoint de calificación en vivo.
- Frontend: TanStack Query, feed con skeletons e infinite scroll, vista de thread, likes optimistas con rollback visible, toasts, composer full-screen con botón de taps de participación (ventana de 1.5 s, 1–3 taps), chip de calificación en el header con desglose por clase.
- Reglas de puntos vigentes: 1 tap = 1 pt (máx 3), 1 like recibido = 1 pt, sin límite diario. El orden del feed es cronológico con engagement bump (`last_activity_at`).
- Tests: 69 backend (pytest), 7 frontend (vitest). Build y lint limpios.
- Pendiente / diferido: deploy real a Railway y QA end-to-end en teléfono (requiere credenciales de Google OAuth y R2 de Mario); tope de puntos por likes sigue siendo pregunta abierta en `future.md`; en SQLite local los timestamps se serializan sin offset UTC (ver `bugs.md`) — en PostgreSQL (prod/CI) es correcto.

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
