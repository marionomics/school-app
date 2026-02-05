from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import inspect
from models.database import Base, engine
# Import all models to ensure they are registered with Base.metadata
from models.models import Student, Attendance, Participation, Grade, Class, StudentClass
from routes import health, students, participation, auth, admin, classes


def tables_exist() -> bool:
    """Check if database tables already exist."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    return "students" in existing_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Database initialization
    # In production, use 'alembic upgrade head' before starting the app
    # For development convenience, create tables if they don't exist
    # NOTE: create_all() only creates tables that don't already exist (checkfirst=True by default)
    # NEVER use drop_all() - it would delete all data
    if not tables_exist():
        # Only for initial setup - after first run, use alembic migrations
        Base.metadata.create_all(bind=engine)
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


@app.get("/api/config")
async def get_config():
    """Return frontend configuration including Google Client ID."""
    return {
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
    }
