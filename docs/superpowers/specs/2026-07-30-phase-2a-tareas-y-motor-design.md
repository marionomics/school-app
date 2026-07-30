# Phase 2a — Tareas y el motor de calificación: Design Spec

Approved 2026-07-30. Source of truth for the Phase 2a implementation plan.

Phase 2 is split into **2a** (this document) and **2b** (exámenes, Revisar, incentivos). The split exists because the semester starts Aug/Sep 2026 and smaller deploys carry less risk. Tareas are auto-scored from timestamps and need no teacher tooling; exámenes are scored by hand and are useless without a grading UI, so they travel with the review surface into 2b.

**Every commit must leave `main` deployable and do something observable.** Where a migration cannot be made useful on its own, it ships together with the endpoint and UI that exercise it.

## 1. Scope

In scope:

- `tarea` post type (teacher-only), default due next Sunday
- "Es mi entrega" toggle on replies, with the lateness penalty shown before confirming
- Lateness auto-score: 100 / 90 / 50 / 20
- `calculate_grade` rewritten complete: tareas + exámenes + ledger + faltas, heavily tested
- Concave like-points, per-class configurable
- Schema for `reviews`, `points_config`, `class_sessions`, `attendance_records`
- Grade chip and breakdown showing rubros

Out of scope (2b unless noted):

- `examen` post type and its 1–10 scoring — the engine term is written and tested now, but nothing can create an examen yet
- Teacher score override UI and the `Revisar` queue
- `incentives` table, CRUD and awarding
- Class settings UI for weights and `points_config`
- `pasar lista` UI (Phase 3) — only the schema lands here
- "Mis entregas" sidebar view

## 2. Decisions

These were open before this spec and are now settled.

### 2.1 Which tareas count

The denominator is **tareas already due** (`due_date <= now`), never the full course. Tareas are created ad hoc — Mario may assign none in a given week — so a fixed denominator would force him to assign homework to keep grades sane.

- Zero tareas due → the rubro is *unevaluated*, not zero.
- One tarea due → that single tarea is the whole `tareas_weight`.
- Tareas due and the student submitted none → each counts 0%, mean is 0, rubro is **0**.

The last two states are different and must stay distinguishable: *unevaluated* means "nothing to measure yet", *0* means "measured, and nothing was handed in". Division by zero never arises because the empty case is handled before any division.

### 2.2 Live grade vs final grade

A rubro is **evaluated** when it has at least one due tarea (or closed examen).

```
live   = Σ evaluated rubros + Ledger − Faltas      unevaluated rubros show "—" and are excluded
final  = live, but any rubro still unevaluated at class end_date awards its full weight
```

The chip therefore climbs from 0 during the semester rather than starting at 60 and descending. The "gift" — full marks for a rubro that never had any items — is intentional and materialises only at the end: Mario promised 30 points for tareas, so students are not punished if he never assigned any.

This is the one place where the live display deliberately differs from the final formula. It is a display rule, not a second formula: both come from the same function, which reports per-rubro `evaluated` flags.

### 2.3 Like points are concave

Participaciones stay linear (1 tap = 1 point, max 3). Likes become concave:

```
like_points = like_value × N ^ like_exponent          N = non-revoked forum_like rows for (user, class)
```

Default `like_exponent = 0.5`. Reaching 100 points from likes alone then requires 10,000 likes; reaching the uncovered 40 requires 1,600. Setting the exponent to `1.0` reproduces today's linear behaviour exactly, so one dial covers both with no special cases. Per class, editable by the teacher (UI in 2b; the column and defaults land here).

This **answers open question 1 in `planning/future.md`** (like cap / anti-cramming). The concave curve is the anti-cramming mechanism; `like_cap` stays in the schema, defaulted off.

Consequence worth being aware of: with the exponent at 0.5, participaciones dominate the ledger and likes become a modest contributor. That is the intent — live participation is the behaviour being rewarded.

### 2.4 Likes in an append-only ledger

A concave curve is not additive: the 100th like is worth `√100 − √99 ≈ 0.05`, not 1. "Sum the rows" and "apply the curve to the total" stop being the same operation.

**The ledger remains the event log; the engine applies the curve.** Like rows keep being written and revoked as they are today, and `calculate_grade` reads their *count* and applies the formula. This is always exact, including after a veto, and fits the project's existing rule that grades are computed and never stored.

The alternative — marginal-value rows that telescope to `√N` — was rejected: revoking a middle row leaves the total silently off the true `√(N−1)`, and silent inexactness in the grade engine is the worst failure mode available.

`CLAUDE.md` says `Ledger = Σ non-revoked ledger rows`. That wording must be updated: it is true for participaciones, incentives, bonuses and penalties, but for likes the ledger holds the events and the engine holds the curve.

### 2.5 Resubmissions

A student may mark several replies as entrega. **The latest wins**, and lateness is measured from it. Marking a new entrega clears the flag on the previous one in the same transaction.

This closes the placeholder loophole (submit an empty reply before the deadline, submit the real work a week later, still score 100%). The cost — a student who tidies up after the deadline drops a tier — is mitigated because the composer shows the penalty before confirming, and a teacher override in 2b can always correct it.

## 3. Data model

One migration. Five schema objects.

### posts (2 new columns)

```
due_date    DateTime(timezone=True), nullable   -- tarea deadline
is_entrega  Boolean, not null, default false
```

`max_points` from the platform spec is **deliberately dropped**. Tareas score as a percentage, exámenes as 1–10; nothing reads it. It returns when per-tarea weighting becomes real.

Default `due_date` for a tarea is the next Sunday at 23:59 in the class timezone (`TIMEZONE`, default `America/Mexico_City`), computed server-side. If today is Sunday, the default is the *following* Sunday, never today.

### reviews (new, rows written lazily)

```
id, entrega_post_id (unique, FK posts), reviewer_id (FK users, nullable),
score Numeric(5,2) nullable, auto_score Numeric(5,2), feedback Text nullable,
created_at, updated_at
```

`score` and `auto_score` are stored **on the scale of the parent post type**: 0–100 for a tarea (a percentage), 1–10 for an examen. The column is shared, the scale is not — every read must know which type it is looking at, and the engine converts at the rubro boundary (`/100` for tareas, `/10` for exámenes).

A row exists **only when a teacher overrides** — so, in practice, only from 2b. Absence of a row means "auto-scored", which matches the philosophy that grading is automatic and the teacher handles exceptions. The lateness score is a pure function of `entrega.created_at` and `tarea.due_date`, so storing it eagerly buys nothing and goes stale the moment a due date is edited. When a row is created, `auto_score` records what the machine would have said, for audit.

### points_config (new, one row per class)

```
class_id (unique, FK classes), tap_value 1.0, like_value 1.0,
like_exponent 0.5, like_cap nullable NULL, daily_post_limit 5
```

Created with defaults when a class is created. Existing classes get a row in the migration. The engine reads config through a helper that falls back to defaults if a row is somehow missing, so a missing row can never zero out a grade.

### class_sessions, attendance_records (new, schema only)

```
class_sessions:      id, class_id, date, opened_at, closed_at
attendance_records:  id, session_id, user_id, status (present|absent|late|excused),
                     justification_text, justification_file_key,
                     justification_status (null|pending|approved|rejected),
                     reviewed_by, reviewed_at
```

Nothing writes to these in 2a. The engine reads them so the faltas term is real and tested from day one, and Phase 3 becomes UI work that only inserts rows.

## 4. Grade engine

`backend/app/services/grades.py` — one pure function, the most-tested code in the repo.

```python
calculate_grade(db, user_id, class_id, now) -> GradeBreakdown
```

### Tareas

Mean over tareas of the class with `due_date <= now`:

```
score%(t) = review.score            if a review row exists for the counting entrega
          = 0                       if the student has no entrega for t
          = lateness(entrega, t)    otherwise

lateness:  delta = entrega.created_at − t.due_date
           delta <= 0            → 100
           0 < delta < 24h       →  90
           24h <= delta < 7d     →  50
           delta >= 7d           →  20

Tareas = mean(score%) / 100 × tareas_weight
```

Boundaries are closed at the top of each tier and stated explicitly in the tests: exactly 24 h late scores 50, exactly 7 days late scores 20.

The counting entrega is the **latest** reply to `t` by that student with `is_entrega = true` and `status = 'active'`. A deleted entrega does not count; a student who deletes their only entrega scores 0 for that tarea.

### Exámenes

Same shape over exámenes whose window has closed, with `score / 10` in place of `score%`. Written and tested in 2a against fixtures; produces nothing until 2b can create an examen.

### Ledger

```
participaciones                              Σ (taps × tap_value)              linear
likes                                        like_value × N ^ like_exponent    concave
incentive | bonus | adjustment | penalty     Σ points                          linear (2b)
```

`N` counts non-revoked `forum_like` rows for `(user, class)`. Likes are attributed to the class of the post they sit on; posts with `class_id = NULL` earn nothing, which `_recipient_can_earn` already enforces. Self-likes are rejected at the router with 400 and teacher likes award nothing — both already true.

### Faltas

```
Faltas = 10 × count(attendance_records where status = 'absent'
                    and (justification_status IS NULL
                         or justification_status != 'approved'))
```

The null case is spelled out on purpose: `justification_status` is nullable, and `!= 'approved'` alone silently drops NULL rows in SQL. `IS DISTINCT FROM` would express this more neatly but is not available on SQLite, which local development runs on.

Subtracted from the total. Each unjustified absence costs **10 points on the 100-scale** — un punto entero, not una décima.

### Assembly

```
live  = Σ (evaluated rubros) + Ledger − Faltas
final = live, plus full weight for any rubro unevaluated at end_date
```

Only `active` enrollments receive a grade. `ghost` and `polizon` post freely and earn nothing.

### Numeric handling

All arithmetic in `Decimal`. `N ^ 0.5` uses `Decimal.sqrt`; other exponents use `Decimal.ln`/`exp`. No float touches a grade. Rounding happens once, at the API boundary, to 2 decimal places, `ROUND_HALF_UP`.

## 5. API

Extensions only — no new endpoints.

- `POST /api/posts` accepts `type=tarea`. Teacher-only (403 otherwise), `class_id` required (422 if absent), `due_date` optional and defaulted server-side. The teacher must own the class — the Phase 1 ownership check already covers this.
- `POST /api/posts` replies accept `is_entrega: bool`. The server validates that the parent is a `tarea`, that it belongs to a class where the student's enrollment is `active`, and that the reply is a direct child of the tarea. Marking a new entrega clears the previous flag in the same transaction.
- `GET /api/students/me/grade` returns the existing per-class shape plus:

```json
{
  "tareas":   { "evaluated": true,  "points": 25.0, "weight": 30, "count_due": 6, "count_entregadas": 5 },
  "examenes": { "evaluated": false, "points": 0.0,  "weight": 30 },
  "ledger":   { "participaciones": 12.0, "likes": 4.24, "likes_count": 18, "other": 0.0 },
  "faltas":   { "count": 0, "points": 0.0 },
  "total": 41.24
}
```

`evaluated: false` is the client's signal to render `—`. `likes_count` is shown alongside the curved value so the number is legible rather than mysterious.

The lateness preview needs **no endpoint**: the client has `due_date` and the clock. The server recomputes authoritatively on submit; the client value is advisory.

## 6. Frontend

- **Composer** — teachers get a type selector (regular / tarea); students never see it. Tarea mode adds a due-date control pre-filled to next Sunday.
- **PostCard** — type badge for tarea with its due date; entrega replies carry a small badge.
- **Thread reply composer** — "Es mi entrega" toggle. While on, it shows the consequence live (*"Entrega a tiempo · 100%"* / *"Con retraso · 90%"*) before the student confirms.
- **GradeChip breakdown** — a rubros section above the existing ledger detail; unevaluated rubros render `—` with a short reason.

All user-facing strings are placeholders in `frontend/src/strings/es.ts`; Mario writes the final copy. Mobile-first, QA at 390 px before desktop.

## 7. Error handling and testing

Errors keep the existing `{detail: "..."}` shape with Spanish messages surfaced as toasts. No new convention.

The engine suite must cover:

- Lateness exactly at 24 h and exactly at 7 days, asserting tier direction
- Zero tareas due → `evaluated: false`, no division by zero; and the end-of-course gift path
- Tareas due with no entrega → `0`, and that this is distinguishable from unevaluated
- Latest-wins with two entregas, including when the later one scores worse
- Deleted entrega falls back to 0
- Like curve at `N = 0` and `N = 1`; `exponent = 1.0` reproducing linear results exactly; recount after a revocation
- Ghost and polizon earn nothing
- Weight changes mid-course recompute cleanly
- A missing `points_config` row falls back to defaults rather than zeroing a grade

Frontend: vitest for the lateness preview function, including the same boundaries as the backend.

CI runs against PostgreSQL, and the migration-plus-drift guard added on 2026-07-30 applies to this migration too.

## 8. Notes for 2b

- `examen` post type, entrega window, 1–10 scoring
- Teacher override writes the first `reviews` rows; grading from the feed and from `Revisar`
- `Revisar`: entregas grouped by tarea, participaciones with one-tap veto
- `incentives` table, CRUD, awarding
- Class settings UI: weights, `tap_value`, `like_value`, `like_exponent`
`CLAUDE.md` was amended on 2026-07-30 with the ledger wording from 2.4 and the concave like rule, and `planning/future.md` open question 1 was marked resolved. Neither is outstanding.
