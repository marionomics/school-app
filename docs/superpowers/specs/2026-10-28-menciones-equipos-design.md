# Menciones y entregas en equipo

**Status:** design approved by Mario on 2026-10-28, section by section in chat. Roadmap: "Menciones y entregas en equipo", ahead of Racha.

## Why

Mario (2026-10-28): students need to be able to `@` each other — for engagement, but above all for group work. If a student `@`s classmates in their entrega, the entrega is theirs too and the grade reaches all of them. Mario never admits groups larger than 3, so a team is the author plus at most 2 others.

Today each team member has to submit separately, and the teacher grades the same work three times.

Success: a team of three hands in one entrega; all three see the same grade; the teacher grades it once and it counts as one item in their pending work.

## Decisions (Mario)

1. **The `@` in a submission is the team** (option B). No separate team picker. Thanking someone with an `@` in an entrega is not a real pattern in class; the only guard needed is a warning when an `@` will not count (a fourth member, someone not in the class, someone already on another team).
2. **First team wins.** Once a student is on an active team for an item, another submission that tags them does not add them — the composer warns. This blocks both freeloading (sitting on two teams and keeping the better grade) and harm (someone tags Pedro into a worse or later entrega and his grade drops for something he didn't do).
3. **The student's own newest submission always counts for them.** Resubmitting alone is how a student leaves a team. Between a student's own entrega and a team entrega that names them, the newer wins — that is the everyday case of one member uploading a draft and another the final team version. Pedro sees "Entregada por @ana · en equipo", so being overridden is visible and he can resubmit.
4. **One grade per entrega.** No per-member adjustments. A member who didn't work is **removed from the team** by the teacher — a flag, reversible, never a different number.
5. **The grade lives on the entrega and members read it** (approach 2 — computed, not copied). There is one review, the author's; every member's grade *is* that review. Regrading, removing a member, lateness or a replaced entrega reach everyone with no copies to keep in sync.
6. **Social mentions reach anyone with a username** (option A): the feed is global, so a ghost 👻 from last semester can be answered. Autocomplete puts classmates first. A team member must be an active classmate in that class.
7. Mentions notify the mentioned person — but notifications are Bloque 5. This block stores mentions so Bloque 5 can use them; it sends nothing.

## 1. Data

New table `post_mentions` (Alembic migration):

| column | type | notes |
|---|---|---|
| `id` | int PK | |
| `post_id` | FK posts.id, indexed | ON DELETE CASCADE (posts are never hard-deleted, but Postgres must not choke) |
| `user_id` | FK users.id, indexed | the mentioned person |
| `kind` | `'social'` \| `'team'` | decided once, at publish |
| `created_at` | timestamptz | |
| `removed_at` | timestamptz, nullable | teacher removed this member from the team |
| `removed_by` | FK users.id, nullable | |

Unique `(post_id, user_id)`.

- **Parsing happens on the server**, at publish, for every post (root or reply, any type). Pattern: `@` followed by `[A-Za-z0-9_]{3,20}` (the `UserUpdate` username pattern), not preceded by a letter or digit (so an email address is not a mention), lowercased before lookup. Only usernames that exist produce a row. The author mentioning themselves is ignored; a repeated `@` produces one row.
- **Team evaluation** runs only when the post is a **submission**: `is_entrega` on a reply to a tarea or examen, or a reply with files to an examen (the `examen_submission` rule). Mentions are taken in the order written; each becomes `team` only if **all** hold, otherwise it is `social`:
  - the **author** is `active` in the item's class (otherwise no team forms at all);
  - the mentioned user is `active` in the item's class (ghost 👻 and polizón 🥷 never — they earn no points);
  - fewer than 2 `team` rows already assigned on this post;
  - the mentioned user is **not already on a team for this item** (§2, "on a team").
- The decision is stored and **never recomputed**. Recomputing would let "first team wins" flip on its own as other entregas arrive or disappear.
- Posts cannot be edited (no PATCH route exists), so a team is fixed at publish. To change it, the author deletes and resubmits — which also frees anyone they had tagged.
- **No backfill.** Existing posts get no mention rows; their text stays plain. Old entregas stay individual.

## 2. Grade engine

All of this lives in `app/services/grades.py`, next to `_counting_entrega`, `examen_submission` and `counting_review`. Every caller keeps going through these functions.

**Definitions** (for one item — a tarea or examen — and one student):

- **Own submissions:** the student's active entregas on the item; for an examen, `examen_submission`'s rule (their entrega, else their newest active reply with files).
- **Author's current submission:** the newest of the author's *own* submissions (never a team one — no recursion).
- **Live team submission for Pedro:** an active submission on the item with a `team` mention of Pedro, `removed_at IS NULL`, **that is still its author's current submission**. If Ana replaces her entrega, she replaces it for the whole team; if her new one tags them again, the team carries over to it.
- **On a team for the item** (used by first-team-wins at publish and at restore): the student is the author of an active submission on the item that has at least one live `team` mention, or is a live `team` member of one.

**Which submission counts for Pedro:** the newest among his own submissions and his live team submissions. `_counting_entrega` and `examen_submission` return it; its `author_id` may not be Pedro.

**Pedro's review:** `counting_review(item, Pedro, submission)` — when `submission.author_id != Pedro`, it reads the review of `(item, submission.author_id)` and applies the usual staleness check against that submission. The review row is always the author's; there is no review row for a team member.

**Lateness:** computed from the counting submission's `created_at` — identical for the whole team.

**Revocation:** a deleted or vetoed submission is not active, so it stops counting for everyone; each member falls back to their own earlier submission if they have one ("sin evidencia no hay puntos").

**Paper exámenes** have no submission: the teacher grades each student individually, as today. Teams do not apply.

**Inlined copies of the rule** must change with it and get agreement tests:
- `feed_query.teacher_pending` (inlined for speed): counts **submissions**, not students — a team entrega is 1 pending item.
- `posts._superseded_entregas` (the thread's "this entrega was replaced"): Pedro's own entrega is superseded when a newer live team submission names him.
- `posts._pinned_tareas` (the feed's "Por entregar", via `_counting_entrega`) picks up the change automatically.

## 3. API

- `GET /api/users/search?q=` — authenticated. `q` ≥ 1 character, matches username or name prefix, case-insensitive. Up to 8 results: classmates of the viewer (any shared class, active enrollment) first, then everyone else with a username. Returns the `UserLink` shape.
- `GET /api/posts/{item_id}/team-check?u=ana&u=pedro` — authenticated, only meaningful for a tarea/examen the viewer can submit to. For each username, in order: `ok` or a reason — `max_team` (beyond the 2nd), `not_in_class`, `on_team` (with the author's username of the team they're on), `unknown`, `self`. Same evaluation as publish, read-only.
- `POST /api/posts` — unchanged inputs. The response's `PostOut` now carries `mentions`.
- `PostOut.mentions: [{user: AuthorOut, kind, removed: bool}]`, for every post that has any. `removed` is visible to everyone (a member who no longer counts shouldn't be listed as one).
- `POST /api/posts/{post_id}/team/{user_id}/remove` and `.../restore` — teacher of the item's class only. Remove sets `removed_at`/`removed_by`. Restore clears them **only if** the student is not on another team for the item now; otherwise 409 with the reason.
- `/api/review/entregas`: one row per **submission**, with `team: [AuthorOut]`. `pending` counts submissions.
- `/api/review/examenes/{id}` (roster): still one row per active student. A member's row carries `team_of: AuthorOut` (the author) and the shared score. Saving any member's score writes the author's review.
- `PUT /api/reviews` with a `student_id` who is a team member resolves to the author's review for that submission. `accept-suggested` grades each submission once.

## 4. Frontend

**Mention autocomplete** in the feed composer (`Compose.tsx`) and the thread reply bar:
- Typing `@` plus at least one letter opens a suggestion list above the field (preset `popover`, added with `npx shadcn add popover` — no hand-rolled primitive). Each suggestion goes through `UserLink plain`. Tapping inserts `@username `. Debounced; empty result closes the list.

**Rendering:** `@username` in post text becomes a `UserLink` when it matches a row in `post.mentions`; any other `@word` stays plain text. No dead links.

**Submission composer** (entrega switch on, or an examen reply with files): under the text, a line **"Equipo: @ana · @pedro"** with a warning per `@` that won't count, from `team-check` (debounced):
- "@luis no cuenta: el equipo es de máximo 3"
- "@pedro ya entregó con el equipo de @ana"
- "@x no está en esta clase"

Warnings never block sending. Publish re-evaluates; if the result differs from the last check, a toast says who ended up on the team.

**A published submission** shows "Equipo: @ana · @pedro · @luis" to everyone (live team members only, not social mentions).

**Teacher:**
- `/revisar` → Entregas: one row per team submission ("@ana · @pedro · @luis"), one score. Counters count submissions.
- Examen roster: member rows say "en equipo con @ana" and show the shared score; saving refreshes the roster so all three rows agree.
- Thread: "Calificar" appears once, on the team submission. The grading sheet (`ReviewSheet`) lists the team; each member has **"Quitar del equipo"** with confirmation ("@pedro deja de recibir esta calificación; vuelve a contar su entrega anterior, si tiene"). A removed member shows **"Devolver al equipo"**; a 409 shows its reason.

**Team member (Pedro):**
- The tarea leaves his "Por entregar" as soon as a live team submission names him; it returns if he's removed or Ana replaces it without him.
- On the thread he sees "Entregada por @ana · en equipo"; his grade breakdown shows the team's score like his own.
- He cannot remove himself; resubmitting alone is his way out.

**Copy:** all strings are placeholders in `frontend/src/strings/es.ts`; Mario writes final copy.

## 5. Testing

- **Engine** (pure functions, most-tested code): union rule (own vs team, newer wins); first team wins at publish; author replaces for the whole team, with and without re-tagging; remove and restore (and restore refused when on another team); delete and veto revoke for everyone; lateness shared; examen digital team; paper examen unaffected; ghost/polizón never team; author not active → no team; max 2; self and duplicate mentions.
- **Agreement:** `teacher_pending`, `_superseded_entregas`, `/revisar` and the examen roster pick the same submission as the engine and count one per team.
- **API:** `users/search` ordering and limits; `team-check` reasons match publish; `mentions` on `PostOut`; remove/restore permissions; `PUT /api/reviews` on a member writes the author's review.
- **Migration:** `post_mentions` upgrade/downgrade (CI on PostgreSQL).
- **Frontend (vitest):** mention parsing/rendering (only resolved mentions link), composer warning mapping.

## Out of scope

- Notifying the mentioned person (Bloque 5 — reads `post_mentions`).
- Backfilling mentions on existing posts.
- Per-member grade adjustments (decision 4).
- Persistent teams across items (YAGNI — teams change per tarea, and the `@` is the team).
- A student leaving a team themselves other than by resubmitting.
