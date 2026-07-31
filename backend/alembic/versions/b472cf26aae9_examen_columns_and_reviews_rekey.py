"""examen columns and reviews rekey

Revision ID: b472cf26aae9
Revises: e912d98d2bc3
Create Date: 2026-07-31 17:50:39.711559

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b472cf26aae9'
down_revision: Union[str, Sequence[str], None] = 'e912d98d2bc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('posts', sa.Column('examen_mode', sa.String(length=10), nullable=True))
    op.add_column('posts', sa.Column('graded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('posts', sa.Column('veto_reason', sa.Text(), nullable=True))

    # reviews shipped empty in 2a — no rows to preserve, so re-key by rebuild.
    op.drop_index(op.f('ix_reviews_entrega_post_id'), table_name='reviews')
    op.drop_table('reviews')
    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('item_post_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('entrega_post_id', sa.Integer(), nullable=True),
        sa.Column('reviewer_id', sa.Integer(), nullable=True),
        sa.Column('score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('auto_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['item_post_id'], ['posts.id'], ),
        sa.ForeignKeyConstraint(['entrega_post_id'], ['posts.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('item_post_id', 'student_id', name='uq_review_item_student'),
    )
    op.create_index(op.f('ix_reviews_item_post_id'), 'reviews', ['item_post_id'])
    op.create_index(op.f('ix_reviews_student_id'), 'reviews', ['student_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_reviews_student_id'), table_name='reviews')
    op.drop_index(op.f('ix_reviews_item_post_id'), table_name='reviews')
    op.drop_table('reviews')
    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entrega_post_id', sa.Integer(), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), nullable=True),
        sa.Column('score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('auto_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['entrega_post_id'], ['posts.id'], ),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reviews_entrega_post_id'), 'reviews', ['entrega_post_id'], unique=True)
    op.drop_column('posts', 'veto_reason')
    op.drop_column('posts', 'graded_at')
    op.drop_column('posts', 'examen_mode')
