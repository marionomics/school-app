# CLAUDE.md

This file provides context for Claude Code when working on this project.

## Project Overview

A FastAPI teaching application for managing student attendance, participation, and grades. Built as an educational tool for classroom management.

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy ORM, Pydantic
- **Database:** SQLite (file: `school.db`)
- **Frontend:** Vanilla JS with Tailwind CSS (CDN)
- **Auth:** Placeholder token-based (to be replaced with OAuth)

## Key Commands

```bash
# Run the server
uvicorn app.main:app --reload

# Seed test data
python seed_data.py
```

## Project Structure

- `app/main.py` - FastAPI app entry point, routes registration
- `app/auth.py` - Placeholder authentication (Bearer token: `student_<id>`)
- `models/models.py` - SQLAlchemy ORM models (Student, Attendance, Participation, Grade)
- `models/schemas.py` - Pydantic request/response schemas
- `models/database.py` - Database connection and session management
- `routes/` - API route handlers
- `static/index.html` - Student dashboard frontend
- `static/js/app.js` - Frontend JavaScript (API calls, rendering)

## API Endpoints

- `GET /api/health` - Health check
- `GET /api/students/me` - Current student info (requires auth)
- `GET /api/students/me/grades` - Student's grades
- `GET /api/students/me/attendance` - Student's attendance
- `POST /api/participation` - Submit participation entry

## Authentication

Currently uses placeholder auth. Token format: `Bearer student_<id>`

Example: `Authorization: Bearer student_1` returns student with ID 1.

**TODO:** Replace with proper OAuth implementation.

## Database

SQLite database auto-creates on first run. Tables:
- `students` - Student records
- `attendances` - Daily attendance (status: present/absent/late/excused)
- `participations` - Class participation entries with points
- `grades` - Scored assignments (category: homework/quiz/exam/project)

## Development Notes

- Frontend uses Tailwind CSS via CDN (no build step)
- Database file (`school.db`) is gitignored
- Run `seed_data.py` to populate test data (creates 3 students, sample records for student ID 1)
