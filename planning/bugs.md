# Bugs

Bugs conocidos de la v2. Formato: estado, descripción, cómo reproducir, notas.

| # | Estado | Descripción | Fase |
|---|--------|-------------|------|
| 1 | Abierto (solo dev) | En SQLite los `DateTime(timezone=True)` se guardan sin offset, así que la API devuelve `"2026-07-29T21:00:00"` en vez de `...+00:00`. El navegador lo interpreta como hora local, por lo que en dev local todo post de las últimas ~6 h dice "ahora" y las fechas del desglose de calificación pueden correrse un día. En PostgreSQL (prod y CI) el offset sí viaja y todo se ve bien. Repro: `npm run dev` contra SQLite, publicar algo, esperar una hora → sigue diciendo "ahora". Fix propuesto: helper `parseApiDate` en `frontend/src/lib/feed.ts` que le agregue `Z` a los timestamps sin offset, usado por `PostCard` y `GradeChip`. | 1 |

## Resueltos

(ninguno)
