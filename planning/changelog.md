# Changelog

## 2026-07-31 (Phase 2b-2 Configurar — completa)
- **7 tareas shipped.** 174 tests en backend (pytest, +22 desde 2b-1); frontend TypeScript limpio en CI.
- **`Incentive` model + tabla `incentives`.** Tipos de puntos extra configurables en-app por clase — nunca hardcodeados. El profesor los nombra (ej. "Libreta completa", "Todo en inglés"). Awarding escribe directamente a `points_ledger` con `source_type='incentive'`; el motor ya sumaba ese bucket en `ledger.other`, así que el chip de calificación se actualiza sin cambios en el engine.
- **Soft-delete inteligente.** Si un incentivo ya fue otorgado, `DELETE` lo marca con `deleted_at` pero conserva las rows del ledger (los puntos siguen contando). Si nunca fue otorgado, se borra físicamente. El alumno nunca pierde puntos por limpiar la lista.
- **Se puede otorgar el mismo incentivo múltiples veces.** No hay dedup — la lógica es que "libreta completa semana 3" y "libreta completa semana 5" son awards distintos del mismo tipo. El teacher controla la frecuencia.
- **`GET/PATCH /api/classes/{id}/settings`.** Permite editar `tareas_weight`, `examenes_weight`, `tap_value`, `like_value`, `like_exponent` con una PATCH parcial. `like_cap` y `daily_post_limit` no están expuestos (la curva cóncava es el mecanismo anti-cramming, no un cap). `extra='forbid'` en el schema rechaza 422 cualquier campo no reconocido.
- **Página `/configurar` (solo teacher).** Dos secciones: (A) formulario de pesos y valores con save explícito, (B) lista de incentivos con crear, eliminar (con confirmación), y otorgar (modal con selector de alumno). La lista de alumnos viene del `GET /api/classes/{id}` ya existente.

## 2026-07-31 (Phase 2b-1 Calificar — completa)
- **16 tareas shipped.** 151 tests en backend (pytest); los tests de frontend (vitest) pasan en CI (Node 22) pero no en local (Node 16, incompatible con Vite 8 — sin solución hasta actualizar Node en el Mac).
- **Exámenes como tipo de post.** Un post `type=examen` lleva `examen_mode` (`paper` o `digital`) y `graded_at`. Los exámenes sólo entran en el rubro cuando el profesor marca `graded_at`; antes de eso el rubro los ignora completamente para que un "0" antes de calificar no asuste a nadie. Desmarcar borra `graded_at` y el rubro vuelve a ignorarlo.
- **Reviews re-keyed en `(item_post_id, student_id)`.** Ya no hay una row de review por `entrega_post_id`; hay una por alumno-por-item, con `entrega_post_id` opcional (nulo para exámenes en papel, que no requieren entrega digital). Una review es "stale" si su `entrega_post_id` ya no coincide con la entrega actual del alumno — `counting_review()` la descarta silenciosamente. Esto permite re-entregar sin perder la calificación de la entrega anterior y sin que la nueva calificación aparezca antes de que el profesor la revise.
- **Regla de rubro vacío a fin de curso.** Si una clase terminó (`end_date` en el pasado) y un rubro nunca tuvo ningún item due (ni tareas ni exámenes), ese rubro aporta su peso completo al denominador de la calificación en vez de ignorarse. Evita que alumnos de clases sin tareas terminen con calificación de 0.
- **Veto de participaciones.** El profesor puede vetar (`POST /api/posts/{id}/veto`) una participación con razón opcional; el post queda `status=vetoed` pero visible en el hilo con la razón. El veto revoca todos los puntos del ledger asociados (taps + likes recibidos). `DELETE /api/posts/{id}/veto` restaura los puntos.
- **`PUT /api/reviews` — única ruta de escritura de calificaciones.** Valida la escala por tipo (tarea 0–100, examen 1–10), verifica inscripción, guarda `auto_score` del alumno para mostrar al profesor. Idempotente: upsert por `(item_post_id, student_id)`.
- **Cola Revisar — 3 pestañas.** `GET /api/review/entregas` agrupa por tarea con contador de pendientes. `GET /api/review/examenes` y `/{id}` listan el roster con las calificaciones actuales. `GET /api/review/participaciones` lista con estado de veto. La página `/revisar` (solo teacher) consume los tres endpoints.
- **Privacidad de calificaciones.** `my_review` y `veto_reason` sólo viajan al autor y al profesor — el servidor los omite para el resto. No hay flag en el cliente; la lógica está server-side.
- **Calificar desde el thread.** Un botón "✎ Calificación" aparece junto a las entregas para el profesor. Abre `ReviewSheet`, el mismo bottom sheet que `/revisar`.
- **Diferido a 2b-2.** Configuración de clase (pesos, `tap_value`, `like_value`, `like_exponent`) y puntos extra configurables (incentives). Bug 2 (borrar la última entrega pierde la tarea) sigue abierto; el fix propuesto no cambia en nada lo que se hizo aquí.

## 2026-07-31 (tarde)
- **Corregida una regla mal escrita desde el día uno.** `CLAUDE.md` y el spec de v2 decían que borrar un post **conserva** los puntos ganados y que sólo el veto los revoca. Es al revés, y el código siempre estuvo bien: borrar revoca. La regla real es **sin evidencia no hay puntos** — una participación es su propia evidencia. Si no fuera así habría una fábrica de puntos: `award()` deduplica por `source_id`, así que publicar → borrar → volver a publicar acredita la misma participación dos veces. `deleted` ≠ `vetoed` sigue significando algo, pero no en el ledger: distingue quién actuó y qué queda visible (el autor lo quita, o el profesor lo invalida con motivo y el post se queda en el hilo).
- Como consecuencia, el veto ahora también revoca los likes recibidos, no sólo los taps (§2.8 del spec de 2b-1, que decía lo contrario, reescrito). Un post invalidado no puede seguir pagando por ninguna vía.
- Editar un post para corregirlo (en vez de borrar y republicar) queda pendiente, no urgente.

## 2026-07-31
- **Revisión de la rama de Fase 2a.** Un bloqueador real: el profesor no podía crear una tarea desde la UI. El backend exige `class_id` para las tareas, pero el composer nunca lo mandaba — el selector de clase estaba detrás de `isStudent` y `resolve_default_class` sólo miraba `enrollments`, y un profesor **nunca** se inscribe en su propia clase (`create_class` no crea `Enrollment`). Resultado: 422 "Una tarea necesita una clase" en todos los intentos. La suite no lo detectó porque todos los tests mandan `class_id` explícito.
- Arreglo: `resolve_default_class` ahora considera también las clases que impartes (in-session por horario primero, luego la única candidata); el composer muestra el selector al profesor sobre `teaching` y bloquea publicar mientras una tarea no tenga clase; el 422 se evalúa después de resolver la clase, no antes. Efecto lateral aceptado: las publicaciones normales del profesor también se atribuyen a su clase cuando sólo tiene una. +3 tests (106 backend, 11 frontend).
- Anotados en `bugs.md` y aquí, sin arreglar: borrar tu entrega más reciente pierde la tarea entera (bug 2), y en `examenes_rubro` una entrega sin `Review.score` suma 0 con el examen ya en el denominador — entre que cierra el examen y lo califica el profesor, el rubro se lee como un cero real. Las tareas tienen el fallback de lateness; los exámenes no tienen equivalente. Se decide en 2b junto con la regla de fin de curso.
- `es.post.entregaReplaces` quedó en el módulo de strings sin usarse; se deja como placeholder para el aviso de "reemplaza tu entrega anterior" en 2b.

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
