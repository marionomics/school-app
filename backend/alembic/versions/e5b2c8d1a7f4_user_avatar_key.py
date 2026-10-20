"""user avatar_key

The user's own profile photo on R2. avatar_url (Google's, set when the
account was created) stays as the fallback.

Revision ID: e5b2c8d1a7f4
Revises: d4a1f7c2e9b3
Create Date: 2026-10-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5b2c8d1a7f4"
down_revision: Union[str, Sequence[str], None] = "d4a1f7c2e9b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_key", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_key")
