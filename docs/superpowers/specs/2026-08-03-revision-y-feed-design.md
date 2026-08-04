# Revisión y feed: Design Spec

Approved 2026-08-03. Source of truth for its implementation plan. Branch: `revision-y-feed`.

Three changes that share no code but share a cause: the app was designed for a class, and Mario teaches around **80 students at a time**. At that size a review queue that never drains is unusable, and a global feed that mixes every class's homework together is actively confusing.

**No grade-engine changes. Nothing here moves a single point.**

## 1. Why

### 1.1 The review queue cannot drain

`CLAUDE.md` states the rule this app was built on:

> Participaciones auto-count on publish; the teacher vetoes exceptions (never a routine approval queue).

That rule is right and stays. It exists to avoid the Google-Classroom failure mode where a teacher's attention is a bottleneck on every student's grade, and it is why the grade chip can be real-time at all.

But it left no way to mark a participación as *looked at*. With 80 students the list is never short, so "pendiente" means nothing, nothing ever leaves, and the only control that removes a row from view is the one that **cancels the student's points**. On 2026-08-03 that combination did what it was always going to do: veto was read as approval and real participaciones were cancelled. They were restored, and the underlying design problem is what this spec fixes.

The fix is not to make validation grant points. It is to separate *"I have seen this"* from *"this does not count"* — two different actions that the interface currently collapses into one.

### 1.2 A tarea sinks

`get_feed` orders by `last_activity_at desc` and nothing else, so a tarea drops out of sight as soon as anyone posts. The one post a student most needs to see is the one the feed is worst at surfacing.

### 1.3 Assignments leak across classes

The feed query has **no class filter at all**. Every student sees every tarea from every class, indistinguishable from work they actually owe.

The v2 spec says "the feed is **global** — all classes, all semesters." That is right for social content and it is the product. It is wrong for assignments: a tarea is class business. §5 records the amendment.

## 2. Decisions

### 2.1 Validar is a marker, not a grant

`reviewed_at` records that the teacher looked. It moves no points, because the points were the student's from the moment they published. The student is never told — no badge, no notification.

Making validation grant points was considered and rejected: it is the approval queue the v2 spec explicitly refuses, it would make the teacher a bottleneck on every grade, and it would break the real-time chip.

So a participación has two independent facts: whether it has been **seen** (`reviewed_at`) and whether it **counts** (`status`). Vetoing still cancels; validating never does.

### 2.2 Bulk validation sends explicit ids

"Validar todas" sends the ids currently rendered on screen — never a class-wide "mark everything pending".

A participación published while the teacher was scrolling would otherwise be marked as seen by a tap made before it existed. The whole point is an honest record of attention; a bulk action that silently covers unseen work destroys the thing being built.

### 2.3 Pinned tareas live outside pagination

`GET /api/feed` returns a separate `pinned` array alongside `items`. It is not merged into the paginated query.

Pinning inside the query would mean ordering by a per-student, time-dependent condition on top of a keyset cursor over a mutable sort key. That is the same fragility that made likes reorder the feed under the reader's thumb (design-pass spec §2.8), and it would return the same post at the top of every page.

A tarea is pinned for a student when **all** hold:

- the student has an enrollment in its class (`active`, `ghost` or `polizon`)
- `due_date` is in the future
- the student has no active entrega on it

It unpins the moment they deliver, and for everyone once the deadline passes — lateness is already scored, and a permanent pin is nagging rather than helping.

Teachers see their own classes' open tareas pinned, since they have no entregas by construction.

### 2.4 Assignments are scoped, social content is not

`tarea` and `examen` posts appear in the feed only for people enrolled in their class — `active`, `ghost` and `polizon` alike, since all three are legitimately in the class — and for the class's teacher.

`regular` and `participacion` posts stay global across all classes and semesters. That is the product and it does not change.

Threads are unaffected: a direct link to a tarea still opens for anyone. This is about what the feed pushes at you, not about secrecy.

## 3. Data model

One migration, two columns, both on `posts` and both meaningful only for participaciones:

| column | type | notes |
|---|---|---|
| `reviewed_at` | `DateTime(timezone=True)`, nullable | null = not yet looked at |
| `reviewed_by` | FK → users.id, nullable | which teacher looked |

No index: the queue always filters by `class_id` first, which is already indexed, and 80 students produce a few hundred rows per semester.

## 4. API

### Writes

| endpoint | body | notes |
|---|---|---|
| `POST /api/posts/{id}/reviewed` | — | participación-only, teacher of that class; sets `reviewed_at` and `reviewed_by` |
| `DELETE /api/posts/{id}/reviewed` | — | clears both, returning the row to the pending queue |
| `POST /api/review/participaciones/reviewed` | `{"post_ids": [int]}` | bulk; every id must be a participación in a class this teacher owns, else 403 and **nothing is written** |

The bulk endpoint is all-or-nothing on purpose: a partial write would leave the teacher unable to tell which taps landed.

### Reads

`GET /api/review/participaciones?class_id=&status=pending|handled` — `pending` means `reviewed_at IS NULL AND status != 'vetoed'`; `handled` is everything else. Each row gains `reviewed: bool`.

`GET /api/feed` gains `pinned`, an array of serialized posts using the same shape as `items`, ordered by `due_date` ascending — soonest deadline first. It is not paginated and ignores the cursor: it is the same short list on every page.

## 5. Amendment to the v2 spec

`docs/superpowers/specs/2026-07-19-v2-platform-rebuild-design.md` line 59 currently reads:

> **The feed is global** — all classes, all semesters, one feed. `class_id` only marks which class a post *counts for* (points, deadlines).

It gains: assignments are the exception — `tarea` and `examen` posts appear only to their class. Social content stays global. `CLAUDE.md`'s Core Model Rules get the same amendment, since it states the rule too.

Leaving the two documents contradicting the code is how the delete/veto rule stayed inverted for two weeks.

## 6. Frontend

**Revisar → Participaciones.** Each pending row gains a validate action alongside veto, and the two read as clearly different things — validating is neutral, vetoing is destructive. A sticky "Validar todas" acts on exactly what is rendered, showing the count. Vetoing keeps its existing behaviour.

Copy must make the difference unmissable, because it already caused a real incident. Placeholders in `strings/es.ts` for Mario to finalise; the veto action states its consequence rather than assuming "vetar" is understood.

**Feed.** Pinned tareas render above the scroll, visually distinct from normal cards and labelled with their deadline. If `pinned` is empty the section does not render.

## 7. Testing

- **API:** validating moves no points (assert the ledger total is identical before and after); a vetoed participación stays out of pending; unmarking returns it; bulk with one foreign id writes nothing and 403s; a student gets 403 on all three endpoints
- **Feed:** a tarea from a class you're in is pinned; it unpins once you have an active entrega; it unpins after the due date; a tarea from a class you're *not* in appears in neither `pinned` nor `items`; a regular post from a class you're not in still appears; the teacher sees their own class's tarea pinned
- **Frontend:** the bulk action sends exactly the rendered ids

Backend suite is at 202 and must stay green; it should grow only from these.

## 8. Out of scope

- Notifying a student that their participación was reviewed (§2.1)
- Any change to how participaciones earn points
- Bug 2 in `planning/bugs.md`
- Editing class name and dates (`planning/future.md`)
