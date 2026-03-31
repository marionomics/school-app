# School Teaching App

A FastAPI application for managing student attendance, participation, and grades. Built for UJED classroom management.

## Features

- **Multi-Class Support**: Teachers create classes with unique codes, students join via codes
- **Class Dashboard**: Comprehensive per-class view with stats, roster, attendance, grades, and participation tabs
- **Flexible Grading System**: Configurable grade categories with weights; per-class grading mode — "Puntos" (uncapped, extras stack freely) or "Porcentajes" (capped at 100)
- **Assignment System (Retos)**: Create assignments with category selection, students submit Google Drive links or upload files (via Cloudflare R2), teacher grading modal with auto-grade support
- **Online Exams**: Teacher uploads a single-file Pyodide HTML exam to R2; sets an activation window and optional time limit; students take the exam in a sandboxed full-screen shell page; auto-graded on submit; receipt JSON stored; draft state saved server-side so students can resume on any device. Teacher can also "Calificar" manually if auto-submit fails.
- **Exam Grading (Exámenes)**: Create in-person exams and grade all students in a fast keyboard-driven modal — search by name, Tab to score, Enter to save and move to next student
- **File Uploads**: Optional Cloudflare R2 integration for direct file submissions (PDF, DOCX, ZIP, images, max 10MB) with upload progress and presigned download URLs
- **Attendance Justifications**: Students submit justifications (text explanation and/or uploaded document) for absences/lates directly from their dashboard; teachers approve/reject; approved justifications change status to "excused" and remove the -1 point grade penalty. Student dashboard shows "Justificar →" button on absence cards, a persistent link when unjustified absences exist, and "⏳ en revisión" badge for pending submissions.
- **Student Preview Mode**: Teachers can preview the student dashboard as any enrolled student via impersonation
- **Combined Landing Page**: Unified page for students — class progress cards (with full grade breakdown modal) → participation form → assignments → forum feed. No separate navigation needed.
- **Forum**: Unified class discussion board showing posts from all enrolled classes, with threaded replies, likes, teacher moderation (pin/lock/delete), and a casino-style engagement points system
- **Forum Points (Casino System)**: Students earn fractional grade points for posting (+0.1/post, max 3/day) and receiving likes (+0.1–0.5/like based on post popularity, with jackpot/double/mini bonus rolls). Anti-exploit: post needs ≥2 likes before awarding; user can only award points to same author once per day. Points add 1:1 to final grade (uncapped, same as participation).
- **Teacher Admin Panel**: Simple class overview with quick stats, click any class to open detailed dashboard
- **Google OAuth**: Secure authentication via Google accounts
- **Spanish UI**: Full Spanish language interface
- **Auto-Migration**: Missing tables and columns are created automatically on startup
- **Railway Ready**: Configured for easy cloud deployment

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, Pydantic
- **Database**: SQLite (dev) / PostgreSQL (production)
- **Storage**: Cloudflare R2 (S3-compatible, optional for file uploads)
- **Frontend**: Vanilla JS, Tailwind CSS (CDN), Inter font (Google Fonts), warm cream/orange palette
- **Auth**: Google OAuth 2.0
- **Deployment**: Railway

## Quick Start

1. **Clone and setup**:
   ```bash
   git clone https://github.com/marionomics/school-app.git
   cd school-app
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your Google OAuth credentials and teacher email
   ```

3. **Setup Google OAuth**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
   - Create OAuth 2.0 Client ID (Web application)
   - Add `http://localhost:8000` to authorized JavaScript origins
   - Copy Client ID to `.env`

4. **Run**:
   ```bash
   python seed_data.py  # Optional: populate test data
   uvicorn app.main:app --reload
   ```

5. **Open**:
   - Student Dashboard: http://localhost:8000
   - Admin Panel: http://localhost:8000/admin
   - Class Dashboard: http://localhost:8000/admin/class/{id}
   - API Docs: http://localhost:8000/docs

## How Classes Work

1. **Teacher creates a class** in the Admin Panel (Clases tab)
   - Enters class name and optional code prefix (e.g., "MICRO")
   - System generates unique code (e.g., "MICRO2026AB3X")

2. **Teacher shares the code** with students

3. **Students join the class** using the code
   - After login, students see "Join Class" screen if not enrolled
   - Enter the class code to enroll

4. **All data is class-scoped**
   - Attendance, grades, and participation are tied to specific classes
   - Students can join multiple classes and switch between them

## Grading System

The app uses a weighted grading formula:

```
Final Grade = Σ(Category Weight × Category Average) + Participation Points + Forum Points + Special Points - Unjustified Absences
```

Each unjustified absence (status = "absent") subtracts 1 point from the final grade. Students can upload justification documents; if the teacher approves, the absence becomes "excused" and the penalty is removed.

### Grading Modes

Each class has a `grading_mode` setting (configurable in the Grades tab under Categories):

| Mode | Behavior |
|------|----------|
| **Puntos** (default) | Final grade is uncapped — participation and special points stack above the category base. Category weights don't need to sum to 100%. |
| **Porcentajes** | Final grade is capped at 100. Category weights should sum to 100% (a warning is shown otherwise). |

The default mode is `points`, which matches UJED's system where categories total 80 pts and extras (participation, special points) can push the grade above 80.

### Grade Categories
- New classes auto-create default categories: "Retos de la Semana" (40%) and "Exámenes y Proyectos" (40%)
- The remaining 20% comes from participation + special points (no category needed)
- Teachers can customize categories per class (add, edit, delete, change weights)
- Each grade is assigned to a category via `category_id`
- Assignments created from the Retos tab include a category selector; grades inherit the assignment's category automatically
- Grades without a `category_id` (legacy data) are grouped into a "Sin categoría" bucket using remaining weight
- Category averages are calculated over graded assignments only (variable count is fine)
- Student dashboard shows "Tu calificacion se calcula sobre X tareas completadas" with pending/unsubmitted counts

### Participation Points
- Students submit participation entries describing their contributions
- Teachers approve/reject and assign 1–3 taps per entry live in class (normal / "¡doble!" / "¡triple!")
- Each approved tap = **1 grade point** directly added to final grade (no cap, no multiplier)
- Natural ceiling ~100 pts for a consistently active student over a semester

### Forum Points
- Students earn fractional points through forum engagement, added directly to final grade (uncapped — same 1:1 ratio as participation points)
- **+0.1 pts** per post created (max 3 posts/day, global across classes)
- **Per-like earnings** (post needs ≥2 likes to qualify, once per author per day): +0.1 (≤10 likes), +0.2 (≤25), +0.3 (≤50), +0.5 (50+ likes)
- **Casino bonus rolls** on each qualifying like: 0.2% jackpot (+5.0 pts), 2% double (×2 base), 5% mini (+0.2 flat)
- Points are permanent — unliking does not remove earned points
- Teacher activity (posting, liking) does not generate or award points

### Special Points
- Two optional categories: English (0.5 pts) and Notebook (0.5 pts)
- Students opt-in at start of semester
- Teacher awards at end of semester if criteria met

## Student Preview Mode

Teachers can preview the student dashboard to see exactly what a student sees:

1. Click "Vista de Estudiante" in the admin panel
2. Select a class (must have at least one enrolled student)
3. View the student dashboard with real data from the first enrolled student
4. Banner shows "Modo de Vista Previa" with the class name
5. Participation form is hidden (teachers can't submit as students)
6. Click "Volver al Panel de Profesor" to return

**Technical**: Uses `X-Impersonate` header — the teacher's auth token is preserved, and student endpoints return the impersonated student's data. Only teachers who own a class where the target student is enrolled can impersonate.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Database connection string |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret |
| `TEACHER_EMAIL` | Email that gets admin access |
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) |
| `SECRET_KEY` | Application secret key |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 access key (optional, enables file uploads) |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 secret key |
| `R2_ENDPOINT` | R2 endpoint URL (e.g., `https://<account_id>.r2.cloudflarestorage.com`) |
| `R2_BUCKET_NAME` | R2 bucket name |

## API Endpoints

### Public
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/config` | Frontend config |
| POST | `/api/auth/google` | Google OAuth login |
| POST | `/api/auth/logout` | Logout |

### Classes
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/classes/` | Create class (teacher) |
| GET | `/api/classes/teaching` | List teacher's classes |
| GET | `/api/classes/teaching/:id` | Get class with students |
| DELETE | `/api/classes/teaching/:id` | Delete class |
| GET | `/api/classes/enrolled` | List student's classes |
| POST | `/api/classes/join` | Join class by code |
| DELETE | `/api/classes/leave/:id` | Leave class |

### Student (requires auth)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/students/me` | Current student info |
| GET | `/api/students/me/grades?class_id=X` | Student's grades |
| GET | `/api/students/me/attendance?class_id=X` | Student's attendance |
| GET | `/api/students/me/participation/points?class_id=X` | Participation point total |
| GET | `/api/students/me/grade-calculation/:class_id` | Full grade breakdown: categories, participation (class + forum split), special pts, absences, pending justification count, final grade |
| GET | `/api/students/me/assignments?class_id=X` | List assignments with submission status |
| POST | `/api/students/me/assignments/:id/submit` | Submit assignment (Google Drive link, auto penalty) |
| POST | `/api/students/me/assignments/:id/upload` | Upload file for assignment (multipart, R2 storage) |
| GET | `/api/students/submissions/:id/file` | Get presigned download URL for submission file |
| DELETE | `/api/students/submissions/:id` | Delete ungraded submission (allows re-submit) |
| POST | `/api/students/me/attendance/:id/justify` | Submit justification for absence (multipart: optional file + optional text; at least one required) |
| GET | `/api/students/attendance/:id/justification-file` | Get presigned URL for justification file |
| POST | `/api/participation` | Submit participation (requires class_id) |
| GET | `/api/students/me/assignments/:id/exam-status` | Active window, time remaining, draft/submit state |
| GET | `/api/students/me/assignments/:id/exam-file` | Presigned R2 URL for exam HTML |
| POST | `/api/students/me/assignments/:id/exam-draft` | Save draft state (upsert) |
| POST | `/api/students/me/assignments/:id/submit-online-exam` | Submit receipt JSON, auto-create grade |

> Student endpoints support teacher impersonation via `X-Impersonate: {student_id}` header.

### Admin (teacher only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/classes/:id/dashboard` | Full class dashboard with stats |
| GET | `/api/admin/roster/:id` | Student roster with grades |
| GET | `/api/admin/students?class_id=X` | List students in class |
| POST | `/api/admin/attendance` | Record bulk attendance (requires class_id) |
| GET | `/api/admin/attendance?class_id=X&date=Y` | Get attendance |
| POST | `/api/admin/grades` | Add grade (requires class_id) |
| GET | `/api/admin/participation?class_id=X` | View participation |
| PATCH | `/api/admin/participation/:id` | Approve/reject |
| GET | `/api/admin/categories/:id` | List grade categories |
| POST | `/api/admin/categories/:id` | Create grade category |
| PUT | `/api/admin/categories/:id/:cat_id` | Update category |
| DELETE | `/api/admin/categories/:id/:cat_id` | Delete category |
| GET | `/api/admin/special-points?class_id=X` | Get special points |
| POST | `/api/admin/special-points` | Create special points entry |
| PATCH | `/api/admin/special-points/:id` | Update special points |
| PATCH | `/api/admin/participation/bulk-approve` | Bulk approve participation |
| POST | `/api/admin/assignments` | Create assignment (reto) |
| GET | `/api/admin/assignments?class_id=X` | List assignments with submission counts |
| DELETE | `/api/admin/assignments/:id` | Delete assignment |
| GET | `/api/admin/assignments/:id/submissions?filter=` | View submissions with student info |
| PATCH | `/api/admin/submissions/:id/grade` | Grade a submission (upserts Grade record) |
| POST | `/api/admin/assignments/:id/auto-grade` | Auto-grade ungraded submissions |
| GET | `/api/admin/justifications?class_id=X` | List pending justifications |
| PATCH | `/api/admin/justifications/:id` | Approve/reject justification |
| PATCH | `/api/admin/classes/:id/settings` | Update class settings (grading_mode) |
| GET | `/api/admin/assignments/:id/exam-grading` | All enrolled students with current exam grade |
| POST | `/api/admin/assignments/:id/exam-grade` | Save/update one student's exam grade (no submission) |
| POST | `/api/admin/assignments/:id/upload-exam-html` | Upload HTML file for online exam (multipart, R2) |
| PATCH | `/api/admin/assignments/:id/settings` | Update online exam settings (window, time limit) |
| GET | `/api/admin/assignments/:id/online-submissions` | List students with online exam submission status |

### Forum (requires auth)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/forum/classes` | Classes the current user can access |
| GET | `/api/forum/posts?class_id=X&page=N` | Paginated post list (class_id optional — returns all accessible classes when omitted) |
| POST | `/api/forum/posts` | Create post (student: max 3/day, earns +0.01 pts) |
| GET | `/api/forum/posts/:id` | Post with replies tree |
| DELETE | `/api/forum/posts/:id` | Delete post (own or teacher) |
| POST | `/api/forum/posts/:id/like` | Toggle like; awards casino points |
| POST | `/api/forum/posts/:id/replies` | Create reply (threaded) |
| DELETE | `/api/forum/replies/:id` | Delete reply (own or teacher) |
| PATCH | `/api/forum/posts/:id/pin` | Toggle pin (teacher only) |
| PATCH | `/api/forum/posts/:id/lock` | Toggle lock (teacher only) |
| GET | `/api/forum/points/summary?class_id=X` | User's total forum points for a class |
| GET | `/api/forum/points/recent` | Last 20 point award events |

## Database Migrations

This project uses a lightweight **auto-migration** approach instead of Alembic. On every startup, `app/main.py` runs two steps:

1. **`Base.metadata.create_all()`** — creates any tables that don't exist yet (safe, never drops)
2. **`_ensure_columns()`** — adds missing columns to existing tables via `ALTER TABLE`

To add a new column to an existing table:

```python
# In app/main.py → _ensure_columns()
if "my_new_column" not in existing_cols:
    conn.execute(text(
        "ALTER TABLE my_table ADD COLUMN my_new_column VARCHAR(100)"
    ))
```

**PostgreSQL compatibility rules:**
- Use `TIMESTAMP` not `DATETIME`
- Use `DEFAULT TRUE` not `DEFAULT 1` for booleans
- Always check `existing_cols` before running ALTER TABLE

## Railway Deployment

1. Push code to GitHub
2. Create new Railway project, connect repo
3. Add PostgreSQL database service
4. Set environment variables in Railway dashboard
5. Add Railway domain to Google OAuth authorized origins
6. Deploy! (migrations run automatically before app starts)

## Project Structure

```
school-app/
├── app/
│   ├── main.py           # FastAPI app, CORS, routes
│   ├── auth.py           # Google OAuth, session management
│   └── storage.py        # Cloudflare R2 storage helpers
├── models/
│   ├── database.py       # SQLAlchemy setup (SQLite/PostgreSQL)
│   ├── models.py         # ORM models (Student, Class, Attendance, etc.)
│   └── schemas.py        # Pydantic schemas
├── routes/
│   ├── auth.py           # Auth endpoints
│   ├── admin.py          # Admin endpoints (class-scoped)
│   ├── classes.py        # Class management endpoints
│   ├── students.py       # Student endpoints
│   ├── participation.py  # Participation endpoints
│   ├── forum.py          # Forum endpoints (posts, replies, likes, moderation, points)
│   └── health.py         # Health check
├── alembic/
│   ├── env.py            # Alembic environment config
│   └── versions/         # Migration files
├── scripts/
│   └── migrate.py        # Production migration script
├── static/
│   ├── index.html        # Combined Forum + Dashboard landing page (Spanish)
│   ├── admin.html        # Admin panel - class overview (Spanish)
│   ├── class-dashboard.html  # Per-class dashboard (Spanish)
│   ├── exam-shell.html   # Online exam shell (auth, timer, iframe, postMessage)
│   ├── forum.html        # Standalone forum page
│   └── js/
│       ├── home.js       # Combined landing page JS (forum + dashboard + casino toasts)
│       ├── app.js        # Legacy student JS (kept for reference)
│       ├── admin.js      # Admin JS (class list, quick stats)
│       ├── class-dashboard.js  # Class dashboard JS (tabs, attendance, grades)
│       └── forum.js      # Standalone forum JS (moderation, likes, modal, toasts)
├── alembic.ini           # Alembic configuration
├── seed_data.py          # Test data script
├── requirements.txt
├── Procfile              # Railway start command (runs migrations)
├── railway.json          # Railway config
└── .env.example
```

## Roadmap

### Planned Features

- **Extra Points Redesign**: Replace boolean special-points flags with a student-driven submission system (teacher creates opportunities, students submit proof, teacher approves)
- **Lessons/Classroom**: Rich content lessons with video embeds, attachments, and progress tracking
- **QR Attendance**: Time-windowed QR codes for automatic attendance, with peer-to-peer chain propagation
- **In-App Notifications**: Bell icon with unread count; triggers on new assignments, participation reviews, etc.

See `planning/ROADMAP.md` for full details and `planning/NEXT_STEPS.md` for current priority queue.

## License

MIT
