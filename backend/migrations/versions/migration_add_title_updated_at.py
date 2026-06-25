# migrations/versions/a1b2c3d4e5f6_add_title_and_updated_at_to_conversations.py
"""add title and updated_at to conversations

Revision ID: a1b2c3d4e5f6
Revises: c3a1f5e7d9b2
Create Date: 2026-06-25

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c3a1f5e7d9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'conversations',
        sa.Column('title', sa.String(), nullable=True),
    )
    op.add_column(
        'conversations',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index('ix_conversations_updated_at', 'conversations', ['updated_at'])
    op.create_index('ix_conversations_title', 'conversations', ['title'])


def downgrade() -> None:
    op.drop_index('ix_conversations_title', table_name='conversations')
    op.drop_index('ix_conversations_updated_at', table_name='conversations')
    op.drop_column('conversations', 'updated_at')
    op.drop_column('conversations', 'title')