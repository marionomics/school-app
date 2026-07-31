# Bugs

Bugs conocidos de la v2. Formato: estado, descripción, cómo reproducir, notas.

| # | Estado | Descripción | Fase |
|---|--------|-------------|------|
| 2 | Abierto | Borrar tu entrega más reciente pierde la tarea entera. Marcar una entrega nueva apaga `is_entrega` en las anteriores (latest-wins, `posts.py`), y el motor sólo mira entregas `status = "active"` (`_counting_entrega` en `services/grades.py`). Secuencia: entrego A → entrego B (A queda apagada) → borro B ⇒ ninguna entrega cuenta y la tarea vale 0, aunque la regla es que borrar conserva los puntos ganados. Repro: dos entregas a la misma tarea y borrar la segunda. Fix propuesto: al borrar una entrega, reactivar la última entrega activa anterior del mismo alumno en esa tarea; o que `_counting_entrega` caiga a la anterior cuando la última está borrada. | 2a |
| 1 | Abierto (solo dev) | En SQLite los `DateTime(timezone=True)` se guardan sin offset, así que la API devuelve `"2026-07-29T21:00:00"` en vez de `...+00:00`. El navegador lo interpreta como hora local, por lo que en dev local todo post de las últimas ~6 h dice "ahora" y las fechas del desglose de calificación pueden correrse un día. En PostgreSQL (prod y CI) el offset sí viaja y todo se ve bien. Repro: `npm run dev` contra SQLite, publicar algo, esperar una hora → sigue diciendo "ahora". Fix propuesto: helper `parseApiDate` en `frontend/src/lib/feed.ts` que le agregue `Z` a los timestamps sin offset, usado por `PostCard` y `GradeChip`. | 1 |

## Resueltos

(ninguno)
