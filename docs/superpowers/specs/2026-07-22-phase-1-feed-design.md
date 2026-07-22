# Phase 1 — El Feed: Design Spec

**Date:** 2026-07-22
**Status:** Approved design, pre-implementation
**Parent spec:** `2026-07-19-v2-platform-rebuild-design.md` (§3 posts/likes/ledger, §4 grade engine, §5 UX)
**Builds on:** Phase 0 (auth, users, classes, enrollments — merged to main)

## 1. Scope

The feed slice of the platform: posts, threaded replies, likes, attachments, the participación tap button, the append-only points ledger, and the live grade chip. First version testable with real users.

**In:** everything below. **Out (Phase 2+):** tarea/examen post types, entregas, Revisar queue, incentives admin, attendance, notifications, salvando el semestre.

Decisions made here that refine the parent spec:
- **Engagement-bump feed** (not purely chronological): posts order by `last_activity_at` — new replies and likes bump a post; quiet posts sink. (Skool-style; requested by Mario.)
- **No daily post limit.** Engagement is the goal; takedown moderation is the backstop. `daily_post_limit` is dropped from the config design.
- **Unlike revokes the point** (net per liker is always 0 or 1 — unexploitable).
- **Unified removal rule:** a post's points exist only while the post exists — author delete AND teacher veto both revoke all points the post generated. (Replaces the v1 "deletion keeps points" rule.) Egregious cases can get an extra manual penalty (ledger `penalty` row; UI for this lands with Phase 2's Revisar).
- **Replies earn like-points too** — replies are posts; helping compañeros is rewarded ("mentoría" goal).

## 2. Data model (Alembic migration, 4 tables)

### posts
`id, author_id (FK users), type ('regular'|'participacion'), class_id (FK classes, nullable), parent_id (FK posts, nullable), content (text), taps (int 1–3, participacion only, else NULL), status ('active'|'deleted'|'vetoed'), like_count (int, denormalized), reply_count (int, denormalized), last_activity_at (tz datetime, indexed), created_at, edited_at (nullable)`

- Replies: `parent_id` set; max depth 3 (post → reply → reply-to-reply); depth validated at creation.
- `type` is extensible — `'tarea'`/`'examen'` arrive in Phase 2 with no schema change.
- `last_activity_at` = `created_at` at insert; bumped to now() on every new reply or like anywhere in the post's thread (replies bump their root post too).
- **No hard deletes.** `'deleted'` (author) / `'vetoed'` (teacher removing someone else's post). A removed post with visible replies renders as "[eliminado]" placeholder preserving the thread; with none, it's filtered out of the feed. Avoids PostgreSQL FK-cascade hazards entirely and keeps the audit trail.
- **Class attribution:** student posts always get `class_id` — auto: the class currently in session per its `schedule_json` (evaluated in `TIMEZONE` env, default `America/Mexico_City`); else the student's only active enrollment; else the composer requires a pick. Teacher posts may be class-less. **Replies do NOT inherit the root post's class** — each reply carries its own author's class attribution (same auto rule), so like-points on a reply feed the *replier's* grade.

### likes
`id, user_id (FK users), post_id (FK posts), created_at` — unique `(user_id, post_id)`.
- Toggle: like inserts, unlike hard-deletes the row (the only hard delete in this phase).
- Self-likes rejected (400). Teachers can like (social signal) but generate no points.

### attachments
`id, post_id (FK posts), file_key (R2), file_name, file_size, mime_type, created_at`
- Uploaded in the same multipart request that creates the post (max 4 files/post). v1 validation rules (types, 10 MB). `file_key` never exposed; download via presigned URL endpoint. If R2 env is not configured, `/api/config` reports `file_uploads_enabled: false` and the composer hides the attach button (v1 pattern).

### points_ledger
`id, user_id (FK users), class_id (FK classes), source_type ('participacion'|'forum_like'|'incentive'|'penalty'|'bonus'|'adjustment'), source_id (int, NO FK — polymorphic; likes can be hard-deleted), points (numeric), note (text, nullable), created_at, revoked_at (nullable), revoked_by (FK users, nullable)`

- Append-only. Revocation = setting `revoked_at`/`revoked_by`; never DELETE or UPDATE of `points`.
- **Only `services/points.py` touches this table.**

### points_config (deferred)
Phase 1 hardcodes `TAP_VALUE = 1.0` and `LIKE_VALUE = 1.0` as constants in `services/points.py`. The per-class `points_config` table ships in Phase 2 with class settings UI; the service reads config-with-fallback then. (YAGNI: no table until something can edit it.)

## 3. Points service (`backend/app/services/points.py`)

```
award(db, *, user_id, class_id, source_type, source_id, points, note=None) -> LedgerRow
revoke(db, *, ledger_id, revoked_by) -> None
revoke_for_source(db, *, source_type, source_id, revoked_by) -> int   # bulk, for post removal
```

Event semantics:

| Event | Ledger effect |
|---|---|
| Participación published | `award(author, post.class_id, 'participacion', post.id, taps × TAP_VALUE)` |
| Like created | `award(post.author, post.class_id, 'forum_like', like.id, LIKE_VALUE)` |
| Unlike | revoke that like's row |
| Re-like | fresh like row + fresh award (net per liker always 0 or 1) |
| Post removed (delete or veto) | revoke ALL rows sourced from the post and its likes |
| Author is ghost 👻 / polizon 🥷, or liker is the author's teacher | no award (skip silently) |
| Author has no `class_id` on the post (teacher posts) | no award |

Rules enforced in the service, not scattered in routers: no award without active enrollment of the recipient in `class_id`; teacher recipients never earn; idempotence — awarding twice for the same `(source_type, source_id)` non-revoked row is a no-op.

## 4. API

All under existing auth (`get_current_user`). Spanish error `detail`s.

- `GET /api/feed?cursor=<b64(last_activity_at,id)>&limit=20` — top-level posts (no replies), status-visible only, keyset-paginated on `(last_activity_at DESC, id DESC)`. Each item: `id, author {id, username, name, avatar_url, role}, type, class_id, class_name, content, taps, like_count, reply_count, liked_by_me, has_attachments, attachments [{id, file_name, mime_type}], created_at, last_activity_at, status`. Removed posts excluded (feed) — shown only as placeholders inside threads.
- `POST /api/posts` — multipart: `content` (required unless files present), `type` (`regular`|`participacion`), `taps` (required 1–3 iff participación), `class_id` (per attribution rule; validated against active enrollment), `parent_id` (replies; depth ≤ 3; participación cannot be a reply), `files[]` (≤4). Awards points per §3. Returns the created post.
- `GET /api/posts/{id}` — the post + full reply tree (3 levels), removed nodes as placeholders.
- `DELETE /api/posts/{id}` — author (→ `deleted`) or teacher (→ `vetoed` when not their own). Revokes all the post's points. 204.
- `POST /api/posts/{id}/like` — toggle. Returns `{liked, like_count}`. Awards/revokes per §3. Bumps `last_activity_at`.
- `GET /api/attachments/{id}/url` — presigned R2 URL (any authenticated user; feed is global).
- `GET /api/students/me/grade?class_id=X` — Phase 1 grade: `{class_id, total, events: [{source_type, points, created_at, note}], counts: {participaciones, likes_received}}` computed live from non-revoked ledger rows. Rubros/faltas join in later phases. Omitting `class_id` → array for all active enrollments.

## 5. Frontend

This phase is also the real design pass: Threads-like, mobile-first, shadcn components replacing Phase 0's bare shell. All copy via `strings/es.ts` (draft — Mario finalizes).

- **TanStack Query** added: `useInfiniteQuery` for the feed (cursor merging, id-dedup since bumped posts can re-appear across pages), optimistic like toggle with rollback + Spanish toast on failure, cache prepend on own new post.
- **Feed (Home):** skeleton cards while loading; PostCard = avatar, `@username` (teacher badge), class chip for participaciones (🗣️ ×2 / ×3), content, attachment previews (images inline, files as chips), like ♥ + reply counts, relative timestamp; tap card → thread view.
- **Thread view:** root post + replies, 3 levels with Threads-style indentation; inline reply composer; removed nodes render "[eliminado]".
- **Composer (full-screen via ➕):** mode toggle Regular / 🗣️ Participación (students only; teachers see Regular only this phase). Class auto-attribution with visible chip (picker only when ambiguous). Attach button (hidden without R2).
  - **Tap button (participación mode):** big circular button. Tap 1 → count =1, ring countdown ~1.5 s starts; taps 2/3 → "¡doble!"/"¡triple!" feedback, ring resets; window expiry → auto-publish with celebratory animation; `navigator.vibrate` pulse per tap where supported. Escape hatch: an "×" cancels before expiry. The tap-window state machine lives in a pure hook (`useTapWindow`) — unit-tested.
- **GradeChip:** persistent in the shell header; shows live ledger total for the student's class (selector in the sheet if multiple); tap → breakdown sheet (participaciones, likes received, event list). Hidden for teachers.
- **Moderation (minimal, Phase 1):** author sees delete on own posts; teacher sees delete on all. Confirmation dialog states points will be revoked.

## 6. Feed algorithm

`ORDER BY last_activity_at DESC, id DESC` — that's the whole algorithm, server-side. New replies and likes bump the root post to now(). Unlike does not un-bump. Cursor is keyset on the same tuple; a post bumped past a reader's cursor may re-appear — the client dedups by id. Affinity/seen-post ranking stays in `future.md`.

## 7. Error handling & testing

- Points service = most-tested code: award/revoke invariants, unlike/re-like cycles, removal revokes everything, ghost/polizon/teacher exclusions, idempotence, no-enrollment guard.
- API tests: feed pagination stability under bumps, depth-3 enforcement, participación validation (taps, class, not-a-reply), like toggle, soft-delete visibility rules, attachment gating without R2.
- Frontend: vitest for `useTapWindow` and cursor-merge/dedup logic; build + lint gates already in CI (Postgres-backed backend tests unchanged).
- Optimistic updates always roll back visibly (toast) on failure; no silent divergence.

## 8. Out-of-scope notes for Phase 2 pickup

- `points_config` table + class settings UI (constants until then).
- Manual penalty UI for egregious farming (rule defined here; interface with Revisar).
- Teacher composer type selector (tarea/examen), Revisar queue, veto-with-reason flow.
- Notifications for likes/replies (mid-semester per roadmap).
