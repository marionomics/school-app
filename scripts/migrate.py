#!/usr/bin/env python3
"""
Database migration script for production deployments.

This script safely applies pending Alembic migrations to the database.
It should be run before starting the application after any schema changes.

Usage:
    python scripts/migrate.py              # Apply all pending migrations
    python scripts/migrate.py --check      # Check migration status only
    python scripts/migrate.py --rollback   # Rollback last migration

For Railway deployment, add this to your start command:
    python scripts/migrate.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT
"""
import os
import sys
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from alembic.config import Config
from alembic import command
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine


def get_database_url():
    """Get database URL from environment."""
    database_url = os.getenv("DATABASE_URL", "sqlite:///./school.db")
    # Railway uses postgres:// but SQLAlchemy requires postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def get_alembic_config():
    """Get Alembic configuration."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", get_database_url())
    return alembic_cfg


def get_current_revision():
    """Get current database revision."""
    engine = create_engine(get_database_url())
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        return context.get_current_revision()


def check_status():
    """Check and display migration status."""
    current = get_current_revision()
    print(f"Current database revision: {current or 'None (no migrations applied)'}")

    alembic_cfg = get_alembic_config()
    print("\nPending migrations:")
    command.history(alembic_cfg, indicate_current=True)


def upgrade():
    """Apply all pending migrations."""
    current = get_current_revision()
    print(f"Current revision: {current or 'None'}")
    print("Applying pending migrations...")

    alembic_cfg = get_alembic_config()
    command.upgrade(alembic_cfg, "head")

    new_revision = get_current_revision()
    print(f"New revision: {new_revision}")
    print("Migration complete!")


def rollback():
    """Rollback the last migration."""
    current = get_current_revision()
    if not current:
        print("No migrations to rollback.")
        return

    print(f"Current revision: {current}")
    print("Rolling back last migration...")

    alembic_cfg = get_alembic_config()
    command.downgrade(alembic_cfg, "-1")

    new_revision = get_current_revision()
    print(f"New revision: {new_revision or 'None'}")
    print("Rollback complete!")


def main():
    parser = argparse.ArgumentParser(description="Database migration tool")
    parser.add_argument("--check", action="store_true", help="Check migration status only")
    parser.add_argument("--rollback", action="store_true", help="Rollback last migration")
    args = parser.parse_args()

    try:
        if args.check:
            check_status()
        elif args.rollback:
            rollback()
        else:
            upgrade()
    except Exception as e:
        print(f"Migration error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
