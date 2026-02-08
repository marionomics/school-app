# CLAUDE.md

This file provides context for Claude Code when working on this project.

## Project Overview

A FastAPI teaching application for managing student attendance, participation, and grades. Built as an educational tool for classroom management with multi-class support.

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy ORM, Pydantic
- **Database:** SQLite (dev) / PostgreSQL (production)
- **Frontend:** Vanilla JS with Tailwind CSS (CDN), Spanish UI
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
- `routes/auth.py` - Authentication endpoints (`/api/auth/google`, `/api/auth/logout`)
- `routes/admin.py` - Teacher admin endpoints (dashboard, roster, attendance, grades, participation, categories)
- `routes/classes.py` - Class management endpoints (create, join, leave, list)
- `routes/students.py` - Student endpoints (grades, attendance, grade-calculation with category breakdown)
- `routes/participation.py` - Participation submission (requires class_id)
- `models/models.py` - SQLAlchemy ORM models (Student, Class, StudentClass, Attendance, Participation, Grade, GradeCategory, SpecialPoints)
- `models/schemas.py` - Pydantic request/response schemas
- `models/database.py` - Database connection and session management
- `static/index.html` - Student dashboard frontend (Spanish: "Portal del Estudiante")
- `static/js/app.js` - Student dashboard JavaScript (class enrollment, switching)
- `static/admin.html` - Teacher admin panel - class overview (Spanish: "Panel del Profesor")
- `static/js/admin.js` - Admin panel JavaScript (class list, quick stats)
- `static/class-dashboard.html` - Per-class dashboard with tabs (Spanish)
- `static/js/class-dashboard.js` - Class dashboard JavaScript (attendance, grades, participation, roster)

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
  ├── Grades tab: add grades (with category_id), manage categories
  └── Participation tab: approve/reject submissions, bulk approve
```

### Database Models
- `Class` - id, name, code (unique), teacher_id, created_at
- `StudentClass` - Junction table (student_id, class_id, joined_at)
- `Attendance`, `Participation` - Have nullable `class_id` for backward compatibility
- `Grade` - Has `category_id` FK to `grade_categories`, `name` field, and legacy `category` string
- `GradeCategory` - Weighted categories per class (name, weight as decimal e.g. 0.4)
- `SpecialPoints` - Optional bonus points per student (english, notebook)

### Code Generation
Class codes are auto-generated: `{PREFIX}{YEAR}{4-RANDOM}` (e.g., "MICRO2026AB3X")

## API Endpoints

### Public
- `GET /api/health` - Health check
- `GET /api/config` - Frontend configuration (Google Client ID)
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
- `GET /api/students/me/grade-calculation/{class_id}` - Full grade breakdown with categories, participation, special points
- `POST /api/participation` - Submit participation entry (requires class_id)

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
- `classes` - Class records (name, code, teacher_id)
- `student_classes` - Student-class enrollments (many-to-many)
- `attendances` - Daily attendance (status: present/absent/late/excused, class_id)
- `participations` - Class participation entries with points and approval status (class_id)
- `grades` - Scored assignments (category_id, name, score, max_score, class_id)
- `grade_categories` - Weighted grade categories per class (name, weight)
- `special_points` - Optional bonus points per student (english, notebook)

### Grading System

**Grade Calculation Formula:**
```
Final Grade = Σ(Category Weight × Category Average) + (Participation Points × 0.1) + Special Points
```

**Default Categories** (auto-created with new classes):
- "Retos de la Semana" — 40%
- "Exámenes y Proyectos" — 40%
- Remaining 20% comes from participation + special points (no category needed)

**Grade Categories** (`grade_categories`):
- Teacher defines categories per class, can add/edit/delete
- Each category has a weight (decimal, e.g. 0.4 = 40%)
- Grades are assigned to categories via `category_id`
- Grade model also has optional `name` field (e.g., "Reto Semana 1")

**Participation Points:**
- No cap on participation points contribution
- Each approved point adds 0.1 to final grade

**Special Points** (`special_points`):
- Two categories: "english" and "notebook" (0.5 pts each)
- Students opt-in, teacher awards at end of semester
- TODO: Add `awarded_at` and `awarded_by` columns for audit trail

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

### 1. Homework System
```
assignments
├── id, class_id, category_id, title, description
├── due_date, max_points, file_required, allow_late, published
└── created_at, updated_at

submissions
├── id, assignment_id, student_id
├── file_url, text_content, submitted_at, is_late
├── grade, feedback, graded_at, graded_by
└── UNIQUE(assignment_id, student_id)
```

### 2. Lessons/Classroom
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

### 3. Forum
```
forum_posts
├── id, class_id, author_id, title, content
├── pinned, locked, reply_count, like_count
└── created_at, updated_at

forum_replies
├── id, post_id, author_id, parent_id (for threading)
├── content, like_count, created_at, updated_at

forum_likes
├── id, user_id, post_id (nullable), reply_id (nullable)
└── CHECK: exactly one of post_id/reply_id is set
```

### Pending Schema Updates
- `special_points`: Add `awarded_at` (DATETIME) and `awarded_by` (FK to students)

## Development Notes

- Frontend uses Tailwind CSS via CDN (no build step)
- Frontend is fully translated to Spanish (UI labels, messages, date formatting uses es-MX locale)
- Database file (`school.db`) is gitignored
- Run `seed_data.py` to populate test data (creates teacher, 3 students, sample class, enrollments, and sample records)
- `class_id` is nullable in attendance/participation/grades for backward compatibility
- **Auto-migration on startup**: `Base.metadata.create_all()` always runs (creates missing tables), plus `_ensure_columns()` adds missing columns (`category_id`, `name`) to existing `grades` table

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
5. Add your Railway domain to Google OAuth authorized origins
6. Deploy!
