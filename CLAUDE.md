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

- `app/main.py` - FastAPI app entry point, routes registration
- `app/auth.py` - Google OAuth token verification and session management
- `routes/auth.py` - Authentication endpoints (`/api/auth/google`, `/api/auth/logout`)
- `routes/admin.py` - Teacher admin endpoints (attendance, grades, participation - all class-scoped)
- `routes/classes.py` - Class management endpoints (create, join, leave, list)
- `routes/students.py` - Student endpoints (grades, attendance with optional class filter)
- `routes/participation.py` - Participation submission (requires class_id)
- `models/models.py` - SQLAlchemy ORM models (Student, Class, StudentClass, Attendance, Participation, Grade)
- `models/schemas.py` - Pydantic request/response schemas
- `models/database.py` - Database connection and session management
- `static/index.html` - Student dashboard frontend (Spanish: "Portal del Estudiante")
- `static/js/app.js` - Student dashboard JavaScript (class enrollment, switching)
- `static/admin.html` - Teacher admin panel frontend (Spanish: "Panel del Profesor")
- `static/js/admin.js` - Admin panel JavaScript (class management, class-scoped operations)

## Multi-Class System

### How It Works
- Teachers create classes with auto-generated codes (e.g., "MICRO2026AB3X")
- Students join classes by entering the code
- All data (attendance, participation, grades) is scoped to specific classes
- Students can be enrolled in multiple classes and switch between them

### Database Models
- `Class` - id, name, code (unique), teacher_id, created_at
- `StudentClass` - Junction table (student_id, class_id, joined_at)
- `Attendance`, `Participation`, `Grade` - All have nullable `class_id` for backward compatibility

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

### Student Endpoints (requires auth)
- `GET /api/students/me` - Current student info
- `GET /api/students/me/grades?class_id=X` - Student's grades (optional class filter)
- `GET /api/students/me/attendance?class_id=X` - Student's attendance (optional class filter)
- `POST /api/participation` - Submit participation entry (requires class_id)

### Admin Endpoints (Teacher only)
- `GET /api/admin/students?class_id=X` - List students (optional: filter by class enrollment)
- `POST /api/admin/attendance` - Record attendance (requires class_id)
- `GET /api/admin/attendance?class_id=X&date=Y` - View attendance for class and date
- `POST /api/admin/grades` - Add grade (requires class_id)
- `GET /api/admin/participation?class_id=X` - View participation for class
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
- `student` - Default role, can view own data, submit participation, join classes
- `teacher` - Admin access, can create/manage classes, attendance, grades, and approve participation

**Teacher Account:** Set `TEACHER_EMAIL` in `.env` - this email gets teacher role on first login.

## Database

- **Development:** SQLite (auto-creates `school.db`)
- **Production:** PostgreSQL (Railway provides this)

Tables:
- `students` - Student records (includes `role`: student/teacher)
- `classes` - Class records (name, code, teacher_id)
- `student_classes` - Student-class enrollments (many-to-many)
- `attendances` - Daily attendance (status: present/absent/late/excused, class_id)
- `participations` - Class participation entries with points and approval status (class_id)
- `grades` - Scored assignments (category: homework/quiz/exam/project, class_id)

## Development Notes

- Frontend uses Tailwind CSS via CDN (no build step)
- Frontend is fully translated to Spanish (UI labels, messages, date formatting uses es-MX locale)
- Database file (`school.db`) is gitignored
- Run `seed_data.py` to populate test data (creates teacher, 3 students, sample class, enrollments, and sample records)
- `class_id` is nullable in attendance/participation/grades for backward compatibility

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
