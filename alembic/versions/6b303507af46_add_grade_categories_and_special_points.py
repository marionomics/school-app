"""Add grade categories and special points

Revision ID: 6b303507af46
Revises: 76b15023e039
Create Date: 2026-02-05 17:32:07.369048

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b303507af46'
down_revision: Union[str, Sequence[str], None] = '76b15023e039'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create new tables
    op.create_table('grade_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('class_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('class_id', 'name', name='unique_class_category')
    )
    op.create_index(op.f('ix_grade_categories_id'), 'grade_categories', ['id'], unique=False)

    op.create_table('special_points',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('class_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=20), nullable=False),
        sa.Column('opted_in', sa.Boolean(), nullable=False),
        sa.Column('awarded', sa.Boolean(), nullable=False),
        sa.Column('points_value', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'class_id', 'category', name='unique_student_class_special')
    )
    op.create_index(op.f('ix_special_points_id'), 'special_points', ['id'], unique=False)

    # Use batch mode for SQLite ALTER TABLE limitations
    with op.batch_alter_table('grades', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('name', sa.String(length=100), nullable=True))
        batch_op.alter_column('category',
            existing_type=sa.VARCHAR(length=50),
            nullable=True)
        batch_op.create_foreign_key('fk_grades_category_id', 'grade_categories', ['category_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Use batch mode for SQLite ALTER TABLE limitations
    with op.batch_alter_table('grades', schema=None) as batch_op:
        batch_op.drop_constraint('fk_grades_category_id', type_='foreignkey')
        batch_op.alter_column('category',
            existing_type=sa.VARCHAR(length=50),
            nullable=False)
        batch_op.drop_column('name')
        batch_op.drop_column('category_id')

    op.drop_index(op.f('ix_special_points_id'), table_name='special_points')
    op.drop_table('special_points')
    op.drop_index(op.f('ix_grade_categories_id'), table_name='grade_categories')
    op.drop_table('grade_categories')
