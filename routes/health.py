"""
Health and debug endpoints.
Debug endpoints are protected by SECRET_KEY passed as X-Debug-Token header.
"""
import os
import sys
import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import inspect as sa_inspect, text

from models.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])

DEBUG_TOKEN = os.getenv("SECRET_KEY", "")


def verify_debug_token(x_debug_token: str = Header()):
    """Require SECRET_KEY in X-Debug-Token header."""
    if not DEBUG_TOKEN or x_debug_token != DEBUG_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid debug token")


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "API is running"}


@router.get("/debug/schema")
async def debug_schema(
    db: Session = Depends(get_db),
    _=Depends(verify_debug_token),
):
    """Show database schema: tables, columns, row counts."""
    try:
        inspector = sa_inspect(db.bind)
        table_names = sorted(inspector.get_table_names())

        schema = {}
        row_counts = {}
        for table in table_names:
            cols = inspector.get_columns(table)
            schema[table] = [
                {"name": c["name"], "type": str(c["type"]), "nullable": c.get("nullable")}
                for c in cols
            ]
            try:
                count = db.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
                row_counts[table] = count
            except Exception as e:
                row_counts[table] = f"error: {e}"

        db_url = os.getenv("DATABASE_URL", "")
        # Mask password in URL
        if "@" in db_url:
            pre, post = db_url.split("@", 1)
            db_type = pre.split("://")[0] if "://" in pre else "unknown"
            db_display = f"{db_type}://***@{post}"
        else:
            db_display = db_url.split("?")[0]

        return {
            "env": {
                "python_version": sys.version,
                "database_type": db_display,
                "debug_mode": os.getenv("DEBUG", "false"),
            },
            "tables": table_names,
            "row_counts": row_counts,
            "schema": schema,
        }
    except Exception as e:
        logger.error(f"Debug schema error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/test-queries")
async def debug_test_queries(
    db: Session = Depends(get_db),
    _=Depends(verify_debug_token),
):
    """Run test queries against each core table to verify they work."""
    results = {}
    queries = {
        "students": "SELECT id, email, role FROM students LIMIT 3",
        "classes": "SELECT id, name, code FROM classes LIMIT 3",
        "student_classes": "SELECT id, student_id, class_id FROM student_classes LIMIT 3",
        "attendances": "SELECT id, student_id, class_id, date, status FROM attendances LIMIT 3",
        "participations": "SELECT id, student_id, class_id, date, approved, points FROM participations LIMIT 3",
        "grades": "SELECT id, student_id, class_id, category, score, max_score, date FROM grades LIMIT 3",
    }

    for name, sql in queries.items():
        try:
            rows = db.execute(text(sql)).fetchall()
            results[name] = {
                "status": "ok",
                "row_count": len(rows),
                "sample": [dict(row._mapping) for row in rows],
            }
        except Exception as e:
            db.rollback()
            results[name] = {"status": "error", "error": str(e)}

    return results
