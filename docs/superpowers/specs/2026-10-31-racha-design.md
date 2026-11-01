# Racha — a streak that raises the odds of 2× / 3× aura

**Status:** design approved by Mario on 2026-10-31, section by section in chat. Roadmap: "Racha (Mario, 2026-10-28)". Absorbs "Premio por comentar" from `planning/future.md`.

## Why

Mario (2026-10-28): the point is for students to be on the platform *and actually move forward*. Keeping a daily streak raises the chance that the aura a post receives counts **2× or 3×** — the longer the streak, the likelier. Seeing your post "come out" triple is the hook; the concave aura curve keeps it from becoming a way to cram points.

Success: more students contribute on more days, without the feed filling up with junk posted only to keep a streak.

## Decisions (Mario)

1. **Any contribution keeps the streak** (option B): a post, a reply, a participación or an entrega. A student who publishes daily and gets no streak would not understand why.
2. **Calendar days** (option A): every day counts, weekends included; a missed day breaks it. No comodín for now (noted in `future.md`).
3. **Levels, configurable per class** (option B), default table below.
4. **The multiplier weighs that post's auras in N** (option A): a 3× post with 4 auras adds 12 to the aura count, not 4. The curve is unchanged.
5. **What counts as a contribution:** ≥ 20 characters of text, or a photo/file. Vetoed or deleted posts don't count. A roll already made is never recomputed.
6. **One streak per student**, never per class. The class only decides which odds table a roll uses (the post's class, like every other setting).
7. **The 2×/3× badge is visible to everyone.**
8. **"Hoy aún no"** shows when the student hasn't contributed today.

## 1. Rules

**Counting contribution:** a post (root or reply, any type) that is `active`, written by a student (`role != "teacher"`), whose `content.strip()` has ≥ 20 characters **or** that has at least one attachment.

**Streak (computed, never stored):** let `D` be the set of calendar dates, in `settings.timezone` (America/Mexico_City), on which the student has at least one counting contribution. The streak is the length of the run of consecutive dates in `D` ending **today**, or, if today ∉ `D`, ending **yesterday**; 0 otherwise. `today_done = today ∈ D`. Because it is computed from posts, deleting or a veto of yesterday's post shortens today's streak (no evidence, no points).

**Roll:** at publish, a counting contribution is rolled **once** when the author has an `active` enrollment in the post's class (`posts.class_id`). Teachers, ghost 👻, polizón 🥷 and posts with no class get no roll (the post still counts for the streak if it qualifies). The streak used is the one **including this post** (so the first post of the day counts the day). Odds come from the class's level table for that streak; one uniform draw `u ∈ [0,1)`: `u < x3 → 3`, else `u < x3 + x2 → 2`, else `1`. The draw is on the server. Every roll — including 1× — is stored.

**Default level table** (`from_days` inclusive; the highest level whose `from_days ≤ streak` applies; below the first level, 0/0):

| from_days | x2 | x3 |
|---|---|---|
| 3 | 0.15 | 0.00 |
| 7 | 0.20 | 0.05 |
| 14 | 0.25 | 0.10 |

**Aura with multipliers:** today `likes = like_value × N^like_exponent` with `N` = count of non-revoked `forum_like` ledger rows for the student in the class. Now `N = Σ over those rows of multiplier(post the like is on)`, where the multiplier is the post's `post_rolls.multiplier`, or 1 if the post has no roll. The engine still never sums the like rows' `points` column; it counts, weights, then applies the curve. Teacher aura still awards nothing. A deleted or vetoed post revokes its like rows, so its multiplier contributes nothing.

Worked example (exponent 0.5, like_value 1): a 3× post with 4 auras → a student at N=4 goes from 2.00 to √12 = 3.46 (+1.46); a student at N=96 goes from 9.80 to √108 = 10.39 (+0.59; the same 4 auras at 1× would give +0.20). The curve makes the streak matter most to students with little aura.

## 2. Data

- New table `post_rolls`: `id`, `post_id` (FK posts, unique, ON DELETE CASCADE), `multiplier` (smallint 1|2|3), `streak_days` (int, at publish), `x2`, `x3` (numeric, the odds used), `created_at`. Append-only; never updated or deleted by the app.
- `points_config.streak_levels`: JSON list of `{from_days: int, x2: number, x3: number}`, NOT NULL with a server default equal to the table above, so every existing class has the feature on deploy with no data step.
- No backfill: existing posts have no roll (count as 1×). Past streaks *do* count, since the streak is computed from posts.

## 3. Backend

- `app/services/streak.py` — pure functions: `contribution_dates(db, user_id) -> set[date]`, `streak_days(dates, today) -> int`, `level_for(days, levels) -> (x2, x3)`, `roll(x2, x3, u) -> int` (u injected for tests), `is_contribution(post) -> bool`.
- `create_post`: after the post (and its attachments) are flushed, if `is_contribution(post)` and the author is active in `post.class_id`, compute the streak, look up the odds in that class's config, draw, insert `post_rolls`.
- `grades.ledger_breakdown`: weight the like count by joining non-revoked `forum_like` rows → `likes.id = source_id` → `likes.post_id` → `post_rolls.multiplier` (default 1). `likes_count` stays the raw count for display; add `likes_weighted` for the curve.
- `PostOut.multiplier: Optional[int]` — 2 or 3 when the post rolled 2×/3×, else null. Visible to everyone; blank for deleted posts.
- `GET /api/streak/me` → `{days, today_done, level: {from_days, x2, x3} | null, next_level_at: int | null, odds: {x2, x3}}`, odds from the student's first active class (the one the composer defaults to); teachers get `days: 0` and no odds.
- `GET /api/users/{username}` gains `streak_days` (public, like the aura count).
- Configurar: the points-config endpoint reads/writes `streak_levels`. Validation: `from_days` ≥ 1 and strictly increasing; `0 ≤ x2, x3`; `x2 + x3 ≤ 1`; at most 8 levels. All zeros is allowed (turns streak odds off for a class).

## 4. Frontend

All strings placeholders in `strings/es.ts` (tú); icons from `@remixicon/react`; preset components only; mobile first.

- **Top bar** (`Shell.tsx`, next to the grade bubble): `RiFireFill` + days. 0 days → `RiFireLine`, muted. `today_done == false` → muted with "hoy aún no" under the number. Tap → a sheet with the level table, the current level highlighted, and "te faltan N días para el doble/triple".
- **Post card:** a "2×"/"3×" badge beside the existing type badges, for everyone.
- **Publish:** if the response's `multiplier` is 2 or 3, a toast "¡Tu publicación salió doble/triple!"; then refresh the streak query.
- **Profile:** "Racha: N días" next to the aura count.
- **Configurar → Racha:** an editable list, one row per level ("desde N días", 2×%, 3×%), add/remove level; summary in the group list "Racha: 3/7/14 días".
- **Grade sheet:** the aura line keeps showing the raw count; points come from the weighted count (the curve already explains "aura → puntos").

## 5. Edge cases

- Day boundaries are computed in `settings.timezone` on the server, never on the phone.
- A post edited later: posts can't be edited, so a roll can't be gamed by editing.
- Deleting and reposting to fish for a better roll is possible but pointless to farm: the deleted post's auras are revoked with it, and a roll only pays if classmates give the new post aura.
- Unlikes revoke the like row → the weighted count drops by that post's multiplier.
- `points_config.daily_post_limit` exists but is not enforced anywhere today; this block does not change that (noted in `future.md` if rolls get farmed).

## 6. Testing

- **Engine (pure, most tested):** streak — consecutive days, a gap breaks it, ends yesterday when today is empty, timezone around midnight, vetoed/deleted posts don't count, the 20-character minimum, attachment-only counts, teacher posts don't count; `level_for` boundaries; `roll` with injected `u` at each threshold; weighted N through `like_points`, revoked likes excluded, posts without rolls = 1×.
- **API:** one roll per qualifying post, stored with streak and odds; no roll for teacher / ghost / polizón / no class / too short; `multiplier` on `PostOut`; `streak/me` shape; Configurar validation; migration upgrade/downgrade with existing rows.
- **Frontend (vitest):** level / "days to next level" helper; toast text by multiplier.

## Out of scope

- Comodín / streak freeze (future.md).
- Notifications about a streak at risk (Bloque 5).
- "Best streak" history.
- Multipliers on anything other than aura (participaciones, entregas, extras are unaffected).
