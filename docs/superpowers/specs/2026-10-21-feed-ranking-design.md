# Bloque 4 — Feed ranking

**Status:** design approved by Mario on 2026-10-21, section by section in chat. Roadmap Bloque 4. Not yet reviewed as a written spec.

## Goal

Interaction pushes posts up and some stay at the top without being relevant. Once you have interacted with a post it should sink **for you** and make room for what is new — except that a conversation you are part of comes back when it moves. And comments should be visible from the feed, because commenting is the behaviour the class wants more of.

## Decisions

1. **Ranking is per viewer**: freshness + recent activity, scaled down by your own touches, plus a lift when the conversation moves after you touched it (roadmap, confirmed 2026-10-21).
2. **Touches sink softly, by kind** (Mario, 2026-10-21, "A adjusted by C"): aura sinks a little, a reply sinks a lot. The penalty is a multiplier, so it reads as "this post is now N days older for you".
3. **A reply subscribes you to the thread** (Mario, 2026-10-21). Replying sinks the post for you right away; a later reply by someone else brings it back. Authoring a root post counts as a reply.
4. **Lift, option C** (Mario, 2026-10-21): a reply *to you* (to your post or to your comment) lifts strongly; any other reply in a thread you are subscribed to lifts less. Aura never lifts and never subscribes.
5. **Teacher validation = teacher aura** (already true since Bloque 2), so it sinks the post for the teacher like any aura.
6. **Order changes only on refresh** (Mario, 2026-10-21). Nothing moves under the finger. The ranking is frozen at load time (`as_of`) for every page of that load.
7. **Coming back to the tab never reorders; a "Publicaciones nuevas" pill appears instead** when something new exists (Mario, 2026-10-21, option C). Tapping it reloads.
8. **One featured comment under each card** (Mario, 2026-10-21), chosen by a ladder: teacher-aura'd reply → most aura → most recent. Level 2 only, active only. **Never under a tarea or examen** — every reply there may be a homework answer, and the profile already hides those (ruling while planning, 2026-10-21).
9. **Interactions only, not impressions.** "Seen" (open question 7 in `future.md`) waits until the first round is measured.
10. **Engagement data decides the weights** (Mario, 2026-10-21). All weights are named constants in one module; a metrics script compares before and after.
11. **The comment prize** (random ×2/×3 for commenting) is out of scope — it moves points, so it belongs to the grade engine and gets its own spec. Recorded in `future.md`.

## 1. The score — `backend/app/services/feed_rank.py`

Pure functions over plain data (dataclasses, no ORM, no DB), tested like the grade engine.

### Inputs

```python
@dataclass(frozen=True)
class Candidate:
    post_id: int
    author_id: int
    created_at: datetime
    replies: tuple["ReplyFact", ...]     # every level-2 and level-3 reply in the thread, created ≤ as_of

@dataclass(frozen=True)
class ReplyFact:
    author_id: int
    created_at: datetime
    parent_author_id: int                # author of the post it answers (root or a level-2 reply)
    active: bool                         # status == "active"

@dataclass(frozen=True)
class ViewerTouches:
    aura_at: dict[int, datetime]         # post_id → when the viewer gave aura to the ROOT, ≤ as_of
```

Reply and authorship touches are derived from `Candidate` itself (the viewer authored the root, or authored a reply in `replies`).

### Formula

All ages are hours before `as_of`. `decay(h) = 0.5 ** (h / HALF_LIFE_H)`.

```
base     = W_FRESH · decay(age(root))
         + W_ACTIVITY · log1p( Σ decay(age(r))  for active replies r by anyone but the viewer )
factor   = REPLY_FACTOR  if the viewer authored the root or any reply in the thread
           AURA_FACTOR   elif the viewer gave aura to the root
           1.0           otherwise
last     = the viewer's most recent touch (authorship, reply or aura), or None
lift     = W_LIFT · log1p( Σ w(r) · decay(age(r))  for active replies r with created_at > last,
                                                    by someone other than the viewer )
           where w(r) = LIFT_TO_ME     if r.parent_author_id == viewer
                        LIFT_IN_THREAD if the viewer is subscribed (factor == REPLY_FACTOR)
                        0              otherwise
score    = base · factor + lift
```

Ties break on `post_id` descending, so the order is total and deterministic.

### Starting weights

| Constant | Value | Meaning |
|---|---|---|
| `HALF_LIFE_H` | 24 | a post's freshness halves every day |
| `W_FRESH` | 1.0 | a brand-new post scores 1.0 |
| `W_ACTIVITY` | 0.4 | `log1p` so a 30-reply thread does not own the feed |
| `AURA_FACTOR` | 0.5 | aura = the post is one day older for you |
| `REPLY_FACTOR` | 0.125 | reply/authorship = three days older for you |
| `W_LIFT` | 1.5 | a fresh reply to you (`1.5·log1p(1) ≈ 1.04`) beats a brand-new post |
| `LIFT_TO_ME` | 1.0 | |
| `LIFT_IN_THREAD` | 0.25 | |
| `WINDOW_DAYS` | 14 | candidate window, see §2 |

These are starting points to be tuned with data, not results of a calculation.

### What is a candidate

Root posts (`parent_id IS NULL`), `status IN ('active','vetoed')` — vetoed posts stay in the feed as today — passing `assignment_visible(viewer_class_ids(...))` from `services/visibility.py`, with `created_at ≤ as_of`. Pinned tareas are still returned separately by `_pinned_tareas`, unchanged.

### The featured reply — `pick_featured(replies, teacher_aura_ids)`

Only for `regular` and `participacion` roots (a tarea's or examen's replies are homework answers — see decision 8). Among level-2 replies (direct answers to the root) with `status == 'active'`:
1. those with teacher aura, then
2. highest `like_count`, then
3. most recent `created_at`, then highest `id`.

Returns at most one. No reply → `None`. Pure function, own tests.

## 2. Pagination, API and client

### `GET /api/feed?cursor=&limit=20`

- **No cursor:** `as_of = now()`.
- **Cursor:** base64 of `{as_of, offset}` (replaces the keyset cursor in `services/cursor.py`; the profile cursor is untouched). An undecodable cursor → 422, as today.
- **Ordered list for a given `as_of`:**
  1. **Window, ranked:** candidates with `created_at ≥ as_of − WINDOW_DAYS`, **or** with at least one reply whose `created_at` is in `[as_of − WINDOW_DAYS, as_of]`. Scored with `feed_rank`, sorted by score.
  2. **Tail, chronological:** every other candidate, ordered by `created_at DESC, id DESC`. Old posts still appear; the feed never ends early.
  Window membership is defined only by `created_at` values, which never change, so every page of one load sees the same list.
- **Page** = `list[offset : offset + limit]`. Re-ranking the window on every page is acceptable at this scale (a few hundred candidates); no snapshot table.
- **Known tolerance:** a status change after `as_of` (a reply deleted, a post vetoed) is not timestamped and can shift a later page by one. `mergePages` already de-duplicates by id; a rare skip is accepted.
- **Response** gains:
  - `as_of` (ISO string) at the top level;
  - `featured_reply: Post | null` on every item, serialized with `serialize_post` (it carries `liked` and teacher aura like any post);
  - `pinned` and `next_cursor` keep their meaning.
- Liked ids, teacher-aura ids and featured replies are loaded in batch for the page, never per post.

### `GET /api/feed/has-new?since=<iso>`

`{"has_new": bool}`. True when, after `since`, there is a visible root post by someone else, or a reply by someone else in a thread the viewer is subscribed to (authored the root or a reply in it). One `EXISTS` per condition.

### Client

- **The feed query never refetches on its own:** `staleTime: Infinity`, `refetchOnWindowFocus: false` on `["feed"]`.
- **One helper, `refreshFeed(qc)`** (in `frontend/src/lib/feed.ts`), resets the infinite query to its first page (`qc.resetQueries`) — refetching every stored page would mix a new `as_of` with old cursors. It is called only from:
  - publishing a post (`Compose.tsx`), as today;
  - tapping **Inicio** while already on Inicio (and scroll to top);
  - tapping the **Publicaciones nuevas** pill (and scroll to top).
- **Every other `invalidateQueries(["feed"])` goes away** (`Thread.tsx` reply and delete, `Revisar.tsx` validate/bulk/veto, `RemovePhotoButton.tsx`). They patch the cached post instead through `postCache.ts` (reply count, teacher aura, veto status, deleted root removed from the list). Otherwise coming back from a thread would reorder the feed and lose the scroll position.
- **The pill:** on `visibilitychange` to visible and on mounting Home, call `has-new` with the first page's `as_of`; if true, show a pill at the top of the feed. Placeholder copy in `es.ts` (`feed.newPosts`); Mario writes the final text.
- **The featured reply** renders under the card: author through `UserLink`, its text clamped to two lines, its aura count, and a "Ver las N respuestas" link to the thread (placeholder copy). Tapping it opens the thread. No action buttons on the featured reply in the feed.
- Aura and veto from the feed keep patching the cache; nothing about them changes.

## 3. Tests and measurement

### Unit — `backend/tests/test_feed_rank.py`
- A newer post beats an older one, all else equal.
- Aura sinks a post by exactly one half-life; a reply sinks it by three.
- Authoring a root post counts as a reply.
- A reply to the viewer after their touch brings the post above a fresh untouched post.
- A reply in a subscribed thread lifts less than a reply to the viewer; a reply in a thread the viewer only gave aura to does not lift.
- The viewer's own replies never count as activity or lift.
- Deleted/vetoed replies count for nothing.
- Touches and replies after `as_of` are ignored.
- Ties break on `post_id`.
- `pick_featured`: teacher aura beats more aura; more aura beats recency; level-3 and non-active replies are never picked.

### Endpoint — `backend/tests/test_feed.py`
- Paging with one `as_of` returns every candidate exactly once, even when the viewer gives aura and new posts are created between pages.
- The class filter still applies (another class's tarea never appears); pinned tareas unchanged.
- Window then tail: an old post with no recent replies appears after every windowed post.
- `featured_reply` present and correct; `null` without replies.
- `has-new`: false right after load; true after another user posts; true after a reply in a subscribed thread; false for a reply in an unrelated thread; the viewer's own post does not count.
- Invalid cursor → 422.

CI on PostgreSQL, as always.

### Measurement — `backend/scripts/feed_metrics.py`
Reads existing tables only. Prints, per ISO week: replies per active student (students with at least one post or reply that week), and the share of root posts that got at least one reply. Run before deploying and again two or three weeks after; the numbers decide whether to tune the weights or open question 7.

## Out of scope
Impressions/"seen", affinity, the comment prize, notifications (Bloque 5 will reuse the "reply to you" signal), more than one featured reply.
