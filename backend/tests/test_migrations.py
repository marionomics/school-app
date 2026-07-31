"""Regression test for the tarea-columns migration against pre-existing data.

Neither the empty local SQLite dev DB nor CI (which migrates an empty
database from scratch) exercises the case that actually matters in
production: applying `alembic upgrade head` against a `posts` table that
already has rows. A `NOT NULL` column added without a `server_default`
would abort that upgrade — and since Railway's start command is
`alembic upgrade head && uvicorn ...`, an aborted migration means the
container never boots. This test builds a throwaway SQLite database,
migrates it to the revision just before the tarea columns, inserts a
`posts` row with raw SQL (mirroring the pre-migration schema), then
upgrades to head and asserts both that the upgrade succeeds and that the
pre-existing row gets a sane `is_entrega` default.
"""

import sqlite3
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import settings
from app.models import utcnow

BACKEND_DIR = Path(__file__).resolve().parent.parent
PRE_TAREA_REVISION = "35864b6a75e3"


def test_tarea_migration_survives_existing_posts():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "migration_test.db"
        db_url = f"sqlite:///{db_path}"

        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        original_db_url = settings.database_url
        settings.database_url = db_url
        try:
            command.upgrade(cfg, PRE_TAREA_REVISION)

            now = utcnow().isoformat()
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute(
                    "INSERT INTO users (id, google_id, email, name, username, bio, "
                    "avatar_url, role, grade_is_private, created_at) VALUES "
                    "(1, 'g1', 'alumno@example.com', 'Alumno', NULL, '', NULL, "
                    "'student', 0, ?)",
                    (now,),
                )
                conn.execute(
                    "INSERT INTO posts (id, author_id, type, class_id, parent_id, "
                    "content, taps, status, like_count, reply_count, "
                    "last_activity_at, created_at, edited_at) VALUES "
                    "(1, 1, 'regular', NULL, NULL, 'ya existía antes de la migración', "
                    "NULL, 'active', 0, 0, ?, ?, NULL)",
                    (now, now),
                )
                conn.commit()
            finally:
                conn.close()

            # This is the line that would raise (IntegrityError / abort) in
            # production if `is_entrega` lacked a server_default.
            command.upgrade(cfg, "head")

            conn = sqlite3.connect(str(db_path))
            try:
                row = conn.execute(
                    "SELECT is_entrega, due_date FROM posts WHERE id = 1"
                ).fetchone()
            finally:
                conn.close()
        finally:
            settings.database_url = original_db_url

    assert row is not None
    is_entrega, due_date = row
    assert is_entrega == 0  # SQLite stores False as 0; server_default backfilled it
    assert due_date is None  # nullable column, no backfill needed
