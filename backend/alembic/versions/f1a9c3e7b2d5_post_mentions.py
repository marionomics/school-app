"""post_mentions

Every @username in a post, and for a submission whether it made that person
part of the team (spec 2026-10-28-menciones-equipos). A new table only — no
existing row changes, so it is safe against production data.

Revision ID: f1a9c3e7b2d5
Revises: e5b2c8d1a7f4
Create Date: 2026-10-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f1a9c3e7b2d5"
down_revision: Union[str, Sequence[str], None] = "e5b2c8d1a7f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "post_mentions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(),
                  sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("post_id", "user_id", name="uq_mention_post_user"),
    )
    op.create_index("ix_post_mentions_post_id", "post_mentions", ["post_id"])
    op.create_index("ix_post_mentions_user_id", "post_mentions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_post_mentions_user_id", "post_mentions")
    op.drop_index("ix_post_mentions_post_id", "post_mentions")
    op.drop_table("post_mentions")
