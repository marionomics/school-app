# Justificar faltas — paso 1 (el profesor justifica)

**Estado:** aprobado por Mario el 2026-10-17 (la falta justificada queda visible, tachada y con etiqueta). Roadmap Bloque 1.

## Problema

Cada falta injustificada vale −10 (un punto entero en la escala de 10), y hoy no hay forma de justificar ninguna. El esquema ya lo tiene (`attendance_records.justification_*`) y el motor ya lo respeta: `faltas_breakdown` sólo cuenta faltas con `justification_status` distinto de `approved`. Faltan endpoints y UI.

## Alcance

**Paso 1 (este spec):** el profesor marca o desmarca una falta como justificada desde el panel de clase.
**Paso 2 (después, spec propio):** el alumno sube su comprobante (R2, `justification_file_key` + `justification_text`), queda `pending`, y el profesor aprueba o rechaza.

## Decisiones

1. **Justificar = `justification_status = "approved"`**, con `reviewed_by` / `reviewed_at`. Quitar la justificación la regresa a `NULL` (en el paso 2 regresará a `pending` si el alumno subió algo). No se escribe en `points_ledger`: las faltas nunca han vivido en el ledger, se calculan desde `attendance_records`, y el motor no cambia.
2. **Sólo una `absent` se justifica.** Un retardo o una asistencia no tienen nada que justificar → 422.
3. **Pasar lista no borra justificaciones.** Hoy `PUT /api/sessions/{id}/attendance` borra todos los registros de la sesión y los vuelve a insertar: volver a guardar la lista de un día borraría en silencio la justificación y regresaría el −10. Se vuelve un upsert por alumno: cambia `status`, conserva los campos `justification_*`, y borra sólo a los alumnos que ya no vienen en la lista. Si una falta justificada pasa a `present` y luego otra vez a `absent`, la justificación sigue ahí.
4. **Visible, tachada, con etiqueta** (Mario). En la hoja del alumno en el panel de clase aparece la lista de sus faltas por fecha. Una justificada se ve tachada con la etiqueta "Justificada" y ya no cuesta. Cada fila es una fecha más su único control — la misma excepción a "un control por línea" que el roster de exámenes y pasar lista.
5. **Actualización optimista con rollback visible**, y al confirmar se invalidan la calificación del alumno y el roster.

## API

- `GET /api/classes/{class_id}/students/{student_id}/faltas` (profesor dueño) → `{"faltas": [{"record_id", "date", "justified"}]}`, más recientes primero. Todas las `absent`, justificadas o no.
- `PUT /api/attendance/{record_id}/justification` (profesor dueño de la clase de la sesión), cuerpo `{"justified": bool}` → `{"record_id", "justified"}`.

## Tests

- Justificar quita el −10 del total; quitar la justificación lo regresa.
- Volver a guardar pasar lista conserva la justificación.
- Sólo una falta se justifica (422 en `present`/`late`); otro profesor → 403; un alumno → 403.
- La lista de faltas incluye las justificadas, marcadas.
