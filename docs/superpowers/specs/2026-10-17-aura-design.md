# Bloque 2 — Aura: validar desde el feed

**Estado:** diseño aprobado por Mario el 2026-10-17, sección por sección. Roadmap Bloque 2.

## Objetivo

En clase, Mario recorre el feed, da aura a las participaciones buenas, veta la rara mala, y `/revisar` termina vacío sin haberlo abierto. Validar deja de ser un trámite aparte: es el mismo gesto que dar aura.

## Decisiones (todas de Mario)

1. **"Like" se llama aura** en toda la app.
2. **El aura del profesor sobre una participación la valida.** Dar aura = `reviewed_at`. "Validar" en `/revisar` enciende el aura y viceversa.
3. **Quitar el aura des-valida** (2026-10-09): `reviewed_at` vuelve a nulo y la participación regresa a la cola.
4. **"Marcar todas como revisadas"** en `/revisar` también da aura a cada una.
5. **El aura del profesor sigue sin dar puntos.** Es lo que ya hace el código (`award_like` devuelve `None` para un profesor) y significa que validar en bloque no mueve ninguna calificación.
6. **Sólo las participaciones se validan.** El aura del profesor sobre una publicación normal o una entrega es sólo aura.
7. **Todos ven el aura del profesor** (opción C, 2026-10-17): una marca discreta en el post.
8. **Vetar desde el feed**, con el mismo diálogo de confirmación que `/revisar`. Aura (validar) y vetar siguen siendo dos controles distintos, nunca uno solo — ver R8.
9. **El aura no reordena el feed.** Ningún aura (de alumno ni de profesor) sube `last_activity_at`; sólo las respuestas lo hacen.
10. **Lo ya validado recibe el aura, y lo que ya tenía aura del profesor queda validado** — una migración de datos, para que las dos cosas nunca discrepen.

## Arquitectura: dos campos, una sola función

Se conservan los dos registros que ya existen — la fila en `likes` y `posts.reviewed_at` — y se escriben siempre juntos desde un solo lugar. Se descartó derivar "validada" de la existencia del like (tira `reviewed_at`, que el incidente del 2026-08-03 demostró que vale como registro propio, y convierte cada consulta de la cola en un join) y se descartó derivar el aura de `reviewed_at` (el conteo de aura no incluiría la del profesor justo cuando la decisión 7 la hace visible).

### `services/aura.py`

`set_teacher_aura(db, post, teacher, on: bool)`:
- **on:** crea el `Like` si no existe y suma 1 a `like_count`; si el post es una participación de una clase que este profesor imparte, fija `reviewed_at = now`, `reviewed_by = teacher.id`.
- **off:** borra el `Like` si existe y resta 1 a `like_count`; si es participación de su clase, `reviewed_at = reviewed_by = NULL`.
- Idempotente. Nunca otorga ni revoca puntos. Nunca toca `last_activity_at`. No hace `commit`: lo hace quien llama, para que el lote siga siendo todo-o-nada.

### Puntos de entrada

| Endpoint | Hoy | Después |
|---|---|---|
| `POST /api/posts/{id}/like` | alterna el like, sube `last_activity_at` | si quien da aura es profesor → `set_teacher_aura(on = not existing)`. El aura de un alumno, como hoy (con puntos). **Nadie sube el post.** |
| `POST /api/posts/{id}/reviewed` | fija `reviewed_at` | `set_teacher_aura(on=True)` |
| `DELETE /api/posts/{id}/reviewed` | limpia `reviewed_at` | `set_teacher_aura(on=False)` |
| `POST /api/review/participaciones/reviewed` | fija `reviewed_at` en cada id | `set_teacher_aura(on=True)` en cada id, todo-o-nada |

Las validaciones de permisos de cada endpoint no cambian. El aura de **otro** profesor (no el de la clase) es aura simple: crea el like, no valida.

### Veto

Sin cambios en el backend. Vetar sigue revocando los taps y el aura recibida (sin evidencia no hay puntos); **no** toca el aura del profesor ni `reviewed_at`, así que quitar el veto deja el post como estaba. Mientras está vetado o borrado no se puede dar ni quitar aura: `/like` ya exige `status = active`.

### `PostOut.teacher_aura: bool`

Verdadero si algún usuario con rol `teacher` tiene un like en el post. Se calcula con una sola consulta por página/hilo (como `_liked_ids`) y viaja a todos los espectadores, alumnos incluidos.

### Renombre en el backend

Sólo textos de error ("No puedes darle aura a tu propia publicación"). La API conserva los nombres `like` (`/like`, `like_count`, `liked_by_me`, tabla `likes`, `source_type = forum_like`): renombrarlos rompería clientes sin ganar nada.

## Migración (sólo datos)

`alembic/versions/<rev>_teacher_aura_validates.py`:
1. Toda participación con `reviewed_at` cuyo profesor de clase no tenga like en ella → insertar `Like(user_id = classes.teacher_id, post_id, created_at = reviewed_at)` y `like_count += 1`.
2. Toda participación con like del profesor de su clase y `reviewed_at` nulo → `reviewed_at = likes.created_at`, `reviewed_by = teacher_id`.

Nunca crea un like del profesor sobre su propio post (el endpoint los prohíbe). No toca `last_activity_at`. Idempotente. `downgrade()` no hace nada: sólo completó datos faltantes.

## Frontend

### Botón de aura (`PostCard`)
- Icono `RiSparkling2Line` / `RiSparkling2Fill` (reemplaza el corazón); encendido en color primario, no en rojo.
- Cuando `teacher_aura` es verdadero, una marca de texto discreta tras el conteo: `✦ 12 · profe` (copy provisional en `es.ts`).
- Optimista con rollback visible, como ya hace `likes.ts`; si quien toca es profesor, también alterna `teacher_aura`. Se borra el comentario de `likes.ts` que rodeaba el salto del feed.
- Sin etiqueta "Validada" aparte: para el profesor, el aura encendida en una participación **es** la validación.

### Vetar desde el feed
- En una participación de su clase, el profesor ve **Vetar** en la fila de acciones de la tarjeta, separado del aura (un toque errado en uno no cae en el otro), con estilo destructivo. Abre el mismo diálogo que `/revisar`.
- El diálogo sale de `Revisar.tsx` a `components/VetoDialog.tsx`, usado por ambos — un solo copy que no puede divergir.
- En una participación vetada: **Quitar veto**, sin diálogo (es la dirección segura).
- Tras vetar o quitar el veto se invalidan feed, hilo, cola de `/revisar` y calificaciones.

### Renombre (placeholders; Mario escribe el copy final)
Sólo en `strings/es.ts`: "Me gusta" → "Dar aura", "Likes recibidos" → "Aura recibida", "{n} likes" → "{n} de aura", "Curva de likes" → "Curva de aura", "100 likes = {n} puntos" → "100 de aura = {n} puntos", "Puntos base por like" → "Puntos base por aura", "Cada like nuevo vale menos que el anterior" → "Cada aura nueva vale menos que la anterior", y el resto de menciones.

### Limpieza en la tarjeta
`PostCard` usa tres emojis como UI, contra `CLAUDE.md`: 💬 → `RiChat3Line`, 🗑 → `RiDeleteBinLine`, 👨‍🏫 → etiqueta de texto "profe" junto al nombre.

## Tests

**Backend** (primero, TDD):
- Por cada punto de entrada (aura, Validar, Quitar validación, lote): después, el like del profesor y `reviewed_at` **coinciden**.
- Quitar el aura devuelve la participación a la cola pendiente.
- Aura del profesor en una publicación normal o en una entrega: like sí, `reviewed_at` no.
- Ninguna acción del profesor cambia el total del alumno (extiende `test_reviewing_moves_no_points`).
- Ningún aura cambia `last_activity_at`; una respuesta sí.
- `teacher_aura` es verdadero para cualquier espectador, alumno incluido.
- Vetar un post con aura del profesor conserva aura y `reviewed_at`; quitar el veto lo restaura igual.
- El aura de otro profesor no valida una participación de esta clase.
- Migración: base sembrada con ambos casos (validada sin like, like sin validar) queda consistente; correrla dos veces no cambia nada. En PostgreSQL en CI.

**Frontend:** test de `likes.ts` — el optimista alterna `teacher_aura` para un profesor y hace rollback al fallar. Tipos, lint y build. QA en el teléfono tras desplegar: dar aura, ver `/revisar`, vetar desde el feed.

## Orden de commits (cada uno desplegable)

1. `set_teacher_aura` + endpoints + el aura deja de subir posts.
2. Migración.
3. `PostOut.teacher_aura`.
4. Frontend: botón de aura, marca "profe", vetar desde el feed, `VetoDialog`.
5. Renombre a aura + limpieza de emojis.

## Fuera de alcance

- Cualquier cambio al motor de calificación o a la curva cóncava.
- Ranking del feed más allá de "el aura no sube posts" (Bloque 4, incluidos los comentarios en el feed).
- Notificaciones de aura recibida (Bloque 5).
