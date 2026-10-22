# Bloque 4b — Feed tiers: touched sinks to the bottom, the teacher's pending work rises

**Status:** design approved by Mario on 2026-10-21, section by section in chat. Amends `2026-10-21-feed-ranking-design.md` (Bloque 4); everything there stands unless this document says otherwise.

## Why

Mario's first look at Bloque 4 (2026-10-21): "it shows me things I already gave aura to, and when I refresh it stays the same — refreshing should restart and show you something new." The soft penalty (aura = one day older) cannot do that in a classroom: posts arrive in the same hour and the teacher touches nearly all of them, so everything sinks by the same factor and the order holds. And for the teacher the feed is also a work queue: participaciones to validate, homework to grade.

## Decisions

1. **Touched goes below everything untouched** (Mario, 2026-10-21 — option B from the morning, which the first design talked him out of). The soft factors stay inside each tier.
2. **A reply to you brings a post back to the untouched tier** — the conversation exception still holds. Aura never does.
3. **The teacher's pending work goes on top, mixed into the feed** (Mario, option A), not a separate pinned list.
4. **Pending is newest first** (Mario, option B): in class the live participación is the one that needs aura; the backlog rises as it is cleared.
5. **Homework shows as the tarea/examen card with "N por calificar"** (Mario, option A), never as entrega cards.
6. **Pending means what `/revisar` means**, evaluated as of `as_of`.

## 1. Tiers

The feed is ordered by tier, then within the tier:

| Tier | Who | What | Order within |
|---|---|---|---|
| 1 | teacher only | their pending work (§2) | `pending_at` newest first, then `post_id` desc |
| 2 | everyone | untouched posts, and touched posts with lift > 0 | `score` (Bloque 4 formula) |
| 3 | everyone | touched posts without lift | `score` |

"Touched" = authored the root, replied in the thread, or gave the root aura — all at or before `as_of` (the same touches `score` uses). "Lift > 0" = a reply by someone else after the viewer's last touch that `score` counts as lift (to the viewer, or in a thread they're subscribed to). Replies under a tarea/examen root never count (Bloque 4 decision 8b), so they never lift.

A tier-1 post is never also placed in tier 2/3 — the tier is a single value per post.

## 2. The teacher's pending work

Only for a viewer with `role == "teacher"`, and only items in classes where `Class.teacher_id == viewer.id`. Computed against `as_of` so every page of one load agrees.

- **Participación pending:** `type == "participacion"`, `status == "active"`, `created_at ≤ as_of`, and `reviewed_at IS NULL OR reviewed_at > as_of`. (Same as `/revisar` pending: not validated, not vetoed, not deleted.) `pending_at = created_at`. No count.
- **Tarea pending:** `type == "tarea"`, `status == "active"`. For each active-enrolled student, their counting entrega as of `as_of` = latest `is_entrega` reply with `status == "active"` and `created_at ≤ as_of`. It is ungraded unless a review exists for (tarea, student) with `entrega_post_id == that entrega` (or NULL) and `COALESCE(updated_at, created_at) ≤ as_of` — the `counting_review` rule, bounded by `as_of`. Pending if at least one ungraded entrega; `pending_at` = the newest ungraded entrega's `created_at`; `pending_count` = number of ungraded entregas.
- **Examen pending:** `type == "examen"`, `status == "active"`, and `graded_at IS NULL OR graded_at > as_of`, with at least one submission as of `as_of` by an active-enrolled student — a submission is an active `is_entrega` reply, or an active reply with attachments (the roster's `_examen_submission` rule). `pending_at` = the newest submission's `created_at`; `pending_count` = active-enrolled students with a submission and no review with a score.

Pending items join the ranked candidates even when they fall outside the 14-day window; otherwise an old participación would never come up.

**Scope (final-review ruling):** only classes whose `end_date` is no more than 14 days before `as_of` — the feed spans every semester, and last term's unreviewed work must not sit on top forever. The teacher's own tareas are never pinned under "Por entregar" (a student's list); they appear in the feed with their badge.

**Known tolerance:** re-grading, removing aura (un-validating) or un-marking calificado mid-scroll can make an item pending again on later pages of the same load (one duplicate or skip). A veto is not timestamped either, so a participación vetoed mid-scroll can shift a later page by one (as in Bloque 4).

## 3. API

- `PostOut.pending_count: Optional[int] = None` — set on `/api/feed` items (and the pinned list is unaffected) only for the teacher's pending tareas/exámenes. Everywhere else `None`.
- No new endpoint. `has-new` is unchanged.

## 4. Client

- `PostCard` shows a badge **"{n} por calificar"** when `pending_count` is a positive number, next to the Tarea/Examen badge. Placeholder copy in `es.ts` (`feed.toGrade`); Mario writes the final text.
- Nothing else changes: validating and grading still patch in place and never reorder until refresh.

## 5. Tests

Pure (`test_feed_rank.py`): tier 1 above tier 2 above tier 3; tier 1 newest-first by `pending_at`; a reply to the viewer after their touch puts the post in tier 2; an aura'd post with a later reply in an unsubscribed thread stays in tier 3; no pending map → no tier 1.

Endpoint (`test_feed_tiers.py`):
- Student: a post they gave aura goes below an older untouched post.
- Teacher: a pending participación sits above a newer regular post; after validating (aura) it falls to tier 3 on the next load.
- A tarea with an ungraded entrega rises with `pending_count == 1`; grading it drops it; a later entrega from another student brings it back with the newest `pending_at`.
- An examen with an uploaded submission rises; a paper examen with nothing uploaded does not; a calificado examen does not.
- Another teacher's class's participación never enters tier 1; students never get `pending_count`.
- Pending older than 14 days still appears in tier 1.
- Paging with one `as_of` stays exhaustive and duplicate-free while the teacher validates between pages.

## Out of scope
Counters or a link to `/revisar` (option C), re-pinning a tarea after a deleted entrega, impressions.
