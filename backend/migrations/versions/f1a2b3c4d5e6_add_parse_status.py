"""add parse_status and parse_error to expert_documents

Revision ID: f1a2b3c4d5e6
Revises: e5a3b7c9d1f2
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

revision = 'f1a2b3c4d5e6'
down_revision = 'e5a3b7c9d1f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'expert_documents',
        sa.Column(
            'parse_status',
            sa.String(length=20),
            nullable=True,
            server_default='pending',
            comment='pending | done | error'
        )
    )
    op.add_column(
        'expert_documents',
        sa.Column(
            'parse_error',
            sa.Text(),
            nullable=True,
            comment='Xato xabari (parse_status=error bo\'lsa)'
        )
    )


def downgrade() -> None:
    op.drop_column('expert_documents', 'parse_error')
    op.drop_column('expert_documents', 'parse_status')