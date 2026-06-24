"""drop document_embeddings table (vector storage moved to Qdrant)

Revision ID: f6b8c2a4e7d3
Revises: e5a3b7c9d1f2
Create Date: 2026-06-23 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f6b8c2a4e7d3'
down_revision: Union[str, Sequence[str], None] = 'e5a3b7c9d1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(
        op.f('ix_document_embeddings_id'),
        table_name='document_embeddings'
    )
    op.drop_table('document_embeddings')


def downgrade() -> None:
    op.create_table(
        'document_embeddings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chunk_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chunk_id')
    )
    op.create_index(
        op.f('ix_document_embeddings_id'),
        'document_embeddings', ['id'], unique=False
    )