# Roadmap — Plataforma v2

v2.0 está en producción con alumnos reales. Fases 0–3 archivadas en `archive/roadmap-v2.0.md`.

Ahora el orden lo dicta el semestre en curso: primero lo que hoy le cuesta puntos a un alumno o trabajo a Mario, después lo que cambia cómo se usa la app. Cada bloque se despliega a Railway antes de empezar el siguiente, y cada bloque con backend nuevo lleva su spec en `docs/superpowers/specs/`.

Origen de los bloques 1–5: nota de Mario del 2026-09-28 ("Bug report y modificaciones"), más las dos notas que había dejado en `bugs.md`.

## ▶ Empieza aquí (sesión nueva)

Estado al 2026-10-28: **Bloques 0–4b cerrados y en producción**, más "Aceptar sugeridas" (calificar en un toque todas las entregas con su calificación automática). Pendiente sólo justificar faltas paso 2.

**Siguiente, en este orden (propuesta, Mario decide):**
1. **Calificar exámenes desde el hilo** (sección propia abajo) — chico, sin spec largo, Mario lo pidió el 2026-10-23. Trae una pregunta abierta: ¿un examen con todas las calificaciones pero sin "calificado" sigue en lo pendiente del profe?
2. **Racha** (sección propia abajo) — la idea grande de Mario para que los alumnos vuelvan y avancen. Toca el motor de calificación, así que va con brainstorming → spec → plan, y absorbe el "premio por comentar" de `future.md`.
3. **Bloque 5 — notificaciones.**

**Medir el Bloque 4:** entre el **2026-11-06 y el 2026-11-13** (dos o tres semanas después del despliegue del 2026-10-23), correr `cd backend && python -m scripts.feed_metrics` contra producción y comparar con las semanas previas. Eso decide si se ajustan los pesos de `backend/app/services/feed_rank.py` o se abre la pregunta 7 de `future.md`. El profe vigila si las participaciones sin validar se le amontonan arriba (capa 1 del feed).

**Deploy:** Railway despliega `main` en cada push cuando pasa CI. Si deja de hacerlo (pasó del 2026-10-21 al 23 por un incidente de Railway; se arregló reconectando GitHub en Settings → Source), `railway up --ci` desde un `main` limpio despliega directo — el CLI ya está ligado al proyecto `poetic-caring`, servicio `school-app`. Para saber si una ruta nueva ya está viva: sin sesión responde 401 si existe y 404 si no.

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
- [x] **Bloque 4b — capas del feed** ✅ 2026-10-21 (spec `2026-10-21-feed-tiers-design.md`): lo que tocaste va debajo de todo lo nuevo, así que refrescar siempre enseña algo nuevo; para el profe, lo pendiente (participaciones por validar, tareas y exámenes por calificar, con "N por calificar") va arriba, lo más reciente primero. Validar o calificar lo baja en la siguiente recarga.
- [x] **Promover los comentarios** (Mario, 2026-10-17). ✅ 2026-10-21: un comentario destacado bajo cada post (nunca en tareas ni exámenes) y una respuesta a ti te regresa el hilo. Dos cosas que el spec del Bloque 4 debe cubrir:
  - **Un comentario en el feed principal.** Debajo de un post, mostrar al menos una respuesta — la que sea más relevante (criterio a definir en el spec: más aura, más reciente, de alguien a quien sigues…).
  - **Una respuesta te lo regresa.** Si alguien responde a tu post o a tu comentario, ese hilo vuelve a subir **para ti**, aunque ya lo hubieras tocado. Es la excepción a "lo que ya tocaste baja". Se cruza con el Bloque 5: es la misma señal que dispara la notificación.

## Racha (Mario, 2026-10-28)
La idea para que los alumnos estén en la plataforma y de verdad avancen: **la racha**. Si mantienen su racha, según cuántos días lleven, sube la probabilidad de que el aura de sus publicaciones valga **2× o 3×**. Mientras más larga la racha, más probable el multiplicador.

Absorbe el **premio por comentar** de `future.md` (2026-10-21: con cierta probabilidad, el aura de un comentario vale doble o triple) — es el mismo mecanismo, ahora atado a la constancia. Pariente de "Salvando el semestre".

Mueve puntos, así que toca el motor: brainstorming → spec → plan, con tests del motor como siempre. Lo que el spec tiene que decidir:
- **Qué mantiene la racha.** ¿Publicar o comentar cualquier cosa, una participación, o sólo comentar (lo que se quiere empujar)? ¿Cuenta la entrega de una tarea? Un comentario vacío o de una palabra no debería bastar.
- **Qué es "un día".** ¿Días naturales o días de clase? Los fines de semana y vacaciones no deberían romperla si la clase no se reúne — el horario de la clase (`schedule_json`) ya existe. Zona horaria del alumno vs del servidor.
- **La curva de probabilidad.** Por ejemplo: 0 % los primeros días y subiendo hasta un tope (¿cuánto 2× y cuánto 3×?). Configurable por clase, como `like_exponent` — nunca valores fijos en el código.
- **A qué se aplica el multiplicador.** Al aura que reciba *esa* publicación. Ojo con la curva cóncava: el aura vale `like_value × N^0.5` sobre el total del alumno, no por post. Hay que definir cómo entra un post con 2× en esa suma (p. ej., sus auras cuentan doble en N, o un bono aparte en el ledger). Escribir el ejemplo con números en el spec.
- **El sorteo se guarda, nunca se recalcula.** Cada sorteo es una fila append-only en el ledger en el momento de publicar; la calificación se computa, no se guarda, así que tirar el dado al calcular cambiaría la nota en cada carga. Si el post se borra o se veta, el multiplicador se va con él ("sin evidencia no hay puntos").
- **Cómo se ve.** Contador de racha (¿en el perfil, junto a la calificación, en el compositor?); el alumno debe ver que su post "salió" 2× o 3× — es lo que engancha. Sin emojis como UI (CLAUDE.md): un icono de remixicon.
- **Quién juega.** Ghost 👻 y polizón 🥷 no ganan puntos, así que tampoco multiplicadores; el aura del profe no da puntos — ¿la multiplica?
- **Anti-trampa.** Publicar basura para no perder la racha. El veto ya cancela; ¿basta?

## Calificar exámenes desde el hilo (Mario, 2026-10-23)
Calificar una tarea ahí mismo, desde el feed y el hilo, funciona y gusta; los exámenes deberían igual. Hoy el botón "Calificar" del hilo sólo aparece en respuestas marcadas como entrega (`Thread.tsx`), y casi nadie marca su examen como entrega — por eso el roster de `/revisar` ya cuenta como entrega la respuesta más reciente con archivos (bug 8 → R12, `_examen_submission`).
- [ ] En el hilo de un examen, "Calificar" aparece en la respuesta que el roster considera la del alumno (su entrega, o si no, su respuesta más reciente con archivos), con la escala 1–10. Misma regla en los dos lugares — reusar `_examen_submission`, no duplicarla.
- [ ] Marcar el examen como "calificado" desde el hilo, sin ir a `/revisar`.
- [ ] Pregunta abierta para el spec: un examen con todas las calificaciones puestas pero sin "calificado", ¿sigue en lo pendiente del profe (Bloque 4b) hasta que lo marque? Hoy sale.

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
