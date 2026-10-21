# Roadmap — Plataforma v2

v2.0 está en producción con alumnos reales. Fases 0–3 archivadas en `archive/roadmap-v2.0.md`.

Ahora el orden lo dicta el semestre en curso: primero lo que hoy le cuesta puntos a un alumno o trabajo a Mario, después lo que cambia cómo se usa la app. Cada bloque se despliega a Railway antes de empezar el siguiente, y cada bloque con backend nuevo lleva su spec en `docs/superpowers/specs/`.

Origen de los bloques 1–5: nota de Mario del 2026-09-28 ("Bug report y modificaciones"), más las dos notas que había dejado en `bugs.md`.

## ▶ Empieza aquí (sesión nueva)

Estado al 2026-10-21: **Bloques 0–4 cerrados y en producción** (salvo justificar faltas paso 2). **Sigue el Bloque 5 — actividad (notificaciones).** Pendiente del Bloque 4: correr `cd backend && python -m scripts.feed_metrics` contra producción dos o tres semanas después del despliegue y comparar con la semana previa; eso decide si se ajustan los pesos de `backend/app/services/feed_rank.py` o se abre la pregunta 7 de `future.md`.

0. **`git fetch` primero** y confirmar `main...origin/main` en sync. Railway despliega `main` en cada push. Pendiente menor: borrar `origin/entregas-con-archivos` (ya mergeada; el borrado lo bloqueó el clasificador, Mario puede hacerlo con `! git push origin --delete entregas-con-archivos`).
1. **Cómo se trabaja un bloque** (lo que funcionó en 2, 3a y 3b): brainstorming con Mario sección por sección → spec **en inglés** en `docs/superpowers/specs/` → plan en `docs/superpowers/plans/` → ejecución *subagent-driven*: cada implementador hace commit **sin push**, una revisión por tarea, y el controlador hace push sólo cuando la revisión sale limpia (cada push llega a los alumnos). Al final, una revisión de todo el bloque en el modelo más capaz, una sola ola de fixes y una re-revisión. Las decisiones que se toman en el camino se anotan como *rulings* y se le entregan a Mario al cerrar.
2. **Bloque 5: hechos del código que su spec tiene que saber.**
   - La señal "te respondieron" ya existe: `has_new` en `backend/app/services/feed_query.py` sabe qué hilos son tuyos (`root_ids_of` + los que escribiste o respondiste) y el ranking (`feed_rank.score`) distingue una respuesta *a ti* de una respuesta *en tu hilo*. Reusarla, no duplicarla.
   - El feed sólo se recarga con `refreshFeed(qc)` (`frontend/src/lib/feed.ts`); todo lo demás parcha la caché (`patchFeedPost`, `dropFromFeed` en `postCache.ts`). Una página de actividad no debe invalidar `["feed"]`.
   - El filtro por clase sigue en `backend/app/services/visibility.py`.
3. **Cómo se trabajó el Bloque 4** (ejecución *native*: un solo contexto, TDD por tarea y una revisión final del bloque completo). Sirve para bloques medianos con plan detallado.
4. Pendientes chicos fuera de bloques: **justificar faltas paso 2** (comprobante del alumno), bugs 9–11 en `bugs.md`, buscador de GIFs en `future.md`.

## Bloque 0 — Higiene ✅ (2026-10-09)
- [x] **`entregas-con-archivos` en `main`.** Ya estaba mergeada en `origin/main` (`ae9998e`, 2026-08-07, junto con los fixes R10 y R11); el `main` local nunca la había jalado. Se rebaseó la replaneación encima, se quitó el worktree y la rama, y `main` se empujó.

## Bloque 1 — Lo que hoy cuesta puntos o trabajo
Pequeños, independientes entre sí, cada uno desplegable solo.
- [x] **Revisar exámenes sin importar la modalidad** (bug 8 → R12). La fila del alumno en el roster muestra lo que subió al hilo del examen — su entrega si la marcó, y si no, su respuesta más reciente con archivos — y la calificación se pone ahí mismo. Si no subió nada, sólo se califica. Presencial vs en línea deja de decidir qué ves. *"El software sirve al flujo de trabajo, no al revés."*
- [x] **Publicaciones normales sin selector de clase** (bug 7 → R10, `a93e60b`).
- [x] **…pero que su aura cuente para alguna clase.** ✅ 2026-10-17: fuera de horario, una publicación normal cuenta para la clase que tuviste más recientemente según el horario. Tareas, exámenes y el selector siguen preguntando. Con más de una clase y ninguna en horario, `resolve_default_class` devuelve `None` y el aura que reciba ese post no cuenta para nadie. Agregar el último paso: la clase más reciente. Test en `attribution`.
- [~] **Justificar faltas.** Paso 1 ✅ 2026-10-17 (spec `2026-10-17-justificar-faltas-design.md`): el profesor justifica desde la hoja del alumno en el panel de clase, y volver a guardar pasar lista ya no borra justificaciones. **Falta el paso 2** (comprobante del alumno). Cada falta injustificada vale −10, y hoy no hay forma de justificar ninguna. El esquema ya existe (`attendance_records.justification_*`) y el motor ya respeta `justification_status = approved`; faltan endpoints y UI. Primero lo mínimo: el profesor marca una falta como justificada desde el panel de clase; la falta sigue visible, tachada y con etiqueta "justificada" (Mario, 2026-10-17). Después: el alumno sube su comprobante (R2) y el profesor aprueba/rechaza.
- [x] **Bug 2** (→ R13) — borrar tu entrega más reciente pierde la tarea. Con archivos en producción, borrar y reentregar ya es cosa de todos los días.
- [x] **Publicaciones largas colapsadas.** ✅ 2026-10-17. En el feed, un post largo se corta a 6 líneas (Mario, 2026-10-17) con "ver más" que lo expande en su lugar. El hilo siempre lo muestra completo.

## Bloque 2 — Aura: validar desde el feed
El like se llama **aura** en toda la app (copy final de Mario). Nada cambia en el motor: sigue siendo la curva cóncava, y el aura del profesor sigue sin dar puntos.
- [x] **Renombrar like → aura** en el módulo de strings. ✅ 2026-10-19
- [x] **El aura del profesor se ve** (Mario, 2026-10-17): todos ven que el profesor le dio aura a un post. Sigue sin dar puntos. ✅ 2026-10-19
- [x] **El aura del profesor sobre una participación la valida.** Dar aura = `reviewed_at`; son el mismo hecho, así que "Validar" en `/revisar` también enciende el aura y viceversa. No mueve puntos — `test_reviewing_moves_no_points` sigue siendo el guardián. ✅ 2026-10-19
- [x] **Quitar el aura des-valida** (decisión de Mario, 2026-10-09): `reviewed_at` vuelve a nulo y la participación regresa a la cola de `/revisar`. Tampoco mueve puntos. ✅ 2026-10-19
- [x] **Vetar desde el feed.** En la tarjeta de una participación, el profesor tiene "Vetar" con el mismo diálogo de confirmación de `/revisar`. Aura (validar) y vetar siguen siendo dos controles distintos; nunca uno solo. ✅ 2026-10-19
- [x] **El aura del profesor no reordena el feed.** Hoy cada like sube `last_activity_at`: validar 30 participaciones las manda todas arriba. Primer paso barato del Bloque 4 — los likes dejan de subir posts; sólo las respuestas lo hacen. ✅ 2026-10-19

## Bloque 3 — Fotos y perfil
Principio de Mario: si aparece un username, se le puede dar click y llegar al perfil.

**Fotos primero** (Mario, 2026-10-19): a veces un alumno se expresa mejor con una foto, y hoy una imagen adjunta aparece como un enlace para abrirla. Las fotos en línea y la foto de perfil comparten el mismo camino (subir → reducir → servir desde R2), así que se diseñan en un solo spec y se construyen primero.
- [x] **Imágenes en línea en el feed y el hilo,** como en una red social: la foto se ve en la tarjeta, no un enlace. Tocarla la abre completa. Varias fotos → cuadrícula. Los demás archivos (PDF, etc.) siguen siendo chips. ✅ 2026-10-20
- [x] **Foto de perfil propia** (subida a R2; hoy `avatar_url` es la de Google). Recorte cuadrado. ✅ 2026-10-20
- [x] **`/perfil`** — cambiar foto y bio (antes no había dónde: `/onboarding` redirige a quien ya tiene username). Lo absorbe `/u/:username`. ✅ 2026-10-20
- Decisiones para el spec (no tomadas aún):
  - **Cómo llega la imagen al `<img>`.** La API autentica con `Authorization: Bearer`, y un `<img src>` no manda ese header, así que `/api/attachments/{id}/url` no sirve directo. Probable: el serializador incluye una URL prefirmada de vida corta para cada adjunto `image/*` (firmar es local, sin llamada a R2) y el cliente la refresca cuando caduca.
  - **Peso en datos móviles.** Una foto de celular pesa 3–10 MB; cuarenta en el feed no caben en el plan de datos de un alumno. Reducir antes de subir (en el navegador, p. ej. a ~1600 px de lado y JPEG/WebP) o generar miniatura en el servidor.
  - **Texto alternativo** opcional al subir (accesibilidad), y qué pasa con las fotos ya subidas (se verán en línea en cuanto exista el cambio — no hace falta migrar datos).
  - **Moderación:** una foto vetada o borrada deja de verse igual que el texto (sin evidencia no hay puntos; el veto no borra, el borrado sí oculta).

Después, el perfil:
- [x] **`/u/:username`** — todo username y avatar en la app enlaza aquí. ✅ 2026-10-20
- [x] **Contenido:** foto, bio, aura recibida (el conteo). Sus publicaciones debajo. ✅ 2026-10-20
- [x] **Tu propio perfil:** editas la bio ahí mismo y cambias tu foto (la del punto de arriba). ✅ 2026-10-20
- [x] **Calificación en el perfil:** sólo la ve el dueño y el profesor. El profesor ve el desglose completo (el mismo del panel de clase). ✅ 2026-10-20

## Bloque 4 — Algoritmo del feed
Problema (Mario): la interacción sube posts y algunos se quedan arriba sin ser relevantes. Lo que se quiere: una vez que interactuaste con un post, baja **para ti** y deja lugar a lo nuevo.
- [x] **Spec primero.** ✅ 2026-10-21: `docs/superpowers/specs/2026-10-21-feed-ranking-design.md`, plan en `docs/superpowers/plans/2026-10-21-feed-ranking.md`. Puntaje por post y por espectador: frescura + actividad reciente − penalización si ya interactuaste (aura, respuesta, validación). Implica dejar la paginación keyset sobre `last_activity_at` — la razón por la que hoy no se hizo. Retoma la idea de `future.md` (prioridad a no vistos, afinidad).
- [x] Implementación + tests del ranking como funciones puras, igual que el motor de calificación. ✅ 2026-10-21 (`feed_rank.py`, `feed_query.py`).
- [x] **Promover los comentarios** (Mario, 2026-10-17). ✅ 2026-10-21: un comentario destacado bajo cada post (nunca en tareas ni exámenes) y una respuesta a ti te regresa el hilo. Dos cosas que el spec del Bloque 4 debe cubrir:
  - **Un comentario en el feed principal.** Debajo de un post, mostrar al menos una respuesta — la que sea más relevante (criterio a definir en el spec: más aura, más reciente, de alguien a quien sigues…).
  - **Una respuesta te lo regresa.** Si alguien responde a tu post o a tu comentario, ese hilo vuelve a subir **para ti**, aunque ya lo hubieras tocado. Es la excepción a "lo que ya tocaste baja". Se cruza con el Bloque 5: es la misma señal que dispara la notificación.

## Bloque 5 — Actividad (notificaciones)
Como "Actividad" en Threads o "Notificaciones" en X.
- [ ] Ícono con puntito rojo cuando hay algo nuevo.
- [ ] Página de actividad: respuestas a tus posts y aura recibida, **agrupada** ("marionomics y otros 4 le dieron aura a tu publicación").
- [ ] Cada fila enlaza al post y cada nombre al perfil (Bloque 3).
- [ ] Después: menciones `@`, filtros, agrupación temporal.

## Resto del semestre
- [ ] Asistencia swipe (estilo Tinder) con retardos automáticos por hora
- [ ] Moderadores (anónimos, solo sobre otras clases, capibara)
- [ ] Protocolo "Salvando el semestre" (multiplicadores aleatorios) — necesita su spec, toca el motor
- [ ] Link previews + embeds de YouTube/Loom
- [ ] Reglas de exención (licenciatura ≥ 8.5)
- [ ] UI de ghosts 👻 y polizones 🥷
- [ ] Editar nombre, fechas y horario de la clase (ver `future.md`)

## Largo plazo
Ver `future.md`.
