from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from models.database import Base, engine
from routes import health, students, participation


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create database tables
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="School Teaching App",
    description="A FastAPI application for managing student attendance, participation, and grades",
    version="0.1.0",
    lifespan=lifespan
)

# Include routers (before static files to ensure API routes take precedence)
app.include_router(health.router)
app.include_router(students.router)
app.include_router(participation.router)

# Mount static files
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Serve the main dashboard."""
    return FileResponse("static/index.html")
