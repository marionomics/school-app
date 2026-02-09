from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import inspect, text
from models.database import Base, engine
# Import all models to ensure they are registered with Base.metadata
from models.models import Student, Attendance, Participation, Grade, Class, StudentClass, GradeCategory, SpecialPoints, Assignment, Submission
from routes import health, students, participation, auth, admin, classes


def _ensure_columns():
    """Add missing columns to existing tables (lightweight migration)."""
    inspector = inspect(engine)

    if "grades" in inspector.get_table_names():
        existing_cols = {col["name"] for col in inspector.get_columns("grades")}

        with engine.begin() as conn:
            if "category_id" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE grades ADD COLUMN category_id INTEGER REFERENCES grade_categories(id)"
                ))
            if "name" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE grades ADD COLUMN name VARCHAR(200)"
                ))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create_all() is safe to call always: checkfirst=True (default) only
    # creates tables that don't already exist, never drops or modifies existing ones.
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="School Teaching App",
    description="A FastAPI application for managing student attendance, participation, and grades",
    version="0.1.0",
    lifespan=lifespan
)

# CORS configuration
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (before static files to ensure API routes take precedence)
app.include_router(health.router)
app.include_router(students.router)
app.include_router(participation.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(classes.router)

# Mount static files
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Serve the main dashboard."""
    return FileResponse("static/index.html")


@app.get("/admin")
async def admin_page():
    """Serve the admin dashboard."""
    return FileResponse("static/admin.html")


@app.get("/admin/class/{class_id}")
async def class_dashboard_page(class_id: int):
    """Serve the class dashboard page."""
    return FileResponse("static/class-dashboard.html")


@app.get("/api/config")
async def get_config():
    """Return frontend configuration including Google Client ID."""
    return {
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
    }
