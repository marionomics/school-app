# CLAUDE.md

This file provides context for Claude Code when working on this project.

## Project Overview

A FastAPI teaching application for managing student attendance, participation, and grades. Built as an educational tool for classroom management.

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy ORM, Pydantic
- **Database:** SQLite (dev) / PostgreSQL (production)
- **Frontend:** Vanilla JS with Tailwind CSS (CDN)
- **Auth:** Google OAuth (Google Identity Services)
- **Deployment:** Railway

## Key Commands

```bash
# Run the server
uvicorn app.main:app --reload

# Seed test data
python seed_data.py
```

## Project Structure

- `app/main.py` - FastAPI app entry point, routes registration
- `app/auth.py` - Google OAuth token verification and session management
- `routes/auth.py` - Authentication endpoints (`/api/auth/google`, `/api/auth/logout`)
- `routes/admin.py` - Teacher admin endpoints (attendance, grades, participation management)
- `models/models.py` - SQLAlchemy ORM models (Student, Attendance, Participation, Grade)
- `models/schemas.py` - Pydantic request/response schemas
- `models/database.py` - Database connection and session management
- `routes/` - API route handlers
- `static/index.html` - Student dashboard frontend
- `static/js/app.js` - Student dashboard JavaScript
- `static/admin.html` - Teacher admin panel frontend
- `static/js/admin.js` - Admin panel JavaScript

## API Endpoints

- `GET /api/health` - Health check
- `GET /api/config` - Frontend configuration (Google Client ID)
- `POST /api/auth/google` - Authenticate with Google ID token
- `POST /api/auth/logout` - Invalidate session
- `GET /api/students/me` - Current student info (requires auth)
- `GET /api/students/me/grades` - Student's grades
- `GET /api/students/me/attendance` - Student's attendance
- `POST /api/participation` - Submit participation entry

### Admin Endpoints (Teacher only)
- `GET /api/admin/students` - List all students
- `POST /api/admin/attendance` - Record attendance for multiple students
- `GET /api/admin/attendance?date=YYYY-MM-DD` - View attendance for a date
- `POST /api/admin/grades` - Add grade for a student
- `GET /api/admin/participation` - View all participation submissions
- `PATCH /api/admin/participation/:id` - Approve/reject participation

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
- `student` - Default role, can view own data and submit participation
- `teacher` - Admin access, can manage attendance, grades, and approve participation

**Teacher Account:** Set `TEACHER_EMAIL` in `.env` - this email gets teacher role on first login.

## Database

- **Development:** SQLite (auto-creates `school.db`)
- **Production:** PostgreSQL (Railway provides this)

Tables:
- `students` - Student records (includes `role`: student/teacher)
- `attendances` - Daily attendance (status: present/absent/late/excused)
- `participations` - Class participation entries with points and approval status
- `grades` - Scored assignments (category: homework/quiz/exam/project)

## Development Notes

- Frontend uses Tailwind CSS via CDN (no build step)
- Database file (`school.db`) is gitignored
- Run `seed_data.py` to populate test data (creates 3 students, sample records for student ID 1)

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
