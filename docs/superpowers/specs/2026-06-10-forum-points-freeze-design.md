# Forum Points Freeze — Design Spec

**Date:** 2026-06-10
**Status:** Approved

## Summary

Add a global toggle that lets the teacher freeze forum points at end of semester. When frozen, likes and posts still work normally but no new points are awarded. Existing points in `forum_points` are never modified.

## Backend

### New Model: `AppConfig`

New table `app_config` in `models/models.py`:

```python
class AppConfig(Base):
    __tablename__ = "app_config"
    id = Column(Integer, primary_key=True, default=1)
    forum_points_enabled = Column(Boolean, default=True)
```

Always exactly one row (id=1). Created automatically by `Base.metadata.create_all()`.

### Startup Initialization

New function `_ensure_app_config()` called in `app/main.py` startup, after `_ensure_columns()`:

```python
def _ensure_app_config(db):
    if not db.query(AppConfig).filter_by(id=1).first():
        db.add(AppConfig(id=1, forum_points_enabled=True))
        db.commit()
```

No ALTER TABLE needed — the table is entirely new.

### New Endpoint: `PATCH /api/admin/config`

Teacher-only. Accepts `{ "forum_points_enabled": bool }`. Updates id=1 row. Returns updated config.

### Updated Endpoint: `GET /api/config`

Already exists. Add `forum_points_enabled` to its response so the frontend can read the initial state on load.

### Forum Routes Changes (`routes/forum.py`)

In `toggle_like` and `create_post`, load `AppConfig` before the points logic:

```python
app_config = db.query(AppConfig).filter_by(id=1).first()
if not app_config or not app_config.forum_points_enabled:
    # skip all points logic
```

The like/post is still recorded. Only point awards are skipped. The response still returns `points_awarded: 0.0` and `bonus_type: None` so the frontend handles it cleanly.

## Frontend

### Admin Panel (`admin.html` / `admin.js`)

A status card rendered in the main admin panel on load, after fetching `GET /api/config`.

**When active:**
- Green/neutral indicator: `● Puntos del foro activos`
- Button: `Congelar puntos` (neutral style)

**When frozen:**
- Muted indicator: `■ Puntos del foro congelados`
- Button: `Reactivar puntos` (primary orange style)

Clicking either button calls `PATCH /api/admin/config`, updates local state, and re-renders the card. No page reload.

### Student-facing behavior

No visible change to students except casino toasts do not appear when `points_awarded == 0` (this already works — the toast logic only fires when `points_awarded > 0`).

## Behavior

- **Existing points preserved** — `forum_points` rows are never modified on freeze.
- **Likes/posts unaffected** — students can still post and like; they just earn no points.
- **Default state** — `forum_points_enabled = True` (points active on all new deployments).
- **No per-class granularity** — this is intentionally global; one switch covers all classes.

## Files to Change

| File | Change |
|---|---|
| `models/models.py` | Add `AppConfig` model |
| `app/main.py` | Import `AppConfig`; add `_ensure_app_config()` call at startup |
| `routes/forum.py` | Check `AppConfig.forum_points_enabled` in `toggle_like` and `create_post` |
| `routes/admin.py` | Add `PATCH /api/admin/config` endpoint |
| `app/main.py` or `routes/` | Update `GET /api/config` to include `forum_points_enabled` |
| `static/admin.html` | Add forum points status card markup |
| `static/js/admin.js` | Render card, handle toggle button, call new endpoint |
