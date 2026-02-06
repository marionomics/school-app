# School Teaching App

A FastAPI application for managing student attendance, participation, and grades. Built for UJED classroom management.

## Features

- **Multi-Class Support**: Teachers create classes with unique codes, students join via codes
- **Class Dashboard**: Comprehensive per-class view with stats, roster, attendance, grades, and participation tabs
- **Weighted Grading System**: Configurable grade categories with weights, participation points, special bonus points
- **Student Dashboard**: View grades breakdown, attendance, submit participation (filtered by class)
- **Teacher Admin Panel**: Simple class overview with quick stats, click any class to open detailed dashboard
- **Google OAuth**: Secure authentication via Google accounts
- **Spanish UI**: Full Spanish language interface
- **Railway Ready**: Configured for easy cloud deployment

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, Pydantic
- **Database**: SQLite (dev) / PostgreSQL (production)
- **Frontend**: Vanilla JS, Tailwind CSS (CDN)
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
Final Grade = Σ(Category Weight × Category Average) + (0.1 × Participation Points) + Special Points
```

### Grade Categories
- Teachers configure categories per class (e.g., "Retos de la Semana" 40%, "Examenes" 40%, "Proyecto" 20%)
- Each grade is assigned to a category
- Category averages are weighted and summed

### Participation Points
- Students submit participation entries describing their contributions
- Teachers approve/reject and assign points (1-3)
- Approved points × 0.1 added to final grade

### Special Points
- Two optional categories: English (0.5 pts) and Notebook (0.5 pts)
- Students opt-in at start of semester
- Teacher awards at end of semester if criteria met

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Database connection string |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret |
| `TEACHER_EMAIL` | Email that gets admin access |
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) |
| `SECRET_KEY` | Application secret key |

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
| POST | `/api/participation` | Submit participation (requires class_id) |

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

## Database Migrations

This project uses **Alembic** for database migrations to safely manage schema changes without data loss.

### Creating a New Migration

After modifying models in `models/models.py`:

```bash
# Generate migration automatically from model changes
alembic revision --autogenerate -m "Add new_field to students"

# Review the generated migration in alembic/versions/
# Then apply it
alembic upgrade head
```

### Applying Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Or use the migration script
python scripts/migrate.py

# Check migration status
python scripts/migrate.py --check
```

### Rolling Back

```bash
# Rollback last migration
alembic downgrade -1

# Or use the script
python scripts/migrate.py --rollback

# Rollback to specific revision
alembic downgrade <revision_id>
```

### Important Notes

- **Never use `drop_all()`** - it deletes all data
- Always review auto-generated migrations before applying
- Test migrations on a copy of production data first
- Migrations run automatically on Railway deployment (via Procfile)

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
│   └── auth.py           # Google OAuth, session management
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
│   └── health.py         # Health check
├── alembic/
│   ├── env.py            # Alembic environment config
│   └── versions/         # Migration files
├── scripts/
│   └── migrate.py        # Production migration script
├── static/
│   ├── index.html        # Student dashboard (Spanish)
│   ├── admin.html        # Admin panel - class overview (Spanish)
│   ├── class-dashboard.html  # Per-class dashboard (Spanish)
│   └── js/
│       ├── app.js        # Student JS (class enrollment, switching)
│       ├── admin.js      # Admin JS (class list, quick stats)
│       └── class-dashboard.js  # Class dashboard JS (tabs, attendance, grades)
├── alembic.ini           # Alembic configuration
├── seed_data.py          # Test data script
├── requirements.txt
├── Procfile              # Railway start command (runs migrations)
├── railway.json          # Railway config
└── .env.example
```

## Roadmap

### Planned Features

- **Homework System**: Assignments with due dates, file uploads, grading, and feedback
- **Lessons/Classroom**: Rich content lessons with video embeds, attachments, and progress tracking
- **Forum**: Class discussion boards with threaded replies and likes

See `CLAUDE.md` for detailed schema designs.

## License

MIT
