# Plataforma de clases v2 — Design Spec

**Date:** 2026-07-19
**Status:** Approved design, pre-implementation
**v1:** archived on branch `v1-archive` (tag `v1-final`). Railway deployment decommissioned.

## 1. Purpose and philosophy

A classroom platform rebuilt from zero around one idea: **the forum feed is the center of everything**. Tareas, exámenes, and in-class participaciones all live in the feed as posts. Grades are computed in real time from feed activity plus attendance.

Design principles (from "Mi filosofía de desarrollo"):

- **The teacher's job is to teach.** Every recurring teacher chore must be eliminated, automated, or distributed to students. Records are a *byproduct* of the workflow, never a separate capture task. This is explicitly *not* a Google Classroom clone — no administrative-surveillance mindset.
- **For students, the app must be entertaining** — closer to Threads/X than to an LMS. Engagement is the currency of the grade economy.
- **Mobile first.** Nearly all usage is on phones. Every screen is designed phone-first.
- **This is a tool, not a hardcoded ruleset.** Point values, caps, incentives, and weights are configurable in-app wherever reasonable.
- **Copy:** Claude drafts all user-facing copy as placeholders; **Mario writes the final copy**. All strings live in one file to make this easy.

## 2. Architecture

```
school-app/
├── backend/          FastAPI + SQLAlchemy + Alembic + pytest
├── frontend/         React + Vite + shadcn (preset b3SkwD0Ou), Tailwind
├── planning/         roadmap.md, bugs.md, changelog.md, future.md
├── docs/             specs and plans
└── CLAUDE.md
```

- **Dev:** Vite dev server proxies `/api/*` → uvicorn (port 8000). SQLite locally.
- **Prod:** FastAPI serves built `frontend/dist`. One Railway service + Railway PostgreSQL + existing Cloudflare R2 bucket for files.
- **Migrations:** Alembic from day one. No ad-hoc `_ensure_columns()` (v1 pain point: SQLite-works/Postgres-breaks).
- **CI/tests run against PostgreSQL**, not just SQLite, to catch FK-enforcement differences by construction.
- **Auth:** Google Identity Services (client-side button) → backend verifies ID token → session token. Same flow as v1 (logic reused, code rewritten).
- **Roles:** `student` (default), `teacher` (via `TEACHER_EMAIL` env). Moderator is a future per-user flag, not a role.
- **Language:** Spanish UI at launch. All copy in a single strings module so English can be added as a second strings file later.

## 3. Data model

The **post is the atomic unit**. Nine core tables:

### users
`id, google_id, email, name, username (unique), bio, avatar_url, role (student|teacher), grade_is_private (bool), created_at`
- Username + bio prompted at first login (social-network identity).
- `grade_is_private`: hides grade from classmates; the teacher always sees it.

### classes
`id, name, code (unique join code), teacher_id, start_date, end_date, schedule_json, tareas_weight (default 30), examenes_weight (default 30), attendance_required_pct (default 80), created_at`
- `schedule_json`: weekdays + start/end times (e.g., Mon–Thu 10:00–11:00). Drives attendance-session suggestions and default class attribution for participaciones.
- Join by code; shareable invite link.

### enrollments
`id, user_id, class_id, status (active|ghost|polizon), joined_at`
- `ghost` 👻: course ended; can still post/comment, earns no points.
- `polizon` 🥷: invited guest; no obligations, earns no points.

### posts
`id, author_id, type (regular|participacion|tarea|examen), class_id (nullable), parent_id (nullable), is_entrega (bool), content, taps (1–3, participacion only), due_date, max_points, status (active|deleted|vetoed), created_at, edited_at`
- **The feed is global** — all classes, all semesters, one feed. `class_id` only marks which class a post *counts for* (points, deadlines).
- Replies are posts with `parent_id`. Max 3 levels: post → comment → comment-on-comment.
- `tarea`/`examen` types are teacher-only. Default tarea due date: next Sunday. Exámenes carry an entrega window (e.g., 24 h).
- `is_entrega`: a reply to a tarea/examen flagged by the student as their formal submission (toggle in the reply composer; off = normal comment/question).
- `deleted` ≠ `vetoed`: deleting a post does **not** remove points already earned; a veto does (via ledger revocation).

### attachments
`id, post_id, file_key (R2), file_name, file_size, mime_type, created_at`
- R2 storage, presigned download URLs, `file_key` never exposed directly. Same validation rules as v1 (types, 10 MB).

### likes
`id, user_id, post_id, created_at` — unique per (user, post). No self-likes counted for points; teacher likes don't generate points.

### points_ledger
`id, user_id, class_id, source_type (participacion|forum_like|incentive|penalty|bonus|adjustment), source_id, points, note, created_at, revoked_at, revoked_by`
- **Every grade-affecting event is one append-only row.** Rows are never deleted or edited; revocation is a flag.
- Teacher veto = revoke the row(s). Fully auditable; no silent grade drift.
- "Salvando el semestre" bonuses, puntos extra awards, and manual adjustments are all just rows.

### reviews
`id, entrega_post_id, reviewer_id, score, auto_score, feedback, created_at, updated_at`
- One review per entrega. `auto_score` = lateness-derived default; `score` = final (teacher may override).
- Examen reviews are scored 1–10.

### class_sessions + attendance_records
- `class_sessions`: `id, class_id, date, opened_at, closed_at`
- `attendance_records`: `id, session_id, user_id, status (present|absent|late|excused), justification_text, justification_file_key, justification_status (null|pending|approved|rejected), reviewed_by, reviewed_at`
- Justification fields exist in schema from day one; the student-facing flow ships mid-semester.

### points_config (per class, with sensible global defaults)
`tap_value (default 1.0), like_value (default 1.0), like_cap (nullable, default NULL = no cap), daily_post_limit (default 5), …`
- Tunable in-app without redeploys. The anti-cramming / cap design is an **open question** deliberately deferred (see future.md).

### incentives (puntos extra — configurable, never hardcoded)
`id, class_id, name, description, points_value, active, created_at`
- Examples: libreta completa, todo en inglés, moderador. Awarding one writes a ledger row referencing the incentive.

## 4. Grade engine

One pure function: `calculate_grade(user_id, class_id) → breakdown`. Always computed, never stored. Scale 0–100 ("una décima" on the 10-scale = 1 point on the 100-scale).

```
Final = Tareas + Exámenes + Ledger − Faltas

Tareas   = mean(score% across all tarea posts of the class) × tareas_weight
           · a tarea with no entrega counts as 0%
           · score% default = auto-score by lateness; teacher can override
Exámenes = mean(score/10 across examen posts) × examenes_weight
Ledger   = Σ non-revoked ledger rows for (user, class)
           · participaciones: taps × tap_value (1 tap = 1 pt)
           · forum likes: likes received × like_value (1 like = 1 pt), linear,
             no cap for now (like_cap config exists, default off)
           · + incentives, + bonuses, − penalties
           · UNCAPPED by design — can exceed the missing 40 and pass 100
Faltas   = −1 pt per unjustified absence (status = absent)
```

- **Lateness auto-score:** on time = 100 %, < 24 h late = 90 %, < 1 week = 50 %, after = 20 %. All entregas accepted; the penalty is automatic so emergencies need no special handling.
- **The gap is the incentive.** Default rubros sum to 60. The remaining ~40 comes from participaciones/forum/extras, uncapped. **Never "fix" the weights to sum to 100. Never warn that they don't.** A student could in theory reach 100 with participaciones alone.
- Ghost and polizon enrollments earn nothing (posts allowed, no ledger rows).
- **Participación flow:** student writes the explanation (required, must be validatable), taps the big button 1–3 times, publishes. Points count **immediately** (auto-count); the teacher vetoes exceptions rather than approving the routine.
- Participación default class attribution: the class currently in session per schedule; otherwise the student picks.
- **Exención (future):** licenciatura ≥ 8.5 exempts ordinario. MVP only displays the grade; exención rules become class settings mid-semester.

## 5. UX

### Student
- **Home = global feed**, chronological (v1 algorithm), Threads-like cards with type badges (Participación ×2 / Tarea · entrega domingo / Examen). Persistent **grade chip** at the top → tap opens full real-time breakdown (rubros, ledger detail, faltas).
- **Composer (+):** full-screen, distraction-free. Attach photos/files. Participación mode = big tap button (1–3 taps) with satisfying animation — the soul of v1, kept and honored.
- **Reply to tarea/examen:** "Es mi entrega" toggle; shows the lateness penalty *before* confirming.
- **Sidebar:** Perfil/bio, Mis clases (join/share code), Mis entregas, Mis faltas, Configuración. Bottom bar: Home · ➕ · (🔔 future) · Perfil.
- Skeleton loaders everywhere; optimistic likes/taps with visible rollback on failure.

### Teacher
- Same feed. Composer gains a type selector (regular default / tarea / examen).
- **Grade from the feed:** entrega replies show auto-score inline; tap to override.
- **Revisar** (sidebar): entregas pending review grouped by tarea; recent participaciones with one-tap veto; justificaciones queue (mid-semester).
- **Clases:** per-class panel — roster with status icons (👻🥷), grade list → student profile with full breakdown, class settings (weights, points_config, incentives).
- **Pasar lista:** during scheduled hours a banner offers to open the session. MVP = full-screen list, one tap per student (presente/falta/retardo). Swipe UX replaces it mid-semester.

## 6. Roadmap

- **Phase 0 — Cimientos (wk 1):** monorepo scaffold, Alembic, Google auth, username/bio onboarding, classes with schedule, deploy skeleton to Railway.
- **Phase 1 — El feed (wks 2–3):** posts/replies/likes, attachments, global feed with skeletons, participación + ledger + grade chip. First real-user testable version.
- **Phase 2 — La economía completa (wks 4–5):** tarea/examen types, entrega toggle, auto-score + override, Revisar queue, full grade engine, incentives admin, veto flow.
- **Phase 3 — Listo para clases (wk 6):** minimal attendance + faltas penalty, class panel, polish, seed data, beta with ex-students.
- **→ Semester start (Aug/Sep 2026): v2.0 live.**
- **Mid-semester:** swipe attendance, justificaciones, notifications, moderators (anonymous, cross-class only), salvando el semestre, link previews/YouTube embeds, exención rules, ghost/polizon UI.
- **Long term:** wiki (integrate vs build — open), `[[]]` wiki tagging, `@` mentions, DMs, feed algorithm, cryptographic attendance, voice-note tareas, English mode, Skool integration.

Details live in `planning/roadmap.md` and `planning/future.md`.

## 7. Error handling & testing

- **Grade engine = pure functions**, the most-tested code: pytest unit tests for lateness boundaries, revocation, ghost/polizon exclusion, faltas, zero-tareas edge cases, weight changes mid-course.
- **Ledger invariants:** append-only, revoke-not-delete, enforced at the service layer.
- **API:** consistent JSON error shape `{error: {code, message}}`; frontend shows Spanish toasts, never blank screens.
- **Tests against PostgreSQL in CI**; SQLite only for quick local runs.
- **Per-phase QA on a real phone**, each phase deployed to Railway before the next begins.

## 8. Open questions (tracked in planning/future.md)

1. **Like-points cap / anti-cramming:** deliberately deferred. Desire: discourage last-minute point farming without cobra effects. Config supports a cap; decision pending real usage data.
2. **Wiki:** integrate (Docmost / wiki.js / BookStack) vs build minimal MD+LaTeX wiki. Needs points-system integration either way.
3. **Moderator incentives:** fixed punto extra vs open sign-up with per-action rewards.
4. **DMs:** maybe never; note leans "probably worth it for engagement". Decide after notifications ship.
5. **Exención mechanics** per program type (licenciatura vs posgrado).
