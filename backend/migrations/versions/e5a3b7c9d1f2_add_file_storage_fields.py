"""add file storage fields to expert_documents

Revision ID: e5a3b7c9d1f2
Revises: d4f2a8c6b3e1
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5a3b7c9d1f2'
down_revision: Union[str, Sequence[str], None] = 'd4f2a8c6b3e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

document_file_type_enum = sa.Enum(
    'text', 'document', 'image', 'audio',
    name='documentfiletype',
)


def upgrade() -> None:
    """Upgrade schema."""
    document_file_type_enum.create(op.get_bind(), checkfirst=True)


    op.alter_column('expert_documents', 'content', existing_type=sa.String(), nullable=True)

    op.add_column(
        'expert_documents',
        sa.Column('file_type', document_file_type_enum, nullable=False, server_default='text'),
    )
    op.add_column('expert_documents', sa.Column('file_object_name', sa.String(), nullable=True))
    op.add_column('expert_documents', sa.Column('original_filename', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('expert_documents', 'original_filename')
    op.drop_column('expert_documents', 'file_object_name')
    op.drop_column('expert_documents', 'file_type')
    op.alter_column('expert_documents', 'content', existing_type=sa.String(), nullable=False)
    document_file_type_enum.drop(op.get_bind(), checkfirst=True)