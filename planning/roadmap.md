# Roadmap — Plataforma v2

v2.0 está en producción con alumnos reales. Fases 0–3 archivadas en `archive/roadmap-v2.0.md`.

Ahora el orden lo dicta el semestre en curso: primero lo que hoy le cuesta puntos a un alumno o trabajo a Mario, después lo que cambia cómo se usa la app. Cada bloque se despliega a Railway antes de empezar el siguiente, y cada bloque con backend nuevo lleva su spec en `docs/superpowers/specs/`.

Origen de los bloques 1–5: nota de Mario del 2026-09-28 ("Bug report y modificaciones"), más las dos notas que había dejado en `bugs.md`.

## ▶ Empieza aquí (sesión nueva)

0. **`git fetch` primero.** El 2026-10-09 el `main` local llevaba dos meses atrás de `origin/main` y se replaneó sobre información vieja. Railway despliega `main` (confirmado por Mario, 2026-10-17). Queda por borrar `origin/entregas-con-archivos` (ya mergeada, sin commits propios).
1. **Bloques 1 y 2** cerrados (salvo justificar faltas paso 2). Sigue **Bloque 3, empezando por las fotos** (spec con brainstorming). Bug 8 y bug 2 son fixes acotados (TDD, sin spec propio). Justificar faltas sí lleva spec corto: el esquema ya existe, falta definir endpoints y dónde vive el control en el panel de clase.
2. Los bloques 2–5 empiezan cada uno con brainstorming → spec → plan. Las decisiones ya tomadas por Mario están escritas en cada bloque; no volver a preguntarlas. La pregunta aún abierta está en `future.md` (7).

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
- [x] **`/perfil`** — cambiar foto y bio (antes no había dónde: `/onboarding` redirige a quien ya tiene username). Lo absorbe `/u/:username`.
- Decisiones para el spec (no tomadas aún):
  - **Cómo llega la imagen al `<img>`.** La API autentica con `Authorization: Bearer`, y un `<img src>` no manda ese header, así que `/api/attachments/{id}/url` no sirve directo. Probable: el serializador incluye una URL prefirmada de vida corta para cada adjunto `image/*` (firmar es local, sin llamada a R2) y el cliente la refresca cuando caduca.
  - **Peso en datos móviles.** Una foto de celular pesa 3–10 MB; cuarenta en el feed no caben en el plan de datos de un alumno. Reducir antes de subir (en el navegador, p. ej. a ~1600 px de lado y JPEG/WebP) o generar miniatura en el servidor.
  - **Texto alternativo** opcional al subir (accesibilidad), y qué pasa con las fotos ya subidas (se verán en línea en cuanto exista el cambio — no hace falta migrar datos).
  - **Moderación:** una foto vetada o borrada deja de verse igual que el texto (sin evidencia no hay puntos; el veto no borra, el borrado sí oculta).

Después, el perfil:
- [ ] **`/u/:username`** — todo username y avatar en la app enlaza aquí.
- [ ] **Contenido:** foto, bio, aura recibida (el conteo). Sus publicaciones debajo.
- [ ] **Tu propio perfil:** editas la bio ahí mismo y cambias tu foto (la del punto de arriba).
- [ ] **Calificación en el perfil:** sólo la ve el dueño y el profesor. El profesor ve el desglose completo (el mismo del panel de clase).

## Bloque 4 — Algoritmo del feed
Problema (Mario): la interacción sube posts y algunos se quedan arriba sin ser relevantes. Lo que se quiere: una vez que interactuaste con un post, baja **para ti** y deja lugar a lo nuevo.
- [ ] **Spec primero.** Puntaje por post y por espectador: frescura + actividad reciente − penalización si ya interactuaste (aura, respuesta, validación). Implica dejar la paginación keyset sobre `last_activity_at` — la razón por la que hoy no se hizo. Retoma la idea de `future.md` (prioridad a no vistos, afinidad).
- [ ] Implementación + tests del ranking como funciones puras, igual que el motor de calificación.
- [ ] **Promover los comentarios** (Mario, 2026-10-17). Dos cosas que el spec del Bloque 4 debe cubrir:
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
