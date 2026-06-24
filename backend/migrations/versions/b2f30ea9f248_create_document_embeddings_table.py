"""create document_embeddings table

Revision ID: b2f30ea9f248
Revises: b18ca1779f63
Create Date: 2026-06-19 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2f30ea9f248'
down_revision: Union[str, Sequence[str], None] = 'b18ca1779f63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'document_embeddings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['expert_documents.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id')
    )
    op.create_index(
        op.f('ix_document_embeddings_id'),
        'document_embeddings', ['id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_document_embeddings_id'),
        table_name='document_embeddings'
    )
    op.drop_table('document_embeddings')