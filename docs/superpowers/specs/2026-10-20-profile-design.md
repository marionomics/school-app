# Bloque 3b — Profile page `/u/:username`

**Status:** design approved by Mario on 2026-10-20, section by section (sections 1–3 in chat; section 4 written here directly at his request). Roadmap Bloque 3, after Bloque 3a (photos).

## Goal

A student taps a classmate's name, sees who they are and what they've posted, and gets back to the feed in one tap. Mario's principle: if a username appears, you can tap it and reach the profile.

## Decisions

1. **Every username and avatar links to `/u/:username`** (Mario, roadmap).
2. **The profile shows photo, bio, aura received and their posts** (Mario, roadmap).
3. **Your own profile is where you edit your bio and photo**; it absorbs `/perfil` (Mario, roadmap).
4. **The grade on a profile is seen only by its owner and the teacher**; the teacher sees the full breakdown, the same one as the class panel (Mario, roadmap).
5. **Two tabs, Publicaciones and Respuestas**, like Threads (Mario, 2026-10-20, option A).
6. **Entregas never appear on a profile** — they live in their tarea's thread; listing them per student would make homework easy to browse and copy (proposed, not objected to).
7. **Aura received** = sum of `like_count` over the person's posts that are neither deleted nor vetoed — the teacher's aura included. A vetoed post's aura no longer counts for points ("no evidence, no points"), so it doesn't count here either.
8. **Grades per class:** the owner sees one row per active enrollment; the teacher sees only the classes they teach that student. Everyone else receives no `grades` key at all.
9. **A dedicated profile API** (option A), not a filter on the feed endpoint — the feed is about to be reshaped by Bloque 4.
10. `users.grade_is_private` stays unused: with decision 4 nobody else can ever see a grade.

## 1. Backend — `backend/app/routers/profiles.py`

No new tables, no migration.

### `GET /api/users/{username}` — the header
```json
{
  "id": 7, "username": "ana", "name": "Ana López", "bio": "…",
  "avatar_url": "…", "role": "student", "is_me": false,
  "aura_received": 42, "has_own_avatar": true,
  "grades": [ { "class_id": 3, "class_name": "Micro", "summary": { … } } ]
}
```
- `avatar_url` via `avatar_for` (own photo or Google's); `has_own_avatar` from the model property (a harmless boolean, sent to everyone — the frontend only acts on it for the teacher's remove button).
- `aura_received`: `SUM(posts.like_count)` where `author_id = user.id` and `status = 'active'`.
- `grades` present only when the viewer is the owner (rows: the owner's `Enrollment.status == 'active'` classes) or a teacher (rows: classes where `Class.teacher_id == viewer.id` and the user has an enrollment). Each `summary` is exactly `grades._summary(db, user_id, klass)` — one grade computation in the codebase. Otherwise the key is omitted.
- Unknown username → 404.

### `GET /api/users/{username}/posts?tab=posts|replies&cursor=…&limit=20`
- `posts`: `author_id = user.id`, `parent_id IS NULL`.
- `replies`: `author_id = user.id`, `parent_id IS NOT NULL`, and not a **submission** — a flagged entrega, or a reply with attachments whose direct parent is a tarea/examen (unflagged examen answers, matching `review_queue._examen_submission`; added after the final review, 2026-10-21). A reply to a submission gets an empty excerpt. Each item carries `parent: { id, author_username, excerpt }` — `excerpt` = the parent's first 120 characters (empty if the parent is deleted).
- Both: `status IN ('active', 'vetoed')`; newest first by `(created_at, id)`; keyset cursor with the existing `encode_cursor`/`decode_cursor`; `{ "items": [...], "next_cursor": "…" | null }`.
- **Class scoping:** a tarea or examen from a class the viewer neither attends (any enrollment status) nor teaches never appears; in `replies`, a reply whose **root** is such an assignment doesn't appear either. The rule is extracted from `get_feed` into one helper in `backend/app/services/visibility.py`:
  - `viewer_class_ids(db, viewer) -> list[int]` (enrollments of any status + classes taught — exactly what the feed computes today),
  - `assignment_visible(class_ids)` → a SQLAlchemy condition `or_(Post.type.notin_(("tarea","examen")), Post.class_id.in_(class_ids))`.
  `get_feed` uses the helper; its behaviour must not change (existing feed tests are the guard).
- Items go through `serialize_post` with the same `liked`, `teacher_aura_ids` and viewer arguments the feed passes, so aura, photos and veto text behave identically.

### Unchanged
`PATCH /api/users/me` (bio) and the avatar endpoints (`PUT/DELETE /api/users/me/avatar`, `DELETE /api/users/{id}/avatar`).

## 2. Frontend — the screen

- Route `/u/:username` inside `Shell`. The bottom-nav "Perfil" icon → `/u/<my username>`. `/perfil` → redirect to the same.
- **Header:** avatar 80 px; name; `@username`; "profe" tag for the teacher; bio (`whitespace-pre-wrap`); aura received with `RiSparkling2Line` and "{n} de aura" (placeholder).
- **Own profile:** "Editar perfil" opens a sheet with today's `/perfil` content, extracted into `components/ProfileEditor.tsx` (photo + bio, unchanged behaviour).
- **Teacher on a student's profile:** "Quitar foto de perfil" with its confirmation, extracted into `components/RemovePhotoButton.tsx`; it moves here from the class panel's student sheet (shown only if the header's `has_own_avatar` is true).
- **Grades** (only when `grades` is present): one row per class (class name + total via `formatPoints`); tapping opens the breakdown, rendered by `components/GradeBreakdown.tsx` — extracted from the class panel's student sheet and used by both. Own profile shows the note "Sólo tú y tu profe ven esto" (placeholder).
- **Tabs** (preset `Tabs`): Publicaciones | Respuestas; infinite scroll like the feed (sentinel), feed skeletons while loading, empty states "Todavía no publica nada" / "Todavía no responde nada" (placeholders). Items render with `PostCard` (aura, veto, photos, "ver más" all work). In Respuestas each item has a line above it, "Respondiendo a @{user}: {excerpt}", linking to the parent's thread.
- **Unknown user:** "Ese usuario no existe" with a link to the feed.
- All copy in `es.ts`, in **tú**. Every points value through `formatPoints`.

## 3. Every username and avatar is a link

- `components/UserLink.tsx`: `UserLink({ user, avatar?, size? })` — renders `@username` (or the avatar when `avatar` is set) as `<Link to="/u/:username">`; a user with no username yet renders plain text.
- Used wherever a username or avatar is printed today: `PostCard` (header avatar + name — outside the body link, which already wraps only the text), `Thread`, `Revisar` rows (entregas, participaciones), `ExamenRoster`, `ReviewSheet`. In `ClassPanel` the list rows keep opening the grade sheet; the sheet title links to the profile.
- No link nested inside another link; inside clickable rows the link stops propagation so it doesn't also fire the row's action.
- `CLAUDE.md` gains a development rule: "Every username or avatar goes through `UserLink`."

## 4. Tests

**Backend** (first):
- Header: fields present (including `has_own_avatar`); `avatar_url` follows `avatar_for`; `is_me` true only for the owner; 404 for an unknown username.
- `aura_received` sums active posts only — a deleted and a vetoed post with likes don't count.
- Grades: owner gets one row per active class; teacher gets only their classes; a classmate gets **no `grades` key**; another teacher (not teaching that student) gets no key. `summary` equals what `/api/classes/{id}/students/{id}/grade` returns.
- Posts tab: top-level only, newest first, deleted excluded, vetoed included, pagination with `next_cursor`.
- Replies tab: replies only, entregas excluded, `parent.excerpt` present.
- Scoping: a student never sees, on the teacher's profile, a tarea from a class they aren't in, nor (in replies) a reply inside another class's examen; they do see tareas of their own class. The feed's existing scoping tests still pass unchanged after `get_feed` moves to the shared helper.

**Frontend:** no new pure logic (the excerpt is cut server-side), so no new unit tests; types, lint, build. Phone QA after deploy: tap a name in the feed → profile → back; own profile edit sheet; teacher sees a student's grade breakdown, a classmate doesn't.

## Commit order (each deployable)

1. Backend: `services/visibility.py` + `get_feed` refactor (no behaviour change).
2. Backend: profile header + posts endpoints.
3. Frontend: `/u/:username` page (header, tabs, grades with `GradeBreakdown`, `ProfileEditor`, `RemovePhotoButton`), nav + `/perfil` redirect.
4. Frontend: `UserLink` everywhere + the `CLAUDE.md` rule.

## Out of scope

Following/followers, profile search, activity/notifications (Bloque 5), feed ranking (Bloque 4), ghost/polizón badges (separate roadmap item).
