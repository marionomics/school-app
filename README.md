# School Teaching App

A FastAPI application for managing student attendance, participation, and grades.

## Project Structure

```
school-app/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application entry point
│   └── auth.py          # Authentication (placeholder)
├── models/
│   ├── __init__.py
│   ├── database.py      # SQLAlchemy database setup
│   ├── models.py        # SQLAlchemy ORM models
│   └── schemas.py       # Pydantic validation schemas
├── routes/
│   ├── __init__.py
│   ├── health.py        # Health check endpoint
│   ├── students.py      # Student-related endpoints
│   └── participation.py # Participation endpoints
├── static/              # Static files (CSS, JS, images)
├── templates/           # Jinja2 templates
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create your `.env` file:
   ```bash
   cp .env.example .env
   ```

4. Run the application:
   ```bash
   uvicorn app.main:app --reload
   ```

5. Open your browser to:
   - API: http://localhost:8000
   - Docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/students/me` | Get current student info |
| GET | `/api/students/me/grades` | Get student's grades |
| GET | `/api/students/me/attendance` | Get student's attendance |
| POST | `/api/participation` | Submit participation |

## Authentication (Placeholder)

Currently using placeholder authentication. To test endpoints:

1. Create a student in the database
2. Use the header: `Authorization: Bearer student_<id>`

Example:
```bash
curl -H "Authorization: Bearer student_1" http://localhost:8000/api/students/me
```

## Database Models

- **Student**: id, name, email, oauth_id, created_at
- **Attendance**: id, student_id, date, status, notes
- **Participation**: id, student_id, date, description, points
- **Grade**: id, student_id, category, score, max_score, date

## Development

The SQLite database (`school.db`) is created automatically on first run.

To add test data, you can use the FastAPI interactive docs at `/docs` or create a seed script.
