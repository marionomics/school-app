# Forum Points Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global teacher toggle that freezes forum point awards at end of semester without affecting likes, posts, or existing points.

**Architecture:** A new single-row `AppConfig` table holds `forum_points_enabled`. The forum routes check this flag before awarding points. The main admin panel exposes an Activar/Congelar button visible only to the teacher.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vanilla JS + Tailwind CSS

---

## File Map

| File | Action | What changes |
|---|---|---|
| `models/models.py` | Modify | Add `AppConfig` model |
| `models/schemas.py` | Modify | Add `AppConfigUpdate` Pydantic schema |
| `app/main.py` | Modify | Import `AppConfig`; add `_ensure_app_config()`; update `GET /api/config` to include `forum_points_enabled` |
| `routes/admin.py` | Modify | Add `PATCH /api/admin/config` endpoint |
| `routes/forum.py` | Modify | Check `AppConfig.forum_points_enabled` in `create_post` and `toggle_like` before awarding points |
| `static/admin.html` | Modify | Add `<div id="forum-points-settings">` placeholder between stats grid and classes section |
| `static/js/admin.js` | Modify | Add `forumPointsEnabled` state, read from `/api/config`, render control card, toggle function |

---

## Task 1: Add `AppConfig` model and startup initialization

**Files:**
- Modify: `models/models.py`
- Modify: `app/main.py`

- [ ] **Step 1: Add `AppConfig` to `models/models.py`**

Open `models/models.py`. After the last model class (find the end of the file), add:

```python
class AppConfig(Base):
    __tablename__ = "app_config"
    id = Column(Integer, primary_key=True, default=1)
    forum_points_enabled = Column(Boolean, default=True)
```

- [ ] **Step 2: Import `AppConfig` in `app/main.py`**

In `app/main.py`, find line 14:
```python
from models.models import Student, Attendance, Participation, Grade, Class, StudentClass, GradeCategory, SpecialPoints, Assignment, Submission, ForumPost, ForumReply, ForumLike, ForumPoints, OnlineExamDraft
```

Replace with (add `AppConfig` at the end):
```python
from models.models import Student, Attendance, Participation, Grade, Class, StudentClass, GradeCategory, SpecialPoints, Assignment, Submission, ForumPost, ForumReply, ForumLike, ForumPoints, OnlineExamDraft, AppConfig
```

- [ ] **Step 3: Add `_ensure_app_config()` in `app/main.py`**

In `app/main.py`, immediately after `_ensure_columns()` (around line 215, before the `@asynccontextmanager` line), add:

```python
def _ensure_app_config():
    """Create the single AppConfig row if it doesn't exist yet."""
    from models.database import SessionLocal
    db = SessionLocal()
    try:
        if not db.query(AppConfig).filter_by(id=1).first():
            db.add(AppConfig(id=1, forum_points_enabled=True))
            db.commit()
    finally:
        db.close()
```

- [ ] **Step 4: Call `_ensure_app_config()` in the lifespan**

In `app/main.py`, find the lifespan function (around line 217):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    yield
```

Replace with:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    _ensure_app_config()
    yield
```

- [ ] **Step 5: Verify server starts without errors**

Run:
```bash
uvicorn app.main:app --reload
```

Expected: server starts, no errors. In the SQLite file you can verify with:
```bash
sqlite3 school.db "SELECT * FROM app_config;"
```
Expected output: `1|1`

- [ ] **Step 6: Commit**

```bash
git add models/models.py app/main.py
git commit -m "feat: add AppConfig model with forum_points_enabled flag"
```

---

## Task 2: Add schema and `PATCH /api/admin/config` endpoint

**Files:**
- Modify: `models/schemas.py`
- Modify: `routes/admin.py`

- [ ] **Step 1: Add `AppConfigUpdate` schema in `models/schemas.py`**

Open `models/schemas.py`. Find the `ClassSettingsUpdate` class (around line 241):
```python
class ClassSettingsUpdate(BaseModel):
    grading_mode: Optional[str] = None
    salvando_semestre: Optional[bool] = None
```

Add the new schema immediately after it:
```python
class AppConfigUpdate(BaseModel):
    forum_points_enabled: Optional[bool] = None
```

- [ ] **Step 2: Add the endpoint in `routes/admin.py`**

Open `routes/admin.py`. Find the import section at the top and ensure `AppConfig` and `AppConfigUpdate` are imported. The models import line looks like:
```python
from models.models import Student, Class, StudentClass, ...
```
Add `AppConfig` to that import. Then find the schemas import and add `AppConfigUpdate`.

Concretely:
1. In the `from models.models import ...` line, append `, AppConfig`
2. In the `from models.schemas import ...` line, append `, AppConfigUpdate`

- [ ] **Step 3: Add the endpoint body in `routes/admin.py`**

Find the `update_class_settings` endpoint (around line 1228). Add the new endpoint immediately after it (after the closing `return` statement), before the `# ==================== Assignments ====================` comment:

```python
@router.patch("/config")
async def update_app_config(
    data: AppConfigUpdate,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Update global app settings (teacher only)."""
    config = db.query(AppConfig).filter_by(id=1).first()
    if not config:
        config = AppConfig(id=1, forum_points_enabled=True)
        db.add(config)

    if data.forum_points_enabled is not None:
        config.forum_points_enabled = data.forum_points_enabled

    db.commit()
    db.refresh(config)
    return {"forum_points_enabled": config.forum_points_enabled}
```

- [ ] **Step 4: Verify the endpoint exists**

With the server running:
```bash
curl -s http://localhost:8000/openapi.json | python3 -c "import sys,json; routes=[r for r in json.load(sys.stdin)['paths'] if 'config' in r]; print(routes)"
```
Expected output includes `/api/admin/config`.

- [ ] **Step 5: Commit**

```bash
git add models/schemas.py routes/admin.py
git commit -m "feat: add PATCH /api/admin/config endpoint for global settings"
```

---

## Task 3: Expose `forum_points_enabled` in `GET /api/config`

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Update `get_config()` in `app/main.py`**

Find the `get_config` function (around line 288):
```python
@app.get("/api/config")
async def get_config():
    """Return frontend configuration including Google Client ID."""
    from app.storage import is_r2_configured
    ta_emails = [e.strip().lower() for e in os.getenv("TA_EMAILS", "").split(",") if e.strip()]
    return {
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "file_uploads_enabled": is_r2_configured(),
        "teacher_email": os.getenv("TEACHER_EMAIL", ""),
        "ta_emails": ta_emails,
    }
```

Replace with:
```python
@app.get("/api/config")
async def get_config(db: Session = Depends(get_db)):
    """Return frontend configuration including Google Client ID."""
    from app.storage import is_r2_configured
    ta_emails = [e.strip().lower() for e in os.getenv("TA_EMAILS", "").split(",") if e.strip()]
    app_config = db.query(AppConfig).filter_by(id=1).first()
    return {
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "file_uploads_enabled": is_r2_configured(),
        "teacher_email": os.getenv("TEACHER_EMAIL", ""),
        "ta_emails": ta_emails,
        "forum_points_enabled": app_config.forum_points_enabled if app_config else True,
    }
```

You also need to ensure `Session` and `get_db` are imported at the top of `app/main.py`. Check the existing imports — if they're not there, add:
```python
from sqlalchemy.orm import Session
from models.database import get_db
from fastapi import Depends
```
(These likely already exist; just verify.)

- [ ] **Step 2: Verify the response**

With the server running:
```bash
curl -s http://localhost:8000/api/config | python3 -m json.tool
```
Expected: JSON response includes `"forum_points_enabled": true`.

- [ ] **Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: include forum_points_enabled in GET /api/config"
```

---

## Task 4: Guard forum points in `routes/forum.py`

**Files:**
- Modify: `routes/forum.py`

- [ ] **Step 1: Import `AppConfig` in `routes/forum.py`**

Open `routes/forum.py`. Find the models import line:
```python
from models.models import Student, Class, StudentClass, ForumPost, ForumReply, ForumLike, ForumPoints
```
Append `, AppConfig` to it.

- [ ] **Step 2: Guard points in `create_post`**

Find the points block in `create_post` (around line 258):
```python
    # Award +0.1 creation points to students
    if user.role == "student":
        post.points_earned = 0.1
        db.add(ForumPoints(
            user_id=user.id,
            post_id=post.id,
            points_earned=0.1,
            bonus_type='post',
        ))
```

Replace with:
```python
    # Award +0.1 creation points to students (if forum points are enabled globally)
    app_config = db.query(AppConfig).filter_by(id=1).first()
    if user.role == "student" and (not app_config or app_config.forum_points_enabled):
        post.points_earned = 0.1
        db.add(ForumPoints(
            user_id=user.id,
            post_id=post.id,
            points_earned=0.1,
            bonus_type='post',
        ))
```

- [ ] **Step 3: Guard points in `toggle_like`**

Find the like points block in `toggle_like` (around line 387):
```python
        # Award points: only when student likes a student post
        if user.role != "teacher" and post.author.role != "teacher":
```

Add the AppConfig check before it (inside the `else:` block for a new like, after `liked = True`):

Replace the block starting at "Award points" (from line 387 to line 416):
```python
        # Award points: only when student likes a student post
        if user.role != "teacher" and post.author.role != "teacher":
            # Rule 1: post needs at least 2 likes before points kick in (anti-spam)
            qualifies = post.like_count >= 2

            # Rule 2: can't award points to the same author more than once per day
            today_start = datetime.combine(date_type.today(), datetime.min.time())
            already_liked_author_today = qualifies and db.query(ForumPoints).join(
                ForumPost, ForumPoints.post_id == ForumPost.id
            ).filter(
                ForumPoints.user_id == user.id,
                ForumPost.author_id == post.author_id,
                ForumPoints.like_id.isnot(None),
                ForumPoints.created_at >= today_start,
            ).first() is not None

            if qualifies and not already_liked_author_today:
                base_pts = _calculate_like_points(post.like_count)
                bonus_type, points_awarded = _roll_bonus(base_pts)

                db.add(ForumPoints(
                    user_id=post.author_id,
                    post_id=post_id,
                    like_id=like.id,
                    points_earned=points_awarded,
                    bonus_type=bonus_type,
                ))
                post.points_earned = round((post.points_earned or 0.0) + points_awarded, 3)
            else:
                bonus_type = 'normal'
```

With:
```python
        # Award points: only when student likes a student post and forum points are enabled
        app_config = db.query(AppConfig).filter_by(id=1).first()
        points_active = not app_config or app_config.forum_points_enabled
        if points_active and user.role != "teacher" and post.author.role != "teacher":
            # Rule 1: post needs at least 2 likes before points kick in (anti-spam)
            qualifies = post.like_count >= 2

            # Rule 2: can't award points to the same author more than once per day
            today_start = datetime.combine(date_type.today(), datetime.min.time())
            already_liked_author_today = qualifies and db.query(ForumPoints).join(
                ForumPost, ForumPoints.post_id == ForumPost.id
            ).filter(
                ForumPoints.user_id == user.id,
                ForumPost.author_id == post.author_id,
                ForumPoints.like_id.isnot(None),
                ForumPoints.created_at >= today_start,
            ).first() is not None

            if qualifies and not already_liked_author_today:
                base_pts = _calculate_like_points(post.like_count)
                bonus_type, points_awarded = _roll_bonus(base_pts)

                db.add(ForumPoints(
                    user_id=post.author_id,
                    post_id=post_id,
                    like_id=like.id,
                    points_earned=points_awarded,
                    bonus_type=bonus_type,
                ))
                post.points_earned = round((post.points_earned or 0.0) + points_awarded, 3)
            else:
                bonus_type = 'normal'
```

- [ ] **Step 4: Verify manually**

With the server running, use two student accounts in the browser:
1. Toggle forum points OFF via: `curl -X PATCH http://localhost:8000/api/admin/config -H "Authorization: Bearer <teacher_token>" -H "Content-Type: application/json" -d '{"forum_points_enabled": false}'`
2. Like a post as a student — the response should have `"points_awarded": 0.0`.
3. Create a post as a student — no `ForumPoints` row should be inserted.
4. Toggle back ON and verify points resume.

- [ ] **Step 5: Commit**

```bash
git add routes/forum.py
git commit -m "feat: skip forum point awards when forum_points_enabled is false"
```

---

## Task 5: Admin panel UI — forum points control card

**Files:**
- Modify: `static/admin.html`
- Modify: `static/js/admin.js`

- [ ] **Step 1: Add placeholder div in `static/admin.html`**

Open `static/admin.html`. Find the comment `<!-- Classes Section -->` (around line 107). Insert a new div immediately before it:

```html
            <!-- Forum Points Settings (rendered by JS, teacher-only) -->
            <div id="forum-points-settings" class="mb-6"></div>

            <!-- Classes Section -->
```

- [ ] **Step 2: Add `forumPointsEnabled` state variable in `static/js/admin.js`**

Open `static/js/admin.js`. Find the top-level variable declarations (near the top of the file, where `let classes = []` or similar globals are declared). Add:

```javascript
let forumPointsEnabled = true;
```

- [ ] **Step 3: Read `forum_points_enabled` from config in `init()`**

In `admin.js`, find the `init()` function's config fetch block:
```javascript
    try {
        const config = await fetch('/api/config').then(r => r.json());
        googleClientId = config.google_client_id;
    } catch (error) {
        console.error('Error al obtener configuracion:', error);
    }
```

Replace with:
```javascript
    try {
        const config = await fetch('/api/config').then(r => r.json());
        googleClientId = config.google_client_id;
        forumPointsEnabled = config.forum_points_enabled ?? true;
    } catch (error) {
        console.error('Error al obtener configuracion:', error);
    }
```

- [ ] **Step 4: Call `renderForumPointsCard()` after login in `showAdmin()`**

In `admin.js`, find the `showAdmin()` function:
```javascript
function showAdmin() {
    document.getElementById('login-section').classList.add('hidden');
    document.getElementById('admin-section').classList.remove('hidden');
    if (currentTeacher) {
        document.getElementById('teacher-name').textContent = currentTeacher.name;
        if (currentTeacher.role === 'ta') {
            document.getElementById('create-class-btn')?.classList.add('hidden');
            document.getElementById('student-view-btn')?.classList.add('hidden');
        }
    }
}
```

Replace with:
```javascript
function showAdmin() {
    document.getElementById('login-section').classList.add('hidden');
    document.getElementById('admin-section').classList.remove('hidden');
    if (currentTeacher) {
        document.getElementById('teacher-name').textContent = currentTeacher.name;
        if (currentTeacher.role === 'ta') {
            document.getElementById('create-class-btn')?.classList.add('hidden');
            document.getElementById('student-view-btn')?.classList.add('hidden');
        }
    }
    renderForumPointsCard();
}
```

- [ ] **Step 5: Add `renderForumPointsCard()` and `toggleForumPoints()` functions**

In `admin.js`, add these two functions before the `init()` function at the bottom of the file:

```javascript
function renderForumPointsCard() {
    const container = document.getElementById('forum-points-settings');
    if (!container || !currentTeacher || currentTeacher.role !== 'teacher') {
        if (container) container.innerHTML = '';
        return;
    }

    if (forumPointsEnabled) {
        container.innerHTML = `
            <div class="flex items-center justify-between gap-3 rounded-xl border border-gray-200 bg-white px-5 py-4 shadow-sm">
                <div class="flex items-center gap-3">
                    <span class="inline-block w-2.5 h-2.5 rounded-full bg-green-400 shrink-0"></span>
                    <div>
                        <p class="font-semibold text-gray-800 text-sm">Puntos del foro activos</p>
                        <p class="text-gray-500 text-xs">Los estudiantes ganan puntos por publicar y recibir likes.</p>
                    </div>
                </div>
                <button onclick="toggleForumPoints(false)"
                        class="shrink-0 px-4 py-1.5 text-xs font-medium bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition">
                    Congelar puntos
                </button>
            </div>`;
    } else {
        container.innerHTML = `
            <div class="flex items-center justify-between gap-3 rounded-xl border-2 border-gray-300 bg-gray-50 px-5 py-4">
                <div class="flex items-center gap-3">
                    <span class="inline-block w-2.5 h-2.5 rounded-full bg-gray-400 shrink-0"></span>
                    <div>
                        <p class="font-semibold text-gray-600 text-sm">Puntos del foro congelados</p>
                        <p class="text-gray-500 text-xs">No se otorgan nuevos puntos. Los puntos existentes se conservan.</p>
                    </div>
                </div>
                <button onclick="toggleForumPoints(true)"
                        class="shrink-0 px-4 py-1.5 text-xs font-medium bg-primary text-white rounded-lg hover:bg-secondary transition">
                    Reactivar puntos
                </button>
            </div>`;
    }
}

async function toggleForumPoints(enable) {
    try {
        const result = await apiCall('/admin/config', {
            method: 'PATCH',
            body: JSON.stringify({ forum_points_enabled: enable }),
        });
        forumPointsEnabled = result.forum_points_enabled;
        renderForumPointsCard();
    } catch (error) {
        alert('Error al cambiar configuración: ' + error.message);
    }
}
```

- [ ] **Step 6: Verify UI in browser**

Start the server and open `http://localhost:8000/admin` in a browser logged in as teacher.

Check:
- The control card renders between the stats grid and "Mis Clases".
- The card shows "Puntos del foro activos" with a green dot and "Congelar puntos" button.
- Clicking "Congelar puntos" changes the card to the frozen state (gray dot, "Reactivar puntos" in orange).
- Clicking "Reactivar puntos" restores the active state.
- Logging in as a TA — the card does not appear.

- [ ] **Step 7: Commit**

```bash
git add static/admin.html static/js/admin.js
git commit -m "feat: add forum points freeze toggle to admin panel"
```
