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

    if "submissions" in inspector.get_table_names():
        existing_cols = {col["name"] for col in inspector.get_columns("submissions")}

        with engine.begin() as conn:
            if "drive_url" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE submissions ADD COLUMN drive_url VARCHAR(500)"
                ))
            if "penalty_pct" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE submissions ADD COLUMN penalty_pct INTEGER DEFAULT 100 NOT NULL"
                ))
            if "file_key" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE submissions ADD COLUMN file_key VARCHAR(500)"
                ))
            if "file_name" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE submissions ADD COLUMN file_name VARCHAR(300)"
                ))
            if "file_size" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE submissions ADD COLUMN file_size INTEGER"
                ))
            if "resubmit_count" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE submissions ADD COLUMN resubmit_count INTEGER DEFAULT 0 NOT NULL"
                ))


    if "classes" in inspector.get_table_names():
        existing_cols = {col["name"] for col in inspector.get_columns("classes")}
        with engine.begin() as conn:
            if "grading_mode" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE classes ADD COLUMN grading_mode VARCHAR(20) DEFAULT 'points'"
                ))

    if "assignments" in inspector.get_table_names():
        existing_cols = {col["name"] for col in inspector.get_columns("assignments")}
        with engine.begin() as conn:
            if "exam_type" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE assignments ADD COLUMN exam_type VARCHAR(20) DEFAULT 'homework'"
                ))

    # Data repair: assign a category to assignments that were saved without one
    if "assignments" in inspector.get_table_names() and "grade_categories" in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE assignments
                SET category_id = (
                    SELECT gc.id FROM grade_categories gc
                    WHERE gc.class_id = assignments.class_id
                    ORDER BY gc.id
                    LIMIT 1
                )
                WHERE category_id IS NULL
                AND EXISTS (
                    SELECT 1 FROM grade_categories gc
                    WHERE gc.class_id = assignments.class_id
                )
            """))

    # Data repair: fix grades from assignments that have category_id = NULL
    # Match by grade name == assignment title within the same class
    if "grades" in inspector.get_table_names() and "assignments" in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE grades
                SET category_id = (
                    SELECT a.category_id FROM assignments a
                    WHERE a.title = grades.name
                    AND a.class_id = grades.class_id
                    AND a.category_id IS NOT NULL
                    LIMIT 1
                )
                WHERE category_id IS NULL
                AND name IS NOT NULL
                AND EXISTS (
                    SELECT 1 FROM assignments a
                    WHERE a.title = grades.name
                    AND a.class_id = grades.class_id
                    AND a.category_id IS NOT NULL
                )
            """))

    if "attendances" in inspector.get_table_names():
        existing_cols = {col["name"] for col in inspector.get_columns("attendances")}

        with engine.begin() as conn:
            if "justification_file_key" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE attendances ADD COLUMN justification_file_key VARCHAR(500)"
                ))
            if "justification_file_name" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE attendances ADD COLUMN justification_file_name VARCHAR(300)"
                ))
            if "justification_text" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE attendances ADD COLUMN justification_text TEXT"
                ))
            if "justification_status" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE attendances ADD COLUMN justification_status VARCHAR(20)"
                ))
            if "justification_submitted_at" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE attendances ADD COLUMN justification_submitted_at TIMESTAMP"
                ))
            if "justification_reviewed_at" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE attendances ADD COLUMN justification_reviewed_at TIMESTAMP"
                ))
            if "justification_reviewed_by" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE attendances ADD COLUMN justification_reviewed_by INTEGER REFERENCES students(id)"
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
    from app.storage import is_r2_configured
    return {
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "file_uploads_enabled": is_r2_configured(),
    }
