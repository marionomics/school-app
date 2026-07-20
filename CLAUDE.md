# CLAUDE.md

Context for Claude Code when working on this project.

## Project Status

**v2 rebuild from zero, in progress.** v1 is fully archived on branch `v1-archive` (tag `v1-final`) — never resurrect its schema; its data model (per-class forum, separate participation system) is exactly what v2 discards. Reuse v1 *logic* only where the spec says so (Google auth flow, R2 helpers, lateness rules).

**Read first:**
- `docs/superpowers/specs/2026-07-19-v2-platform-rebuild-design.md` — the approved design spec (source of truth)
- `planning/roadmap.md` — phases and current progress
- `planning/bugs.md`, `planning/changelog.md`, `planning/future.md`

## What This Is

A classroom platform where **the forum feed is the center of everything**: tareas, exámenes, and in-class participaciones are all posts. Grades are computed in real time from feed activity + attendance. Closer to Threads than to an LMS. Explicitly NOT a Google Classroom clone — no administrative-surveillance mindset.

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy, Alembic (real migrations — no ad-hoc ALTER TABLE), pytest
- **Frontend:** React + Vite + shadcn (preset `b3SkwD0Ou`), Tailwind, mobile-first
- **DB:** SQLite (quick local) / PostgreSQL (prod and CI tests)
- **Storage:** Cloudflare R2 (presigned URLs, keys never exposed)
- **Auth:** Google Identity Services; roles `student`/`teacher` (`TEACHER_EMAIL` env)
- **Deploy:** Railway, single service — FastAPI serves `frontend/dist`

## Repo Layout

```
backend/    FastAPI app
frontend/   React app
planning/   roadmap, bugs, changelog, future (planning/archive-v1/ is local-only, never commit)
docs/       specs and plans
```

## ⚠️ Grading Philosophy — do NOT "fix" this

- Scale 0–100. **"Una décima"** (10-scale) = **1 point** (100-scale). Mario sometimes says "points" meaning décimas — always clarify.
- Default rubros: Tareas 30 + Exámenes 30 = 60. **The missing ~40 is intentional** — it's filled by participaciones/forum/extras, which are **uncapped**. Never make weights sum to 100, never warn that they don't, never suggest filling the gap.
- Formula: `Final = Tareas + Exámenes + Ledger − Faltas` (see spec §4).
- 1 participation tap = 1 pt (max 3 taps). 1 like received = 1 pt, linear, no cap for now (configurable in `points_config`; cap design is an open question in `planning/future.md`).
- Faltas injustificadas: −1 pt each.
- Grades are always **computed, never stored**. Every grade-affecting event is an append-only `points_ledger` row; veto = revocation flag, never DELETE.
- Participaciones auto-count on publish; the teacher vetoes exceptions (never a routine approval queue).

## Core Model Rules

- **The post is the atom.** `posts.type ∈ {regular, participacion, tarea, examen}`; replies are posts (`parent_id`, max 3 levels); an entrega is a reply with `is_entrega = true`.
- The feed is **global** (all classes, all semesters). `posts.class_id` only marks which class a post counts for.
- `deleted` ≠ `vetoed`: deletion keeps earned points; veto revokes them.
- Lateness auto-score: 100 / 90 (<24 h) / 50 (<1 wk) / 20. All entregas accepted, penalty automatic.
- Enrollment status: `active`, `ghost` 👻 (course over — posts yes, points no), `polizon` 🥷 (guest — points no).
- Puntos extra are `incentives` rows, configurable in-app. **Never hardcode incentive types.**

## Development Rules

- **Mobile first.** Design and QA on a phone viewport before desktop.
- **Copy:** draft all user-facing text as placeholders in the single strings module; **Mario writes final copy**. Spanish at launch, English-ready structure.
- **Testing:** the grade engine is pure functions and the most-tested code in the repo. CI runs against PostgreSQL.
- Skeleton loading + optimistic updates (with visible rollback) are the norm, not polish.
- Each roadmap phase deploys to Railway before the next begins.
