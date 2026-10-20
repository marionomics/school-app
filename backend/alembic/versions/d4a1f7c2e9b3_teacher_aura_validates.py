"""teacher aura validates (data only)

The teacher's aura on a participación and its validation became one fact in
Bloque 2. This fills in whichever half is missing on existing rows so the
two never disagree: validated posts get the teacher's like, and liked posts
get reviewed_at. Never a self-like; never touches last_activity_at.

Revision ID: d4a1f7c2e9b3
Revises: c02ad66222b5
Create Date: 2026-10-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4a1f7c2e9b3"
down_revision: Union[str, Sequence[str], None] = "c02ad66222b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Validated participaciones of a class whose teacher has not liked them yet.
_MISSING_LIKE = """
    FROM posts p JOIN classes c ON c.id = p.class_id
    WHERE p.type = 'participacion'
      AND p.reviewed_at IS NOT NULL
      AND p.author_id <> c.teacher_id
      AND NOT EXISTS (SELECT 1 FROM likes l
                      WHERE l.post_id = p.id AND l.user_id = c.teacher_id)
"""


def upgrade() -> None:
    bind = op.get_bind()
    # 1a. Count first, while the predicate still selects exactly these posts.
    bind.execute(sa.text(
        f"UPDATE posts SET like_count = like_count + 1 "
        f"WHERE id IN (SELECT p.id {_MISSING_LIKE})"))
    # 1b. Then the like itself, dated when the teacher validated.
    bind.execute(sa.text(
        f"INSERT INTO likes (user_id, post_id, created_at) "
        f"SELECT c.teacher_id, p.id, p.reviewed_at {_MISSING_LIKE}"))
    # 2. Participaciones the class teacher liked but never validated.
    bind.execute(sa.text("""
        UPDATE posts SET
          reviewed_at = (SELECT l.created_at FROM likes l JOIN classes c
                         ON c.teacher_id = l.user_id
                         WHERE l.post_id = posts.id AND c.id = posts.class_id),
          reviewed_by = (SELECT c.teacher_id FROM classes c WHERE c.id = posts.class_id)
        WHERE type = 'participacion'
          AND reviewed_at IS NULL
          AND EXISTS (SELECT 1 FROM likes l JOIN classes c ON c.id = posts.class_id
                      WHERE l.post_id = posts.id AND l.user_id = c.teacher_id)
    """))


def downgrade() -> None:
    # Data only: it filled in missing halves. Nothing to undo.
    pass
