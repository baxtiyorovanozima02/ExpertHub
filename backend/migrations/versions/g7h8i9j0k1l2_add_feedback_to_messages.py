"""add feedback to messages

Revision ID: g7h8i9j0k1l2
Revises: F6b8c2a4e7d3
Create Date: 2026-06-25

"""
from alembic import op
import sqlalchemy as sa

revision = 'g7h8i9j0k1l2'
down_revision = 'F6b8c2a4e7d3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'messages',
        sa.Column('feedback', sa.SmallInteger(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('messages', 'feedback')