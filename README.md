# School Teaching App

A FastAPI application for managing student attendance, participation, and grades. Built for UJED classroom management.

## Features

- **Student Dashboard**: View grades, attendance, submit participation
- **Teacher Admin Panel**: Record attendance, manage grades, approve participation
- **Google OAuth**: Secure authentication via Google accounts
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
   - API Docs: http://localhost:8000/docs

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

### Student (requires auth)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/students/me` | Current student info |
| GET | `/api/students/me/grades` | Student's grades |
| GET | `/api/students/me/attendance` | Student's attendance |
| POST | `/api/participation` | Submit participation |

### Admin (teacher only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/students` | List all students |
| POST | `/api/admin/attendance` | Record bulk attendance |
| GET | `/api/admin/attendance` | Get attendance by date |
| POST | `/api/admin/grades` | Add grade |
| GET | `/api/admin/participation` | View all participation |
| PATCH | `/api/admin/participation/:id` | Approve/reject |

## Railway Deployment

1. Push code to GitHub
2. Create new Railway project, connect repo
3. Add PostgreSQL database service
4. Set environment variables in Railway dashboard
5. Add Railway domain to Google OAuth authorized origins
6. Deploy!

## Project Structure

```
school-app/
├── app/
│   ├── main.py           # FastAPI app, CORS, routes
│   └── auth.py           # Google OAuth, session management
├── models/
│   ├── database.py       # SQLAlchemy setup (SQLite/PostgreSQL)
│   ├── models.py         # ORM models
│   └── schemas.py        # Pydantic schemas
├── routes/
│   ├── auth.py           # Auth endpoints
│   ├── admin.py          # Admin endpoints
│   ├── students.py       # Student endpoints
│   ├── participation.py  # Participation endpoints
│   └── health.py         # Health check
├── static/
│   ├── index.html        # Student dashboard
│   ├── admin.html        # Admin panel
│   └── js/
│       ├── app.js        # Student JS
│       └── admin.js      # Admin JS
├── seed_data.py          # Test data script
├── requirements.txt
├── Procfile              # Railway start command
├── railway.json          # Railway config
└── .env.example
```

## License

MIT
