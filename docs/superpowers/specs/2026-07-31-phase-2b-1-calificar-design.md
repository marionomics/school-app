# Phase 2b-1 — Calificar: Design Spec

Approved 2026-07-31. Source of truth for the Phase 2b-1 implementation plan.

Phase 2b is split into **2b-1** (this document — the grading loop) and **2b-2** (incentivos y configuración de clase). The split follows the same reasoning as the 2a/2b split: the semester starts Aug/Sep 2026, smaller deploys carry less risk, and the two halves are independently useful. 2b-1 is the half that cannot slip — without it exámenes cannot be graded at all and the teacher has no way to correct a wrong auto-score. 2b-2 is CRUD over class configuration and can land after the first week of class if the calendar squeezes.

**Every commit must leave `main` deployable and do something observable.** Where a migration cannot be made useful on its own, it ships together with the endpoint and UI that exercise it.

## 1. Scope

In scope:

- `examen` post type (teacher-only), in two modalities: **paper** (graded from a roster) and **digital** (graded from entregas)
- `graded_at` on exámenes — the "calificado" flip that decides when an examen counts
- `reviews` restructured to be keyed on (item, student) so a paper examen can carry a score with no entrega
- Teacher score override for tarea entregas, with feedback
- `Revisar`: three tabs — Entregas, Exámenes, Participaciones — with one-tap veto
- Grading from the feed thread, through the same endpoint as Revisar
- Student-private visibility of scores, feedback and veto reasons
- End-of-course rule for a rubro that never had items

Out of scope (2b-2 unless noted):

- `incentives` table, CRUD and awarding
- Class settings UI: weights, `tap_value`, `like_value`, `like_exponent`
- Per-class panel, roster and grade list — Phase 3
- Attendance capture — Phase 3; the faltas term already exists in the engine at zero
- Notifications when a score or veto lands — mid-semester; the student sees it on their next visit

## 2. Decisions

### 2.1 An examen is paper or digital

`posts.examen_mode ∈ {paper, digital}`, examen-only. A paper examen is written in class and has no entregas: the teacher opens a roster of active enrollments and types a score per student. A digital examen behaves like a tarea — students reply with `is_entrega` — but is scored 1–10 instead of auto-scored from timestamps.

Both modalities produce the same artefact: one `reviews` row per (examen, student). Everything downstream — the engine, the API, the rubro — is indifferent to which modality produced it.

### 2.2 An examen counts when the teacher says it does

A tarea enters the grade the moment its `due_date` passes, because lateness already gives it a score without any teacher action. An examen has no such default: until somebody types a number, there is nothing to average.

So each examen carries `graded_at` (nullable). While it is null the examen is invisible to the rubro — no student sees a zero for work the teacher has not finished grading. When the teacher flips it to calificado, the examen enters the denominator **for every active enrollment**, and a student with no review row scores 0. That is the "didn't take it, didn't submit" case, and it is now an explicit consequence of the teacher declaring the batch done rather than an artefact of unfinished grading.

The flip is reversible: un-marking sets `graded_at` back to null and the examen leaves the rubro again.

This closes the hole recorded in `planning/changelog.md` on 2026-07-31, where an entrega with no `Review.score` summed 0 while the examen already sat in the denominator.

### 2.3 Reviews are keyed on (item, student), not on the entrega

The 2a schema hangs a review off `entrega_post_id`. A paper examen has no entrega post, so that key cannot represent the majority of real exams. The table is re-keyed:

```
UNIQUE (item_post_id, student_id)
```

where `item_post_id` is the tarea or examen. `entrega_post_id` stays as a nullable column recording *which submission the score was written against*.

Nothing writes `reviews` in production yet — the table shipped empty in 2a — so this is a restructure, not a data migration.

### 2.4 A review can go stale

Entregas are latest-wins (2a §2.5). If a teacher grades an entrega and the student then submits a new one, the old score must not silently freeze the student's grade against work they have replaced.

A review is **stale** when `review.entrega_post_id` is not the student's current counting entrega. A stale review is ignored by the engine — the rubro falls back to the lateness auto-score — and the entrega reappears in Revisar as unopened. Paper exámenes have `entrega_post_id = NULL` and can never be stale.

The teacher is not notified; the entrega simply returns to the queue, which is the same signal as any other unreviewed work.

### 2.5 "Pending" means "you haven't opened it"

Nothing in the grading loop blocks a grade: a tarea entrega counts from the moment it lands, reviewed or not. So "pending" cannot mean "blocking". It means unread.

An entrega is pending until the teacher opens it and confirms. Confirming writes the review row **even when the auto-score is kept unchanged** — `score` is set to the auto-score explicitly. "I read this and it was fine" becomes a record rather than an absence, which is what makes the queue drain.

### 2.6 Scores are private to their author

The feed is shared by the whole class, so anything rendered on a post is rendered to everyone unless the server withholds it.

A score, its feedback, and a veto reason are visible **only to the student who wrote the post and to the teacher**. Classmates see a normal reply, or a participación that looks untouched. This is enforced server-side in the thread serializer, not by hiding fields in the client.

The consequence accepted here: the class never sees what a 100 looks like. Publishing exemplary work is a teacher action for a later phase, not a side effect of grading.

### 2.7 An empty rubro pays out at end of course

If the course ends and a rubro never had a single item — no exámenes assigned all semester — every student receives its full weight. Nobody is penalised for work the teacher chose not to assign, and the reachable maximum stays where students believed it was all semester.

Trigger: `now > class.end_date`. Applies only when the rubro had **zero** items ever. A rubro with items behaves normally: a student who skipped every tarea still scores 0.

### 2.8 A veto revokes everything the post earned

Vetoing a participación revokes every ledger row the post produced — its taps **and** the likes it received. The governing rule is *no evidence, no points*: once the teacher has ruled the participación invalid, nothing it attracted should keep paying. This matches deletion, which revokes on the same principle, and it is the rule a student can be told in one sentence.

An earlier draft of this spec had veto sparing likes, on the theory that a like is the liker's action rather than the author's claim. That was overturned on 2026-07-31: it left a vetoed post still paying its author, which is both hard to explain and easy to exploit.

The liker keeps their own behaviour intact — likes are not points *for the liker*, so there is nothing of theirs to revoke. The post stays in the thread with `status = vetoed` and its reason visible to its author.

Un-vetoing restores exactly what was revoked, by clearing the same flags.

## 3. Data model

One migration. Two tables touched.

### posts (3 new columns)

| column | type | notes |
|---|---|---|
| `examen_mode` | `String(10)`, nullable | `paper` \| `digital`; null for every non-examen post |
| `graded_at` | `DateTime(timezone=True)`, nullable | examen-only; null = not yet counted |
| `veto_reason` | `Text`, nullable | shown to the post's author only |

### reviews (restructured)

| column | type | notes |
|---|---|---|
| `id` | PK | |
| `item_post_id` | FK → posts.id, indexed | the tarea or examen |
| `student_id` | FK → users.id, indexed | |
| `entrega_post_id` | FK → posts.id, nullable | which submission this was written against; null for paper |
| `score` | `Numeric(5,2)`, nullable | 0–100 for a tarea, 1–10 for an examen |
| `auto_score` | `Numeric(5,2)`, nullable | the lateness value at review time, for audit |
| `feedback` | `Text`, nullable | |
| `reviewer_id` | FK → users.id, nullable | |
| `created_at`, `updated_at` | timestamps | |

`UNIQUE (item_post_id, student_id)`. The old `UNIQUE (entrega_post_id)` index is dropped.

Scale follows the parent item's type, exactly as in 2a: a tarea review is 0–100, an examen review is 1–10. The API validates against the item type on write.

## 4. Grade engine

Changes to `services/grades.py`, all of them local to the two rubro functions plus one new helper.

### Tareas

Unchanged except for how the review is found and whether it is trusted:

```
score = review.score  if a non-stale review exists with score not null
        lateness_score(entrega.created_at, tarea.due_date)  otherwise
```

Review lookup moves from `Review.entrega_post_id == entrega.id` to `(item_post_id == tarea.id, student_id == user_id)`, then the staleness check from §2.4.

### Exámenes

```
closed   = exámenes with graded_at IS NOT NULL
score_i  = review.score / 10   if a review with score not null exists
           0                    otherwise
points   = mean(score_i) × examenes_weight
```

The `due_date <= now` filter disappears — `graded_at` replaces it. An examen whose date has passed but which the teacher has not finished grading does not count.

### Empty rubro at end of course

A new helper wraps both rubros:

```
if rubro has zero items ever and now > class.end_date:
    Rubro(evaluated=True, points=weight, weight=weight, count_due=0, count_entregadas=0)
```

"Zero items ever" ignores `graded_at` and `due_date` — an examen that exists but was never graded means the rubro *did* have items, and the payout does not apply. This is deliberate: the rule exists for the teacher who never assigned exámenes at all, not for the one who forgot to finish grading.

### Everything else

Ledger, likes curve, faltas and assembly are untouched. Rounding stays at the API boundary only.

## 5. API

All new endpoints are teacher-only and scoped to classes where `teacher_id == user.id`. A teacher hitting another teacher's class gets 403; a student gets 403.

### Writes

| endpoint | body | notes |
|---|---|---|
| `PUT /api/reviews` | `item_post_id`, `student_id`, `entrega_post_id?`, `score?`, `feedback?` | upsert on (item, student); validates `score` against the item type (0–100 tarea, 1–10 examen) |
| `POST /api/posts/{id}/graded` | — | examen-only; sets `graded_at = now` |
| `DELETE /api/posts/{id}/graded` | — | clears `graded_at` |
| `POST /api/posts/{id}/veto` | `reason?` | participación-only; `status = vetoed`, revokes its ledger rows, stores `veto_reason` |
| `DELETE /api/posts/{id}/veto` | — | `status = active`, clears `revoked_at`/`revoked_by`, clears the reason |

### Reads

| endpoint | returns |
|---|---|
| `GET /api/review/entregas?class_id=&status=unopened\|all` | entregas grouped by tarea, each with student, entrega, auto-score and review state |
| `GET /api/review/examenes/{id}` | the roster: every active enrollment × its score, plus the entrega link when the examen is digital, plus `graded_at` |
| `GET /api/review/participaciones?class_id=&limit=` | recent participaciones with taps, points and veto state |

### Changed endpoint

`GET /api/posts/{id}` (thread) includes a reply's review and a post's `veto_reason` **only when the requester is the post's author or the class's teacher**. Enforced in the serializer per §2.6.

`POST /api/posts` accepts `examen_mode` when `type == "examen"`, defaulting to `paper`. Exámenes are teacher-only and require a class, exactly like tareas.

## 6. Frontend

New route `/revisar`, teacher-only, reachable from a nav entry in `Shell`. Three tabs with pending counts.

**Entregas** — grouped by tarea, newest due first. A row shows student, auto-score, lateness label and an unopened marker. Tapping opens a sheet with the entrega's content and attachments, a score prefilled with the auto-score, a feedback box, and save-and-advance to the next unopened item.

**Exámenes** — a list of exámenes; tapping one opens its roster. Paper exams render a numeric column over active enrollments; digital ones link each row to its entrega. The header carries "Marcar como calificado", which warns before flipping: *"12 alumnos sin calificación contarán como 0."*

**Participaciones** — recent participaciones with a one-tap veto, optimistic with visible rollback, and an optional reason.

**In the feed thread** — an entrega reply shows a score chip to the teacher and to its author. Tapping it opens the same sheet component and calls the same `PUT /api/reviews`. Grading behaves identically wherever it is done.

**Students** see their own score and feedback on their entrega, and a clear "no cuenta" marker with the reason on a vetoed participación. Classmates see neither.

Per-device treatment, following the mobile-first rule but not pretending a roster is a phone task: phone gets a single column, large tap targets and `inputMode="numeric"`; laptop widens each tab into a table, and the roster supports tab-through with Enter advancing to the next student.

All copy ships as placeholders in `strings/es.ts` for Mario to rewrite.

## 7. Error handling and testing

Error handling:

- Score outside the item's scale → 422 with the valid range in the message
- Grading, vetoing or flipping an item in a class you do not teach → 403
- `PUT /api/reviews` for a student with no active enrollment in that class → 422
- Marking an examen calificado with zero scores entered → allowed, warned in the UI only. The teacher may genuinely mean "nobody passed"; the server does not second-guess it
- Concurrent edits to the same review → last write wins, `updated_at` bumped. No locking; two teachers do not exist yet

Testing, following the 2a shape — the engine stays the most-tested code in the repo:

- **Engine**: stale review ignored, non-stale review honoured, `graded_at` gating in both directions, missing score counting as 0 in a graded examen, paper vs digital producing identical rubro maths, empty rubro paying full weight after `end_date`, empty rubro paying nothing before it, a rubro with an ungraded examen *not* qualifying as empty
- **API**: authz matrix (owning teacher, other teacher, student, anonymous) across every new endpoint; upsert idempotency; score range validation per item type; veto → un-veto restoring the exact ledger contribution; thread serializer withholding a review from a classmate and exposing it to the author
- **Frontend**: queue grouping helper, score validation for both scales, optimistic veto rollback on failure

CI keeps running against PostgreSQL, including the migration chain and the drift check.

## 8. Notes for 2b-2

- `incentives` table, CRUD, awarding — the only remaining way for a teacher to move a grade by hand
- Class settings UI: weights, `tap_value`, `like_value`, `like_exponent`
- Bug 2 in `planning/bugs.md` (deleting your latest entrega loses the tarea) is *not* fixed here. It is a deletion-path bug, not a grading-path one, and the fix belongs with whatever phase touches post deletion. Left open deliberately
