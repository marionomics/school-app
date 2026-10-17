# Roadmap — Plataforma v2

v2.0 está en producción con alumnos reales. Fases 0–3 archivadas en `archive/roadmap-v2.0.md`.

Ahora el orden lo dicta el semestre en curso: primero lo que hoy le cuesta puntos a un alumno o trabajo a Mario, después lo que cambia cómo se usa la app. Cada bloque se despliega a Railway antes de empezar el siguiente, y cada bloque con backend nuevo lleva su spec en `docs/superpowers/specs/`.

Origen de los bloques 1–5: nota de Mario del 2026-09-28 ("Bug report y modificaciones"), más las dos notas que había dejado en `bugs.md`.

## ▶ Empieza aquí (sesión nueva)

0. **`git fetch` primero.** El 2026-10-09 el `main` local llevaba dos meses atrás de `origin/main` y se replaneó sobre información vieja. **Pendiente de Mario:** confirmar en el dashboard de Railway que el servicio despliega `main` (todo indica que seguía en `entregas-con-archivos`: el fix del bug 7 de agosto no estaba en producción en septiembre). Cuando esté confirmado, borrar `origin/entregas-con-archivos`.
1. **Bloque 1**, en este orden (Mario, 2026-10-17): bug 2 → justificar faltas → publicaciones largas. Bug 8 y bug 2 son fixes acotados (TDD, sin spec propio). Justificar faltas sí lleva spec corto: el esquema ya existe, falta definir endpoints y dónde vive el control en el panel de clase.
2. Los bloques 2–5 empiezan cada uno con brainstorming → spec → plan. Las decisiones ya tomadas por Mario están escritas en cada bloque; no volver a preguntarlas. La pregunta aún abierta está en `future.md` (7).

## Bloque 0 — Higiene ✅ (2026-10-09)
- [x] **`entregas-con-archivos` en `main`.** Ya estaba mergeada en `origin/main` (`ae9998e`, 2026-08-07, junto con los fixes R10 y R11); el `main` local nunca la había jalado. Se rebaseó la replaneación encima, se quitó el worktree y la rama, y `main` se empujó.

## Bloque 1 — Lo que hoy cuesta puntos o trabajo
Pequeños, independientes entre sí, cada uno desplegable solo.
- [x] **Revisar exámenes sin importar la modalidad** (bug 8 → R12). La fila del alumno en el roster muestra lo que subió al hilo del examen — su entrega si la marcó, y si no, su respuesta más reciente con archivos — y la calificación se pone ahí mismo. Si no subió nada, sólo se califica. Presencial vs en línea deja de decidir qué ves. *"El software sirve al flujo de trabajo, no al revés."*
- [x] **Publicaciones normales sin selector de clase** (bug 7 → R10, `a93e60b`).
- [x] **…pero que su aura cuente para alguna clase.** ✅ 2026-10-17: fuera de horario, una publicación normal cuenta para la clase que tuviste más recientemente según el horario. Tareas, exámenes y el selector siguen preguntando. Con más de una clase y ninguna en horario, `resolve_default_class` devuelve `None` y el aura que reciba ese post no cuenta para nadie. Agregar el último paso: la clase más reciente. Test en `attribution`.
- [ ] **Justificar faltas.** Cada falta injustificada vale −10, y hoy no hay forma de justificar ninguna. El esquema ya existe (`attendance_records.justification_*`) y el motor ya respeta `justification_status = approved`; faltan endpoints y UI. Primero lo mínimo: el profesor marca una falta como justificada desde el panel de clase; la falta sigue visible, tachada y con etiqueta "justificada" (Mario, 2026-10-17). Después: el alumno sube su comprobante (R2) y el profesor aprueba/rechaza.
- [ ] **Bug 2** — borrar tu entrega más reciente pierde la tarea. Con archivos en producción, borrar y reentregar ya es cosa de todos los días.
- [ ] **Publicaciones largas colapsadas.** En el feed, un post largo se corta a 6 líneas (Mario, 2026-10-17) con "ver más" que lo expande en su lugar. El hilo siempre lo muestra completo.

## Bloque 2 — Aura: validar desde el feed
El like se llama **aura** en toda la app (copy final de Mario). Nada cambia en el motor: sigue siendo la curva cóncava, y el aura del profesor sigue sin dar puntos.
- [ ] **Renombrar like → aura** en el módulo de strings.
- [ ] **El aura del profesor sobre una participación la valida.** Dar aura = `reviewed_at`; son el mismo hecho, así que "Validar" en `/revisar` también enciende el aura y viceversa. No mueve puntos — `test_reviewing_moves_no_points` sigue siendo el guardián.
- [ ] **Quitar el aura des-valida** (decisión de Mario, 2026-10-09): `reviewed_at` vuelve a nulo y la participación regresa a la cola de `/revisar`. Tampoco mueve puntos.
- [ ] **Vetar desde el feed.** En la tarjeta de una participación, el profesor tiene "Vetar" con el mismo diálogo de confirmación de `/revisar`. Aura (validar) y vetar siguen siendo dos controles distintos; nunca uno solo.
- [ ] **El aura del profesor no reordena el feed.** Hoy cada like sube `last_activity_at`: validar 30 participaciones las manda todas arriba. Primer paso barato del Bloque 4 — los likes dejan de subir posts; sólo las respuestas lo hacen.

## Bloque 3 — Perfil
Principio de Mario: si aparece un username, se le puede dar click y llegar al perfil.
- [ ] **`/u/:username`** — todo username y avatar en la app enlaza aquí.
- [ ] **Contenido:** foto, bio, aura recibida (el conteo). Sus publicaciones debajo.
- [ ] **Tu propio perfil:** editas la bio ahí mismo y cambias tu foto (subida a R2; hoy `avatar_url` es la de Google).
- [ ] **Calificación en el perfil:** sólo la ve el dueño y el profesor. El profesor ve el desglose completo (el mismo del panel de clase).

## Bloque 4 — Algoritmo del feed
Problema (Mario): la interacción sube posts y algunos se quedan arriba sin ser relevantes. Lo que se quiere: una vez que interactuaste con un post, baja **para ti** y deja lugar a lo nuevo.
- [ ] **Spec primero.** Puntaje por post y por espectador: frescura + actividad reciente − penalización si ya interactuaste (aura, respuesta, validación). Implica dejar la paginación keyset sobre `last_activity_at` — la razón por la que hoy no se hizo. Retoma la idea de `future.md` (prioridad a no vistos, afinidad).
- [ ] Implementación + tests del ranking como funciones puras, igual que el motor de calificación.

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
