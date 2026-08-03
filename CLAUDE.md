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
- **Frontend:** React + Vite + Tailwind, mobile-first. shadcn style **`base-sera`** on `@base-ui/react`, base color zinc, icons from **`@remixicon/react`** — all of it already configured in `frontend/components.json`. Angular, uppercase-labelled, Geist.
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
- 1 participation tap = 1 pt (max 3 taps) — **linear**, always.
- Likes received are **concave**: `like_value × N^like_exponent`, default exponent `0.5`. So 100 likes = 10 pts, and a 10 earned purely from likes needs 10,000. Per-class configurable; `like_exponent = 1.0` restores linear. The curve *is* the anti-cramming mechanism, so `like_cap` stays off (this closed open question 1 in `planning/future.md`).
- Faltas injustificadas: **−10 pts (100-scale) each** — un punto entero (1.0 on the 10-scale, 10 décimas), NOT una décima.
- Grades are always **computed, never stored**. Every grade-affecting event is an append-only `points_ledger` row; veto = revocation flag, never DELETE.
- The ledger is the **event log**; the engine applies the maths. For participaciones, incentives, bonuses and penalties the contribution is `Σ row.points`. For likes it is **not** — the engine counts non-revoked `forum_like` rows and applies the concave curve, because the nth like is worth `√n − √(n−1)`, not 1. Never "fix" this by summing like rows.
- Participaciones auto-count on publish; the teacher vetoes exceptions (never a routine approval queue).

## Core Model Rules

- **The post is the atom.** `posts.type ∈ {regular, participacion, tarea, examen}`; replies are posts (`parent_id`, max 3 levels); an entrega is a reply with `is_entrega = true`.
- The feed is **global** (all classes, all semesters). `posts.class_id` only marks which class a post counts for.
- **No evidence, no points.** Both `deleted` and `vetoed` revoke what the post earned — the taps *and* the likes it received. A participación is its own evidence: if the post is gone or invalidated, nothing backs the points. Deleting and reposting is not a way to bank points twice. `deleted` ≠ `vetoed` is about *who acted and what stays visible* (author removes it vs teacher invalidates it, with a reason, post still in the thread), never about the ledger.
- Lateness auto-score: 100 / 90 (<24 h) / 50 (<1 wk) / 20. All entregas accepted, penalty automatic.
- Enrollment status: `active`, `ghost` 👻 (course over — posts yes, points no), `polizon` 🥷 (guest — points no).
- Puntos extra are `incentives` rows, configurable in-app. **Never hardcode incentive types.**

## Development Rules

- **Mobile first.** Design and QA on a phone viewport before desktop.
- **Use the preset components as they arrive.** Add them with `npx shadcn add`; never restyle a primitive, never edit `--radius` or strip `uppercase` to make something look softer. If a component is wrong for a surface, pick a different one. Reaching for a hand-rolled `<input className="border …">` is how the app ended up with twelve different guesses at what a form field looks like.
- **One control per line** in any form. The only exception is a list row pairing a person with the one thing you're setting — the examen roster and pasar lista.
- **Every points value goes through `formatPoints`** (`frontend/src/lib/points.ts`). One point on the 100-scale is one décima; a bare number is how that gets misread by a factor of ten.
- Icons come from `@remixicon/react`. Emojis are not UI — the only survivors are 👻 ghost and 🥷 polizón, which carry meaning.
- **Copy:** draft all user-facing text as placeholders in the single strings module; **Mario writes final copy**. Spanish at launch, English-ready structure.
- **Testing:** the grade engine is pure functions and the most-tested code in the repo. CI runs against PostgreSQL.
- Skeleton loading + optimistic updates (with visible rollback) are the norm, not polish.
- Each roadmap phase deploys to Railway before the next begins.
