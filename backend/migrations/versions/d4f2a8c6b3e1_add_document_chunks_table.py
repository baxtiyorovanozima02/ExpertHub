"""add document_chunks table and switch embeddings to chunk_id

Revision ID: d4f2a8c6b3e1
Revises: c3a1f5e7d9b2
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd4f2a8c6b3e1'
down_revision: Union[str, Sequence[str], None] = 'c3a1f5e7d9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True
        ),
        sa.ForeignKeyConstraint(['document_id'], ['expert_documents.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_document_chunks_id'),
        'document_chunks', ['id'], unique=False
    )

    # document_embeddings jadvalini chunk_id ga o'tkazish
    op.execute("DELETE FROM document_embeddings")

    op.drop_constraint(
        'document_embeddings_document_id_fkey',
        'document_embeddings', type_='foreignkey'
    )
    op.drop_constraint(
        'document_embeddings_document_id_key',
        'document_embeddings', type_='unique'
    )
    op.drop_column('document_embeddings', 'document_id')

    op.add_column(
        'document_embeddings',
        sa.Column('chunk_id', sa.Integer(), nullable=False)
    )
    op.create_foreign_key(
        'document_embeddings_chunk_id_fkey',
        'document_embeddings', 'document_chunks',
        ['chunk_id'], ['id'],
    )
    op.create_unique_constraint(
        'document_embeddings_chunk_id_key',
        'document_embeddings', ['chunk_id']
    )


def downgrade() -> None:
    op.drop_constraint(
        'document_embeddings_chunk_id_key',
        'document_embeddings', type_='unique'
    )
    op.drop_constraint(
        'document_embeddings_chunk_id_fkey',
        'document_embeddings', type_='foreignkey'
    )
    op.drop_column('document_embeddings', 'chunk_id')

    op.add_column(
        'document_embeddings',
        sa.Column('document_id', sa.Integer(), nullable=False)
    )
    op.create_foreign_key(
        'document_embeddings_document_id_fkey',
        'document_embeddings', 'expert_documents',
        ['document_id'], ['id'],
    )
    op.create_unique_constraint(
        'document_embeddings_document_id_key',
        'document_embeddings', ['document_id']
    )

    op.drop_index(
        op.f('ix_document_chunks_id'),
        table_name='document_chunks'
    )
    op.drop_table('document_chunks')