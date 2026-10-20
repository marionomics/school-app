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


def test_reviews_is_keyed_on_item_and_student(db):
    from sqlalchemy import inspect

    cols = {c["name"] for c in inspect(db.bind).get_columns("reviews")}
    assert {"item_post_id", "student_id", "entrega_post_id"} <= cols
    uniques = inspect(db.bind).get_unique_constraints("reviews")
    indexes = inspect(db.bind).get_indexes("reviews")
    keyed = [u["column_names"] for u in uniques] + \
            [i["column_names"] for i in indexes if i.get("unique")]
    assert ["item_post_id", "student_id"] in keyed


def test_posts_has_examen_and_veto_columns(db):
    from sqlalchemy import inspect

    cols = {c["name"] for c in inspect(db.bind).get_columns("posts")}
    assert {"examen_mode", "graded_at", "veto_reason"} <= cols


def test_incentives_table_has_required_columns(db):
    from sqlalchemy import inspect

    cols = {c["name"] for c in inspect(db.bind).get_columns("incentives")}
    assert {"id", "class_id", "name", "points", "description",
            "created_at", "deleted_at"} <= cols


def test_posts_has_reviewed_columns(db):
    from sqlalchemy import inspect

    cols = {c["name"] for c in inspect(db.bind).get_columns("posts")}
    assert {"reviewed_at", "reviewed_by"} <= cols


def test_teacher_aura_migration_reconciles_likes_and_validations():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "aura_migration.db"
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        original_db_url = settings.database_url
        settings.database_url = f"sqlite:///{db_path}"
        try:
            command.upgrade(cfg, "c02ad66222b5")
            now = utcnow().isoformat()
            conn = sqlite3.connect(str(db_path))
            try:
                for uid, role in ((1, "teacher"), (2, "student")):
                    conn.execute(
                        "INSERT INTO users (id, google_id, email, name, username, bio, "
                        "avatar_url, role, grade_is_private, created_at) VALUES "
                        "(?, ?, ?, 'U', NULL, '', NULL, ?, 0, ?)",
                        (uid, f"g{uid}", f"u{uid}@example.com", role, now))
                conn.execute(
                    "INSERT INTO classes (id, name, code, teacher_id, start_date, end_date, "
                    "schedule_json, tareas_weight, examenes_weight, attendance_required_pct, "
                    "created_at) VALUES (1, 'Micro', 'MICRO', 1, '2026-08-17', '2026-12-04', "
                    "'[]', 30, 30, 80, ?)", (now,))
                posts = [
                    # id, author, type, reviewed_at, like_count
                    (1, 2, "participacion", "2026-09-01T10:00:00", 0),  # validated, no aura
                    (2, 2, "participacion", None, 1),                   # aura, not validated
                    (3, 1, "participacion", "2026-09-01T10:00:00", 0),  # teacher's own
                    (4, 2, "regular", None, 1),                         # aura on a regular post
                ]
                for pid, author, ptype, reviewed_at, likes in posts:
                    conn.execute(
                        "INSERT INTO posts (id, author_id, type, class_id, parent_id, content, "
                        "taps, status, like_count, reply_count, last_activity_at, created_at, "
                        "is_entrega, reviewed_at, reviewed_by) VALUES "
                        "(?, ?, ?, 1, NULL, 'c', 1, 'active', ?, 0, '2026-09-01T09:00:00', ?, 0, ?, ?)",
                        (pid, author, ptype, likes, now, reviewed_at, 1 if reviewed_at else None))
                for pid in (2, 4):
                    conn.execute(
                        "INSERT INTO likes (user_id, post_id, created_at) VALUES "
                        "(1, ?, '2026-09-02T10:00:00')", (pid,))
                conn.commit()
            finally:
                conn.close()

            command.upgrade(cfg, "head")
            # Idempotent: going back (a no-op) and up again changes nothing.
            command.downgrade(cfg, "c02ad66222b5")
            command.upgrade(cfg, "head")

            conn = sqlite3.connect(str(db_path))
            try:
                rows = {pid: (lc, rv, act) for pid, lc, rv, act in conn.execute(
                    "SELECT id, like_count, reviewed_at, last_activity_at FROM posts")}
                likes = {(u, p) for u, p in conn.execute("SELECT user_id, post_id FROM likes")}
            finally:
                conn.close()
        finally:
            settings.database_url = original_db_url

    assert (1, 1) in likes and rows[1][0] == 1          # validated → got the aura, once
    assert rows[2][1] is not None                       # aura → validated
    assert (1, 3) not in likes and rows[3][0] == 0      # never a self-like
    assert rows[4][1] is None                           # a regular post is not validated
    assert {r[2] for r in rows.values()} == {"2026-09-01T09:00:00"}  # no bump


def test_avatar_key_migration_keeps_google_photos():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "avatar_migration.db"
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        original_db_url = settings.database_url
        settings.database_url = f"sqlite:///{db_path}"
        try:
            command.upgrade(cfg, "d4a1f7c2e9b3")
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute(
                    "INSERT INTO users (id, google_id, email, name, username, bio, "
                    "avatar_url, role, grade_is_private, created_at) VALUES "
                    "(1, 'g1', 'a@example.com', 'A', 'a', '', 'https://google.test/a.jpg', "
                    "'student', 0, ?)", (utcnow().isoformat(),))
                conn.commit()
            finally:
                conn.close()
            command.upgrade(cfg, "head")
            conn = sqlite3.connect(str(db_path))
            try:
                row = conn.execute("SELECT avatar_url, avatar_key FROM users WHERE id = 1").fetchone()
            finally:
                conn.close()
        finally:
            settings.database_url = original_db_url
    assert row == ("https://google.test/a.jpg", None)
