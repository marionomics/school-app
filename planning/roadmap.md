# Roadmap — Plataforma v2

Objetivo: v2.0 en producción para el inicio del semestre (ago/sep 2026).
Cada fase se despliega a Railway y se prueba antes de pasar a la siguiente.

## Fase 0 — Cimientos (semana 1)
- [x] Scaffold monorepo (`backend/` FastAPI + Alembic, `frontend/` React + Vite + shadcn preset)
- [x] Auth con Google Identity Services + sesiones
- [x] Onboarding: username único + bio al primer login
- [x] Clases: crear (con horario, fechas, pesos), unirse por código, link de invitación
- [x] Config lista para Railway (FastAPI sirve el build de Vite) + PostgreSQL — código listo, CI en GitHub Actions
- [x] Deploy real a Railway (crear proyecto, conectar repo, variables de entorno, dominio en Google OAuth) — hecho 2026-07-30: https://school-app-production-e9f4.up.railway.app (build por Dockerfile, no Nixpacks). Falta dominio propio.

## Fase 1 — El feed (semanas 2–3)
- [x] Posts, replies (3 niveles), likes
- [x] Attachments vía R2 (fotos, PDFs)
- [x] Feed global cronológico con skeleton loading
- [x] Post tipo participación: botón de taps (1–3) con animación
- [x] Points ledger (append-only, revocación)
- [x] Chip de calificación en vivo + desglose completo
- [ ] 🧪 Primera versión probable con usuarios reales — pendiente, depende del deploy real a Railway

## Fase 2 — La economía completa (semanas 4–5)
- [x] Posts tipo tarea (solo teacher; tarea default domingo) — examen en 2b
- [x] Toggle "Es mi entrega" en replies + preview de penalización
- [x] Auto-score por lateness (100/90/50/20) — override del profe en 2b
- [x] Motor de calificación completo (rubros + ledger + faltas) con tests
- [x] **2b-1 Calificar** — exámenes (papel y digital) 1–10, `graded_at`, override del profe, sección Revisar (3 pestañas), calificar desde el feed, regla de rubro vacío a fin de curso
- [x] **2b-2 Configurar** — puntos extra configurables (incentives) + admin, UI de configuración de clase (pesos, `tap_value`, `like_value`, `like_exponent`)

## Fase 3 — Listo para clases (semana 6)
- [x] Asistencia mínima: sesiones desde horario, lista tap-por-alumno, −10/100 por falta injustificada (un punto entero)
- [x] Panel de clase: roster, lista de calificaciones → perfil con desglose
- [x] Polish pass móvil + seed data
- [ ] Beta con ex-alumnos

## → Inicio de semestre: v2.0 live

## Medio semestre
- [ ] Asistencia swipe (estilo Tinder) con retardos automáticos por hora
- [ ] Justificación de faltas (alumno sube comprobante → aprobar → excused)
- [ ] Notificaciones 🔔 (likes, comentarios, menciones; filtros y agrupación temporal)
- [ ] Moderadores (anónimos, solo sobre otras clases, capibara)
- [ ] Protocolo "Salvando el semestre" (multiplicadores aleatorios)
- [ ] Link previews + embeds de YouTube/Loom
- [ ] Reglas de exención (licenciatura ≥ 8.5)
- [ ] UI de ghosts 👻 y polizones 🥷

## Largo plazo
Ver `future.md`.
