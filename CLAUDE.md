# CLAUDE.md

This file provides context for Claude Code when working on this project.

## Project Overview

A FastAPI teaching application for managing student attendance, participation, and grades. Built as an educational tool for classroom management with multi-class support.

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy ORM, Pydantic
- **Database:** SQLite (dev) / PostgreSQL (production)
- **Storage:** Cloudflare R2 (S3-compatible, optional — enables file uploads)
- **Frontend:** Vanilla JS with Tailwind CSS (CDN), Spanish UI, custom warm palette (#F2F0E4 cream, #1F2020 dark, #EA8251 orange, #9C4927 rust)
- **Auth:** Google OAuth (Google Identity Services)
- **Deployment:** Railway

## Key Commands

```bash
# Run the server
uvicorn app.main:app --reload

# Seed test data (creates sample class and enrolls students)
python seed_data.py
```

## Project Structure

- `app/main.py` - FastAPI app entry point, routes registration, serves static pages
- `app/auth.py` - Google OAuth token verification and session management
- `app/storage.py` - Cloudflare R2 (S3-compatible) storage helpers (upload, presign, validate, delete)
- `routes/auth.py` - Authentication endpoints (`/api/auth/google`, `/api/auth/logout`)
- `routes/admin.py` - Teacher admin endpoints (dashboard, roster, attendance, grades, participation, categories)
- `routes/classes.py` - Class management endpoints (create, join, leave, list)
- `routes/students.py` - Student endpoints (grades, attendance, grade-calculation, assignments/submissions, file upload/download)
- `routes/participation.py` - Participation submission (requires class_id)
- `models/models.py` - SQLAlchemy ORM models (Student, Class, StudentClass, Attendance, Participation, Grade, GradeCategory, SpecialPoints, Assignment, Submission, ForumPost, ForumReply, ForumLike, ForumPoints)
- `models/schemas.py` - Pydantic request/response schemas
- `models/database.py` - Database connection and session management
- `routes/forum.py` - Forum endpoints (posts, replies, likes, pin/lock, points summary)
- `static/index.html` - Student landing page (Spanish: "Portal del Estudiante"): progress cards → participation form → justification link → assignments → forum
- `static/js/home.js` - Landing page JS: class cards with grade breakdown modal, participation form, justification modal (openJustificationModal/submitJustification), assignments, unified forum feed, casino toast notifications
- `static/js/app.js` - Legacy student dashboard JS (kept for reference; landing page now uses home.js)
- `static/admin.html` - Teacher admin panel - class overview (Spanish: "Panel del Profesor")
- `static/js/admin.js` - Admin panel JavaScript (class list, quick stats)
- `static/class-dashboard.html` - Per-class dashboard with tabs (Spanish)
- `static/js/class-dashboard.js` - Class dashboard JavaScript (attendance, grades, participation, roster, assignment grading modal, file viewer, justification review)
- `static/exam-shell.html` - Online exam shell page (authenticates, fetches exam HTML from R2, renders in iframe, handles postMessage for draft save and submit)
- `static/forum.html` - Standalone forum page (accessible from admin nav; same content as landing page forum section)
- `static/js/forum.js` - Standalone forum JavaScript (teacher moderation, likes, post modal, casino toasts)

## Multi-Class System

### How It Works
- Teachers create classes with auto-generated codes (e.g., "MICRO2026AB3X")
- Students join classes by entering the code
- All data (attendance, participation, grades) is scoped to specific classes
- Students can be enrolled in multiple classes and switch between them

### Teacher UI Flow
```
/admin (Main Panel)
  - Quick stats: total classes, students, pending participation
  - List of class cards (click to open dashboard)
  - Create class button
  - "Vista de Estudiante" button (preview student dashboard)
      ↓ Click a class
/admin/class/{id} (Class Dashboard)
  ├── Overview tab: quick actions, at-risk students, recent activity, category overview
  ├── Roster tab: student list with search/filter/sort
  ├── Attendance tab: take attendance by date
  ├── Exámenes tab: exam list + "Nuevo Examen Presencial" form + fast grading modal; manage grade categories; secondary individual grade form
  ├── Participation tab: approve/reject submissions, bulk approve
  ├── Retos tab: create assignments (with category selector), click to open submissions modal, grade/auto-grade
  └── Justificaciones tab: review/approve/reject student absence justifications
```

### Database Models
- `Class` - id, name, code (unique), teacher_id, created_at, grading_mode ('points'|'percentage', default 'points')
- `StudentClass` - Junction table (student_id, class_id, joined_at)
- `Attendance` - Daily attendance with justification support (justification_file_key, justification_status: null/pending/approved/rejected, justification_reviewed_by). Has nullable `class_id` for backward compatibility
- `Participation` - Has nullable `class_id` for backward compatibility
- `Grade` - Has `category_id` FK to `grade_categories`, `name` field, and legacy `category` string
- `GradeCategory` - Weighted categories per class (name, weight as decimal e.g. 0.4)
- `SpecialPoints` - Optional bonus points per student (english, notebook)
- `Assignment` - Homework/retos and exams per class (title, description, due_date, max_points, allow_late, published, exam_type: 'homework'|'exam'|'online', available_from, available_until, time_limit_min, allow_save, exam_html_key)
- `OnlineExamDraft` - Draft state for online exams (assignment_id, student_id, draft_json, started_at, saved_at)
- `Submission` - Student submissions (drive_url, file_key, file_name, file_size, penalty_pct, is_late, grade, feedback, receipt_json)
- `ForumPost` - Forum posts (class_id, author_id, title, content, pinned, locked, like_count, comment_count, points_earned)
- `ForumReply` - Threaded replies (post_id, author_id, parent_reply_id, content)
- `ForumLike` - Likes on posts (user_id, post_id; unique constraint)
- `ForumPoints` - Casino point ledger (user_id, post_id, like_id, points_earned, bonus_type: 'normal'|'mini'|'double'|'jackpot')

### Code Generation
Class codes are auto-generated: `{PREFIX}{YEAR}{4-RANDOM}` (e.g., "MICRO2026AB3X")

## API Endpoints

### Public
- `GET /api/health` - Health check
- `GET /api/config` - Frontend configuration (Google Client ID, file_uploads_enabled)
- `POST /api/auth/google` - Authenticate with Google ID token
- `POST /api/auth/logout` - Invalidate session

### Class Management
- `POST /api/classes/` - Create class (teacher only)
- `GET /api/classes/teaching` - List teacher's classes with student counts
- `GET /api/classes/teaching/{id}` - Get class details with enrolled students
- `DELETE /api/classes/teaching/{id}` - Delete class (teacher only)
- `GET /api/classes/enrolled` - List student's enrolled classes
- `POST /api/classes/join` - Join class by code (student only)
- `DELETE /api/classes/leave/{id}` - Leave class (student only)

### Student Endpoints (requires auth, supports impersonation via X-Impersonate header)
- `GET /api/students/me` - Current student info
- `GET /api/students/me/grades?class_id=X` - Student's grades (optional class filter)
- `GET /api/students/me/attendance?class_id=X` - Student's attendance (optional class filter)
- `GET /api/students/me/participation/points?class_id=X` - Total approved participation points
- `GET /api/students/me/grade-calculation/{class_id}` - Full grade breakdown with categories, participation, special points, absence penalty
- `GET /api/students/me/assignments?class_id=X` - List assignments with submission status
- `POST /api/students/me/assignments/{id}/submit` - Submit assignment (Google Drive link, auto penalty)
- `POST /api/students/me/assignments/{id}/upload` - Upload file for assignment (multipart/form-data, R2 storage, allows re-upload)
- `GET /api/students/submissions/{id}/file` - Get presigned download URL for submission file (owner or class teacher)
- `DELETE /api/students/submissions/{id}` - Delete ungraded submission (soft-reset, allows re-submit)
- `POST /api/students/me/attendance/{id}/justify` - Submit justification for absence/late (multipart: `file` optional + `justification_text` Form optional; at least one required; file upload requires R2)
- `GET /api/students/attendance/{id}/justification-file` - Get presigned URL for justification file (owner or class teacher)
- `POST /api/participation` - Submit participation entry (requires class_id)

### Forum Endpoints (requires auth)
- `GET /api/forum/classes` - List classes the current user can access (enrolled or teaching)
- `GET /api/forum/posts?class_id=X&page=N&limit=N` - Paginated post list with liked_by_me, author_role
- `POST /api/forum/posts` - Create post (student: max 5/day, earns +0.1 pts; teacher: no limit, no points)
- `GET /api/forum/posts/{id}` - Get single post with replies tree
- `DELETE /api/forum/posts/{id}` - Delete post (own post or teacher)
- `POST /api/forum/posts/{id}/like` - Toggle like; awards casino points to post author (students only); returns points_awarded, bonus_type, post_points_earned
- `POST /api/forum/posts/{id}/replies` - Create reply (supports parent_reply_id for threading)
- `DELETE /api/forum/replies/{id}` - Delete reply (own or teacher)
- `PATCH /api/forum/posts/{id}/pin` - Toggle pin (teacher only)
- `PATCH /api/forum/posts/{id}/lock` - Toggle lock (teacher only); locked posts hide reply form
- `GET /api/forum/points/summary?class_id=X` - Total forum points earned by current user in a class
- `GET /api/forum/points/recent` - Last 20 point award events for current user

### Admin Endpoints (Teacher only)
- `GET /api/admin/classes/{id}/dashboard` - Full class dashboard with stats, students, categories, recent activity
- `GET /api/admin/roster/{id}` - Student roster with category-based grade breakdowns
- `GET /api/admin/students?class_id=X` - List students (optional: filter by class enrollment)
- `POST /api/admin/attendance` - Record attendance (requires class_id)
- `GET /api/admin/attendance?class_id=X&date=Y` - View attendance for class and date
- `POST /api/admin/grades` - Add grade (requires class_id, category_id)
- `GET /api/admin/participation?class_id=X` - View participation for class
- `PATCH /api/admin/participation/:id` - Approve/reject participation
- `PATCH /api/admin/participation/bulk-approve` - Bulk approve participation
- `GET /api/admin/categories/{class_id}` - List grade categories for class
- `POST /api/admin/categories/{class_id}` - Create grade category
- `PUT /api/admin/categories/{class_id}/{cat_id}` - Update category
- `DELETE /api/admin/categories/{class_id}/{cat_id}` - Delete category
- `GET /api/admin/special-points?class_id=X` - Get special points for class
- `POST /api/admin/special-points` - Create special points entry
- `PATCH /api/admin/special-points/{id}` - Update special points (opt-in, awarded)
- `POST /api/admin/assignments` - Create assignment (reto) for a class (accepts optional `category_id`; auto-picks first category if omitted)
- `GET /api/admin/assignments?class_id=X` - List assignments with submission/graded counts
- `DELETE /api/admin/assignments/{id}` - Delete assignment
- `GET /api/admin/assignments/{id}/submissions?filter=` - View submissions with student info, auto-grade, not-submitted list (filter: graded/ungraded/late)
- `PATCH /api/admin/submissions/{id}/grade` - Grade submission (score, feedback), upserts Grade record
- `POST /api/admin/assignments/{id}/auto-grade` - Auto-grade all ungraded submissions (penalty_pct/100 * max_points)
- `GET /api/admin/assignments/{id}/exam-grading` - All enrolled students with their current grade for an exam (sorted ungraded-first)
- `POST /api/admin/assignments/{id}/exam-grade` - Upsert grade for one student in an exam (no submission needed); body: `{student_id, score}`
- `GET /api/admin/justifications?class_id=X&status_filter=` - List justifications (default: pending)
- `PATCH /api/admin/justifications/{id}` - Approve/reject justification (approved → status becomes "excused")
- `PATCH /api/admin/classes/{id}/settings` - Update class settings (grading_mode: 'points'|'percentage')
- `POST /api/admin/assignments/{id}/upload-exam-html` - Upload HTML file for online exam (multipart, R2)
- `PATCH /api/admin/assignments/{id}/settings` - Update online exam settings (available_from, available_until, time_limit_min, allow_save)
- `GET /api/admin/assignments/{id}/online-submissions` - List students with online exam submission status

### Online Exam Endpoints (Student)
- `GET /exam/{assignment_id}` - Serves exam shell page (auth checked via JS)
- `GET /api/students/me/assignments/{id}/exam-status` - Active window, time remaining, draft/submit state
- `GET /api/students/me/assignments/{id}/exam-file` - Presigned R2 URL for exam HTML
- `POST /api/students/me/assignments/{id}/exam-draft` - Save draft state (upsert, preserves started_at)
- `POST /api/students/me/assignments/{id}/submit-online-exam` - Submit receipt JSON, auto-create grade

## Authentication

Uses Google OAuth with Google Identity Services (client-side Sign-In button).

**Setup:**
1. Create a project in Google Cloud Console
2. Enable Google+ API and configure OAuth consent screen
3. Create OAuth 2.0 Client ID (Web application type)
4. Add `http://localhost:8000` to authorized JavaScript origins
5. Copy the Client ID to `.env` as `GOOGLE_CLIENT_ID`

**Flow:**
1. User clicks "Sign in with Google" button
2. Google popup authenticates user
3. Frontend receives ID token, POSTs to `/api/auth/google`
4. Backend verifies token with Google, finds/creates student
5. Backend returns session token
6. Frontend stores token in localStorage for API calls

**Roles:**
- `student` - Default role, can view own data, submit participation, join classes
- `teacher` - Admin access, can create/manage classes, attendance, grades, and approve participation

**Teacher Account:** Set `TEACHER_EMAIL` in `.env` - this email gets teacher role on first login.

## Database

- **Development:** SQLite (auto-creates `school.db`)
- **Production:** PostgreSQL (Railway provides this)

### Current Tables
- `students` - Student records (includes `role`: student/teacher)
- `classes` - Class records (name, code, teacher_id, grading_mode)
- `student_classes` - Student-class enrollments (many-to-many)
- `attendances` - Daily attendance (status: present/absent/late/excused, class_id, justification_file_key, justification_status, justification_reviewed_by)
- `participations` - Class participation entries with points and approval status (class_id)
- `grades` - Scored assignments (category_id, name, score, max_score, class_id)
- `grade_categories` - Weighted grade categories per class (name, weight)
- `special_points` - Optional bonus points per student (english, notebook)
- `assignments` - Homework/retos and exams (class_id, category_id, title, description, due_date, max_points, allow_late, published, exam_type, available_from, available_until, time_limit_min, allow_save, exam_html_key)
- `online_exam_drafts` - Draft state for online exams (assignment_id, student_id, draft_json, started_at, saved_at)
- `submissions` - Student submissions (assignment_id, student_id, drive_url, file_key, file_name, file_size, penalty_pct, is_late, grade, feedback)
- `forum_posts` - Forum posts (class_id, author_id, title, content, pinned, locked, like_count, comment_count, points_earned)
- `forum_replies` - Threaded replies (post_id, author_id, parent_reply_id, content)
- `forum_likes` - Post likes (user_id, post_id; unique per user+post)
- `forum_points` - Casino points ledger (user_id, post_id, like_id, points_earned, bonus_type)

### Grading System

#### ⚠️ Core Philosophy — Grades Are Intentionally Incomplete

**The category weights do NOT need to sum to 100%. This is by design.**

The default setup is 40% + 40% = 80%. A student who only does required work (retos + exams) reaches ~80. The remaining ~20 points come from participation, which is **unlimited and uncapped**. This is intentional: the incentive structure is designed so that showing up and engaging in class is always worth it, and the grade ceiling never kills motivation. A student can exceed 100 (the DB stores the raw value; Railway/frontend cap display at 100 if needed, but the raw grade can go beyond). **Never "fix" the weights to sum to 100. Never add a warning that they don't. Do not suggest the teacher fill the remaining 20% with a category.** The gap is the participation incentive.

**Grade Calculation Formula:**
```
Final Grade = Σ(Category Weight × Category Average)
            + participation_points   (1 pt per approved tap, no cap)
            + forum_points           (casino system, no cap)
            + special_points         (up to 1.0 pt)
            - unjustified_absences   (1 pt each)
```

**Grading Mode** (`classes.grading_mode`):
- `'points'` (default) — Final grade is **uncapped**. This is the intended mode. No weight-sum warning.
- `'percentage'` — Final grade is **capped at 100**. UI warns if category weights don't sum to 100%. Available for teachers who prefer it, but not the default philosophy.
- Grade-calculation responses include `grading_mode` and `max_base_grade` (= sum of category weights × 100).
- The Grades tab → Categories section shows a radio toggle to switch modes per class.

**Default Categories** (auto-created with new classes):
- "Retos de la Semana" — 40%
- "Exámenes y Proyectos" — 40%
- The remaining ~20 points come from participation + forum + special points — **this gap is intentional** (see philosophy above)

**Grade Categories** (`grade_categories`):
- Teacher defines categories per class, can add/edit/delete
- Each category has a weight (decimal, e.g. 0.4 = 40%)
- Grades are assigned to categories via `category_id`
- Grade model also has optional `name` field (e.g., "Reto Semana 1")
- Category average = mean of graded assignments only (variable count — doesn't matter if 4 or 15 assignments exist)
- Grade-calculation response includes per-category: `graded_count`, `pending_count`, `total_assignments`
- Grade-calculation response top-level: `participation_points` (class-only, for compat), `participation_points_class`, `participation_points_forum` (raw forum pts), `forum_points` (uncapped), `final_grade`, `grading_mode`, `max_base_grade`
- Student dashboard grade modal shows breakdown: categories, class participation (1 pt per tap), forum pts, special pts, absence penalty, final grade
- **Uncategorized grades fallback**: Grades with `category_id = NULL` (legacy/manual entries) are grouped into a "Sin categoría" bucket in grade-calculation. They get the remaining weight after defined categories (e.g., if categories sum to 0.8, uncategorized gets 0.2). This ensures legacy grades are never silently dropped.

**Participation Points:**
- Each approved participation tap = **1 full grade point** directly. No multiplier.
- Teacher assigns weight live in class: 1 tap (normal), 2 taps ("¡doble!"), 3 taps ("¡triple!").
- No cap. Natural ceiling ~100 pts for a consistently active student over the semester.
- ~42 students, ~60 class hours — reaching 100 is earned, not gamed.
- Formula: `participation_contribution = float(class_part_pts)` in `routes/students.py → get_grade_calculation()`

**Special Points** (`special_points`):
- Two categories: "english" and "notebook" (0.5 pts each)
- Students opt-in, teacher awards at end of semester
- `awarded_at` (DATETIME nullable) and `awarded_by` (INTEGER FK → students, nullable) record when and by whom points were awarded. Set when `awarded` transitions to `true`; cleared if award is revoked.

**Forum Points** (`forum_points`):
- Students earn points for forum engagement; included in final grade (hard cap: 3.0 pts per class)
- `+0.1 pts` for creating a post (max 3 posts/day globally, not per-class)
- Per-like points: +0.1 (≤10 likes), +0.2 (≤25), +0.3 (≤50), +0.5 (50+ likes)
- Anti-exploit: post must have ≥2 total likes before any points are awarded; user can only award points to the same author once per day
- Casino bonus rolls: 0.2% jackpot (+5.0 pts), 2% double (×2 base), 5% mini (+0.2 flat)
- Teachers excluded from earning or granting points
- Points are permanent — unliking does not remove awarded points
- No grade cap — forum points add 1:1 to final grade, same as participation (see Participation Points)
- `forum_posts.points_earned` is a denormalized cumulative for display on post cards
- Grade-calc endpoint includes `forum_points` (uncapped), `participation_points_forum` (raw) in the returned dict

**Absence Penalty:**
- Each unjustified absence (status = "absent") subtracts 1 point from final grade
- Students can upload justification documents (PDF, images) via R2
- Justification workflow: student submits → status = "pending" → teacher approves/rejects
- Approved justification changes attendance status to "excused" (no longer penalized)
- Rejected justifications can be re-submitted
- Grade-calculation response includes `absence_count`, `absence_penalty`, and `pending_justification_count` (absences currently under review)
- R2 key format: `justifications/{student_id}_{attendance_id}_{timestamp}.{ext}`

### Assignment Submissions (Retos)

**Submission methods:** Students can either submit a Google Drive link (shared from their @alumnos.ujed.mx account) or upload a file directly via Cloudflare R2 (PDF, DOCX, ZIP, images, max 10MB). Both methods coexist — a submission can have a Drive link, an uploaded file, or both.

**Lateness Penalty (`penalty_pct`):**
| Timing | penalty_pct |
|---|---|
| On time | 100 |
| 0-24h late | 90 |
| 24h-1 week late | 50 |
| >1 week late | 10 |

- All submissions are always accepted (no hard rejection for lateness)
- `is_late` is set to `true` when `penalty_pct < 100`
- `penalty_pct` stored on the `Submission` row for grading reference
- Student UI shows color-coded penalty badge and clickable "Ver entrega" Drive link or "Ver archivo" file link

**Assignment Creation:**
- Teacher clicks "Nuevo Reto" in the Retos tab → form with title, description, category dropdown, due date, max points
- Category dropdown is populated from `grade_categories` for this class (e.g., "Retos de la Semana (40%)")
- Frontend sends `category_id` in the payload; backend validates it belongs to the class
- If `category_id` is omitted, backend auto-picks the first category for the class
- Assignment is saved with the correct `category_id` FK, ensuring grades inherit it

**Teacher Grading Flow:**
1. Teacher clicks an assignment card in the Retos tab → submissions modal opens
2. Modal shows all submissions with student name, late badge, auto-grade (`penalty_pct/100 * max_points`), Drive link, file link
3. Teacher enters score → `PATCH /admin/submissions/{id}/grade` updates `submissions.grade` and upserts `grades` row
4. "Aceptar auto-calificaciones" button → `POST /admin/assignments/{id}/auto-grade` bulk-grades all ungraded submissions
5. Grading a submission creates/updates a `grades` row (student_id, class_id, category_id from assignment, name=assignment.title)
6. Grade appears in student's weighted grade calculation under the assignment's category

**Submissions Modal Features:**
- Filter dropdown: Todos / Sin calificar / Calificados / Entrega tardia
- Each row: student name, penalty badge, graded status, submitted date, Drive link, file link (presigned URL), score input, Calificar button
- Collapsible "Sin entregar" section showing students who haven't submitted
- Re-grading updates existing Grade record (no duplicates)

**File Upload (R2):**
- Requires `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET_NAME` env vars
- If R2 not configured, `/api/config` returns `file_uploads_enabled: false` and upload UI is hidden
- `app/storage.py` provides: `is_r2_configured()`, `get_s3_client()`, `validate_file()`, `upload_file()`, `generate_presigned_url()`, `delete_file()`
- Allowed file types: PDF, DOC/DOCX, XLS/XLSX, PPT/PPTX, TXT, CSV, ZIP, RAR, 7Z, PNG, JPG, JPEG, GIF, WEBP, SVG
- Max file size: 10 MB
- R2 object key format: `submissions/{student_id}_{assignment_id}_{timestamp}.{ext}`
- File upload allows re-submission (old R2 file is deleted), unlike Drive URL which rejects duplicates
- `file_key` is never exposed in API responses — only `has_file` boolean; download goes through presigned URL endpoint
- Frontend uses XHR (not fetch) for upload progress events via `apiUpload()` helper

### Exam Grading (Exámenes Tab)

The "Calificaciones" tab was renamed "Exámenes" and redesigned for fast in-person exam grading.

**Assignment types (`exam_type` field on `Assignment`):**
- `'homework'` (default) — online retos, students submit via Drive link or file upload
- `'exam'` — in-person exams, teacher grades all students directly; no submissions required
- `'online'` — Pyodide HTML exam; teacher uploads .html file to R2; student takes exam in-app via `/exam/{id}` shell page; auto-graded; receipt JSON stored in `submission.receipt_json`; supports draft saving (server-side) and time limits

**Exam creation flow:**
1. Teacher enters exam name, optionally selects category and max points
2. Clicks "Crear y Calificar" → creates `Assignment` with `exam_type='exam'`, auto-picks "Exámenes y Proyectos" category
3. Grading modal opens immediately

**Exam grading modal (keyboard-first UX):**
- Search bar autofocused on open
- Two sections: "Por Calificar" (expanded, ungraded students first) / "Calificados" (collapsed, already graded)
- Keyboard flow: type name to filter → **Tab** or **↓** to focus score input → type score → **Enter** to save grade, clear search, refocus search
- Esc from score input → returns focus to search; Esc from search → closes modal
- Saving immediately moves student from "Por Calificar" to "Calificados" section (local state update)

**Grade storage:** Exam grades go directly into the `grades` table (same as assignment grades) — `POST /api/admin/assignments/{id}/exam-grade` upserts by `(student_id, class_id, name=assignment.title)`. No `Submission` record is created.

**Existing exam list:** Tab shows all `exam_type='exam'` assignments for the class, with graded count and a Calificar button to re-open the grading modal.

**Secondary:** A collapsible `<details>` element contains the old individual grade form for manual one-off grades.

### Student Preview Mode (Impersonation)

Teachers can preview the student dashboard for any of their classes:

**How it works:**
1. Teacher clicks "Vista de Estudiante" → selects a class
2. Frontend fetches first enrolled student, stores `previewStudentId` in sessionStorage
3. Navigates to student dashboard (`/?preview=true`)
4. `apiCall()` adds `X-Impersonate: {studentId}` header to all requests
5. Backend `get_student_or_impersonated()` verifies teacher owns a class where target is enrolled
6. Student endpoints return impersonated student's data
7. Preview banner shown, participation form hidden

**Auth dependency:** `get_student_or_impersonated()` in `app/auth.py`
- Used by: all `/api/students/me/*` endpoints and `GET /api/classes/enrolled`
- Falls through to normal student if no `X-Impersonate` header
- `get_current_student` is unchanged (used by participation submission, class join/leave)

## Planned Features (Schema Design)

### 1. Lessons/Classroom
```
lessons
├── id, class_id, title, content_html, video_url
├── order_index, published, created_at, updated_at

lesson_attachments
├── id, lesson_id, file_name, file_url, file_type, file_size

lesson_progress
├── id, lesson_id, student_id
├── started_at, completed, completed_at, time_spent_sec
└── UNIQUE(lesson_id, student_id)
```

### Pending Schema Updates
- `special_points`: Add `awarded_at` (DATETIME) and `awarded_by` (FK to students)

## Implemented Features

### Forum System
- **Routes:** `routes/forum.py`
- **Frontend:** `static/forum.html` + `static/js/forum.js` (standalone); forum also embedded in combined landing page via `home.js`
- Threaded replies (one level of nesting via `parent_reply_id`)
- Like system with per-post toggle (one like per user per post)
- Teacher moderation: pin posts (📌), lock posts (🔒 hides reply form), delete any post/reply
- Teacher posts show 👨‍🏫 badge; teacher author label is rust-colored
- Casino points system: students earn fractional grade points for posting and receiving likes (see Forum Points section above)
- Daily post limit: 3 posts/day per student globally (anti-spam)
- Casino toast notifications on like: normal (dark), mini ✨, double 🎰, jackpot 💰
- Context-aware delete confirmation: "¿Eliminar publicación de [name]?" when teacher deletes another user's post

### Combined Landing Page (`/`)
- `static/index.html` + `static/js/home.js` replace the old student-only dashboard
- Section order: progress cards → participation form → justification link (if absences) → assignments → forum
- Student class cards show: final grade (color-coded), participation pts (pending in violet), forum pts, special pts, absence count with "Justificar →" button (or "⏳ X en revisión" if pending)
- Grade breakdown modal (`openGradeModal(classId)`) with full category/participation/extras breakdown
- **Justification modal** (`openJustificationModal(classId)`): class selector, absence dropdown (absent/late dates), status hints (pending/rejected/approved), text area, optional file upload; calls `POST /api/students/me/attendance/{id}/justify`
- Teacher class cards link to `/admin/class/{id}`
- Upcoming assignments section with Drive link + file upload support
- Join class modal accessible from nav, no-class state, and dashboard CTA

## Development Notes

- Frontend uses Tailwind CSS via CDN (no build step) with custom color palette defined in each HTML file's `<script>` (Tailwind config) and `<style>` blocks (opacity variants like `.bg-primary-5`, `.bg-primary-10`, `.hover\:bg-primary-5:hover` etc.)
- **Theme colors**: `primary: #EA8251` (orange), `secondary: #9C4927` (rust), `cream: #F2F0E4` (background), `dark: #1F2020` (near-black). Body uses `bg-cream`. Buttons use `bg-primary hover:bg-secondary`. Opacity variants defined as plain CSS classes (Tailwind CDN doesn't support `/opacity` syntax with custom colors).
- Frontend is fully translated to Spanish (UI labels, messages, date formatting uses es-MX locale)
- Database file (`school.db`) is gitignored
- Run `seed_data.py` to populate test data (creates teacher, 3 students, sample class, enrollments, and sample records)
- `class_id` is nullable in attendance/participation/grades for backward compatibility
- **Auto-migration on startup**: `Base.metadata.create_all()` always runs (creates missing tables), plus `_ensure_columns()` adds missing columns (`category_id`, `name` to `grades` table; `drive_url`, `penalty_pct`, `file_key`, `file_name`, `file_size`, `resubmit_count`, `receipt_json` to `submissions` table; `justification_file_key`, `justification_file_name`, `justification_text`, `justification_status`, `justification_submitted_at`, `justification_reviewed_at`, `justification_reviewed_by` to `attendances` table; `grading_mode` to `classes` table; `exam_type`, `available_from`, `available_until`, `time_limit_min`, `allow_save`, `exam_html_key` to `assignments` table; `points_earned` to `forum_posts` table). **Always use `TIMESTAMP` (not `DATETIME`) and `DEFAULT TRUE` (not `DEFAULT 1`) for PostgreSQL compatibility.**

## Railway Deployment

1. Push code to GitHub
2. Create new project in Railway, connect to GitHub repo
3. Add PostgreSQL database service
4. Set environment variables in Railway:
   - `GOOGLE_CLIENT_ID` - From Google Cloud Console
   - `GOOGLE_CLIENT_SECRET` - From Google Cloud Console
   - `TEACHER_EMAIL` - Your teacher email
   - `ALLOWED_ORIGINS` - Your Railway domain (e.g., `https://your-app.up.railway.app`)
   - `SECRET_KEY` - Random secret string
   - `R2_ACCESS_KEY_ID` - (Optional) Cloudflare R2 access key for file uploads
   - `R2_SECRET_ACCESS_KEY` - (Optional) Cloudflare R2 secret key
   - `R2_ENDPOINT` - (Optional) R2 endpoint URL
   - `R2_BUCKET_NAME` - (Optional) R2 bucket name
5. Add your Railway domain to Google OAuth authorized origins
6. Deploy!
