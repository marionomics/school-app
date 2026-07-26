from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import storage
from app.auth.deps import get_current_user
from app.config import settings
from app.models import User
from app.routers import auth as auth_router
from app.routers import classes as classes_router
from app.routers import posts as posts_router
from app.routers import users as users_router
from app.schemas import UserOut

app = FastAPI(title="Plataforma v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(classes_router.router)
app.include_router(posts_router.router)
app.include_router(posts_router.feed_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config():
    return {
        "google_client_id": settings.google_client_id,
        "file_uploads_enabled": storage.is_r2_configured(),
    }


@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def _resolve_within(base: Path, full_path: str) -> Path:
    """Resolve full_path against base and return a safe path to serve.

    Returns base / "index.html" if the resolved candidate would escape
    base (path traversal) or doesn't exist as a file; otherwise returns
    the resolved candidate itself.
    """
    resolved_base = base.resolve()
    try:
        candidate = (resolved_base / full_path).resolve()
    except (OSError, RuntimeError):
        return resolved_base / "index.html"
    if candidate != resolved_base and resolved_base not in candidate.parents:
        return resolved_base / "index.html"
    if candidate.is_file():
        return candidate
    return resolved_base / "index.html"


if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            # let FastAPI's 404 handling apply — this route only catches non-API paths
            raise HTTPException(status_code=404)
        return FileResponse(_resolve_within(FRONTEND_DIST, full_path))
