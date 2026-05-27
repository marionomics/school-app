# Forum Moderation: Points Revocation & Penalty System

**Date:** 2026-05-26  
**Status:** Approved  
**Scope:** Forum moderation — when a teacher deletes a student's post, earned points are revoked automatically. Teacher may optionally apply an additional penalty with an optional message.

---

## Problem

Currently, when a teacher deletes a forum post via `DELETE /api/forum/posts/{id}`, the associated `ForumPoints` records remain in the database. This means the student's grade is unaffected despite the post being removed for poor quality. Teachers have no mechanism to discourage spam or low-effort content.

---

## Goals

1. Auto-revoke all `ForumPoints` earned from a post when a teacher deletes it.
2. Allow the teacher to optionally apply an additional point penalty with an optional text message.
3. Notify the student via a visible banner in the forum section (visible for 7 days, no dismiss required).

---

## Out of Scope

- Penalizing replies (only posts)
- Revoking points when a student deletes their own post
- A "read/unread" system for notifications
- Push notifications or email alerts

---

## Data Layer

### Changes to `forum_points` table

Two new nullable columns added via `_ensure_columns()` in `app/main.py`:

| Column | Type | Purpose |
|---|---|---|
| `class_id` | `INTEGER` FK → `classes.id` (nullable) | Links penalty records to a class without needing an active post |
| `message` | `VARCHAR(300)` (nullable) | Optional moderator message shown to the student |

Existing rows are unaffected (`class_id = NULL`, `message = NULL`).

### Penalty record shape

When a teacher applies a penalty, a new `ForumPoints` row is inserted:

```
user_id      = post.author_id
post_id      = NULL              # post is being deleted
class_id     = post.class_id    # class context for grade calc
points_earned = -(penalty_amount)
bonus_type   = 'penalty'
message      = teacher's optional text (or NULL)
created_at   = now()
```

### Revocation

All `ForumPoints` rows where `post_id == deleted_post_id` are deleted before the post is removed. No new rows are created for revocation — the records simply disappear.

---

## Backend Changes

### 1. `DELETE /api/forum/posts/{post_id}`

Accepts an optional JSON body (only honored when a teacher deletes another user's post):

```json
{
  "penalty": 1.5,
  "message": "Post sin contenido académico"
}
```

New internal flow:
1. Authorize (author or teacher).
2. **If teacher deleting another's post:**
   a. Delete all `ForumPoints` where `post_id == post_id` (revocation).
   b. If `penalty > 0`: insert penalty `ForumPoints` record (see shape above).
3. Delete R2 file if present.
4. Delete the post.
5. Return `{ "message": "Post eliminado", "points_revoked": float, "penalty_applied": float }`.

### 2. Grade calculation (`routes/students.py → get_grade_calculation`)

The `forum_pts_raw` query is updated to include penalty records (which have `post_id = NULL` but `class_id` set):

```python
from sqlalchemy import or_

forum_pts_raw = db.query(func.sum(ForumPoints.points_earned)).filter(
    ForumPoints.user_id == current_student.id,
    or_(
        ForumPoints.post_id.in_(
            db.query(ForumPost.id).filter(ForumPost.class_id == class_id)
        ),
        ForumPoints.class_id == class_id,  # penalty records
    )
).scalar() or 0.0
```

### 3. New endpoint: `GET /api/forum/penalties/recent?class_id=X`

Returns penalty records for the current user in the given class, created within the last 7 days:

```json
[
  {
    "points_earned": -1.5,
    "message": "Post sin contenido académico",
    "created_at": "2026-05-24T10:30:00"
  }
]
```

- Requires auth (student role reads own records; teacher could be excluded or included — no need to filter by role since penalty records only exist for students).
- Filters: `bonus_type == 'penalty'`, `class_id == class_id`, `created_at >= now - 7 days`.

---

## Frontend Changes

### 4. Delete confirmation modal (shared component)

Replaces `confirm()` in **both** `forum.js` and `home.js` when a teacher deletes another user's post. Self-deletion continues to use `confirm()`.

A single `<div id="delete-post-modal">` is added to `forum.html` and `index.html`. JS populates and shows it dynamically.

**Modal structure:**
```
┌─────────────────────────────────────────┐
│ 🗑 Eliminar publicación de {nombre}     │
│                                         │
│ "{snippet de 80 chars del post}"        │
│                                         │
│ ─────────────────────────────────────── │
│ ⚠ Se revocarán los puntos de foro      │
│   que ganó este post ({X} pts).        │
│                                         │
│ ☐ Penalizar adicionalmente              │
│   [  1.0  ] pts                        │
│   Motivo (opcional): [____________]    │
│                                         │
│            [Cancelar]  [Eliminar]      │
└─────────────────────────────────────────┘
```

**Behavior:**
- Penalty fields (input + motivo) are hidden until the checkbox is checked.
- "Eliminar" sends `DELETE` with body `{ penalty, message }` when penalty > 0.
- Modal closes on Cancelar or click-outside.
- Styled with warm palette: rust/orange for the delete button, no purple/violet.

### 5. Student notification banner (`home.js`, `forum.js`)

On forum section load, calls `GET /api/forum/penalties/recent?class_id=X`. If results exist, renders a banner above the post feed:

```
┌─────────────────────────────────────────────────────┐
│ ⚠  Se eliminó una publicación tuya                  │
│    -1.5 pts de foro · hace 2 días                   │
│    "Post sin contenido académico"  (if message)     │
└─────────────────────────────────────────────────────┘
```

**Behavior:**
- Style: `bg-amber-50 border border-amber-300 text-amber-800`, rounded, padding sm.
- Multiple penalties → stacked banners, one per record.
- No dismiss button — banners disappear naturally after 7 days (server-side filter).
- Only rendered when `currentUser.role !== 'teacher'`.

---

## File Map

| File | Change |
|---|---|
| `app/main.py` | Add `class_id` + `message` columns to `_ensure_columns()` |
| `models/models.py` | Add `class_id` + `message` fields to `ForumPoints` model |
| `models/schemas.py` | Add `DeletePostRequest` schema (`penalty: float = 0`, `message: str = ""`) |
| `routes/forum.py` | Update `delete_post`; add `GET /penalties/recent` endpoint |
| `routes/students.py` | Update `forum_pts_raw` query with `OR class_id == class_id` |
| `static/js/forum.js` | Replace `confirm()` with modal for teacher moderation; add banner |
| `static/js/home.js` | Same modal + banner integration |
| `static/forum.html` | Add modal HTML |
| `static/index.html` | Add modal HTML |
