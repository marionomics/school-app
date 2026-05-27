# Forum Moderation: Points Revocation & Penalty System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a teacher deletes a student's post, auto-revoke earned ForumPoints; optionally apply an additional penalty shown as a banner to the student for 7 days.

**Architecture:** Add two nullable columns (`class_id`, `message`) to `forum_points` via `_ensure_columns()`. The delete endpoint receives an optional JSON body `{penalty, message}`, deletes associated ForumPoints (revocation), and optionally inserts a negative-points penalty record. Grade calc is updated with an `OR class_id` clause to pick up penalty records. The frontend replaces `confirm()` on teacher-deletes-other with a custom modal, and shows an amber banner to students when recent penalties exist. The banner uses DOM `textContent` for all user-supplied strings (no innerHTML for user data).

**Tech Stack:** FastAPI, SQLAlchemy, SQLite/PostgreSQL, Vanilla JS, Tailwind CSS (CDN)

**Spec:** `docs/superpowers/specs/2026-05-26-forum-moderation-points-revocation.md`

---

## File Map

| File | Change |
|---|---|
| `models/models.py` | Add `class_id` + `message` fields to `ForumPoints` |
| `app/main.py` | Add `forum_points` block in `_ensure_columns()` |
| `routes/forum.py` | Add `DeletePostRequest` schema; update `delete_post`; add `GET /penalties/recent` |
| `routes/students.py` | Update `forum_pts_raw` query with `OR class_id == class_id` |
| `static/forum.html` | Add delete modal HTML before `</body>` |
| `static/index.html` | Add delete modal HTML before `</body>` |
| `static/js/forum.js` | Add modal functions; update `deletePost` + `deleteModalPost`; add banner |
| `static/js/home.js` | Add modal functions; update `deletePost` + `deleteModalPost`; add banner |

---

## Task 1 — DB: Add `class_id` and `message` columns to `forum_points`

**Files:**
- Modify: `models/models.py`
- Modify: `app/main.py`

- [ ] **Step 1.1 — Add fields to the `ForumPoints` ORM model**

In `models/models.py`, find `class ForumPoints(Base):` and add two new columns after `like_id`:

```python
class ForumPoints(Base):
    __tablename__ = "forum_points"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("forum_posts.id"), nullable=True)
    like_id = Column(Integer, ForeignKey("forum_likes.id"), nullable=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)   # NEW — for penalty records
    message = Column(String(300), nullable=True)                           # NEW — moderator note
    points_earned = Column(Float, nullable=False)
    bonus_type = Column(String(20), nullable=False, default='normal')
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("Student")
    post = relationship("ForumPost")
```

- [ ] **Step 1.2 — Add migration block to `_ensure_columns()` in `app/main.py`**

Find the last `if "..."  in inspector.get_table_names():` block in `_ensure_columns()` and append this block after it:

```python
    if "forum_points" in inspector.get_table_names():
        existing_cols = {col["name"] for col in inspector.get_columns("forum_points")}
        with engine.begin() as conn:
            if "class_id" not in existing_cols:
                conn.execute(text("ALTER TABLE forum_points ADD COLUMN class_id INTEGER"))
            if "message" not in existing_cols:
                conn.execute(text("ALTER TABLE forum_points ADD COLUMN message VARCHAR(300)"))
```

- [ ] **Step 1.3 — Restart server and verify columns**

```bash
uvicorn app.main:app --reload
```

In another terminal:
```bash
python -c "
import sqlite3
conn = sqlite3.connect('school.db')
cols = [r[1] for r in conn.execute('PRAGMA table_info(forum_points)').fetchall()]
print(cols)
assert 'class_id' in cols, 'MISSING class_id'
assert 'message' in cols, 'MISSING message'
print('OK — both columns present')
"
```

Expected: list of columns including `class_id` and `message`, then `OK — both columns present`.

- [ ] **Step 1.4 — Commit**

```bash
git add models/models.py app/main.py
git commit -m "feat: add class_id and message columns to forum_points for moderation"
```

---

## Task 2 — Backend: Update `delete_post` to revoke points and apply optional penalty

**Files:**
- Modify: `routes/forum.py`

- [ ] **Step 2.1 — Add `Body` to fastapi imports and add `DeletePostRequest` schema**

At the top of `routes/forum.py`, update the fastapi import line to include `Body`:

```python
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile, Body
```

Then, after the existing inline schema classes (e.g., after `class ForumReplyCreate`) add:

```python
class DeletePostRequest(BaseModel):
    penalty: float = 0.0
    message: Optional[str] = None
```

- [ ] **Step 2.2 — Replace the `delete_post` function**

Replace the entire existing `delete_post` function (from `@router.delete("/posts/{post_id}")` through `return {"message": "Post eliminado"}`) with:

```python
@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: int,
    payload: Optional[DeletePostRequest] = Body(default=None),
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Delete a post. Only author or teacher can delete.
    Teachers deleting another user's post may pass {penalty, message} to deduct extra points.
    All ForumPoints earned by this post are always revoked on moderation delete.
    """
    post = db.query(ForumPost).filter(ForumPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post no encontrado")

    if post.author_id != user.id and user.role != "teacher":
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar este post")

    is_moderation = user.role == "teacher" and post.author_id != user.id
    points_revoked = 0.0

    if is_moderation:
        # Revoke all points earned from this post
        point_records = db.query(ForumPoints).filter(ForumPoints.post_id == post_id).all()
        points_revoked = sum(abs(r.points_earned) for r in point_records)
        for r in point_records:
            db.delete(r)

        # Apply optional extra penalty
        penalty_amount = round((payload.penalty if payload else 0.0) or 0.0, 2)
        penalty_message = (payload.message if payload else None)
        if penalty_amount > 0:
            db.add(ForumPoints(
                user_id=post.author_id,
                post_id=None,
                class_id=post.class_id,
                points_earned=-penalty_amount,
                bonus_type="penalty",
                message=penalty_message,
            ))

    if post.file_key:
        from app.storage import is_r2_configured, delete_file
        if is_r2_configured():
            delete_file(post.file_key)

    db.delete(post)
    db.commit()
    return {
        "message": "Post eliminado",
        "points_revoked": round(points_revoked, 2),
        "penalty_applied": round((payload.penalty if payload else 0.0) or 0.0, 2),
    }
```

- [ ] **Step 2.3 — Verify revocation via curl**

With server running, delete a student's post as teacher with a penalty:

```bash
curl -s -X DELETE http://localhost:8000/api/forum/posts/1 \
  -H "Authorization: Bearer <TEACHER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"penalty": 0.5, "message": "Post sin contenido"}' | python -m json.tool
```

Expected response:
```json
{
    "message": "Post eliminado",
    "points_revoked": 0.1,
    "penalty_applied": 0.5
}
```

Verify penalty record exists and original points are gone:
```bash
python -c "
import sqlite3
conn = sqlite3.connect('school.db')
print('Penalties:', conn.execute('SELECT user_id, class_id, points_earned, message FROM forum_points WHERE bonus_type=\"penalty\"').fetchall())
print('Points for deleted post:', conn.execute('SELECT * FROM forum_points WHERE post_id=1').fetchall())
"
```

Expected: penalty row present, no rows for `post_id=1`.

- [ ] **Step 2.4 — Commit**

```bash
git add routes/forum.py
git commit -m "feat: revoke forum points on moderation delete, support optional penalty"
```

---

## Task 3 — Backend: Add `GET /api/forum/penalties/recent` endpoint

**Files:**
- Modify: `routes/forum.py`

- [ ] **Step 3.1 — Add the endpoint after `get_recent_points`**

Find `@router.get("/points/recent")` in `routes/forum.py`. After the closing of that function, add:

```python
@router.get("/penalties/recent")
async def get_recent_penalties(
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    class_id: Optional[int] = None,
):
    """Penalty records for the current user in the last 7 days.
    Pass class_id to filter to one class; omit to get all classes.
    """
    cutoff = datetime.utcnow() - timedelta(days=7)
    q = db.query(ForumPoints).filter(
        ForumPoints.user_id == user.id,
        ForumPoints.bonus_type == "penalty",
        ForumPoints.created_at >= cutoff,
    )
    if class_id is not None:
        q = q.filter(ForumPoints.class_id == class_id)
    records = q.order_by(ForumPoints.created_at.desc()).all()
    return [
        {
            "points_earned": r.points_earned,
            "message": r.message,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]
```

Note: `timedelta` is already imported at the top of `routes/forum.py`. Verify: `grep timedelta routes/forum.py`.

- [ ] **Step 3.2 — Verify endpoint**

```bash
curl -s "http://localhost:8000/api/forum/penalties/recent" \
  -H "Authorization: Bearer <STUDENT_TOKEN>" | python -m json.tool
```

Expected (student whose post was deleted in Task 2):
```json
[
    {
        "points_earned": -0.5,
        "message": "Post sin contenido",
        "created_at": "2026-05-26T..."
    }
]
```

- [ ] **Step 3.3 — Commit**

```bash
git add routes/forum.py
git commit -m "feat: add GET /api/forum/penalties/recent for student notification banner"
```

---

## Task 4 — Backend: Update grade calculation to include penalty records

**Files:**
- Modify: `routes/students.py`

- [ ] **Step 4.1 — Add `or_` to sqlalchemy imports**

In `routes/students.py`, find:
```python
from sqlalchemy import func
```
Change to:
```python
from sqlalchemy import func, or_
```

- [ ] **Step 4.2 — Update the `forum_pts_raw` query**

In `routes/students.py`, inside `get_grade_calculation`, find:

```python
    # Forum points (sum of casino-style points earned from posts in this class)
    forum_pts_raw = db.query(func.sum(ForumPoints.points_earned)).filter(
        ForumPoints.user_id == current_student.id,
        ForumPoints.post_id.in_(
            db.query(ForumPost.id).filter(ForumPost.class_id == class_id)
        ),
    ).scalar() or 0.0
```

Replace with:

```python
    # Forum points: sum of casino points for this class's posts, PLUS any direct
    # penalty records (bonus_type='penalty') linked to this class via class_id.
    forum_pts_raw = db.query(func.sum(ForumPoints.points_earned)).filter(
        ForumPoints.user_id == current_student.id,
        or_(
            ForumPoints.post_id.in_(
                db.query(ForumPost.id).filter(ForumPost.class_id == class_id)
            ),
            ForumPoints.class_id == class_id,
        ),
    ).scalar() or 0.0
```

- [ ] **Step 4.3 — Verify grade calculation reflects penalty**

```bash
curl -s "http://localhost:8000/api/students/me/grade-calculation/1" \
  -H "Authorization: Bearer <STUDENT_TOKEN>" | python -m json.tool
```

Check that `forum_points` in the response is reduced by the penalty amount applied in Task 2 (0.5 pts in the example).

- [ ] **Step 4.4 — Commit**

```bash
git add routes/students.py
git commit -m "fix: include penalty records in forum_pts grade calculation"
```

---

## Task 5 — Frontend HTML: Add delete modal to `forum.html` and `index.html`

**Files:**
- Modify: `static/forum.html`
- Modify: `static/index.html`

- [ ] **Step 5.1 — Add modal HTML to `forum.html`**

Find `</body>` at the end of `static/forum.html`. Insert this block immediately before it:

```html
    <!-- ======= Delete Post Modal (teacher moderation) ======= -->
    <div id="delete-post-modal" class="hidden fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
         onclick="if(event.target===this)closeDpm()">
        <div class="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
            <div class="flex items-center gap-2 mb-1">
                <svg class="w-4 h-4 text-red-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
                <h3 class="font-semibold text-gray-800 text-sm">Eliminar publicación de <span id="dpm-author" class="text-secondary"></span></h3>
            </div>
            <p id="dpm-snippet" class="text-gray-500 text-xs italic line-clamp-2 mb-3 ml-6"></p>

            <div id="dpm-pts-row" class="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-4 text-xs text-amber-800">
                <svg class="w-3.5 h-3.5 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <span>Se revocarán los <strong><span id="dpm-pts"></span> pts</strong> de foro que ganó este post.</span>
            </div>

            <label class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer mb-2">
                <input type="checkbox" id="dpm-penalty-check" onchange="toggleDpmPenalty()"
                       class="rounded border-gray-300 text-primary focus:ring-primary">
                Penalizar adicionalmente
            </label>

            <div id="dpm-penalty-fields" class="hidden ml-5 space-y-2 mb-4">
                <div class="flex items-center gap-2">
                    <label class="text-xs text-gray-500 shrink-0">Puntos:</label>
                    <input type="number" id="dpm-penalty-pts" min="0" max="10" step="0.5" value="1"
                           class="w-24 px-2 py-1 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary outline-none">
                </div>
                <input type="text" id="dpm-penalty-msg" maxlength="300"
                       placeholder="Motivo (opcional)"
                       class="w-full px-2 py-1 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary outline-none">
            </div>

            <div class="flex justify-end gap-2 mt-2">
                <button onclick="closeDpm()"
                        class="px-4 py-1.5 text-sm text-gray-600 hover:text-gray-800 rounded-lg transition">
                    Cancelar
                </button>
                <button onclick="confirmDeletePost()"
                        class="px-5 py-1.5 text-sm bg-red-500 hover:bg-red-600 text-white font-medium rounded-lg transition">
                    Eliminar
                </button>
            </div>
        </div>
    </div>
```

Note: `dpm-author` and `dpm-snippet` are populated via `.textContent` in JS (not innerHTML) — user data never touches innerHTML.

- [ ] **Step 5.2 — Add the same modal HTML to `index.html`**

Find `</body>` at the end of `static/index.html`. Insert the exact same HTML block from Step 5.1 immediately before `</body>`.

- [ ] **Step 5.3 — Commit**

```bash
git add static/forum.html static/index.html
git commit -m "feat: add delete-post modal HTML for teacher moderation"
```

---

## Task 6 — Frontend JS: Update `forum.js` (modal + banner)

**Files:**
- Modify: `static/js/forum.js`

- [ ] **Step 6.1 — Add delete modal state and functions**

Find `// ==================== Notifications ====================` in `forum.js`. Insert the following block **before** it:

```javascript
// ==================== Delete Post Modal ====================

let _dpmPostId = null;
let _dpmCallback = null;

function openDeletePostModal(post, onConfirm) {
    _dpmPostId = post.id;
    _dpmCallback = onConfirm;
    // Use textContent for user-supplied strings to prevent XSS
    document.getElementById('dpm-author').textContent = post.author_name || '';
    document.getElementById('dpm-snippet').textContent = (post.title || post.content || '').slice(0, 80);
    const pts = (post.points_earned || 0).toFixed(2);
    document.getElementById('dpm-pts').textContent = pts;
    document.getElementById('dpm-pts-row').classList.toggle('hidden', parseFloat(pts) <= 0);
    document.getElementById('dpm-penalty-check').checked = false;
    document.getElementById('dpm-penalty-fields').classList.add('hidden');
    document.getElementById('dpm-penalty-pts').value = '1';
    document.getElementById('dpm-penalty-msg').value = '';
    document.getElementById('delete-post-modal').classList.remove('hidden');
}

function closeDpm() {
    document.getElementById('delete-post-modal').classList.add('hidden');
    _dpmPostId = null;
    _dpmCallback = null;
}

function toggleDpmPenalty() {
    const checked = document.getElementById('dpm-penalty-check').checked;
    document.getElementById('dpm-penalty-fields').classList.toggle('hidden', !checked);
}

async function confirmDeletePost() {
    const postId = _dpmPostId;
    const callback = _dpmCallback;
    const penaltyChecked = document.getElementById('dpm-penalty-check').checked;
    const penalty = penaltyChecked ? (parseFloat(document.getElementById('dpm-penalty-pts').value) || 0) : 0;
    const message = document.getElementById('dpm-penalty-msg').value.trim() || null;
    const body = {};
    if (penalty > 0) { body.penalty = penalty; body.message = message; }
    try {
        await apiCall(`/forum/posts/${postId}`, { method: 'DELETE', body: JSON.stringify(body) });
        closeDpm();
        if (callback) callback(postId);
    } catch (e) {
        alert('Error al eliminar: ' + e.message);
    }
}
```

- [ ] **Step 6.2 — Replace `deletePost` function**

Find `async function deletePost(event, postId)` in `forum.js` and replace it entirely with:

```javascript
async function deletePost(event, postId) {
    event.stopPropagation();
    const post = posts.find(p => p.id === postId);
    const isTeacherModerating = currentUser.role === 'teacher' && post && post.author_id !== currentUser.id;

    if (isTeacherModerating) {
        openDeletePostModal(post, (deletedId) => {
            posts = posts.filter(p => p.id !== deletedId);
            const card = document.querySelector(`article[onclick="openPost(${deletedId})"]`);
            if (card) card.remove();
            if (!posts.length) document.getElementById('empty-state').classList.remove('hidden');
        });
        return;
    }

    if (!confirm('¿Estás seguro de eliminar esta publicación?')) return;
    try {
        await apiCall(`/forum/posts/${postId}`, { method: 'DELETE' });
        posts = posts.filter(p => p.id !== postId);
        const card = document.querySelector(`article[onclick="openPost(${postId})"]`);
        if (card) card.remove();
        if (!posts.length) document.getElementById('empty-state').classList.remove('hidden');
    } catch (e) {
        alert('Error al eliminar: ' + e.message);
    }
}
```

- [ ] **Step 6.3 — Replace `deleteModalPost` function**

Find `async function deleteModalPost()` in `forum.js` and replace it entirely with:

```javascript
async function deleteModalPost() {
    if (!currentModalPost) return;
    const isTeacherModerating = currentUser.role === 'teacher' && currentModalPost.author_id !== currentUser.id;

    if (isTeacherModerating) {
        openDeletePostModal(currentModalPost, (deletedId) => {
            closePostModal();
            posts = posts.filter(p => p.id !== deletedId);
            const card = document.querySelector(`article[onclick="openPost(${deletedId})"]`);
            if (card) card.remove();
            if (!posts.length) document.getElementById('empty-state').classList.remove('hidden');
        });
        return;
    }

    if (!confirm('¿Estás seguro de eliminar esta publicación?')) return;
    const postId = currentModalPost.id;
    try {
        await apiCall(`/forum/posts/${postId}`, { method: 'DELETE' });
        closePostModal();
        posts = posts.filter(p => p.id !== postId);
        const card = document.querySelector(`article[onclick="openPost(${postId})"]`);
        if (card) card.remove();
        if (!posts.length) document.getElementById('empty-state').classList.remove('hidden');
    } catch (e) {
        alert('Error al eliminar: ' + e.message);
    }
}
```

- [ ] **Step 6.4 — Add `loadPenaltyBanner` function using safe DOM methods**

In the Notifications section of `forum.js`, add after `_showLikeToast`:

```javascript
async function loadPenaltyBanner() {
    if (!selectedClassId || currentUser.role === 'teacher') return;
    try {
        const penalties = await apiCall(`/forum/penalties/recent?class_id=${selectedClassId}`);
        const existing = document.getElementById('penalty-banner');
        if (existing) existing.remove();
        if (!penalties.length) return;

        const wrapper = document.createElement('div');
        wrapper.id = 'penalty-banner';
        wrapper.className = 'space-y-2 mb-2';

        penalties.forEach(p => {
            const pts = Math.abs(p.points_earned).toFixed(2);
            const when = timeAgo(p.created_at);

            const row = document.createElement('div');
            row.className = 'flex items-start gap-2 bg-amber-50 border border-amber-300 rounded-xl px-4 py-3 text-sm text-amber-800';

            const textDiv = document.createElement('div');

            const mainSpan = document.createElement('span');
            mainSpan.className = 'font-medium';
            mainSpan.textContent = 'Se eliminó una publicación tuya';

            const detailSpan = document.createElement('span');
            detailSpan.className = 'text-amber-700';
            detailSpan.textContent = ' −' + pts + ' pts de foro · ' + when;

            textDiv.appendChild(mainSpan);
            textDiv.appendChild(detailSpan);

            if (p.message) {
                const msgP = document.createElement('p');
                msgP.className = 'text-xs text-amber-600 mt-0.5';
                // textContent prevents XSS — message is user-supplied
                msgP.textContent = '“' + p.message + '”';
                textDiv.appendChild(msgP);
            }

            row.appendChild(textDiv);
            wrapper.appendChild(row);
        });

        document.getElementById('posts-container').before(wrapper);
    } catch (_) { /* banner is non-critical */ }
}
```

- [ ] **Step 6.5 — Call `loadPenaltyBanner` from `onClassChange` and initial class load**

In `forum.js`, find `async function onClassChange()`. Add the banner call after `loadPosts`:

```javascript
async function onClassChange() {
    selectedClassId = parseInt(document.getElementById('class-selector').value);
    await loadPosts(true);
    await loadPenaltyBanner();   // NEW
}
```

Then find the initial block where `selectedClassId` is first assigned and `loadPosts(true)` is first called (around line 96). Add `await loadPenaltyBanner()` on the line immediately after `await loadPosts(true)`:

```javascript
        selectedClassId = parseInt(selector.value);
        // ... (existing code) ...
        await loadPosts(true);
        await loadPenaltyBanner();   // NEW
```

- [ ] **Step 6.6 — Commit**

```bash
git add static/js/forum.js
git commit -m "feat: add moderation delete modal and penalty banner to forum.js"
```

---

## Task 7 — Frontend JS: Update `home.js` (modal + banner)

**Files:**
- Modify: `static/js/home.js`

- [ ] **Step 7.1 — Add delete modal state and functions**

Find `// ==================== Forum: load classes + posts ====================` in `home.js`. Insert the following block **before** it:

```javascript
// ==================== Delete Post Modal ====================

let _dpmPostId = null;
let _dpmCallback = null;

function openDeletePostModal(post, onConfirm) {
    _dpmPostId = post.id;
    _dpmCallback = onConfirm;
    // Use textContent for user-supplied strings to prevent XSS
    document.getElementById('dpm-author').textContent = post.author_name || '';
    document.getElementById('dpm-snippet').textContent = (post.title || post.content || '').slice(0, 80);
    const pts = (post.points_earned || 0).toFixed(2);
    document.getElementById('dpm-pts').textContent = pts;
    document.getElementById('dpm-pts-row').classList.toggle('hidden', parseFloat(pts) <= 0);
    document.getElementById('dpm-penalty-check').checked = false;
    document.getElementById('dpm-penalty-fields').classList.add('hidden');
    document.getElementById('dpm-penalty-pts').value = '1';
    document.getElementById('dpm-penalty-msg').value = '';
    document.getElementById('delete-post-modal').classList.remove('hidden');
}

function closeDpm() {
    document.getElementById('delete-post-modal').classList.add('hidden');
    _dpmPostId = null;
    _dpmCallback = null;
}

function toggleDpmPenalty() {
    const checked = document.getElementById('dpm-penalty-check').checked;
    document.getElementById('dpm-penalty-fields').classList.toggle('hidden', !checked);
}

async function confirmDeletePost() {
    const postId = _dpmPostId;
    const callback = _dpmCallback;
    const penaltyChecked = document.getElementById('dpm-penalty-check').checked;
    const penalty = penaltyChecked ? (parseFloat(document.getElementById('dpm-penalty-pts').value) || 0) : 0;
    const message = document.getElementById('dpm-penalty-msg').value.trim() || null;
    const body = {};
    if (penalty > 0) { body.penalty = penalty; body.message = message; }
    try {
        await apiCall(`/forum/posts/${postId}`, { method: 'DELETE', body: JSON.stringify(body) });
        closeDpm();
        if (callback) callback(postId);
    } catch (e) {
        alert('Error al eliminar: ' + e.message);
    }
}
```

- [ ] **Step 7.2 — Replace `deletePost` function in `home.js`**

Find `async function deletePost(event, postId)` in `home.js` and replace it entirely with:

```javascript
async function deletePost(event, postId) {
    event.stopPropagation();
    const post = posts.find(p => p.id === postId);
    const isTeacherModerating = currentUser.role === 'teacher' && post && post.author_id !== currentUser.id;

    if (isTeacherModerating) {
        openDeletePostModal(post, (deletedId) => {
            posts = posts.filter(p => p.id !== deletedId);
            document.querySelector(`article[onclick="openPost(${deletedId})"]`)?.remove();
            if (!posts.length) document.getElementById('forum-empty').classList.remove('hidden');
        });
        return;
    }

    if (!confirm('¿Estás seguro de eliminar esta publicación?')) return;
    try {
        await apiCall(`/forum/posts/${postId}`, { method: 'DELETE' });
        posts = posts.filter(p => p.id !== postId);
        document.querySelector(`article[onclick="openPost(${postId})"]`)?.remove();
        if (!posts.length) document.getElementById('forum-empty').classList.remove('hidden');
    } catch (e) { alert('Error al eliminar: ' + e.message); }
}
```

- [ ] **Step 7.3 — Replace `deleteModalPost` function in `home.js`**

Find `async function deleteModalPost()` in `home.js` and replace it entirely with:

```javascript
async function deleteModalPost() {
    if (!currentModalPost) return;
    const isTeacherModerating = currentUser.role === 'teacher' && currentModalPost.author_id !== currentUser.id;

    if (isTeacherModerating) {
        openDeletePostModal(currentModalPost, (deletedId) => {
            closePostModal();
            posts = posts.filter(p => p.id !== deletedId);
            document.querySelector(`article[onclick="openPost(${deletedId})"]`)?.remove();
            if (!posts.length) document.getElementById('forum-empty').classList.remove('hidden');
        });
        return;
    }

    if (!confirm('¿Estás seguro de eliminar esta publicación?')) return;
    const postId = currentModalPost.id;
    try {
        await apiCall(`/forum/posts/${postId}`, { method: 'DELETE' });
        closePostModal();
        posts = posts.filter(p => p.id !== postId);
        document.querySelector(`article[onclick="openPost(${postId})"]`)?.remove();
        if (!posts.length) document.getElementById('forum-empty').classList.remove('hidden');
    } catch (e) { alert('Error al eliminar: ' + e.message); }
}
```

- [ ] **Step 7.4 — Add `loadPenaltyBanner` to `home.js`**

In `home.js`, add this function immediately after the closing brace of `loadForumSection`:

```javascript
async function loadPenaltyBanner() {
    if (currentUser.role === 'teacher') return;
    try {
        // No class_id — fetch penalties across all classes (home forum is class-agnostic)
        const penalties = await apiCall('/forum/penalties/recent');
        const existing = document.getElementById('penalty-banner');
        if (existing) existing.remove();
        if (!penalties.length) return;

        const wrapper = document.createElement('div');
        wrapper.id = 'penalty-banner';
        wrapper.className = 'space-y-2 mb-2';

        penalties.forEach(p => {
            const pts = Math.abs(p.points_earned).toFixed(2);
            const when = timeAgo(p.created_at);

            const row = document.createElement('div');
            row.className = 'flex items-start gap-2 bg-amber-50 border border-amber-300 rounded-xl px-4 py-3 text-sm text-amber-800';

            const textDiv = document.createElement('div');

            const mainSpan = document.createElement('span');
            mainSpan.className = 'font-medium';
            mainSpan.textContent = 'Se eliminó una publicación tuya';

            const detailSpan = document.createElement('span');
            detailSpan.className = 'text-amber-700';
            detailSpan.textContent = ' −' + pts + ' pts de foro · ' + when;

            textDiv.appendChild(mainSpan);
            textDiv.appendChild(detailSpan);

            if (p.message) {
                const msgP = document.createElement('p');
                msgP.className = 'text-xs text-amber-600 mt-0.5';
                // textContent prevents XSS — message is user-supplied
                msgP.textContent = '“' + p.message + '”';
                textDiv.appendChild(msgP);
            }

            row.appendChild(textDiv);
            wrapper.appendChild(row);
        });

        document.getElementById('posts-container').before(wrapper);
    } catch (_) { /* banner is non-critical */ }
}
```

- [ ] **Step 7.5 — Call `loadPenaltyBanner` from `loadForumSection`**

In `home.js`, `loadForumSection` ends with `await loadPosts(true)`. Add the banner call after:

```javascript
    await loadPosts(true);
    await loadPenaltyBanner();   // NEW
```

The full updated `loadForumSection` looks like:

```javascript
async function loadForumSection() {
    try {
        forumClasses = await apiCall('/forum/classes');
    } catch (e) { forumClasses = []; }

    if (!forumClasses.length) {
        document.getElementById('posts-container').innerHTML = '';
        document.getElementById('forum-no-class').classList.remove('hidden');
        document.getElementById('composer-wrapper').classList.add('hidden');
        return;
    }

    const composerSel = document.getElementById('composer-class-selector');
    if (composerSel) {
        composerSel.innerHTML = forumClasses.map(c => `<option value="${c.id}">${escHtml(c.name)}</option>`).join('');
    }

    await loadPosts(true);
    await loadPenaltyBanner();   // NEW
}
```

- [ ] **Step 7.6 — Commit**

```bash
git add static/js/home.js
git commit -m "feat: add moderation delete modal and penalty banner to home.js"
```

---

## Task 8 — Manual end-to-end verification

- [ ] **Step 8.1 — Start the server**

```bash
uvicorn app.main:app --reload
```

- [ ] **Step 8.2 — Test teacher moderation modal (forum.html)**

1. Open `http://localhost:8000/static/forum.html`, log in as **teacher**
2. Find a post created by a student
3. Click the trash icon on the post card
4. **Verify:** Custom modal appears (not a browser `confirm()`). Shows student name, post snippet, points warning
5. Check "Penalizar adicionalmente" — penalty fields appear
6. Enter 1.0 pt and "Post de prueba sin valor" as motivo → click "Eliminar"
7. **Verify:** Post disappears from the feed; no console errors

Check DB:
```bash
python -c "
import sqlite3; conn = sqlite3.connect('school.db')
print('Penalty record:', conn.execute('SELECT user_id, class_id, points_earned, message, bonus_type FROM forum_points WHERE bonus_type=\"penalty\"').fetchall())
"
```

Expected: one row with `bonus_type='penalty'`, `points_earned=-1.0`.

- [ ] **Step 8.3 — Test student penalty banner (index.html)**

1. Open `http://localhost:8000`, log in as the **student** whose post was deleted
2. Scroll to the forum section
3. **Verify:** Amber banner appears above the posts: "Se eliminó una publicación tuya −1.00 pts de foro · hace Xm" with the reason in quotes

- [ ] **Step 8.4 — Test teacher deleting own post (no modal)**

1. Log in as teacher, create a test post, then click trash on it
2. **Verify:** Browser native `confirm()` dialog appears (not the custom modal)

- [ ] **Step 8.5 — Test grade impact**

```bash
# Replace CLASS_ID with the class where the penalty was applied
curl -s "http://localhost:8000/api/students/me/grade-calculation/CLASS_ID" \
  -H "Authorization: Bearer <STUDENT_TOKEN>" | python -c "import sys,json; d=json.load(sys.stdin); print('forum_points:', d['forum_points'])"
```

Verify `forum_points` is reduced by the penalty amount (1.0 in this example).

- [ ] **Step 8.6 — Final commit if any cleanup needed**

```bash
git add -A
git commit -m "feat: forum moderation — points revocation and penalty banner complete"
```
