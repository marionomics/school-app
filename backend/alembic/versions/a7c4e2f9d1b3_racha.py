"""racha: post_rolls and points_config.streak_levels

Spec 2026-10-31-racha. A new table plus a NOT NULL JSON column with a server
default, so every existing class gets the default odds with no data step.

Revision ID: a7c4e2f9d1b3
Revises: f1a9c3e7b2d5
Create Date: 2026-10-31
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a7c4e2f9d1b3"
down_revision: Union[str, Sequence[str], None] = "f1a9c3e7b2d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT = [
    {"from_days": 3, "x2": 0.15, "x3": 0.0},
    {"from_days": 7, "x2": 0.2, "x3": 0.05},
    {"from_days": 14, "x2": 0.25, "x3": 0.1},
]


def upgrade() -> None:
    op.create_table(
        "post_rolls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(),
                  sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("multiplier", sa.SmallInteger(), nullable=False),
        sa.Column("streak_days", sa.Integer(), nullable=False),
        sa.Column("x2", sa.Numeric(4, 3), nullable=False),
        sa.Column("x3", sa.Numeric(4, 3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_post_rolls_post_id", "post_rolls", ["post_id"], unique=True)
    # A quoted literal is untyped in Postgres and casts to json; SQLite stores it.
    op.add_column("points_config", sa.Column(
        "streak_levels", sa.JSON(), nullable=False,
        server_default=sa.text("'" + json.dumps(DEFAULT) + "'")))


def downgrade() -> None:
    op.drop_column("points_config", "streak_levels")
    op.drop_index("ix_post_rolls_post_id", "post_rolls")
    op.drop_table("post_rolls")
