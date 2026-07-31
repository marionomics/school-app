# Changelog

## 2026-07-30
- **Fase 2a (Tareas y el motor de calificación) complete**: 9 tareas del plan shipped.
- Nuevo tipo de post `tarea` (solo teacher), con fecha límite default al próximo domingo 23:59 en el timezone de la clase. Las replies ganan un toggle "Es mi entrega" — latest-wins (la última entrega activa es la que cuenta) — que muestra la penalización por lateness *antes* de confirmar.
- Auto-score por lateness: 100 / 90 (<24 h) / 50 (<1 semana) / 20, límites cerrados por arriba (24 h exactas = 50, no 90; 7 d exactas = 20, no 50). El override manual del profesor queda para 2b.
- Motor de calificación reescrito completo, en `Decimal` de punta a punta: tareas + exámenes + ledger + faltas, con la única rounding boundary en la API. `points_config` por clase y el esquema de `reviews`, `class_sessions` y `attendance_records` ya están, aunque nada escribe asistencia todavía (las faltas se calculan pero no hay UI hasta Fase 3) — el término de faltas convive en el motor desde ya, en cero, sin romper nada.
- Puntos por like pasan de lineales a cóncavos (`like_value × N^like_exponent`, exponente default 0.5) para que el like 50 valga menos que el primero; los taps de participación se quedan lineales.
- Chip y desglose de calificación ahora muestran rubros reales (tareas/exámenes/ledger/faltas) con `—` para rubros que todavía no tienen nada vencido, en vez del contador plano de v1. La clave legacy `counts` del payload de calificación (mantenida a propósito desde la Tarea 3 para no romper el frontend desplegado a mitad de fase) se eliminó en la última tarea, ya que el frontend dejó de leerla.
- Diferido a 2b: creación de exámenes y calificación 1–10, override manual del profe, la cola Revisar, incentives, UI de configuración de clase, y la regla de fin de curso que da el peso completo a un rubro que nunca tuvo items.
- **v2 en producción por primera vez**: https://school-app-production-e9f4.up.railway.app — Fase 0 + Fase 1 desplegadas. Verificado en vivo: `/api/health` ok, `/api/config` devuelve el client ID correcto, el SPA sirve rutas profundas (`/componer`) al refrescar, las rutas `/api/*` no las traga el fallback, y el feed responde 401 sin sesión.
- **Build migrado de Nixpacks a Dockerfile.** Nixpacks instalaba solo los 466 paquetes del lockfile sin restricción `os`/`cpu` y se saltaba los 40 binarios nativos (rolldown, tailwind oxide, lightningcss), así que `vite build` moría con `Cannot find native binding`. `--include=optional` no lo corregía. GitHub CI instala 473 en linux-x64 con el mismo lockfile, o sea que era el entorno de Nixpacks, no el lockfile. Ahora: multi-stage `node:22-bookworm-slim` → `python:3.12-slim`, un solo servicio, `npm ci` intacto. Portable a AWS más adelante.
- Antes de eso hubo que fijar Node 22 (`engines.node`): Nixpacks usaba Node 18 y Vite 8 necesita `styleText` de `node:util` (Node 20+).
- Nuevo cliente OAuth de Google (el de v1 quedó retirado). v2 usa solo el flujo de ID token: **no necesita client secret** en producción.
- Pendiente: dominio propio, R2 para adjuntos, y QA end-to-end en teléfono con alumnos reales. El `<title>` sigue siendo `vite-app` y el favicon el de Vite.

## 2026-07-29
- **Fase 1 (El Feed) complete**: las 12 tareas del plan shipped.
- Backend: modelos `Post`/`Like`/`Attachment`/`PointsLedger` con migración; servicio de puntos como único escritor del ledger append-only; storage R2 con URLs presignadas; creación de posts con atribución automática de clase; feed global con paginación keyset; thread (3 niveles); toggle de like; borrado suave con revocación; endpoint de calificación en vivo.
- Frontend: TanStack Query, feed con skeletons e infinite scroll, vista de thread, likes optimistas con rollback visible, toasts, composer full-screen con botón de taps de participación (ventana de 1.5 s, 1–3 taps), chip de calificación en el header con desglose por clase.
- Reglas de puntos vigentes: 1 tap = 1 pt (máx 3), 1 like recibido = 1 pt, sin límite diario. El orden del feed es cronológico con engagement bump (`last_activity_at`).
- Tests: 69 backend (pytest), 7 frontend (vitest). Build y lint limpios.
- **CI arreglado — nunca había pasado.** Los dos jobs fallaban antes de correr un solo test: el backend usaba `pytest backend/tests` con `working-directory: backend` (resolvía a `backend/backend/tests`, exit 4) y el frontend fallaba en `npm ci` por un lockfile desincronizado. Con los tests corriendo de verdad contra PostgreSQL apareció la primera divergencia real: un `Like(user_id=999)` que SQLite acepta y Postgres rechaza. Se añadieron además dos pasos de CI que aplican la cadena de migraciones sobre PostgreSQL y verifican que no haya drift contra los modelos — justo lo que Railway ejecuta al arrancar.
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
